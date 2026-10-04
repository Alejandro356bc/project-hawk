"""Vote parsing and vote arithmetic.

Deliberately free of UI, provider, and network imports: these are the rules that
decide what a debate concluded, so they are pure functions that a unit test can
pin down. ``ui_layout`` renders what this module computes; it does not decide.

Two failure modes drove the parser's shape, both observed against real panelist
prose:

* **Substring bleed.** The previous check asked ``"no" in vote`` before it asked
  about "abstain", so ``VOTE: Abstain - not enough context`` matched on the "no"
  inside "not" and was tallied as a *Reject*. Every keyword test here is a
  word-boundary regex against a captured ballot token, never a substring scan of
  free text.
* **Quoted ballots.** Round 2+ prompts ask panelists to critique each other's
  votes, so a response routinely contains someone else's ``VOTE:`` line before
  its own. Taking the *first* match therefore recorded the wrong panelist's
  vote. Resolution order below prefers a ballot on its own line and, among
  equals, takes the LAST one -- which is where the instructions say a panelist's
  own vote goes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping

# Cast ballots.
APPROVE = "Approve"
REJECT = "Reject"
ABSTAIN = "Abstain"
# NOT a ballot: the panelist never answered, or answered with nothing parseable.
# Kept distinct from ABSTAIN on purpose -- an abstention is a panelist declining
# to decide, silence is a panelist who was never heard, and collapsing the two
# lets a timeout read as a considered neutral position.
NO_VOTE = "No Vote"

# Transient UI states, before a ballot exists.
PENDING = "Voting..."
THINKING = "Thinking..."

# Outcomes.
APPROVED = "APPROVED"
REJECTED = "REJECTED"
NO_CONSENSUS = "NO CONSENSUS"

_BALLOTS: Dict[str, str] = {"approve": APPROVE, "reject": REJECT, "abstain": ABSTAIN}

_KEYWORDS = "approve|reject|abstain"

# A ballot on its own line -- the format the vote instructions demand. The
# allowed prefix covers list bullets and bold markers but deliberately EXCLUDES
# ">", so a markdown-quoted ballot from another panelist cannot win here.
_ANCHORED = re.compile(
    rf"^[ \t*_+-]*\**\s*VOTE:\s*\**\s*({_KEYWORDS})\b",
    re.IGNORECASE | re.MULTILINE,
)
# A ballot anywhere, including inline and quoted.
_INLINE = re.compile(rf"VOTE:\s*\**\s*({_KEYWORDS})\b", re.IGNORECASE)
# Prose forms: "I vote to approve", "voted reject".
_PHRASE = re.compile(
    rf"\b(?:vote|votes|voting|voted)\s+(?:to|is|for)?\s*\**\s*({_KEYWORDS})\b",
    re.IGNORECASE,
)
# Last-ditch: a bare keyword in the closing text.
_BARE = re.compile(rf"\b({_KEYWORDS})\b", re.IGNORECASE)

# How much of the tail the bare-keyword fallback may consider.
TAIL_CHARS = 300


def parse_vote(text: str) -> str:
    """The ballot a panelist cast, or ``NO_VOTE`` if it cast none.

    Resolution order, most explicit first; within each pattern the LAST match
    wins, because the instructions put a panelist's own vote on its final line
    and anything earlier is likely a quotation of a peer.
    """
    if not text or not text.strip():
        return NO_VOTE
    for pattern, haystack in (
        (_ANCHORED, text),
        (_INLINE, text),
        (_PHRASE, text),
        (_BARE, text[-TAIL_CHARS:]),
    ):
        found = pattern.findall(haystack)
        if found:
            return _BALLOTS[found[-1].lower()]
    return NO_VOTE


def tally(votes: Iterable[str]) -> Dict[str, int]:
    """Count ballots into the four buckets. Anything still pending counts as
    ``No Vote``: a debate that ended with a panelist mid-sentence did not
    receive that panelist's opinion, and must not be scored as though it did."""
    counts = {APPROVE: 0, REJECT: 0, ABSTAIN: 0, NO_VOTE: 0}
    for vote in votes:
        counts[vote if vote in counts else NO_VOTE] += 1
    return counts


def format_tally(counts: Mapping[str, int], prefix: str = "Tally") -> str:
    """Render a tally for the status bar. ``No Vote`` is shown only when it
    happened -- but it is never hidden when it did."""
    text = (
        f"{prefix}: {counts[APPROVE]} Approve | "
        f"{counts[REJECT]} Reject | {counts[ABSTAIN]} Abstain"
    )
    if counts.get(NO_VOTE):
        text += f" | {counts[NO_VOTE]} No Vote"
    return text


@dataclass(frozen=True)
class Decision:
    """What the panel actually decided, computed from the ballots rather than
    narrated by a model. ``provisional`` marks an outcome reached while some
    panelist was never heard from."""

    outcome: str
    counts: Dict[str, int]
    provisional: bool
    reason: str

    @property
    def headline(self) -> str:
        return f"{self.outcome} (PROVISIONAL)" if self.provisional else self.outcome

    def summary(self) -> str:
        return f"{self.headline} -- {format_tally(self.counts, 'final')} -- {self.reason}"


def decide(counts: Mapping[str, int]) -> Decision:
    """Turn a tally into an outcome.

    The rules, stated so they can be argued with:

    * Only Approve and Reject are decisive. Abstain and No Vote are recorded and
      displayed but never counted as agreement.
    * A strict majority of the decisive ballots wins. A tie is NO CONSENSUS, not
      a pass -- a split panel has not agreed on anything.
    * An approval reached while a panelist was never heard is PROVISIONAL. The
      outcome still stands; it is labelled so nobody reads a timeout as assent.
    """
    approve = counts.get(APPROVE, 0)
    reject = counts.get(REJECT, 0)
    abstain = counts.get(ABSTAIN, 0)
    silent = counts.get(NO_VOTE, 0)
    cast = approve + reject
    full = dict({APPROVE: approve, REJECT: reject, ABSTAIN: abstain, NO_VOTE: silent})

    if cast == 0:
        missing = [
            label for count, label in ((abstain, f"{abstain} abstained"),
                                       (silent, f"{silent} never voted")) if count
        ]
        return Decision(
            NO_CONSENSUS, full, False,
            "no panelist cast a decisive vote"
            + (f" ({', '.join(missing)})" if missing else ""),
        )
    if approve == reject:
        return Decision(NO_CONSENSUS, full, False, f"the panel split {approve}-{reject}")
    if approve > reject:
        return Decision(
            APPROVED, full, silent > 0,
            f"{approve} of {cast} decisive votes approved"
            + (f"; {silent} panelist(s) never voted" if silent else ""),
        )
    return Decision(
        REJECTED, full, False,
        f"{reject} of {cast} decisive votes rejected",
    )
