# Quorum

**Multi-LLM panel debates for coding tasks** - several models discuss, vote, and synthesize a consensus while you watch live.

Quorum runs an interactive CLI with two modes:

- **Driver chat** - talk to a primary model for day-to-day coding help
- **Quorum debate** - summon a panel (`/quorum`) that argues in rounds, casts Approve/Reject/Abstain votes, and produces a synthesized conclusion

No paid subscriptions required. A free [OpenRouter](https://openrouter.ai) key is enough to run a 3-model panel.

---

## Features

- Live multi-pane debate UI (Textual) with streaming responses and vote tallies
- First-run setup wizard - walks you through provider options before anything else runs
- Free-tier friendly - Groq, Cerebras, Agy/Gemini, Mistral, GitHub Models, NVIDIA NIM, Ollama, OpenRouter `:free` models
- Subscription CLI support - Claude Code and Codex when you already have them
- Optional tool use for API providers - read/write files, grep, run commands when explicitly enabled
- Rate-limit resilience - automatic 429 retry with user-visible backoff messages

---

## Quick start

### 1. Install

Clone this repository using the URL from GitHub's **Code** menu, then:

```bash
cd Quorum
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

python -m pip install .
```

### 2. Configure providers

On first launch, Quorum runs an interactive setup wizard. **Recommended path:**

1. Sign up at [openrouter.ai/keys](https://openrouter.ai/keys) (free, no credit card for `:free` models)
2. Choose **option 1** in the setup menu
3. Paste your key - you get three free panelists automatically

Or copy the template and edit manually:

```bash
# macOS / Linux
cp .env.example .env
```

```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

### 3. Run

```bash
quorum
```

You can also launch it with `python -m quorum`.

### 4. Use it

```
You: /quorum 2 Should we refactor auth.py to use JWT or sessions?
```

- `/quorum [rounds] <prompt>` - start a panel debate
- `/setup` - re-run the provider setup wizard
- `exit` - quit

---

## Provider options

| Path | Cost | Setup |
|------|------|-------|
| **OpenRouter free quorum** | Free (rate-limited) | `OPENROUTER_API_KEY` + `OPENROUTER_FREE_MODELS` |
| **Individual free APIs** | Free | One key each: Groq, Cerebras, Gemini, Mistral, GitHub, NVIDIA |
| **Agy CLI** | Subscription / local CLI | `AGY_CLI_CMD="agy --print-timeout 5m --print"` with `AGY_MODEL="Gemini 3.1 Pro (High)"` |
| **Ollama (local)** | Free, offline | `OLLAMA_MODEL=llama3.1` - no key needed |
| **Claude Code / Codex CLI** | Subscription | `ENABLE_CLAUDE_CLI=on` / `ENABLE_CODEX_CLI=on` + `npx` |

See [`.env.example`](.env.example) for every variable.

Local file and shell tools are off by default for API providers. Enable them per provider with flags such as `GROQ_TOOLS=on` only in repositories and directories you trust.

**Tip:** Three or more panelists make the best debates. Quorum nudges you if your panel is thin.

---

## How a debate is decided

The outcome is computed from the ballots by `quorum/voting.py`, printed before
the written summary, and is not up for negotiation by any model. The rules:

| ballot | counts toward the outcome? |
|--------|----------------------------|
| `Approve` / `Reject` | yes - these are the decisive votes |
| `Abstain` | no. Recorded and shown; a panelist declining to decide is not agreement |
| `No Vote` | no. The panelist timed out or cast nothing parseable - it was never heard |

- A **strict majority of the decisive votes** wins.
- A **tie is `NO CONSENSUS`**, not a pass. A split panel has not agreed on anything.
- An approval reached while some panelist was never heard is **`APPROVED (PROVISIONAL)`**,
  so a timeout can never be read as assent.

The synthesized write-up that follows is a *summary* of that result, written by one
of the panelists (`QUORUM_SYNTHESIZER=<name>` picks which; it defaults to the first
configured provider). It is told the outcome and instructed not to overturn it - so
a model that lost the vote cannot narrate itself a win.

Panelists cast their vote on the last line of a response as `VOTE: Approve`,
`VOTE: Reject`, or `VOTE: Abstain`.

---

## Architecture

```
src/quorum/
|-- main.py              CLI entry point and driver chat loop
|-- setup.py             First-run wizard and .env management
|-- ui_layout.py         Textual debate UI (SpectacleQuorum)
|-- prompts.py           System prompt builders (per provider type)
|-- voting.py            Ballot parsing and quorum arithmetic (pure, unit-tested)
|-- tools.py             Function-calling tools for API providers
|-- models/schemas.py    Message and discussion schemas
'-- providers/
    |-- base.py          BaseProvider ABC
    |-- openai_provider.py   OpenAI-compatible API providers + retry logic
    |-- claude_code_provider.py
    |-- codex_cli_provider.py
    '-- cli_provider.py
```

**Provider selection** is env-driven (`providers/__init__.py` -> `create_clients()`). Each provider that fails to initialize is skipped with a warning - the app degrades gracefully.

---

## Development

```bash
# Lint
ruff check src tests

# Type check
mypy src

# Tests (no API keys required)
pytest
```

---

## Security notes

- **Never commit `.env`** - it is gitignored by default
- Keep `.env.example` public-safe: empty values and placeholders only
- Run `detect-secrets-hook` before the first push; CI scans tracked files again
- API keys stay on your machine; Quorum does not phone home
- API provider tools can read files, write files, and run shell commands when `*_TOOLS=on`
- CLI providers are explicit opt-in and use their provider's native file/shell tools
- Codex sandbox bypass is off by default; enable only with `CODEX_BYPASS_SANDBOX=on`
- Claude permission mode is unset by default; use `CLAUDE_PERMISSION_MODE=bypassPermissions` only in trusted environments

See [SECURITY.md](SECURITY.md) for the supported reporting path and operational cautions.

---

## License

MIT - see [LICENSE](LICENSE).
