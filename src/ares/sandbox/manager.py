"""Docker sandbox manager for isolated, resource-constrained test execution."""

import contextlib
import io
import tarfile
import time
from pathlib import Path
from typing import Any

import docker
from docker.errors import DockerException

from ares.config.settings import settings
from ares.sandbox.models import SandboxExecutionResult

IGNORED_ARCHIVE_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def create_archive_stream(source_dir: Path) -> io.BytesIO:
    """Pack directory contents into an in-memory tar stream for container injection."""
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as tar:
        for item in source_dir.iterdir():
            if item.name in IGNORED_ARCHIVE_DIRS:
                continue
            tar.add(str(item), arcname=item.name)
    stream.seek(0)
    return stream


class DockerSandboxManager:
    """Manages ephemeral, network-isolated Docker containers for code repair testing."""

    def __init__(
        self,
        image: str | None = None,
        timeout_seconds: int | None = None,
        memory_limit: str | None = None,
        cpu_limit: float | None = None,
    ) -> None:
        self.image = image or settings.sandbox_image
        self.timeout_seconds = timeout_seconds or settings.sandbox_timeout_seconds
        self.memory_limit = memory_limit or settings.sandbox_memory_limit
        self.cpu_limit = cpu_limit or settings.sandbox_cpu_limit
        self._client: Any = None

    def get_client(self) -> Any:
        """Lazily initialize and return the Docker client."""
        if self._client is None:
            if docker is None:
                raise RuntimeError("docker package is not installed.")
            try:
                self._client = docker.from_env()
            except DockerException as e:
                raise RuntimeError(f"Cannot connect to Docker daemon: {e}") from e
        return self._client

    def is_available(self) -> bool:
        """Check if Docker daemon is accessible and responding."""
        try:
            client = self.get_client()
            return bool(client.ping())
        except Exception:
            return False

    def run_command(
        self,
        command: list[str] | str,
        repo_path: str | Path = ".",
        timeout_seconds: int | None = None,
    ) -> SandboxExecutionResult:
        """Run an arbitrary command inside an ephemeral air-gapped container.

        Args:
            command: Shell command string or list of argument tokens.
            repo_path: Local repository to package and inject into /workspace.
            timeout_seconds: Maximum allowed runtime before SIGKILL.

        Returns:
            SandboxExecutionResult with captured stdout, stderr, and timings.
        """
        timeout = timeout_seconds or self.timeout_seconds
        client = self.get_client()
        target_dir = Path(repo_path).resolve()

        container = None
        start_time = time.perf_counter()
        timed_out = False

        cmd_tokens = ["/bin/bash", "-c", command] if isinstance(command, str) else command

        try:
            # Create unstarted container with strict isolation
            container = client.containers.create(
                image=self.image,
                command=cmd_tokens,
                network_mode="none",
                mem_limit=self.memory_limit,
                nano_cpus=int(self.cpu_limit * 1_000_000_000),
                user="sandboxuser",
                working_dir="/workspace",
            )

            # Stream files into container /workspace if directory exists and has files
            if target_dir.exists() and any(target_dir.iterdir()):
                tar_stream = create_archive_stream(target_dir)
                container.put_archive("/workspace", tar_stream)

            container.start()

            # Wait for completion with timeout
            try:
                wait_res = container.wait(timeout=timeout)
                exit_code = wait_res.get("StatusCode", 0)
            except Exception:
                # Timeout expired
                timed_out = True
                with contextlib.suppress(Exception):
                    container.kill()
                exit_code = 124

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

            if timed_out:
                stderr += f"\n[Ares] Execution timed out after {timeout} seconds."

            return SandboxExecutionResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_ms=elapsed_ms,
                timed_out=timed_out,
                network_blocked=True,
            )

        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return SandboxExecutionResult(
                stdout="",
                stderr=str(e),
                exit_code=1,
                duration_ms=elapsed_ms,
                timed_out=False,
                error=f"Container execution error: {e}",
            )
        finally:
            if container is not None:
                with contextlib.suppress(Exception):
                    container.remove(force=True)

    def run_pytest(
        self,
        test_target: str = "",
        repo_path: str | Path = ".",
        timeout_seconds: int | None = None,
    ) -> SandboxExecutionResult:
        """Run pytest inside the sandbox container."""
        cmd = f"pytest {test_target}".strip() if test_target else "pytest"
        return self.run_command(command=cmd, repo_path=repo_path, timeout_seconds=timeout_seconds)


default_sandbox = DockerSandboxManager()
