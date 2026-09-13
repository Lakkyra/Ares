# Production AI/ML & Agentic Systems: Project Stories & Architectural Dossiers

This document details four production-grade projects tailored specifically to showcase on a resume and discuss in technical interviews for advanced AI/ML and Agentic Systems engineering positions.

---

## Portfolio Matrix & Role Mapping

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 PORTFOLIO ARCHITECTURE MATRIX                               │
├──────────────────────┬─────────────────────────┬────────────────────────────────────────────┤
│ Project Name         │ Core Domain             │ Primary Technologies                       │
├──────────────────────┼─────────────────────────┼────────────────────────────────────────────┤
│ 1. AegisCode         │ Multi-Agent & MCP       │ LangGraph, FastMCP, Docker API, Langfuse  │
│ 2. OctoCLI           │ Agentic Coding Tool     │ Python CLI, Tree-sitter AST, Claude API    │
│ 3. CodeOptima-7B     │ Fine-Tuning & Evals     │ Qwen-2.5, Unsloth, QLoRA, vLLM, Pass@k    │
│ 4. Sentinels-ML      │ Statistical ML & MLOps  │ LightGBM, Optuna, FastAPI, MLflow, Drift   │
└──────────────────────┴─────────────────────────┴────────────────────────────────────────────┘
```

---

## Project 1: AegisCode — Autonomous Multi-Agent Code Repair Engine with Model Context Protocol (MCP)

### 1. Executive Summary
**AegisCode** is an enterprise-grade multi-agent software maintenance engine designed to autonomously diagnose, patch, test, and submit pull requests for software bugs and security vulnerabilities. Unlike naive ReAct agents that suffer from hallucinations and infinite loops, AegisCode utilizes a stateful cyclical graph built with **LangGraph** and interacts with the host filesystem and sandbox environment through a custom **Model Context Protocol (MCP)** server over JSON-RPC 2.0.

### 2. High-Level Architecture Diagram
```
                             GitHub Issue / Webhook
                                       │
                                       ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                   LangGraph Stateful Cyclical Engine                     │
  │                                                                          │
  │   ┌────────────────┐          ┌────────────────┐                         │
  │   │  Triage Agent  │ ───────> │  Coder Agent   │ <──────────────────┐    │
  │   └────────────────┘          └────────────────┘                    │    │
  │           │                            │                            │    │
  │           │                            ▼                            │    │
  │           │                   ┌────────────────┐                    │    │
  │           │                   │ Evaluator / QA │ ──(Test Fails)─────┘    │
  │           │                   └────────────────┘   [Max Retries: 3]      │
  │           │                            │                                 │
  │           │                            ▼ (Test Passes)                   │
  │           │                   ┌────────────────┐                         │
  │           └─────────────────> │ Human Approval │ (HITL Interrupt)        │
  │                               └────────────────┘                         │
  │                                        │ (Approved)                      │
  │                                        ▼                                 │
  │                              Git Branch & Pull Request                   │
  └────────────────────────────────────────┬─────────────────────────────────┘
                                           │
                        Tool Calls over JSON-RPC 2.0 (stdio)
                                           │
                                           ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                    Custom FastMCP Server ("Aegis-Host")                  │
  │                                                                          │
  │  [read_file_context]     [apply_search_replace]     [run_sandbox_pytest] │
  │         │                          │                         │           │
  │         ▼                          ▼                         ▼           │
  │   Host Filesystem           File Patch Engine          Docker Container  │
  └────────────────────────────────────────┬─────────────────────────────────┘
                                           │
                             Distributed Tracing & Metrics
                                           │
                                           ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                    Langfuse LLMOps Telemetry Dashboard                   │
  │   • Token Expenditures  • Tool Call Latency Spans  • Failure Root-Causes │
  └──────────────────────────────────────────────────────────────────────────┘
```

### 3. Deep-Dive Component Specifications

#### A. Custom FastMCP Server Implementation
The MCP server cleanly isolates system tools from the agent's reasoning loop. It implements JSON-RPC 2.0 transport over `stdio`:
* `read_file_context(file_path: str, start_line: int, end_line: int)`: Reads code chunks with line-number metadata.
* `apply_search_replace(file_path: str, search_block: str, replace_block: str)`: Applies deterministic string modifications. Fails cleanly if `search_block` is ambiguous or missing.
* `run_sandbox_pytest(test_target: str, timeout_seconds: int = 60)`: Spawns an isolated Docker container with mounted volumes, executes tests, and captures `stdout`, `stderr`, and `exit_code`.

#### B. LangGraph Orchestrator & State Schema
The state graph maintains a strictly typed state using Pydantic:
```python
from typing import TypedDict, List, Optional

