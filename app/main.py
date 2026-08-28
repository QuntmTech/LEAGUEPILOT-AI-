from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.bootstrap import bootstrap_founder_workspace
from app.config import Settings, get_settings
from app.database import Database
from app.meta import VERSION
from app.rate_limit import LoginRateLimiter
from app.routers import (
    activity,
    connections,
    dashboard,
    intelligence,
    jobs,
    notifications,
    reports,
    session,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    database = Database(resolved)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        database.create_schema()
        with database.session_factory() as db:
            bootstrap_founder_workspace(db, resolved)
        yield
        database.dispose()

    app = FastAPI(
        title=resolved.app_name,
        version=VERSION,
        docs_url="/api/docs" if resolved.environment != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.state.database = database
    app.state.login_limiter = LoginRateLimiter(
        limit=resolved.login_attempt_limit,
        window_seconds=resolved.login_window_seconds,
    )

    if resolved.parsed_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved.parsed_cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
        )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        if resolved.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(Exception)
    async def unhandled_error(_: Request, __: Exception):
        return JSONResponse(status_code=500, content={"detail": "Unexpected server error"})

    @app.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": VERSION, "environment": resolved.environment}

    @app.get("/api/setup/status", tags=["system"])
    def setup_status() -> dict[str, object]:
        return {
            "configured": resolved.admin_token is not None,
            "credential_encryption": resolved.encryption_key is not None,
            "demo_mode": resolved.demo_mode,
        }

    app.include_router(session.router)
    app.include_router(activity.router)
    app.include_router(connections.router)
    app.include_router(dashboard.router)
    app.include_router(intelligence.router)
    app.include_router(reports.router)
    app.include_router(notifications.router)
    app.include_router(jobs.router)

    static_dir = Path(__file__).parent / "static"
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="dashboard")
    return app


app = create_app()
