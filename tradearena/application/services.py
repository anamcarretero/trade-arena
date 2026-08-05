"""Cuentas, sesiones, ligas privadas e invitaciones con autorización central."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from .models import (
    Invitation, InvitationStatus, League, Membership, Profile, Role, User,
)
from tradearena.ports.identity import IdentityAssertion


class ApplicationError(Exception):
    code = "application_error"


class NotFound(ApplicationError):
    code = "not_found"


class Forbidden(ApplicationError):
    code = "forbidden"


class Conflict(ApplicationError):
    code = "conflict"


class InvalidInput(ApplicationError):
    code = "invalid_input"


class PlanLimitExceeded(ApplicationError):
    code = "plan_limit_exceeded"


class SessionService:
    TTL = timedelta(days=30)

    def __init__(
        self, store, token_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(32))
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def issue(self, user_id: str, now: datetime | None = None) -> str:
        token = self._token_factory()
        issued_at = now or self._clock()
        with self.store.transaction():
            self.store.sessions[self._hash(token)] = (user_id, issued_at + self.TTL)
        return token

    def authenticate(self, token: str | None) -> str:
        session = self.store.sessions.get(self._hash(token or ""))
        if not session or self._clock() >= session[1]:
            raise Forbidden("sesión inválida")
        user_id = session[0]
        user = self.store.users.get(user_id or "")
        if not user_id or not user or user.deleted_at is not None:
            raise Forbidden("sesión inválida")
        return user_id

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    """Orquesta identidad externa, cuenta local y sesión revocable."""

    def __init__(self, identity, accounts, sessions) -> None:
        self.identity = identity
        self.accounts = accounts
        self.sessions = sessions

    def begin_email(self, email: str, now: datetime) -> str:
        return self.identity.begin_email_login(email, now + timedelta(minutes=15))

    def finish_email(self, token: str, now: datetime) -> str:
        assertion = self.identity.verify_email_token(token, now)
        user = self.accounts.login(assertion, now)
        return self.sessions.issue(user.id, now)

    def login_google(self, claims: dict[str, object], now: datetime) -> str:
        assertion = self.identity.verify_google_claims(claims)
        user = self.accounts.login(assertion, now)
        return self.sessions.issue(user.id, now)


class AccountService:
    def __init__(self, store, id_factory: Callable[[], str]) -> None:
        self.store = store
        self._id = id_factory

    def login(self, assertion: IdentityAssertion, now: datetime) -> User:
        if not assertion.email_verified:
            raise Forbidden("el email debe estar verificado")
        identity = (assertion.provider, assertion.subject)
        with self.store.transaction():
            existing_id = self.store.users_by_identity.get(identity)
            if existing_id:
                return self._active_user(existing_id)
            email = assertion.email.lower()
            same_email_id = self.store.users_by_email.get(email)
            if same_email_id:
                user = self._active_user(same_email_id)
                self.store.users_by_identity[identity] = user.id
                self.store.record_audit(
                    now, user.id, "identity.linked", "user", user.id,
                    {"provider": assertion.provider},
                )
                return user
            user = User(
                self._id(), email, assertion.provider,
                assertion.subject, now,
            )
            self.store.users[user.id] = user
            self.store.users_by_identity[identity] = user.id
            self.store.users_by_email[email] = user.id
            self.store.record_audit(now, user.id, "account.created", "user", user.id)
            return user

    def set_profile(
        self, user_id: str, display_name: str, locale: str,
        birth_date: date, accepted_terms_at: datetime, now: datetime,
    ) -> Profile:
        if locale not in {"es", "en"}:
            raise InvalidInput("idioma no soportado")
        age = now.year - birth_date.year - (
            (now.month, now.day) < (birth_date.month, birth_date.day)
        )
        if age < 18:
            raise InvalidInput("es necesario tener al menos 18 años")
        profile = Profile(user_id, display_name.strip(), locale,
                          accepted_terms_at, birth_date)
        if not profile.display_name:
            raise InvalidInput("el nombre visible es obligatorio")
        with self.store.transaction():
            self._active_user(user_id)
            self.store.profiles[user_id] = profile
            self.store.record_audit(now, user_id, "profile.updated", "user", user_id)
        return profile

    def export(self, actor_id: str, user_id: str) -> dict:
        if actor_id != user_id:
            raise Forbidden("solo se pueden exportar los datos propios")
        user = self._active_user(user_id)
        profile = self.store.profiles.get(user_id)
        memberships = [asdict(item) for item in self.store.memberships.values()
                       if item.user_id == user_id]
        invitations = [asdict(item) for item in self.store.invitations.values()
                       if item.email == user.email]
        return {
            "user": asdict(user),
            "profile": asdict(profile) if profile else None,
            "memberships": memberships,
            "invitations": invitations,
        }

    def delete(self, actor_id: str, user_id: str, now: datetime) -> None:
        if actor_id != user_id:
            raise Forbidden("solo se puede borrar la cuenta propia")
        with self.store.transaction():
            user = self._active_user(user_id)
            old_email = user.email
            user.deleted_at = now
            user.email = f"deleted+{user.id}@invalid.local"
            self.store.users_by_email.pop(old_email, None)
            self.store.users_by_identity = {
                identity: uid for identity, uid in self.store.users_by_identity.items()
                if uid != user_id
            }
            self.store.profiles.pop(user_id, None)
            for membership in self.store.memberships.values():
                if membership.user_id == user_id and membership.removed_at is None:
                    membership.removed_at = now
            self.store.sessions = {
                token: session for token, session in self.store.sessions.items()
                if session[0] != user_id
            }
            self.store.record_audit(now, user_id, "account.deleted", "user", user_id)

    def _active_user(self, user_id: str) -> User:
        user = self.store.users.get(user_id)
        if not user or user.deleted_at is not None:
            raise NotFound("cuenta no encontrada")
        return user


class LeagueService:
    FREE_MAX_ACTIVE_LEAGUES = 1
    FREE_MAX_MEMBERS = 2

    def __init__(self, store, id_factory: Callable[[], str]) -> None:
        self.store = store
        self._id = id_factory

    def create(self, actor_id: str, name: str, now: datetime) -> League:
        with self.store.transaction():
            user = self.store.users.get(actor_id)
            if not user or user.deleted_at is not None:
                raise Forbidden("cuenta no activa")
            active_owned = sum(
                1 for league in self.store.leagues.values()
                if league.owner_id == actor_id and league.active and league.plan == "free"
            )
            if active_owned >= self.FREE_MAX_ACTIVE_LEAGUES:
                raise PlanLimitExceeded("Free permite una liga activa")
            league = League(self._id(), name.strip(), actor_id, now)
            if not league.name:
                raise InvalidInput("el nombre de liga es obligatorio")
            self.store.leagues[league.id] = league
            self.store.memberships[(league.id, actor_id)] = Membership(
                league.id, actor_id, Role.OWNER, now
            )
            self.store.record_audit(now, actor_id, "league.created", "league", league.id)
            return league

    def get(self, actor_id: str, league_id: str) -> League:
        self._membership(actor_id, league_id)
        league = self.store.leagues.get(league_id)
        if not league:
            raise NotFound("liga no encontrada")
        return league

    def list_for(self, actor_id: str) -> list[League]:
        allowed = {
            league_id for (league_id, user_id), member in self.store.memberships.items()
            if user_id == actor_id and member.removed_at is None
        }
        return [league for league in self.store.leagues.values() if league.id in allowed]

    def invite(
        self, actor_id: str, league_id: str, email: str,
        expires_at: datetime, now: datetime,
    ) -> Invitation:
        with self.store.transaction():
            if expires_at <= now:
                raise InvalidInput("la invitación debe caducar en el futuro")
            actor = self._membership(actor_id, league_id)
            if actor.role not in {Role.OWNER, Role.ADMIN}:
                raise Forbidden("el rol no permite invitar")
            league = self.store.leagues[league_id]
            occupied = self._occupied_slots(league_id, now)
            if league.plan == "free" and occupied >= self.FREE_MAX_MEMBERS:
                raise PlanLimitExceeded("Free permite dos miembros, incluidas invitaciones")
            invitation = Invitation(
                self._id(), league_id, email.strip().lower(), Role.MEMBER,
                actor_id, now, expires_at,
            )
            self.store.invitations[invitation.id] = invitation
            self.store.record_audit(
                now, actor_id, "invitation.created", "invitation", invitation.id,
                {"league_id": league_id},
            )
            return invitation

    def revoke(self, actor_id: str, league_id: str, invitation_id: str, now: datetime) -> None:
        with self.store.transaction():
            actor = self._membership(actor_id, league_id)
            if actor.role not in {Role.OWNER, Role.ADMIN}:
                raise Forbidden("el rol no permite revocar")
            invitation = self.store.invitations.get(invitation_id)
            if not invitation or invitation.league_id != league_id:
                raise NotFound("invitación no encontrada")
            if invitation.status is not InvitationStatus.PENDING:
                raise Conflict("la invitación ya no está pendiente")
            invitation.status = InvitationStatus.REVOKED
            self.store.record_audit(
                now, actor_id, "invitation.revoked", "invitation", invitation.id
            )

    def accept(self, actor_id: str, invitation_id: str, now: datetime) -> Membership:
        with self.store.transaction():
            invitation = self.store.invitations.get(invitation_id)
            if not invitation:
                raise NotFound("invitación no encontrada")
            if invitation.status is not InvitationStatus.PENDING:
                raise Conflict("la invitación ya no está pendiente")
            if now >= invitation.expires_at:
                invitation.status = InvitationStatus.EXPIRED
                raise Conflict("la invitación ha caducado")
            user = self.store.users.get(actor_id)
            if not user or user.email.lower() != invitation.email:
                raise Forbidden("la invitación pertenece a otro email")
            league = self.store.leagues[invitation.league_id]
            active_members = sum(
                1 for member in self.store.memberships.values()
                if member.league_id == league.id and member.removed_at is None
            )
            if league.plan == "free" and active_members >= self.FREE_MAX_MEMBERS:
                raise PlanLimitExceeded("la liga Free ya está completa")
            membership = Membership(league.id, actor_id, invitation.role, now)
            self.store.memberships[(league.id, actor_id)] = membership
            invitation.status = InvitationStatus.ACCEPTED
            invitation.accepted_by = actor_id
            self.store.record_audit(
                now, actor_id, "invitation.accepted", "league", league.id
            )
            return membership

    def remove_member(
        self, actor_id: str, league_id: str, user_id: str, now: datetime
    ) -> None:
        with self.store.transaction():
            actor = self._membership(actor_id, league_id)
            if actor.role not in {Role.OWNER, Role.ADMIN}:
                raise Forbidden("el rol no permite expulsar")
            target = self._membership(user_id, league_id)
            if target.role is Role.OWNER:
                raise Conflict("no se puede expulsar al propietario")
            target.removed_at = now
            self.store.record_audit(
                now, actor_id, "member.removed", "league", league_id,
                {"user_id": user_id},
            )

    def _membership(self, user_id: str, league_id: str) -> Membership:
        membership = self.store.memberships.get((league_id, user_id))
        if not membership or membership.removed_at is not None:
            # No revela si la liga existe: evita enumeración entre ligas.
            raise NotFound("liga no encontrada")
        return membership

    def _occupied_slots(self, league_id: str, now: datetime) -> int:
        members = sum(
            1 for item in self.store.memberships.values()
            if item.league_id == league_id and item.removed_at is None
        )
        pending = sum(
            1 for item in self.store.invitations.values()
            if item.league_id == league_id
            and item.status is InvitationStatus.PENDING
            and item.expires_at > now
        )
        return members + pending
