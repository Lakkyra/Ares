"""Human-In-The-Loop Approval Agent node."""

from typing import Any

from ares.agents.state import AgentState


def approval_node(state: AgentState) -> dict[str, Any]:
    """Inspect approval status and determine final resolution."""
    is_approved = state.get("is_approved", True)

    if is_approved:
        return {"resolution_status": "resolved"}
    return {"resolution_status": "rejected"}
