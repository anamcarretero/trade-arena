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


class Api:
    def __init__(
        self, sessions, accounts, leagues, clock: Callable[[], datetime],
        auth=None, bff_shared_secret: str | None = None,
    ) -> None:
        self.sessions = sessions
        self.accounts = accounts
        self.leagues = leagues
        self.clock = clock
        self.auth = auth
        self.bff_shared_secret = bff_shared_secret

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
                self.accounts.delete(actor, actor, now)
                return ApiResponse(204, None)
            if route == ["leagues"] and method == "GET":
                return ApiResponse(200, [_json(asdict(item))
                                         for item in self.leagues.list_for(actor)])
            if route == ["leagues"] and method == "POST":
                league = self.leagues.create(actor, str(body.get("name", "")), now)
                return ApiResponse(201, _json(asdict(league)))
            if len(route) == 2 and route[0] == "leagues" and method == "GET":
                league = self.leagues.get(actor, route[1])
                return ApiResponse(200, _json(asdict(league)))
            if len(route) == 3 and route[0] == "leagues" \
                    and route[2] == "invitations" and method == "POST":
                invitation = self.leagues.invite(
                    actor, route[1], str(body.get("email", "")),
                    datetime.fromisoformat(str(body["expires_at"])), now,
                )
                return ApiResponse(201, _json(asdict(invitation)))
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
        except (ValueError, InvalidInput) as exc:
            return ApiResponse(400, {"error": "invalid_input", "detail": str(exc)})
        except Forbidden as exc:
            return ApiResponse(403, {"error": exc.code})
        except NotFound as exc:
            return ApiResponse(404, {"error": exc.code})
        except (Conflict, PlanLimitExceeded) as exc:
            return ApiResponse(409, {"error": exc.code, "detail": str(exc)})
        except ApplicationError as exc:
            return ApiResponse(422, {"error": exc.code})
