# Changelog

All notable changes to Hawk will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Made shell-command tests quote arguments correctly on both Windows and POSIX,
  matching the shell used by `run_command`.
- **Votes were mis-tallied.** `VOTE: Abstain - not enough context` was recorded as a
  *Reject*, because the parser tested `"no" in vote` (matching the "no" inside "not")
  before it tested for "abstain". Ballot keywords are now matched on word boundaries
  against a captured token instead of by substring scan.
- **A quoted ballot could overwrite a panelist's own.** The parser took the *first*
  `VOTE:` in a response, so a panelist quoting a peer - which round 2+ explicitly asks
  it to do - was recorded with the peer's vote. Resolution now prefers a ballot on its
  own line and takes the last one, and the round transcript no longer feeds a literal
  `VOTE:` token back to the panel.
- **A timed-out panelist was recorded as `Abstain`**, turning silence into a
  considered neutral position. Unanswered panelists are now `No Vote`, tracked in
  their own bucket, and never counted as agreement.

### Added

- Automated secret scanning for local commits and GitHub Actions.
- Packaging rules that explicitly exclude environment files and private-key formats.
- `hawk/voting.py`: ballot parsing and vote arithmetic as pure functions,
  covered by `tests/test_voting.py` (19 tests pinning the above).
- **The tally now decides the debate.** `decide()` computes the outcome - `APPROVED`,
  `REJECTED`, or `NO CONSENSUS` - from the ballots: a strict majority of decisive
  votes wins, a tie is no consensus, and an approval reached while a panelist was
  never heard is marked `APPROVED (PROVISIONAL)`. It is printed before the synthesis.
- `HAWK_SYNTHESIZER` selects which panelist writes the summary.

### Changed

- The synthesizer is handed the computed outcome and instructed not to overturn it,
  and its write-up is labelled as one panelist's summary. Previously the conclusion
  was narrated by `clients[0]` - a debater writing the verdict on its own debate,
  with the vote count playing no part in it.
- Vote instructions ask for the ballot alone on the final line and tell panelists not
  to reproduce each other's vote lines.

## [0.1.0] - 2026-08-13

### Added

- Interactive driver chat and multi-model panel debates.
- OpenAI-compatible API, local Ollama, Claude Code, Codex CLI, and Agy CLI providers.
- First-run provider setup, opt-in local tools, live vote tallies, and retry handling.
- Tests, type checking, linting, and GitHub Actions CI.
