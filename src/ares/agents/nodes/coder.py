"""Coder Agent node implementation."""

from typing import Any

from ares.agents.state import AgentState
from ares.mcp_server.tools import apply_search_replace


def coder_node(state: AgentState, llm: Any = None) -> dict[str, Any]:
    """Generate and apply targeted search-and-replace patches."""
    repo_path = state.get("repo_path", ".")
    candidates = state.get("candidate_files", [])
    iteration = state.get("iteration_count", 0) + 1
    hunks = state.get("patch_hunks", [])
    diffs: list[str] = []

    # If LLM is supplied and returns patch hunks
    if llm is not None and hasattr(llm, "invoke"):
        try:
            error_feedback = state.get("error_context", "")
            prompt = (
                f"Issue: {state.get('issue_description')}\n"
                f"Candidates: {candidates}\n"
                f"Previous Error: {error_feedback}\n"
                "Provide search-and-replace patch."
            )
            resp = llm.invoke(prompt)
            raw = getattr(resp, "content", str(resp))
            # If the LLM returned structured hunks or custom payload, handle here
            if isinstance(raw, list):
                hunks = raw
        except Exception:
            pass

    # Apply any pending patch hunks
    for hunk in hunks:
        file_path = hunk.get("file_path", "")
        search_block = hunk.get("search_block", "")
        replace_block = hunk.get("replace_block", "")

        if file_path and search_block:
            res = apply_search_replace(
                file_path=file_path,
                search_block=search_block,
                replace_block=replace_block,
                repo_root=repo_path,
            )
            if res.success and res.diff:
                diffs.append(res.diff)

    combined_diff = "\n".join(diffs) if diffs else state.get("proposed_patch")

    return {
        "iteration_count": iteration,
        "proposed_patch": combined_diff,
        "patch_hunks": hunks,
    }
