"""Ares CLI entrypoint."""

import typer
from rich.console import Console
from rich.panel import Panel

import ares

app = typer.Typer(
    name="ares",
    help="Autonomous Multi-Agent Code Repair Engine",
    no_args_is_help=True,
)
console = Console()


@app.command()
def version() -> None:
    """Show the Ares version and environment details."""
    text = (
        f"[bold cyan]Ares[/bold cyan] - Autonomous Multi-Agent Code Repair Engine\n"
        f"Version: [green]{ares.__version__}[/green]"
    )
    console.print(
        Panel(
            text,
            title="Ares System Info",
            border_style="cyan",
        )
    )


@app.command()
def fix(
    issue: str = typer.Argument(
        ..., help="Issue description, error trace, or reproduction instructions"
    ),
    repo: str = typer.Option(".", "--repo", "-r", help="Path to local repository to repair"),
    max_turns: int = typer.Option(5, "--max-turns", "-m", help="Maximum fix-test feedback loops"),
) -> None:
    """Analyze and repair a bug in a target repository."""
    console.print("[bold green]Starting repair pipeline...[/bold green]")
    console.print(f"Target repository: [yellow]{repo}[/yellow]")
    console.print(f"Issue: [italic]{issue}[/italic]")
    console.print(f"Max turns: {max_turns}")
    console.print(
        "[yellow]Phase 0 skeleton: Repair agent graph will be connected in Phase 2.[/yellow]"
    )


@app.command()
def config() -> None:
    """Show current configuration settings."""
    from ares.config.settings import settings

    console.print(f"[bold]App Name:[/bold] {settings.app_name}")
    console.print(f"[bold]Primary Model:[/bold] {settings.primary_model}")
    console.print(f"[bold]Fallback Model:[/bold] {settings.fallback_model}")
    console.print(f"[bold]Postgres DSN:[/bold] {settings.postgres_dsn}")
    console.print(f"[bold]Sandbox Image:[/bold] {settings.sandbox_image}")


if __name__ == "__main__":
    app()
