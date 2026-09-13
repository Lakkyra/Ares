# Agent Rules — Ares Project

## Project Context
This is **Ares** — an autonomous multi-agent code repair engine using LangGraph, FastMCP, Docker sandboxing, and Langfuse observability. The project is a portfolio piece for AI/ML engineering interviews.

## Key Documents
- `PRD.md` — Product requirements document
- `REQUIREMENTS.md` — Functional/non-functional requirements with IDs
- `PHASES.md` — 8-phase implementation plan with checklists
- `docs/Agentic_ML_Project_Stories.md` — Original project story/dossier (gitignored)
- `docs/Interview_Prep.md` — Interview prep: tech reasoning, tradeoffs, alternatives (gitignored)

## Conventions
- **Language:** Python 3.11+
- **Package Manager:** `uv` (preferred) or `poetry`
- **Linting:** `ruff`
- **Type Checking:** `mypy`
- **Testing:** `pytest` + `pytest-asyncio`
- **Formatting:** `ruff format` (88-char line width)
- **Docstrings:** Google-style
- **Imports:** Absolute imports only (no relative)

## Architecture Rules
- All file I/O and shell execution MUST go through MCP tools — agents never touch the filesystem directly.
- All test execution MUST run inside Docker containers with `--network=none`.
- State is managed via LangGraph's `AgentState` TypedDict — no global mutable state.
- Every LLM call and tool invocation MUST be traced via Langfuse.
- Search-and-replace is the ONLY patching mechanism — no full-file rewrites.

## When Updating Code
- After completing a phase, update `PHASES.md` checkboxes and `docs/Interview_Prep.md` with learnings.
- Keep `REQUIREMENTS.md` in sync if requirements change during implementation.
- Add tests for every new module before marking a phase deliverable as complete.
