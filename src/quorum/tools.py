import json
import logging
import os
import re
import subprocess
import time
from typing import Any

log = logging.getLogger("quorum.tools")

_DEFAULT_COMMAND_TIMEOUT_SEC = 20
_MAX_COMMAND_TIMEOUT_SEC = 30

_SENSITIVE_FILENAMES = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.test",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "id_rsa",
    "id_ed25519",
    "known_hosts",
}
_SENSITIVE_EXTENSIONS = {".pem", ".key", ".p12", ".pfx"}
_SECRET_PATTERNS = [
    re.compile(
        r"(?im)^([A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|AUTH)[A-Z0-9_]*\s*=\s*)([^\r\n]+)"
    ),
    re.compile(r"\b(sk-[A-Za-z0-9_.\-/+=]{12,})\b"),
    re.compile(r"\b(sk-ant-[A-Za-z0-9_.\-/+=]{12,})\b"),
]


def _is_sensitive_path(path: str) -> bool:
    normalized = os.path.normpath(path)
    name = os.path.basename(normalized).lower()
    stem, ext = os.path.splitext(name)
    return (
        name in _SENSITIVE_FILENAMES
        or name.startswith(".env.")
        or stem in {"id_rsa", "id_ed25519"}
        or ext in _SENSITIVE_EXTENSIONS
    )


def _redact_sensitive_text(text: str) -> str:
    redacted = text
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 2:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _coerce_command_timeout(value: Any) -> int:
    try:
        timeout = int(value)
    except (TypeError, ValueError):
        timeout = _DEFAULT_COMMAND_TIMEOUT_SEC
    return max(1, min(timeout, _MAX_COMMAND_TIMEOUT_SEC))


def _terminate_process_tree(pid: int) -> None:
    """Terminate a Windows process tree; fall back quietly on other systems."""
    if os.name != "nt":
        return
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception as exc:
        log.warning(f"taskkill failed for pid={pid}: {exc}")

TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the contents of a local file and returns it. Secret files such as .env and key files are blocked. Automatically truncates if the file is extremely large to prevent model context window crashes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute or relative path to the file to read."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Creates or overwrites a file with the given content. Secret files such as .env and key files are blocked. Use this to edit code, create new files, or save analysis results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute or relative path to the file to write."
                    },
                    "content": {
                        "type": "string",
                        "description": "The full content to write into the file."
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lists all files and folders inside a local directory. Automatically truncates if the directory contains too many files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute or relative path to the directory."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Executes a shell command on the local system and returns its stdout and stderr. Automatically truncates long output and redacts secret-looking values.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute (e.g. 'python script.py', 'dir', 'git status')."
                    },
                    "command_timeout": {
                        "type": "integer",
                        "description": "Optional timeout in seconds. Capped at 30 seconds."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Searches for a text pattern in files within a directory. Secret files are skipped. Broad searches are bounded by time and file count. Natively ignores virtual environments (.venv, .venv-torch, .venv-xpu) and version control directories (.git) to run instantly and avoid timeouts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "The text or regex pattern to search for."
                    },
                    "path": {
                        "type": "string",
                        "description": "The directory or file to search in."
                    }
                },
                "required": ["pattern", "path"]
            }
        }
    }
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def read_file(path: str) -> str:
    log.info(f"read_file called with path={path}")
    try:
        if _is_sensitive_path(path):
            log.warning(f"read_file: blocked sensitive path: {path}")
            return f"Error: Refusing to read sensitive file '{path}'."
        if not os.path.exists(path):
            log.warning(f"read_file: path does not exist: {path}")
            return f"Error: File '{path}' does not exist."
        if not os.path.isfile(path):
            return f"Error: '{path}' is not a file."

        # Check size before reading
        file_size = os.path.getsize(path)
        if file_size > 150_000:
            log.warning(f"read_file: file {path} is too large ({file_size} bytes), truncating")
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(100_000)
            content = _redact_sensitive_text(content)
            return (
                f"[WARNING: File '{path}' is too large ({file_size} bytes). "
                f"To prevent model context window exhaustion and API errors, it has been truncated to the first 100,000 characters.]\n\n"
                f"{content}\n\n"
                f"[WARNING: File truncated. Use grep_search or specify smaller files if you need details from later in the file.]"
            )

        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        log.info(f"read_file: successfully read {len(content)} chars from {path}")
        return _redact_sensitive_text(content)
    except Exception as e:
        log.error(f"read_file: exception reading {path}: {e}")
        return f"Error reading file '{path}': {e}"


