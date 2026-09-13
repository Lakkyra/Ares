# Technical Requirements
## Autonomous Multi-Agent Code Repair Engine

> **Version:** 1.0  
> **Last Updated:** 2026-09-13

---

## 1. Functional Requirements

### FR-1: Issue Ingestion & Triage
| ID | Requirement | Priority |
|---|---|---|
| FR-1.1 | System SHALL accept bug descriptions as plain-text input via CLI arguments or stdin | P0 |
| FR-1.2 | System SHALL accept structured input (JSON) containing `issue_description`, `target_files` (optional), and `test_command` | P0 |
| FR-1.3 | Triage Agent SHALL analyze the issue description and produce a list of candidate source files and initial hypotheses | P0 |
| FR-1.4 | System SHOULD support GitHub webhook ingestion for automated issue-to-fix pipelines | P1 |
| FR-1.5 | Triage Agent SHALL use codebase search tools (grep/ripgrep) to locate relevant code when target files are not explicitly provided | P0 |

### FR-2: Code Analysis & Patching
| ID | Requirement | Priority |
|---|---|---|
| FR-2.1 | Coder Agent SHALL read source files using the MCP `read_file_context` tool with specific line ranges | P0 |
| FR-2.2 | Coder Agent SHALL generate patches using **search-and-replace** block format only (no full-file rewrites) | P0 |
| FR-2.3 | `apply_search_replace` tool SHALL fail explicitly if the search block is not found or matches multiple locations ambiguously | P0 |
| FR-2.4 | `apply_search_replace` SHALL enforce exact whitespace matching to prevent indentation corruption | P0 |
| FR-2.5 | System SHALL support multi-hunk patches (multiple search-and-replace blocks in a single turn) | P1 |
| FR-2.6 | System SHOULD implement fuzzy line matching as a fallback when exact search fails due to minor formatting differences | P2 |

### FR-3: Sandboxed Test Execution
| ID | Requirement | Priority |
|---|---|---|
| FR-3.1 | `run_sandbox_pytest` SHALL execute tests inside an ephemeral Docker container | P0 |
| FR-3.2 | Docker container SHALL have **no network access** | P0 |
| FR-3.3 | Docker container SHALL enforce a configurable timeout (default: 60 seconds) | P0 |
| FR-3.4 | Docker container SHALL enforce CPU and memory limits | P1 |
| FR-3.5 | Tool SHALL return structured output: `{ stdout, stderr, exit_code, duration_ms }` | P0 |
| FR-3.6 | Source volumes SHALL be mounted as **read-only** with patched files copied into a writable overlay | P0 |

### FR-4: Evaluator & Retry Logic
| ID | Requirement | Priority |
|---|---|---|
| FR-4.1 | Evaluator Agent SHALL classify test failures into categories: `code_bug`, `environment_error`, `timeout`, `flaky_test` | P0 |
| FR-4.2 | On `code_bug` classification, Evaluator SHALL route `test_stderr` back to Coder Agent for retry | P0 |
| FR-4.3 | System SHALL enforce a hard maximum retry count (default: 3, configurable) | P0 |
| FR-4.4 | On `environment_error` or `timeout`, system SHALL abort with a diagnostic message rather than retrying | P0 |
| FR-4.5 | On max retries exceeded, system SHALL output the best-effort patch and failure diagnostics | P1 |

### FR-5: Human-in-the-Loop Approval
| ID | Requirement | Priority |
|---|---|---|
| FR-5.1 | System SHALL pause execution and present the complete diff to the developer before any git operations | P0 |
| FR-5.2 | Developer SHALL be able to **approve**, **reject**, or **edit** the proposed patch | P0 |
| FR-5.3 | Approval interface SHALL support CLI interactive mode (stdin/stdout) | P0 |
| FR-5.4 | Approval state SHALL be persisted via LangGraph checkpointer for resumable sessions | P1 |

### FR-6: Git Operations
| ID | Requirement | Priority |
|---|---|---|
| FR-6.1 | System SHALL create a new branch with naming convention `fix/<issue-id>-<short-description>` | P0 |
| FR-6.2 | System SHALL generate a descriptive commit message referencing the original issue | P0 |
| FR-6.3 | System SHOULD support creating a GitHub Pull Request via API | P1 |
| FR-6.4 | System SHALL NOT force-push or modify existing branches without explicit permission | P0 |

### FR-7: Observability & Telemetry
| ID | Requirement | Priority |
|---|---|---|
| FR-7.1 | Every agent node transition SHALL be traced in Langfuse with timing data | P0 |
| FR-7.2 | Every LLM call SHALL log prompt tokens, completion tokens, model name, and latency | P0 |
| FR-7.3 | Every tool call SHALL log arguments, return values, and execution duration | P0 |
| FR-7.4 | Sessions SHALL be tagged with `repo_name`, `issue_id`, and `resolution_status` | P0 |
| FR-7.5 | System SHOULD expose a cost-per-resolution summary at session end | P1 |

---

## 2. Non-Functional Requirements

### NFR-1: Performance
| ID | Requirement | Target |
|---|---|---|
| NFR-1.1 | End-to-end resolution time for single-file bugs | < 5 minutes |
| NFR-1.2 | MCP tool call latency (excluding test execution) | < 500ms |
| NFR-1.3 | LLM response streaming | First token < 2 seconds |

### NFR-2: Security
| ID | Requirement |
|---|---|
| NFR-2.1 | All file mutations SHALL only occur through allowlisted MCP tools |
| NFR-2.2 | Docker sandbox SHALL run with `--network=none` and `--read-only` root filesystem |
| NFR-2.3 | No arbitrary shell command execution outside of the Docker sandbox |
| NFR-2.4 | MCP server SHALL validate all tool input parameters against strict schemas |
| NFR-2.5 | Secrets (API keys, tokens) SHALL be loaded from environment variables, never hardcoded |

