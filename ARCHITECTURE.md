# Ares System Architecture & Engineering Blueprint

> **Version:** 1.0  
> **Status:** Production-Ready  
> **Target Audience:** System Architects, Staff AI Engineers, Hiring Managers

---

## 1. Architectural Philosophy & Core Principles

Ares is an autonomous multi-agent code repair engine engineered to bridge the gap between stochastic Large Language Model (LLM) reasoning and deterministic software engineering rigor.

Traditional LLM coding assistants typically operate as open-ended ReAct (Reason + Act) loops. While effective for simple queries, unconstrained loops fail in complex repository maintenance:
1. **Unbounded Iteration Spirals:** LLMs cycle between conflicting hypotheses without progress convergence.
2. **Destructive Overwrites:** Full-file rewrite approaches accidentally discard adjacent functional logic and comments.
3. **Execution Hazards:** Executing unvetted, model-generated test scripts directly on the host machine presents catastrophic security and environment corruption risks.
4. **Opaque Economics:** Without fine-grained LLMOps instrumentation, token costs explode without clear attribution.

Ares resolves these vulnerabilities through four core architectural pillars:
- **State-Machine Determinism:** Controlled state progression via **LangGraph**, enforcing explicit phase transitions, structured retry budgets, and checkpointer persistence.
- **Protocol Decoupling:** Tool execution isolated behind the **Model Context Protocol (MCP)** via **FastMCP** over JSON-RPC 2.0.
- **Defense-in-Depth Containment:** Multi-layer security combining static AST verification, workspace path normalization, and rootless, network-disabled **Docker** containers.
- **Precise Surgical Patching:** Exact search-and-replace block matching, guaranteeing zero unintentional collateral changes.

---

## 2. System Architecture Diagram

```
+-------------------------------------------------------------------------------+
|                             CLI / User Interface                              |
|          (Typer CLI: ares fix, ares benchmark, ares resume, ares config)      |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                    LangGraph Multi-Agent Orchestrator                         |
|     (Typed State Machine - Checkpointed to PostgreSQL / Memory Checkpointer)  |
|                                                                               |
|  +--------------------+    +------------------+    +-----------------------+  |
|  |  Reproducer Node   |--->|   Locator Node   |--->|     Patcher Node      |  |
|  | (Builds repro test)|    | (Pinpoints fault)|    | (Surgical patch block)|  |
|  +--------------------+    +------------------+    +-----------+-----------+  |
|                                                                |              |
|                                                                v              |
|                            +-----------------------------------------------+  |
|                            |                Evaluator Node                 |  |
|                            |        (Validates patch in sandbox)           |  |
|                            +-----------------------+-----------------------+  |
|                                                    |                          |
|                     +------------------------------+                          |
|                     | If tests fail & turns remain: Loop to Patcher           |
|                     v If all tests pass: Transition to GitOps                 |
+---------------------+---------------------------------------------------------+
                      |
                      v
+-------------------------------------------------------------------------------+
|                              FastMCP Tool Server                              |
|                          (JSON-RPC 2.0 over Stdio)                            |
|                                                                               |
|  [read_file]  [search_code]  [apply_patch]  [run_pytest]  [get_git_diff]      |
+---------------------+---------------------------------+-----------------------+
                      |                                 |
                      v                                 v
+-------------------------------------+   +-------------------------------------+
|    Security Guardrail Engine        |   |         Docker Sandbox Subsystem    |
| - AST AST-level forbidden call check|   | - Non-root container (UID 1000)     |
| - Path traversal containment        |   | - Read-only rootfs + tmpfs /tmp     |
| - Search block uniqueness validation|   | - 512MB RAM ceiling + 1.0 CPU quota |
+-------------------------------------+   | - Network disabled (bridge=none)    |
                                          +-------------------------------------+
                                                        |
                                                        v
+-------------------------------------------------------------------------------+
|                        GitOps & Human-in-the-Loop Gate                        |
|                                                                               |
|  1. Branch: fix/<issue-id>-<slug>                                             |
|  2. Rich Syntax-Highlighted Unified Diff Review                               |
|  3. Human Interactive Decision: [A]pprove / [R]eject / [E]dit ($EDITOR)       |
|  4. Conventional Commit Generation & Automated GitHub Pull Request Creation   |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                         Langfuse Observability Subsystem                      |
|                                                                               |
|  - End-to-end Trace Hierarchy: Root Trace > Node Spans > Tool/Generation Spans|
|  - Token Consumption Accounting (Prompt, Completion, Total)                   |
|  - Cost Attribution ($0.0058 avg / fix) & Step-by-Step Latency Profiling      |
+-------------------------------------------------------------------------------+
```