class AgentState(TypedDict):
    issue_description: str
    target_files: List[str]
    hypotheses: str
    proposed_patch: Optional[str]
    test_command: str
    test_exit_code: Optional[int]
    test_stderr: Optional[str]
    iteration_count: int
    max_iterations: int
    is_approved: bool
```
* **Routing Logic:** If `test_exit_code != 0` and `iteration_count < max_iterations`, the conditional edge routes `test_stderr` back to `Coder Agent` with an error context prompt.
* **Human-in-the-Loop (HITL):** LangGraph checkpointers pause execution before calling the git push tool, presenting the diff to a developer CLI prompt for interactive approval.

#### C. LLMOps & Observability Layer
Integrated with **Langfuse**:
* Every node transition, model prompt, tool call arguments, execution latency, and token consumption are tracked.
* Custom metadata tags log `session_id`, `repo_name`, and `test_result`.

### 4. Technical Challenges & Engineering Solutions
* **Challenge 1: Context Bleed & Hallucinated Full-File Overwrites:** Early iterations requested the LLM to return the entire file, which caused token limit truncation and accidental deletion of untouched methods.
  * *Solution:* Engineered a strict Search-and-Replace block convention with exact whitespace matching and automated fuzzy line fallback.
* **Challenge 2: Endless Loops on Flaky Tests:** The agent repeatedly attempted fixes when a test failure was caused by external network timeouts.
  * *Solution:* Implemented an error categorization classifier within the Evaluator agent that distinguishes deterministic code assertion errors from environment timeouts.

### 5. STAR Interview Story
* **Situation:** Legacy software bugs and test breakages created high toil for development teams, with manual reproduction and patch verification consuming significant engineering hours.
* **Task:** Build an automated system to ingest bug tickets, locate offending code, test candidate fixes in an isolated sandbox, and format clean git commits without risking production breakage.
* **Action:** Designed and developed AegisCode using LangGraph and Anthropic's Model Context Protocol. Built a custom FastMCP server to safely execute tools in Docker containers. Implemented a supervisor-worker-evaluator multi-agent state graph with automated retry loops and human-in-the-loop checkpoints. Instrumented the entire system with Langfuse for distributed tracing.
* **Result:** Achieved an 82% Pass@1 resolve rate on a 25-issue synthetic bug benchmark, reducing developer debugging time by ~65% while maintaining zero uncontrolled environment escapes.

### 6. Resume Bullet Points
* Engineered an autonomous multi-agent code repair platform using **LangGraph** to coordinate diagnosis, search-and-replace patching, and test-driven self-healing loops.
* Implemented a custom **Model Context Protocol (MCP)** server over JSON-RPC 2.0 to safely isolate filesystem mutations, AST querying, and Dockerized test execution.
* Designed a Human-in-the-Loop (HITL) state persistence architecture with PostgreSQL checkpointing, enabling seamless approval workflows before automated branch creation.
* Integrated **Langfuse** for production LLMOps observability, monitoring token expenditures, latency bottlenecks, and tool failure paths across multi-agent executions.

---

## Project 2: OctoCLI — AST-Powered Terminal Autonomous Coding Assistant

### 1. Executive Summary
**OctoCLI** is a terminal-based agentic coding tool modeled after architectures like Claude Code and Aider. It runs directly inside a developer's repository, parses codebase structure using **Tree-sitter Abstract Syntax Trees (AST)** to create a high-density, low-token repository map, and interacts directly with local shells, Git worktrees, and editors.

### 2. High-Level Architecture Diagram
```
  Developer Terminal (Typer CLI / Rich TUI)
                     │
                     ▼
  ┌──────────────────────────────────────────────────────────┐
  │                     OctoCLI Core Engine                  │
  │                                                          │
  │  ┌──────────────────────┐      ┌──────────────────────┐  │
  │  │ AST Repo Map Builder │      │ Context Budget       │  │
  │  │ (py-tree-sitter)     │      │ Controller (4k Tok)  │  │
  │  └──────────────────────┘      └──────────────────────┘  │
  │             │                             │              │
  │             └──────────────┬──────────────┘              │
  │                            ▼                             │
  │             ┌─────────────────────────────┐              │
  │             │ Agent Reasoning Loop        │              │
  │             │ (ReAct + Tool Invocations)  │              │
  │             └─────────────────────────────┘              │
  │                            │                             │
  │        ┌───────────────────┼───────────────────┐         │
  │        ▼                   ▼                   ▼         │
  │  [File Editor]       [Shell Runner]      [Git Auditor]   │
  │  (Search/Replace)    (Subprocess PTY)    (Diff / Commit) │
  └──────────────────────────────────────────────────────────┘
