"""Unit tests for the Ares Typer CLI interface and human approval gate."""

from pathlib import Path
from unittest.mock import patch

import git
import pytest
from typer.testing import CliRunner

from ares.cli.approval import prompt_human_approval
from ares.cli.main import app

runner = CliRunner()


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Create a temporary initialized git repository for CLI tests."""
    repo = git.Repo.init(str(tmp_path))
    repo.config_writer().set_value("user", "name", "Ares Test").release()
    repo.config_writer().set_value("user", "email", "ares@test.com").release()

    readme = tmp_path / "README.md"
    readme.write_text("# Test Repo\n", encoding="utf-8")
    repo.index.add(["README.md"])
    repo.index.commit("chore: initial commit")
    return tmp_path


def test_cli_version() -> None:
    """Verify `ares version` displays system diagnostics table."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Ares System Diagnostics" in result.stdout
    assert "Ares Engine" in result.stdout
    assert "Python Runtime" in result.stdout


def test_cli_config() -> None:
    """Verify `ares config` displays active configuration table with masked secrets."""
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "Ares Active Configuration" in result.stdout
    assert "Primary Model" in result.stdout
    assert "Sandbox Timeout" in result.stdout


def test_cli_help() -> None:
    """Verify root help text contains expected CLI commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "fix" in result.stdout
    assert "resume" in result.stdout
    assert "config" in result.stdout
    assert "version" in result.stdout


def test_prompt_approval_empty_diff() -> None:
    """Verify approval gate returns False on empty diff."""
    approved, diff = prompt_human_approval("   ")
    assert approved is False
    assert diff == ""


def test_prompt_approval_auto_approve() -> None:
    """Verify approval gate returns True without prompting when auto_approve=True."""
    sample_diff = "+def foo():\n+    pass\n"
    approved, diff = prompt_human_approval(sample_diff, auto_approve=True)
    assert approved is True
    assert diff == sample_diff


def test_prompt_approval_interactive_approve() -> None:
    """Verify user typing 'a' approves patch."""
    sample_diff = "+new line\n"
    with patch("rich.prompt.Prompt.ask", return_value="a"):
        approved, diff = prompt_human_approval(sample_diff, auto_approve=False)
        assert approved is True
        assert diff == sample_diff


def test_prompt_approval_interactive_reject() -> None:
    """Verify user typing 'r' rejects patch."""
    sample_diff = "+buggy fix\n"
    with patch("rich.prompt.Prompt.ask", return_value="r"):
        approved, diff = prompt_human_approval(sample_diff, auto_approve=False)
        assert approved is False
        assert diff == sample_diff


def test_cli_fix_dry_run(temp_git_repo: Path) -> None:
    """Verify `ares fix --dry-run` runs repair without making git changes."""
    mock_final_state = {
        "resolution_status": "resolved",
        "iteration_count": 1,
        "proposed_patch": "--- a/README.md\n+++ b/README.md\n@@ -1 +1,2 @@\n # Test Repo\n+# Patched",
    }

    with patch("ares.cli.main.run_repair_workflow", return_value=mock_final_state):
        result = runner.invoke(
            app,
            [
                "fix",
                "Fix readme typo",
                "--repo",
                str(temp_git_repo),
                "--issue-id",
                "42",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "DRY-RUN" in result.stdout
        assert "Ares Session Telemetry Summary" in result.stdout

        # Verify no branch or new commit was created in git
        repo = git.Repo(str(temp_git_repo))
        branches = [b.name for b in repo.branches]
        assert "fix/42-fix-readme-typo" not in branches


def test_cli_fix_auto_approve_creates_branch_and_commit(temp_git_repo: Path) -> None:
    """Verify `ares fix --auto-approve` creates git branch and commit on resolution."""
    # Modify a file in the repo
    readme = temp_git_repo / "README.md"
    readme.write_text("# Test Repo\n# Modified by agent\n", encoding="utf-8")

    mock_final_state = {
        "resolution_status": "resolved",
        "iteration_count": 1,
        "proposed_patch": None,
    }

    with patch("ares.cli.main.run_repair_workflow", return_value=mock_final_state):
        result = runner.invoke(
            app,
            [
                "fix",
                "Update documentation header",
                "--repo",
                str(temp_git_repo),
                "--issue-id",
                "88",
                "--auto-approve",
            ],
        )
        assert result.exit_code == 0
        assert "Created branch" in result.stdout
        assert "committed" in result.stdout

        # Verify branch exists
        repo = git.Repo(str(temp_git_repo))
        assert "fix/88-update-documentation-header" in [b.name for b in repo.branches]
        assert repo.active_branch.name == "fix/88-update-documentation-header"


def test_cli_resume_command(temp_git_repo: Path) -> None:
    """Verify `ares resume` calls workflow with existing thread_id."""
    mock_final_state = {
        "resolution_status": "resolved",
        "iteration_count": 2,
    }

    with patch("ares.cli.main.run_repair_workflow", return_value=mock_final_state):
        result = runner.invoke(
            app,
            [
                "resume",
                "ares-session-1234",
                "--repo",
                str(temp_git_repo),
                "--auto-approve",
            ],
        )
        assert result.exit_code == 0
        assert "Resuming session" in result.stdout
        assert "RESOLVED" in result.stdout
