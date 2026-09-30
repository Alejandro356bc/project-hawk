import asyncio
import logging
import os
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any, AsyncGenerator, List

from openai import APIStatusError, AsyncOpenAI, RateLimitError

from quorum.models.schemas import Message
from quorum.providers.base import BaseProvider
from quorum.tools import TOOLS_SCHEMA, execute_tool

log = logging.getLogger("quorum.provider")

# Retry policy for free-tier rate limits (429) and transient overload (503).
_MAX_RETRIES = 5
_RETRY_BASE_SEC = 2.0
_RETRY_MAX_SEC = 60.0


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


_MAX_TOOL_SECONDS = max(15.0, _env_float("QUORUM_PROVIDER_TIME_LIMIT_SEC", 90.0))
_MAX_TOOL_LOOPS = max(1, _env_int("QUORUM_PROVIDER_MAX_LOOPS", 8))
_COMPLETION_TIMEOUT_SEC = max(15.0, _env_float("QUORUM_COMPLETION_TIMEOUT_SEC", 120.0))


def display_name_from_model(model: str) -> str:
    """Create a compact UI label from a provider-specific model id."""
    core = model.split("/")[-1].split(":")[0]
    if core == "claude-opus-4-8":
        return "Claude Opus 4.8"

    words = core.replace("_", "-").split("-")
    display_words = []
    for word in words:
        lower = word.lower()
        if lower == "gpt":
            display_words.append("GPT")
        elif re.fullmatch(r"[a-z]+[0-9.]+", lower):
            display_words.append(lower.upper())
        else:
            display_words.append(word.title())
    return " ".join(display_words)


