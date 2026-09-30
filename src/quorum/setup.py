"""First-run setup wizard for Quorum.

When no LLM providers are configured, this module walks the user through
their options and writes a ``.env`` file. Setup is the first thing that
happens on launch until at least one provider is available.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from quorum.providers import create_clients

# Default free-model quorum - three distinct panelists from one OpenRouter key.
DEFAULT_OPENROUTER_FREE_MODELS = (
    "deepseek/deepseek-r1:free,"
    " meta-llama/llama-3.3-70b-instruct:free,"
    " qwen/qwen3-coder:free"
)

# Free API providers: (display name, env var, signup URL, blurb)
FREE_API_OPTIONS: List[Tuple[str, str, str, str]] = [
    (
        "Groq",
        "GROQ_API_KEY",
        "https://console.groq.com/keys",
        "Fast inference; Llama 3.3 70B free tier (~30 req/min).",
    ),
    (
        "Cerebras",
        "CEREBRAS_API_KEY",
        "https://cloud.cerebras.ai",
        "Very fast; ~1M tokens/day free.",
    ),
    (
        "Google Gemini",
        "GEMINI_API_KEY",
        "https://aistudio.google.com/apikey",
        "Gemini 2.5 Flash/Pro; generous free tier, no card.",
    ),
    (
        "Mistral",
        "MISTRAL_API_KEY",
        "https://console.mistral.ai/api-keys",
        "Mistral Small; ~1B tokens/month free (slow rate limit).",
    ),
    (
        "GitHub Models",
        "GITHUB_TOKEN",
        "https://github.com/settings/tokens",
        "GPT-4o-mini, Llama 3.3 70B, etc. with any GitHub PAT.",
    ),
    (
        "NVIDIA NIM",
        "NVIDIA_API_KEY",
        "https://build.nvidia.com/",
        "Llama 3.3 70B, DeepSeek R1; generous free tier.",
    ),
    (
        "Token Harbor",
        "TOKENHARBOR_API_KEY",
        "https://tokenharbor.ai/keys",
        "DeepSeek V4.1 Flash free tier via Token Harbor gateway.",
    ),
]


def resolve_env_path() -> Path:
    """Return the preferred ``.env`` path (project root, else cwd)."""
    # src/quorum/setup.py -> project root is three levels up
    module_root = Path(__file__).resolve().parent.parent.parent
    project_env = module_root / ".env"
    if project_env.exists():
        return project_env
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        return cwd_env
    return project_env


def load_quorum_env(env_path: Path) -> None:
    """Load environment from the resolved ``.env`` path."""
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path), override=True)
    else:
        load_dotenv(override=True)


def has_configured_providers() -> bool:
    """True when ``create_clients()`` would return at least one provider."""
    return bool(create_clients())


def upsert_env_vars(env_path: Path, updates: Dict[str, str]) -> None:
    """Create or update keys in ``.env`` without dropping unrelated entries."""
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    seen: set[str] = set()

    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            if not raw.strip() or raw.lstrip().startswith("#"):
                lines.append(raw)
                continue
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", raw.strip())
            if not match:
                lines.append(raw)
                continue
            key = match.group(1)
            if key in updates:
                lines.append(f"{key}={updates[key]}")
                seen.add(key)
            else:
                lines.append(raw)
                seen.add(key)

    if not env_path.exists():
        lines.append("# Quorum - LLM provider configuration")
        lines.append("# Docs: see .env.example in the project root")
        lines.append("")

    for key, value in updates.items():
        if key not in seen:
            lines.append(f"{key}={value}")

    env_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _print_options_overview(console: Console) -> None:
    console.print(
        Panel(
            "[bold]Quorum needs at least one LLM to chat; three or more for a real panel debate.[/bold]\n\n"
            "You do [bold]not[/bold] need paid subscriptions. Common free paths:\n"
            "  - [cyan]OpenRouter[/cyan] - one free key, three free models (easiest quorum)\n"
            "  - [cyan]Free API keys[/cyan] - Groq, Cerebras, Gemini, Mistral, GitHub, NVIDIA\n"
            "  - [cyan]Ollama[/cyan] - run models locally, no key\n"
            "  - [cyan]CLI subscriptions[/cyan] - Claude Code / Codex if you already pay for them\n\n"
            "[dim]All keys are stored in your local .env file only.[/dim]",
            title="Welcome - model setup",
            border_style="yellow",
        )
    )


def _print_catalog(console: Console) -> None:
    table = Table(title="Free API providers (pick any combination)", show_header=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Provider")
    table.add_column("Env variable")
    table.add_column("Notes")

    for i, (name, env_key, _url, blurb) in enumerate(FREE_API_OPTIONS, 1):
        table.add_row(str(i), name, env_key, blurb)

    console.print(table)
    console.print(
        "\n[bold]OpenRouter free quorum[/bold] - set OPENROUTER_API_KEY + OPENROUTER_FREE_MODELS\n"
        "[bold]Ollama[/bold] - set OLLAMA_MODEL=llama3.1 (comma-separate for multiple panelists)\n"
        "[bold]CLI subscriptions[/bold] - ENABLE_CLAUDE_CLI=1 / ENABLE_CODEX_CLI=1 "
        "(requires npx + active subscription)\n"
    )


def _prompt_key(console: Console, label: str, signup_url: str) -> Optional[str]:
    console.print(f"\n[bold]{label}[/bold]")
    console.print(f"[dim]Get a free key: {signup_url}[/dim]")
    value = console.input("[yellow]Paste API key (Enter to skip):[/yellow] ").strip()
    return value or None


def _setup_openrouter_free(console: Console, env_path: Path) -> bool:
    console.print(
        Panel(
            "[bold]Recommended for beginners[/bold]\n\n"
            "One free OpenRouter account gives you three panelists at no cost:\n"
            "  - DeepSeek R1 (reasoning)\n"
            "  - Llama 3.3 70B (general)\n"
            "  - Qwen3 Coder (coding)\n\n"
            "Sign up: [link=https://openrouter.ai/keys]openrouter.ai/keys[/link] "
            "(no credit card for free models)",
            border_style="green",
        )
    )
    key = _prompt_key(console, "OpenRouter API key", "https://openrouter.ai/keys")
    if not key:
        return False
    upsert_env_vars(
        env_path,
        {
            "OPENROUTER_API_KEY": key,
            "OPENROUTER_FREE_MODELS": DEFAULT_OPENROUTER_FREE_MODELS,
            "OPENROUTER_FREE_TOOLS": "off",
        },
    )
    console.print(f"[green]Saved to {env_path}[/green]")
    return True


def _setup_free_api(console: Console, env_path: Path) -> bool:
    _print_catalog(console)
    console.print(
        "[dim]Enter the numbers of providers to add (e.g. 1,3,5) or 'all'.[/dim]"
    )
    choice = console.input("[yellow]Which providers?[/yellow] ").strip().lower()
    if not choice:
        return False

    selected: List[Tuple[str, str, str, str]] = []
    if choice == "all":
        selected = list(FREE_API_OPTIONS)
    else:
        for part in re.split(r"[,\s]+", choice):
            if not part.isdigit():
                continue
            idx = int(part) - 1
            if 0 <= idx < len(FREE_API_OPTIONS):
                selected.append(FREE_API_OPTIONS[idx])

    if not selected:
        console.print("[red]No valid providers selected.[/red]")
        return False

    updates: Dict[str, str] = {}
    tool_flags = {
        "GROQ_API_KEY": "GROQ_TOOLS",  # pragma: allowlist secret
        "CEREBRAS_API_KEY": "CEREBRAS_TOOLS",  # pragma: allowlist secret
        "GEMINI_API_KEY": "GEMINI_TOOLS",  # pragma: allowlist secret
        "MISTRAL_API_KEY": "MISTRAL_TOOLS",  # pragma: allowlist secret
        "GITHUB_TOKEN": "GITHUB_TOOLS",
        "NVIDIA_API_KEY": "NVIDIA_TOOLS",  # pragma: allowlist secret
        "TOKENHARBOR_API_KEY": "TOKENHARBOR_TOOLS",  # pragma: allowlist secret
    }
    for name, env_key, url, _blurb in selected:
        key = _prompt_key(console, name, url)
        if key:
            updates[env_key] = key
            flag = tool_flags.get(env_key)
            if flag:
                updates[flag] = "off"

    if not updates:
        return False

    upsert_env_vars(env_path, updates)
    console.print(f"[green]Saved {len([k for k in updates if k.endswith('_KEY') or k.endswith('_TOKEN')])} key(s) to {env_path}[/green]")
    return True


def _setup_ollama(console: Console, env_path: Path) -> bool:
    console.print(
        Panel(
            "Run models locally with [bold]Ollama[/bold] - free, offline, no API key.\n\n"
            "1. Install: [link=https://ollama.com]ollama.com[/link]\n"
            "2. Pull a model: [cyan]ollama pull llama3.1[/cyan]\n"
            "3. Enter model name(s) below (comma-separated for multiple panelists)",
            border_style="blue",
        )
    )
    models = console.input(
        "[yellow]Model name(s), e.g. llama3.1 or llama3.1,qwen2.5-coder:[/yellow] "
    ).strip()
    if not models:
        return False
    upsert_env_vars(
        env_path,
        {
            "OLLAMA_MODEL": models,
            "OLLAMA_TOOLS": "off",
        },
    )
    console.print(f"[green]Saved Ollama config to {env_path}[/green]")
    return True


def _setup_cli_subscriptions(console: Console, env_path: Path) -> bool:
    npx_ok = shutil.which("npx") is not None
    console.print(
        Panel(
            "For users who already pay for [bold]Claude Code[/bold] or [bold]Codex[/bold] "
            "subscriptions.\n\n"
            f"npx on PATH: {'[green]yes[/green]' if npx_ok else '[red]no - install Node.js first[/red]'}\n\n"
            "You must be logged in to those CLIs separately "
            "(e.g. [cyan]npx @anthropic-ai/claude-code[/cyan]).",
            border_style="magenta",
        )
    )
    updates: Dict[str, str] = {}
    if console.input("[yellow]Enable Claude Code CLI? (y/N):[/yellow] ").strip().lower() in ("y", "yes"):
        updates["ENABLE_CLAUDE_CLI"] = "on"
        model = console.input("[dim]CLAUDE_MODEL[/dim] [Enter=claude-opus-4-8]: ").strip()
        if model:
            updates["CLAUDE_MODEL"] = model
    if console.input("[yellow]Enable Codex CLI? (y/N):[/yellow] ").strip().lower() in ("y", "yes"):
        updates["ENABLE_CODEX_CLI"] = "on"
        model = console.input("[dim]CODEX_MODEL[/dim] [Enter=gpt-5.5]: ").strip()
        updates["CODEX_MODEL"] = model or "gpt-5.5"
        effort = console.input("[dim]CODEX_REASONING_EFFORT[/dim] [Enter=xhigh]: ").strip()
        updates["CODEX_REASONING_EFFORT"] = effort or "xhigh"

    if not updates:
        return False
    upsert_env_vars(env_path, updates)
    console.print(f"[green]Saved CLI settings to {env_path}[/green]")
    return True


def _show_env_location(console: Console, env_path: Path) -> None:
    example = env_path.parent / ".env.example"
    console.print(
        Panel(
            f"Edit manually: [cyan]{env_path}[/cyan]\n"
            f"Reference template: [cyan]{example}[/cyan]\n\n"
            "After editing, restart Quorum or run [bold]/setup[/bold] again.",
            title="Manual configuration",
            border_style="dim",
        )
    )


def run_setup_wizard(console: Console, env_path: Optional[Path] = None) -> bool:
    """
    Interactive first-run setup. Returns True when at least one provider
    is configured after the wizard finishes.
    """
    env_path = env_path or resolve_env_path()
    _print_options_overview(console)

    while True:
        console.print("\n[bold]Setup menu[/bold]")
        console.print("  [green]1[/green]  OpenRouter free quorum [dim](recommended - 1 key, 3 models)[/dim]")
        console.print("  [cyan]2[/cyan]  Add free API provider key(s)")
        console.print("  [blue]3[/blue]  Local Ollama (no key)")
        console.print("  [magenta]4[/magenta]  Subscription CLIs (Claude Code / Codex)")
        console.print("  [dim]5[/dim]  View all provider options")
        console.print("  [dim]6[/dim]  Manual .env edit (show file paths)")
        console.print("  [dim]q[/dim]  Quit without starting\n")

        choice = console.input("[bold yellow]Choose:[/bold yellow] ").strip().lower()

        changed = False
        if choice == "1":
            changed = _setup_openrouter_free(console, env_path)
        elif choice == "2":
            changed = _setup_free_api(console, env_path)
        elif choice == "3":
            changed = _setup_ollama(console, env_path)
        elif choice == "4":
            changed = _setup_cli_subscriptions(console, env_path)
        elif choice == "5":
            _print_catalog(console)
            continue
        elif choice == "6":
            _show_env_location(console, env_path)
            continue
        elif choice in ("q", "quit", "exit"):
            return False
        else:
            console.print("[red]Invalid choice.[/red]")
            continue

        if changed:
            load_quorum_env(env_path)
            clients = create_clients()
            if clients:
                names = ", ".join(f"@{c.name}" for c in clients)
                console.print(
                    Panel(
                        f"[green]Setup complete![/green] Active panel: {names}\n\n"
                        "Tip: run a debate with [bold]/quorum 2 your question[/bold]",
                        border_style="green",
                    )
                )
                return True
            console.print(
                "[yellow]Settings saved, but no providers activated yet. "
                "Add another key or check your .env.[/yellow]"
            )

    return False


def print_panel_size_hint(console: Console, panel_size: int) -> None:
    """Nudge users toward a 3+ panelist quorum when the panel is thin."""
    if panel_size >= 3:
        return
    need = 3 - panel_size
    word = "panelist" if panel_size == 1 else "panelists"
    console.print(
        f"[dim]Tip: {panel_size} {word} active - add {need} more for a richer "
        f"quorum debate ([bold]/setup[/bold]).[/dim]\n"
    )


def ensure_providers_configured(console: Console) -> bool:
    """
    Block on first-run setup until providers exist or the user quits.
    Returns True when Quorum can proceed.
    """
    env_path = resolve_env_path()
    load_quorum_env(env_path)

    if has_configured_providers():
        return True

    console.print(
        "\n[bold yellow]No models configured yet - let's set that up first.[/bold yellow]\n"
    )
    return run_setup_wizard(console, env_path)
