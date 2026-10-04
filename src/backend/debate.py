"""One round of a web panel debate: three panelists answer in parallel, vote,
and one of them writes the conclusion.

The rules are the CLI's: votes are read by ``hawk.voting.parse_vote`` and the
outcome is computed by ``hawk.voting.decide`` *before* the synthesizer writes,
so the conclusion reports the panel's decision rather than inventing one.

Keys arrive per request (resolved by the Next.js server) and are never stored or
logged. Base URLs are fixed here, never taken from the request, so the API can
only talk to the platforms listed below.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from hawk.models.schemas import Message
from hawk.prompts import (
    SYNTHESIZER_SYSTEM_PROMPT,
    append_vote_instructions,
    build_synthesis_prompt,
)
from hawk.providers.openai_provider import BaseOpenAIProvider, display_name_from_model
from hawk.voting import NO_VOTE, decide, format_tally, parse_vote, tally

log = logging.getLogger("hawk.backend.debate")

PANEL_SIZE = 3
MAX_ROUNDS = 3
SEAT_TIMEOUT_SEC = 150.0

# OpenAI-compatible endpoints for every platform the website offers.
BASE_URLS: Dict[str, str] = {
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "mistral": "https://api.mistral.ai/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "tokenharbor": "https://tokenharbor.ai/v1",
    "ollama": "https://ollama.com/v1",
    "claude": "https://api.anthropic.com/v1/",
    "codex": "https://api.openai.com/v1",
}

ProviderId = Literal["openrouter", "groq", "gemini", "mistral", "nvidia", "tokenharbor", "ollama", "claude", "codex"]


class Seat(BaseModel):
    provider: ProviderId
    model: str = Field(min_length=1, max_length=200)
    key: str = Field(min_length=1, max_length=512)


class PriorResponse(BaseModel):
    text: str = Field(max_length=40_000)
    vote: str = Field(max_length=20)


class PriorRound(BaseModel):
    responses: List[PriorResponse] = Field(min_length=PANEL_SIZE, max_length=PANEL_SIZE)


class RoundRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4_000)
    seats: List[Seat] = Field(min_length=PANEL_SIZE, max_length=PANEL_SIZE)
    previous: List[PriorRound] = Field(default_factory=list, max_length=MAX_ROUNDS - 1)


def debate_system_prompt(others: str) -> str:
    """The panelist prompt for the web: no tools, no filesystem."""
    return (
        "You are an expert panelist in a multi-model panel debate about a software or "
        f"engineering question. The other panelists are: {others}. "
        "You can address them directly using their @ names.\n\n"
        "Be concise but thorough: a focused answer of a few short paragraphs, with a "
        "clear recommendation. You cannot run code or read files; reason from the "
        "question and the other panelists' arguments.\n\n"
        "You will be asked to cast a vote at the end of your response."
    )


def build_round_prompt(question: str, names: List[str], previous: List[PriorRound]) -> str:
    """Same transcript format as the CLI (hawk.ui_layout): earlier rounds are
    fed back with "[voted: X]" (not "VOTE: X") so a model quoting a peer can't
    be mistaken for that peer's ballot."""
    history = question
    for number, prior in enumerate(previous, start=1):
        counts = tally(r.vote for r in prior.responses)
        history += f"\n\n--- ROUND {number} TRANSCRIPT (VOTES CAST: {format_tally(counts, 'Tally')}) ---\n"
        for name, response in zip(names, prior.responses):
            history += f"@{name} [voted: {response.vote}]: {response.text}\n\n"
    if previous:
        history += (
            "Please review and critique the other panelists' positions, votes, and arguments "
            "from the previous round. Work towards consensus by adjusting your vote/solution if convinced."
        )
    return history


RESTATE = "Open by restating the decision above verbatim."


def web_synthesis_prompt(question: str, rounds: int, transcript: str, decision_summary: str) -> str:
    """The CLI's synthesis prompt, minus "restate the decision verbatim": the
    website already shows the computed decision right above the conclusion."""
    prompt = build_synthesis_prompt(question, rounds, transcript, decision_summary)
    assert RESTATE in prompt, "hawk.prompts.build_synthesis_prompt changed; update web_synthesis_prompt"
    return prompt.replace(
        RESTATE,
        "The decision is already shown to the reader, so do not restate it; start with what the panel concluded.",
    )