class BaseOpenAIProvider(BaseProvider):
    def __init__(
        self,
        name: str,
        model_name: str,
        color: str,
        base_url: str,
        api_key: str,
        uses_custom_tools: bool = True,
    ) -> None:
        super().__init__(name, model_name, color=color, uses_custom_tools=uses_custom_tools)
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
        )
        log.info(
            f"[{name}] Initialized provider - model={model_name}, "
            f"base_url={base_url}, tools={'on' if uses_custom_tools else 'off'}"
        )

    @property
    def _tools_arg(self) -> list[dict[str, Any]] | None:
        """Tool schema to send, or None for models without tool support."""
        return TOOLS_SCHEMA if self.uses_custom_tools else None

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, RateLimitError):
            return True
        if isinstance(exc, APIStatusError) and exc.status_code in (429, 503):
            return True
        text = str(exc).lower()
        return "429" in text or "rate limit" in text or "too many requests" in text

    @staticmethod
    def _retry_delay_sec(exc: Exception, attempt: int) -> float:
        """Honor Retry-After when present; otherwise exponential backoff."""
        response = getattr(exc, "response", None)
        if response is not None:
            headers = getattr(response, "headers", None) or {}
            retry_after = headers.get("retry-after") or headers.get("Retry-After")
            if retry_after is not None:
                try:
                    parsed_retry_after = float(retry_after)
                    return min(parsed_retry_after, _RETRY_MAX_SEC)
                except ValueError:
                    pass
        return float(min(_RETRY_BASE_SEC * (2 ** attempt), _RETRY_MAX_SEC))

    @staticmethod
    def _format_retry_message(delay: float) -> str:
        secs = max(1, int(round(delay)))
        unit = "second" if secs == 1 else "seconds"
        return (
            f"\n*[This model needs a break. Will return in {secs} {unit}]*\n"
        )

    async def _completion_events(self, **kwargs: Any) -> AsyncGenerator[tuple[str, Any], None]:
        """Yield ``('wait', notice)`` while backing off, then ``('result', completion)``."""
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                completion = await asyncio.wait_for(
                    self.client.chat.completions.create(**kwargs),
                    timeout=_COMPLETION_TIMEOUT_SEC,
                )
                yield ("result", completion)
                return
            except Exception as exc:
                last_exc = exc
                if not self._is_retryable(exc) or attempt >= _MAX_RETRIES:
                    raise
                delay = self._retry_delay_sec(exc, attempt)
                log.warning(
                    f"[{self.name}] Rate limited or overloaded "
                    f"(attempt {attempt + 1}/{_MAX_RETRIES}), "
                    f"retrying in {delay:.1f}s: {exc}"
                )
                yield ("wait", self._format_retry_message(delay))
                await asyncio.sleep(delay)
        if last_exc:
            raise last_exc

    async def _emit_retry_notice(self, notice: str) -> None:
        """Surface rate-limit waits in logs and the terminal (driver chat)."""
        plain = notice.strip().strip("*").strip()
        log.info(f"[{self.name}] {plain}")
        print(f"  [{self.name}] {plain}", flush=True)

    async def _resolve_completion(
        self,
        emit_wait: Callable[[str], Awaitable[None]] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Await a completion, optionally notifying the caller on each retry wait."""
        async for kind, payload in self._completion_events(**kwargs):
            if kind == "wait":
                if emit_wait:
                    await emit_wait(payload)
            else:
                return payload
        raise RuntimeError("Completion loop ended without a result")

    async def start_session(self, system_prompt: str) -> None:
        pass

    async def close_session(self) -> None:
        pass

    def _prepare_messages(self, system_prompt: str, messages: List[Message]) -> List[dict[str, Any]]:
        api_messages: List[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            m: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.name:
                m["name"] = msg.name
            if msg.tool_calls:
                m["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            api_messages.append(m)
        return api_messages

    async def generate_response(self, system_prompt: str, messages: List[Message]) -> str:
        local_messages = list(messages)
        loop_count = 0
        start_time = time.time()

        while True:
            loop_count += 1
            elapsed = time.time() - start_time
            is_cutoff = (elapsed >= _MAX_TOOL_SECONDS) or (loop_count >= _MAX_TOOL_LOOPS)

            log.info(f"[{self.name}] generate_response loop={loop_count}, elapsed={elapsed:.2f}s, sending {len(local_messages)} messages to model={self.model_name}")
            try:
                if is_cutoff:
                    warning_content = "\n\n[SYSTEM WARNING: You have reached your execution limit. You MUST now provide your final response and cast your vote (VOTE: Approve, VOTE: Reject, or VOTE: Abstain) using the information you have gathered. Do NOT attempt to call any more tools, as they are now disabled. Summarize your findings and state your conclusion.]"
                    if local_messages:
                        last_msg = local_messages[-1]
                        copied_msg = Message(
                            role=last_msg.role,
                            content=(last_msg.content or "") + warning_content,
                            name=last_msg.name,
                            tool_calls=last_msg.tool_calls,
                            tool_call_id=last_msg.tool_call_id
                        )
                        local_messages[-1] = copied_msg
                    else:
                        local_messages.append(Message(role="user", content=warning_content))
                    response = await self._resolve_completion(
                        emit_wait=self._emit_retry_notice,
                        model=self.model_name,
                        messages=self._prepare_messages(system_prompt, local_messages),
                        tools=None  # Disable tools
                    )
                else:
                    response = await self._resolve_completion(
                        emit_wait=self._emit_retry_notice,
                        model=self.model_name,
                        messages=self._prepare_messages(system_prompt, local_messages),
                        tools=self._tools_arg
                    )
            except Exception as e:
                log.error(f"[{self.name}] API call FAILED: {e}", exc_info=True)
                return f"Error: API call failed: {e}"

            if not response.choices:
                log.error(f"[{self.name}] API returned empty choices. Full response: {response}")
                return "Error: No response choices returned."

            msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason
            log.info(f"[{self.name}] Response received - finish_reason={finish_reason}, has_tool_calls={bool(msg and msg.tool_calls)}, content_length={len(msg.content) if msg and msg.content else 0}")

            if not msg:
                log.error(f"[{self.name}] Message object is None")
                return "Error: Empty message in response."

            if is_cutoff:
                content = msg.content or ""
                log.info(f"[{self.name}] Forced final text response due to execution limit ({len(content)} chars): {content[:200]}...")
                return content

            if msg.tool_calls:
                log.info(f"[{self.name}] {len(msg.tool_calls)} tool call(s) requested")
                local_messages.append(Message(
                    role="assistant",
                    content=msg.content or "",
                    tool_calls=[tc.model_dump() for tc in msg.tool_calls]
                ))

                for tool_call in msg.tool_calls:
                    fn = tool_call.function
                    fn_name = fn.name if fn and fn.name else "unknown"
                    fn_args = fn.arguments if fn and fn.arguments else "{}"
                    log.info(f"[{self.name}]   -> Tool: {fn_name}({fn_args})")
                    result = await asyncio.to_thread(execute_tool, fn_name, fn_args)
                    log.info(f"[{self.name}]   <- Result: {result[:200]}{'...' if len(result) > 200 else ''}")
                    local_messages.append(Message(
                        role="tool",
                        content=result,
                        tool_call_id=tool_call.id,
                        name=fn_name
                    ))
            else:
                content = msg.content or ""
                log.info(f"[{self.name}] Final text response ({len(content)} chars): {content[:200]}{'...' if len(content) > 200 else ''}")
                return content

    async def async_stream_response(self, system_prompt: str, messages: List[Message]) -> AsyncGenerator[str, None]:
        local_messages = list(messages)
        loop_count = 0
        start_time = time.time()

        while True:
            loop_count += 1
            elapsed = time.time() - start_time
            is_cutoff = (elapsed >= _MAX_TOOL_SECONDS) or (loop_count >= _MAX_TOOL_LOOPS)

            log.info(f"[{self.name}] async_stream loop={loop_count}, elapsed={elapsed:.2f}s, sending {len(local_messages)} messages to model={self.model_name}")
            try:
                if is_cutoff:
                    warning_content = "\n\n[SYSTEM WARNING: You have reached your execution limit. You MUST now provide your final response and cast your vote (VOTE: Approve, VOTE: Reject, or VOTE: Abstain) using the information you have gathered. Do NOT attempt to call any more tools, as they are now disabled. Summarize your findings and state your conclusion.]"
                    if local_messages:
                        last_msg = local_messages[-1]
                        copied_msg = Message(
                            role=last_msg.role,
                            content=(last_msg.content or "") + warning_content,
                            name=last_msg.name,
                            tool_calls=last_msg.tool_calls,
                            tool_call_id=last_msg.tool_call_id
                        )
                        local_messages[-1] = copied_msg
                    else:
                        local_messages.append(Message(role="user", content=warning_content))
                    yield "\n\n*[System: Maximum execution limit reached. Directing model to render opinion and vote...]*\n\n"
                    try:
                        stream = None
                        async for kind, payload in self._completion_events(
                            model=self.model_name,
                            messages=self._prepare_messages(system_prompt, local_messages),
                            stream=True,
                        ):
                            if kind == "wait":
                                yield payload
                            else:
                                stream = payload
                                break
                        if stream is None:
                            yield "[Error: No stream returned.]"
                            return
                        async for chunk in stream:
                            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                                yield chunk.choices[0].delta.content
                    except Exception as e:
                        log.error(f"[{self.name}] Streaming FAILED: {e}", exc_info=True)
                        yield f"[Error streaming final response: {e}]"
                    log.info(f"[{self.name}] Streaming complete (forced due to execution limit)")
                    return
                else:
                    response = None
                    async for kind, payload in self._completion_events(
                        model=self.model_name,
                        messages=self._prepare_messages(system_prompt, local_messages),
                        tools=self._tools_arg,
                    ):
                        if kind == "wait":
                            yield payload
                        else:
                            response = payload
                            break
                    if response is None:
                        yield "[Error: No response returned.]"
                        return
            except Exception as e:
                log.error(f"[{self.name}] API call FAILED: {e}", exc_info=True)
                yield f"[Error: API call failed: {e}]"
                return

            if not response.choices:
                log.error(f"[{self.name}] API returned empty choices. Full response: {response}")
                yield "[Error: No response choices returned.]"
                return

            msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason
            log.info(f"[{self.name}] Response received - finish_reason={finish_reason}, has_tool_calls={bool(msg and msg.tool_calls)}, content_length={len(msg.content) if msg and msg.content else 0}")

            if not msg:
                log.error(f"[{self.name}] Message object is None")
                yield "[Error: Empty message in response.]"
                return

            if msg.tool_calls:
                log.info(f"[{self.name}] {len(msg.tool_calls)} tool call(s) requested")
                yield f"\n\n*[System: {self.name} is executing {len(msg.tool_calls)} tools...]*\n"
                local_messages.append(Message(
                    role="assistant",
                    content=msg.content or "",
                    tool_calls=[tc.model_dump() for tc in msg.tool_calls]
                ))

                for tool_call in msg.tool_calls:
                    fn = tool_call.function
                    fn_name = fn.name if fn and fn.name else "unknown"
                    fn_args = fn.arguments if fn and fn.arguments else "{}"
                    log.info(f"[{self.name}]   -> Tool: {fn_name}({fn_args})")
                    result = await asyncio.to_thread(execute_tool, fn_name, fn_args)
                    log.info(f"[{self.name}]   <- Result: {result[:200]}{'...' if len(result) > 200 else ''}")
                    local_messages.append(Message(
                        role="tool",
                        content=result,
                        tool_call_id=tool_call.id,
                        name=fn_name
                    ))
            else:
                log.info(f"[{self.name}] No more tool calls - streaming final text response")
                try:
                    stream = None
                    async for kind, payload in self._completion_events(
                        model=self.model_name,
                        messages=self._prepare_messages(system_prompt, local_messages),
                        stream=True,
                    ):
                        if kind == "wait":
                            yield payload
                        else:
                            stream = payload
                            break
                    if stream is None:
                        yield "[Error: No stream returned.]"
                        return
                    async for chunk in stream:
                        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
                except Exception as e:
                    log.error(f"[{self.name}] Streaming FAILED: {e}", exc_info=True)
                    yield f"[Error streaming final response: {e}]"
                log.info(f"[{self.name}] Streaming complete")
                return

class OpenRouterProvider(BaseOpenAIProvider):
    def __init__(self, model_name: str = "minimax/minimax-m3") -> None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set.")
        super().__init__(display_name_from_model(model_name), model_name, "magenta", "https://openrouter.ai/api/v1", api_key)

class MoonshotProvider(BaseOpenAIProvider):
    def __init__(self, model_name: str = "moonshotai/kimi-k2.7-code") -> None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set.")
        super().__init__(display_name_from_model(model_name), model_name, "white", "https://openrouter.ai/api/v1", api_key)

class AlibabaProvider(BaseOpenAIProvider):
    def __init__(self, model_name: str = "qwen/qwen-plus") -> None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set.")
        super().__init__(display_name_from_model(model_name), model_name, "cyan", "https://openrouter.ai/api/v1", api_key)

class ClaudeProvider(BaseOpenAIProvider):
    def __init__(self, model_name: str = "anthropic/claude-sonnet-4.6") -> None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set.")
        super().__init__(display_name_from_model(model_name), model_name, "yellow", "https://openrouter.ai/api/v1", api_key)

class GeminiProvider(BaseOpenAIProvider):
    def __init__(self, model_name: str = "google/gemini-3.5-flash") -> None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set.")
        super().__init__(display_name_from_model(model_name), model_name, "blue", "https://openrouter.ai/api/v1", api_key)

class CodexProvider(BaseOpenAIProvider):
    def __init__(self, model_name: str = "openai/gpt-4o") -> None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set.")
        super().__init__(display_name_from_model(model_name), model_name, "cyan", "https://openrouter.ai/api/v1", api_key)
