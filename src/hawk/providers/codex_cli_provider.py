import asyncio
import json
import logging
import shutil
from typing import AsyncGenerator, List, Optional

from hawk.models.schemas import Message
from hawk.providers.base import BaseProvider
from hawk.providers.cli_prompt import build_cli_user_prompt
from hawk.providers.openai_provider import display_name_from_model

log = logging.getLogger("hawk.provider.codex")


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


class CodexCLIProvider(BaseProvider):
    """
    Provider that interfaces with the OpenAI Codex CLI using session persistence.

    Uses ``codex exec`` with ``--json`` for structured JSONL output and
    ``codex exec resume`` to maintain a persistent conversation across calls
    so context accumulates naturally without re-sending full history.

    Runs entirely on the user's ChatGPT/Codex subscription - no API key required.
    """

    def __init__(
        self,
        model_name: str = "gpt-5.5",
        color: str = "cyan",
        bypass_sandbox: bool = False,
        reasoning_effort: Optional[str] = None,
    ) -> None:
        display_name = display_name_from_model(model_name)
        if reasoning_effort:
            display_name = f"{display_name} {reasoning_effort}"
        super().__init__(display_name, model_name, color=color)
        self.thread_id: Optional[str] = None
        self._system_prompt: Optional[str] = None
        self.bypass_sandbox = bypass_sandbox
        self.reasoning_effort = reasoning_effort

    # -- Lifecycle ---------------------------------------------------------

    async def start_session(self, system_prompt: str) -> None:
        """Store system prompt for first-call injection."""
        self._system_prompt = system_prompt
        self.thread_id = None
        log.info(
            f"[{self.name}] Session prepared - model={self.model_name}"
        )

    async def close_session(self) -> None:
        log.info(
            f"[{self.name}] Session closed - thread_id={self.thread_id}"
        )

    # -- Command construction ----------------------------------------------

    def _build_command(self) -> List[str]:
        """Assemble the ``codex exec`` CLI invocation."""
        if self.thread_id:
            # Resume existing session
            parts = [
                _npx_executable(), "@openai/codex",
                "exec", "resume", self.thread_id,
                "--json",
                "--model", self.model_name,
                "--skip-git-repo-check",
                "-",
            ]
        else:
            # First call - new session
            parts = [
                _npx_executable(), "@openai/codex",
                "exec",
                "--json",
                "--model", self.model_name,
                "--skip-git-repo-check",
                "-",
            ]

        if self.reasoning_effort:
            insert_at = len(parts) - 1
            parts[insert_at:insert_at] = [
                "-c",
                f'model_reasoning_effort="{self.reasoning_effort}"',
            ]

        if self.bypass_sandbox:
            insert_at = len(parts) - 1
            parts.insert(insert_at, "--dangerously-bypass-approvals-and-sandbox")

        return parts

    # -- Non-streaming response --------------------------------------------

    async def generate_response(
        self, system_prompt: str, messages: List[Message]
    ) -> str:
        prompt = build_cli_user_prompt(
            messages,
            system_prompt,
            self._system_prompt,
            append_session_on_first_call=True,
            session_active=self.thread_id is not None,
        )
        cmd = self._build_command()

        log.info(
            f"[{self.name}] generate_response - "
            f"thread_id={self.thread_id}, "
            f"prompt_len={len(prompt)}"
        )

        process: asyncio.subprocess.Process | None = None
        try:
            # Pipe empty stdin so codex doesn't hang waiting for input
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=prompt.encode("utf-8")), timeout=660
            )

            output = stdout.decode("utf-8", errors="ignore").strip()
            err_output = stderr.decode("utf-8", errors="ignore").strip()

            if process.returncode != 0 and not output:
                log.error(
                    f"[{self.name}] CLI error (rc={process.returncode}): "
                    f"{err_output}"
                )
                return f"[Codex CLI Error: {err_output}]"

            return self._parse_jsonl_result(output)

        except asyncio.TimeoutError:
            if process is not None:
                await _terminate_process_tree(process)
            log.error(f"[{self.name}] CLI timed out after 660s")
            return "[Error: Codex CLI timed out after 660s]"
        except asyncio.CancelledError:
            if process is not None:
                await _terminate_process_tree(process)
            raise
        except Exception as e:
            log.error(
                f"[{self.name}] CLI execution failed: {e}", exc_info=True
            )
            return f"[Error: {e}]"

    # -- Streaming response ------------------------------------------------

    async def async_stream_response(
        self, system_prompt: str, messages: List[Message]
    ) -> AsyncGenerator[str, None]:
        prompt = build_cli_user_prompt(
            messages,
            system_prompt,
            self._system_prompt,
            append_session_on_first_call=True,
            session_active=self.thread_id is not None,
        )
        cmd = self._build_command()

        log.info(
            f"[{self.name}] async_stream_response - "
            f"thread_id={self.thread_id}, "
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
            if process.stdin is not None:
                process.stdin.write(prompt.encode("utf-8"))
                await process.stdin.drain()
                process.stdin.close()
                await process.stdin.wait_closed()

            if process.stdout is None:
                yield "\n[Error streaming from Codex CLI: stdout pipe unavailable]"
                return

            emitted_chars = 0
            stderr_task = (
                asyncio.create_task(process.stderr.read())
                if process.stderr is not None
                else None
            )

            async for line in self._iter_stdout_lines(process.stdout):
                if not line or not line.startswith("{"):
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                etype = event.get("type")

                # Capture the thread_id for session resumption
                if etype == "thread.started":
                    tid = event.get("thread_id")
                    if tid:
                        self.thread_id = tid
                        log.info(
                            f"[{self.name}] Thread started - "
                            f"thread_id={self.thread_id}"
                        )

                # Agent text response
                elif etype == "item.completed":
                    item = event.get("item", {})
                    if item.get("type") == "agent_message":
                        text = item.get("text", "")
                        if text:
                            yield text
                            emitted_chars += len(text)
                    elif item.get("type") == "tool_call":
                        tool_name = item.get("name", "shell")
                        notice = f"\n*[Tool: {tool_name}]*\n"
                        yield notice
                        emitted_chars += len(notice)
                    elif item.get("type") == "error":
                        err_msg = item.get("message", "")
                        # Skip non-fatal warnings (skill budget, etc.)
                        if "Skill descriptions were shortened" in err_msg:
                            continue
                        if err_msg:
                            warning = f"\n*[Warning: {err_msg}]*\n"
                            yield warning
                            emitted_chars += len(warning)

                # Turn complete - log usage
                elif etype == "turn.completed":
                    usage = event.get("usage", {})
                    log.info(
                        f"[{self.name}] Turn complete - "
                        f"input_tokens={usage.get('input_tokens', 0)}, "
                        f"output_tokens={usage.get('output_tokens', 0)}"
                    )

                # Error events
                elif etype == "error":
                    err_msg = event.get("message", "Unknown error")
                    log.error(f"[{self.name}] Error event: {err_msg}")
                    error = f"\n[Codex Error: {err_msg}]\n"
                    yield error
                    emitted_chars += len(error)

                elif etype == "turn.failed":
                    err = event.get("error", {})
                    err_msg = err.get("message", "Turn failed")
                    log.error(f"[{self.name}] Turn failed: {err_msg}")
                    error = f"\n[Codex Error: {err_msg}]\n"
                    yield error
                    emitted_chars += len(error)

            await process.wait()
            stderr_text = ""
            if stderr_task is not None:
                stderr_text = (await stderr_task).decode("utf-8", errors="ignore").strip()

            log.info(
                f"[{self.name}] CLI stream process exited - "
                f"rc={process.returncode}, emitted_chars={emitted_chars}, "
                f"stderr_len={len(stderr_text)}"
            )
            if process.returncode != 0:
                yield f"\n[Codex CLI Error rc={process.returncode}: {stderr_text or 'no stderr'}]\n"
            elif emitted_chars == 0:
                detail = f": {stderr_text}" if stderr_text else ""
                yield f"\n[Codex CLI produced no output{detail}]\n"

        except asyncio.CancelledError:
            if process is not None:
                await _terminate_process_tree(process)
            raise
        except Exception as e:
            log.error(
                f"[{self.name}] Streaming failed: {e}", exc_info=True
            )
            yield f"\n[Error streaming from Codex CLI: {e}]"

    # -- Helpers -----------------------------------------------------------

    async def _iter_stdout_lines(
        self, stdout: asyncio.StreamReader
    ) -> AsyncGenerator[str, None]:
        buffer = ""
        max_buffer = 16 * 1024 * 1024
        while True:
            chunk = await stdout.read(65_536)
            if not chunk:
                break
            buffer += chunk.decode("utf-8", errors="ignore")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                yield line.strip()
            if len(buffer) > max_buffer:
                log.warning(
                    f"[{self.name}] Dropping oversized partial JSONL buffer "
                    f"({len(buffer)} chars)"
                )
                buffer = ""
        if buffer.strip():
            yield buffer.strip()

    def _parse_jsonl_result(self, output: str) -> str:
        """Parse the JSONL ``--json`` output and extract the response."""
        agent_messages: List[str] = []

        for line in output.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = event.get("type")

            # Capture thread_id for session resumption
            if etype == "thread.started":
                tid = event.get("thread_id")
                if tid:
                    self.thread_id = tid
                    log.info(
                        f"[{self.name}] Thread started - "
                        f"thread_id={self.thread_id}"
                    )

            # Collect agent messages
            elif etype == "item.completed":
                item = event.get("item", {})
                if item.get("type") == "agent_message":
                    text = item.get("text", "")
                    if text:
                        agent_messages.append(str(text))

            # Log usage
            elif etype == "turn.completed":
                usage = event.get("usage", {})
                log.info(
                    f"[{self.name}] Turn complete - "
                    f"input_tokens={usage.get('input_tokens', 0)}, "
                    f"output_tokens={usage.get('output_tokens', 0)}"
                )

            # Handle errors
            elif etype == "error":
                err_msg = event.get("message", "Unknown error")
                log.error(f"[{self.name}] Error: {err_msg}")
                return f"[Codex Error: {err_msg}]"

            elif etype == "turn.failed":
                err = event.get("error", {})
                err_msg = err.get("message", "Turn failed")
                log.error(f"[{self.name}] Turn failed: {err_msg}")
                return f"[Codex Error: {err_msg}]"

        if agent_messages:
            return "\n\n".join(agent_messages)

        log.warning(
            f"[{self.name}] No agent messages found in output, "
            f"returning raw"
        )
        clean = "\n".join(
            line for line in output.splitlines()
            if not line.startswith("Reading additional input")
        )
        return clean or "[No response from Codex CLI]"
