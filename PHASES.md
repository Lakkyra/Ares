# Implementation Phases
## Autonomous Multi-Agent Code Repair Engine

> **Version:** 1.0  
> **Last Updated:** 2026-09-13  
> **Total Estimated Duration:** 6–8 weeks (solo developer, part-time)

---

## Phase Overview

```
┌─────────┬─────────────────────────────────────┬──────────┬────────────────────┐
│  Phase  │ Focus Area                          │ Duration │ Key Deliverable    │
├─────────┼─────────────────────────────────────┼──────────┼────────────────────┤
│ Phase 0 │ Project Scaffolding & Environment   │ 2–3 days │ Runnable skeleton  │
│ Phase 1 │ MCP Server & Core Tools             │ 1 week   │ Working tool suite │
│ Phase 2 │ Agent Graph & Orchestration         │ 1.5 weeks│ End-to-end flow    │
│ Phase 3 │ Sandbox, Safety & HITL              │ 1 week   │ Secure execution   │
│ Phase 4 │ Observability & Telemetry           │ 3–4 days │ Full traceability  │
│ Phase 5 │ Git Integration & CLI Polish        │ 3–4 days │ Ship-ready CLI     │
│ Phase 6 │ Benchmarking & Evaluation           │ 1 week   │ Quantified results │
│ Phase 7 │ Documentation & Portfolio Packaging │ 3–4 days │ Resume-ready       │
└─────────┴─────────────────────────────────────┴──────────┴────────────────────┘
```

---

## Phase 0: Project Scaffolding & Environment Setup
**Duration:** 2–3 days  
**Goal:** Establish a clean, reproducible project foundation.

### Deliverables
- [ ] Initialize Python project with `pyproject.toml` (using `uv` or `poetry`)
- [ ] Set up directory structure:
  ```
  src/
  ├── agents/          # LangGraph agent nodes
  ├── mcp_server/      # FastMCP server and tools
  ├── sandbox/         # Docker sandbox manager
  ├── git_ops/         # Git/GitHub integration
  ├── observability/   # Langfuse instrumentation
  ├── config/          # Pydantic settings
  └── cli/             # Typer CLI entrypoint
  tests/
  ├── unit/
  ├── integration/
  └── benchmarks/
  ```
- [ ] Configure development tooling: `ruff` (linting), `mypy` (type checking), `pytest`
- [ ] Create `docker-compose.yml` for local PostgreSQL (LangGraph checkpointer)
- [ ] Create `Dockerfile.sandbox` for test execution container
- [ ] Set up `.env.example` with all required environment variables
- [ ] Write initial `README.md` with setup instructions

### Exit Criteria
✅ `pytest` runs and passes with a single placeholder test  
✅ Docker sandbox container builds successfully  
✅ PostgreSQL container starts via docker-compose  

---

## Phase 1: MCP Server & Core Tools
**Duration:** 1 week  
**Goal:** Build a fully functional FastMCP server with all required code interaction tools.

### Deliverables
- [ ] Implement `FastMCP` server with JSON-RPC 2.0 over stdio transport
- [ ] Implement tool: `read_file_context(file_path, start_line, end_line)`
  - Returns file content with line numbers and metadata
  - Handles file-not-found and permission errors gracefully
- [ ] Implement tool: `apply_search_replace(file_path, search_block, replace_block)`
  - Exact whitespace matching
  - Fails on ambiguous matches (multiple occurrences)
  - Returns applied diff as confirmation
- [ ] Implement tool: `list_directory(path, recursive, max_depth)`
  - Returns structured directory tree
- [ ] Implement tool: `search_codebase(query, file_pattern, max_results)`
  - Uses ripgrep subprocess for fast full-text search
- [ ] Write comprehensive unit tests for each tool (including edge cases)
- [ ] Test MCP server end-to-end with a simple MCP client

### Exit Criteria
✅ All 4 tools pass unit tests with >90% edge case coverage  
✅ MCP server responds correctly to JSON-RPC 2.0 requests  
✅ `apply_search_replace` correctly rejects ambiguous/missing search blocks  

---

## Phase 2: Agent Graph & Multi-Agent Orchestration
**Duration:** 1.5 weeks  
**Goal:** Build the LangGraph state machine with all agent nodes and routing logic.

