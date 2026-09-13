"""Data models for benchmark issues, evaluation results, and aggregate reporting."""

from enum import StrEnum

from pydantic import BaseModel, Field


class BenchmarkCategory(StrEnum):
    """Five core bug categories evaluated in Ares benchmarks."""

    LOGIC_ERROR = "logic_error"
    EXCEPTION_HANDLING = "exception_handling"
    IMPORT_DEPENDENCY = "import_dependency"
    TYPE_MISMATCH = "type_mismatch"
    EDGE_CASE = "edge_case"


class BenchmarkIssue(BaseModel):
    """Specification of a single benchmark bug issue with test suite and patch."""

    issue_id: str = Field(..., description="Unique issue identifier, e.g. BENCH-01")
    category: BenchmarkCategory = Field(..., description="Category of bug")
    title: str = Field(..., description="Short descriptive title of the issue")
    description: str = Field(..., description="Bug report or reproduction instructions")
    file_path: str = Field(..., description="Relative file path in repository, e.g. calc.py")
    buggy_code: str = Field(..., description="Initial buggy source code")
    test_code: str = Field(..., description="Pytest suite asserting expected behavior")
    search_block: str = Field(..., description="Exact code to replace for canonical fix")
    replace_block: str = Field(..., description="Replacement code that resolves the bug")


class BenchmarkResult(BaseModel):
    """Outcome of running the repair pipeline against a benchmark issue."""

    issue_id: str
    category: BenchmarkCategory
    title: str
    resolved: bool = False
    pass_at_1: bool = False
    iterations: int = 1
    duration_ms: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    error: str | None = None


class BenchmarkSuiteSummary(BaseModel):
    """Aggregated metrics across the full benchmark execution suite."""

    total_issues: int
    resolved_count: int
    resolve_rate_percent: float
    pass_at_1_count: int
    pass_at_1_rate_percent: float
    total_cost_usd: float
    avg_cost_usd: float
    total_duration_ms: int
    avg_duration_ms: float
    category_breakdown: dict[str, dict[str, float | int]] = Field(default_factory=dict)
