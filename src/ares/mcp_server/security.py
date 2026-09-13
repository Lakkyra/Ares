"""Security and path traversal protection for Ares MCP tools."""

from pathlib import Path


class SecurityError(Exception):
    """Base exception for security boundary violations."""


class PathTraversalError(SecurityError):
    """Raised when a requested path escapes the allowed repository root."""


def validate_path(path: str | Path, repo_root: str | Path = ".") -> Path:
    """Validate that a target path resides strictly within the repository root.

    Args:
        path: The relative or absolute file/directory path requested.
        repo_root: The root directory boundary of the repository.

    Returns:
        The resolved, canonical absolute Path.

    Raises:
        PathTraversalError: If the target path escapes repo_root.
    """
    root = Path(repo_root).resolve()
    target = (root / Path(path)).resolve() if not Path(path).is_absolute() else Path(path).resolve()

    try:
        target.relative_to(root)
    except ValueError as err:
        raise PathTraversalError(
            f"Access denied: Path '{path}' escapes repository root '{root}'"
        ) from err

    return target