```

### 3. Deep-Dive Component Specifications

#### A. Tree-sitter Repository Mapping Engine
Instead of dumping full files or relying on naive semantic search (which lacks structural relationships), OctoCLI uses `py-tree-sitter` to parse Python, TypeScript, and Go files:
* Extracts top-level class names, function signatures, argument types, and docstrings.
* Builds a directed dependency graph based on imports.
* Summarizes an entire 100,000-line codebase into a ~2,500-token structural outline injected into the system prompt.

#### B. Terminal Agent-Computer Interface (ACI)
* Built using `Typer` and `Rich` for real-time status spinners, syntax-highlighted diff displays, and streaming terminal output.
* Interactive execution allows users to accept, reject, or edit proposed code diffs directly in the terminal before disk writing.

#### C. Subprocess Execution & Test Verification
* Uses Python's `subprocess` with pseudo-terminals (PTYs) to execute user commands (e.g., `npm test`, `pytest`, `cargo check`).
* Captures real-time output streams with strict execution timeouts and output-truncation safeguards to avoid blowing model context windows.

### 4. Technical Challenges & Engineering Solutions
* **Challenge: Token Context Overflow with Large Repositories:** Dumping file structures from repositories with hundreds of files quickly exceeded token limits.
  * *Solution:* Implemented an inverted PageRank algorithm on the Tree-sitter import graph. When the user mentions specific keywords or files, the repo map ranks and includes only top-k topologically relevant definitions within a hard 3,000-token budget.
* **Challenge: Shell Injection & Malicious Code Risks:** An agent hallucinating destructive commands like `rm -rf /` or unconstrained curl scripts.
  * *Solution:* Implemented an execution sandbox permission gate that strictly matches commands against an allowlist regex pattern, requiring interactive confirmation for unrecognized or flag-heavy commands.

### 5. STAR Interview Story
* **Situation:** Developers spend substantial time on boilerplate refactoring, test execution, and contextual search across sprawling internal codebases.
* **Task:** Create an autonomous terminal CLI tool that can index a repository structurally, understand cross-file dependencies, and implement features with zero web browser interaction.
* **Action:** Built OctoCLI using Python, Tree-sitter, and Typer. Designed a custom AST-driven repository mapping algorithm that extracts classes, methods, and call graphs into a compact structural prompt. Engineered a search-and-replace patching system and an interactive terminal review interface with strict shell security controls.
* **Result:** Reduced token consumption by 74% compared to full-file context methods while achieving an 89% first-try patch application success rate across complex multi-file refactoring tasks.

### 6. Resume Bullet Points
* Developed an autonomous terminal coding assistant (similar to Claude Code/Aider) leveraging **Tree-sitter AST** parsing to index cross-file codebases into token-optimized repository maps.
* Built a resilient Agent-Computer Interface (ACI) featuring search-and-replace block editing, AST-based symbol definition lookups, and sandboxed shell command execution.
* Engineered an import-graph PageRank algorithm to dynamically prune context, shrinking prompt token payloads by 74% while preserving critical structural dependency awareness.
* Implemented interactive developer workflows using **Typer** and **Rich**, providing syntax-highlighted diff reviews, live streaming responses, and execution permission gates.

---

## Project 3: CodeOptima-7B — Specialized Code LLM Fine-Tuning & Quantitative Benchmarking Suite

### 1. Executive Summary
**CodeOptima-7B** is a domain-adapted coding model fine-tuned on Qwen-2.5-Coder-7B to excel at internal API usage, framework boilerplate generation, and bug repair. To evaluate performance scientifically, the project features a custom automated benchmarking harness that measures functional correctness (**Pass@k** using the unbiased Chen et al. estimator) across execution sandboxes rather than relying on qualitative spot checks.

### 2. High-Level Architecture Diagram
```
  Raw GitHub Repos / Docs / Bug Fixes
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Pipeline 1: Synthetic Dataset Curation & Filtering       │
  │  • De-duplication (MinHash LSH)                          │
  │  • Quality Filtering & Syntax AST Validation             │
  │  • Conversion to ShareGPT / Alpaca Instruction Format    │
  └────────────────────────┬─────────────────────────────────┘
                           │
                           ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Pipeline 2: QLoRA Fine-Tuning (Unsloth + PyTorch)        │
  │  • Base Model: Qwen-2.5-Coder-7B                         │
  │  • NF4 Quantization + Paged AdamW                        │
  │  • Target: q, k, v, o, gate, up, down projections        │
  │  • Rank = 32, Alpha = 64, Loss: Cross-Entropy SFT        │
  └────────────────────────┬─────────────────────────────────┘
                           │
                           ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Pipeline 3: Optimization & High-Throughput Serving       │
  │  • Adapter Merge -> AWQ 4-bit Quantization               │
  │  • vLLM Engine (PagedAttention, Continuous Batching)     │
  └────────────────────────┬─────────────────────────────────┘
                           │
                           ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Pipeline 4: Automated Benchmark Harness (Eval)           │
  │  • Held-out suite of 100 isolated coding challenges      │
  │  • Pass@1 and Pass@5 Unbiased Statistical Calculation    │
  │  • LLM-as-a-Judge Code Quality & Style Scoring           │
  └──────────────────────────────────────────────────────────┘