### Deliverables
- [ ] Define `AgentState` TypedDict/Pydantic model with all required fields
- [ ] Implement **Triage Agent** node:
  - Analyzes issue description
  - Uses `search_codebase` and `list_directory` to identify candidate files
  - Outputs hypotheses and ranked file list
- [ ] Implement **Coder Agent** node:
  - Reads file context via `read_file_context`
  - Generates search-and-replace patch blocks
  - Applies patches via `apply_search_replace`
- [ ] Implement **Evaluator Agent** node:
  - Triggers test execution (placeholder — sandbox in Phase 3)
  - Classifies failures: `code_bug` | `environment_error` | `timeout` | `flaky_test`
  - Constructs error context for retry prompt
- [ ] Implement **conditional routing edges**:
  - `test_exit_code != 0 AND iteration_count < max_iterations` → route to Coder
  - `test_exit_code == 0` → route to Human Approval
  - `iteration_count >= max_iterations` → route to failure terminal
- [ ] Wire up LangGraph `StateGraph` with all nodes and edges
- [ ] Configure PostgreSQL checkpointer for state persistence
- [ ] Write integration test: full graph traversal with mocked LLM responses

### Exit Criteria
✅ Graph executes end-to-end with mocked LLM and tools  
✅ Retry loop correctly fires up to `max_iterations` on test failure  
✅ State persists to PostgreSQL and can be resumed  

---

## Phase 3: Docker Sandbox & Safety Guardrails
**Duration:** 1 week  
**Goal:** Implement secure, isolated test execution and safety boundaries.

### Deliverables
- [ ] Implement `run_sandbox_pytest` MCP tool:
  - Builds/pulls sandbox Docker image
  - Mounts repository as read-only volume
  - Copies patched files into writable overlay
  - Executes test command with `--network=none`
  - Enforces timeout, CPU, and memory limits
  - Captures and returns `{ stdout, stderr, exit_code, duration_ms }`
- [ ] Implement container lifecycle management:
  - Auto-cleanup of exited containers
  - Graceful kill on timeout (SIGTERM → SIGKILL)
- [ ] Add input validation to all MCP tool parameters:
  - Path traversal prevention (no `../` escapes)
  - Maximum file size limits for reads
  - Argument schema validation
- [ ] Integrate sandbox tool into the Evaluator Agent node
- [ ] Write security test suite:
  - Verify no network access from sandbox
  - Verify file system isolation
  - Verify timeout enforcement

### Exit Criteria
✅ Tests execute inside Docker with correct isolation  
✅ Network access blocked (verified by test)  
✅ Timeout enforcement works (runaway test killed correctly)  
✅ Path traversal attacks rejected  

---

## Phase 4: Observability & LLMOps Telemetry
**Duration:** 3–4 days  
**Goal:** Instrument the entire system with production-grade tracing and cost analytics.

### Deliverables
- [ ] Integrate Langfuse Python SDK into the agent runtime
- [ ] Instrument LLM calls:
  - Prompt/completion token counts
  - Model name, temperature, latency
  - Input/output content (with optional redaction)
- [ ] Instrument tool calls:
  - Tool name, arguments, return value summary
  - Execution duration
  - Success/failure status
- [ ] Instrument graph transitions:
  - Node entry/exit timestamps
  - Routing decisions and conditions
- [ ] Add session-level metadata:
  - `session_id`, `repo_name`, `issue_id`, `resolution_status`
- [ ] Implement end-of-session cost summary:
  - Total tokens, estimated cost, total duration, iterations used
- [ ] Verify traces appear correctly in Langfuse dashboard

### Exit Criteria
✅ Full session trace visible in Langfuse with all spans  
✅ Token costs accurately tracked per LLM call  
✅ Tool call latencies and error rates visible  

---

## Phase 5: Git Integration & CLI Polish
**Duration:** 3–4 days  
**Goal:** Complete the git workflow and build a polished developer CLI.

### Deliverables
- [ ] Implement git operations module:
  - Create branch: `fix/<issue-id>-<slug>`
  - Stage changed files
  - Generate descriptive commit message
  - Optional: Push and create GitHub PR via PyGithub
