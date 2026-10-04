import logging
import os
import shlex
import shutil
from typing import Callable, List, Optional

from hawk.providers.base import BaseProvider
from hawk.providers.claude_code_provider import ClaudeCodeProvider
from hawk.providers.cli_provider import CLIProvider
from hawk.providers.codex_cli_provider import CodexCLIProvider
from hawk.providers.openai_provider import (
    AlibabaProvider,
    BaseOpenAIProvider,
    GeminiProvider,
    MoonshotProvider,
    OpenRouterProvider,
    display_name_from_model,
)

log = logging.getLogger("hawk.providers")

# Free / low-cost OpenAI-compatible providers. Each is enabled only when its
# API key env var is present. Model and base URL can be overridden per provider
# via ``<NAME>_MODEL`` and ``<NAME>_BASE_URL``; tool-calling is opt-in via
# ``<NAME>_TOOLS=on`` because those tools can read, write, and run commands.
#   (name, env_key, base_url, default_model, color)
_FREE_API_PROVIDERS: list[tuple[str, str, str, str, str]] = [
    ("Groq",     "GROQ_API_KEY",     "https://api.groq.com/openai/v1",                            "llama-3.3-70b-versatile",     "green"),
    ("Cerebras", "CEREBRAS_API_KEY", "https://api.cerebras.ai/v1",                                "llama-3.3-70b",               "magenta"),
    ("Gemini",   "GEMINI_API_KEY",   "https://generativelanguage.googleapis.com/v1beta/openai/",  "gemini-2.5-flash",            "blue"),
    ("Mistral",  "MISTRAL_API_KEY",  "https://api.mistral.ai/v1",                                 "mistral-small-latest",        "red"),
    ("NVIDIA",      "NVIDIA_API_KEY",      "https://integrate.api.nvidia.com/v1",                       "deepseek-ai/deepseek-v4.1-flash" , "cyan"),
    ("TokenHarbor", "TOKENHARBOR_API_KEY", "https://tokenharbor.ai/v1",                                 "deepseek-v4.1-flash:free",    "yellow"),
    ("OllamaCloud", "OLLAMA_API_KEY",      "https://ollama.com/v1",                                     "gpt-oss:120b",                "white"),
]

_PALETTE: list[str] = ["magenta", "green", "blue", "cyan", "yellow", "red", "white"]


def _env_flag(name: str, default: Optional[bool] = None) -> Optional[bool]:
    """Parse a boolean-ish env var. Returns ``default`` when unset."""
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _safe_add(clients: List[BaseProvider], factory: Callable[[], BaseProvider], label: str) -> None:
    """Construct a provider, logging and skipping on failure instead of crashing startup."""
    try:
        clients.append(factory())
        log.info(f"Enabled provider: {label}")
    except Exception as e:
        log.warning(f"Skipping provider '{label}': {e}")


def _friendly_name(model: str) -> str:
    """Derive a short display name from a model id (e.g. deepseek/deepseek-r1:free -> 'Deepseek R1')."""
    core = model.split("/")[-1].split(":")[0]
    return core.replace("-", " ").replace("_", " ").title()


def _openai_provider_factory(
    name: str,
    model: str,
    color: str,
    base_url: str,
    api_key: str,
    uses_custom_tools: bool,
) -> Callable[[], BaseProvider]:
    def factory() -> BaseProvider:
        return BaseOpenAIProvider(
            name,
            model,
            color,
            base_url,
            api_key,
            uses_custom_tools=uses_custom_tools,
        )

    return factory


def _cli_enabled(flag_env: str) -> bool:
    """Decide whether a CLI-backed provider should be added.

    CLI providers can execute commands through their native tools, so they are
    explicit opt-in: ``<flag>`` must be on. ``npx`` is still required because
    the providers launch through it.
    """
    flag = _env_flag(flag_env)
    if flag is not True:
        return False
    npx_available = shutil.which("npx") is not None
    if not npx_available:
        log.warning(f"{flag_env}=on but 'npx' was not found on PATH; skipping CLI provider.")
    return npx_available


def _with_agy_model(args: List[str], model: str) -> List[str]:
    """Add Agy's --model flag unless the configured command already has one."""
    if "--model" in args:
        return args
    return [args[0], "--model", model, *args[1:]] if args else args