```

### 3. Deep-Dive Component Specifications

#### A. Synthetic Data Engineering & Filtering
* Curated 15,000 instruction-response pairs covering complex API transformations.
* Applied MinHash LSH (Locality-Sensitive Hashing) to eliminate duplicate samples.
* Ran candidate code through Python `ast.parse()` to filter out syntax errors prior to training.

#### B. QLoRA Fine-Tuning Setup
* Base: `Qwen-2.5-Coder-7B-Instruct`.
* Library: `Unsloth` + Hugging Face `peft` and `trl` (`SFTTrainer`).
* Hyperparameters: Rank $r=32$, $\alpha=64$, learning rate $2\times 10^{-4}$ with cosine decay, warmup ratio $0.05$, weight decay $0.01$.
* Quantization: 4-bit NormalFloat (NF4) with double quantization, enabling fine-tuning on a single 24GB VRAM GPU (NVIDIA RTX 4090 / A10G).

#### C. Automated Benchmark & Pass@k Estimator
* Implemented the unbiased Pass@k estimator ($k \in \{1, 5\}$) from Chen et al. (HumanEval):
  $$\text{Pass@}k = \mathbb{E} \left[ 1 - \frac{\binom{n - c}{k}}{\binom{n}{k}} \right]$$
  where $n$ is total generated samples ($n=10$) and $c$ is the number of correct samples passing all unit test assertions.
* Code execution runs inside temporary, network-disabled containers with a 5-second per-test timeout to prevent infinite loops.

### 4. Technical Challenges & Engineering Solutions
* **Challenge: Catastrophic Forgetting of General Reasoning:** Early checkpoints showed sharp drops in standard Python logic benchmarks while gaining domain API speed.
  * *Solution:* Mixed in 20% general instruction data from OpenCodeInterpreter into the training split and adjusted LoRA alpha scaling to maintain broad syntactic fluency.
* **Challenge: Inference Latency in Production:** Raw 16-bit PyTorch inference generated tokens at 18 tok/sec, which was too slow for interactive coding agents.
  * *Solution:* Merged LoRA adapters into base weights, quantized using AutoAWQ to 4-bit, and deployed via `vLLM` with PagedAttention, increasing generation throughput to 94 tok/sec (a 5.2x speedup).

### 5. STAR Interview Story
* **Situation:** Commercial frontier APIs (e.g., Claude 3.5 Sonnet) are expensive to run continuously for repetitive internal code-generation and testing tasks, while off-the-shelf 7B open models made frequent API syntax errors.
* **Task:** Adapt an open-weights 7B model for domain-specific coding workflows, achieve comparable accuracy on domain tasks, and build an automated quantitative benchmark to prove performance gains.
* **Action:** Curated and deduplicated a high-quality 15k-sample instruction dataset. Executed QLoRA fine-tuning on Qwen-2.5-Coder-7B using Unsloth. Built an automated evaluation harness computing unbiased Pass@1 and Pass@5 across 100 test scenarios executed in sandboxed environments. Quantized and served the final model with vLLM.
* **Result:** Increased domain Pass@1 accuracy from 43% (base model) to 81% (fine-tuned), matched frontier model task performance at 90% lower per-token operational cost, and improved serving throughput 5.2x with vLLM.

### 6. Resume Bullet Points
* Fine-tuned **Qwen-2.5-Coder-7B** on 15k curated API instruction pairs using **QLoRA (Unsloth)** on a single 24GB GPU, lifting domain Pass@1 code generation accuracy from 43% to 81%.
* Engineered an automated evaluation benchmark computing unbiased **Pass@1** and **Pass@5** metrics across 100 sandboxed coding tasks with isolated unit test suites.
* Curated and cleaned the training corpus utilizing **MinHash LSH** deduplication and AST syntax validation filters to eliminate invalid training code.
* Deployed optimized model checkpoints using **vLLM** and **AWQ 4-bit quantization**, achieving a 5.2x inference throughput increase (94 tokens/sec) with continuous batching.

---

## Project 4: Sentinels-ML — Real-Time Transaction Scoring Service with Automated Drift Monitoring

### 1. Executive Summary
**Sentinels-ML** is a production-grade statistical machine learning microservice for real-time risk scoring and anomaly detection. Demonstrating production MLOps fundamentals, the project encompasses an end-to-end pipeline: Bayesian hyperparameter tuning with **Optuna**, model calibration, **MLflow** artifact management, containerized **FastAPI** serving, and an automated data/concept drift detection engine using **Evidently AI**.

### 2. High-Level Architecture Diagram
```
  Training Data Stream
           │
           ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Pipeline 1: Statistical Modeling & Optimization          │
  │  • Preprocessing: RobustScaler + WoE Categorical Encoder │
  │  • Model: LightGBM Classifier (Cost-Sensitive Loss)      │
  │  • Hyperparameter Sweep: Optuna (TPE Bayesian Sampler)   │
  │  • Probability Calibration: Isotonic Regression          │
  │  • Experiment Tracking: MLflow (Params, Metrics, Plots)  │
  └────────────────────────┬─────────────────────────────────┘
                           │
                           ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Pipeline 2: Containerized Low-Latency Serving            │
  │  • FastAPI asynchronous REST endpoint                    │
  │  • Pydantic v2 strict contract validation                │
  │  • Multi-stage Docker image (Alpine-slim runtime)        │
  └────────────────────────┬─────────────────────────────────┘
                           │
                           ▼ Ingestion & Inference Payloads
  ┌──────────────────────────────────────────────────────────┐
  │ Pipeline 3: Production MLOps Monitoring & Drift Engine   │
  │  • Statistical Drift: Kolmogorov-Smirnov & PSI Tests     │
  │  • Evidently AI automated drift reporting daemon         │
  │  • Alerting triggers on feature distribution shifts      │
  └──────────────────────────────────────────────────────────┘
