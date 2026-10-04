"""Tests for API provider retry and messaging helpers."""

from hawk.providers.openai_provider import BaseOpenAIProvider


def test_format_retry_message() -> None:
    provider = BaseOpenAIProvider("Test", "model", "green", "http://localhost/v1", "key")
    msg = provider._format_retry_message(5.0)
    assert "needs a break" in msg
    assert "5 seconds" in msg


def test_is_retryable_detects_429() -> None:
    assert BaseOpenAIProvider._is_retryable(Exception("HTTP 429 rate limit exceeded"))
    assert not BaseOpenAIProvider._is_retryable(Exception("invalid api key"))


def test_retry_delay_exponential() -> None:
    assert BaseOpenAIProvider._retry_delay_sec(Exception("429"), 0) == 2.0
    assert BaseOpenAIProvider._retry_delay_sec(Exception("429"), 2) == 8.0