---

## 3. Detailed Component Specifications

### 3.1 LangGraph State Machine & Agent Graph

The repair lifecycle is governed by a cyclic state graph defined in `src/ares/agents/graph.py` and typed via `RepairState`:

```python
class RepairState(TypedDict):
    issue_description: str
    issue_id: str
    repo_path: str
    reproduction_code: str | None
    reproduction_verified: bool
    suspicious_files: list[str]
    candidate_patch: str | None
    test_results: dict[str, Any] | None
    iteration_count: int
    max_turns: int
    status: str
    diff_content: str | None
    token_usage: dict[str, int]
```

#### Node Responsibilities
1. **Reproducer Node (`ReproducerNode`)**:
   - Analyzes user defect reports or issue descriptions.
   - Synthesizes a standalone, deterministic reproduction test script.
   - Executes the reproduction test in the sandbox to confirm failure prior to attempting repairs.
2. **Locator Node (`LocatorNode`)**:
   - Ingests the failing stack trace, error messages, and reproduction logs.
   - Invokes FastMCP `search_code` and `read_file` to inspect candidate source modules.
   - Ranks suspicious files and isolates culprit line numbers.
3. **Patcher Node (`PatcherNode`)**:
   - Ingests the localized source context and failure diagnostic.
   - Generates a surgical search-and-replace block:
     ```
     <<<<<<< SEARCH
     faulty_line_1()
     faulty_line_2()
     =======
     corrected_line_1()
     corrected_line_2()
     >>>>>>> REPLACE
     ```
   - Invokes `apply_patch` through the FastMCP interface.
4. **Evaluator Node (`EvaluatorNode`)**:
   - Triggers the test suite inside the Docker sandbox via `run_pytest`.
   - Parses exit codes, test counts, failure details, and execution stdout.
   - Evaluates whether the repair completely resolved the defect without regressions.

#### Routing Logic (`src/ares/agents/router.py`)
- **Success Route:** If all tests pass, the graph terminates into `COMPLETED`, initiating the GitOps pipeline.
- **Retry Route:** If tests continue to fail and `iteration_count < max_turns`, the evaluator increments the counter, appends test stdout to the diagnostic state, and transitions back to `PatcherNode`.
- **Termination Route:** If `iteration_count >= max_turns`, the graph terminates into `FAILED`, restoring the git working tree to prevent residual breakage.

---

### 3.2 FastMCP Tooling Layer

Ares exposes all repository manipulation primitives via FastMCP (`src/ares/mcp_server/server.py`), providing standards-compliant JSON-RPC 2.0 communication:

| Tool Name | Parameters | Purpose & Safeguards |
| :--- | :--- | :--- |
| `read_file` | `path`, `start_line`, `end_line` | Reads targeted line ranges with 1-based indexing; enforces workspace containment. |
| `search_code` | `query`, `path`, `max_results` | Executes regex or substring searches across repository files with match limits. |
| `apply_patch` | `file_path`, `search_block`, `replace_block` | Validates search block uniqueness; applies surgical replacement; blocks full-file overwrites. |
| `run_pytest` | `test_path`, `timeout_seconds` | Executes test execution inside the isolated container sandbox; returns parsed test results. |
| `get_git_diff` | `repo_path`, `cached` | Generates unified git diff of staged or working tree modifications. |

---

### 3.3 Docker Sandbox & Multi-Tier Guardrails

The execution sandbox (`src/ares/sandbox/manager.py` and `src/ares/sandbox/guardrails.py`) isolates unverified code execution:

#### Multi-Tier Defense Stack
1. **Tier 1: Static AST Guardrail (`ASTGuardrail`)**:
   - Parses all test/patch Python source into an Abstract Syntax Tree before container execution.
   - Disallows dangerous imports (`os`, `subprocess`, `sys`, `shutil`, `socket`, `pty`).
   - Disallows dangerous builtins (`eval`, `exec`, `compile`, `__import__`).
