from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import demo
from app.config import Settings
from app.main import create_app
from app.models import AuditEvent, EspnConnection, NotificationChannel, Report
from app.security import generate_encryption_key


def test_health_and_security_headers(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == "0.3.0"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_session_requires_csrf_for_mutation(
    client: TestClient,
    authenticated: dict[str, str],
) -> None:
    workspace_id = authenticated["workspace_id"]

    missing = client.post(f"/api/workspaces/{workspace_id}/analyses/lineup")
    assert missing.status_code == 401

    accepted = client.get(f"/api/workspaces/{workspace_id}/dashboard")
    assert accepted.status_code == 200


def test_private_espn_credentials_are_encrypted_and_never_returned(
    client: TestClient,
    authenticated: dict[str, str],
) -> None:
    workspace_id = authenticated["workspace_id"]
    response = client.put(
        f"/api/workspaces/{workspace_id}/connections/espn",
        headers={"X-CSRF-Token": authenticated["csrf"]},
        json={
            "league_id": 123456,
            "team_id": 1,
            "season": 2026,
            "is_public": False,
            "espn_s2": "super-sensitive-cookie",
            "swid": "{private-swid}",
        },
    )
    assert response.status_code == 200
    assert "super-sensitive-cookie" not in response.text
    assert "private-swid" not in response.text

    with client.app.state.database.session_factory() as db:
        connection = db.scalar(select(EspnConnection))
        assert connection is not None
        assert "super-sensitive-cookie" not in connection.credentials_ciphertext
        assert "private-swid" not in connection.credentials_ciphertext


def test_private_connection_edit_can_keep_existing_encrypted_credentials(
    client: TestClient,
    authenticated: dict[str, str],
) -> None:
    workspace_id = authenticated["workspace_id"]
    url = f"/api/workspaces/{workspace_id}/connections/espn"
    headers = {"X-CSRF-Token": authenticated["csrf"]}
    first = client.put(
        url,
        headers=headers,
        json={
            "league_id": 123456,
            "team_id": 1,
            "season": 2026,
            "is_public": False,
            "espn_s2": "initial-private-cookie",
            "swid": "{initial-private-swid}",
        },
    )
    assert first.status_code == 200
    with client.app.state.database.session_factory() as db:
        original = db.scalar(select(EspnConnection)).credentials_ciphertext

    edited = client.put(
        url,
        headers=headers,
        json={
            "league_id": 123456,
            "team_id": 2,
            "season": 2026,
            "is_public": False,
            "espn_s2": None,
            "swid": None,
        },
    )
    assert edited.status_code == 200
    assert edited.json()["team_id"] == 2
    with client.app.state.database.session_factory() as db:
        assert db.scalar(select(EspnConnection)).credentials_ciphertext == original


def test_editing_league_identity_reuses_the_workspace_connection(
    client: TestClient,
    authenticated: dict[str, str],
) -> None:
    workspace_id = authenticated["workspace_id"]
    url = f"/api/workspaces/{workspace_id}/connections/espn"
    headers = {"X-CSRF-Token": authenticated["csrf"]}

    first = client.put(
        url,
        headers=headers,
        json={"league_id": 111, "team_id": 1, "season": 2026, "is_public": True},
    )
    edited = client.put(
        url,
        headers=headers,
        json={"league_id": 222, "team_id": 3, "season": 2027, "is_public": True},
    )

    assert first.status_code == 200
    assert edited.status_code == 200
    assert edited.json()["id"] == first.json()["id"]
    connections = client.get(url).json()
    assert len(connections) == 1
    assert connections[0]["league_id"] == 222
    assert connections[0]["season"] == 2027


def test_cross_workspace_id_is_hidden(
    client: TestClient,
    authenticated: dict[str, str],
) -> None:
    response = client.get("/api/workspaces/not-your-workspace/dashboard")

    assert response.status_code == 404


def test_static_dashboard_is_served(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "LEAGUEPILOT AI" in response.text
    assert "PROJ SHARE" in response.text
    assert "WIN EDGE" not in response.text
    assert 'id="notification-channel-list"' in response.text


def test_csrf_cookie_can_be_refreshed_for_a_new_browser_tab(
    client: TestClient,
    authenticated: dict[str, str],
) -> None:
    old_csrf = authenticated["csrf"]
    assert client.cookies.get("fcc_csrf") == old_csrf

    refreshed = client.get("/api/session/csrf")
    assert refreshed.status_code == 200
    new_csrf = refreshed.json()["csrf_token"]
    assert new_csrf != old_csrf
    assert client.cookies.get("fcc_csrf") == new_csrf

    rejected = client.put(
        f"/api/workspaces/{authenticated['workspace_id']}/connections/espn",
        headers={"X-CSRF-Token": old_csrf},
        json={"league_id": 8, "team_id": 1, "season": 2026, "is_public": True},
    )
    assert rejected.status_code == 401
    accepted = client.put(
        f"/api/workspaces/{authenticated['workspace_id']}/connections/espn",
        headers={"X-CSRF-Token": new_csrf},
        json={"league_id": 8, "team_id": 1, "season": 2026, "is_public": True},
    )
    assert accepted.status_code == 200


def test_activity_and_notification_management_are_workspace_scoped(
    client: TestClient,
    authenticated: dict[str, str],
) -> None:
    workspace_id = authenticated["workspace_id"]
    headers = {"X-CSRF-Token": authenticated["csrf"]}
    webhook = "https://discord.com/api/webhooks/123456789/secret-token-value"
    created = client.post(
        f"/api/workspaces/{workspace_id}/notifications",
        headers=headers,
        json={"kind": "discord", "label": "League chat", "target": webhook},
    )
    assert created.status_code == 200
    channel_id = created.json()["id"]
    assert created.json()["created_at"]
    assert webhook not in created.text

    activity = client.get(f"/api/workspaces/{workspace_id}/activity")
    assert activity.status_code == 200
    assert any(item["action"] == "notification.channel.created" for item in activity.json())

    disabled = client.delete(
        f"/api/workspaces/{workspace_id}/notifications/{channel_id}",
        headers=headers,
    )
    assert disabled.status_code == 200
    with client.app.state.database.session_factory() as db:
        channel = db.get(NotificationChannel, channel_id)
        assert channel is not None
        assert channel.is_active is False
        assert channel.target_ciphertext == "disabled"

    blocked_test = client.post(
        f"/api/workspaces/{workspace_id}/notifications/{channel_id}/test",
        headers=headers,
    )
    assert blocked_test.status_code == 409
    assert blocked_test.json()["detail"] == "Notification channel is disabled"


def test_notification_target_rejects_non_official_webhook(
    client: TestClient,
    authenticated: dict[str, str],
) -> None:
    response = client.post(
        f"/api/workspaces/{authenticated['workspace_id']}/notifications",
        headers={"X-CSRF-Token": authenticated["csrf"]},
        json={
            "kind": "discord",
            "label": "Unsafe target",
            "target": "https://attacker.example/api/webhooks/123/secret",
        },
    )
    assert response.status_code == 422


def test_founder_login_is_rate_limited_after_repeated_failures(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'limited.db'}",
        admin_token="valid-founder-token-with-more-than-thirty-two-characters",
        encryption_key=generate_encryption_key(),
        login_attempt_limit=3,
        login_window_seconds=60,
    )
    with TestClient(create_app(settings)) as limited_client:
        for _ in range(3):
            response = limited_client.post(
                "/api/session",
                json={"token": "invalid-token-with-enough-characters"},
            )
            assert response.status_code == 401
        blocked = limited_client.post(
            "/api/session",
            json={"token": "valid-founder-token-with-more-than-thirty-two-characters"},
        )
        assert blocked.status_code == 429
        assert int(blocked.headers["retry-after"]) >= 1


def test_demo_mode_seeds_fictional_league_and_runs_analysis(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'demo.db'}",
        admin_token="demo-founder-token-with-more-than-thirty-two-characters",
        encryption_key=generate_encryption_key(),
        demo_mode=True,
    )
    with TestClient(create_app(settings)) as demo_client:
        login = demo_client.post(
            "/api/session",
            json={"token": "demo-founder-token-with-more-than-thirty-two-characters"},
        )
        csrf = login.json()["csrf_token"]
        workspace_id = demo_client.get("/api/me").json()["workspaces"][0]["id"]
        dashboard = demo_client.get(f"/api/workspaces/{workspace_id}/dashboard")

        assert dashboard.status_code == 200
        assert dashboard.json()["demo"] is True
        assert "Fictional Demo" in dashboard.json()["league"]["name"]

        analysis = demo_client.post(
            f"/api/workspaces/{workspace_id}/analyses/lineup",
            headers={"X-CSRF-Token": csrf},
        )
        assert analysis.status_code == 200
        assert analysis.json()


