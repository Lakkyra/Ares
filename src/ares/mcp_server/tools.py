"""Core MCP tool implementations for file operations and code repair."""

import ast
import difflib
import fnmatch
import os
from pathlib import Path

from pydantic import BaseModel, Field

from ares.mcp_server.security import PathTraversalError, validate_path

IGNORED_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".tox",
    "dist",
    "build",
}


# --- Pydantic Data Models ---


class ReadFileResult(BaseModel):
    """Result of read_file_context."""

    file_path: str
    content: str
    start_line: int
    end_line: int
    total_lines: int
    size_bytes: int
    error: str | None = None


class PatchResult(BaseModel):
    """Result of apply_search_replace."""

    file_path: str
    success: bool
    diff: str
    syntax_valid: bool
    error: str | None = None


class DirectoryEntry(BaseModel):
    """Single file or folder entry in directory listing."""

    name: str
    path: str
    is_dir: bool
    size_bytes: int | None = None


class DirectoryListResult(BaseModel):
    """Result of list_directory."""

    root_path: str
    entries: list[DirectoryEntry] = Field(default_factory=list)
    total_entries: int
    error: str | None = None


class SearchMatch(BaseModel):
    """Single line match from codebase search."""

    file_path: str
    line_number: int
    line_content: str


class SearchResult(BaseModel):
    """Result of search_codebase."""

    query: str
    matches: list[SearchMatch] = Field(default_factory=list)
    total_matches: int
    error: str | None = None


# --- Exceptions ---


class ToolExecutionError(Exception):
    """Base error for tool execution failures."""


class MatchNotFoundError(ToolExecutionError):
    """Raised when search block is not found in file."""


class AmbiguousMatchError(ToolExecutionError):
    """Raised when search block matches multiple locations."""


# --- Core Tool Functions ---


def read_file_context(
    file_path: str,
    start_line: int | None = None,
    end_line: int | None = None,
    repo_root: str | Path = ".",
) -> ReadFileResult:
    """Read source file contents with 1-indexed line numbers and slice window.

    Args:
        file_path: Path to the target file (relative or absolute within repo).
        start_line: 1-indexed starting line (inclusive). Defaults to 1.
        end_line: 1-indexed ending line (inclusive). Defaults to total lines.
        repo_root: Repository root directory for sandbox boundaries.

    Returns:
        ReadFileResult containing formatted line-numbered content or error.
    """
    try:
        target = validate_path(file_path, repo_root)
    except PathTraversalError as e:
        return ReadFileResult(
            file_path=str(file_path),
            content="",
            start_line=0,
            end_line=0,
            total_lines=0,
            size_bytes=0,
            error=str(e),
        )

    if not target.exists():
        return ReadFileResult(
            file_path=str(file_path),
            content="",
            start_line=0,
            end_line=0,
            total_lines=0,
            size_bytes=0,
            error=f"File not found: '{file_path}'",
        )

    if target.is_dir():
        return ReadFileResult(
            file_path=str(file_path),
            content="",
            start_line=0,
            end_line=0,
            total_lines=0,
            size_bytes=0,
            error=f"Target path is a directory, not a file: '{file_path}'",
        )

    # Detect binary files
    try:
        raw_bytes = target.read_bytes()
        if b"\x00" in raw_bytes[:1024]:
            return ReadFileResult(
                file_path=str(file_path),
                content="",
                start_line=0,
                end_line=0,
                total_lines=0,
                size_bytes=len(raw_bytes),
                error=f"Cannot read binary file: '{file_path}'",
            )
        text = raw_bytes.decode("utf-8", errors="replace")
    except Exception as e:
        return ReadFileResult(
            file_path=str(file_path),
            content="",
            start_line=0,
            end_line=0,
            total_lines=0,
            size_bytes=0,
            error=f"Failed to read file: {e}",
        )

    lines = text.splitlines()
    total_lines = len(lines)

    if total_lines == 0:
        return ReadFileResult(
            file_path=str(file_path),
            content="",
            start_line=0,
            end_line=0,
            total_lines=0,
            size_bytes=0,
        )

    s_line = 1 if start_line is None else max(1, start_line)
    e_line = total_lines if end_line is None else min(total_lines, end_line)

    if s_line > e_line:
        return ReadFileResult(
            file_path=str(file_path),
            content="",
            start_line=s_line,
            end_line=e_line,
            total_lines=total_lines,
            size_bytes=len(raw_bytes),
            error=f"Invalid line range: start_line ({s_line}) > end_line ({e_line})",
        )

    selected_lines = lines[s_line - 1 : e_line]
    pad_width = len(str(e_line))
    formatted_lines = [
        f"{idx:>{pad_width}} | {line}" for idx, line in enumerate(selected_lines, start=s_line)
    ]
    formatted_content = "\n".join(formatted_lines)

    return ReadFileResult(
        file_path=str(file_path),
        content=formatted_content,
        start_line=s_line,
        end_line=e_line,
        total_lines=total_lines,
        size_bytes=len(raw_bytes),
    )


