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
from tradearena.ports.store import StoreConflict


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
        with self.store.transaction() as uow:
            uow.sessions.add(
                self._hash(token), user_id, issued_at, issued_at + self.TTL
            )
        return token

    def authenticate(self, token: str | None) -> str:
        with self.store.transaction() as uow:
            session = uow.sessions.get(self._hash(token or ""))
            if not session or self._clock() >= session[1]:
                raise Forbidden("sesión inválida")
            user_id = session[0]
            user = uow.users.get(user_id or "")
            if not user_id or not user or user.deleted_at is not None:
                raise Forbidden("sesión inválida")
            return user_id

    def revoke(self, token: str | None, now: datetime | None = None) -> None:
        if not token:
            return
        with self.store.transaction() as uow:
            uow.sessions.revoke(self._hash(token), now or self._clock())

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

    def exchange_auth0(self, id_token: str, nonce: str, now: datetime) -> str:
        assertion = self.identity.verify_id_token(id_token, nonce)
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
        with self.store.transaction() as uow:
            existing = uow.users.get_by_identity(*identity)
            if existing:
                return self._active_user(uow, existing.id)
            email = assertion.email.lower()
            same_email = uow.users.get_by_email(email)
            if same_email:
                user = self._active_user(uow, same_email.id)
                uow.users.link_identity(
                    assertion.provider, assertion.subject, user.id, True
                )
                uow.audit.add(
                    now, user.id, "identity.linked", "user", user.id,
                    {"provider": assertion.provider},
                )
                return user
            user = User(
                self._id(), email, assertion.provider,
                assertion.subject, now,
            )
            uow.users.add(user)
            uow.users.link_identity(
                assertion.provider, assertion.subject, user.id, True
            )
            uow.audit.add(now, user.id, "account.created", "user", user.id)
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
        with self.store.transaction() as uow:
            self._active_user(uow, user_id)
            uow.profiles.save(profile)
            uow.audit.add(now, user_id, "profile.updated", "user", user_id)
        return profile

    def export(self, actor_id: str, user_id: str) -> dict:
        if actor_id != user_id:
            raise Forbidden("solo se pueden exportar los datos propios")
        with self.store.transaction() as uow:
            user = self._active_user(uow, user_id)
            profile = uow.profiles.get(user_id)
            memberships = [
                asdict(item) for item in uow.memberships.list_for_user(user_id)
            ]
            invitations = [
                asdict(item) for item in uow.invitations.list_for_email(user.email)
            ]
            return {
                "user": asdict(user),
                "profile": asdict(profile) if profile else None,
                "memberships": memberships,
                "invitations": invitations,
            }

    def delete(self, actor_id: str, user_id: str, now: datetime) -> None:
        if actor_id != user_id:
            raise Forbidden("solo se puede borrar la cuenta propia")
        with self.store.transaction() as uow:
            user = self._active_user(uow, user_id)
            user.deleted_at = now
            user.email = f"deleted+{user.id}@invalid.local"
            uow.users.save(user)
            uow.users.delete_identities(user_id)
            uow.profiles.delete(user_id)
            uow.memberships.remove_active_for_user(user_id, now)
            uow.sessions.revoke_for_user(user_id, now)
            uow.audit.add(now, user_id, "account.deleted", "user", user_id)

    @staticmethod
    def _active_user(uow, user_id: str) -> User:
        user = uow.users.get(user_id)
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
        try:
            with self.store.transaction() as uow:
                user = uow.users.get(actor_id, for_update=True)
                if not user or user.deleted_at is not None:
                    raise Forbidden("cuenta no activa")
                if uow.leagues.count_active_free_owned(actor_id) \
                        >= self.FREE_MAX_ACTIVE_LEAGUES:
                    raise PlanLimitExceeded("Free permite una liga activa")
                league = League(self._id(), name.strip(), actor_id, now)
                if not league.name:
                    raise InvalidInput("el nombre de liga es obligatorio")
                uow.leagues.add(league)
                uow.memberships.save(Membership(
                    league.id, actor_id, Role.OWNER, now
                ))
                uow.audit.add(
                    now, actor_id, "league.created", "league", league.id
                )
                return league
        except StoreConflict as exc:
            if exc.constraint == "one_active_free_league_per_owner":
                raise PlanLimitExceeded("Free permite una liga activa") from exc
            raise Conflict("escritura duplicada") from exc

    def get(self, actor_id: str, league_id: str) -> League:
        with self.store.transaction() as uow:
            self._membership(uow, actor_id, league_id)
            league = uow.leagues.get(league_id)
            if not league:
                raise NotFound("liga no encontrada")
            return league

    def list_for(self, actor_id: str) -> list[League]:
        with self.store.transaction() as uow:
            return uow.leagues.list_for_user(actor_id)

    def invite(
        self, actor_id: str, league_id: str, email: str,
        expires_at: datetime, now: datetime,
    ) -> Invitation:
        with self.store.transaction() as uow:
            if expires_at <= now:
                raise InvalidInput("la invitación debe caducar en el futuro")
            actor = self._membership(uow, actor_id, league_id)
            if actor.role not in {Role.OWNER, Role.ADMIN}:
                raise Forbidden("el rol no permite invitar")
            league = uow.leagues.get(league_id, for_update=True)
            if not league:
                raise NotFound("liga no encontrada")
            occupied = self._occupied_slots(uow, league_id, now)
            if league.plan == "free" and occupied >= self.FREE_MAX_MEMBERS:
                raise PlanLimitExceeded("Free permite dos miembros, incluidas invitaciones")
            invitation = Invitation(
                self._id(), league_id, email.strip().lower(), Role.MEMBER,
                actor_id, now, expires_at,
            )
            uow.invitations.save(invitation)
            uow.audit.add(
                now, actor_id, "invitation.created", "invitation", invitation.id,
                {"league_id": league_id},
            )
            return invitation

    def revoke(self, actor_id: str, league_id: str, invitation_id: str, now: datetime) -> None:
        with self.store.transaction() as uow:
            actor = self._membership(uow, actor_id, league_id)
            if actor.role not in {Role.OWNER, Role.ADMIN}:
                raise Forbidden("el rol no permite revocar")
            invitation = uow.invitations.get(invitation_id)
            if not invitation or invitation.league_id != league_id:
                raise NotFound("invitación no encontrada")
            if invitation.status is not InvitationStatus.PENDING:
                raise Conflict("la invitación ya no está pendiente")
            invitation.status = InvitationStatus.REVOKED
            uow.invitations.save(invitation)
            uow.audit.add(
                now, actor_id, "invitation.revoked", "invitation", invitation.id
            )

    def accept(self, actor_id: str, invitation_id: str, now: datetime) -> Membership:
        with self.store.transaction() as uow:
            invitation = uow.invitations.get(invitation_id)
            if not invitation:
                raise NotFound("invitación no encontrada")
            if invitation.status is not InvitationStatus.PENDING:
                raise Conflict("la invitación ya no está pendiente")
            if now >= invitation.expires_at:
                invitation.status = InvitationStatus.EXPIRED
                uow.invitations.save(invitation)
                raise Conflict("la invitación ha caducado")
            user = uow.users.get(actor_id)
            if not user or user.email.lower() != invitation.email:
                raise Forbidden("la invitación pertenece a otro email")
            league = uow.leagues.get(invitation.league_id, for_update=True)
            if not league:
                raise NotFound("liga no encontrada")
            active_members = uow.memberships.count_active(league.id)
            if league.plan == "free" and active_members >= self.FREE_MAX_MEMBERS:
                raise PlanLimitExceeded("la liga Free ya está completa")
            membership = Membership(league.id, actor_id, invitation.role, now)
            uow.memberships.save(membership)
            invitation.status = InvitationStatus.ACCEPTED
            invitation.accepted_by = actor_id
            uow.invitations.save(invitation)
            uow.audit.add(
                now, actor_id, "invitation.accepted", "league", league.id
            )
            return membership

    def remove_member(
        self, actor_id: str, league_id: str, user_id: str, now: datetime
    ) -> None:
        with self.store.transaction() as uow:
            actor = self._membership(uow, actor_id, league_id)
            if actor.role not in {Role.OWNER, Role.ADMIN}:
                raise Forbidden("el rol no permite expulsar")
            target = self._membership(uow, user_id, league_id)
            if target.role is Role.OWNER:
                raise Conflict("no se puede expulsar al propietario")
            target.removed_at = now
            uow.memberships.save(target)
            uow.audit.add(
                now, actor_id, "member.removed", "league", league_id,
                {"user_id": user_id},
            )

    @staticmethod
    def _membership(uow, user_id: str, league_id: str) -> Membership:
        membership = uow.memberships.get(league_id, user_id)
        if not membership or membership.removed_at is not None:
            # No revela si la liga existe: evita enumeración entre ligas.
            raise NotFound("liga no encontrada")
        return membership

    @staticmethod
    def _occupied_slots(uow, league_id: str, now: datetime) -> int:
        return (
            uow.memberships.count_active(league_id)
            + uow.invitations.count_pending(league_id, now)
        )
