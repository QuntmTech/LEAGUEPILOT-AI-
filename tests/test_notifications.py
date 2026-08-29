from __future__ import annotations

import httpx
import pytest

from app.services.notifications import NotificationError, deliver


def test_discord_delivery_bounds_message_and_disables_redirects() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(204, request=request)

    deliver(
        "discord",
        "https://discord.com/api/webhooks/123/private-token",
        "x" * 3000,
        transport=httpx.MockTransport(handler),
    )

    request = captured["request"]
    assert isinstance(request, httpx.Request)
    assert request.headers["user-agent"] == "LeaguePilotAI/0.4.0"
    assert len(request.content) < 2100


def test_delivery_error_never_exposes_notification_target() -> None:
    secret_target = "https://discord.com/api/webhooks/123/do-not-leak"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, request=request)

    with pytest.raises(NotificationError) as caught:
        deliver(
            "discord",
            secret_target,
            "hello",
            transport=httpx.MockTransport(handler),
        )

    assert str(caught.value) == "discord delivery failed with HTTP 403"
    assert secret_target not in str(caught.value)


def test_unsupported_notification_channel_fails_closed() -> None:
    with pytest.raises(NotificationError, match="Unsupported notification channel"):
        deliver("carrier-pigeon", "irrelevant", "hello")


def test_outbound_chat_message_neutralizes_mass_mentions() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(204, request=request)

    deliver(
        "discord",
        "https://discord.com/api/webhooks/123/private-token",
        "@everyone check the recap",
        transport=httpx.MockTransport(handler),
    )

    assert "@everyone" not in str(captured["body"])
