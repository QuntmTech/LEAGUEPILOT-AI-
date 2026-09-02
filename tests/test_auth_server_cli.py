"""The authorization server entrypoint.

Thin, but it is what systemd actually executes on the VPS. A typo here is a deployment
that never binds a port, so the wiring is asserted rather than assumed.
"""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.auth_server import cli


def test_main_builds_the_app_and_serves_it_behind_a_trusted_proxy(monkeypatch, tmp_path):
    monkeypatch.setenv("LEAGUEPILOT_AUTH_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("LEAGUEPILOT_AUTH_DATABASE_URL", f"sqlite:///{tmp_path/'cli.db'}")
    monkeypatch.setenv("LEAGUEPILOT_AUTH_HOST", "127.0.0.1")
    monkeypatch.setenv("LEAGUEPILOT_AUTH_PORT", "9443")
    monkeypatch.setenv("LEAGUEPILOT_AUTH_INTROSPECTION_SECRET",
                       "cli-test-introspection-secret-0123456789")

    captured = {}

    def _fake_run(app, **kwargs):
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setattr(cli.uvicorn, "run", _fake_run)
    assert cli.main() == 0

    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 9443
    # The server sits behind Apache; without these, every redirect_uri and issuer check
    # would see http:// and the wrong host.
    assert captured["proxy_headers"] is True
    assert captured["forwarded_allow_ips"] == "127.0.0.1"
    assert captured["log_level"] == captured["log_level"].lower()

    # The object handed to uvicorn must be the real ASGI app, with routes mounted.
    paths = {route.path for route in captured["app"].routes}
    for required in ("/authorize", "/token", "/register", "/revoke", "/healthz",
                     "/.well-known/jwks.json", "/.well-known/oauth-authorization-server"):
        assert required in paths, required


def test_missing_encryption_key_fails_fast_rather_than_serving(monkeypatch, tmp_path):
    """Better a refused start than a server that silently invalidates every grant."""
    monkeypatch.delenv("LEAGUEPILOT_AUTH_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("LEAGUEPILOT_AUTH_DATABASE_URL", f"sqlite:///{tmp_path/'cli2.db'}")
    monkeypatch.setenv("LEAGUEPILOT_AUTH_INTROSPECTION_SECRET",
                       "cli-test-introspection-secret-0123456789")

    def _must_not_run(*args, **kwargs):
        raise AssertionError("uvicorn.run must not be reached without an encryption key")

    monkeypatch.setattr(cli.uvicorn, "run", _must_not_run)
    with pytest.raises(RuntimeError, match="LEAGUEPILOT_AUTH_ENCRYPTION_KEY"):
        cli.main()


def test_missing_introspection_secret_fails_fast_rather_than_serving(monkeypatch, tmp_path):
    """Introspection guards revocation. Starting without its credential would leave the
    gateway unable to confirm any grant, so refuse at startup rather than at runtime."""
    from pydantic import ValidationError

    monkeypatch.setenv("LEAGUEPILOT_AUTH_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("LEAGUEPILOT_AUTH_DATABASE_URL", f"sqlite:///{tmp_path/'cli3.db'}")
    monkeypatch.delenv("LEAGUEPILOT_AUTH_INTROSPECTION_SECRET", raising=False)

    def _must_not_run(*args, **kwargs):
        raise AssertionError("uvicorn.run must not be reached without a service credential")

    monkeypatch.setattr(cli.uvicorn, "run", _must_not_run)
    with pytest.raises(ValidationError):
        cli.main()
