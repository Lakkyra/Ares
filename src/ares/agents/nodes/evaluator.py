"""Evaluator Agent node implementation."""

import subprocess
from collections.abc import Callable
from typing import Any

from ares.agents.state import AgentState
from ares.sandbox.manager import default_sandbox

TestRunnerFunc = Callable[[str, str], tuple[int, str, str]]


def default_runner(command: str, repo_path: str) -> tuple[int, str, str]:
    """Execute test command using Docker sandbox if available, or local subprocess."""
    if default_sandbox.is_available():
        test_target = command.replace("pytest", "").strip()
        res = default_sandbox.run_pytest(test_target=test_target, repo_path=repo_path)
        return res.exit_code, res.stdout, res.stderr

    # Fallback to local subprocess if Docker daemon is offline
    try:
        proc = subprocess.run(
            command,
            cwd=repo_path,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        return 124, "", f"Execution timed out after 30s: {e}"
    except Exception as e:
        return 1, "", f"Failed to execute command '{command}': {e}"


def evaluator_node(
    state: AgentState,
    test_runner: TestRunnerFunc | None = None,
) -> dict[str, Any]:
    """Execute tests and classify failure characteristics."""
    command = state.get("test_command", "pytest")
    repo_path = state.get("repo_path", ".")
    runner = test_runner or default_runner

    exit_code, stdout, stderr = runner(command, repo_path)

    failure_cat = None
    error_context = None

    if exit_code == 0:
        resolution = "resolved"
    else:
        combined_err = f"{stdout}\n{stderr}".lower()
        if exit_code == 124 or "timed out" in combined_err:
            failure_cat = "timeout"
        elif "modulenotfounderror" in combined_err or "command not found" in combined_err:
            failure_cat = "environment_error"
        elif "flaky" in combined_err:
            failure_cat = "flaky_test"
        else:
            failure_cat = "code_bug"

        error_context = stderr or stdout or "Test failed without explicit output."

        iteration = state.get("iteration_count", 0)
        max_iters = state.get("max_iterations", 3)
        resolution = (
            "failed"
            if iteration >= max_iters or failure_cat in ("environment_error", "timeout")
            else "pending"
        )

    return {
        "test_exit_code": exit_code,
        "test_stdout": stdout,
        "test_stderr": stderr,
        "failure_category": failure_cat,
        "error_context": error_context,
        "resolution_status": resolution,
    }
