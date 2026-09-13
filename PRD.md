# Product Requirements Document (PRD)
## Autonomous Multi-Agent Code Repair Engine with Model Context Protocol

> **Version:** 1.0  
> **Status:** Draft  
> **Last Updated:** 2026-09-13  
> **Author:** Project Lead

---

## 1. Vision & Problem Statement

### 1.1 Problem
Software engineering teams spend a disproportionate amount of time on **reactive maintenance work** — reproducing bugs, diagnosing root causes, writing patches, running test suites, and shepherding pull requests through review. Studies estimate that developers spend **~35–50% of their time** on debugging and fixing existing code rather than building new features. This creates a massive productivity bottleneck, especially in large-scale codebases with frequent regressions.

### 1.2 Vision
Build an **autonomous multi-agent system** that can ingest a bug report (GitHub issue, webhook, or CLI input), diagnose the root cause by reading relevant source files, generate a targeted code patch using search-and-replace semantics, validate the fix by executing tests in an isolated sandbox, and — upon human approval — create a clean git branch and pull request. The system should operate safely, transparently, and observably.

### 1.3 Target Users
| User Persona | Description |
|---|---|
| **Staff/Senior Engineers** | Teams maintaining large codebases who want to accelerate bug triage and resolution |
| **DevOps / Platform Teams** | Teams seeking automated incident response for test failures in CI pipelines |
| **AI/ML Engineers** | Engineers building or extending agentic coding systems |

---

## 2. Product Goals & Success Metrics

### 2.1 Goals
1. **Autonomous Bug Resolution** — Given a bug description and a codebase, the system should autonomously locate, patch, and validate fixes with minimal human intervention.
2. **Safe Execution** — All code mutations and test executions must occur in isolated sandboxes. No uncontrolled writes to the host filesystem or network.
3. **Human-in-the-Loop Guardrails** — No code is committed or pushed without explicit developer approval.
4. **Full Observability** — Every agent decision, tool call, token expenditure, and failure path must be traceable through an LLMOps dashboard.