def test_protected_full_job_runs_every_engine_and_records_completion(
    client: TestClient,
    authenticated: dict[str, str],
    monkeypatch,
) -> None:
    workspace_id = authenticated["workspace_id"]
    connection = client.put(
        f"/api/workspaces/{workspace_id}/connections/espn",
        headers={"X-CSRF-Token": authenticated["csrf"]},
        json={"league_id": 44, "team_id": 1, "season": 2026, "is_public": True},
    )
    assert connection.status_code == 200

    class FakeGateway:
        def __init__(self, _timeout: float) -> None:
            pass

        def fetch_snapshot(self, **_kwargs):
            return demo.demo_snapshot(2026)

    monkeypatch.setattr("app.routers.jobs.EspnGateway", FakeGateway)
    response = client.post(
        "/api/internal/jobs/run",
        headers={"X-Job-Token": "test-job-token-with-more-than-thirty-two-characters"},
        json={"kind": "full", "notify": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["workspace_count"] == 1
    assert body["outcomes"][0]["status"] == "completed"
    assert body["outcomes"][0]["recommendation_count"] >= 1
    with client.app.state.database.session_factory() as db:
        assert db.scalar(select(Report)) is not None
        completed = db.scalars(select(AuditEvent).where(AuditEvent.action == "job.completed")).all()
        assert len(completed) == 1


def test_protected_job_rejects_invalid_token(client: TestClient) -> None:
    response = client.post(
        "/api/internal/jobs/run",
        headers={"X-Job-Token": "wrong-token"},
        json={"kind": "lineup", "notify": False},
    )
    assert response.status_code == 401


def test_unhandled_errors_never_return_exception_details(
    settings: Settings,
    monkeypatch,
) -> None:
    app = create_app(settings)

    def fail_for_test(*_args, **_kwargs):
        raise RuntimeError("private-diagnostic-value")

    monkeypatch.setattr("app.routers.dashboard.latest_snapshot_record", fail_for_test)
    with TestClient(app, raise_server_exceptions=False) as safe_client:
        login = safe_client.post(
            "/api/session",
            json={"token": "test-founder-token-with-more-than-thirty-two-characters"},
        )
        assert login.status_code == 200
        workspace_id = safe_client.get("/api/me").json()["workspaces"][0]["id"]
        response = safe_client.get(f"/api/workspaces/{workspace_id}/dashboard")

    assert response.status_code == 500
    assert response.json() == {"detail": "Unexpected server error"}
    assert "private-diagnostic-value" not in response.text
