import asyncio
import logging
import os
import re
import sys
from typing import List, Tuple

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from hawk.models.schemas import Message
from hawk.prompts import (
    DRIVER_SYSTEM_PROMPT,
    SYNTHESIZER_SYSTEM_PROMPT,
    build_global_system_prompt,
    build_synthesis_prompt,
)
from hawk.providers import create_clients
from hawk.providers.base import BaseProvider
from hawk.setup import (
    ensure_providers_configured,
    load_hawk_env,
    print_panel_size_hint,
    resolve_env_path,
    run_setup_wizard,
)
from hawk.ui_layout import SpectacleHawk
from hawk.voting import APPROVED, REJECTED, Decision, format_tally

# Configure logging - writes to hawk.log in current working directory
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("hawk.log", mode="w", encoding="utf-8"),
    ]
)
# Silence noisy HTTP libraries so the log stays readable
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("markdown_it").setLevel(logging.WARNING)

log = logging.getLogger("hawk.main")

# Caps to keep prompt injection from blowing up the context window.
_MAX_FILE_INJECT_CHARS = 30_000   # per file
_MAX_TOTAL_INJECT_CHARS = 100_000  # across all injected paths
_SKIP_PATH_PARTS = {"venv", ".venv", ".git", "node_modules", "__pycache__", "site-packages"}

def expand_paths_in_prompt(prompt: str) -> str:
    potential_paths = set()
    # Find quoted strings
    quoted = re.findall(r'["\'](.*?)["\']', prompt)
    potential_paths.update(quoted)
    # Find standalone words that might be paths
    words = [w.strip('.,?!;') for w in prompt.split()]
    potential_paths.update(words)

    additions = []
    total_chars = 0
    for path in sorted(potential_paths):
        if not path or len(path) < 2:
            continue
        # Only treat tokens that clearly look like paths (contain a separator)
        if not (":" in path or "/" in path or "\\" in path):
            continue
        # Don't walk into dependency/VCS directories
        if any(part in _SKIP_PATH_PARTS for part in re.split(r"[\\/]+", path)):
            continue
        if total_chars >= _MAX_TOTAL_INJECT_CHARS:
            break

        if not os.path.exists(path):
            continue

        if os.path.isfile(path):
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(_MAX_FILE_INJECT_CHARS + 1)
                truncated = len(content) > _MAX_FILE_INJECT_CHARS
                content = content[:_MAX_FILE_INJECT_CHARS]
                note = "\n... (truncated)" if truncated else ""
                block = f"\n--- Contents of FILE: {path} ---\n{content}{note}\n--- END FILE ---"
                additions.append(block)
                total_chars += len(block)
            except Exception as e:
                additions.append(f"\n--- FILE: {path} (Error reading: {e}) ---")
        elif os.path.isdir(path):
            try:
                files = os.listdir(path)
                files_str = "\n".join(files[:100])  # Limit to 100 entries
                if len(files) > 100:
                    files_str += "\n... (truncated)"
                block = f"\n--- Contents of DIRECTORY: {path} ---\n{files_str}\n--- END DIRECTORY ---"
                additions.append(block)
                total_chars += len(block)
            except Exception:
                pass

    if additions:
        return prompt + "\n\n[SYSTEM INJECTED LOCAL PATHS]:\n" + "\n".join(additions)
    return prompt


def choose_driver(clients: List[BaseProvider], preferred: str = "") -> BaseProvider:
    """Select the active driver from available clients.

    Checks preferred parameter or HAWK_DRIVER env var first.
    Matches by 1-based index, exact name, or partial name.
    Falls back to Claude if present, then the first client.
    """
    if not clients:
        raise ValueError("No clients available")

    target = (preferred or os.getenv("HAWK_DRIVER") or "").strip().lower().lstrip("@")
    if target:
        if target.isdigit():
            idx = int(target) - 1
            if 0 <= idx < len(clients):
                return clients[idx]
        for c in clients:
            if c.name.lower() == target:
                return c
        for c in clients:
            if target in c.name.lower():
                return c
        log.warning(f"HAWK_DRIVER={target!r} not found on panel; using default driver")

    for c in clients:
        if "claude" in c.name.lower():
            return c
    return clients[0]