def apply_search_replace(
    file_path: str,
    search_block: str,
    replace_block: str,
    repo_root: str | Path = ".",
) -> PatchResult:
    """Apply an exact whitespace-sensitive search-and-replace edit to a file.

    Args:
        file_path: Path to the target file to modify.
        search_block: Exact text block to locate (must match whitespace exactly).
        replace_block: Replacement text block.
        repo_root: Repository root directory for sandbox boundaries.

    Returns:
        PatchResult detailing whether the patch succeeded, the diff, and syntax validity.
    """
    try:
        target = validate_path(file_path, repo_root)
    except PathTraversalError as e:
        return PatchResult(
            file_path=str(file_path),
            success=False,
            diff="",
            syntax_valid=False,
            error=str(e),
        )

    if not target.exists():
        return PatchResult(
            file_path=str(file_path),
            success=False,
            diff="",
            syntax_valid=False,
            error=f"File not found: '{file_path}'",
        )

    try:
        original_content = target.read_text(encoding="utf-8")
    except Exception as e:
        return PatchResult(
            file_path=str(file_path),
            success=False,
            diff="",
            syntax_valid=False,
            error=f"Error reading file '{file_path}': {e}",
        )

    # Normalize newlines in memory to match file format
    # Check exact occurrences
    matches_count = original_content.count(search_block)

    if matches_count == 0:
        # Check if newline mismatch is the issue
        normalized_orig = original_content.replace("\r\n", "\n")
        normalized_search = search_block.replace("\r\n", "\n")
        if normalized_search in normalized_orig:
            # Reconstruct with matching line endings
            pass

        return PatchResult(
            file_path=str(file_path),
            success=False,
            diff="",
            syntax_valid=False,
            error=(
                f"Search block not found in '{file_path}'. "
                "Ensure exact character and whitespace matching including indentation."
            ),
        )

    if matches_count > 1:
        return PatchResult(
            file_path=str(file_path),
            success=False,
            diff="",
            syntax_valid=False,
            error=(
                f"Search block is ambiguous in '{file_path}': found {matches_count} occurrences. "
                "Provide more surrounding lines to create a unique search block."
            ),
        )

    # Apply replacement
    new_content = original_content.replace(search_block, replace_block, 1)

    # Validate Python syntax if target is a Python file
    syntax_valid = True
    syntax_error_msg = None
    if target.suffix == ".py":
        try:
            ast.parse(new_content, filename=str(target))
        except SyntaxError as e:
            syntax_valid = False
            syntax_error_msg = f"Python SyntaxError on line {e.lineno}: {e.msg}"

    # Generate unified diff
    root = Path(repo_root).resolve()
    try:
        rel_path = target.relative_to(root)
    except ValueError:
        rel_path = target

    orig_lines = original_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
        )
    )
    diff_str = "".join(diff_lines)

    # Write patched content to file
    try:
        target.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return PatchResult(
            file_path=str(file_path),
            success=False,
            diff="",
            syntax_valid=syntax_valid,
            error=f"Failed writing modified content to '{file_path}': {e}",
        )

    error_note = syntax_error_msg if not syntax_valid else None
    return PatchResult(
        file_path=str(file_path),
        success=True,
        diff=diff_str,
        syntax_valid=syntax_valid,
        error=error_note,
    )


