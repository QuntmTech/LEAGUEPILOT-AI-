from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApiKey, BrowserSession, Membership, User, Workspace

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
SESSION_COOKIE = "fcc_session"
CSRF_COOKIE = "fcc_csrf"


def digest_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token(byte_length: int = 32) -> str:
    return secrets.token_urlsafe(byte_length)


def generate_encryption_key() -> str:
    return base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode("ascii")


class SecretBox:
    def __init__(self, encoded_key: str) -> None:
        try:
            key = base64.urlsafe_b64decode(encoded_key.encode("ascii"))
        except Exception as exc:  # pragma: no cover - precise message matters more than subtype
            raise ValueError("FCC_ENCRYPTION_KEY must be URL-safe base64") from exc
        if len(key) != 32:
            raise ValueError("FCC_ENCRYPTION_KEY must decode to exactly 32 bytes")
        self._cipher = AESGCM(key)

    def seal_json(self, payload: dict[str, object], *, context: str) -> str:
        nonce = secrets.token_bytes(12)
        plaintext = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        ciphertext = self._cipher.encrypt(nonce, plaintext, context.encode("utf-8"))
        return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

    def open_json(self, token: str, *, context: str) -> dict[str, object]:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
        if len(raw) < 29:
            raise ValueError("Encrypted value is malformed")
        plaintext = self._cipher.decrypt(raw[:12], raw[12:], context.encode("utf-8"))
        value = json.loads(plaintext.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Encrypted value must contain an object")
        return value


@dataclass(frozen=True)
class Principal:
    user: User
    workspaces: tuple[Workspace, ...]
    session: BrowserSession | None = None

    def can_access(self, workspace_id: str) -> bool:
        return any(workspace.id == workspace_id for workspace in self.workspaces)


def authenticate_api_key(db: Session, raw_token: str) -> Principal | None:
    key = db.scalar(
        select(ApiKey).where(
            ApiKey.token_digest == digest_token(raw_token),
            ApiKey.revoked_at.is_(None),
        )
    )
    now = datetime.now(UTC)
    if key is None or (key.expires_at is not None and _aware(key.expires_at) <= now):
        return None
    user = db.get(User, key.user_id)
    if user is None or not user.is_active:
        return None
    key.last_used_at = now
    db.commit()
    return _principal_for_user(db, user)


def create_browser_session(
    db: Session,
    user: User,
    *,
    lifetime_days: int,
) -> tuple[str, str, BrowserSession]:
    raw_session = new_token()
    raw_csrf = new_token(24)
    session = BrowserSession(
        user_id=user.id,
        token_digest=digest_token(raw_session),
        csrf_digest=digest_token(raw_csrf),
        expires_at=datetime.now(UTC) + timedelta(days=lifetime_days),
    )
    db.add(session)
    db.commit()
    return raw_session, raw_csrf, session


def rotate_csrf_token(db: Session, session: BrowserSession) -> str:
    raw_csrf = new_token(24)
    session.csrf_digest = digest_token(raw_csrf)
    db.commit()
    return raw_csrf


def authenticate_session(
    db: Session,
    raw_token: str,
    *,
    method: str,
    csrf_token: str | None,
) -> Principal | None:
    session = db.scalar(
        select(BrowserSession).where(
            BrowserSession.token_digest == digest_token(raw_token),
            BrowserSession.revoked_at.is_(None),
        )
    )
    now = datetime.now(UTC)
    if session is None or _aware(session.expires_at) <= now:
        return None
    if method.upper() not in SAFE_METHODS:
        if not csrf_token or not hmac.compare_digest(
            session.csrf_digest,
            digest_token(csrf_token),
        ):
            return None
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None
    principal = _principal_for_user(db, user)
    return Principal(principal.user, principal.workspaces, session=session)


def _principal_for_user(db: Session, user: User) -> Principal:
    workspaces = tuple(
        db.scalars(
            select(Workspace)
            .join(Membership, Membership.workspace_id == Workspace.id)
            .where(Membership.user_id == user.id)
            .order_by(Workspace.created_at)
        ).all()
    )
    return Principal(user=user, workspaces=workspaces)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
