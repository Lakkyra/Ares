"""Integration and security verification tests for Docker Sandbox."""

from pathlib import Path

import pytest

from ares.sandbox.manager import DockerSandboxManager


@pytest.fixture
def sandbox() -> DockerSandboxManager:
    """Create sandbox manager pointing to local image."""
    mgr = DockerSandboxManager(image="ares-sandbox:latest", timeout_seconds=5)
    if not mgr.is_available():
        pytest.skip("Docker daemon is not available.")
    return mgr


def test_sandbox_network_isolation(sandbox: DockerSandboxManager, tmp_path: Path) -> None:
    """Verify container has NO network access (--network=none)."""
    # Attempt outbound HTTP request to public DNS
    cmd = "python -c \"import urllib.request; urllib.request.urlopen('http://1.1.1.1', timeout=2)\""
    res = sandbox.run_command(cmd, repo_path=tmp_path)
    assert res.exit_code != 0
    assert "Network is unreachable" in res.stderr or "urllib.error.URLError" in res.stderr
    assert res.network_blocked is True


def test_sandbox_timeout_enforcement(sandbox: DockerSandboxManager, tmp_path: Path) -> None:
    """Verify runaway processes are terminated when exceeding timeout."""
    # Process sleeps for 20 seconds, with sandbox timeout set to 2 seconds
    cmd = 'python -c "import time; time.sleep(20)"'
    res = sandbox.run_command(cmd, repo_path=tmp_path, timeout_seconds=2)
    assert res.timed_out is True
    assert res.exit_code == 124
    assert res.duration_ms >= 1800
    assert res.duration_ms < 6000


def test_sandbox_filesystem_isolation(sandbox: DockerSandboxManager, tmp_path: Path) -> None:
    """Verify container modifications do NOT alter host filesystem."""
    test_file = tmp_path / "host_file.txt"
    test_file.write_text("ORIGINAL_CONTENT", encoding="utf-8")

    # Command overwrites host_file.txt inside container
    cmd = "echo 'MUTATED_BY_CONTAINER' > host_file.txt"
    res = sandbox.run_command(cmd, repo_path=tmp_path)
    assert res.exit_code == 0

    # Host file must remain unmodified
    assert test_file.read_text(encoding="utf-8") == "ORIGINAL_CONTENT"


def test_sandbox_non_root_user(sandbox: DockerSandboxManager, tmp_path: Path) -> None:
    """Verify execution runs as unprivileged sandboxuser (UID 1000)."""
    res = sandbox.run_command("whoami && id -u", repo_path=tmp_path)
    assert res.exit_code == 0
    lines = res.stdout.strip().splitlines()
    assert "sandboxuser" in lines[0]
    assert "1000" in lines[1]


def test_sandbox_run_pytest(sandbox: DockerSandboxManager, tmp_path: Path) -> None:
    """Verify run_pytest runs successfully inside the container."""
    test_file = tmp_path / "test_sample.py"
    test_file.write_text(
        "def test_pass():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )
    res = sandbox.run_pytest(repo_path=tmp_path)
    assert res.exit_code == 0
    assert "1 passed" in res.stdout
