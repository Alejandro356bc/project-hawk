import asyncio
import logging
import os
from typing import Dict, List, Tuple

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid
from textual.widgets import RichLog, Static

from quorum.models.schemas import Message
from quorum.prompts import append_vote_instructions, build_debate_system_prompt
from quorum.providers.base import BaseProvider
from quorum.voting import (
    NO_VOTE,
    PENDING,
    THINKING,
    Decision,
    decide,
    format_tally,
    parse_vote,
    tally,
)

log = logging.getLogger("quorum.ui")

def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default

_CLIENT_TIMEOUT_SEC = max(30.0, _env_float("QUORUM_CLIENT_TIMEOUT_SEC", 150.0))

# Map Rich color names to CSS hex colors for Textual borders
COLOR_MAP = {
    "magenta": "#ff55ff",
    "white":   "#cccccc",
    "cyan":    "#00ddff",
    "yellow":  "#ffdd00",
    "blue":    "#4488ff",
    "green":   "#00cc66",
    "red":     "#ff4444",
}

class QuorumDebateApp(App[None]):
    """Full-screen Textual app for the quorum debate with individually
    scrollable, auto-scrolling model panes and live voting metrics."""

    CSS = """
    Screen {
        background: #0a0a0f;
    }

    #debate-header {
        dock: top;
        height: 3;
        content-align: center middle;
        background: #cc0000;
        color: #ffffff;
        text-style: bold;
        width: 100%;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: #1a1a2e;
        color: #666688;
        content-align: center middle;
    }

    #grid {
        grid-size: 3;
        grid-gutter: 1;
        padding: 1;
        height: 1fr;
    }

    .model-pane {
        height: 1fr;
        min-height: 6;
        border: solid #333344;
        background: #0e0e18;
        scrollbar-size-vertical: 1;
        scrollbar-color: #333344;
        scrollbar-color-hover: #6666aa;
        scrollbar-color-active: #aaaaff;
        text-wrap: wrap;
        overflow-x: hidden;
    }
    """

    BINDINGS = [
        Binding("q", "quit_app", "Continue", show=True),
        Binding("escape", "quit_app", "Continue", show=False),
    ]

    def __init__(
        self,
        clients: List[BaseProvider],
        num_rounds: int,
        initial_prompt: str,
    ) -> None:
        super().__init__()
        self.clients = clients
        self.num_rounds = num_rounds
        self.initial_prompt = initial_prompt
        self.responses: Dict[str, str] = {c.name: "" for c in clients}
        self.votes: Dict[str, str] = {c.name: PENDING for c in clients}

        # Pre-compute widget IDs (Textual IDs must be CSS-safe)
        self._ids: Dict[str, Dict[str, str]] = {}
        for c in clients:
            safe = c.name.replace(" ", "-").replace(".", "-").lower()
            self._ids[c.name] = {
                "pane": f"pane-{safe}",
            }

        # Results handed back to caller after the app exits
        self.result_responses: Dict[str, str] = {}
        self.result_history: str = ""
        # The panel's decision, computed from ballots by quorum.voting. Set on
        # every exit path -- including an early quit -- so main.py never has to
        # guess what a half-finished debate concluded.
        self.result_decision: Decision = decide(tally(self.votes.values()))
        self._debate_done = False

    # -- Layout ------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static(
            " QUORUM DEBATE - ROUND 1 ", id="debate-header"
        )

        with Grid(id="grid"):
            for client in self.clients:
                ids = self._ids[client.name]
                pane = RichLog(
                    highlight=False,
                    auto_scroll=True,
                    wrap=True,
                    min_width=0,
                    id=ids["pane"],
                    classes="model-pane"
                )
                pane.border_title = f" @{client.name} "
                yield pane

        yield Static(
            " Streaming... | Scroll panes with mouse wheel | Press Q when done ",
            id="status-bar",
        )

    def on_mount(self) -> None:
        # Apply border colours
        for client in self.clients:
            ids = self._ids[client.name]
            color = COLOR_MAP.get(client.color, "#00cc66")

            pane = self.query_one(f"#{ids['pane']}", RichLog)
            pane.styles.border = ("solid", color)
            pane.border_title = f" @{client.name} "

        # Adapt the grid column count to the number of models
        cols = min(len(self.clients), 3) if self.clients else 1
        self.query_one("#grid", Grid).styles.grid_size_columns = cols

        # Fire off the debate
        self._run_debate()

    # -- Vote tallying -----------------------------------------------------

    def _tally_votes(self) -> Dict[str, int]:
        """Count the current ballots. The rules live in quorum.voting so they
        can be tested without standing up a Textual app."""
        return tally(self.votes.values())

    # -- Debate orchestration ----------------------------------------------

    @work(exclusive=True, thread=False)
    async def _run_debate(self) -> None:
        history = self.initial_prompt

        for round_num in range(1, self.num_rounds + 1):
            # Header
            try:
                self.query_one("#debate-header", Static).update(
                    f" QUORUM DEBATE - ROUND {round_num} OF {self.num_rounds} "
                )
            except Exception:
                pass

            # Reset panes and votes
            for c in self.clients:
                self.responses[c.name] = ""
                self.votes[c.name] = THINKING
                try:
                    pane = self.query_one(f"#{self._ids[c.name]['pane']}", RichLog)
                    pane.clear()
                    pane.border_title = f" @{c.name} [Thinking...] "
                except Exception:
                    pass

            log.info(f"=== ROUND {round_num} START ===")
            await asyncio.gather(
                *(self._stream_client_with_timeout(c, history, round_num) for c in self.clients)
            )
            log.info(f"=== ROUND {round_num} COMPLETE ===")

            # Calculate vote tally
            counts = self._tally_votes()
            tally_str = format_tally(counts, "Tally")

            try:
                self.query_one("#status-bar", Static).update(
                    f" Round {round_num} Complete | {tally_str} | Scroll to review "
                )
            except Exception:
                pass

            # Build transcript for the next round
            history += f"\n\n--- ROUND {round_num} TRANSCRIPT (VOTES CAST: {tally_str}) ---\n"
            for c in self.clients:
                # "[voted: X]" rather than "VOTE: X" ON PURPOSE. This transcript is
                # fed back to every panelist next round, and a model that echoes a
                # peer's line verbatim would otherwise be quoting a well-formed
                # ballot into its own response, where the parser has to guess whose
                # it was. Keeping the wire format out of the transcript removes the
                # ambiguity at the source instead of parsing around it.
                history += f"@{c.name} [voted: {self.votes[c.name]}]: {self.responses[c.name]}\n\n"

            if round_num < self.num_rounds:
                history += (
                    "Please review and critique the other panelists' positions, votes, and arguments "
                    "from the previous round. Work towards consensus by adjusting your vote/solution if convinced."
                )
                await asyncio.sleep(4)

        # -- Done ----------------------------------------------------------
        self.result_responses = dict(self.responses)
        self.result_history = history
        self._debate_done = True

        # THE OUTCOME IS COMPUTED, NOT NARRATED. The synthesizer downstream is
        # itself a panelist, so if prose were the only verdict a model that lost
        # the vote could still write the "consensus". decide() settles it from
        # the ballots first, and the synthesizer is told what it may not
        # contradict.
        decision = decide(self._tally_votes())
        self.result_decision = decision

        try:
            self.query_one("#debate-header", Static).update(
                f" DEBATE COMPLETE - {decision.headline} - "
                f"{format_tally(decision.counts, 'Final')} "
            )
            self.query_one("#status-bar", Static).update(
                f" {decision.reason} | Press Q to proceed to Synthesis "
            )
        except Exception:
            pass
        log.info(f"Debate complete - {decision.summary()} - waiting for user to press Q")

    # -- Per-model streaming -----------------------------------------------

    async def _stream_client_with_timeout(
        self, client: BaseProvider, prompt: str, round_num: int
    ) -> None:
        try:
            await asyncio.wait_for(
                self._stream_client(client, prompt, round_num),
                timeout=_CLIENT_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            # RECORDED AS NO VOTE, NOT ABSTAIN. A panelist that never answered
            # did not weigh in and decline to decide -- it was never heard. An
            # abstention is a position; silence is missing data, and scoring it
            # as a neutral ballot lets a timeout pass for considered assent.
            msg = (
                f"\n[Timed out after {_CLIENT_TIMEOUT_SEC:g}s in round {round_num}; "
                "continuing without this panelist. Recorded as No Vote, not an "
                "abstention.]\n"
            )
            log.warning(f"[{client.name}] {msg.strip()}")
            self.responses[client.name] += msg
            self.votes[client.name] = NO_VOTE
            try:
                pane = self.query_one(f"#{self._ids[client.name]['pane']}", RichLog)
                pane.write(msg)
                pane.border_title = f" @{client.name} [{NO_VOTE}] "
            except Exception:
                pass

    async def _stream_client(
        self, client: BaseProvider, prompt: str, round_num: int
    ) -> None:
        panelist_names = ", ".join(
            f"@{c.name}" for c in self.clients if c.name != client.name
        )
        cwd = os.getcwd()

        system_prompt = build_debate_system_prompt(
            panelist_names, cwd, client.uses_custom_tools
        )
        # Vote instructions ride in the user prompt so they reach CLI providers,
        # which ignore the per-call system prompt.
        user_prompt = append_vote_instructions(prompt)

        try:
            async for chunk in client.async_stream_response(
                system_prompt, [Message(role="user", content=user_prompt)]
            ):
                self.responses[client.name] += chunk
                try:
                    self.query_one(f"#{self._ids[client.name]['pane']}", RichLog).write(chunk)
                except Exception:
                    pass

        except Exception as e:
            log.error(
                f"[{client.name}] Streaming error: {e}", exc_info=True
            )
            err_msg = f"\n[Error: {e}]"
            self.responses[client.name] += err_msg
            try:
                self.query_one(f"#{self._ids[client.name]['pane']}", RichLog).write(err_msg)
            except Exception:
                pass

        # ONE PARSER, IN quorum.voting. This used to be ~35 lines of inline
        # regex and substring checks whose failures were invisible: "VOTE:
        # Abstain - not enough context" tallied as Reject (the "no" inside
        # "not"), and a response quoting a peer's ballot recorded that peer's
        # vote instead of its own. Both are pinned by tests/test_voting.py now.
        self.votes[client.name] = parse_vote(self.responses[client.name])

        # Update border title to show cast vote
        try:
            pane = self.query_one(f"#{self._ids[client.name]['pane']}", RichLog)
            pane.border_title = f" @{client.name} [{self.votes[client.name]}] "
        except Exception:
            pass

        log.info(
            f"[{client.name}] Done - Voted: {self.votes[client.name]} - "
            f"{len(self.responses[client.name])} chars total"
        )

    # -- Actions -----------------------------------------------------------

    def action_quit_app(self) -> None:
        # Save whatever we have so far (may be partial if mid-stream). The
        # decision is recomputed here too: quitting mid-debate leaves panelists
        # un-heard, and decide() scores those as No Vote, so an abandoned
        # debate reports NO CONSENSUS (or a PROVISIONAL result) rather than
        # inheriting the optimistic default.
        if not self._debate_done:
            self.result_responses = dict(self.responses)
            self.result_history = self.initial_prompt
            self.result_decision = decide(self._tally_votes())
        self.exit()

# -----------------------------------------------------------------------------
# Public wrapper - keeps the interface that main.py expects
# -----------------------------------------------------------------------------

class SpectacleQuorum:
    """Drop-in replacement consumed by main.py's ``run_quorum()``."""

    def __init__(self, clients: List[BaseProvider]):
        self.clients = clients

    async def run_rounds(
        self, initial_prompt: str, num_rounds: int
    ) -> Tuple[Dict[str, str], str, Decision]:
        """Returns the per-panelist responses, the transcript, and the panel's
        DECISION. The decision is third rather than derived by the caller so
        there is exactly one place that scores a debate."""
        app = QuorumDebateApp(self.clients, num_rounds, initial_prompt)
        await app.run_async()
        return app.result_responses, app.result_history, app.result_decision

