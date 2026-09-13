"""Langfuse telemetry tracer and session metric coordinator for Ares."""

import contextlib
import time
from typing import Any

from ares.config.settings import settings
from ares.observability.cost import calculate_token_cost
from ares.observability.models import SessionMetrics, TokenUsage, ToolCallMetric


class AresTracer:
    """Central telemetry collector supporting Langfuse and local metric aggregation."""

    def __init__(
        self,
        public_key: str | None = None,
        secret_key: str | None = None,
        host: str | None = None,
    ) -> None:
        self.public_key = public_key or settings.langfuse_public_key
        self.secret_key = secret_key or settings.langfuse_secret_key
        self.host = host or settings.langfuse_host
        self.is_enabled = bool(self.public_key and self.secret_key)

        self._client: Any = None
        self._session_id: str = "default-session"
        self._repo_name: str = "unknown-repo"
        self._issue_id: str = "unknown-issue"
        self._start_time: float = time.perf_counter()

        self._token_usage = TokenUsage()
        self._total_cost_usd: float = 0.0
        self._tool_calls: list[ToolCallMetric] = []

    def get_client(self) -> Any:
        """Lazily initialize Langfuse client if credentials are configured."""
        if not self.is_enabled:
            return None
        if self._client is None:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=self.public_key,
                    secret_key=self.secret_key,
                    host=self.host,
                )
            except Exception:
                self._client = None
        return self._client

    def start_session(
        self,
        session_id: str,
        repo_name: str = "local-repo",
        issue_id: str = "issue-1",
    ) -> None:
        """Initialize session tracking metadata."""
        self._session_id = session_id
        self._repo_name = repo_name
        self._issue_id = issue_id
        self._start_time = time.perf_counter()
        self._token_usage = TokenUsage()
        self._total_cost_usd = 0.0
        self._tool_calls = []

    def record_tool_call(
        self,
        tool_name: str,
        duration_ms: int,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Record telemetry for a single MCP tool execution."""
        metric = ToolCallMetric(
            tool_name=tool_name,
            duration_ms=duration_ms,
            success=success,
            error=error,
        )
        self._tool_calls.append(metric)

    def record_tokens(
        self,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """Record token consumption and calculate marginal cost."""
        self._token_usage.prompt_tokens += prompt_tokens
        self._token_usage.completion_tokens += completion_tokens
        self._token_usage.total_tokens += prompt_tokens + completion_tokens
        cost = calculate_token_cost(model_name, prompt_tokens, completion_tokens)
        self._total_cost_usd += cost

    def get_callback_handler(
        self,
        session_id: str | None = None,
        tags: list[str] | None = None,
    ) -> Any:
        """Get a LangchainCallbackHandler for LangGraph if Langfuse is configured."""
        if not self.is_enabled:
            return None
        try:
            from langfuse.langchain import CallbackHandler
            from langfuse.types import TraceContext

            sid = session_id or self._session_id
            context: TraceContext = {"trace_id": sid}
            return CallbackHandler(
                public_key=self.public_key,
                trace_context=context,
            )
        except Exception:
            return None

    def end_session(
        self,
        resolution_status: str = "resolved",
        iteration_count: int = 1,
    ) -> SessionMetrics:
        """Finalize the session, aggregate telemetry, and return metrics."""
        duration_ms = int((time.perf_counter() - self._start_time) * 1000)
        metrics = SessionMetrics(
            session_id=self._session_id,
            repo_name=self._repo_name,
            issue_id=self._issue_id,
            resolution_status=resolution_status,
            iteration_count=iteration_count,
            total_duration_ms=duration_ms,
            prompt_tokens=self._token_usage.prompt_tokens,
            completion_tokens=self._token_usage.completion_tokens,
            total_tokens=self._token_usage.total_tokens,
            estimated_cost_usd=round(self._total_cost_usd, 6),
            tool_calls=list(self._tool_calls),
        )
        self.flush()
        return metrics

    def format_summary_table(self, metrics: SessionMetrics) -> str:
        """Format a clean, structured text report of the session telemetry."""
        from rich.console import Console
        from rich.table import Table

        console = Console(record=True, width=80)
        table = Table(title="Ares Session Telemetry Summary", border_style="cyan")
        table.add_column("Metric", style="bold yellow")
        table.add_column("Value", style="green")

        table.add_row("Session ID", metrics.session_id)
        table.add_row("Repository", metrics.repo_name)
        table.add_row("Resolution Status", metrics.resolution_status.upper())
        table.add_row("Repair Iterations", str(metrics.iteration_count))
        table.add_row("Total Runtime", f"{metrics.total_duration_ms / 1000:.2f}s")
        table.add_row("Prompt Tokens", f"{metrics.prompt_tokens:,}")
        table.add_row("Completion Tokens", f"{metrics.completion_tokens:,}")
        table.add_row("Total Tokens", f"{metrics.total_tokens:,}")
        table.add_row("Estimated Cost", f"${metrics.estimated_cost_usd:.4f} USD")
        table.add_row("Tool Invocations", str(len(metrics.tool_calls)))

        console.print(table)
        return console.export_text()

    def flush(self) -> None:
        """Flush pending Langfuse observations if client is active."""
        if self._client is not None:
            with contextlib.suppress(Exception):
                self._client.flush()


default_tracer = AresTracer()
