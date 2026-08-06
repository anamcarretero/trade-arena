"""API REST v1 transportable a cualquier servidor WSGI/ASGI.

``handle`` mantiene las reglas HTTP fuera de los casos de uso. Resulta fácil de
probar sin red y puede envolverse con el servidor elegido en Fase 3.
"""

from __future__ import annotations

import hmac
from dataclasses import asdict, dataclass
from datetime import date, datetime
from enum import Enum
from typing import Callable
from zoneinfo import ZoneInfo

from tradearena.application.services import (
    ApplicationError, Conflict, Forbidden, InvalidInput, NotFound,
    PlanLimitExceeded,
)


@dataclass(frozen=True)
class ApiResponse:
    status: int
    body: object


def _json(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value


def _reported_datetime(value: object, timezone_name: object) -> datetime:
    name = str(timezone_name or "Europe/Madrid")
    if name not in {"Europe/Madrid", "UTC"}:
        raise InvalidInput("zona horaria no soportada")
    result = datetime.fromisoformat(str(value))
    if result.tzinfo is None:
        result = result.replace(tzinfo=ZoneInfo(name))
    return result


class Api:
    def __init__(
        self, sessions, accounts, leagues, clock: Callable[[], datetime],
        auth=None, bff_shared_secret: str | None = None, competitions=None,
        trading=None, notifications=None,
    ) -> None:
        self.sessions = sessions
        self.accounts = accounts
        self.leagues = leagues
        self.clock = clock
        self.auth = auth
        self.bff_shared_secret = bff_shared_secret
        self.competitions = competitions
        self.trading = trading
        self.notifications = notifications

    def handle(
        self, method: str, path: str, token: str | None = None,
        body: dict | None = None, service_token: str | None = None,
    ) -> ApiResponse:
        body = body or {}
        try:
            segments = [segment for segment in path.strip("/").split("/") if segment]
            if segments[:2] != ["api", "v1"]:
                return ApiResponse(404, {"error": "not_found"})
            route = segments[2:]
            now = self.clock()
            if method == "POST" and route == ["auth", "session"]:
                configured = self.auth is not None and self.bff_shared_secret
                valid_service = configured and service_token and hmac.compare_digest(
                    self.bff_shared_secret, service_token
                )
                if not valid_service:
                    raise Forbidden("BFF no autorizado")
                session = self.auth.exchange_auth0(
                    str(body.get("id_token", "")), str(body.get("nonce", "")), now
                )
                return ApiResponse(201, {
                    "session_token": session,
                    "expires_in": int(self.sessions.TTL.total_seconds()),
                })
            actor = self.sessions.authenticate(token)
            if method == "POST" and route == ["auth", "logout"]:
                self.sessions.revoke(token, now)
                return ApiResponse(204, None)
            if method == "GET" and route == ["me"]:
                return ApiResponse(200, _json(self.accounts.export(actor, actor)))
            if method == "PATCH" and route == ["me", "profile"]:
                profile = self.accounts.set_profile(
                    actor, str(body.get("display_name", "")),
                    str(body.get("locale", "")), date.fromisoformat(str(body["birth_date"])),
                    datetime.fromisoformat(str(body["accepted_terms_at"])), now,
                )
                return ApiResponse(200, _json(asdict(profile)))
            if method == "DELETE" and route == ["me"]:
                self.accounts.delete(
                    actor, actor, now,
                    confirmed=body.get("confirm_account_deletion") is True,
                )
                return ApiResponse(204, None)
            if route == ["notifications"] and method == "GET":
                return ApiResponse(200, _json(self.notifications.list_for(actor)))
            if len(route) == 3 and route[0] == "notifications" \
                    and route[2] == "read" and method == "POST":
                return ApiResponse(200, _json(
                    self.notifications.mark_read(actor, route[1], now)
                ))
            if route == ["invitations"] and method == "GET":
                return ApiResponse(200, [
                    _json(asdict(item))
                    for item in self.leagues.list_invitations(actor, now)
                ])
            if route == ["leagues"] and method == "GET":
                return ApiResponse(200, [_json(asdict(item))
                                         for item in self.leagues.list_for(actor, now)])
            if route == ["leagues"] and method == "POST":
                league = self.leagues.create(actor, str(body.get("name", "")), now)
                return ApiResponse(
                    201, _json(asdict(self.leagues.get(actor, league.id, now)))
                )
            if len(route) == 2 and route[0] == "leagues" and method == "GET":
                league = self.leagues.get(actor, route[1], now)
                return ApiResponse(200, _json(asdict(league)))
            if len(route) == 3 and route[0] == "leagues" \
                    and route[2] == "competitions" and method == "GET":
                items = self.competitions.list_for(actor, route[1])
                return ApiResponse(200, [_json(asdict(item)) for item in items])
            if len(route) == 3 and route[0] == "leagues" \
                    and route[2] == "competitions" and method == "POST":
                competition = self.competitions.create(
                    actor, route[1], str(body.get("name", "")),
                    datetime.fromisoformat(str(body["starts_at"])),
                    datetime.fromisoformat(str(body["ends_at"])), now,
                )
                return ApiResponse(201, _json(asdict(competition)))
            if len(route) == 4 and route[0] == "leagues" \
                    and route[2] == "competitions" and method == "GET":
                competition = self.competitions.get(actor, route[1], route[3])
                return ApiResponse(200, _json(asdict(competition)))
            if len(route) == 5 and route[0] == "leagues" \
                    and route[2] == "competitions" and route[4] == "start" \
                    and method == "POST":
                competition = self.competitions.start(
                    actor, route[1], route[3], now,
                )
                return ApiResponse(200, _json(asdict(competition)))
            if len(route) == 5 and route[0] == "leagues" \
                    and route[2] == "competitions" and route[4] == "portfolio" \
                    and method == "GET":
                result = self.trading.portfolio(actor, route[1], route[3], now)
                return ApiResponse(200, _json(asdict(result)))
            if len(route) == 5 and route[0] == "leagues" \
                    and route[2] == "competitions" and route[4] == "orders" \
                    and method == "POST":
                result = self.trading.submit_order(
                    actor, route[1], route[3], str(body.get("symbol", "")),
                    str(body.get("side", "")), body.get("quantity"),
                    str(body.get("order_type", "")),
                    bool(body.get("allow_extended_hours", False)),
                    str(body["limit_price"]) if body.get("limit_price") is not None else None,
                    now, str(body["client_order_id"])
                    if body.get("client_order_id") else None,
                    str(body["commission"]).replace(",", ".")
                    if body.get("commission") is not None else None,
                )
                return ApiResponse(201, _json(asdict(result)))
            if len(route) == 7 and route[0] == "leagues" \
                    and route[2] == "competitions" \
                    and route[4] == "reported-trades" \
                    and route[6] == "corrections" and method == "POST":
                result = self.trading.correct_reported_trade(
                    actor, route[1], route[3], route[5],
                    occurred_at=_reported_datetime(
                        body["date"], body.get("timezone", "Europe/Madrid")
                    ),
                    client_trade_id=str(body.get("client_trade_id", "")),
                    now=now,
                )
                return ApiResponse(201, _json(asdict(result)))
            if len(route) == 5 and route[0] == "leagues" \
                    and route[2] == "competitions" \
                    and route[4] == "reported-trades" and method == "POST":
                result = self.trading.report_trade(
                    actor, route[1], route[3],
                    occurred_at=_reported_datetime(
                        body["date"], body.get("timezone", "Europe/Madrid")
                    ),
                    symbol=str(body.get("ticker", "")),
                    side=str(body.get("type", "")),
                    quantity_value=str(body.get("quantity", "")),
                    price_per_share=str(body.get("price_per_share", "")).replace(",", "."),
                    total_amount=str(body.get("total_amount", "")).replace(",", "."),
                    currency=str(body.get("currency", "")),
                    fx_rate=str(body.get("fx_rate", "")),
                    client_trade_id=str(body.get("client_trade_id", "")),
                    now=now,
                    commission_value=(
                        str(body["commission"]).replace(",", ".")
                        if body.get("commission") is not None else None
                    ),
                )
                return ApiResponse(201, _json(asdict(result)))
            if len(route) == 6 and route[0] == "leagues" \
                    and route[2] == "competitions" and route[4] == "orders" \
                    and method == "DELETE":
                result = self.trading.cancel_order(
                    actor, route[1], route[3], route[5], now,
                )
                return ApiResponse(200, _json(asdict(result)))
            if len(route) == 5 and route[0] == "leagues" \
                    and route[2] == "competitions" and route[4] == "ranking" \
                    and method == "GET":
                result = self.trading.ranking(actor, route[1], route[3], now)
                return ApiResponse(200, _json(asdict(result)))
            if len(route) == 3 and route[0] == "leagues" \
                    and route[2] == "invitations" and method == "POST":
                invitation = self.leagues.invite(
                    actor, route[1], str(body.get("email", "")), now,
                )
                return ApiResponse(201, _json({
                    "id": invitation.id,
                    "email": invitation.email,
                    "expires_at": invitation.expires_at,
                    "status": invitation.status,
                }))
            if len(route) == 4 and route[0] == "leagues" \
                    and route[2] == "invitations" and method == "DELETE":
                self.leagues.revoke(actor, route[1], route[3], now)
                return ApiResponse(204, None)
            if len(route) == 2 and route[0] == "invitations" \
                    and method == "POST":
                membership = self.leagues.accept(actor, route[1], now)
                return ApiResponse(200, _json(asdict(membership)))
            if len(route) == 4 and route[0] == "leagues" \
                    and route[2] == "members" and method == "DELETE":
                self.leagues.remove_member(actor, route[1], route[3], now)
                return ApiResponse(204, None)
            return ApiResponse(404, {"error": "not_found"})
        except KeyError as exc:
            return ApiResponse(400, {"error": "invalid_input", "detail": f"falta {exc.args[0]}"})
        except (TypeError, ValueError, InvalidInput) as exc:
            return ApiResponse(400, {"error": "invalid_input", "detail": str(exc)})
        except Forbidden as exc:
            return ApiResponse(403, {"error": exc.code})
        except NotFound as exc:
            return ApiResponse(404, {"error": exc.code})
        except (Conflict, PlanLimitExceeded) as exc:
            return ApiResponse(409, {"error": exc.code, "detail": str(exc)})
        except ApplicationError as exc:
            return ApiResponse(422, {"error": exc.code})
