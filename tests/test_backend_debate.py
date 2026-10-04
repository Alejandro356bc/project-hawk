"""Web debate rounds (backend.debate) with the model calls faked."""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import debate
from backend.main import app
from hawk.providers.openai_provider import BaseOpenAIProvider

ANSWERS = {
    "model-a": "Keep sessions.\nVOTE: Approve",
    "model-b": "Use JWT.\nVOTE: Reject",
    "model-c": "Sessions, hardened.\nVOTE: Approve",
}


def _seats(*models: str) -> List[Dict[str, str]]:
    return [{"provider": "groq", "model": m, "key": "k"} for m in models]


@pytest.fixture
def fake_models(monkeypatch: pytest.MonkeyPatch) -> List[Dict[str, Any]]:
    """Each model streams its canned answer in two chunks; the synthesizer streams a summary."""
    calls: List[Dict[str, Any]] = []

    async def fake_stream(self: BaseOpenAIProvider, system_prompt: str, messages: list) -> AsyncGenerator[tuple[str, str], None]:
        calls.append({"model": self.model_name, "system": system_prompt, "user": messages[0].content})
        if system_prompt == debate.SYNTHESIZER_SYSTEM_PROMPT:
            yield ("text", "APPROVED. ")
            yield ("text", "Keep sessions.")
            return
        if self.model_name == "broken":
            raise RuntimeError("boom")
        text = ANSWERS[self.model_name]
        half = len(text) // 2
        yield ("text", text[:half])
        yield ("text", text[half:])

    monkeypatch.setattr(BaseOpenAIProvider, "stream_text", fake_stream)
    return calls


async def _collect(req: debate.RoundRequest) -> List[Dict[str, Any]]:
    return [event async for event in debate.run_round(req)]


async def test_round_streams_votes_decision_and_verdict(fake_models: List[Dict[str, Any]]) -> None:
    req = debate.RoundRequest(question="JWT or sessions?", seats=_seats("model-a", "model-b", "model-c"))
    events = await _collect(req)

    assert events[0] == {"type": "start", "round": 1}
    text = {i: "".join(e["text"] for e in events if e["type"] == "delta" and e["seat"] == i) for i in range(3)}
    assert text[1] == ANSWERS["model-b"]
    votes = {e["seat"]: e["vote"] for e in events if e["type"] == "vote"}
    assert votes == {0: "Approve", 1: "Reject", 2: "Approve"}

    decision = next(e for e in events if e["type"] == "decision")
    assert decision["outcome"] == "APPROVED"
    assert decision["counts"]["Approve"] == 2

    assert next(e for e in events if e["type"] == "verdict_start")["seat"] == 0
    assert "".join(e["text"] for e in events if e["type"] == "verdict_delta") == "APPROVED. Keep sessions."
    assert events[-1] == {"type": "done"}
    # The decision is computed before the synthesizer is called, and handed to it.
    synth = next(c for c in fake_models if c["system"] == debate.SYNTHESIZER_SYSTEM_PROMPT)
    assert synth["user"].startswith("PANEL DECISION")


async def test_failed_model_is_no_vote_not_abstain(fake_models: List[Dict[str, Any]]) -> None:
    req = debate.RoundRequest(question="Q?", seats=_seats("model-a", "broken", "model-c"))
    events = await _collect(req)

    assert any(e["type"] == "error" and e["seat"] == 1 for e in events)
    votes = {e["seat"]: e["vote"] for e in events if e["type"] == "vote"}
    assert votes[1] == "No Vote"
    decision = next(e for e in events if e["type"] == "decision")
    assert decision["provisional"] is True


async def test_later_rounds_see_the_transcript(fake_models: List[Dict[str, Any]]) -> None:
    previous = [{"responses": [{"text": "Old A", "vote": "Approve"}, {"text": "Old B", "vote": "Reject"}, {"text": "Old C", "vote": "Abstain"}]}]
    req = debate.RoundRequest(question="Q?", seats=_seats("model-a", "model-b", "model-c"), previous=previous)
    events = await _collect(req)

    assert events[0] == {"type": "start", "round": 2}
    panelist_prompt = next(c for c in fake_models if c["model"] == "model-a" and c["system"] != debate.SYNTHESIZER_SYSTEM_PROMPT)["user"]
    assert "--- ROUND 1 TRANSCRIPT" in panelist_prompt
    assert "[voted: Reject]: Old B" in panelist_prompt
    assert "VOTE: Reject" not in panelist_prompt.split("---\nIMPORTANT")[0]


def test_panel_must_have_exactly_three_seats() -> None:
    with pytest.raises(ValidationError):
        debate.RoundRequest(question="Q?", seats=_seats("model-a", "model-b"))
    with pytest.raises(ValidationError):
        debate.RoundRequest(question="Q?", seats=_seats("a", "b", "c", "d"))


def test_unknown_platform_is_rejected() -> None:
    seats = _seats("a", "b", "c")
    seats[0]["provider"] = "example.com"
    with pytest.raises(ValidationError):
        debate.RoundRequest(question="Q?", seats=seats)


def test_endpoint_streams_server_sent_events(fake_models: List[Dict[str, Any]]) -> None:
    client = TestClient(app)
    res = client.post("/debate/round", json={"question": "Q?", "seats": _seats("model-a", "model-b", "model-c")})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    lines = [line for line in res.text.splitlines() if line.startswith("data: ")]
    assert lines[0] == 'data: {"type": "start", "round": 1}'
    assert lines[-1] == 'data: {"type": "done"}'
