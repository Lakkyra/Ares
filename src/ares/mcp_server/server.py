"""FastMCP server definition and programmatic tool dispatcher for Ares."""

from typing import Any

from mcp.server.mcpserver import MCPServer

from ares.mcp_server.tools import (
    apply_search_replace,
    list_directory,
    read_file_context,
    search_codebase,
)


def create_mcp_server(name: str = "ares-code-tools") -> MCPServer:
    """Instantiate and register tools with the MCP Server."""
    server = MCPServer(name)

    @server.tool(
        name="read_file_context",
        description="Read source file content with line numbers and slice boundaries.",
    )
    def tool_read_file(
        file_path: str,
        start_line: int | None = None,
        end_line: int | None = None,
        repo_root: str = ".",
    ) -> str:
        res = read_file_context(file_path, start_line, end_line, repo_root)
        if res.error:
            return f"Error: {res.error}"
        return res.content

    @server.tool(
        name="apply_search_replace",
        description="Apply an exact search-and-replace patch to a file. Fails on ambiguous matches.",
    )
    def tool_apply_patch(
        file_path: str,
        search_block: str,
        replace_block: str,
        repo_root: str = ".",
    ) -> str:
        res = apply_search_replace(file_path, search_block, replace_block, repo_root)
        if not res.success:
            return f"Error: {res.error}"
        note = f"\nNote: {res.error}" if res.error else ""
        return f"Patch applied successfully.\nUnified Diff:\n{res.diff}{note}"

    @server.tool(
        name="list_directory", description="List directory contents, filtering noise directories."
    )
    def tool_list_dir(
        path: str = ".",
        recursive: bool = False,
        max_depth: int = 3,
        repo_root: str = ".",
    ) -> str:
        res = list_directory(path, recursive, max_depth, repo_root)
        if res.error:
            return f"Error: {res.error}"
        lines = [
            f"{'[DIR] ' if e.is_dir else '[FILE]'} {e.path} ({e.size_bytes or 0} B)"
            for e in res.entries
        ]
        return "\n".join(lines) if lines else "Directory is empty."

    @server.tool(
        name="search_codebase", description="Search for text matches across codebase files."
    )
    def tool_search(
        query: str,
        path: str = ".",
        file_pattern: str | None = None,
        max_results: int = 50,
        case_sensitive: bool = True,
        repo_root: str = ".",
    ) -> str:
        res = search_codebase(query, path, file_pattern, max_results, case_sensitive, repo_root)
        if res.error:
            return f"Error: {res.error}"
        if not res.matches:
            return f"No matches found for query '{query}'."
        lines = [f"{m.file_path}:{m.line_number}: {m.line_content}" for m in res.matches]
        return "\n".join(lines)

    return server


# Global default instance
mcp_server = create_mcp_server()


async def execute_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
    server: MCPServer | None = None,
) -> Any:
    """Execute an MCP tool programmatically and return the result content."""
    srv = server or mcp_server
    result = await srv.call_tool(tool_name, arguments)
    return result


async def run_server_stdio() -> None:
    """Run the MCP server over standard input/output transport."""
    await mcp_server.run_stdio_async()
