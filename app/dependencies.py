from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.models import Workspace
from app.security import (
    SESSION_COOKIE,
    Principal,
    authenticate_api_key,
    authenticate_session,
)


def get_db(request: Request) -> Generator[Session, None, None]:
    yield from request.app.state.database.sessions()


def get_principal(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_csrf_token: str | None = Header(default=None),
) -> Principal:
    cookie = request.cookies.get(SESSION_COOKIE)
    principal: Principal | None = None
    if cookie:
        principal = authenticate_session(
            db,
            cookie,
            method=request.method,
            csrf_token=x_csrf_token,
        )
    elif authorization and authorization.lower().startswith("bearer "):
        principal = authenticate_api_key(db, authorization[7:].strip())

    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed or the CSRF token is missing",
        )
    return principal


def require_workspace(
    workspace_id: str,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> Workspace:
    if not principal.can_access(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace
