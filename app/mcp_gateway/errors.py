from __future__ import annotations


class McpBackendError(RuntimeError):
    """A safe, credential-free error suitable for returning through MCP."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class McpInputError(ValueError):
    """A caller-correctable MCP input error."""
