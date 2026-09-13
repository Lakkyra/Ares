"""Integration tests for end-to-end LangGraph multi-agent repair workflow."""

from pathlib import Path

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from ares.agents.graph import build_repair_graph, run_repair_workflow
from ares.agents.state import create_initial_state


@pytest.fixture
def dummy_bug_repo(tmp_path: Path) -> Path:
    """Create a mock repository with a failing test."""
    repo = tmp_path / "repo"
    repo.mkdir()

    calc_file = repo / "calc.py"
    calc_file.write_text(
        "def compute(x: int) -> int:\n    return x - 1\n",  # Bug: should be x + 1
        encoding="utf-8",
    )
    return repo


def test_graph_end_to_end_single_turn_success(dummy_bug_repo: Path) -> None:
    """Verify graph resolves a bug on turn 1 when patch passes test."""

    # Test runner that passes if calc.py has x + 1
    def mock_test_runner(command: str, repo_path: str) -> tuple[int, str, str]:
        content = (Path(repo_path) / "calc.py").read_text(encoding="utf-8")
        if "return x + 1" in content:
            return 0, "1 passed in 0.01s", ""
        return 1, "", "AssertionError: expected 2, got 0"

    initial_state = create_initial_state(
        issue_description="calc.py returns incorrect computation",
        repo_path=str(dummy_bug_repo),
        target_files=["calc.py"],
        max_iterations=3,
        auto_approve=True,
    )
    # Inject patch hunk into initial state
    initial_state["patch_hunks"] = [
        {
            "file_path": "calc.py",
            "search_block": "return x - 1",
            "replace_block": "return x + 1",
        }
    ]

    final_state = run_repair_workflow(
        initial_state=initial_state,
        thread_id="test-session-1",
        test_runner=mock_test_runner,
    )

    assert final_state["resolution_status"] == "resolved"
    assert final_state["test_exit_code"] == 0
    assert final_state["iteration_count"] == 1
    assert "return x + 1" in (dummy_bug_repo / "calc.py").read_text(encoding="utf-8")


def test_graph_retry_loop_until_max_iterations(dummy_bug_repo: Path) -> None:
    """Verify graph loops Coder -> Evaluator up to max_iterations on failure."""

    # Test runner that always fails
    def mock_failing_runner(command: str, repo_path: str) -> tuple[int, str, str]:
        return 1, "", "AssertionError: always failing test"

    initial_state = create_initial_state(
        issue_description="Unfixable bug",
        repo_path=str(dummy_bug_repo),
        target_files=["calc.py"],
        max_iterations=3,
    )

    final_state = run_repair_workflow(
        initial_state=initial_state,
        thread_id="test-session-retry",
        test_runner=mock_failing_runner,
    )

    assert final_state["resolution_status"] == "failed"
    assert final_state["iteration_count"] == 3
    assert final_state["failure_category"] == "code_bug"


def test_graph_checkpoint_persistence(dummy_bug_repo: Path) -> None:
    """Verify state is saved to checkpointer and can be inspected by thread_id."""
    saver = MemorySaver()
    graph = build_repair_graph(checkpointer=saver)

    initial_state = create_initial_state(
        issue_description="State persistence test",
        repo_path=str(dummy_bug_repo),
        target_files=["calc.py"],
        max_iterations=2,
    )

    config: RunnableConfig = {"configurable": {"thread_id": "persisted-thread-42"}}
    final_state = graph.invoke(initial_state, config=config)

    # Retrieve checkpoint directly from graph
    checkpoint_state = graph.get_state(config)
    assert checkpoint_state.values["iteration_count"] == final_state["iteration_count"]
    assert checkpoint_state.values["issue_description"] == "State persistence test"