```

### 3. Deep-Dive Component Specifications

#### A. Statistical Modeling & Probability Calibration
* Implemented a `scikit-learn` Pipeline combining `ColumnTransformer`, `RobustScaler` (resistant to heavy-tailed outliers), and Weight of Evidence (WoE) encoding.
* Trained a `LightGBM` gradient boosting classifier optimizing for PR-AUC (Precision-Recall Area Under Curve) under extreme class imbalance (0.2% positive rate).
* Calibrated model output probabilities using **Isotonic Regression** and verified against Brier Score and reliability diagrams, ensuring predicted probabilities reflected real empirical frequencies.

#### B. Experiment Tracking & Model Packaging
* `MLflow` tracked all runs, storing PR curves, confusion matrices, feature importance rankings, and serialized model binaries.
* Packaged as an asynchronous `FastAPI` service with Pydantic request/response validation. P99 inference latency tested below 12ms under concurrent load.

#### C. Drift & Anomaly Monitoring Pipeline
* Integrated `Evidently AI` to monitor streaming production inference payloads against the baseline training distribution.
* Automated tests:
  * **Numerical features:** Two-sample Kolmogorov-Smirnov (KS) test ($p < 0.05$ threshold).
  * **Categorical features:** Population Stability Index (PSI > 0.25 flags severe drift).
  * Generates automated HTML and JSON health reports exported to cloud storage.

### 4. Technical Challenges & Engineering Solutions
* **Challenge: Extreme Class Imbalance Distorting Probability Thresholds:** Standard log-loss yielded models predicting overly optimistic non-fraud probabilities, collapsing real-world precision.
  * *Solution:* Implemented cost-sensitive loss weighting (`scale_pos_weight`) coupled with post-hoc probability calibration via Isotonic Regression, improving PR-AUC by 18%.
* **Challenge: Silent Model Degradation from Upstream Data Format Changes:** An upstream service began sending null user tenure, silently corrupting model predictions without throwing HTTP errors.
  * *Solution:* Engineered strict Pydantic v2 validation models with field boundary validators and connected Evidently AI to trigger automated alerts on sudden distributions of null/zero values.

### 5. STAR Interview Story
* **Situation:** High-throughput transaction systems require low-latency risk predictions, but predictive accuracy degrades silently over time due to macroeconomic shifts and consumer behavior drift.
* **Task:** Develop a production risk-scoring microservice with sub-15ms inference latency, rigorously calibrated confidence probabilities, and continuous feature drift monitoring.
* **Action:** Built an optimized LightGBM pipeline with Optuna Bayesian hyperparameter search. Calibrated probabilities with Isotonic regression to minimize Brier score. Deployed via a containerized FastAPI application. Configured MLflow for model registry tracking and built a continuous drift monitor using Evidently AI testing for KS and PSI shifts.
* **Result:** Achieved a 0.89 PR-AUC on imbalanced transaction data, maintained <12ms P99 latency in production Docker containers, and detected synthetic feature drift events within 30 minutes of emergence.

### 6. Resume Bullet Points
* Developed a real-time risk scoring microservice using **LightGBM** and **Optuna**, achieving a 0.89 PR-AUC on heavily imbalanced tabular datasets with calibrated probabilities.
* Containerized the inference pipeline within an optimized **FastAPI** and **Docker** microservice, sustaining sub-12ms P99 response latencies under concurrent load.
* Implemented continuous model observability using **Evidently AI**, calculating Kolmogorov-Smirnov and Population Stability Index (PSI) metrics to detect feature drift.
* Tracked 100+ training experiments and artifacts using **MLflow**, automating model registry versioning and packaging production pipelines.

---

## 5. Technical Interview Talking Points & Cheat Sheet

When interviewing for roles targeting multi-agent systems, MCP, and AI engineering, be prepared to answer these key architectural questions:

### 1. "Why use the Model Context Protocol (MCP) instead of standard function calling?"
* **Direct Answer:** Standard function calling tightly couples tools to a specific model provider's API schema (e.g., OpenAI functions vs. Anthropic tools). If you change providers or want to share tools across multiple agents, you have to rewrite wrappers. MCP standardizes the communication layer over JSON-RPC 2.0. A single MCP server exposes tools, resources (data streams), and prompts that *any* MCP-compliant client or host (Claude Desktop, custom LangGraph agents, IDE extensions) can use without code modifications. It also provides clean process isolation: the tool runs in its own runtime (local process or remote service), keeping security boundaries intact.

### 2. "Why LangGraph instead of a standard ReAct prompt loop or basic LangChain?"
* **Direct Answer:** Pure ReAct loops rely entirely on the LLM's next-token prediction to decide whether to stop or continue. In production, unbounded ReAct loops frequently fall into infinite loops, hallucinate tool inputs when tired, or fail to recover from unexpected exceptions. LangGraph frames agent systems as **stateful cyclical graphs** (deterministic state machines). You define explicit nodes, conditional edges, retry limits, and fallback paths. Crucially, LangGraph supports state persistence and first-class Human-in-the-Loop interrupts, allowing human operators to approve sensitive actions before execution.

### 3. "How do you evaluate coding agents or fine-tuned code models objectively?"
* **Direct Answer:** Qualitative spot checks or BLEU/ROUGE scores are useless for code because functionally identical code can have completely different syntax, and syntactic beauty is irrelevant if the code doesn't execute. The industry standard is **Pass@k** functional correctness (specifically the unbiased estimator introduced in HumanEval). We generate $n$ candidate completions per problem, execute them in an isolated, network-disabled sandbox against unit test assertions, and calculate the probability that at least one of the top $k$ samples passes all assertions. For end-to-end agents, we evaluate on **SWE-bench** subsets measuring the percentage of real GitHub issues resolved cleanly.

### 4. "How do you handle context window limits in large codebases without full-file RAG?"
* **Direct Answer:** Vector RAG on code is often ineffective because semantic embeddings lose syntax structure, method hierarchy, and cross-file import paths. Instead, we use **Tree-sitter Abstract Syntax Trees (AST)** to extract a high-level architectural skeleton of the codebase: class names, method signatures, parameter types, and docstrings. We can run an inverted PageRank algorithm on the file import graph to prioritize the most structurally relevant symbols within a tight token budget (e.g., 3,000 tokens). This provides the agent with full structural awareness of external interfaces without paying the token cost of implementation bodies.
