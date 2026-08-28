from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import uvicorn
from sqlalchemy.engine import make_url

from app.config import Settings
from app.security import SecretBox, generate_encryption_key, new_token


def init_environment(target: Path, *, force: bool = False) -> None:
    if target.exists() and not force:
        raise FileExistsError(
            f"{target} already exists; use --force only if you intend to rotate keys"
        )
    admin_token = new_token(36)
    encryption_key = generate_encryption_key()
    job_token = new_token(36)
    content = "\n".join(
        [
            "# Generated locally. Never commit this file.",
            "FCC_ENVIRONMENT=development",
            "FCC_HOST=127.0.0.1",
            "FCC_PORT=8765",
            "FCC_DATABASE_URL=sqlite:///./.data/fantasy-command-center.db",
            f"FCC_ADMIN_TOKEN={admin_token}",
            f"FCC_ENCRYPTION_KEY={encryption_key}",
            f"FCC_JOB_TOKEN={job_token}",
            "FCC_DEFAULT_SEASON=2026",
            "FCC_AI_PROVIDER=rules",
            "",
        ]
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    descriptor = os.open(target, flags, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(content)
    print(f"Created {target} with owner-only permissions.")
    print("Founder access token (store it in your password manager):")
    print(admin_token)


def doctor() -> int:
    try:
        settings = Settings()
        if settings.admin_token is None:
            print("FAIL: FCC_ADMIN_TOKEN is not configured")
            return 1
        if settings.encryption_key is None:
            print("FAIL: FCC_ENCRYPTION_KEY is not configured")
            return 1
        SecretBox(settings.encryption_key.get_secret_value())
        try:
            safe_database_url = make_url(settings.database_url).render_as_string(hide_password=True)
        except Exception:
            print("FAIL: FCC_DATABASE_URL is not a valid SQLAlchemy database URL")
            return 1
        print(f"PASS: configuration valid for {settings.environment}")
        print(f"PASS: database target is {safe_database_url}")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(prog="leaguepilot-ai")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init", help="Generate local secrets and configuration")
    init_parser.add_argument("--target", default=".env", type=Path)
    init_parser.add_argument("--force", action="store_true")
    subparsers.add_parser("doctor", help="Validate local configuration")
    subparsers.add_parser("serve", help="Start the API and dashboard")
    args = parser.parse_args()

    if args.command == "init":
        try:
            init_environment(args.target, force=args.force)
        except FileExistsError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2) from exc
        return
    if args.command == "doctor":
        raise SystemExit(doctor())
    settings = Settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
    )


if __name__ == "__main__":
    main()
