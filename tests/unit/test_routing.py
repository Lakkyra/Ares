"""Unit tests for Evaluator conditional routing logic."""

from ares.agents.routing import route_evaluator
from ares.agents.state import AgentState


def test_route_evaluator_success() -> None:
    """Passing tests route to approval."""
    state = AgentState(
        test_exit_code=0,
        iteration_count=1,
        max_iterations=3,
        failure_category=None,
    )
    assert route_evaluator(state) == "approval"


def test_route_evaluator_retry_within_budget() -> None:
    """Failing tests with remaining iterations route back to Coder."""
    state = AgentState(
        test_exit_code=1,
        iteration_count=1,
        max_iterations=3,
        failure_category="code_bug",
    )
    assert route_evaluator(state) == "coder"


def test_route_evaluator_exceed_max_iterations() -> None:
    """Failing tests at max iterations route to failure terminal."""
    state = AgentState(
        test_exit_code=1,
        iteration_count=3,
        max_iterations=3,
        failure_category="code_bug",
    )
    assert route_evaluator(state) == "failure"


def test_route_evaluator_environment_error_aborts() -> None:
    """Environment errors abort immediately regardless of iteration count."""
    state = AgentState(
        test_exit_code=127,
        iteration_count=1,
        max_iterations=5,
        failure_category="environment_error",
    )
    assert route_evaluator(state) == "failure"


def test_route_evaluator_timeout_aborts() -> None:
    """Timeouts abort immediately without wasting retries."""
    state = AgentState(
        test_exit_code=124,
        iteration_count=1,
        max_iterations=5,
        failure_category="timeout",
    )
    assert route_evaluator(state) == "failure"