### 2.2 Success Metrics (KPIs)
| Metric | Target | Measurement Method |
|---|---|---|
| **Pass@1 Resolve Rate** | ≥ 75% on synthetic bug benchmark | Automated eval harness |
| **Avg. Resolution Time** | < 5 minutes per issue (end-to-end) | Langfuse session duration |
| **Sandbox Escape Rate** | 0% | Docker isolation audit |
| **False Positive Patch Rate** | < 10% (patches that pass tests but don't fix the root cause) | Manual code review sampling |
| **Token Cost per Resolution** | < $0.50 average (using Claude Sonnet-class models) | Langfuse token tracking |

---

## 3. Core Capabilities

### 3.1 Multi-Agent Orchestration (LangGraph)
- **Triage Agent** — Analyzes the issue description, identifies candidate files, and forms initial hypotheses about the bug location and nature.
- **Coder Agent** — Reads relevant code context via MCP tools, generates a targeted search-and-replace patch.
- **Evaluator / QA Agent** — Executes the patched code against the test suite in a Docker sandbox. Classifies test failures as code bugs vs. environment issues. Routes failures back to the Coder Agent (up to 3 retries).
- **Human Approval Gate** — Presents the final diff to a human developer for approval before any git operations.

### 3.2 Model Context Protocol (MCP) Server
A custom **FastMCP** server exposing tools over JSON-RPC 2.0 (stdio transport):
- `read_file_context` — Read specific line ranges from source files with line-number metadata.
- `apply_search_replace` — Apply deterministic, whitespace-exact string replacements to files.
- `run_sandbox_pytest` — Execute test commands inside isolated Docker containers with timeout enforcement.
- `list_directory` — Enumerate directory structure for codebase navigation.
- `search_codebase` — Grep/ripgrep search across the repository.

### 3.3 Sandboxed Test Execution
- All test runs execute inside **ephemeral Docker containers** with:
  - Mounted read-only source volumes (patched files copied in)
  - No network access
  - CPU/memory limits
  - Hard timeout enforcement (default: 60 seconds)
- Captures `stdout`, `stderr`, and `exit_code` for agent consumption.

### 3.4 LLMOps Observability (Langfuse)
- Distributed tracing of every agent node transition
- Token consumption tracking per model call
- Tool call latency spans
- Error/failure classification and root-cause logging
- Session-level metadata: `repo_name`, `issue_id`, `resolution_status`

### 3.5 Git Integration
- Automated branch creation (`fix/<issue-id>-<short-description>`)
- Clean commit messages with issue cross-references
- Pull request creation via GitHub API (optional — can be CLI-only)

---

## 4. Architecture Overview

```
  Input (GitHub Issue / CLI / Webhook)
              │
              ▼
  ┌─────────────────────────────────────────────────┐
  │          LangGraph Stateful Graph Engine          │
  │                                                   │
  │  Triage ──► Coder ──► Evaluator ──► Human Gate   │
  │              ▲              │                      │
  │              └──(retry)─────┘                      │
  └──────────────────────┬────────────────────────────┘
                         │ JSON-RPC 2.0 (stdio)
                         ▼
  ┌─────────────────────────────────────────────────┐
  │            FastMCP Tool Server                    │
  │  [read_file] [search_replace] [run_tests] [git]  │
  └──────────────────────┬────────────────────────────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
         Filesystem   Docker    Git CLI
                      Sandbox
```

---

## 5. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Security** | No uncontrolled host filesystem writes. Docker sandbox with no network. Allowlisted tool operations only. |
| **Reliability** | Deterministic retry limits (max 3 iterations). Graceful failure with diagnostic output on timeout or unrecoverable errors. |
| **Performance** | End-to-end resolution in < 5 minutes for single-file bugs. Tool call latency < 500ms (excluding test execution). |
| **Extensibility** | MCP server tools are independently deployable. New tools can be added without modifying the agent graph. |
| **Observability** | 100% of agent decisions and tool calls traced in Langfuse. Zero blind spots. |
| **Portability** | Runs on any system with Python 3.11+, Docker, and Git. No cloud-specific dependencies for core functionality. |

---

## 6. Out of Scope (v1)

- **Multi-repository support** — v1 targets a single repository per session.
- **Auto-merge without approval** — All PRs require human approval.
- **IDE plugin integration** — v1 is CLI/API-only.
- **Non-Python language support** — v1 focuses on Python codebases (extensible later).
- **Continuous monitoring / webhook listener daemon** — v1 is invoked on-demand.

---

## 7. Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| LLM hallucinates destructive code changes | High | Search-and-replace semantics prevent full-file overwrites. Docker sandbox isolates execution. HITL gate before commit. |
| Agent enters infinite retry loop | Medium | Hard `max_iterations` cap (default: 3). Evaluator classifies flaky/environment failures to break loops. |
| Token cost escalation on complex bugs | Medium | Context budget controller limits file reads. Capped retry count. Langfuse cost alerts. |
| MCP server security vulnerabilities | High | Allowlisted tool operations. No arbitrary code execution outside Docker. Strict input validation on all tool parameters. |

---

## 8. Dependencies

| Dependency | Version | Purpose |
|---|---|---|
| Python | ≥ 3.11 | Runtime |
| LangGraph | ≥ 0.2.x | Multi-agent orchestration |
| FastMCP | ≥ 0.1.x | MCP server framework |
| Docker Engine | ≥ 24.x | Sandbox test execution |
| Langfuse | ≥ 2.x | LLMOps observability |
| Anthropic Claude API | Sonnet 4 / Haiku | LLM backbone |
| PostgreSQL | ≥ 15 | LangGraph checkpoint persistence |
| GitPython / GitHub API | Latest | Git operations |

---

## 9. Glossary

| Term | Definition |
|---|---|
| **MCP** | Model Context Protocol — an open standard for connecting AI models to external tools and data sources |
| **LangGraph** | A library for building stateful, multi-actor applications with LLMs as directed graphs |
| **FastMCP** | A Python framework for building MCP servers quickly |
| **HITL** | Human-in-the-Loop — a design pattern where human approval is required at critical decision points |
| **Pass@1** | The probability that a single generated solution passes all test assertions |
| **Search-and-Replace** | A patching strategy where only targeted text blocks are modified, avoiding full-file rewrites |
