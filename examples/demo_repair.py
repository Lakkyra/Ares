"""Interactive terminal demonstration of Ares Autonomous Code Repair Engine.

Run this script to observe the end-to-end code repair flow:
Issue Input -> Reproduction -> Localization -> Patching -> Sandbox Test -> Rich Diff -> Approval -> Commit.
"""

import time

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

console = Console()


def run_demo() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]Ares Autonomous Code Repair Engine[/bold cyan]\n"
            "[dim]Live Terminal Execution Demonstration[/dim]",
            border_style="cyan",
        )
    )
    time.sleep(0.5)

    # Step 1: Issue Ingestion
    console.print("[bold yellow]Step 1: Ingesting Defect Report[/bold yellow]")
    issue_table = Table(show_header=False, border_style="dim")
    issue_table.add_column("Key", style="bold green")
    issue_table.add_column("Value")
    issue_table.add_row("Issue ID", "ISSUE-104")
    issue_table.add_row("Repository", "local://calculator-service")
    issue_table.add_row(
        "Description",
        "ZeroDivisionError in calculate_average() when input array is empty",
    )
    issue_table.add_row("Target File", "src/calc/stats.py")
    console.print(issue_table)
    time.sleep(0.6)

    # Step 2: Reproducer Agent Node
    console.print("\n[bold yellow]Step 2: Reproducer Agent Node[/bold yellow]")
    console.print("  [cyan]?[/cyan] Synthesizing standalone reproduction test case...")
    time.sleep(0.5)
    console.print("  [red]?[/red] Executed repro test: [bold red]FAILED (ZeroDivisionError: division by zero)[/bold red]")
    time.sleep(0.5)

    # Step 3: Locator Agent Node
    console.print("\n[bold yellow]Step 3: Locator Agent Node[/bold yellow]")
    console.print("  [cyan]?[/cyan] Invoking FastMCP tool: [bold]search_code[/bold](query='def calculate_average')")
    time.sleep(0.4)
    console.print("  [green]?[/green] Culprit localized: [bold]src/calc/stats.py:L14-L18[/bold] (confidence: 0.98)")
    time.sleep(0.5)

    # Step 4: Patcher Agent Node
    console.print("\n[bold yellow]Step 4: Patcher Agent Node[/bold yellow]")
    console.print("  [cyan]?[/cyan] Generating surgical search-and-replace patch block...")
    time.sleep(0.5)
    console.print("  [green]?[/green] Validated search block uniqueness in [bold]src/calc/stats.py[/bold]")
    console.print("  [green]?[/green] Applied surgical patch block.")
    time.sleep(0.4)

    # Step 5: Evaluator Agent Node (Docker Sandbox)
    console.print("\n[bold yellow]Step 5: Evaluator Agent Node (Docker Sandbox)[/bold yellow]")
    console.print("  [dim]Container configuration: rootless, read-only rootfs, 512MB RAM, no-network[/dim]")
    console.print("  [cyan]?[/cyan] Running AST security verification... [bold green]PASSED[/bold green]")
    console.print("  [cyan]?[/cyan] Running pytest in container sandbox...")
    time.sleep(0.7)
    console.print("  [bold green]? All 6 unit tests PASSED (0 regressions, 0.04s execution)[/bold green]")
    time.sleep(0.5)

    # Step 6: GitOps & Human Approval Gate
    console.print("\n[bold yellow]Step 6: GitOps & Human Approval Gate[/bold yellow]")
    diff_sample = """--- a/src/calc/stats.py
+++ b/src/calc/stats.py
@@ -14,5 +14,7 @@
 def calculate_average(numbers: list[float]) -> float:
+    if not numbers:
+        return 0.0
     return sum(numbers) / len(numbers)
"""
    syntax = Syntax(diff_sample, "diff", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title="Proposed Patch Diff (src/calc/stats.py)", border_style="green"))
    time.sleep(0.5)

    console.print("Human Approval Gate: [bold green][A]pprove[/bold green] / [bold red][R]eject[/bold red] / [bold yellow][E]dit[/bold yellow]")
    console.print("User selection: [bold green]A (Approve)[/bold green]")
    time.sleep(0.4)

    # Step 7: Commit and PR
    console.print("\n[bold yellow]Step 7: Automated GitOps Lifecycle[/bold yellow]")
    console.print("  [green]?[/green] Created branch: [bold]fix/104-zerodivisionerror-in-calculate-average[/bold]")
    console.print("  [green]?[/green] Created conventional commit: [bold]fix(104): handle empty array in calculate_average[/bold]")
    console.print("  [green]?[/green] Telemetry flushed to Langfuse (Trace ID: [dim]tr-4f901c2[/dim], Cost: [bold green]$0.0054 USD[/bold green])")
    console.print("\n[bold green]? Defect repair lifecycle completed successfully![/bold green]")


if __name__ == "__main__":
    run_demo()
