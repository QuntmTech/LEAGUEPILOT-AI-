from __future__ import annotations

import stat

from app.cli import doctor, init_environment
from app.security import generate_encryption_key


def test_force_init_restores_owner_only_permissions(tmp_path) -> None:
    target = tmp_path / ".env"
    target.write_text("old configuration", encoding="utf-8")
    target.chmod(0o644)

    init_environment(target, force=True)

    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert "FCC_ENCRYPTION_KEY=" in target.read_text(encoding="utf-8")


def test_doctor_redacts_database_password(monkeypatch, capsys) -> None:
    monkeypatch.setenv("FCC_ADMIN_TOKEN", "a" * 40)
    monkeypatch.setenv("FCC_ENCRYPTION_KEY", generate_encryption_key())
    monkeypatch.setenv(
        "FCC_DATABASE_URL",
        "postgresql://leaguepilot:database-secret@db.example/leaguepilot",
    )

    assert doctor() == 0
    output = capsys.readouterr().out
    assert "database-secret" not in output
    assert "***" in output


def test_doctor_rejects_invalid_database_url_without_echoing_it(monkeypatch, capsys) -> None:
    monkeypatch.setenv("FCC_ADMIN_TOKEN", "a" * 40)
    monkeypatch.setenv("FCC_ENCRYPTION_KEY", generate_encryption_key())
    monkeypatch.setenv("FCC_DATABASE_URL", "not-a-url-with-database-secret")

    assert doctor() == 1
    output = capsys.readouterr().out
    assert "database-secret" not in output
    assert "not a valid SQLAlchemy database URL" in output