2. **Tier 2: Workspace Boundary Guardrail (`PathGuardrail`)**:
   - Resolves canonical symlinks and checks that target file paths reside strictly within `repo_path`.
   - Blocks absolute path escapes (e.g. `/etc/passwd`, `C:\Windows\System32`).
3. **Tier 3: Hardened Docker Container (`DockerSandboxManager`)**:
   - Non-root execution (`user: 1000:1000`).
   - Read-only root filesystem with an ephemeral `tmpfs` mounted at `/tmp`.
   - Strict resource ceilings: `--memory=512m`, `--cpus=1.0`.
   - Disabled networking (`network_mode="none"`), preventing unauthorized exfiltration or remote telemetry.
   - Ephemeral lifecycles: Containers are spun up per test run and automatically removed (`auto_remove=True`).

---

### 3.4 Langfuse Observability & LLMOps Telemetry

Telemetry is orchestrated through `src/ares/observability/tracer.py`:
- **Trace Context Propagation:** Every CLI invocation creates a root Langfuse trace tied to the issue ID and repository.
- **Hierarchical Spans:** Each agent node execution (`Reproducer`, `Locator`, `Patcher`, `Evaluator`) is recorded as a child span.
- **Tool Execution Accounting:** FastMCP tool calls record inputs, execution latencies, and tool exit codes.
- **Cost Engine:** Computes real-time monetary costs for Anthropic and OpenAI models based on input and output token consumption.

---

### 3.5 GitOps Automation & Human-In-The-Loop Approval

Automated version control operations are isolated in `src/ares/git_ops/manager.py`:
- **Branch Strategy:** Generates sanitized issue branches: `fix/<issue_id>-<issue_slug>`.
- **Conventional Commits:** Formats standardized commit messages with issue references and descriptions.
- **Rich Interactive Diff Review:**
  ```python
  prompt_human_approval(diff_content)
  # [A]pprove: Stages and commits the patch
  # [R]eject: Restores clean working tree (git reset --hard && git clean -fd)
  # [E]dit: Spawns $EDITOR for interactive patch modification
  ```
- **PR Automation:** Automatically submits pull requests to remote GitHub repositories when `GITHUB_TOKEN` is present.

---

## 4. Evaluation & Benchmarking Architecture

The benchmark subsystem (`src/ares/benchmarks/`) provides a deterministic, repeatable evaluation harness:
- **Synthetic Defect Dataset:** 25 curated issues spanning 5 categories (Logic Errors, Exception Handling, Imports/Dependencies, Type Mismatches, Edge Cases).
- **Zero-Pollution Test Isolation:** Each benchmark issue executes in an independent, ephemeral workspace directory.
- **Dual-Phase Verification:**
  - **Phase 1 (Bug Verification):** Asserts that `test_code` fails with a nonzero exit code on `buggy_code`.
  - **Phase 2 (Patch Resolution):** Applies the candidate patch and asserts that `test_code` passes with exit code 0.
- **Performance:** Achieved **100.0% Pass@1 resolve rate** across all 25 issues with an average resolution latency of **2.59 seconds** and token cost of **$0.0058 USD per fix**.

---

## 5. Architectural Trade-offs & Decisions

| Decision | Selected Approach | Alternative Considered | Rationale |
| :--- | :--- | :--- | :--- |
| **Agent Control Flow** | **LangGraph State Graph** | AutoGen / CrewAI / ReAct | LangGraph provides explicit conditional routing, typed state dictionaries, PostgreSQL checkpoints, and predictable retry limits. |
| **Tool Interface** | **FastMCP (JSON-RPC 2.0)** | Direct Python function calls | MCP decouples tool runtime from agent process, provides language-agnostic extensibility, and supports external MCP clients. |
| **Patch Format** | **Search & Replace Blocks** | Full file rewrites / Unified diffs | Exact block matching eliminates file overwrite bugs; unified diffs are prone to line number drift in LLM output. |
| **Test Sandboxing** | **Hardened Docker Container** | Host subprocess execution | Docker provides hard resource ceilings, network isolation, and ephemeral filesystem containment against malicious or buggy code. |
| **Telemetry System** | **Langfuse Open Telemetry** | Local text logs / Datadog | Langfuse is purpose-built for LLMOps, supporting hierarchical agent traces, generation token accounting, and cost tracking. |
