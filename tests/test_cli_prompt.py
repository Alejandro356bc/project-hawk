"""Tests for CLI provider prompt folding."""

from hawk.models.schemas import Message
from hawk.prompts import DRIVER_SYSTEM_PROMPT, append_turn_instructions
from hawk.providers.cli_prompt import build_cli_user_prompt


def test_append_turn_instructions() -> None:
    result = append_turn_instructions("Hello", "Be concise.")
    assert "Hello" in result
    assert "Instructions for this turn: Be concise." in result


def test_append_turn_instructions_skips_empty() -> None:
    assert append_turn_instructions("Hello", "") == "Hello"


def test_build_cli_user_prompt_injects_driver_on_active_session() -> None:
    session = "You are a Hawk member."
    messages = [Message(role="user", content="Fix the bug in auth.py")]
    prompt = build_cli_user_prompt(
        messages,
        DRIVER_SYSTEM_PROMPT,
        session,
        session_active=True,
    )
    assert "Fix the bug in auth.py" in prompt
    assert "Instructions for this turn:" in prompt
    assert "primary Driver AI" in prompt


def test_build_cli_user_prompt_skips_duplicate_session_text() -> None:
    session = "Same instructions"
    messages = [Message(role="user", content="Hi")]
    prompt = build_cli_user_prompt(
        messages,
        "Same instructions",
        session,
        session_active=True,
    )
    assert prompt == "Hi"


def test_codex_first_call_includes_session_guidelines() -> None:
    session = "Panel context here"
    messages = [Message(role="user", content="Question")]
    prompt = build_cli_user_prompt(
        messages,
        DRIVER_SYSTEM_PROMPT,
        session,
        append_session_on_first_call=True,
        session_active=False,
    )
    assert "Behavioral guidelines for this session" in prompt
    assert "Panel context here" in prompt
    assert "primary Driver AI" in prompt
