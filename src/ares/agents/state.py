"""AgentState definitions for the LangGraph code repair pipeline."""

from typing import Any, Literal, TypedDict


class PatchHunk(TypedDict):
    """Represents a single search-and-replace modification."""

    file_path: str
    search_block: str
    replace_block: str


class AgentState(TypedDict, total=False):
    """State schema for the multi-agent code repair graph."""

    # Input specifications
    issue_description: str
    target_files: list[str]
    test_command: str
    repo_path: str

    # Triage Agent output
    hypotheses: str
    candidate_files: list[str]

    # Coder Agent output
    proposed_patch: str | None
    patch_hunks: list[dict[str, Any]]

    # Evaluator Agent output
    test_exit_code: int | None
    test_stdout: str | None
    test_stderr: str | None
    failure_category: Literal["code_bug", "environment_error", "timeout", "flaky_test"] | None
    error_context: str | None

    # Control flow
    iteration_count: int
    max_iterations: int
    is_approved: bool
    resolution_status: Literal["pending", "resolved", "failed", "rejected"]


def create_initial_state(
    issue_description: str,
    repo_path: str = ".",
    target_files: list[str] | None = None,
    test_command: str = "pytest",
    max_iterations: int = 3,
    auto_approve: bool = True,
) -> AgentState:
    """Initialize a default clean AgentState."""
    return AgentState(
        issue_description=issue_description,
        target_files=target_files or [],
        test_command=test_command,
        repo_path=repo_path,
        hypotheses="",
        candidate_files=target_files or [],
        proposed_patch=None,
        patch_hunks=[],
        test_exit_code=None,
        test_stdout=None,
        test_stderr=None,
        failure_category=None,
        error_context=None,
        iteration_count=0,
        max_iterations=max_iterations,
        is_approved=auto_approve,
        resolution_status="pending",
    )
