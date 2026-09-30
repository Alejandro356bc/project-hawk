"""Shared prompt assembly for CLI-backed providers."""

from __future__ import annotations

from typing import List, Optional

from quorum.models.schemas import Message
from quorum.prompts import append_turn_instructions


def last_user_content(messages: List[Message]) -> str:
    """Return the latest user message, or a concatenated fallback."""
    for msg in reversed(messages):
        if msg.role == "user" and msg.content:
            return msg.content
    return "\n\n".join(m.content for m in messages if m.content)


def build_cli_user_prompt(
    messages: List[Message],
    call_system: str,
    session_system: Optional[str],
    *,
    append_session_on_first_call: bool = False,
    session_active: bool = False,
) -> str:
    """
    Build the user prompt sent to a persistent CLI session.

    * ``session_system`` - from ``start_session`` (panel membership, tools, cwd)
    * ``call_system`` - per-call role (driver, synthesizer, debate panelist)
    * ``append_session_on_first_call`` - Codex has no ``--system-prompt`` flag,
      so session guidelines are inlined on the first message only
    """
    prompt = last_user_content(messages)
    session = (session_system or "").strip()
    call = (call_system or "").strip()

    if append_session_on_first_call and not session_active and session:
        prompt = append_turn_instructions(
            prompt, f"Behavioral guidelines for this session: {session}"
        )

    if call and call != session:
        prompt = append_turn_instructions(prompt, call)

    return prompt