def list_directory(
    path: str = ".",
    recursive: bool = False,
    max_depth: int = 3,
    repo_root: str | Path = ".",
) -> DirectoryListResult:
    """List directory contents excluding ignored directories and files.

    Args:
        path: Path to directory to list.
        recursive: Whether to list subdirectories recursively.
        max_depth: Maximum recursion depth when recursive is True.
        repo_root: Repository root boundary.

    Returns:
        DirectoryListResult with structured file/folder entries.
    """
    try:
        target = validate_path(path, repo_root)
    except PathTraversalError as e:
        return DirectoryListResult(root_path=str(path), total_entries=0, error=str(e))

    if not target.exists():
        return DirectoryListResult(
            root_path=str(path), total_entries=0, error=f"Path not found: '{path}'"
        )

    if not target.is_dir():
        return DirectoryListResult(
            root_path=str(path),
            total_entries=0,
            error=f"Path is not a directory: '{path}'",
        )

    entries: list[DirectoryEntry] = []
    root = Path(repo_root).resolve()

    def scan_dir(curr_dir: Path, current_depth: int) -> None:
        if current_depth > max_depth:
            return
        try:
            items = sorted(curr_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return

        for item in items:
            if item.name in IGNORED_DIRS:
                continue

            try:
                rel = item.relative_to(root)
            except ValueError:
                rel = item

            is_directory = item.is_dir()
            size = item.stat().st_size if not is_directory else None

            entries.append(
                DirectoryEntry(
                    name=item.name,
                    path=str(rel).replace("\\", "/"),
                    is_dir=is_directory,
                    size_bytes=size,
                )
            )

            if is_directory and recursive and current_depth < max_depth:
                scan_dir(item, current_depth + 1)

    scan_dir(target, 1)

    return DirectoryListResult(
        root_path=str(path),
        entries=entries,
        total_entries=len(entries),
    )


def search_codebase(
    query: str,
    path: str = ".",
    file_pattern: str | None = None,
    max_results: int = 50,
    case_sensitive: bool = True,
    repo_root: str | Path = ".",
) -> SearchResult:
    """Search for string occurrences across files in the codebase.

    Args:
        query: String or literal phrase to find.
        path: Starting path for search.
        file_pattern: Optional glob pattern (e.g. '*.py', '*.ts').
        max_results: Max number of matches to return.
        case_sensitive: Whether to perform case-sensitive search.
        repo_root: Repository root boundary.

    Returns:
        SearchResult containing line matches.
    """
    try:
        start_dir = validate_path(path, repo_root)
    except PathTraversalError as e:
        return SearchResult(query=query, total_matches=0, error=str(e))

    if not start_dir.exists():
        return SearchResult(query=query, total_matches=0, error=f"Path not found: '{path}'")

    matches: list[SearchMatch] = []
    root = Path(repo_root).resolve()
    query_target = query if case_sensitive else query.lower()

    for dirpath, dirnames, filenames in os.walk(start_dir):
        # Exclude ignored dirs in-place
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]

        for fname in filenames:
            if file_pattern and not fnmatch.fnmatch(fname, file_pattern):
                continue

            file_path = Path(dirpath) / fname
            try:
                rel_path = str(file_path.relative_to(root)).replace("\\", "/")
            except ValueError:
                rel_path = str(file_path).replace("\\", "/")

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for line_idx, line in enumerate(content.splitlines(), start=1):
                check_line = line if case_sensitive else line.lower()
                if query_target in check_line:
                    matches.append(
                        SearchMatch(
                            file_path=rel_path,
                            line_number=line_idx,
                            line_content=line.strip(),
                        )
                    )
                    if len(matches) >= max_results:
                        return SearchResult(
                            query=query,
                            matches=matches,
                            total_matches=len(matches),
                        )

    return SearchResult(
        query=query,
        matches=matches,
        total_matches=len(matches),
    )
