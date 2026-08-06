"""Adaptador FastAPI para el dispatcher HTTP de TradeArena."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime

from fastapi import Depends, FastAPI, Header, Security
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from .api import Api, ApiResponse


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1)
    locale: str
    birth_date: date
    accepted_terms_at: datetime


class LeagueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)


class InvitationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)


class CompetitionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    starts_at: datetime
    ends_at: datetime


class AuthSessionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_token: str = Field(min_length=1)
    nonce: str = Field(min_length=16)


_bearer = HTTPBearer(auto_error=False)


def _token(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> str | None:
    return credentials.credentials if credentials else None


def _response(result: ApiResponse) -> Response:
    if result.status == 204:
        return Response(status_code=204)
    return JSONResponse(status_code=result.status, content=result.body)


def create_app(api: Api, readiness: Callable[[], bool] | None = None) -> FastAPI:
    """Crea la aplicación ASGI sin acoplar el transporte al adaptador de datos."""

    ready = readiness or (lambda: True)
    app = FastAPI(title="TradeArena API", version="1.0.0")

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request, exc: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_input", "detail": exc.errors()},
        )

    @app.get("/health/live", operation_id="healthLive", include_in_schema=True)
    def health_live():
        return {"status": "ok"}

    @app.get("/health/ready", operation_id="healthReady", include_in_schema=True)
    def health_ready():
        try:
            available = ready()
        except Exception:
            available = False
        if not available:
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return {"status": "ok"}

    @app.get("/api/v1/me", operation_id="exportOwnAccount")
    def export_own_account(token: str | None = Depends(_token)):
        return _response(api.handle("GET", "/api/v1/me", token))

    @app.post("/api/v1/auth/session", operation_id="exchangeAuth0Session")
    def exchange_auth0_session(
        data: AuthSessionInput,
        bff_secret: str | None = Header(default=None, alias="X-TradeArena-BFF"),
    ):
        return _response(api.handle(
            "POST", "/api/v1/auth/session", body=data.model_dump(),
            service_token=bff_secret,
        ))

    @app.post("/api/v1/auth/logout", operation_id="revokeOwnSession")
    def revoke_own_session(token: str | None = Depends(_token)):
        return _response(api.handle("POST", "/api/v1/auth/logout", token))

    @app.delete("/api/v1/me", operation_id="deleteOwnAccount")
    def delete_own_account(token: str | None = Depends(_token)):
        return _response(api.handle("DELETE", "/api/v1/me", token))

    @app.patch("/api/v1/me/profile", operation_id="updateOwnProfile")
    def update_own_profile(data: ProfileInput, token: str | None = Depends(_token)):
        return _response(api.handle(
            "PATCH", "/api/v1/me/profile", token, data.model_dump(mode="json")
        ))

    @app.get("/api/v1/leagues", operation_id="listOwnLeagues")
    def list_own_leagues(token: str | None = Depends(_token)):
        return _response(api.handle("GET", "/api/v1/leagues", token))

    @app.get("/api/v1/invitations", operation_id="listOwnInvitations")
    def list_own_invitations(token: str | None = Depends(_token)):
        return _response(api.handle("GET", "/api/v1/invitations", token))

    @app.post("/api/v1/leagues", operation_id="createLeague")
    def create_league(data: LeagueInput, token: str | None = Depends(_token)):
        return _response(api.handle(
            "POST", "/api/v1/leagues", token, data.model_dump(mode="json")
        ))

    @app.get("/api/v1/leagues/{league_id}", operation_id="getLeague")
    def get_league(league_id: str, token: str | None = Depends(_token)):
        return _response(api.handle(
            "GET", f"/api/v1/leagues/{league_id}", token
        ))

    @app.get(
        "/api/v1/leagues/{league_id}/competitions",
        operation_id="listLeagueCompetitions",
    )
    def list_league_competitions(
        league_id: str, token: str | None = Depends(_token)
    ):
        return _response(api.handle(
            "GET", f"/api/v1/leagues/{league_id}/competitions", token
        ))

    @app.post(
        "/api/v1/leagues/{league_id}/competitions",
        operation_id="createCompetition",
    )
    def create_competition(
        league_id: str, data: CompetitionInput,
        token: str | None = Depends(_token),
    ):
        return _response(api.handle(
            "POST", f"/api/v1/leagues/{league_id}/competitions", token,
            data.model_dump(mode="json"),
        ))

    @app.get(
        "/api/v1/leagues/{league_id}/competitions/{competition_id}",
        operation_id="getCompetition",
    )
    def get_competition(
        league_id: str, competition_id: str,
        token: str | None = Depends(_token),
    ):
        return _response(api.handle(
            "GET",
            f"/api/v1/leagues/{league_id}/competitions/{competition_id}", token,
        ))

    @app.post(
        "/api/v1/leagues/{league_id}/competitions/{competition_id}/start",
        operation_id="startCompetition",
    )
    def start_competition(
        league_id: str, competition_id: str,
        token: str | None = Depends(_token),
    ):
        return _response(api.handle(
            "POST",
            f"/api/v1/leagues/{league_id}/competitions/{competition_id}/start",
            token,
        ))

    @app.post(
        "/api/v1/leagues/{league_id}/invitations",
        operation_id="inviteLeagueMember",
    )
    def invite_league_member(
        league_id: str, data: InvitationInput, token: str | None = Depends(_token)
    ):
        return _response(api.handle(
            "POST", f"/api/v1/leagues/{league_id}/invitations", token,
            data.model_dump(mode="json"),
        ))

    @app.delete(
        "/api/v1/leagues/{league_id}/invitations/{invitation_id}",
        operation_id="revokeLeagueInvitation",
    )
    def revoke_league_invitation(
        league_id: str, invitation_id: str, token: str | None = Depends(_token)
    ):
        return _response(api.handle(
            "DELETE", f"/api/v1/leagues/{league_id}/invitations/{invitation_id}",
            token,
        ))

    @app.post(
        "/api/v1/invitations/{invitation_id}", operation_id="acceptInvitation"
    )
    def accept_invitation(invitation_id: str, token: str | None = Depends(_token)):
        return _response(api.handle(
            "POST", f"/api/v1/invitations/{invitation_id}", token
        ))

    @app.delete(
        "/api/v1/leagues/{league_id}/members/{user_id}",
        operation_id="removeLeagueMember",
    )
    def remove_league_member(
        league_id: str, user_id: str, token: str | None = Depends(_token)
    ):
        return _response(api.handle(
            "DELETE", f"/api/v1/leagues/{league_id}/members/{user_id}", token
        ))

    return app
