from __future__ import annotations

import uvicorn

from app.auth_server.server import create_app
from app.auth_server.settings import AuthServerSettings


def main() -> int:
    settings = AuthServerSettings()
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
        log_level=settings.log_level.lower(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
