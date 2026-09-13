"""Observability and telemetry data models for Ares."""

from pydantic import BaseModel, Field


class ToolCallMetric(BaseModel):
    """Telemetry metric for a single MCP tool execution."""

    tool_name: str
    duration_ms: int
    success: bool
    error: str | None = None


class TokenUsage(BaseModel):
    """Aggregated token count."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class SessionMetrics(BaseModel):
    """Full session execution telemetry report."""

    session_id: str
    repo_name: str
    issue_id: str
    resolution_status: str
    iteration_count: int
    total_duration_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    tool_calls: list[ToolCallMetric] = Field(default_factory=list)
