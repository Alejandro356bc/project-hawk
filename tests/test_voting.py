"""Tests for ballot parsing and quorum arithmetic.

The first two parsing tests below pin the bugs this module was extracted to fix.
They were found by running the previous inline parser (ui_layout.py) against
realistic panelist prose, and each one silently recorded the WRONG vote in a
tally the user was reading as fact:

* an Abstain whose trailing words contained "not" was scored as a Reject,
  because "no" was tested as a substring before "abstain" was tested at all;
* a response quoting a peer's ballot before casting its own was scored with the
  PEER's vote, because the first ``VOTE:`` match in the text won.
"""

from quorum.voting import (
    ABSTAIN,
    APPROVE,
    APPROVED,
    NO_CONSENSUS,
    NO_VOTE,
    REJECT,
    REJECTED,
    decide,
    format_tally,
    parse_vote,
    tally,
)

# -- Parsing ------------------------------------------------------------------

def test_abstain_with_no_bearing_words_is_not_a_reject() -> None:
    """'not' contains 'no'. The old parser turned this Abstain into a Reject."""
    assert parse_vote("VOTE: Abstain - not enough context to judge") == ABSTAIN
    assert parse_vote("VOTE: Abstain\nI do not know this codebase well.") == ABSTAIN
    assert parse_vote("VOTE: Abstain (none of the options are load-bearing)") == ABSTAIN


def test_quoted_peer_ballot_does_not_win() -> None:
    """Round 2+ asks panelists to critique each other's votes, so a response
    routinely contains a peer's ballot before its own. The panelist's OWN vote
    is the one on its own line, last."""
    text = (
        "@gpt wrote VOTE: Reject last round, but I disagree with the reasoning.\n"
        "The migration is reversible.\n"
        "VOTE: Approve"
    )
    assert parse_vote(text) == APPROVE


def test_markdown_quoted_ballot_is_not_the_panelists_own() -> None:
    text = "VOTE: Approve\n\n> @gemini said VOTE: Reject"
    assert parse_vote(text) == APPROVE


def test_plain_ballots() -> None:
    assert parse_vote("Looks correct.\nVOTE: Approve") == APPROVE
    assert parse_vote("This breaks auth.\nVOTE: Reject") == REJECT
    assert parse_vote("VOTE: Abstain") == ABSTAIN


def test_formatting_variants() -> None:
    assert parse_vote("**VOTE: Approve**") == APPROVE
    assert parse_vote("- VOTE: reject") == REJECT
    assert parse_vote("vote: APPROVE") == APPROVE
    assert parse_vote("VOTE:Approve") == APPROVE


def test_prose_vote_forms() -> None:
    assert parse_vote("After review I vote to approve this change.") == APPROVE
    assert parse_vote("I voted reject in round 1 and stand by it.") == REJECT


def test_negation_before_the_ballot_does_not_flip_it() -> None:
    """The ballot line is authoritative; prose above it is not re-interpreted."""
    assert parse_vote("I cannot approve this design.\nVOTE: Reject") == REJECT


def test_missing_or_empty_response_is_no_vote_not_abstain() -> None:
    assert parse_vote("") == NO_VOTE
    assert parse_vote("   \n  ") == NO_VOTE
    assert parse_vote("The build is broken and I ran out of time.") == NO_VOTE


def test_tail_fallback_takes_the_last_keyword() -> None:
    assert parse_vote("I reject the first option. On balance: approve.") == APPROVE


# -- Tally --------------------------------------------------------------------

def test_tally_buckets_unknown_states_as_no_vote() -> None:
    counts = tally([APPROVE, REJECT, ABSTAIN, "Thinking...", "Voting...", "???"])
    assert counts == {APPROVE: 1, REJECT: 1, ABSTAIN: 1, NO_VOTE: 3}


def test_format_tally_hides_empty_no_vote_but_never_a_real_one() -> None:
    assert "No Vote" not in format_tally(tally([APPROVE, REJECT]))
    assert "1 No Vote" in format_tally(tally([APPROVE, NO_VOTE]))


# -- Decision -----------------------------------------------------------------

def test_majority_of_decisive_votes_wins() -> None:
    assert decide(tally([APPROVE, APPROVE, REJECT])).outcome == APPROVED
    assert decide(tally([REJECT, REJECT, APPROVE])).outcome == REJECTED


def test_tie_is_not_a_pass() -> None:
    decision = decide(tally([APPROVE, REJECT]))
    assert decision.outcome == NO_CONSENSUS
    assert "split" in decision.reason


def test_abstentions_are_not_agreement() -> None:
    decision = decide(tally([ABSTAIN, ABSTAIN, ABSTAIN]))
    assert decision.outcome == NO_CONSENSUS
    assert not decision.provisional


def test_abstentions_do_not_block_a_decisive_majority() -> None:
    assert decide(tally([APPROVE, APPROVE, ABSTAIN])).outcome == APPROVED


def test_silence_makes_an_approval_provisional() -> None:
    """A panelist that timed out was never heard. The approval stands, but it is
    labelled, so nobody reads a timeout as assent."""
    decision = decide(tally([APPROVE, APPROVE, NO_VOTE]))
    assert decision.outcome == APPROVED
    assert decision.provisional
    assert decision.headline == "APPROVED (PROVISIONAL)"
    assert "never voted" in decision.reason


def test_a_rejection_is_never_provisional() -> None:
    """Provisional exists to stop silence reading as consent; a rejection does
    not need the caveat."""
    assert not decide(tally([REJECT, REJECT, NO_VOTE])).provisional


def test_no_ballots_at_all_is_no_consensus() -> None:
    decision = decide(tally([NO_VOTE, NO_VOTE]))
    assert decision.outcome == NO_CONSENSUS
    assert "no panelist cast a decisive vote" in decision.reason


def test_summary_reports_counts_and_reason() -> None:
    summary = decide(tally([APPROVE, APPROVE, REJECT])).summary()
    assert "APPROVED" in summary
    assert "2 Approve" in summary
    assert "1 Reject" in summary
