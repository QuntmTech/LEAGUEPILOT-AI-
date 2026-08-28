from __future__ import annotations

import httpx

from app.meta import VERSION


class NotificationError(RuntimeError):
    pass


def deliver(
    kind: str,
    target: str,
    message: str,
    *,
    timeout: float = 10.0,
    transport: httpx.BaseTransport | None = None,
) -> None:
    bounded_message = message[:8000]
    try:
        with httpx.Client(
            timeout=httpx.Timeout(timeout),
            trust_env=False,
            follow_redirects=False,
            headers={"User-Agent": f"LeaguePilotAI/{VERSION}"},
            transport=transport,
        ) as client:
            if kind == "discord":
                response = client.post(target, json={"content": bounded_message[:2000]})
            elif kind == "groupme":
                response = client.post(
                    "https://api.groupme.com/v3/bots/post",
                    json={"bot_id": target, "text": bounded_message[:1000]},
                )
            else:
                raise NotificationError(f"Unsupported notification channel: {kind}")
            response.raise_for_status()
    except NotificationError:
        raise
    except httpx.HTTPStatusError as exc:
        raise NotificationError(
            f"{kind} delivery failed with HTTP {exc.response.status_code}"
        ) from exc
    except httpx.HTTPError as exc:
        raise NotificationError(f"{kind} delivery failed due to a network error") from exc
