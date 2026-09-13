"""Triage Agent node implementation."""

from typing import Any

from ares.agents.state import AgentState
from ares.mcp_server.tools import list_directory, search_codebase


def triage_node(state: AgentState, llm: Any = None) -> dict[str, Any]:
    """Analyze issue description, explore repository, and identify candidate files."""
    issue = state.get("issue_description", "")
    repo_path = state.get("repo_path", ".")
    explicit_targets = state.get("target_files", [])

    candidates: list[str] = list(explicit_targets)

    # Search for keywords in repo if no explicit target files provided
    if not candidates:
        words = [w for w in issue.replace(":", " ").replace(".", " ").split() if len(w) > 4]
        for word in words[:3]:
            res = search_codebase(word, path=".", max_results=5, repo_root=repo_path)
            for m in res.matches:
                if m.file_path not in candidates:
                    candidates.append(m.file_path)

    # Fallback to listing top-level python files if still empty
    if not candidates:
        dir_res = list_directory(".", recursive=True, max_depth=2, repo_root=repo_path)
        candidates = [e.path for e in dir_res.entries if e.path.endswith(".py")][:3]

    hypothesis = f"Issue '{issue}' is likely localized in {candidates or 'unknown files'}."

    if llm is not None and hasattr(llm, "invoke"):
        try:
            prompt = f"Bug: {issue}\nFiles: {candidates}\nFormulate a root cause hypothesis."
            response = llm.invoke(prompt)
            hypothesis = getattr(response, "content", str(response))
        except Exception:
            pass

    return {
        "hypotheses": hypothesis,
        "candidate_files": candidates,
    }
