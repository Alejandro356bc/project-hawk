# Contributing

Thanks for taking the time to improve Quorum.

## Development Setup

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

python -m pip install -e ".[dev]"
pre-commit install
```

## Checks

Run these before opening a pull request:

```bash
ruff check src tests
mypy src
pytest
```

The test suite is designed to run without live API keys.

Before the first push, and whenever credential handling changes, scan every
tracked file:

```bash
git ls-files -z | xargs -0 detect-secrets-hook
```

In PowerShell:

```powershell
$files = git ls-files
detect-secrets-hook $files
```

The pre-commit hook runs the same detector on staged files. CI repeats the scan
on every push and pull request.

## Pull Requests

- Keep changes focused and explain user-visible behavior changes.
- Add or update tests for bug fixes and new provider behavior.
- Do not commit `.env`, logs, caches, virtual environments, or generated build artifacts.
- Keep real credentials out of `.env.example`; it is intentionally public.
- Call out any change that affects local file access, shell execution, CLI permissions, or API-key handling.
