"""Comprehensive unit tests for Ares MCP tools and server."""

from pathlib import Path

import pytest

from ares.mcp_server.security import PathTraversalError, validate_path
from ares.mcp_server.server import create_mcp_server, execute_mcp_tool
from ares.mcp_server.tools import (
    apply_search_replace,
    list_directory,
    read_file_context,
    search_codebase,
)


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Set up a mock repository with files for tool testing."""
    repo = tmp_path / "mock_repo"
    repo.mkdir()

    # Create dummy files
    calc_py = repo / "calculator.py"
    calc_py.write_text(
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n\n"
        "def divide(a: int, b: int) -> float:\n"
        "    # Bug here: no zero check\n"
        "    return a / b\n",
        encoding="utf-8",
    )

    utils_py = repo / "utils.py"
    utils_py.write_text(
        "# Utility functions\n"
        "def helper():\n"
        "    pass\n"
        "def duplicate():\n"
        "    return 1\n"
        "def duplicate():\n"
        "    return 2\n",
        encoding="utf-8",
    )

    sub_dir = repo / "subpkg"
    sub_dir.mkdir()
    (sub_dir / "module.py").write_text("VALUE = 42\n", encoding="utf-8")

    # Noise dirs that should be ignored
    git_dir = repo / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    venv_dir = repo / ".venv"
    venv_dir.mkdir()
    (venv_dir / "pyvenv.cfg").write_text("home = ...\n", encoding="utf-8")

    return repo


# --- Security & Path Traversal Tests ---


def test_validate_path_valid(temp_repo: Path) -> None:
    """Valid relative path resolves correctly within repo."""
    target = validate_path("calculator.py", temp_repo)
    assert target == (temp_repo / "calculator.py").resolve()


def test_validate_path_traversal_relative(temp_repo: Path) -> None:
    """Path escaping repo root via ../ is rejected."""
    with pytest.raises(PathTraversalError):
        validate_path("../../outside.txt", temp_repo)


def test_validate_path_traversal_absolute(temp_repo: Path) -> None:
    """Absolute path outside repo root is rejected."""
    outside = (
        Path("C:/Windows/System32/drivers/etc/hosts")
        if Path("C:/").exists()
        else Path("/etc/passwd")
    )
    with pytest.raises(PathTraversalError):
        validate_path(str(outside), temp_repo)


# --- read_file_context Tests ---


def test_read_file_context_full(temp_repo: Path) -> None:
    """Read entire file context with formatted line numbers."""
    res = read_file_context("calculator.py", repo_root=temp_repo)
    assert res.error is None
    assert res.total_lines == 6
    assert res.start_line == 1
    assert res.end_line == 6
    assert "1 | def add(a: int, b: int) -> int:" in res.content
    assert "6 |     return a / b" in res.content


def test_read_file_context_slice(temp_repo: Path) -> None:
    """Read specific line slice."""
    res = read_file_context("calculator.py", start_line=3, end_line=5, repo_root=temp_repo)
    assert res.error is None
    assert res.start_line == 3
    assert res.end_line == 5
    assert "def add" not in res.content
    assert "4 | def divide(a: int, b: int) -> float:" in res.content


def test_read_file_context_invalid_range(temp_repo: Path) -> None:
    """Start line > end line returns error."""
    res = read_file_context("calculator.py", start_line=5, end_line=2, repo_root=temp_repo)
    assert res.error is not None
    assert "Invalid line range" in res.error


def test_read_file_context_nonexistent(temp_repo: Path) -> None:
    """Non-existent file returns error gracefully."""
    res = read_file_context("missing.py", repo_root=temp_repo)
    assert res.error is not None
    assert "File not found" in res.error


def test_read_file_context_path_traversal(temp_repo: Path) -> None:
    """Path traversal attempt returns security error."""
    res = read_file_context("../secret.env", repo_root=temp_repo)
    assert res.error is not None
    assert "escapes repository root" in res.error


def test_read_file_context_binary(temp_repo: Path) -> None:
    """Binary file detection blocks raw reading."""
    bin_file = temp_repo / "image.bin"
    bin_file.write_bytes(b"\x7fELF\x00\x00\x01\x01")
    res = read_file_context("image.bin", repo_root=temp_repo)
    assert res.error is not None
    assert "Cannot read binary file" in res.error


# --- apply_search_replace Tests ---


def test_apply_search_replace_success(temp_repo: Path) -> None:
    """Apply successful single search-and-replace patch."""
    search = "def divide(a: int, b: int) -> float:\n    # Bug here: no zero check\n    return a / b"
    replace = (
        "def divide(a: int, b: int) -> float:\n"
        "    if b == 0:\n"
        "        raise ZeroDivisionError('division by zero')\n"
        "    return a / b"
    )
    res = apply_search_replace("calculator.py", search, replace, repo_root=temp_repo)
    assert res.success is True
    assert res.error is None
    assert res.syntax_valid is True
    assert "-    # Bug here: no zero check" in res.diff
    assert "+        raise ZeroDivisionError('division by zero')" in res.diff

    # Verify content on disk
    updated = (temp_repo / "calculator.py").read_text(encoding="utf-8")
    assert "if b == 0:" in updated


def test_apply_search_replace_not_found(temp_repo: Path) -> None:
    """Fails when search block does not exist."""
    res = apply_search_replace(
        "calculator.py",
        "non_existent_code_block()",
        "replacement()",
        repo_root=temp_repo,
    )
    assert res.success is False
    assert "Search block not found" in res.error  # type: ignore


def test_apply_search_replace_ambiguous(temp_repo: Path) -> None:
    """Fails when search block appears multiple times in file."""
    res = apply_search_replace(
        "utils.py",
        "def duplicate():",
        "def unique():",
        repo_root=temp_repo,
    )
    assert res.success is False
    assert "Search block is ambiguous" in res.error  # type: ignore
    assert "found 2 occurrences" in res.error  # type: ignore


def test_apply_search_replace_syntax_error_warning(temp_repo: Path) -> None:
    """Detects invalid Python syntax introduced by patch."""
    search = "return a + b"
    replace = "return a + + %%% syntax error"
    res = apply_search_replace("calculator.py", search, replace, repo_root=temp_repo)
    assert res.success is True
    assert res.syntax_valid is False
    assert "Python SyntaxError" in res.error  # type: ignore


# --- list_directory Tests ---


def test_list_directory_shallow(temp_repo: Path) -> None:
    """List directory excluding noise folders (.git, .venv)."""
    res = list_directory(".", recursive=False, repo_root=temp_repo)
    assert res.error is None
    names = [e.name for e in res.entries]
    assert "calculator.py" in names
    assert "utils.py" in names
    assert "subpkg" in names
    assert ".git" not in names
    assert ".venv" not in names


def test_list_directory_recursive(temp_repo: Path) -> None:
    """List directory recursively."""
    res = list_directory(".", recursive=True, max_depth=3, repo_root=temp_repo)
    assert res.error is None
    paths = [e.path for e in res.entries]
    assert "calculator.py" in paths
    assert "subpkg/module.py" in paths


# --- search_codebase Tests ---


def test_search_codebase_literal(temp_repo: Path) -> None:
    """Search for string occurrences."""
    res = search_codebase("def divide", repo_root=temp_repo)
    assert res.error is None
    assert res.total_matches == 1
    assert res.matches[0].file_path == "calculator.py"
    assert res.matches[0].line_number == 4


def test_search_codebase_with_file_pattern(temp_repo: Path) -> None:
    """Filter search by file pattern."""
    res = search_codebase("VALUE", file_pattern="*.py", repo_root=temp_repo)
    assert res.error is None
    assert res.total_matches == 1
    assert "module.py" in res.matches[0].file_path


def test_search_codebase_no_match(temp_repo: Path) -> None:
    """Search returns 0 matches for non-existent term."""
    res = search_codebase("this_string_does_not_exist", repo_root=temp_repo)
    assert res.error is None
    assert res.total_matches == 0


# --- MCP Server Protocol Integration Tests ---


@pytest.mark.asyncio
async def test_mcp_server_tool_registration() -> None:
    """Verify MCP server registers all 4 tools."""
    server = create_mcp_server("test-server")
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    assert "read_file_context" in tool_names
    assert "apply_search_replace" in tool_names
    assert "list_directory" in tool_names
    assert "search_codebase" in tool_names


@pytest.mark.asyncio
async def test_execute_mcp_tool_end_to_end(temp_repo: Path) -> None:
    """Verify executing MCP tools via server.call_tool."""
    server = create_mcp_server("test-server")

    # Read file tool call
    res = await execute_mcp_tool(
        "read_file_context",
        {"file_path": "calculator.py", "repo_root": str(temp_repo)},
        server=server,
    )
    assert res.content[0].type == "text"
    assert "def add" in res.content[0].text

    # Search replace tool call
    patch_res = await execute_mcp_tool(
        "apply_search_replace",
        {
            "file_path": "calculator.py",
            "search_block": "return a + b",
            "replace_block": "return (a + b)",
            "repo_root": str(temp_repo),
        },
        server=server,
    )
    assert "Patch applied successfully" in patch_res.content[0].text


# --- Additional Edge Case Tests for >90% Coverage ---


def test_read_file_context_directory(temp_repo: Path) -> None:
    """Reading a directory as a file returns an informative error."""
    res = read_file_context("subpkg", repo_root=temp_repo)
    assert res.error is not None
    assert "is a directory" in res.error


def test_read_file_context_empty_file(temp_repo: Path) -> None:
    """Reading an empty file succeeds with 0 lines."""
    empty = temp_repo / "empty.txt"
    empty.write_text("", encoding="utf-8")
    res = read_file_context("empty.txt", repo_root=temp_repo)
    assert res.error is None
    assert res.total_lines == 0
    assert res.content == ""


def test_apply_search_replace_on_directory(temp_repo: Path) -> None:
    """Patching a directory fails gracefully."""
    res = apply_search_replace("subpkg", "search", "replace", repo_root=temp_repo)
    assert res.success is False
    assert res.error is not None


def test_apply_search_replace_path_traversal(temp_repo: Path) -> None:
    """Path traversal attempt in search_replace returns security error."""
    res = apply_search_replace("../outside.py", "a", "b", repo_root=temp_repo)
    assert res.success is False
    assert "escapes repository root" in res.error  # type: ignore


def test_list_directory_on_file(temp_repo: Path) -> None:
    """Listing a file path returns an error."""
    res = list_directory("calculator.py", repo_root=temp_repo)
    assert res.error is not None
    assert "not a directory" in res.error


def test_list_directory_not_found(temp_repo: Path) -> None:
    """Listing a non-existent path returns error."""
    res = list_directory("non_existent_folder", repo_root=temp_repo)
    assert res.error is not None
    assert "Path not found" in res.error


def test_list_directory_path_traversal(temp_repo: Path) -> None:
    """Listing outside repo root is blocked."""
    res = list_directory("../../outside", repo_root=temp_repo)
    assert res.error is not None
    assert "escapes repository root" in res.error


def test_search_codebase_not_found_dir(temp_repo: Path) -> None:
    """Searching in non-existent directory returns error."""
    res = search_codebase("foo", path="missing_dir", repo_root=temp_repo)
    assert res.error is not None
    assert "Path not found" in res.error


def test_search_codebase_path_traversal(temp_repo: Path) -> None:
    """Searching outside repo root is blocked."""
    res = search_codebase("foo", path="../../outside", repo_root=temp_repo)
    assert res.error is not None
    assert "escapes repository root" in res.error


def test_search_codebase_case_insensitive(temp_repo: Path) -> None:
    """Case-insensitive search finds lower and upper matches."""
    res = search_codebase("value", case_sensitive=False, repo_root=temp_repo)
    assert res.error is None
    assert res.total_matches == 1
    assert "VALUE = 42" in res.matches[0].line_content


@pytest.mark.asyncio
async def test_execute_all_tools_via_mcp_server(temp_repo: Path) -> None:
    """Verify list_directory and search_codebase via MCP Server."""
    server = create_mcp_server("test-server")

    # List dir via MCP
    ld_res = await execute_mcp_tool(
        "list_directory",
        {"path": ".", "recursive": True, "repo_root": str(temp_repo)},
        server=server,
    )
    assert "[FILE] calculator.py" in ld_res.content[0].text

    # Search codebase via MCP
    sc_res = await execute_mcp_tool(
        "search_codebase",
        {"query": "def add", "repo_root": str(temp_repo)},
        server=server,
    )
    assert "calculator.py:1: def add" in sc_res.content[0].text

    # Error handling via MCP
    err_res = await execute_mcp_tool(
        "read_file_context",
        {"file_path": "nonexistent.py", "repo_root": str(temp_repo)},
        server=server,
    )
    assert "Error: File not found" in err_res.content[0].text
