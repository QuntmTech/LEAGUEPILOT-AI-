from __future__ import annotations

import uvicorn

from app.mcp_gateway.settings import McpSettings


def main() -> None:
    settings = McpSettings()
    uvicorn.run(
        "app.mcp_gateway.server:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
