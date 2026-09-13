"""Unit tests for individual agent node behaviors and edge cases."""

from pathlib import Path
from unittest.mock import MagicMock

from ares.agents.nodes.approval import approval_node
from ares.agents.nodes.coder import coder_node
from ares.agents.nodes.evaluator import evaluator_node
from ares.agents.nodes.triage import triage_node
from ares.agents.state import AgentState, create_initial_state


def test_approval_node_rejected() -> None:
    """Approval node sets rejected status when is_approved is False."""
    state = AgentState(is_approved=False)
    res = approval_node(state)
    assert res["resolution_status"] == "rejected"


def test_approval_node_approved() -> None:
    """Approval node sets resolved status when is_approved is True."""
    state = AgentState(is_approved=True)
    res = approval_node(state)
    assert res["resolution_status"] == "resolved"


def test_triage_node_auto_discovery(tmp_path: Path) -> None:
    """Triage node searches codebase when no explicit target files provided."""
    repo = tmp_path / "repo"
    repo.mkdir()
    auth_file = repo / "auth_service.py"
    auth_file.write_text("def authenticate_user(): pass\n", encoding="utf-8")

    state = create_initial_state(
        issue_description="authenticate_user fails on invalid credentials",
        repo_path=str(repo),
        target_files=[],
    )

    res = triage_node(state)
    assert "auth_service.py" in res["candidate_files"]
    assert "auth_service.py" in res["hypotheses"]


def test_triage_node_with_mock_llm(tmp_path: Path) -> None:
    """Triage node uses LLM hypothesis when provided."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="Root cause: missing exception handler")

    state = create_initial_state(
        issue_description="division by zero in math module",
        repo_path=str(tmp_path),
        target_files=["math.py"],
    )

    res = triage_node(state, llm=mock_llm)
    assert res["hypotheses"] == "Root cause: missing exception handler"
    mock_llm.invoke.assert_called_once()


def test_coder_node_with_mock_llm(tmp_path: Path) -> None:
    """Coder node invokes LLM when provided."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(
        content=[
            {
                "file_path": "calc.py",
                "search_block": "return 1",
                "replace_block": "return 2",
            }
        ]
    )

    state = create_initial_state(
        issue_description="wrong return value",
        repo_path=str(tmp_path),
        target_files=["calc.py"],
    )
    # create calc.py
    (tmp_path / "calc.py").write_text("def run():\n    return 1\n", encoding="utf-8")

    res = coder_node(state, llm=mock_llm)
    assert res["iteration_count"] == 1
    assert "return 2" in (tmp_path / "calc.py").read_text(encoding="utf-8")


def test_evaluator_node_timeout_classification() -> None:
    """Evaluator classifies timeout exit codes."""

    def timeout_runner(cmd: str, repo: str) -> tuple[int, str, str]:
        return 124, "", "Execution timed out"

    state = create_initial_state(issue_description="slow query")
    res = evaluator_node(state, test_runner=timeout_runner)
    assert res["test_exit_code"] == 124
    assert res["failure_category"] == "timeout"
    assert res["resolution_status"] == "failed"


def test_evaluator_node_environment_error_classification() -> None:
    """Evaluator classifies missing modules as environment errors."""

    def env_err_runner(cmd: str, repo: str) -> tuple[int, str, str]:
        return 1, "", "ModuleNotFoundError: No module named 'foo'"

    state = create_initial_state(issue_description="missing dep")
    res = evaluator_node(state, test_runner=env_err_runner)
    assert res["failure_category"] == "environment_error"
    assert res["resolution_status"] == "failed"


def test_evaluator_node_flaky_classification() -> None:
    """Evaluator classifies flaky test outputs."""

    def flaky_runner(cmd: str, repo: str) -> tuple[int, str, str]:
        return 1, "flaky test detected", ""

    state = create_initial_state(issue_description="flaky run")
    res = evaluator_node(state, test_runner=flaky_runner)
    assert res["failure_category"] == "flaky_test"
    assert res["resolution_status"] == "pending"