def write_file(path: str, content: str) -> str:
    log.info(f"write_file called with path={path}, content_length={len(content)}")
    try:
        if _is_sensitive_path(path):
            log.warning(f"write_file: blocked sensitive path: {path}")
            return f"Error: Refusing to write sensitive file '{path}'."
        # Create parent directories if they don't exist
        parent = os.path.dirname(path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
            log.info(f"write_file: created parent directories for {path}")

        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        log.info(f"write_file: successfully wrote {len(content)} chars to {path}")
        return f"Successfully wrote {len(content)} characters to '{path}'."
    except Exception as e:
        log.error(f"write_file: exception writing {path}: {e}")
        return f"Error writing file '{path}': {e}"


def list_directory(path: str) -> str:
    log.info(f"list_directory called with path={path}")
    try:
        if not os.path.exists(path):
            log.warning(f"list_directory: path does not exist: {path}")
            return f"Error: Directory '{path}' does not exist."
        if not os.path.isdir(path):
            return f"Error: '{path}' is not a directory."
        files = os.listdir(path)
        log.info(f"list_directory: found {len(files)} entries in {path}")

        # Sort files so output is predictable
        files.sort()

        if len(files) > 250:
            truncated_files = files[:250]
            result_str = json.dumps(truncated_files, indent=2)
            return (
                f"{result_str}\n\n"
                f"[WARNING: Directory contains {len(files)} entries. "
                f"Showing first 250 entries. {len(files) - 250} entries were truncated to prevent model context crashes.]"
            )

        return json.dumps(files, indent=2)
    except Exception as e:
        log.error(f"list_directory: exception: {e}")
        return f"Error listing directory '{path}': {e}"


def run_command(command: str, command_timeout: Any = None) -> str:
    timeout = _coerce_command_timeout(command_timeout)
    log.info(f"run_command called with command={command}, timeout={timeout}s")
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.getcwd(),
            errors='ignore',
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        stdout, stderr = process.communicate(timeout=timeout)
        stdout = (stdout or "").strip()
        stderr = (stderr or "").strip()
        exit_code = process.returncode

        log.info(f"run_command: exit_code={exit_code}, stdout_len={len(stdout)}, stderr_len={len(stderr)}")

        output = f"Exit Code: {exit_code}\n"
        if stdout:
            if len(stdout) > 50_000:
                stdout = stdout[:50_000] + "\n\n[WARNING: STDOUT truncated after 50,000 characters]"
            output += f"STDOUT:\n{_redact_sensitive_text(stdout)}\n"
        if stderr:
            if len(stderr) > 20_000:
                stderr = stderr[:20_000] + "\n\n[WARNING: STDERR truncated after 20,000 characters]"
            output += f"STDERR:\n{_redact_sensitive_text(stderr)}\n"
        if not stdout and not stderr:
            output += "(no output)\n"
        return output
    except subprocess.TimeoutExpired:
        if process is not None:
            _terminate_process_tree(process.pid)
            try:
                process.communicate(timeout=2)
            except Exception:
                pass
        log.warning(f"run_command: command timed out after {timeout}s: {command}")
        return f"Error: Command timed out after {timeout} seconds."
    except Exception as e:
        log.error(f"run_command: exception: {e}")
        return f"Error running command: {e}"


def grep_search(pattern: str, path: str) -> str:
    log.info(f"grep_search called with pattern={pattern}, path={path}")
    try:
        if not os.path.exists(path):
            log.warning(f"grep_search: path does not exist: {path}")
            return f"Error: Path '{path}' does not exist."
        if os.path.isfile(path) and _is_sensitive_path(path):
            log.warning(f"grep_search: blocked sensitive path: {path}")
            return f"Error: Refusing to search sensitive file '{path}'."

        # Compile pattern (case-insensitive by default)
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except Exception as e:
            return f"Error: Invalid search pattern: {e}"

        # Standard directories to skip (prevents walking huge virtual environments)
        skip_dirs = {
            ".git", "venv", ".venv", ".venv-torch", ".venv-xpu",
            "node_modules", "__pycache__", ".ruff_cache", ".pytest_cache", ".claude"
        }

        matches = []
        max_matches = 50
        max_files = 3_000
        max_file_size = 500_000  # Skip files larger than 500 KB to avoid slow-down
        max_seconds = 8.0
        files_seen = 0
        deadline = time.monotonic() + max_seconds
        stopped_reason = ""

        def timed_out() -> bool:
            return time.monotonic() >= deadline

        def search_file(file_path: str) -> None:
            nonlocal files_seen, stopped_reason
            try:
                if timed_out():
                    stopped_reason = f"search stopped after {max_seconds:g}s"
                    return
                files_seen += 1
                if files_seen > max_files:
                    stopped_reason = f"search stopped after {max_files} files"
                    return
                if _is_sensitive_path(file_path):
                    return
                if os.path.getsize(file_path) > max_file_size:
                    return
                # Skip binary file extensions
                _, ext = os.path.splitext(file_path.lower())
                if ext in {'.exe', '.dll', '.so', '.pyc', '.png', '.jpg', '.jpeg', '.gif', '.zip', '.tar', '.gz', '.pdf', '.onnx', '.onnx.txt'}:
                    return

                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        if regex.search(line):
                            line_text = _redact_sensitive_text(line.strip())
                            matches.append(f"{file_path}:{line_num}: {line_text}")
                            if len(matches) >= max_matches:
                                return
                        if timed_out():
                            stopped_reason = f"search stopped after {max_seconds:g}s"
                            return
            except Exception:
                pass

        # Perform the search
        if os.path.isfile(path):
            search_file(path)
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                # Prune directory list in-place so os.walk skips them
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                if timed_out():
                    stopped_reason = f"search stopped after {max_seconds:g}s"
                    break
                for file in files:
                    search_file(os.path.join(root, file))
                    if len(matches) >= max_matches or stopped_reason:
                        break
                if len(matches) >= max_matches or stopped_reason:
                    break

        if not matches:
            if stopped_reason:
                return (
                    f"No matches found for '{pattern}' in '{path}'. "
                    f"[WARNING: {stopped_reason}; searched {min(files_seen, max_files)} files.]"
                )
            return f"No matches found for '{pattern}' in '{path}'."

        output = "\n".join(matches)
        if len(matches) >= max_matches:
            output += f"\n... (maximum of {max_matches} matches reached)"
        if stopped_reason:
            output += f"\n[WARNING: {stopped_reason}; searched {min(files_seen, max_files)} files.]"
        return output
    except Exception as e:
        log.error(f"grep_search: exception: {e}")
        return f"Error searching: {e}"


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

def execute_tool(name: str, arguments: str) -> str:
    log.info(f"execute_tool called: name={name}, arguments={arguments}")
    if not arguments:
        log.warning(f"execute_tool: no arguments provided for '{name}'")
        return f"Error: No arguments provided for tool '{name}'."
    try:
        args = json.loads(arguments)
    except (json.JSONDecodeError, TypeError) as e:
        log.error(f"execute_tool: failed to parse arguments for '{name}': {e}")
        return f"Error: Invalid JSON arguments for tool '{name}'."

    if name == "read_file":
        return read_file(args.get("path", ""))
    elif name == "write_file":
        return write_file(args.get("path", ""), args.get("content", ""))
    elif name == "list_directory":
        return list_directory(args.get("path", ""))
    elif name == "run_command":
        return run_command(args.get("command", ""), args.get("command_timeout"))
    elif name == "grep_search":
        return grep_search(args.get("pattern", ""), args.get("path", ""))
    else:
        log.warning(f"execute_tool: unknown tool '{name}'")
        return f"Error: Unknown tool '{name}'."