- [ ] Implement **Human Approval Gate**:
  - Display syntax-highlighted diff in terminal (Rich)
  - Interactive prompt: `[A]pprove / [R]eject / [E]dit`
  - On edit: open diff in `$EDITOR`
- [ ] Build Typer CLI with commands:
  - `fix` — Main bug resolution flow
  - `resume` — Resume a paused session
  - `config` — Show/validate configuration
  - `version` — Display version info
- [ ] Add `--auto-approve` flag for CI/non-interactive use
- [ ] Add `--dry-run` flag (run everything except git operations)
- [ ] Write CLI usage documentation and `--help` text

### Exit Criteria
✅ Full end-to-end flow works from CLI input to git branch creation  
✅ Human approval gate pauses correctly and resumes on input  
✅ `--dry-run` mode executes without side effects  

---

## Phase 6: Benchmarking & Evaluation
**Duration:** 1 week  
**Goal:** Quantify system performance with a reproducible benchmark suite.

### Deliverables
- [ ] Create synthetic bug benchmark repository:
  - 25 issues across categories:
    - Logic errors (off-by-one, wrong operator)
    - Exception handling gaps
    - Import/dependency issues
    - Type annotation mismatches
    - Missing edge case handling
  - Each issue includes: description, buggy code, test file, expected fix
- [ ] Build automated benchmark runner:
  - Iterates through all issues
  - Runs the full agent pipeline per issue
  - Records: pass/fail, iterations used, token cost, wall time
- [ ] Compute and report metrics:
  - **Pass@1 resolve rate** (target: ≥ 75%)
  - **Average token cost per resolution**
  - **Average resolution time**
  - **Failure category breakdown**
- [ ] Generate benchmark results report (Markdown + charts)
- [ ] Profile and optimize:
  - Identify highest-cost issues
  - Tune prompts for common failure modes
  - Optimize context window usage

### Exit Criteria
✅ All 25 benchmark issues execute automatically  
✅ Pass@1 ≥ 75% achieved  
✅ Results documented with reproducible methodology  

---

## Phase 7: Documentation & Portfolio Packaging
**Duration:** 3–4 days  
**Goal:** Package the project for resume presentation and technical interviews.

### Deliverables
- [ ] Write comprehensive `README.md`:
  - Project overview and motivation
  - Architecture diagram
  - Quick start guide
  - Configuration reference
  - Benchmark results summary
- [ ] Create `ARCHITECTURE.md` with detailed component documentation
- [ ] Record a 2–3 minute demo video / GIF showing:
  - Issue input → triage → patch → test → approval → commit
- [ ] Add LICENSE file (MIT or Apache 2.0)
- [ ] Clean up code:
  - Remove dead code and TODOs
  - Ensure consistent docstrings
  - Run final linting pass (`ruff`, `mypy`)
- [ ] Prepare resume bullet points and STAR story (from project stories doc)
- [ ] Tag release `v1.0.0`

### Exit Criteria
✅ README provides a clear, professional project overview  
✅ Demo recording shows the full end-to-end flow  
✅ Code passes all linting and type checks  
✅ Repository is portfolio-ready  

---

## Milestone Summary

```
Week 1:   [Phase 0 ████] [Phase 1 ████████████████████]
Week 2:   [Phase 1 ██] [Phase 2 ██████████████████████████████]
Week 3:   [Phase 2 ████████] [Phase 3 ████████████████████████]
Week 4:   [Phase 3 ████] [Phase 4 ██████████████] [Phase 5 ████]
Week 5:   [Phase 5 ██████████████] [Phase 6 ██████████████████]
Week 6:   [Phase 6 ██████████████] [Phase 7 ██████████████████]
```

---

## Risk-Adjusted Schedule Notes

| Risk | Impact | Contingency |
|---|---|---|
| Docker/sandbox edge cases take longer | Phase 3 extends by 2–3 days | Reduce sandbox security tests; use basic isolation first |
| LLM prompt engineering for Triage/Coder needs iteration | Phase 2 extends by 3–4 days | Start with hardcoded file targets; iterate prompts in Phase 6 |
| Langfuse integration issues | Phase 4 extends by 1–2 days | Fall back to file-based logging initially |
| Benchmark Pass@1 below 75% | Phase 6 extends by 3–5 days | Additional prompt tuning, add retry budget, expand error classifier |
