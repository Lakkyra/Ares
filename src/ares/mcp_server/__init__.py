"""Ares Model Context Protocol (MCP) server and tools."""

from ares.mcp_server.security import PathTraversalError, SecurityError, validate_path
from ares.mcp_server.server import (
    create_mcp_server,
    execute_mcp_tool,
    mcp_server,
    run_server_stdio,
)
from ares.mcp_server.tools import (
    AmbiguousMatchError,
    DirectoryEntry,
    DirectoryListResult,
    MatchNotFoundError,
    PatchResult,
    ReadFileResult,
    SearchMatch,
    SearchResult,
    ToolExecutionError,
    apply_search_replace,
    list_directory,
    read_file_context,
    run_sandbox_pytest,
    search_codebase,
)

__all__ = [
    "PathTraversalError",
    "SecurityError",
    "validate_path",
    "create_mcp_server",
    "execute_mcp_tool",
    "mcp_server",
    "run_server_stdio",
    "ToolExecutionError",
    "MatchNotFoundError",
    "AmbiguousMatchError",
    "ReadFileResult",
    "PatchResult",
    "DirectoryEntry",
    "DirectoryListResult",
    "SearchMatch",
    "SearchResult",
    "read_file_context",
    "apply_search_replace",
    "list_directory",
    "search_codebase",
    "run_sandbox_pytest",
]