### NFR-3: Reliability
| ID | Requirement |
|---|---|
| NFR-3.1 | System SHALL gracefully handle LLM API timeouts and rate limits with exponential backoff |
| NFR-3.2 | System SHALL gracefully handle Docker daemon unavailability with clear error messages |
| NFR-3.3 | LangGraph state SHALL be persisted to PostgreSQL for crash recovery |
| NFR-3.4 | All tool failures SHALL return structured error objects (not raw exceptions) |

### NFR-4: Extensibility
| ID | Requirement |
|---|---|
| NFR-4.1 | New MCP tools SHALL be addable without modifying the agent graph logic |
| NFR-4.2 | LLM provider SHALL be swappable (Anthropic, OpenAI, local models) via configuration |
| NFR-4.3 | Test runner SHALL be configurable (pytest, unittest, custom commands) |

### NFR-5: Portability
| ID | Requirement |
|---|---|
| NFR-5.1 | System SHALL run on Linux, macOS, and Windows (WSL2) |
| NFR-5.2 | No cloud-specific dependencies for core functionality |
| NFR-5.3 | All dependencies SHALL be installable via `pip` and `docker` |

---

## 3. Technology Stack

| Layer | Technology | Justification |
|---|---|---|
| **Language** | Python 3.11+ | Ecosystem maturity for AI/ML tooling |
| **Agent Framework** | LangGraph ≥ 0.2 | Stateful cyclical graphs with HITL support |
| **MCP Framework** | FastMCP | Rapid MCP server development with JSON-RPC 2.0 |
| **LLM Provider** | Anthropic Claude (Sonnet 4) | Strong coding performance, tool-use support |
| **Sandbox** | Docker Engine ≥ 24 | Process isolation, resource limits |
| **State Persistence** | PostgreSQL ≥ 15 | LangGraph checkpointer backend |
| **Observability** | Langfuse ≥ 2.x | LLMOps tracing and cost analytics |
| **Git Operations** | GitPython + PyGithub | Programmatic git and GitHub API access |
| **CLI Framework** | Typer + Rich | Developer-friendly terminal interface |
| **Testing** | pytest + pytest-asyncio | Unit and integration test framework |
| **Config Management** | Pydantic Settings | Type-safe configuration from env vars |
| **Containerization** | Docker Compose | Local development orchestration |

---

## 4. Data Models

### 4.1 Agent State (LangGraph)
```python
from typing import TypedDict, List, Optional, Literal


class AgentState(TypedDict):
    # Input
    issue_description: str
    target_files: List[str]
    test_command: str

    # Triage output
    hypotheses: str
    candidate_files: List[str]

    # Coder output
    proposed_patch: Optional[str]
    patch_hunks: List[dict]  # [{file, search, replace}]

    # Evaluator output
    test_exit_code: Optional[int]
    test_stdout: Optional[str]
    test_stderr: Optional[str]
    failure_category: Optional[Literal["code_bug", "environment_error", "timeout", "flaky_test"]]

    # Control flow
    iteration_count: int
    max_iterations: int  # default: 3
    is_approved: bool
    resolution_status: Literal["pending", "resolved", "failed", "rejected"]
```

### 4.2 MCP Tool Schemas
```python
# read_file_context
{
    "file_path": str,  # Absolute or repo-relative path
    "start_line": int,  # 1-indexed, inclusive
    "end_line": int,  # 1-indexed, inclusive
}

# apply_search_replace
{
    "file_path": str,
    "search_block": str,  # Exact text to find (whitespace-sensitive)
    "replace_block": str,  # Replacement text
}

# run_sandbox_pytest
{
    "test_target": str,  # e.g., "tests/test_auth.py::test_login"
    "timeout_seconds": int,  # default: 60
}
```

---

## 5. Interface Requirements

### 5.1 CLI Interface
```bash
# Basic usage
ares fix --issue "Login endpoint returns 500 when email contains +" \
          --test "pytest tests/test_auth.py" \
          --repo /path/to/repo

# With explicit target files
ares fix --issue "..." \
          --files src/auth/handler.py src/auth/validators.py \
          --test "pytest tests/test_auth.py"

# Non-interactive mode (auto-approve for CI)
ares fix --issue "..." --test "..." --auto-approve

# Resume a paused session
ares resume --session-id <uuid>
```

### 5.2 Configuration File (`ares.yaml`)
```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-20250514
  max_tokens: 4096
  temperature: 0.0

sandbox:
  docker_image: python:3.11-slim
  timeout_seconds: 60
  memory_limit: 512m
  cpu_limit: 1.0
  network: none

agent:
  max_iterations: 3
  auto_approve: false

observability:
  langfuse_enabled: true
  langfuse_public_key: ${LANGFUSE_PUBLIC_KEY}
  langfuse_secret_key: ${LANGFUSE_SECRET_KEY}

git:
  branch_prefix: fix/
  auto_push: false
```

---

## 6. Testing Requirements

### 6.1 Unit Tests
- All MCP tool functions with mocked filesystem and Docker
- Agent state transitions and conditional routing logic
- Error classification logic in the Evaluator
- Search-and-replace engine edge cases (whitespace, multi-match, not-found)

### 6.2 Integration Tests
- End-to-end flow with a real Docker sandbox and a synthetic bug repository
- LangGraph checkpoint persistence and session resumption
- Langfuse trace verification

### 6.3 Benchmark Suite
- 25-issue synthetic bug benchmark covering:
  - Single-file logic bugs
  - Import/dependency errors
  - Off-by-one errors
  - Exception handling gaps
  - Type annotation mismatches
- Measured by: Pass@1 resolve rate, token cost, resolution time
