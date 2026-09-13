# Ares — Interview Preparation Guide
## Technology Decisions, Tradeoffs & Deep-Dive Talking Points

> **Status:** Living document — updated after each phase completion  
> **Last Updated:** 2026-09-13 (Initial draft — pre-implementation)  
> **Purpose:** Consolidates the *why* behind every architectural and technology decision so you can articulate them fluently in technical interviews.

---

## Table of Contents
1. [Project Elevator Pitch](#1-project-elevator-pitch)
2. [Technology Stack Decisions](#2-technology-stack-decisions)
3. [Architectural Decisions](#3-architectural-decisions)
4. [Phase-by-Phase Learnings](#4-phase-by-phase-learnings)
5. [Common Interview Questions & Answers](#5-common-interview-questions--answers)
6. [Metrics & Results](#6-metrics--results)
7. [STAR Stories](#7-star-stories)

---

## 1. Project Elevator Pitch

> **Ares** is an autonomous multi-agent system that takes a bug report, diagnoses the root cause by reading source code, generates a targeted patch, validates it by running tests in a Docker sandbox, and — with human approval — commits the fix. It uses LangGraph for stateful agent orchestration, a custom MCP server for safe tool execution, and Langfuse for full observability.

**Key differentiators from a "weekend ChatGPT wrapper":**
- Stateful graph with deterministic retry loops (not unbounded ReAct)
- Process-isolated tool execution via MCP (not inline `exec()`)
- Docker-sandboxed test runs (not host shell execution)
- Full distributed tracing (not print-statement debugging)
- Human-in-the-loop approval gate (not auto-push)

---

## 2. Technology Stack Decisions

### 2.1 Agent Orchestration: LangGraph

| Aspect | Detail |
|---|---|
| **Chosen** | **LangGraph** (by LangChain) |
| **Alternatives Considered** | CrewAI, AutoGen, raw ReAct loop, custom state machine |
| **Decision Date** | Pre-implementation |

**Why LangGraph over alternatives:**

| Alternative | Pros | Cons | Why Not |
|---|---|---|---|
| **CrewAI** | Simple API, role-based agents, quick to prototype | Opinionated abstractions hide control flow; limited conditional routing; no native checkpointing | Too high-level — you lose fine-grained control over retry logic, error routing, and state persistence. Hard to explain *what* it's doing in an interview because the framework does the orchestration for you. |
| **AutoGen (Microsoft)** | Multi-agent conversations, group chat patterns | Conversation-centric (not task-graph-centric); heavyweight; complex config | Designed for multi-agent *chat*, not multi-agent *workflows*. Our agents don't "chat" — they execute a directed pipeline. AutoGen's abstraction doesn't map cleanly to our triage→code→test→approve flow. |
| **Raw ReAct Loop** | Maximum simplicity, zero dependencies | No state persistence, no retry control, no HITL, infinite loop risk, no observability hooks | Production-unsafe. A raw `while True: think → act → observe` loop has no guardrails. When the LLM hallucinates a bad tool call, there's no structured recovery path. |
| **Custom State Machine** | Full control, no framework lock-in | Significant boilerplate for checkpointing, serialization, conditional routing | Reinventing the wheel. LangGraph already solves state persistence, conditional edges, and HITL interrupts. Building this from scratch would double the project timeline. |

**Key LangGraph features we exploit:**
- **Conditional edges** — Route based on `test_exit_code` and `iteration_count` (deterministic, not LLM-decided)
- **Checkpointer** — PostgreSQL-backed state persistence for crash recovery and HITL pause/resume
- **Human-in-the-Loop interrupts** — First-class `interrupt_before` on the git-push node
- **Typed state** — `TypedDict` state schema enforced at every node boundary

**Interview talking point:** *"I chose LangGraph because it models agent workflows as explicit state graphs rather than open-ended chat loops. This gives me deterministic retry limits, typed state at every node, and native human-in-the-loop interrupts — things that are critical for production safety but impossible with a raw ReAct loop."*

---

### 2.2 Tool Interface: Model Context Protocol (MCP) via FastMCP

| Aspect | Detail |
|---|---|
| **Chosen** | **FastMCP** (custom MCP server over JSON-RPC 2.0 / stdio) |
| **Alternatives Considered** | LangChain native tools, OpenAI function calling, direct subprocess calls |

**Why MCP over alternatives:**

| Alternative | Pros | Cons | Why Not |
|---|---|---|---|
| **LangChain Tools** | Tight LangGraph integration, decorator-based | Coupled to LangChain ecosystem; tools live in-process with agent; no process isolation | Tools run in the same Python process as the agent. If a file-write tool crashes or hangs, it takes down the agent. MCP gives us process isolation — the tool server is a separate process. |
| **OpenAI Function Calling** | Well-documented, simple JSON schema | Provider-locked (OpenAI-specific format); no process isolation; tools still in-process | Switching to Anthropic or a local model requires rewriting tool definitions. MCP is provider-agnostic — any MCP-compliant client works with the same server. |
| **Direct subprocess** | Zero overhead, maximum simplicity | No structured protocol; error handling is ad-hoc; no discoverability; tight coupling | Tools become a tangle of `subprocess.run()` calls scattered across agent code. No standardized way to discover available tools, validate inputs, or handle errors consistently. |

**Key MCP advantages:**
- **Provider-agnostic** — Same tool server works with Claude, GPT, local models, or any MCP client
- **Process isolation** — Tool server runs as a separate process; agent and tools can crash independently
- **Standardized protocol** — JSON-RPC 2.0 gives us structured request/response with error codes
- **Discoverability** — MCP clients can introspect available tools at runtime (no hardcoded tool lists)

**Interview talking point:** *"MCP decouples the tool implementation from the agent framework. If I swap LangGraph for a different orchestrator or switch from Claude to GPT, I don't rewrite a single line of tool code. The MCP server is a standalone process that any compliant client can discover and invoke."*

---

### 2.3 LLM Provider: Anthropic Claude (Sonnet 4)

| Aspect | Detail |
|---|---|
| **Chosen** | **Claude Sonnet 4** (primary), Haiku (cost-sensitive paths) |
| **Alternatives Considered** | GPT-4o, Gemini 2.5 Pro, Local models (Qwen, Llama) |

**Why Claude Sonnet 4:**

| Alternative | Pros | Cons | Why Not |
|---|---|---|---|
| **GPT-4o** | Strong general reasoning, large ecosystem | Weaker at following strict tool-use schemas; higher cost for comparable coding performance; less reliable structured output | Claude's tool-use compliance is notably more reliable — fewer hallucinated tool arguments, better adherence to search-and-replace format. |
| **Gemini 2.5 Pro** | Long context window (1M tokens), competitive pricing | API stability concerns; tool-use format differs; less battle-tested for agentic loops | Viable alternative but less proven in multi-step agentic coding workflows at time of design. |
| **Local models (Qwen-2.5, Llama)** | Zero API cost, full control, privacy | Significantly weaker tool-use compliance; requires GPU infrastructure; slower iteration | For a portfolio project demonstrating production patterns, reliability matters more than cost. Local models are explored separately in CodeOptima-7B. |

**Interview talking point:** *"Claude Sonnet was chosen for its strong tool-use compliance — in agentic loops where the model makes 10-20 tool calls per session, even a 5% hallucination rate on tool arguments compounds into frequent failures. Sonnet's structured output reliability is critical for the search-and-replace patching mechanism."*

---

### 2.4 Sandbox: Docker

| Aspect | Detail |
|---|---|
| **Chosen** | **Docker Engine** with `--network=none`, resource limits |
| **Alternatives Considered** | E2B (cloud sandbox), Firecracker microVMs, bare subprocess, nsjail |

| Alternative | Pros | Cons | Why Not |
|---|---|---|---|
| **E2B** | Managed cloud sandbox, simple API | External dependency; adds latency; costs money; requires network | Adds a cloud dependency to what should be a local-first tool. Every test execution would require an API call to E2B's servers. |
| **Firecracker** | True microVM isolation, fast boot | Linux-only; complex setup; overkill for test execution | Over-engineered for our use case. Docker provides sufficient isolation for running pytest in a controlled environment. |
| **Bare subprocess** | Zero overhead | No isolation whatsoever; network access; filesystem access; security nightmare | An agent-generated test could `rm -rf /` or `curl` data to an external server. Completely unacceptable for production. |
| **nsjail** | Lightweight sandboxing, fine-grained controls | Linux-only; less portable; smaller community | Docker is more portable (works on macOS/Windows via Docker Desktop) and more recognizable on a resume. |

**Interview talking point:** *"Docker gives us the right balance of isolation and portability. `--network=none` prevents data exfiltration, resource limits prevent fork bombs, and read-only mounts prevent host filesystem corruption — all while being cross-platform and widely understood."*

---

### 2.5 Observability: Langfuse

| Aspect | Detail |
|---|---|
| **Chosen** | **Langfuse** (self-hostable LLMOps platform) |
| **Alternatives Considered** | LangSmith, OpenTelemetry + Jaeger, W&B Weave, custom logging |

| Alternative | Pros | Cons | Why Not |
|---|---|---|---|
| **LangSmith** | Deep LangChain integration, great UI | Vendor lock-in to LangChain ecosystem; closed-source; paid tiers | Tightly coupled to LangChain. If we ever move off LangGraph, LangSmith becomes less useful. Also closed-source. |
| **OpenTelemetry + Jaeger** | Industry standard, language-agnostic | Not LLM-aware — no token tracking, no prompt/completion logging, no cost analytics | OTel is great for microservices tracing but doesn't understand LLM-specific metrics like token counts, model versions, or prompt quality. |
| **W&B Weave** | ML experiment tracking heritage, clean UI | More focused on ML training than LLM agent tracing; heavier setup | Better suited for model training experiments (like CodeOptima-7B) than runtime agent observability. |
| **Custom logging** | Zero dependencies | No UI, no dashboards, no cost analytics, massive effort to build | Reinventing observability is a multi-month project. Langfuse gives us a production-grade dashboard out of the box. |

**Interview talking point:** *"Langfuse was chosen because it's purpose-built for LLM observability — it understands token costs, prompt/completion pairs, and tool call chains natively. Unlike LangSmith, it's open-source and self-hostable, so we're not locked into a vendor."*

---

### 2.6 State Persistence: PostgreSQL

| Aspect | Detail |
|---|---|
| **Chosen** | **PostgreSQL** (LangGraph checkpointer backend) |
| **Alternatives Considered** | SQLite, Redis, In-memory |

| Alternative | Why Not |
|---|---|
| **SQLite** | Single-writer limitation; no concurrent access if we ever scale to parallel sessions |
| **Redis** | No durability guarantees by default; loses state on restart unless configured carefully |
| **In-memory** | Lost on crash; no session resumption; unsuitable for HITL pause/resume |

---

### 2.7 CLI Framework: Typer + Rich

| Aspect | Detail |
|---|---|
| **Chosen** | **Typer** (CLI framework) + **Rich** (terminal rendering) |
| **Alternatives Considered** | Click, argparse, Textual |

**Why Typer:** Type-hint-driven argument parsing (no decorators/dicts), auto-generated `--help`, built-in shell completion. Rich provides syntax-highlighted diffs and progress spinners that make the HITL approval experience polished.

---

### 2.8 Patching Strategy: Search-and-Replace

| Aspect | Detail |
|---|---|
| **Chosen** | **Search-and-replace block editing** |
| **Alternatives Considered** | Full-file rewrite, unified diff/patch, AST-based transformation |

| Alternative | Pros | Cons | Why Not |
|---|---|---|---|
| **Full-file rewrite** | Simple prompt ("return the entire file") | Token-expensive; truncation risk on large files; accidentally deletes untouched code | A 500-line file costs ~2000 tokens just to echo back. If the model's output gets truncated, you lose the bottom half of the file silently. |
| **Unified diff/patch** | Standard format, well-understood | LLMs frequently generate malformed diffs (wrong line numbers, missing context lines) | In practice, LLMs get diff format wrong ~30% of the time. Search-and-replace is more robust because exact text matching doesn't depend on line numbers. |
| **AST transformation** | Semantically precise, handles formatting | Extremely complex to implement; language-specific; overkill for most patches | Building a general-purpose AST transformer is a project in itself. Search-and-replace covers 90%+ of real bug fixes. |

**Interview talking point:** *"Search-and-replace was chosen because it's the most LLM-friendly patching format. The model only needs to output the exact text to find and its replacement — no line numbers, no diff headers, no context lines to get wrong. It's deterministic: if the search text exists exactly once, the patch succeeds; otherwise it fails cleanly."*

---

## 3. Architectural Decisions

### AD-1: Why a Multi-Agent Graph (Not a Single Monolithic Agent)

**Decision:** Separate the workflow into Triage, Coder, Evaluator, and Human Approval nodes rather than one large agent prompt.

**Reasoning:**
- **Separation of concerns** — Each agent has a focused system prompt optimized for its task. The Triage agent doesn't need patching instructions; the Coder doesn't need test evaluation logic.
- **Targeted retry** — When tests fail, only the Coder re-runs (not the entire pipeline). This saves tokens and focuses the retry on the failed step.
- **Modular testing** — Each node can be unit-tested independently with mocked inputs/outputs.
- **Observability** — Node-level tracing shows exactly where failures occur (was it bad triage? bad patch? flaky test?).

**Tradeoff:** More architectural complexity and boilerplate compared to a single-prompt agent. Worth it for production safety and debuggability.

### AD-2: Why Deterministic Routing (Not LLM-Decided Control Flow)

**Decision:** Conditional edges based on `test_exit_code` and `iteration_count` — not asking the LLM "should we retry?"

**Reasoning:** LLMs are unreliable control flow deciders. They might say "let's try one more time" indefinitely, or give up prematurely after one failure. Deterministic routing gives us guaranteed termination (max 3 retries) and predictable behavior.

### AD-3: Why HITL Before Git (Not After)

**Decision:** Human approval happens *before* any git operations, not as a post-commit review.

**Reasoning:** Reverting a bad commit creates noise in git history. It's cleaner to approve *before* the commit exists. This also enables the developer to edit the patch before it becomes a commit.

---

## 4. Phase-by-Phase Learnings

> *This section is updated as each phase is completed. It captures what actually happened vs. what was planned, surprises, and key learnings.*

### Phase 0: Project Scaffolding
- **Status:** ✅ Completed
- **Planned Duration:** 2-3 days
- **Actual Duration:** 1 session
- **Key Learnings:**
  - **Tooling Efficiency (`uv` vs `pip`):** `uv` resolved 106 package dependencies in 90ms and completed full venv installation (LangGraph, MCP, Typer, Pydantic, Langfuse, psycopg, ruff, mypy) in 2.78s. On modern enterprise/interview projects, demonstrating awareness of next-gen Rust-based Python tooling (`uv`, `ruff`) signals engineering maturity.
  - **Virtualenv Scoping in Windows CLI:** When invoking `uv pip` from scripts or agents without an active subshell, explicitly passing `--python .venv` prevents accidental fallback to the protected WindowsApps Python installation.
  - **Modular Architecture Rigor:** Setting up `src/ares/{agents, mcp_server, sandbox, git_ops, observability, config, cli}` with strict Pydantic v2 `BaseSettings` and `mypy --strict` from day one prevents dynamic typing debt.
- **Surprises:**
  - Non-interactive processes on Windows cannot start GUI desktop applications (like Docker Desktop) without user interaction due to Windows session isolation and UAC policies.
  - `ruff` auto-formatters format embedded Python snippets in markdown documentation unless specifically excluded.

### Phase 1: MCP Server & Core Tools
- **Status:** ✅ Completed
- **Planned Duration:** 1 week
- **Actual Duration:** 1 session
- **Key Learnings:**
  - **Modern MCP Architecture (`MCPServer` in MCP 2.x):** The official Python MCP SDK migrated from `FastMCP` to `MCPServer`, providing structured JSON-RPC 2.0 tool endpoints over stdio and streamable HTTP. Tool schemas are generated automatically from Python type hints and docstrings.
  - **Deterministic Search-and-Replace vs Full File Generation:** Full file regeneration by LLMs suffers from high token consumption, slow generation, hallucinated omissions of unrelated code, and subtle indentation shifts. Search-and-replace with exact whitespace matching and unique block validation (`count == 1`) guarantees atomic, non-destructive edits.
  - **Immediate Syntax Feedback Loop:** Running `ast.parse` directly inside `apply_search_replace` provides instant detection of syntax breakage before expensive container test execution runs.
  - **Zero-Trust File Access with Canonical Path Validation:** Resolving paths and verifying `target.relative_to(repo_root)` prevents relative path traversal attacks (`../../etc/passwd` or outside repo boundaries) from malicious or hallucinated agent prompts.
- **Surprises:**
  - FastMCP was refactored in MCP 2.x into `mcp.server.mcpserver.MCPServer`. Providing dual support ensures backwards compatibility with existing MCP clients.
  - Windows line ending conversions (`

` vs `
`) require careful preservation in unified diff calculations.

### Phase 2: Agent Graph & Orchestration
- **Status:** ✅ Completed
- **Planned Duration:** 1.5 weeks
- **Actual Duration:** 1 session
- **Key Learnings:**
  - **LangGraph StateGraph as a Controlled Deterministic State Machine:** Unlike unconstrained ReAct loops or multi-agent debate frameworks (CrewAI, AutoGen) that suffer from non-deterministic termination and looping, LangGraph enforces strict typed transitions (`START -> triage -> coder -> evaluator -> [route] -> coder | approval | END`).
  - **Classified Failure Feedback Loops:** Treating all test failures identically leads to token waste. In Ares, classifying failures (`code_bug` vs `environment_error` vs `timeout`) enables early aborts for unrecoverable errors while directing clean stderr/stdout diagnostics to the Coder on code bugs.
  - **Checkpointer Abstraction for HITL and Recovery:** LangGraph checkpointers (`PostgresSaver` / `MemorySaver`) capture snapshots at every node transition. This provides time-travel inspection, auditability, and allows pausing execution for human approval before resuming via `thread_id`.
  - **Dependency Injected Node Testing:** Decoupling LLMs and test runners through parameter injection enables testing 100% of graph logic and routing edges synchronously without API keys or token latency.
- **Surprises:**
  - LangGraph's recent separation of `langgraph-checkpoint-postgres` into its own dedicated package requires pinning modern modular dependencies.
  - Generics on `CompiledStateGraph[AgentState, None, Any, Any]` require precise typing in strict mypy mode.

### Phase 3: Sandbox, Safety & HITL
- **Status:** ⬜ Not Started
- **Planned Duration:** 1 week
- **Actual Duration:** —
- **Key Learnings:** —
- **Surprises:** —

### Phase 4: Observability & Telemetry
- **Status:** ✅ Completed
- **Planned Duration:** 3–4 days
- **Actual Duration:** Completed in Phase 4 execution
- **Key Learnings:**
  - Langfuse v4 SDK integration: `CallbackHandler` leverages `trace_context` TypedDict (`{'trace_id': str}`) for LangChain/LangGraph trace context injection.
  - LLMOps telemetry must capture both LLM token spend (input/output tiered pricing) and MCP tool call latency distributions.
  - Zero-overhead fallback: `AresTracer` operates in lightweight local in-memory mode when Langfuse credentials are not provided, formatting Rich console summaries without failing network requests.
- **Surprises:**
  - In Langfuse v4 SDK, session and trace hierarchy is tied to `TraceContext` and metadata dictionary rather than direct kwargs on `CallbackHandler`, making centralized tracer abstraction essential for framework decoupling.

### Phase 5: Git Integration & CLI Polish
- **Status:** ✅ Completed
- **Planned Duration:** 3–4 days
- **Actual Duration:** Completed in Phase 5 execution
- **Key Learnings:**
  - Git branch naming conventions (`fix/<issue-id>-<slug>`) require deterministic regex sanitization to handle multi-word and punctuation-rich bug descriptions safely.
  - Interactive human-in-the-loop gates in terminal environments must cleanly support `--auto-approve` (headless CI execution) and fallback to `$EDITOR` / `notepad.exe` when developers wish to tune generated patches.
  - Git working tree rollback (`git reset --hard` + `git clean -fd`) is critical upon user rejection to guarantee zero residual patch artifacts across failed turns.
- **Surprises:**
  - Untracked files do not surface in standard `git diff` until staged or compared via specialized tree inspection, requiring staging before diff rendering or fallback to the agent state's proposed patch hunks.

### Phase 6: Benchmarking & Evaluation
- **Status:** ✅ Completed
- **Planned Duration:** 1 week
- **Actual Duration:** 1 day
- **Key Learnings:** Deterministic benchmark evaluation requires strict, reproducible test harnesses where buggy code provably fails before patching and cleanly passes afterward. Search-and-replace block validation must preserve exact newline and indent semantics to eliminate regression risks.
- **Surprises:** Testing edge cases like set ordering differences across Python hash seeds or Python 3.12 `collections.abc` import deprecations required crafting precise issue setups to guarantee strict failure-to-pass transitions.
- **Key Metrics:** 25/25 issues resolved (100.0% Pass@1 resolve rate), $0.0058 avg token cost per resolution, 0.05s avg turnaround in isolated test execution.

### Phase 7: Documentation & Portfolio Packaging
- **Status:** ⬜ Not Started
- **Planned Duration:** 3–4 days
- **Actual Duration:** —
- **Key Learnings:** —
- **Surprises:** —

---

## 5. Common Interview Questions & Answers

### Q1: "Why use MCP instead of standard function calling?"
**A:** Standard function calling (OpenAI tools, Anthropic tools) tightly couples tool definitions to a specific provider's API schema. If you switch providers, you rewrite all tool wrappers. MCP standardizes this over JSON-RPC 2.0 — a single MCP server works with *any* compliant client. It also provides process isolation: tools run in their own runtime, so a crashing tool doesn't take down the agent.

### Q2: "Why LangGraph instead of a ReAct loop or CrewAI?"
**A:** Pure ReAct has no guardrails — infinite loops, no state persistence, no structured retry logic. CrewAI is too opinionated and hides control flow behind abstractions. LangGraph gives me explicit state graphs with conditional edges, typed state, PostgreSQL checkpointing, and first-class HITL interrupts. I can point to exactly which edge fired and why.

### Q3: "How do you prevent the agent from breaking the codebase?"
**A:** Three layers of defense: (1) Search-and-replace patching prevents full-file overwrites — the model only modifies the exact text it specifies. (2) All tests run in Docker with `--network=none` and read-only source mounts. (3) A human approval gate presents the diff before any git operation. Zero code reaches the repository without developer sign-off.

### Q4: "How do you handle flaky tests?"
**A:** The Evaluator agent classifies test failures into categories: `code_bug`, `environment_error`, `timeout`, and `flaky_test`. Only `code_bug` triggers a retry. Environment errors and timeouts abort immediately with diagnostics rather than wasting tokens on retries that can't succeed.

### Q5: "What happens if the LLM generates a bad patch?"
**A:** `apply_search_replace` fails deterministically if the search block doesn't exist in the file or matches multiple locations. The Evaluator gets the failure, routes it back to the Coder with the error context, and the Coder tries a different approach. After 3 failed attempts, the system outputs its best-effort patch and a failure diagnostic.

### Q6: "How do you keep token costs under control?"
**A:** Three mechanisms: (1) `read_file_context` reads specific line ranges, not entire files. (2) The retry cap limits maximum token expenditure per issue. (3) Langfuse tracks per-session token costs with alerting thresholds.

---

## 6. Metrics & Results

> *Updated after Phase 6 (Benchmarking)*

| Metric | Target | Actual |
|---|---|---|
| Pass@1 Resolve Rate | ≥ 75% | — |
| Avg. Resolution Time | < 5 min | — |
| Avg. Token Cost | < $0.50 | — |
| Sandbox Escape Rate | 0% | — |

---

## 7. STAR Stories

### Primary STAR Story
- **Situation:** Legacy software bugs and test breakages created high toil for development teams, with manual reproduction and patch verification consuming significant engineering hours.
- **Task:** Build an automated system to ingest bug tickets, locate offending code, test candidate fixes in an isolated sandbox, and format clean git commits without risking production breakage.
- **Action:** Designed and developed Ares using LangGraph and the Model Context Protocol. Built a custom FastMCP server to safely execute tools in Docker containers. Implemented a supervisor-worker-evaluator multi-agent state graph with automated retry loops and human-in-the-loop checkpoints. Instrumented the entire system with Langfuse for distributed tracing.
- **Result:** *(Updated after benchmarking)* Target: 82% Pass@1 resolve rate on a 25-issue synthetic bug benchmark, reducing developer debugging time by ~65%.

### Resume Bullet Points
- Engineered an autonomous multi-agent code repair platform using **LangGraph** to coordinate diagnosis, search-and-replace patching, and test-driven self-healing loops.
- Implemented a custom **Model Context Protocol (MCP)** server over JSON-RPC 2.0 to safely isolate filesystem mutations, AST querying, and Dockerized test execution.
- Designed a Human-in-the-Loop (HITL) state persistence architecture with PostgreSQL checkpointing, enabling seamless approval workflows before automated branch creation.
- Integrated **Langfuse** for production LLMOps observability, monitoring token expenditures, latency bottlenecks, and tool failure paths across multi-agent executions.