async def run_hawk(
    prompt: str,
    num_rounds: int,
    clients: List[BaseProvider],
    driver: BaseProvider,
    console: Console,
) -> Tuple[str, Decision]:
    spectacle = SpectacleHawk(clients)

    console.clear()

    responses, full_history, decision = await spectacle.run_rounds(prompt, num_rounds)

    # THE DECISION IS PRINTED BEFORE THE PROSE, AND BY CODE. It comes from the
    # ballots via hawk.voting.decide(); the synthesizer below is itself one of
    # the panelists, so anything it writes is a summary of this result, never
    # the result. Colour follows the outcome so a NO CONSENSUS cannot be skimmed
    # as agreement.
    outcome_style = {
        APPROVED: "bold white on green",
        REJECTED: "bold white on red",
    }.get(decision.outcome, "bold black on yellow")
    console.print("\n" + "=" * 50)
    console.print(Text(f" PANEL DECISION: {decision.headline} ", style=outcome_style, justify="center"))
    console.print("=" * 50)
    console.print(f"[dim]{format_tally(decision.counts, 'Final')} - {decision.reason}[/dim]\n")

    synthesis_prompt = build_synthesis_prompt(
        prompt, num_rounds, full_history, decision.summary()
    )

    synthesizer = driver

    console.print(Text(" SYNTHESIZING CONCLUSIONS ", style="bold white on blue", justify="center"))
    console.print()

    with console.status(f"[bold {synthesizer.color}]@{synthesizer.name} is synthesizing..."):
        final_conclusion = await synthesizer.generate_response(
            SYNTHESIZER_SYSTEM_PROMPT,
            [Message(role="user", content=synthesis_prompt)]
        )

    console.print(Panel(
        Markdown(final_conclusion),
        title=f"summary by @{synthesizer.name} (a panelist)",
        border_style="green",
    ))
    return final_conclusion, decision