def create_clients() -> List[BaseProvider]:
    """
    Factory that assembles the active panel of LLM providers from the
    environment. Designed to degrade gracefully: any provider that is not
    configured or fails to initialize is simply skipped (logged as a warning)
    so the app still runs with whatever is available.

    Enablement summary:
        * Free API providers (Groq, Cerebras, Gemini, Mistral, NVIDIA,
          Token Harbor, Ollama Cloud) - enabled when their API key env var is set.
        * Local Ollama - enabled when ``OLLAMA_MODEL`` is set (no key needed).
        * OpenRouter - a free-model hawk when ``OPENROUTER_FREE_MODELS`` is
          set, otherwise the legacy paid provider set (backwards compatible).
        * Agy CLI - preferred Gemini CLI path when ``AGY_CLI_CMD`` is set.
        * Claude Code / Codex CLIs - subscription providers, added only when
          explicitly enabled and ``npx`` is present.
    """
    clients: List[BaseProvider] = []
    agy_cli = os.getenv("AGY_CLI_CMD")

    # 1. Free OpenAI-compatible API providers (key-gated)
    for name, env_key, base_url, default_model, color in _FREE_API_PROVIDERS:
        if name == "Gemini" and agy_cli:
            log.info("Skipping Gemini API provider because AGY_CLI_CMD is configured.")
            continue
        api_key = os.getenv(env_key)
        if not api_key:
            continue
        model = os.getenv(f"{name.upper()}_MODEL", default_model)
        base = os.getenv(f"{name.upper()}_BASE_URL", base_url)
        tools = _env_flag(f"{name.upper()}_TOOLS", default=False)
        _safe_add(
            clients,
            _openai_provider_factory(
                display_name_from_model(model),
                model,
                color,
                base,
                api_key,
                uses_custom_tools=bool(tools),
            ),
            f"{name} ({model})",
        )

    # 2. Local Ollama - no key required; supports one or more comma-separated models
    ollama_models = os.getenv("OLLAMA_MODEL", "")
    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    ollama_tools = _env_flag("OLLAMA_TOOLS", default=False)
    ollama_list = [m.strip() for m in ollama_models.split(",") if m.strip()]
    for i, model in enumerate(ollama_list):
        name = f"Ollama-{_friendly_name(model)}" if len(ollama_list) > 1 else "Ollama"
        color = _PALETTE[i % len(_PALETTE)]
        _safe_add(
            clients,
            _openai_provider_factory(
                name if len(ollama_list) > 1 else display_name_from_model(model),
                model,
                color,
                ollama_base,
                "ollama",
                uses_custom_tools=bool(ollama_tools),
            ),
            f"{name} ({model})",
        )

    # 3. OpenRouter
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    free_list = [m.strip() for m in os.getenv("OPENROUTER_FREE_MODELS", "").split(",") if m.strip()]
    if openrouter_key and free_list:
        # Single-key free panel: one panelist per free model
        or_tools = _env_flag("OPENROUTER_FREE_TOOLS", default=False)
        for i, model in enumerate(free_list):
            name = _friendly_name(model)
            color = _PALETTE[i % len(_PALETTE)]
            _safe_add(
                clients,
                _openai_provider_factory(
                    name,
                    model,
                    color,
                    "https://openrouter.ai/api/v1",
                    openrouter_key,
                    uses_custom_tools=bool(or_tools),
                ),
                f"{name} ({model}, OpenRouter free)",
            )
    elif openrouter_key:
        # Legacy paid OpenRouter set (kept for backwards compatibility)
        _safe_add(clients, OpenRouterProvider, "OpenRouter")
        _safe_add(clients, MoonshotProvider, "Moonshot (via OpenRouter)")
        _safe_add(clients, AlibabaProvider, "Alibaba (via OpenRouter)")
        if not agy_cli:
            _safe_add(clients, GeminiProvider, "Gemini (via OpenRouter)")
        else:
            log.info("Skipping Gemini via OpenRouter because AGY_CLI_CMD is configured.")

    # 4. Agy CLI wrapper if explicitly configured
    if agy_cli:
        agy_model = os.getenv("AGY_MODEL", "Gemini 3.1 Pro (High)")
        agy_display = os.getenv("AGY_DISPLAY_NAME", "Gemini 3.1 Pro high")
        agy_args = _with_agy_model(shlex.split(agy_cli), agy_model)
        _safe_add(
            clients,
            lambda: CLIProvider(
                agy_display,
                agy_args,
                color="blue",
                model_name=agy_model,
                prompt_transport="argument_file",
            ),
            "Agy CLI",
        )

    # 5. Claude Code CLI (subscription) - only when available/enabled
    if _cli_enabled("ENABLE_CLAUDE_CLI"):
        claude_model = os.getenv("CLAUDE_MODEL", "claude-opus-4-8")
        permission_mode = os.getenv("CLAUDE_PERMISSION_MODE") or None
        _safe_add(
            clients,
            lambda: ClaudeCodeProvider(model_name=claude_model, permission_mode=permission_mode),
            f"Claude Code CLI ({claude_model})",
        )

    # 6. Codex CLI (subscription) - only when available/enabled
    if _cli_enabled("ENABLE_CODEX_CLI"):
        codex_model = os.getenv("CODEX_MODEL", "gpt-5.5")
        reasoning_effort = (
            os.getenv("CODEX_REASONING_EFFORT")
            or os.getenv("CODEX_EFFORT")
            or None
        )
        bypass_sandbox = bool(_env_flag("CODEX_BYPASS_SANDBOX", default=False))
        _safe_add(
            clients,
            lambda: CodexCLIProvider(
                model_name=codex_model,
                bypass_sandbox=bypass_sandbox,
                reasoning_effort=reasoning_effort,
            ),
            f"Codex CLI ({codex_model}{' ' + reasoning_effort if reasoning_effort else ''})",
        )

    # Deduplicate by display name (panes/votes are keyed on name downstream)
    unique: List[BaseProvider] = []
    seen = set()
    for c in clients:
        if c.name in seen:
            log.warning(f"Duplicate provider name '{c.name}' skipped.")
            continue
        seen.add(c.name)
        unique.append(c)

    if not unique:
        log.warning("create_clients: no providers configured or available.")
    return unique
