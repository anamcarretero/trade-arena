from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from tradearena.adapters.memory import MemoryStore
from tradearena.adapters.market_data import FixtureMarketDataAdapter
from tradearena.application.services import (
    AccountService, AuthService, CompetitionService, LeagueService,
    NotificationService, SessionService, TradingService,
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
    notifications = NotificationService(store, ids)
    notifications.create(
        owner.id, "competition.started", {"message": "Season ready"}, NOW,
    )
    dispatcher = Api(
        sessions, accounts, leagues, lambda: NOW,
        competitions=CompetitionService(store, ids),
        trading=TradingService(store, ids, FixtureMarketDataAdapter()),
        notifications=notifications,
    )
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


def test_fastapi_creates_and_starts_competition_with_snapshot():
    client, token = build_client()
    headers = {"Authorization": f"Bearer {token}"}
    league_id = client.post(
        "/api/v1/leagues", headers=headers, json={"name": "Privada"}
    ).json()["id"]
    created = client.post(
        f"/api/v1/leagues/{league_id}/competitions", headers=headers,
        json={
            "name": "Otoño",
            "starts_at": (NOW + timedelta(days=1)).isoformat(),
            "ends_at": (NOW + timedelta(days=31)).isoformat(),
        },
    )
    assert created.status_code == 201
    assert created.json()["rules_snapshot"] is None
    started = client.post(
        f"/api/v1/leagues/{league_id}/competitions/{created.json()['id']}/start",
        headers=headers,
    )
    assert started.status_code == 200
    assert started.json()["rules_snapshot"]["rules"]["initial_capital"] \
        == "3000.00"


def test_fastapi_exposes_portfolio_orders_history_and_ranking():
    client, token = build_client()
    headers = {"Authorization": f"Bearer {token}"}
    league_id = client.post(
        "/api/v1/leagues", headers=headers, json={"name": "Trading"}
    ).json()["id"]
    competition = client.post(
        f"/api/v1/leagues/{league_id}/competitions", headers=headers,
        json={
            "name": "Actual", "starts_at": NOW.isoformat(),
            "ends_at": (NOW + timedelta(days=7)).isoformat(),
        },
    ).json()
    client.post(
        f"/api/v1/leagues/{league_id}/competitions/{competition['id']}/start",
        headers=headers,
    )
    base = f"/api/v1/leagues/{league_id}/competitions/{competition['id']}"
    portfolio = client.get(f"{base}/portfolio", headers=headers)
    assert portfolio.status_code == 200
    assert portfolio.json()["initial_cash"] == "3000.00"
    submitted = client.post(
        f"{base}/orders", headers=headers, json={
            "symbol": "AAPL", "side": "buy", "quantity": 1,
            "order_type": "limit", "limit_price": "1.0000",
            "allow_extended_hours": False, "client_order_id": "order-e2e",
        },
    )
    assert submitted.status_code == 201
    assert submitted.json()["orders"][0]["status"] == "pending"
    order_id = submitted.json()["orders"][0]["id"]
    cancelled = client.delete(f"{base}/orders/{order_id}", headers=headers)
    assert cancelled.json()["orders"][0]["status"] == "cancelled"
    ranking = client.get(f"{base}/ranking", headers=headers)
    assert ranking.status_code == 200
    assert ranking.json()["rows"][0]["cumulative_return"] == "0E-12"


def test_fastapi_reports_fractional_trades_and_compensating_corrections():
    client, token = build_client()
    headers = {"Authorization": f"Bearer {token}"}
    league_id = client.post(
        "/api/v1/leagues", headers=headers, json={"name": "Reported"}
    ).json()["id"]
    competition = client.post(
        f"/api/v1/leagues/{league_id}/competitions", headers=headers,
        json={
            "name": "Actual", "starts_at": NOW.isoformat(),
            "ends_at": (NOW + timedelta(days=7)).isoformat(),
        },
    ).json()
    client.post(
        f"/api/v1/leagues/{league_id}/competitions/{competition['id']}/start",
        headers=headers,
    )
    base = f"/api/v1/leagues/{league_id}/competitions/{competition['id']}"
    payload = {
        "date": NOW.isoformat(), "ticker": "AAPL", "type": "buy",
        "quantity": "0.5", "price_per_share": "100",
        "total_amount": "51.15", "currency": "USD", "fx_rate": "1",
        "client_trade_id": "reported-api",
    }
    created = client.post(f"{base}/reported-trades", headers=headers, json=payload)
    assert created.status_code == 201
    assert created.json()["executions"][0]["source"] == "reported"
    assert created.json()["positions"][0]["quantity"] == "0.5"
    assert len(client.post(
        f"{base}/reported-trades", headers=headers, json=payload
    ).json()["executions"]) == 1

    execution_id = created.json()["executions"][0]["id"]
    correction = client.post(
        f"{base}/reported-trades/{execution_id}/corrections", headers=headers,
        json={"date": NOW.isoformat(), "client_trade_id": "correction-api"},
    )
    assert correction.status_code == 201
    assert correction.json()["cash"] == "3000.00"
    assert any(item["correction_of"] == execution_id
               for item in correction.json()["executions"])


def test_reported_trade_contract_rejects_excess_precision_and_non_usd():
    client, token = build_client()
    headers = {"Authorization": f"Bearer {token}"}
    invalid = client.post(
        "/api/v1/leagues/foreign/competitions/foreign/reported-trades",
        headers=headers,
        json={
            "date": NOW.isoformat(), "ticker": "AAPL", "type": "buy",
            "quantity": "0.123456789", "price_per_share": "100",
            "total_amount": "13.50", "currency": "EUR", "fx_rate": "1.1",
            "client_trade_id": "bad",
        },
    )
    assert invalid.status_code == 400
    hidden = client.post(
        "/api/v1/leagues/foreign/competitions/foreign/reported-trades",
        headers=headers,
        json={
            "date": NOW.isoformat(), "ticker": "AAPL", "type": "buy",
            "quantity": "0.5", "price_per_share": "100",
            "total_amount": "51.15", "currency": "USD", "fx_rate": "1",
            "client_trade_id": "hidden",
        },
    )
    assert hidden.status_code == 404


def test_reported_trade_accepts_madrid_time_and_decimal_commas_by_default():
    client, token = build_client()
    headers = {"Authorization": f"Bearer {token}"}
    league_id = client.post(
        "/api/v1/leagues", headers=headers, json={"name": "Madrid"}
    ).json()["id"]
    competition = client.post(
        f"/api/v1/leagues/{league_id}/competitions", headers=headers,
        json={
            "name": "Horario local",
            "starts_at": (NOW - timedelta(days=1)).isoformat(),
            "ends_at": (NOW + timedelta(days=1)).isoformat(),
        },
    ).json()
    client.post(
        f"/api/v1/leagues/{league_id}/competitions/{competition['id']}/start",
        headers=headers,
    )
    response = client.post(
        f"/api/v1/leagues/{league_id}/competitions/{competition['id']}/reported-trades",
        headers=headers,
        json={
            "date": "2026-08-05T10:11:00", "ticker": "MU", "type": "buy",
            "quantity": "1", "price_per_share": "855,70",
            "total_amount": "856,85", "currency": "USD", "fx_rate": "1",
            "client_trade_id": "madrid-comma",
        },
    )
    assert response.status_code == 201
    execution = response.json()["executions"][0]
    assert execution["price"] == "855.7000"
    assert execution["commission"] == "1.15"
    assert execution["executed_at"] == "2026-08-05T10:11:00+02:00"


def test_api_accepts_optional_decimal_comma_commissions():
    client, token = build_client()
    headers = {"Authorization": f"Bearer {token}"}
    league_id = client.post(
        "/api/v1/leagues", headers=headers, json={"name": "Fees"}
    ).json()["id"]
    competition = client.post(
        f"/api/v1/leagues/{league_id}/competitions", headers=headers,
        json={
            "name": "Custom fees", "starts_at": NOW.isoformat(),
            "ends_at": (NOW + timedelta(days=1)).isoformat(),
        },
    ).json()
    base = f"/api/v1/leagues/{league_id}/competitions/{competition['id']}"
    client.post(f"{base}/start", headers=headers)
    order = client.post(f"{base}/orders", headers=headers, json={
        "symbol": "AAPL", "side": "buy", "quantity": "1",
        "order_type": "limit", "allow_extended_hours": False,
        "limit_price": "1", "commission": "0,75",
        "client_order_id": "custom-fee",
    })
    assert order.status_code == 201
    assert order.json()["orders"][0]["commission"] == "0.75"

    reported = client.post(f"{base}/reported-trades", headers=headers, json={
        "date": NOW.isoformat(), "ticker": "MU", "type": "buy",
        "quantity": "1", "price_per_share": "100", "total_amount": "100,43",
        "commission": "0,43", "currency": "USD", "fx_rate": "1",
        "client_trade_id": "reported-custom-fee",
    })
    assert reported.status_code == 201
    assert reported.json()["executions"][0]["commission"] == "0.43"


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


def test_notifications_are_private_readable_and_idempotent():
    client, token = build_client()
    headers = {"Authorization": f"Bearer {token}"}

    listed = client.get("/api/v1/notifications", headers=headers)
    assert listed.status_code == 200
    notification = listed.json()[0]
    assert notification["read_at"] is None
    first = client.post(
        f"/api/v1/notifications/{notification['id']}/read", headers=headers,
    )
    second = client.post(
        f"/api/v1/notifications/{notification['id']}/read", headers=headers,
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["read_at"] == second.json()["read_at"] == NOW.isoformat()
    assert client.post(
        "/api/v1/notifications/foreign/read", headers=headers,
    ).status_code == 404


def test_account_delete_requires_confirmation_and_revokes_session():
    client, token = build_client()
    headers = {"Authorization": f"Bearer {token}"}

    denied = client.request(
        "DELETE", "/api/v1/me", headers=headers,
        json={"confirm_account_deletion": False},
    )
    assert denied.status_code == 400
    deleted = client.request(
        "DELETE", "/api/v1/me", headers=headers,
        json={"confirm_account_deletion": True},
    )
    assert deleted.status_code == 204
    assert client.get("/api/v1/me", headers=headers).status_code == 403


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
    exported = client.get(
        "/api/v1/me", headers={"Authorization": "Bearer opaque-session"}
    )
    assert exported.status_code == 200
    assert exported.json()["schema_version"] == "1"
    assert "identity_subject" not in exported.text
    assert "opaque-session" not in exported.text
    assert client.post(
        "/api/v1/auth/logout", headers={"Authorization": "Bearer opaque-session"}
    ).status_code == 204
    assert client.get(
        "/api/v1/me", headers={"Authorization": "Bearer opaque-session"}
    ).status_code == 403
