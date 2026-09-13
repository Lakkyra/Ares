"""Conditional routing edges for the Ares LangGraph workflow."""

from typing import Literal

from ares.agents.state import AgentState


def route_evaluator(state: AgentState) -> Literal["coder", "approval", "failure"]:
    """Determine next graph step based on test evaluation results.

    Rules:
    1. If test passed (exit_code == 0): route to human approval gate.
    2. If failure is environment_error or timeout: abort to failure (FR-4.4).
    3. If iteration_count < max_iterations: retry with Coder (FR-4.2).
    4. If iteration_count >= max_iterations: abort to failure (FR-4.3).
    """
    exit_code = state.get("test_exit_code")
    if exit_code == 0:
        return "approval"

    # Abort on environment / timeout errors
    category = state.get("failure_category")
    if category in ("environment_error", "timeout"):
        return "failure"

    count = state.get("iteration_count", 0)
    max_iters = state.get("max_iterations", 3)

    if count < max_iters:
        return "coder"

    return "failure"
