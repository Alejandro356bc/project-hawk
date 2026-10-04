"""Tests for provider factory - no live API keys required."""

import os

import pytest

from hawk.providers import create_clients
from hawk.providers.claude_code_provider import ClaudeCodeProvider
from hawk.providers.codex_cli_provider import CodexCLIProvider


@pytest.fixture(autouse=True)
def _clear_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate tests from the developer's real .env."""
    for key in list(os.environ):
        if any(
            key.startswith(p)
            for p in (
                "OPENROUTER_",
                "GROQ_",
                "CEREBRAS_",
                "GEMINI_",
                "MISTRAL_",
                "GITHUB_",
                "NVIDIA_",
                "TOKENHARBOR_",
                "OLLAMA_",
                "OLLAMACLOUD_",
                "AGY_",
                "ENABLE_",
                "CLAUDE_",
                "CODEX_",
            )
        ):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ENABLE_CLAUDE_CLI", "0")
    monkeypatch.setenv("ENABLE_CODEX_CLI", "0")


def test_create_clients_empty_without_config() -> None:
    assert create_clients() == []


def test_openrouter_free_hawk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv(
        "OPENROUTER_FREE_MODELS",
        "deepseek/deepseek-r1:free, meta-llama/llama-3.3-70b-instruct:free",
    )
    clients = create_clients()
    assert len(clients) == 2
    assert clients[0].uses_custom_tools is False
    assert clients[1].uses_custom_tools is False


def test_groq_provider_disables_tools_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gk")
    clients = create_clients()
    assert len(clients) == 1
    assert clients[0].name == "Llama 3.3 70B Versatile"
    assert clients[0].uses_custom_tools is False


def test_groq_provider_tools_are_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gk")
    monkeypatch.setenv("GROQ_TOOLS", "on")
    clients = create_clients()
    assert len(clients) == 1
    assert clients[0].name == "Llama 3.3 70B Versatile"
    assert clients[0].uses_custom_tools is True


def test_ollama_no_tools_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1, qwen2.5-coder")
    clients = create_clients()
    assert len(clients) == 2
    assert all(not c.uses_custom_tools for c in clients)


def test_agy_cli_provider_uses_argument_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGY_CLI_CMD", "agy --print-timeout 5m --print")
    clients = create_clients()
    assert len(clients) == 1
    assert clients[0].name == "Gemini 3.1 Pro high"
    assert clients[0].model_name == "Gemini 3.1 Pro (High)"
    assert getattr(clients[0], "prompt_transport") == "argument_file"
    assert "--model" in getattr(clients[0], "cli_command_prefix")


def test_agy_replaces_legacy_openrouter_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("AGY_CLI_CMD", "agy --print-timeout 5m --print")
    clients = create_clients()
    names = [client.name for client in clients]
    assert "Gemini 3.1 Pro high" in names
    assert names.count("Gemini 3.1 Pro high") == 1
    assert "Minimax M3" in names
    assert "Kimi K2.7 Code" in names
    assert "Qwen Plus" in names


def test_codex_cli_uses_gpt_55_xhigh(monkeypatch: pytest.MonkeyPatch) -> None:
    def _mock_which(_name: str) -> str:
        return "npx.cmd"

    monkeypatch.setattr("hawk.providers.shutil.which", _mock_which)
    monkeypatch.setenv("ENABLE_CODEX_CLI", "on")
    monkeypatch.setenv("CODEX_MODEL", "gpt-5.5")
    monkeypatch.setenv("CODEX_REASONING_EFFORT", "xhigh")

    clients = create_clients()
    assert len(clients) == 1
    assert clients[0].name == "GPT 5.5 xhigh"
    assert getattr(clients[0], "reasoning_effort") == "xhigh"


def test_claude_code_prompt_is_not_command_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "hawk.providers.claude_code_provider._npx_executable",
        lambda: "npx.cmd",
    )
    provider = ClaudeCodeProvider(model_name="claude-opus-4-8")

    cmd = provider._build_command(stream=True)

    assert cmd[:3] == ["npx.cmd", "@anthropic-ai/claude-code", "-p"]
    assert "--output-format" in cmd
    assert "stream-json" in cmd
    assert "prompt text" not in cmd


def test_codex_cli_prompt_is_read_from_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "hawk.providers.codex_cli_provider._npx_executable",
        lambda: "npx.cmd",
    )
    provider = CodexCLIProvider(model_name="gpt-5.5", reasoning_effort="xhigh")

    cmd = provider._build_command()

    assert cmd[:3] == ["npx.cmd", "@openai/codex", "exec"]
    assert cmd[-1] == "-"
    assert "prompt text" not in cmd


def test_tokenharbor_provider_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKENHARBOR_API_KEY", "thk-test")
    clients = create_clients()
    assert len(clients) == 1
    assert clients[0].name == "Deepseek V4.1 Flash"
    assert clients[0].model_name == "deepseek-v4.1-flash:free"
    assert clients[0].uses_custom_tools is False


def test_tokenharbor_provider_tools_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKENHARBOR_API_KEY", "thk-test")
    monkeypatch.setenv("TOKENHARBOR_TOOLS", "on")
    clients = create_clients()
    assert len(clients) == 1
    assert clients[0].uses_custom_tools is True


def test_ollama_cloud_provider_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama-test")
    clients = create_clients()
    assert len(clients) == 1
    assert clients[0].model_name == "gpt-oss:120b"
    assert clients[0].uses_custom_tools is False


def test_ollama_cloud_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama-test")
    monkeypatch.setenv("OLLAMACLOUD_MODEL", "kimi-k2.6")
    clients = create_clients()
    assert [c.model_name for c in clients] == ["kimi-k2.6"]
