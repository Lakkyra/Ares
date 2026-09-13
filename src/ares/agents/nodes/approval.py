"""Human-In-The-Loop Approval Agent node."""

from typing import Any

from ares.agents.state import AgentState


def approval_node(state: AgentState) -> dict[str, Any]:
    """Inspect patch diff and approval status to finalize repair resolution."""
    is_approved = state.get("is_approved", True)
    diff = state.get("proposed_patch", "")

    # If diff is empty or already approved, finalize resolution
    if is_approved:
        return {
            "resolution_status": "resolved",
            "proposed_patch": diff,
        }

    return {
        "resolution_status": "rejected",
        "proposed_patch": diff,
    }
