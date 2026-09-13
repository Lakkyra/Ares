"""Human Approval Gate for reviewing and editing patches before Git operations."""

import os
import subprocess
import sys
import tempfile

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax

console = Console()


def open_diff_in_editor(diff: str, editor: str | None = None) -> str:
    """Open diff text in the user's preferred editor and return modified text."""
    selected_editor = (
        editor or os.environ.get("EDITOR") or ("notepad.exe" if sys.platform == "win32" else "nano")
    )
    with tempfile.NamedTemporaryFile(
        suffix=".diff", delete=False, mode="w", encoding="utf-8"
    ) as tf:
        tf.write(diff)
        temp_path = tf.name

    try:
        subprocess.run([selected_editor, temp_path], check=True)
        with open(temp_path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        console.print(f"[bold red]Failed to launch editor ({selected_editor}): {e}[/bold red]")
        return diff
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def prompt_human_approval(
    diff: str,
    auto_approve: bool = False,
    editor: str | None = None,
    interactive_prompt: bool = True,
) -> tuple[bool, str]:
    """Render unified diff and prompt developer for approval, rejection, or edit."""
    if not diff.strip():
        console.print("[bold yellow]No code changes detected in proposed patch.[/bold yellow]")
        return False, ""

    if auto_approve or not interactive_prompt:
        console.print(
            "[bold green]Auto-approving proposed patch (--auto-approve enabled).[/bold green]"
        )
        return True, diff

    # Display syntax-highlighted diff
    syntax = Syntax(diff, "diff", theme="monokai", line_numbers=True)
    console.print(
        Panel(
            syntax,
            title="[bold cyan]Proposed Patch (Unified Diff)[/bold cyan]",
            subtitle="[dim]Ares Autonomous Code Repair[/dim]",
            border_style="cyan",
        )
    )

    current_diff = diff
    while True:
        choice = Prompt.ask(
            "\n[bold yellow]Action[/bold yellow] ([bold green]A[/bold green]pprove / [bold red]R[/bold red]eject / [bold cyan]E[/bold cyan]dit)",
            choices=["a", "r", "e", "A", "R", "E"],
            default="a",
        ).lower()

        if choice == "a":
            console.print("[bold green]Patch approved by developer.[/bold green]")
            return True, current_diff
        elif choice == "r":
            console.print("[bold red]Patch rejected by developer. Aborting git commit.[/bold red]")
            return False, current_diff
        elif choice == "e":
            console.print("[cyan]Opening patch in editor...[/cyan]")
            current_diff = open_diff_in_editor(current_diff, editor=editor)
            console.print("[cyan]Updated diff from editor session:[/cyan]")
            new_syntax = Syntax(current_diff, "diff", theme="monokai", line_numbers=True)
            console.print(
                Panel(
                    new_syntax, title="[bold cyan]Updated Patch[/bold cyan]", border_style="yellow"
                )
            )
