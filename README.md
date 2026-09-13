# Ares (CodeRepair Engine)

> **Autonomous Multi-Agent Code Repair Engine**  
> Powered by LangGraph, FastMCP, Docker Sandboxing, and Langfuse Observability.

Ares is an autonomous multi-agent system designed to localize, patch, and rigorously verify software bugs in codebases without human intervention (unless requested via Human-In-The-Loop safety mechanisms).

---

## Architecture Overview

```
                          +-------------------------+
                          |   CLI / User Input      |
                          +------------+------------+
                                       |
                                       v
                    +-------------------------------------+
                    |       LangGraph Orchestrator        |
                    |  (State, Checkpoints in PostgreSQL) |
                    +----+-------------+-------------+----+
                         |             |             |
           +-------------+             |             +-------------+
           v                           v                           v
+--------------------+      +--------------------+      +--------------------+
|  Reproducer Agent  |      |   Locator Agent    |      |    Patcher Agent   |
| (Generates repro)  |      | (Pinpoints fault)  |      | (Targeted patch)   |
+---------+----------+      +---------+----------+      +---------+----------+
          |                           |                           |
          +-------------------+-------+---------------------------+
                              |
                              v
                  +-----------------------+
                  |    FastMCP Server     |
                  |  (Tools: file read,   |
                  |   patch, test runner) |
                  +-----------+-----------+
                              |
                              v
                  +-----------------------+
                  |    Docker Sandbox     |
                  |  (Isolated execution, |
                  |   network-disabled)   |
                  +-----------------------+
```

---

## Prerequisites

- **Python**: 3.11 or higher
- **Package Manager**: [uv](https://github.com/astral-sh/uv) (`pip install uv`)
- **Docker**: Docker Desktop (with daemon running)
- **API Keys**: Anthropic and/or OpenAI, Langfuse (optional for tracing)

---

## Quickstart

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/Lakkyra/Ares.git
cd Ares

# Create venv and install dependencies via uv
uv venv .venv
# On Windows:
.venv\Scripts\activate
# On Unix:
source .venv/bin/activate

uv pip install -e ".[dev]"
```

### 2. Environment Configuration

```bash
cp .env.example .env
# Edit .env with your LLM API keys
```

### 3. Start PostgreSQL Checkpoint Database

```bash
docker compose up -d
```

### 4. Build Test Sandbox Container

```bash
docker build -f Dockerfile.sandbox -t ares-sandbox:latest .
```

### 5. Run Verification & Tests

```bash
# Run pytest
pytest tests/unit/

# Run type checks & linter
ruff check .
mypy src
```

---

## CLI Usage

```bash
# Show version
ares version

# Check configuration
ares config

# Run autonomous code repair
ares fix "pytest tests/test_calculator.py fails with ZeroDivisionError" --repo ./my-project
```

---

## Project Structure

```
Ares/
├── src/
│   └── ares/
│       ├── agents/          # LangGraph nodes (Reproducer, Locator, Patcher, etc.)
│       ├── mcp_server/      # FastMCP tool server and registry
│       ├── sandbox/         # Docker container manager and isolation guards
│       ├── git_ops/         # Git branch, diff, commit, and PR creation
│       ├── observability/   # Langfuse telemetry and span handlers
│       ├── config/          # Pydantic settings and env loader
│       └── cli/             # Typer CLI application
├── tests/
│   ├── unit/                # Fast unit tests (no LLM, mocked tools)
│   ├── integration/         # Docker + MCP integration tests
│   └── benchmarks/          # Evaluation suite on synthetic bugs
├── docs/                    # Architectural documents & Interview prep
├── docker-compose.yml       # Local PostgreSQL checkpointer
├── Dockerfile.sandbox       # Secure test runner image
├── pyproject.toml           # Project build config & dependencies
└── README.md
```
