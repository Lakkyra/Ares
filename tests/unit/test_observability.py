"""Unit tests for Ares observability, cost calculation, and telemetry."""

from unittest.mock import MagicMock, patch

from ares.observability.cost import calculate_token_cost
from ares.observability.tracer import AresTracer, default_tracer


def test_cost_calculation_claude_sonnet() -> None:
    """Verify cost calculation for Claude 3.5 Sonnet ($3/M in, $15/M out)."""
    # 100k input = $0.30, 10k output = $0.15 -> total $0.45
    cost = calculate_token_cost(
        model_name="claude-3-5-sonnet-20241022",
        prompt_tokens=100_000,
        completion_tokens=10_000,
    )
    assert cost == 0.45


def test_cost_calculation_gpt4o() -> None:
    """Verify cost calculation for GPT-4o ($2.50/M in, $10/M out)."""
    # 200k input = $0.50, 50k output = $0.50 -> total $1.00
    cost = calculate_token_cost(
        model_name="gpt-4o",
        prompt_tokens=200_000,
        completion_tokens=50_000,
    )
    assert cost == 1.0


def test_cost_calculation_unknown_model() -> None:
    """Verify fallback cost calculation for unrecognized models ($2.50/M in, $10/M out)."""
    cost = calculate_token_cost(
        model_name="unknown-custom-model",
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
    )
    # Default is $2.50/M in, $10.00/M out -> total $12.50
    assert cost == 12.5


def test_tracer_session_lifecycle_and_metrics() -> None:
    """Verify full tracer session lifecycle and metrics aggregation."""
    tracer = AresTracer(public_key="", secret_key="")  # Local mode
    assert tracer.is_enabled is False

    tracer.start_session(session_id="session-123", repo_name="demo-repo", issue_id="bug-42")

    # Record tool calls
    tracer.record_tool_call("read_file_context", duration_ms=45, success=True)
    tracer.record_tool_call(
        "apply_search_replace", duration_ms=12, success=False, error="Ambiguous match"
    )

    # Record tokens
    tracer.record_tokens("claude-3-5-sonnet-20241022", prompt_tokens=5000, completion_tokens=1000)

    # End session
    metrics = tracer.end_session(resolution_status="resolved", iteration_count=2)

    assert metrics.session_id == "session-123"
    assert metrics.repo_name == "demo-repo"
    assert metrics.issue_id == "bug-42"
    assert metrics.resolution_status == "resolved"
    assert metrics.iteration_count == 2
    assert metrics.prompt_tokens == 5000
    assert metrics.completion_tokens == 1000
    assert metrics.total_tokens == 6000
    assert metrics.estimated_cost_usd > 0.0
    assert len(metrics.tool_calls) == 2
    assert metrics.tool_calls[0].tool_name == "read_file_context"
    assert metrics.tool_calls[1].success is False


def test_format_summary_table() -> None:
    """Verify formatted Rich table output string."""
    tracer = AresTracer(public_key="", secret_key="")
    tracer.start_session("sess-1", "repo-1", "issue-1")
    tracer.record_tokens("gpt-4o", 1000, 500)
    metrics = tracer.end_session("resolved", 1)

    table_text = tracer.format_summary_table(metrics)
    assert "Ares Session Telemetry Summary" in table_text
    assert "sess-1" in table_text
    assert "RESOLVED" in table_text


def test_callback_handler_disabled() -> None:
    """Verify get_callback_handler returns None when Langfuse keys are absent."""
    tracer = AresTracer(public_key="", secret_key="")
    assert tracer.get_callback_handler() is None


def test_callback_handler_enabled() -> None:
    """Verify get_callback_handler returns a CallbackHandler when enabled."""
    tracer = AresTracer(
        public_key="pk-lf-test", secret_key="sk-lf-test", host="http://localhost:3000"
    )
    assert tracer.is_enabled is True
    handler = tracer.get_callback_handler(session_id="trace-session-123")
    assert handler is not None


def test_format_summary_table_with_tools_and_failure() -> None:
    """Verify Rich table formatting when resolution fails and tools are recorded."""
    tracer = AresTracer(public_key="", secret_key="")
    tracer.start_session("sess-fail", "repo-fail", "issue-fail")
    tracer.record_tool_call("read_file_context", duration_ms=10, success=True)
    tracer.record_tool_call(
        "apply_search_replace", duration_ms=25, success=False, error="Syntax error"
    )
    metrics = tracer.end_session(resolution_status="failed", iteration_count=3)

    table_text = tracer.format_summary_table(metrics)
    assert "FAILED" in table_text
    assert "Tool Invocations" in table_text
    assert "2" in table_text


def test_default_tracer_instance() -> None:
    """Verify default_tracer singleton is available and initialized."""
    assert isinstance(default_tracer, AresTracer)


def test_tracer_langfuse_init_and_flush() -> None:
    """Verify tracer initializes Langfuse client and flushes cleanly."""
    mock_client = MagicMock()
    with patch("langfuse.Langfuse", return_value=mock_client):
        tracer = AresTracer(
            public_key="pk-lf-valid",
            secret_key="sk-lf-valid",
            host="https://cloud.langfuse.com",
        )
        assert tracer.is_enabled is True
        client = tracer.get_client()
        assert client is mock_client
        assert tracer._client is mock_client

        # Flush
        tracer.flush()
        mock_client.flush.assert_called_once()
