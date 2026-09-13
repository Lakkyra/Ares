"""Ares developer CLI entrypoint."""

import asyncio
import os
import sys
import uuid
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import ares
from ares.agents.graph import run_repair_workflow
from ares.agents.state import create_initial_state
from ares.cli.approval import prompt_human_approval
from ares.config.settings import settings
from ares.git_ops.manager import GitOpsManager
from ares.observability.tracer import default_tracer

app = typer.Typer(
    name="ares",
    help="Autonomous Multi-Agent Code Repair Engine",
    no_args_is_help=True,
)
console = Console()


def mask_secret(value: str | None) -> str:
    """Mask sensitive credentials for terminal output."""
    if not value:
        return "[dim]Not Configured[/dim]"
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


@app.command()
def version() -> None:
    """Show the Ares version, runtime environment, and sandbox details."""
    table = Table(title="Ares System Diagnostics", border_style="cyan")
    table.add_column("Component", style="bold yellow")
    table.add_column("Status / Version", style="green")

    table.add_row("Ares Engine", ares.__version__)
    table.add_row("Python Runtime", sys.version.split()[0])
    table.add_row("Platform", sys.platform)
    table.add_row("Primary Model", settings.primary_model)
    table.add_row("Sandbox Image", settings.sandbox_image)

    # Check Docker responsiveness
    docker_status = "[red]Offline[/red]"
    try:
        import docker

        client = docker.from_env()
        if client.ping():
            docker_status = "[green]Online[/green]"
    except Exception:
        docker_status = "[yellow]Unavailable[/yellow]"
    table.add_row("Docker Daemon", docker_status)

    console.print(table)


@app.command()
def config() -> None:
    """Show sanitized current configuration settings."""
    table = Table(title="Ares Active Configuration", border_style="cyan")
    table.add_column("Setting", style="bold yellow")
    table.add_column("Configured Value", style="green")

    table.add_row("App Name", settings.app_name)
    table.add_row("Primary Model", settings.primary_model)
    table.add_row("Fallback Model", settings.fallback_model)
    table.add_row("Sandbox Timeout", f"{settings.sandbox_timeout_seconds}s")
    table.add_row("Sandbox Memory", settings.sandbox_memory_limit)
    table.add_row("Sandbox Image", settings.sandbox_image)
    table.add_row("Postgres DSN", mask_secret(settings.postgres_dsn))
    table.add_row("Anthropic API Key", mask_secret(settings.anthropic_api_key))
    table.add_row("OpenAI API Key", mask_secret(settings.openai_api_key))
    table.add_row("Langfuse Public Key", mask_secret(settings.langfuse_public_key))
    table.add_row("GitHub Token", mask_secret(os.environ.get("GITHUB_TOKEN")))

    console.print(table)


@app.command()
def fix(
    issue: str = typer.Argument(
        ..., help="Issue description, error trace, or reproduction instructions"
    ),
    repo: Path = typer.Option(
        Path("."), "--repo", "-r", help="Path to local git repository to repair"
    ),
    issue_id: str = typer.Option("1", "--issue-id", "-i", help="Issue ID for fix branch name"),
    auto_approve: bool = typer.Option(
        False, "--auto-approve", "-y", help="Auto-approve patch without prompt"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Run repair without creating git branch or commit"
    ),
    max_turns: int = typer.Option(5, "--max-turns", "-m", help="Maximum fix-test feedback loops"),
    model: str | None = typer.Option(None, "--model", help="Override primary LLM model"),
) -> None:
    """Analyze and repair a bug in a target repository with git workflow."""
    repo_path = repo.resolve()
    console.print("[bold cyan]=== Ares Autonomous Code Repair Engine ===[/bold cyan]")
    console.print(f"Target repository: [yellow]{repo_path}[/yellow]")
    console.print(f"Issue: [italic]{issue}[/italic]")
    console.print(f"Issue ID: [cyan]{issue_id}[/cyan]")
    console.print(f"Max turns: {max_turns}")
    if dry_run:
        console.print(
            "[bold magenta]Mode: DRY-RUN (no git branch/commit will be created)[/bold magenta]"
        )

    # Check Git repository
    git_mgr: GitOpsManager | None = None
    try:
        git_mgr = GitOpsManager(repo_path)
    except ValueError as e:
        console.print(f"[yellow]Warning: {e}[/yellow]")
        if not dry_run:
            console.print("[red]Aborting: Git operations require a valid git repository.[/red]")
            raise typer.Exit(code=1) from e

    session_id = f"ares-{uuid.uuid4().hex[:8]}"
    default_tracer.start_session(
        session_id=session_id,
        repo_name=repo_path.name,
        issue_id=issue_id,
    )

    initial_state = create_initial_state(
        issue_description=issue,
        repo_path=str(repo_path),
        max_iterations=max_turns,
        auto_approve=auto_approve,
    )

    console.print("\n[bold green]Running multi-agent repair workflow...[/bold green]")
    final_state = run_repair_workflow(
        initial_state=initial_state,
        thread_id=session_id,
    )

    resolution = final_state.get("resolution_status", "unresolved")
    console.print(f"Workflow outcome: [bold]{resolution.upper()}[/bold]")

    # Retrieve git diff
    diff = ""
    if git_mgr is not None:
        diff = git_mgr.get_diff(staged=False)

    if not diff.strip() and final_state.get("proposed_patch"):
        patch_val = final_state["proposed_patch"]
        if patch_val:
            diff = patch_val

    if dry_run:
        if diff.strip():
            from rich.syntax import Syntax

            console.print(
                Panel(
                    Syntax(diff, "diff", theme="monokai"), title="[magenta]Dry-Run Diff[/magenta]"
                )
            )
        else:
            console.print("[yellow]No diff generated.[/yellow]")
        console.print(
            "[bold magenta][DRY-RUN] Completed without modifying git repository.[/bold magenta]"
        )
    elif git_mgr is not None:
        if not diff.strip():
            console.print("[yellow]No code modifications produced by repair engine.[/yellow]")
        else:
            approved, _ = prompt_human_approval(diff, auto_approve=auto_approve)
            if approved:
                branch = git_mgr.create_fix_branch(issue_id=issue_id, title=issue[:30])
                git_mgr.stage_files()
                sha = git_mgr.commit_changes(issue_id=issue_id, summary=issue[:50])
                console.print(
                    f"[bold green]Created branch [cyan]{branch}[/cyan] and committed [yellow]{sha[:8]}[/yellow].[/bold green]"
                )

                # Attempt PR creation if token is present
                pr_url = git_mgr.create_pull_request(
                    title=f"fix({issue_id}): {issue[:50]}",
                    body=f"Automated repair by Ares\n\nIssue: {issue}\nCommit: {sha}",
                )
                if pr_url:
                    console.print(
                        f"[bold green]Pull request opened: [link={pr_url}]{pr_url}[/link][/bold green]"
                    )
            else:
                console.print("[yellow]Rolling back changes in working tree...[/yellow]")
                git_mgr.rollback()

    # Finalize and print telemetry summary
    metrics = default_tracer.end_session(
        resolution_status=resolution,
        iteration_count=final_state.get("iteration_count", 1),
    )
    summary_table = default_tracer.format_summary_table(metrics)
    console.print(summary_table)


