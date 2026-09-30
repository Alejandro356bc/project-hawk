"""Tests for setup helpers and env management."""

from pathlib import Path

import pytest

from quorum.setup import (
    DEFAULT_OPENROUTER_FREE_MODELS,
    ensure_providers_configured,
    print_panel_size_hint,
    upsert_env_vars,
)


def test_upsert_env_creates_and_updates(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    upsert_env_vars(env_file, {"OPENROUTER_API_KEY": "test-value"})  # pragma: allowlist secret
    text = env_file.read_text(encoding="utf-8")
    assert "OPENROUTER_API_KEY=test-value" in text

    upsert_env_vars(env_file, {"GROQ_API_KEY": "test-value"})  # pragma: allowlist secret
    text = env_file.read_text(encoding="utf-8")
    assert "OPENROUTER_API_KEY=test-value" in text
    assert "GROQ_API_KEY=test-value" in text


def test_upsert_env_preserves_unrelated_lines(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("# my comment\nFOO=bar\n", encoding="utf-8")
    upsert_env_vars(env_file, {"OPENROUTER_API_KEY": "test-value"})  # pragma: allowlist secret
    text = env_file.read_text(encoding="utf-8")
    assert "# my comment" in text
    assert "FOO=bar" in text
    assert "OPENROUTER_API_KEY=test-value" in text


def test_default_openrouter_free_models_has_three_entries() -> None:
    models = [m.strip() for m in DEFAULT_OPENROUTER_FREE_MODELS.split(",") if m.strip()]
    assert len(models) == 3
    assert all(":free" in m for m in models)


def test_print_panel_size_hint_no_crash() -> None:
    from io import StringIO

    from rich.console import Console

    console = Console(file=StringIO(), width=80)
    print_panel_size_hint(console, 1)
    print_panel_size_hint(console, 3)


def test_ensure_providers_configured_uses_existing_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from io import StringIO

    from rich.console import Console

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENROUTER_API_KEY=sk-test",
                "OPENROUTER_FREE_MODELS=deepseek/deepseek-r1:free",
                "ENABLE_CLAUDE_CLI=off",
                "ENABLE_CODEX_CLI=off",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for key in (
        "OPENROUTER_API_KEY",
        "OPENROUTER_FREE_MODELS",
        "ENABLE_CLAUDE_CLI",
        "ENABLE_CODEX_CLI",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("quorum.setup.resolve_env_path", lambda: env_file)

    console = Console(file=StringIO(), width=80)
    assert ensure_providers_configured(console) is True


def test_cli_entrypoint_imports() -> None:
    from quorum.main import cli_entry

    assert callable(cli_entry)
