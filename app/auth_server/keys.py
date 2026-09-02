from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import secrets

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth_server.models import SigningKey

# All asymmetric crypto, JWT signing and verification is delegated to `authlib` and
# `cryptography`. Nothing in this module implements a primitive by hand: the only local
# logic is key lifecycle (generate, publish, rotate, retire) and at-rest encryption of
# private material, both built on those libraries.


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def constant_time_equals(a: str, b: str) -> bool:
    """Timing-safe comparison for anything token-shaped."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def hash_token(value: str) -> str:
    """Tokens and codes are stored only as hashes, so a database read cannot replay them."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_secret(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def verify_pkce(verifier: str, challenge: str, method: str) -> bool:
    """Verify an S256 PKCE challenge.

    Only S256 is accepted. OAuth 2.1 forbids `plain`, and accepting it would let a network
    attacker who observes the authorization request complete the exchange.
    """
    if method != "S256":
        return False
    if not verifier or not (43 <= len(verifier) <= 128):
        return False
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return constant_time_equals(_b64u(digest), challenge)


class KeyStore:
    """Signing-key lifecycle with rotation.

    Private keys are encrypted at rest with a Fernet key supplied by the environment, so a
    stolen database file alone cannot forge tokens. Rotation publishes a new active key and
    keeps the previous one in the JWKS until every token it signed has expired — clients
    caching the JWKS never see a token they cannot verify.
    """

    def __init__(self, session_factory, encryption_key: str, key_ttl_seconds: int) -> None:
        self._sessions = session_factory
        self._fernet = Fernet(encryption_key.encode("utf-8"))
        self._ttl = key_ttl_seconds

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")

    def active_key(self) -> tuple[str, str]:
        """Return (kid, private PEM), generating or rotating as needed."""
        now = dt.datetime.now(dt.timezone.utc)
        with self._sessions() as session:
            key = (
                session.query(SigningKey)
                .filter(SigningKey.is_active.is_(True))
                .order_by(SigningKey.created_at.desc())
                .first()
            )
            if key and key.retire_after > now:
                return key.kid, self.decrypt(key.private_pem_encrypted)

            if key:
                # Rotate: the outgoing key stays in the JWKS until its retire window ends.
                key.is_active = False
                session.add(key)

            private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            pem = private.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode("ascii")
            numbers = private.public_key().public_numbers()
            kid = secrets.token_hex(8)
            jwk = {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": kid,
                "n": _b64u(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
                "e": _b64u(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
            }
            record = SigningKey(
                kid=kid,
                private_pem_encrypted=self.encrypt(pem),
                public_jwk=json.dumps(jwk),
                is_active=True,
                retire_after=now + dt.timedelta(seconds=self._ttl),
            )
            session.add(record)
            session.commit()
            return kid, pem

    def public_jwks(self) -> dict:
        """Every key still inside its retire window, so recently issued tokens verify."""
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)
        with self._sessions() as session:
            rows = (
                session.query(SigningKey)
                .filter(SigningKey.retire_after > cutoff)
                .order_by(SigningKey.created_at.desc())
                .all()
            )
            return {"keys": [json.loads(r.public_jwk) for r in rows]}


def load_encryption_key() -> str:
    """Read the at-rest encryption key from the environment.

    Never generated implicitly in production: a key that changes between restarts would
    silently invalidate every stored grant. Absent configuration is a startup failure.
    """
    value = os.environ.get("LEAGUEPILOT_AUTH_ENCRYPTION_KEY", "").strip()
    if not value:
        raise RuntimeError(
            "LEAGUEPILOT_AUTH_ENCRYPTION_KEY is required; generate one with "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"`"
        )
    return value