async def main() -> None:
    console = Console()

    header_text = Text(" Q U O R U M ", style="bold white on blue", justify="center")
    console.print(Panel(header_text, border_style="blue", padding=(1, 5)))
    console.print("[dim]Interactive Coding Assistant with Persistent Hawk CLIs[/dim]\n", justify="center")

    env_path = resolve_env_path()
    if not ensure_providers_configured(console):
        console.print("[dim]Setup incomplete. Run [bold]hawk[/bold] again when ready.[/dim]")
        return

    # Reload after wizard may have written .env
    load_hawk_env(env_path)

    clients = create_clients()
    if not clients:
        console.print(
            Panel(
                "[bold red]No active providers.[/bold red] Run [bold]/setup[/bold] "
                "or edit your .env (see .env.example).",
                border_style="red",
            )
        )
        return

    cwd = os.getcwd()
    client_names_list = ", ".join([f"@{c.name}" for c in clients])

    with console.status("[bold cyan]Initializing persistent background sessions...[/bold cyan]"):
        # Each provider gets a system prompt tailored to whether it uses
        # Hawk's custom tools or its own native CLI tools.
        init_tasks = [
            c.start_session(
                build_global_system_prompt(client_names_list, cwd, c.uses_custom_tools)
            )
            for c in clients
        ]
        results = await asyncio.gather(*init_tasks, return_exceptions=True)

        active_clients = []
        for client, result in zip(clients, results):
            if isinstance(result, Exception):
                console.print(f"[yellow]Warning: Could not start {client.name} ({result})[/yellow]")
            else:
                active_clients.append(client)
        clients = active_clients

    if not clients:
        console.print("[red]Error: All models failed to initialize.[/red]")
        return

    cli_driver = ""
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg in ("--driver", "-d") and i < len(sys.argv) - 1:
            cli_driver = sys.argv[i + 1]
            break
        elif arg.startswith("--driver="):
            cli_driver = arg.split("=", 1)[1]
            break

    driver = choose_driver(clients, preferred=cli_driver)

    client_tags = [f"[{c.color}]@{c.name}[/{c.color}]" for c in clients]
    console.print(f"[bold]Available Models:[/bold] {', '.join(client_tags)}")
    console.print(f"[bold]Current Driver:[/bold] [{driver.color}]@{driver.name}[/{driver.color}]\n")
    print_panel_size_hint(console, len(clients))
    console.print("[dim]Type '/driver [model]' to change driver. "
                  "Type '/hawk \\[rounds] <prompt>' to summon the panel. "
                  "Type '/setup' to change models. Type 'exit' to quit.[/dim]\n")

    history: List[Message] = []

    try:
        while True:
            user_input = console.input("[bold yellow]You:[/bold yellow] ")
            if user_input.strip().lower() in ['exit', 'quit']:
                break
            if not user_input.strip():
                continue

            if user_input.strip().lower() in ("/help", "help"):
                console.print(
                    "\n[bold]Commands:[/bold]\n"
                    "  [cyan]/driver [name or number][/cyan] - View or change the active driver\n"
                    "  [cyan]/hawk [rounds] <prompt>[/cyan] - Summon the panel for debate & vote\n"
                    "  [cyan]/setup[/cyan]                     - Change model configuration\n"
                    "  [cyan]exit[/cyan]                       - Quit Hawk\n"
                )
                continue

            if user_input.strip().lower().startswith(("/driver", "/model")):
                parts = user_input.strip().split(maxsplit=1)
                target = parts[1].strip() if len(parts) > 1 else ""
                if not target:
                    console.print("\n[bold]Available Models:[/bold]")
                    for idx, c in enumerate(clients, 1):
                        current_mark = " [bold green](current)[/bold green]" if c == driver else ""
                        console.print(f"  [bold cyan]{idx}[/bold cyan]. [{c.color}]@{c.name}[/{c.color}]{current_mark}")
                    choice = console.input("\n[yellow]Select driver number or name [Enter to cancel]:[/yellow] ").strip()
                    if not choice:
                        continue
                    target = choice

                target_clean = target.lower().lstrip("@")
                new_driver = None
                if target_clean.isdigit():
                    idx = int(target_clean) - 1
                    if 0 <= idx < len(clients):
                        new_driver = clients[idx]
                if not new_driver:
                    for c in clients:
                        if c.name.lower() == target_clean:
                            new_driver = c
                            break
                if not new_driver:
                    for c in clients:
                        if target_clean in c.name.lower():
                            new_driver = c
                            break

                if new_driver:
                    driver = new_driver
                    console.print(f"[bold green]Current Driver changed to [{driver.color}]@{driver.name}[/{driver.color}][/bold green]\n")
                else:
                    valid_names = ", ".join(f"@{c.name}" for c in clients)
                    console.print(f"[red]Unknown model '{target}'. Available: {valid_names}[/red]\n")
                continue

            if user_input.strip().startswith("@"):
                raw = user_input.strip()[1:]
                match = re.match(r'^([^:\s]+(?:\s+[^:\s]+)*?)(?::|\s+|$)(.*)', raw)
                if match:
                    potential_model = match.group(1).strip().lower()
                    rest_prompt = match.group(2).strip()
                    matched_client = None
                    for c in clients:
                        if c.name.lower() == potential_model or potential_model in c.name.lower():
                            matched_client = c
                            break
                    if matched_client:
                        driver = matched_client
                        console.print(f"[bold green]Current Driver switched to [{driver.color}]@{driver.name}[/{driver.color}][/bold green]\n")
                        if not rest_prompt:
                            continue
                        user_input = rest_prompt

            if user_input.strip().lower() in ("/setup", "setup"):
                if run_setup_wizard(console, env_path):
                    load_hawk_env(env_path)
                    new_clients = create_clients()
                    if new_clients:
                        with console.status("[bold cyan]Re-initializing sessions...[/bold cyan]"):
                            close_tasks = [c.close_session() for c in clients]
                            await asyncio.gather(*close_tasks, return_exceptions=True)
                            client_names_list = ", ".join([f"@{c.name}" for c in new_clients])
                            init_tasks = [
                                c.start_session(
                                    build_global_system_prompt(
                                        client_names_list, cwd, c.uses_custom_tools
                                    )
                                )
                                for c in new_clients
                            ]
                            results = await asyncio.gather(*init_tasks, return_exceptions=True)
                            active = [
                                c for c, r in zip(new_clients, results)
                                if not isinstance(r, Exception)
                            ]
                            if active:
                                clients = active
                                driver = choose_driver(clients)
                                client_tags = [
                                    f"[{c.color}]@{c.name}[/{c.color}]" for c in clients
                                ]
                                console.print(
                                    f"\n[bold]Updated panel:[/bold] {', '.join(client_tags)}\n"
                                )
                                console.print(f"[bold]Current Driver:[/bold] [{driver.color}]@{driver.name}[/{driver.color}]\n")
                                print_panel_size_hint(console, len(clients))
                continue

            if user_input.startswith("/hawk"):
                match = re.match(r'/hawk\s+(\d+)\s+(.*)', user_input)
                if match:
                    num_rounds = int(match.group(1))
                    hawk_prompt = match.group(2).strip()
                else:
                    num_rounds = 1
                    hawk_prompt = user_input.replace("/hawk", "").strip()

                if not hawk_prompt:
                    console.print("[red]Please provide a prompt for the panel.[/red]")
                    continue

                # Expand files in the prompt
                expanded_prompt = expand_paths_in_prompt(hawk_prompt)

                synthesis, decision = await run_hawk(
                    expanded_prompt, num_rounds, clients, driver, console
                )

                history.append(Message(role="user", content=f"[HAWK TRIGGERED for {num_rounds} rounds]: {expanded_prompt}"))
                history.append(Message(role="system", content=(
                    f"The Hawk panel voted: {decision.summary()}\n\n"
                    f"Summary written by @{driver.name}, one of the "
                    f"panelists:\n{synthesis}\n\n"
                    "The vote above is the panel's decision; the summary is one member's "
                    "account of it. Use this advice to assist the user."
                )))

            else:
                # Expand files in normal driver chat
                expanded_input = expand_paths_in_prompt(user_input)
                history.append(Message(role="user", content=expanded_input))

                with console.status(f"[bold {driver.color}]@{driver.name} is thinking..."):
                    response = await driver.generate_response(
                        DRIVER_SYSTEM_PROMPT,
                        history
                    )

                history.append(Message(role="assistant", content=response))
                console.print(f"\n[bold {driver.color}]@{driver.name}:[/bold {driver.color}]")
                console.print(Markdown(response))
                console.print("-" * 50)
    finally:
        with console.status("[bold red]Shutting down persistent background sessions...[/bold red]"):
            close_tasks = [c.close_session() for c in clients]
            await asyncio.gather(*close_tasks)
        console.print("[dim]Sessions closed. Goodbye.[/dim]")

def cli_entry() -> None:
    """Synchronous entry point for the global CLI command."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSession terminated by user.")

if __name__ == "__main__":
    cli_entry()
