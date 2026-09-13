"""Data models for Docker sandbox execution."""

from pydantic import BaseModel, Field


class SandboxExecutionResult(BaseModel):
    """Result of code or test execution inside an isolated Docker sandbox."""

    stdout: str = Field(default="", description="Captured standard output")
    stderr: str = Field(default="", description="Captured standard error")
    exit_code: int = Field(default=0, description="Process exit code")
    duration_ms: int = Field(default=0, description="Execution duration in milliseconds")
    timed_out: bool = Field(default=False, description="Whether execution exceeded timeout")
    network_blocked: bool = Field(default=True, description="Confirms network isolation")
    error: str | None = Field(default=None, description="Sandbox daemon error if any")
