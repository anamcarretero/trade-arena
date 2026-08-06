from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from tradearena.adapters.memory import MemoryStore
from tradearena.application.services import (
    AccountService, AuthService, LeagueService, SessionService,
)
from tradearena.ports.identity import IdentityAssertion
from tradearena.presentation.api import Api
from tradearena.presentation.asgi import create_app


NOW = datetime(2026, 8, 5, 12, tzinfo=timezone.utc)


class Ids:
    def __init__(self):
        self.value = 0

    def __call__(self):
        self.value += 1
        return f"id-{self.value}"


def build_client(readiness=lambda: True):
    store = MemoryStore()
    ids = Ids()
    accounts = AccountService(store, ids)
    leagues = LeagueService(store, ids)
    sessions = SessionService(store, lambda: "owner-token", lambda: NOW)
    owner = accounts.login(
        IdentityAssertion("email", "owner@example.com", "owner@example.com", True),
        NOW,
    )
    token = sessions.issue(owner.id, NOW)
    dispatcher = Api(sessions, accounts, leagues, lambda: NOW)
    return TestClient(create_app(dispatcher, readiness)), token


class TrustedAuth0:
    def verify_id_token(self, token, nonce):
        assert token == "valid-id-token"
        assert nonce == "valid-auth0-nonce"
        return IdentityAssertion("auth0", "auth0|new", "new@example.com", True)


def test_health_checks_distinguish_liveness_and_readiness():
    client, _ = build_client(lambda: False)

    assert client.get("/health/live").json() == {"status": "ok"}
    unavailable = client.get("/health/ready")
    assert unavailable.status_code == 503
    assert unavailable.json() == {"status": "unavailable"}


def test_fastapi_wraps_dispatcher_and_preserves_private_authorization():
    client, token = build_client()

    missing = client.get("/api/v1/leagues")
    assert missing.status_code == 403
    created = client.post(
        "/api/v1/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Privada"},
    )
    assert created.status_code == 201
    assert created.json()["name"] == "Privada"
    league_id = created.json()["id"]
    assert created.json()["actor_role"] == "owner"
    invitation = client.post(
        f"/api/v1/leagues/{league_id}/invitations",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "member@example.com"},
    )
    assert invitation.status_code == 201
    assert invitation.json()["status"] == "pending"
    detail = client.get(
        f"/api/v1/leagues/{league_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.json()["invitations"][0]["id"] == invitation.json()["id"]


def test_validation_is_a_stable_400_error():
    client, token = build_client()

    response = client.post(
        "/api/v1/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "", "unexpected": True},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_input"


def test_fastapi_routes_match_canonical_openapi_operation_ids():
    client, _ = build_client()
    generated = client.get("/openapi.json").json()
    canonical_path = (
        Path(__file__).parents[2] / "tradearena" / "presentation" / "openapi.yaml"
    )
    canonical = yaml.safe_load(canonical_path.read_text())

    methods = {"get", "post", "patch", "put", "delete"}

    def operations(document):
        return {
            (path, method, definition["operationId"])
            for path, path_item in document["paths"].items()
            for method, definition in path_item.items()
            if method in methods
        }

    assert operations(generated) == operations(canonical)


def test_auth0_exchange_is_bff_only_and_logout_revokes_server_session():
    store = MemoryStore()
    ids = Ids()
    accounts = AccountService(store, ids)
    sessions = SessionService(store, lambda: "opaque-session", lambda: NOW)
    dispatcher = Api(
        sessions, accounts, LeagueService(store, ids), lambda: NOW,
        AuthService(TrustedAuth0(), accounts, sessions), "shared-bff-secret",
    )
    client = TestClient(create_app(dispatcher))

    body = {"id_token": "valid-id-token", "nonce": "valid-auth0-nonce"}
    denied = client.post("/api/v1/auth/session", json=body)
    assert denied.status_code == 403
    exchanged = client.post(
        "/api/v1/auth/session",
        headers={"X-TradeArena-BFF": "shared-bff-secret"},
        json=body,
    )
    assert exchanged.status_code == 201
    assert exchanged.json()["session_token"] == "opaque-session"
    assert client.get(
        "/api/v1/me", headers={"Authorization": "Bearer opaque-session"}
    ).status_code == 200
    assert client.post(
        "/api/v1/auth/logout", headers={"Authorization": "Bearer opaque-session"}
    ).status_code == 204
    assert client.get(
        "/api/v1/me", headers={"Authorization": "Bearer opaque-session"}
    ).status_code == 403
