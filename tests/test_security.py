from __future__ import annotations

import base64

import pytest
from cryptography.exceptions import InvalidTag
from pydantic import ValidationError

from app.config import Settings
from app.security import SecretBox, generate_encryption_key


def test_secret_box_round_trip_and_context_binding() -> None:
    box = SecretBox(generate_encryption_key())
    ciphertext = box.seal_json({"espn_s2": "secret", "swid": "{abc}"}, context="league:one")

    assert box.open_json(ciphertext, context="league:one") == {
        "espn_s2": "secret",
        "swid": "{abc}",
    }
    with pytest.raises(InvalidTag):
        box.open_json(ciphertext, context="league:two")


def test_secret_box_rejects_tampering() -> None:
    box = SecretBox(generate_encryption_key())
    ciphertext = box.seal_json({"target": "https://example.invalid"}, context="notification")
    raw = bytearray(base64.urlsafe_b64decode(ciphertext))
    raw[-1] ^= 1

    with pytest.raises(InvalidTag):
        box.open_json(base64.urlsafe_b64encode(raw).decode(), context="notification")


def test_secret_box_rejects_short_key() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        SecretBox(base64.urlsafe_b64encode(b"too-short").decode())


def test_production_refuses_demo_mode() -> None:
    with pytest.raises(ValidationError, match="FCC_DEMO_MODE must be false"):
        Settings(_env_file=None, environment="production", demo_mode=True)


def test_settings_reject_malformed_encryption_key_before_startup() -> None:
    with pytest.raises(ValidationError, match="exactly 32 bytes"):
        Settings(_env_file=None, encryption_key=base64.urlsafe_b64encode(b"short").decode())


def test_production_rejects_insecure_ai_provider_url() -> None:
    with pytest.raises(ValidationError, match="must use HTTPS"):
        Settings(
            _env_file=None,
            environment="production",
            admin_token="a" * 40,
            encryption_key=generate_encryption_key(),
            ai_base_url="http://models.example/v1",
        )