def _client(seat: Seat, name: str) -> BaseOpenAIProvider:
    return BaseOpenAIProvider(
        name=name,
        model_name=seat.model,
        color="white",
        base_url=BASE_URLS[seat.provider],
        api_key=seat.key,
        uses_custom_tools=False,
    )


def _friendly_error(exc: BaseException) -> str:
    status = getattr(exc, "status_code", None)
    if status in (401, 403):
        return "The platform rejected the key for this model."
    if status == 404:
        return "This model isn't available on the platform (or for this key)."
    if status == 429:
        return "Rate limited by the platform. Try again in a minute."
    if isinstance(exc, asyncio.TimeoutError):
        return "The model took too long to answer."
    return "The model couldn't answer."


async def run_round(req: RoundRequest) -> AsyncGenerator[Dict[str, Any], None]:
    """Yield the events of one round. See ``RoundEvent`` in the frontend for the shapes."""
    round_number = len(req.previous) + 1
    names = [display_name_from_model(s.model) for s in req.seats]
    # Two seats can run the same model; keep their @names distinct.
    names = [f"{n} ({i + 1})" if names.count(n) > 1 else n for i, n in enumerate(names)]
    prompt = append_vote_instructions(build_round_prompt(req.question, names, req.previous))

    yield {"type": "start", "round": round_number}

    queue: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue()
    texts = [""] * PANEL_SIZE
    votes = [NO_VOTE] * PANEL_SIZE
    failed = [False] * PANEL_SIZE

    async def speak(i: int) -> None:
        others = ", ".join(f"@{n}" for j, n in enumerate(names) if j != i)
        client = _client(req.seats[i], names[i])

        async def stream() -> None:
            async for kind, chunk in client.stream_text(debate_system_prompt(others), [Message(role="user", content=prompt)]):
                if kind == "text":
                    texts[i] += chunk
                    await queue.put({"type": "delta", "seat": i, "text": chunk})
                else:
                    await queue.put({"type": "wait", "seat": i, "text": chunk})

        try:
            await asyncio.wait_for(stream(), timeout=SEAT_TIMEOUT_SEC)
            votes[i] = parse_vote(texts[i])
        except Exception as exc:  # noqa: BLE001 - every failure becomes a visible "No Vote"
            log.warning("seat %s (%s/%s) failed: %s", i, req.seats[i].provider, req.seats[i].model, type(exc).__name__)
            failed[i] = True
            votes[i] = NO_VOTE
            await queue.put({"type": "error", "seat": i, "message": _friendly_error(exc)})
        await queue.put({"type": "vote", "seat": i, "vote": votes[i]})
        await queue.put(None)

    tasks = [asyncio.create_task(speak(i)) for i in range(PANEL_SIZE)]
    try:
        finished = 0
        while finished < PANEL_SIZE:
            event = await queue.get()
            if event is None:
                finished += 1
            else:
                yield event
    finally:
        for task in tasks:
            task.cancel()

    # THE OUTCOME IS COMPUTED, NOT NARRATED (same rule as the CLI).
    counts = tally(votes)
    decision = decide(counts)
    yield {
        "type": "decision",
        "counts": counts,
        "outcome": decision.outcome,
        "headline": decision.headline,
        "reason": decision.reason,
        "provisional": decision.provisional,
    }

    # The first panelist that actually answered writes the conclusion.
    writer = next((i for i in range(PANEL_SIZE) if not failed[i] and texts[i].strip()), None)
    if writer is None:
        yield {"type": "verdict_error", "message": "No panelist answered, so there is no conclusion."}
        yield {"type": "done"}
        return

    transcript = build_round_prompt(
        req.question,
        names,
        [*req.previous, PriorRound(responses=[PriorResponse(text=t, vote=v) for t, v in zip(texts, votes)])],
    )
    synthesis = web_synthesis_prompt(req.question, round_number, transcript, decision.summary())
    yield {"type": "verdict_start", "seat": writer}
    try:
        client = _client(req.seats[writer], names[writer])

        async def write() -> AsyncGenerator[str, None]:
            async for kind, chunk in client.stream_text(SYNTHESIZER_SYSTEM_PROMPT, [Message(role="user", content=synthesis)]):
                if kind == "text":
                    yield chunk

        async for chunk in write():
            yield {"type": "verdict_delta", "text": chunk}
    except Exception as exc:  # noqa: BLE001
        log.warning("synthesis by seat %s failed: %s", writer, type(exc).__name__)
        yield {"type": "verdict_error", "message": _friendly_error(exc)}
    yield {"type": "done"}