@app.command()
def resume(
    thread_id: str = typer.Argument(..., help="Session or thread ID to resume"),
    repo: Path = typer.Option(Path("."), "--repo", "-r", help="Path to local git repository"),
    auto_approve: bool = typer.Option(
        False, "--auto-approve", "-y", help="Auto-approve patch without prompt"
    ),
) -> None:
    """Resume a paused or interrupted repair session by thread ID."""
    repo_path = repo.resolve()
    console.print(f"[bold cyan]Resuming session [yellow]{thread_id}[/yellow]...[/bold cyan]")
    try:
        git_mgr = GitOpsManager(repo_path)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from e

    initial_state = create_initial_state(
        issue_description="Resumed repair session",
        repo_path=str(repo_path),
        auto_approve=auto_approve,
    )
    final_state = run_repair_workflow(initial_state=initial_state, thread_id=thread_id)
    resolution = final_state.get("resolution_status", "unresolved")
    console.print(f"Resumed workflow outcome: [bold]{resolution.upper()}[/bold]")

    diff = git_mgr.get_diff(staged=False)
    if diff.strip():
        approved, _ = prompt_human_approval(diff, auto_approve=auto_approve)
        if approved:
            branch = git_mgr.create_fix_branch(issue_id="resume", title="resumed-patch")
            git_mgr.stage_files()
            sha = git_mgr.commit_changes(issue_id="resume", summary="Resumed repair patch")
            console.print(
                f"[bold green]Committed [yellow]{sha[:8]}[/yellow] on branch [cyan]{branch}[/cyan][/bold green]"
            )
        else:
            git_mgr.rollback()


@app.command()
def benchmark(
    category: str | None = typer.Option(
        None, "--category", "-c", help="Filter by category (e.g. logic_error)"
    ),
    limit: int | None = typer.Option(
        None, "--limit", "-n", help="Limit number of benchmark issues to evaluate"
    ),
    output: Path = typer.Option(
        Path("BENCHMARK_REPORT.md"), "--output", "-o", help="Path to save Markdown report"
    ),
    canonical: bool = typer.Option(
        True, "--canonical/--agent", help="Use canonical patch baseline"
    ),
) -> None:
    """Run synthetic bug benchmarks and generate evaluation reports."""
    from ares.benchmarks.dataset import get_all_issues, get_issues_by_category
    from ares.benchmarks.runner import BenchmarkRunner

    issues = get_issues_by_category(category) if category else get_all_issues()
    if limit:
        issues = issues[:limit]

    runner = BenchmarkRunner()
    summary, results = runner.run_suite(issues=issues, use_canonical_patch=canonical)

    table = runner.format_terminal_summary(summary, results)
    console.print(table)

    output_path = output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_md = runner.generate_markdown_report(summary, results)
    output_path.write_text(report_md, encoding="utf-8")
    console.print(
        f"[bold green]Saved benchmark evaluation report to [cyan]{output_path}[/cyan][/bold green]"
    )


@app.command(name="mcp-serve")
def mcp_serve() -> None:
    """Run the MCP server over stdio for external MCP clients."""
    from ares.mcp_server.server import run_server_stdio

    console.print("[bold cyan]Starting Ares MCP server over stdio...[/bold cyan]")
    asyncio.run(run_server_stdio())


if __name__ == "__main__":
    app()
