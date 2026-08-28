from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_db, get_principal
from app.schemas import MeResponse, SessionCreate, WorkspaceSummary
from app.security import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    Principal,
    authenticate_api_key,
    create_browser_session,
    rotate_csrf_token,
)

router = APIRouter(prefix="/api", tags=["session"])


@router.post("/session")
def create_session(
    payload: SessionCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    client_key = request.client.host if request.client else "unknown"
    allowed, retry_after = request.app.state.login_limiter.check(client_key)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed sign-in attempts. Try again shortly.",
            headers={"Retry-After": str(retry_after)},
        )
    principal = authenticate_api_key(db, payload.token)
    if principal is None:
        request.app.state.login_limiter.record_failure(client_key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    request.app.state.login_limiter.clear(client_key)
    settings: Settings = request.app.state.settings
    raw_session, csrf_token, _ = create_browser_session(
        db,
        principal.user,
        lifetime_days=settings.session_days,
    )
    response.set_cookie(
        key=SESSION_COOKIE,
        value=raw_session,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        max_age=settings.session_days * 86400,
        path="/",
    )
    _set_csrf_cookie(response, csrf_token, settings)
    return {"authenticated": True, "csrf_token": csrf_token}


@router.get("/session/csrf")
def refresh_csrf(
    request: Request,
    response: Response,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if principal.session is None:
        raise HTTPException(status_code=409, detail="CSRF is only available to browser sessions")
    csrf_token = rotate_csrf_token(db, principal.session)
    _set_csrf_cookie(response, csrf_token, request.app.state.settings)
    return {"csrf_token": csrf_token}


@router.delete("/session")
def delete_session(
    response: Response,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    if principal.session is not None:
        principal.session.revoked_at = datetime.now(UTC)
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"signed_out": True}


@router.get("/me", response_model=MeResponse)
def me(principal: Principal = Depends(get_principal)) -> MeResponse:
    return MeResponse(
        user_id=principal.user.id,
        display_name=principal.user.display_name,
        email=principal.user.email,
        workspaces=[
            WorkspaceSummary(
                id=workspace.id,
                name=workspace.name,
                slug=workspace.slug,
                plan=workspace.plan,
            )
            for workspace in principal.workspaces
        ],
    )


def _set_csrf_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        httponly=False,
        secure=settings.environment == "production",
        samesite="strict",
        max_age=settings.session_days * 86400,
        path="/",
    )
