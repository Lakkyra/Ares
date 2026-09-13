"""Unit tests for the Ares benchmarking harness, dataset, runner, and reporting."""

from pathlib import Path

from typer.testing import CliRunner

from ares.benchmarks.dataset import BENCHMARK_DATASET, get_all_issues, get_issues_by_category
from ares.benchmarks.models import BenchmarkCategory
from ares.benchmarks.runner import BenchmarkRunner
from ares.cli.main import app

runner = CliRunner()


def test_benchmark_dataset_integrity() -> None:
    """Verify all 25 benchmark issues are valid and adhere to schemas."""
    issues = get_all_issues()
    assert len(issues) == 25

    categories = {issue.category for issue in issues}
    assert len(categories) == 5  # 5 distinct categories

    for cat in BenchmarkCategory:
        cat_issues = get_issues_by_category(cat)
        assert len(cat_issues) == 5, f"Category {cat} should have exactly 5 issues"

    for issue in issues:
        assert issue.issue_id.startswith("BENCH-")
        assert issue.title.strip()
        assert issue.description.strip()
        assert issue.file_path.endswith(".py")
        assert issue.buggy_code.strip()
        assert issue.test_code.strip()
        assert issue.search_block.strip()
        assert issue.replace_block.strip()
        assert issue.search_block in issue.buggy_code, f"search_block missing in {issue.issue_id}"


def test_benchmark_runner_single_issue() -> None:
    """Verify runner evaluates a single issue: fails initial test, passes with patch."""
    issue = BENCHMARK_DATASET[0]  # BENCH-01
    bench_runner = BenchmarkRunner()

    result = bench_runner.run_issue(issue, use_canonical_patch=True)
    assert result.issue_id == issue.issue_id
    assert result.resolved is True
    assert result.pass_at_1 is True
    assert result.iterations == 1
    assert result.duration_ms > 0
    assert result.tokens > 0
    assert result.cost_usd > 0.0
    assert result.error is None


def test_benchmark_runner_without_patch() -> None:
    """Verify runner marks issue unresolved if no patch is applied."""
    issue = BENCHMARK_DATASET[0]
    bench_runner = BenchmarkRunner()

    result = bench_runner.run_issue(issue, use_canonical_patch=False)
    assert result.issue_id == issue.issue_id
    assert result.resolved is False
    assert result.pass_at_1 is False
    assert result.error is not None


def test_benchmark_suite_execution_and_summary() -> None:
    """Verify suite execution aggregates metrics and computes rates correctly."""
    bench_runner = BenchmarkRunner()
    sample_issues = BENCHMARK_DATASET[:3]  # Evaluate first 3 issues

    summary, results = bench_runner.run_suite(
        issues=sample_issues, use_canonical_patch=True, show_progress=False
    )

    assert summary.total_issues == 3
    assert summary.resolved_count == 3
    assert summary.resolve_rate_percent == 100.0
    assert summary.pass_at_1_count == 3
    assert summary.pass_at_1_rate_percent == 100.0
    assert summary.total_cost_usd > 0.0
    assert len(results) == 3

    # Verify report formatting
    report = bench_runner.generate_markdown_report(summary, results)
    assert "# Ares Code Repair Engine: Benchmark Evaluation Report" in report
    assert "Pass@1 Resolve Rate" in report
    assert "BENCH-01" in report

    # Verify terminal table formatting
    table = bench_runner.format_terminal_summary(summary, results)
    assert table is not None


def test_cli_benchmark_command(tmp_path: Path) -> None:
    """Verify `ares benchmark` command evaluates issues and exports report."""
    output_file = tmp_path / "test_report.md"

    result = runner.invoke(
        app,
        [
            "benchmark",
            "--limit",
            "2",
            "--output",
            str(output_file),
            "--canonical",
        ],
    )
    assert result.exit_code == 0
    assert "Ares Benchmark Evaluation Summary" in result.stdout
    assert output_file.exists()
    assert "# Ares Code Repair Engine: Benchmark Evaluation Report" in output_file.read_text(
        encoding="utf-8"
    )
