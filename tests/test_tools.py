import os
import shlex
import subprocess
import sys

from quorum.tools import grep_search, read_file, run_command, write_file


def _shell_join(args: list[str]) -> str:
    """Quote a command for the platform shell used by run_command."""
    if os.name == "nt":
        return subprocess.list2cmdline(args)
    return shlex.join(args)


# pyrefly: ignore [implicit-any-parameter]
def test_read_file_blocks_env_files(tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENROUTER_API_KEY=not-a-secret\n", encoding="utf-8")

    result = read_file(str(env_path))

    assert "Refusing to read sensitive file" in result
    assert "not-a-secret" not in result


def test_write_file_blocks_env_files(tmp_path) -> None:
    env_path = tmp_path / ".env.local"

    result = write_file(str(env_path), "OPENROUTER_API_KEY=not-a-secret\n")

    assert "Refusing to write sensitive file" in result
    assert not env_path.exists()


def test_grep_search_skips_sensitive_files(tmp_path) -> None:
    public_path = tmp_path / "notes.txt"
    env_path = tmp_path / ".env"
    public_path.write_text("NEEDLE public value\n", encoding="utf-8")
    env_path.write_text(
        "NEEDLE OPENROUTER_API_KEY=not-a-secret\n", encoding="utf-8"
    )

    result = grep_search("NEEDLE", str(tmp_path))

    assert "notes.txt" in result
    assert ".env" not in result
    assert "not-a-secret" not in result


def test_run_command_redacts_secret_output() -> None:
    command = _shell_join(
        [
            sys.executable,
            "-c",
            "print('OPENROUTER_API_KEY=not-a-secret')",
        ]
    )

    result = run_command(command)

    assert "OPENROUTER_API_KEY=[REDACTED]" in result
    assert "not-a-secret" not in result


def test_run_command_timeout_returns_quickly() -> None:
    command = _shell_join(
        [
            sys.executable,
            "-c",
            "import time; time.sleep(5)",
        ]
    )

    result = run_command(command, command_timeout=1)

    assert "timed out after 1 seconds" in result
