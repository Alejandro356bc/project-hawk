import asyncio
import json
import logging
import shutil
import uuid
from typing import AsyncGenerator, List, Optional

from quorum.models.schemas import Message
from quorum.providers.base import BaseProvider
from quorum.providers.cli_prompt import build_cli_user_prompt
from quorum.providers.openai_provider import display_name_from_model

log = logging.getLogger("quorum.provider.claude_code")


def _npx_executable() -> str:
    return shutil.which("npx.cmd") or shutil.which("npx") or "npx"


async def _terminate_process_tree(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    if process.pid and shutil.which("taskkill"):
        try:
            killer = await asyncio.create_subprocess_exec(
                "taskkill",
                "/PID",
                str(process.pid),
                "/T",
                "/F",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(killer.wait(), timeout=5)
            return
        except Exception:
            pass
    try:
        process.kill()
    except ProcessLookupError:
        pass


class ClaudeCodeProvider(BaseProvider):
    """
    Provider that interfaces with the Claude Code CLI using session persistence.

    Uses ``--print`` mode with JSON output for structured responses and
    ``--session-id`` / ``--resume`` to maintain a persistent conversation across
    calls so context accumulates naturally without re-sending full history.

    The CLI itself has full tool access (Bash, Read, Write, Grep, etc.) through
    the user's Claude Code subscription - no API key required.
    """

    def __init__(
        self,
        model_name: str = "claude-opus-4-8",
        color: str = "yellow",
        permission_mode: Optional[str] = None,
    ) -> None:
        super().__init__(display_name_from_model(model_name), model_name, color=color)
        self.session_id: str = str(uuid.uuid4())
        self.permission_mode = permission_mode
        self._system_prompt: Optional[str] = None
        self._session_started = False

    # -- Lifecycle ---------------------------------------------------------

    async def start_session(self, system_prompt: str) -> None:
        """Store system prompt for first-call injection."""
        self._system_prompt = system_prompt
        self.session_id = str(uuid.uuid4())
        self._session_started = False
        log.info(
            f"[{self.name}] Session prepared - "
            f"session_id={self.session_id}, model={self.model_name}"
        )

    async def close_session(self) -> None:
        log.info(f"[{self.name}] Session closed - session_id={self.session_id}")

    # -- Command construction ----------------------------------------------

    def _build_command(self, stream: bool = False) -> List[str]:
        """Assemble the ``claude`` CLI invocation."""
        parts = [
            _npx_executable(), "@anthropic-ai/claude-code",
            "-p",
            "--model", self.model_name,
        ]
        if self.permission_mode:
            parts.extend(["--permission-mode", self.permission_mode])

        if stream:
            parts.extend(["--output-format", "stream-json", "--verbose"])
        else:
            parts.extend(["--output-format", "json"])

        if self._session_started:
            # Resume existing session - context is already inside the CLI
            parts.extend(["--resume", self.session_id])
        else:
            # First call - set session ID and inject system prompt
            parts.extend(["--session-id", self.session_id])
            if self._system_prompt:
                parts.extend(["--system-prompt", self._system_prompt])

        return parts

    async def _write_prompt(self, process: asyncio.subprocess.Process, prompt: str) -> None:
        """Send the print-mode prompt via stdin and close the stream."""
        if process.stdin is None:
            raise RuntimeError("Claude Code CLI stdin pipe unavailable")

        process.stdin.write(prompt.encode("utf-8"))
        await process.stdin.drain()
        process.stdin.close()
        await process.stdin.wait_closed()

    # -- Non-streaming response --------------------------------------------

    async def generate_response(
        self, system_prompt: str, messages: List[Message]
    ) -> str:
        prompt = build_cli_user_prompt(
            messages,
            system_prompt,
            self._system_prompt,
            session_active=self._session_started,
        )
        cmd = self._build_command(stream=False)

        log.info(
            f"[{self.name}] generate_response - "
            f"session_started={self._session_started}, "
            f"prompt_len={len(prompt)}"
        )

        process: asyncio.subprocess.Process | None = None
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await self._write_prompt(process, prompt)
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=660
            )

            self._session_started = True
            output = stdout.decode("utf-8", errors="ignore").strip()
            err_output = stderr.decode("utf-8", errors="ignore").strip()

            if process.returncode != 0 and not output:
                log.error(f"[{self.name}] CLI error (rc={process.returncode}): {err_output}")
                return f"[Claude CLI Error: {err_output}]"

            return self._parse_json_result(output)

        except asyncio.TimeoutError:
            if process is not None:
                await _terminate_process_tree(process)
            log.error(f"[{self.name}] CLI timed out after 660s")
            return "[Error: Claude Code CLI timed out after 660s]"
        except asyncio.CancelledError:
            if process is not None:
                await _terminate_process_tree(process)
            raise
        except Exception as e:
            log.error(f"[{self.name}] CLI execution failed: {e}", exc_info=True)
            return f"[Error: {e}]"

    # -- Streaming response ------------------------------------------------

    async def async_stream_response(
        self, system_prompt: str, messages: List[Message]
    ) -> AsyncGenerator[str, None]:
        prompt = build_cli_user_prompt(
            messages,
            system_prompt,
            self._system_prompt,
            session_active=self._session_started,
        )
        cmd = self._build_command(stream=True)

        log.info(
            f"[{self.name}] async_stream_response - "
            f"session_started={self._session_started}, "
            f"prompt_len={len(prompt)}"
        )

        process: asyncio.subprocess.Process | None = None
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await self._write_prompt(process, prompt)

            self._session_started = True
            emitted_len = 0  # Track how much text we've yielded so far

            if process.stdout is None:
                yield "\n[Error streaming from Claude Code CLI: stdout pipe unavailable]"
                return

            stderr_task = (
                asyncio.create_task(process.stderr.read())
                if process.stderr is not None
                else None
            )

            async for raw_line in process.stdout:
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                # Skip non-JSON lines (e.g. "Warning: no stdin data...")
                if not line.startswith("{"):
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                etype = event.get("type")

                # -- assistant message (contains full content so far) --
                if etype == "assistant":
                    msg = event.get("message", {})
                    for block in msg.get("content", []):
                        if block.get("type") == "text":
                            full_text = block.get("text", "")
                            if len(full_text) > emitted_len:
                                yield full_text[emitted_len:]
                                emitted_len = len(full_text)

                # -- tool use notifications ----------------------------
                elif etype == "tool_use":
                    tool_name = event.get("name", "unknown")
                    yield f"\n*[Tool: {tool_name}]*\n"

                # -- final result --------------------------------------
                elif etype == "result":
                    result_text = event.get("result", "")
                    cost = event.get("total_cost_usd", 0)
                    log.info(
                        f"[{self.name}] Stream complete - "
                        f"cost=${cost:.4f}, "
                        f"result_len={len(result_text)}"
                    )
                    # Yield any remaining text not yet emitted
                    if result_text and len(result_text) > emitted_len:
                        yield result_text[emitted_len:]
                        emitted_len = len(result_text)

            await process.wait()
            stderr_text = ""
            if stderr_task is not None:
                stderr_text = (await stderr_task).decode("utf-8", errors="ignore").strip()

            log.info(
                f"[{self.name}] CLI stream process exited - "
                f"rc={process.returncode}, emitted_len={emitted_len}, "
                f"stderr_len={len(stderr_text)}"
            )
            if process.returncode != 0:
                yield f"\n[Claude Code CLI Error rc={process.returncode}: {stderr_text or 'no stderr'}]\n"
            elif emitted_len == 0:
                detail = f": {stderr_text}" if stderr_text else ""
                yield f"\n[Claude Code CLI produced no output{detail}]\n"

        except asyncio.CancelledError:
            if process is not None:
                await _terminate_process_tree(process)
            raise
        except Exception as e:
            log.error(f"[{self.name}] Streaming failed: {e}", exc_info=True)
            yield f"\n[Error streaming from Claude Code CLI: {e}]"

    # -- Helpers -----------------------------------------------------------

    def _parse_json_result(self, output: str) -> str:
        """Parse the JSON ``--output-format json`` response."""
        for line in output.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                data = json.loads(line)
                if data.get("type") == "result":
                    result = data.get("result", "")
                    if not isinstance(result, str):
                        result = json.dumps(result)
                    cost = data.get("total_cost_usd", 0)
                    is_error = data.get("is_error", False)
                    log.info(
                        f"[{self.name}] Parsed result - "
                        f"cost=${cost:.4f}, "
                        f"error={is_error}, "
                        f"len={len(result)}"
                    )
                    if is_error:
                        return f"[Claude Error: {result}]"
                    return result
            except json.JSONDecodeError:
                continue

        log.warning(f"[{self.name}] Could not parse JSON output, returning raw")
        # Strip the stdin warning if present
        clean = "\n".join(
            line for line in output.splitlines()
            if not line.startswith("Warning: no stdin")
        )
        return clean or "[No response from Claude Code CLI]"
