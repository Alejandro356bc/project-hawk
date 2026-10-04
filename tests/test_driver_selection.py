"""Tests for driver selection in Hawk."""

from typing import AsyncGenerator

import pytest

from hawk.main import choose_driver
from hawk.models.schemas import Message
from hawk.providers.base import BaseProvider


class DummyProvider(BaseProvider):
    def __init__(self, name: str, color: str = "white") -> None:
        super().__init__(name=name, model_name=name.lower(), color=color)

    async def generate_response(self, system_prompt: str, messages: list[Message]) -> str:
        return "ok"

    async def async_stream_response(
        self, system_prompt: str, messages: list[Message]
    ) -> AsyncGenerator[str, None]:
        yield "ok"


def test_choose_driver_empty_raises() -> None:
    with pytest.raises(ValueError):
        choose_driver([])


def test_choose_driver_default_first() -> None:
    p1 = DummyProvider("Deepseek V4.1 Flash")
    p2 = DummyProvider("GPT Oss 120B")
    assert choose_driver([p1, p2]) == p1


def test_choose_driver_default_prefers_claude() -> None:
    p1 = DummyProvider("Deepseek V4.1 Flash")
    p2 = DummyProvider("Claude Opus 4.8")
    p3 = DummyProvider("GPT Oss 120B")
    assert choose_driver([p1, p2, p3]) == p2


def test_choose_driver_by_index() -> None:
    p1 = DummyProvider("Deepseek V4.1 Flash")
    p2 = DummyProvider("GPT Oss 120B")
    assert choose_driver([p1, p2], preferred="2") == p2
    assert choose_driver([p1, p2], preferred="1") == p1


def test_choose_driver_by_name() -> None:
    p1 = DummyProvider("Deepseek V4.1 Flash")
    p2 = DummyProvider("GPT Oss 120B")
    assert choose_driver([p1, p2], preferred="GPT Oss 120B") == p2
    assert choose_driver([p1, p2], preferred="@gpt") == p2
    assert choose_driver([p1, p2], preferred="deepseek") == p1


def test_choose_driver_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    p1 = DummyProvider("Deepseek V4.1 Flash")
    p2 = DummyProvider("GPT Oss 120B")
    monkeypatch.setenv("HAWK_DRIVER", "gpt")
    assert choose_driver([p1, p2]) == p2


def test_choose_driver_invalid_fallback() -> None:
    p1 = DummyProvider("Deepseek V4.1 Flash")
    p2 = DummyProvider("GPT Oss 120B")
    assert choose_driver([p1, p2], preferred="nonexistent") == p1
