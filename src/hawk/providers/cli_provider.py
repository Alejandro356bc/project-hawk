import asyncio
import logging
import os
import shutil
import tempfile
from typing import AsyncGenerator, List, Literal

from hawk.models.schemas import Message
from hawk.providers.base import BaseProvider

log = logging.getLogger("hawk.provider.cli")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


_CLI_TIMEOUT_SEC = max(30.0, _env_float("HAWK_CLI_TIMEOUT_SEC", 150.0))


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


class CLIProvider(BaseProvider):
    """
    Provider implementation that spawns a stateless CLI session per query.
    This resolves issues with interactive CLIs hanging on pipes when they expect EOF.
    """
    def __init__(
        self,
        name: str,
        cli_command_prefix: List[str],
        color: str = "white",
        model_name: str = "cli-wrapper",
        prompt_transport: Literal["stdin", "argument", "argument_file"] = "stdin",
    ) -> None:
        super().__init__(name, model_name, color=color)
        self.cli_command_prefix = cli_command_prefix
        self.prompt_transport = prompt_transport

    async def start_session(self, system_prompt: str) -> None:
        # Stateless, no persistent process needed
        pass

    async def close_session(self) -> None:
        pass

    def _build_prompt(self, system_prompt: str, messages: List[Message]) -> str:
        # Build the full conversation history to send via stdin
        prompt = f"System Instruction: {system_prompt}\n\n"
        for msg in messages:
            prompt += f"{msg.role}: {msg.content}\n\n"
        prompt += "assistant: "
        return prompt

    def _write_prompt_file(self, prompt: str) -> str:
        fd, path = tempfile.mkstemp(
            prefix="hawk_prompt_",
            suffix=".txt",
            text=True,
        )
        with os.fdopen(fd, "w", encoding="utf-8", errors="ignore") as handle:
            handle.write(prompt)
        return path

    async def generate_response(self, system_prompt: str, messages: List[Message]) -> str:
        prompt = self._build_prompt(system_prompt, messages)
        log.info(
            "[%s] generate_response - command=%s, transport=%s, prompt_len=%s",
            self.name,
            self.cli_command_prefix,
            self.prompt_transport,
            len(prompt),
        )

        process: asyncio.subprocess.Process | None = None
        prompt_file: str | None = None
        try:
            if self.prompt_transport == "argument":
                process = await asyncio.create_subprocess_exec(
                    *self.cli_command_prefix,
                    prompt,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=_CLI_TIMEOUT_SEC,
                )
            elif self.prompt_transport == "argument_file":
                prompt_file = self._write_prompt_file(prompt)
                prompt_arg = (
                    "Read the full prompt from this file and follow it exactly: "
                    f"{prompt_file}"
                )
                process = await asyncio.create_subprocess_exec(
                    *self.cli_command_prefix,
                    prompt_arg,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=_CLI_TIMEOUT_SEC,
                )
            else:
                cmd_str = " ".join(self.cli_command_prefix)
                # shell=True preserves compatibility with user-provided CLI wrappers.
                process = await asyncio.create_subprocess_shell(
                    cmd_str,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=prompt.encode("utf-8")),
                    timeout=_CLI_TIMEOUT_SEC,
                )

            out = stdout.decode("utf-8", errors="ignore").strip()
            err = stderr.decode("utf-8", errors="ignore").strip()
            log.info(
                "[%s] CLI complete - rc=%s, stdout_len=%s, stderr_len=%s",
                self.name,
                process.returncode,
                len(out),
                len(err),
            )

            if process.returncode != 0:
                return f"[CLI Error rc={process.returncode}: {err or out}]"
            if not out and err:
                return f"[CLI Error: {err}]"
            elif not out:
                return "[No Output Received]"
            return out
        except asyncio.TimeoutError:
            if process is not None:
                await _terminate_process_tree(process)
            return f"[CLI Error: timed out after {_CLI_TIMEOUT_SEC:g}s]"
        except asyncio.CancelledError:
            if process is not None:
                await _terminate_process_tree(process)
            raise
        except Exception as e:
            return f"[CLI Execution Error: {e}]"
        finally:
            if prompt_file:
                try:
                    os.remove(prompt_file)
                except OSError:
                    pass

    async def async_stream_response(self, system_prompt: str, messages: List[Message]) -> AsyncGenerator[str, None]:
        # Emulate streaming by generating the full response and yielding it.
        # This prevents hanging since we cannot stream EOF dynamically while receiving output
        # easily on standard CLI wrappers.
        response = await self.generate_response(system_prompt, messages)
        yield response
