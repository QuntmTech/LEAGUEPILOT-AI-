from __future__ import annotations


class McpBackendError(RuntimeError):
    """A safe, credential-free error suitable for returning through MCP."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class McpInputError(ValueError):
    """A caller-correctable MCP input error."""


class McpScopeError(PermissionError):
    """The caller authenticated, but its token lacks the scope this tool needs.

    RFC 6750 models this as HTTP 403 `insufficient_scope`. That status can only be sent
    by the transport-level middleware, which runs before JSON-RPC dispatch and therefore
    cannot know which tool was invoked. Per-tool denials must surface as MCP tool errors
    instead, so this exception carries the same code and status explicitly and the
    message names them — a client can act on `insufficient_scope` either way.
    """

    def __init__(self, required_scope: str, *, granted: tuple[str, ...] = ()) -> None:
        self.required_scope = required_scope
        self.granted = tuple(granted)
        self.status_code = 403
        self.oauth_error = "insufficient_scope"
        super().__init__(
            f"insufficient_scope (403): this connection is missing the "
            f"{required_scope} scope. Reconnect and grant it to use this tool."
        )


class McpAuthenticationError(PermissionError):
    """No usable credential was presented."""

    def __init__(self) -> None:
        self.status_code = 401
        self.oauth_error = "invalid_token"
        super().__init__(
            "invalid_token (401): a valid LEAGUEPILOT account connection is required."
        )
