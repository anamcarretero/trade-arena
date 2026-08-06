"""Cuentas, sesiones, ligas privadas e invitaciones con autorización central."""

from __future__ import annotations

import hashlib
import secrets
import copy
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable

from .models import (
    Competition, CompetitionStatus, CompetitionView, Invitation,
    InvitationStatus, League, LeagueInvitationView, LeagueMemberView, LeagueView,
    ExecutionView, Membership, OrderView, OwnInvitationView, PortfolioView,
    PositionView, Profile, RankingView, Role, TradingAccount, User,
)
from tradearena.ports.identity import IdentityAssertion
from tradearena.ports.store import StoreConflict
from tradearena.domain.competition import build_rules_snapshot
from tradearena.domain.ranking import build_ranking
from tradearena.domain.trading import (
    ExecutionSource, Order, OrderSide, OrderStatus, OrderType, Portfolio,
    Session, TradingEngine,
)
from tradearena.domain.money import decimal, money, price, quantity


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
    INVITATION_TTL = timedelta(days=7)

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

    def get(self, actor_id: str, league_id: str, now: datetime) -> LeagueView:
        with self.store.transaction() as uow:
            actor = self._membership(uow, actor_id, league_id)
            league = uow.leagues.get(league_id)
            if not league:
                raise NotFound("liga no encontrada")
            return self._view(uow, league, actor, now)

    def list_for(self, actor_id: str, now: datetime) -> list[LeagueView]:
        with self.store.transaction() as uow:
            result = []
            for league in uow.leagues.list_for_user(actor_id):
                actor = self._membership(uow, actor_id, league.id)
                result.append(self._view(uow, league, actor, now))
            return result

    def list_invitations(
        self, actor_id: str, now: datetime
    ) -> list[OwnInvitationView]:
        with self.store.transaction() as uow:
            user = uow.users.get(actor_id)
            if not user or user.deleted_at is not None:
                raise Forbidden("cuenta no activa")
            result = []
            for invitation in uow.invitations.list_pending_for_email(
                user.email, now
            ):
                league = uow.leagues.get(invitation.league_id)
                if league and league.active:
                    result.append(OwnInvitationView(
                        invitation.id, league.id, league.name,
                        invitation.expires_at,
                    ))
            return result

    def invite(
        self, actor_id: str, league_id: str, email: str, now: datetime,
    ) -> Invitation:
        with self.store.transaction() as uow:
            actor = self._membership(uow, actor_id, league_id)
            if actor.role not in {Role.OWNER, Role.ADMIN}:
                raise Forbidden("el rol no permite invitar")
            league = uow.leagues.get(league_id, for_update=True)
            if not league:
                raise NotFound("liga no encontrada")
            normalized_email = self._normalize_email(email)
            invited_user = uow.users.get_by_email(normalized_email)
            if invited_user:
                existing = uow.memberships.get(league_id, invited_user.id)
                if existing and existing.removed_at is None:
                    raise Conflict("esa persona ya pertenece a la liga")
            occupied = self._occupied_slots(uow, league_id, now)
            if league.plan == "free" and occupied >= self.FREE_MAX_MEMBERS:
                raise PlanLimitExceeded("Free permite dos miembros, incluidas invitaciones")
            invitation = Invitation(
                self._id(), league_id, normalized_email, Role.MEMBER,
                actor_id, now, now + self.INVITATION_TTL,
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
        membership = None
        expired = False
        with self.store.transaction() as uow:
            invitation = uow.invitations.get(invitation_id)
            if not invitation:
                raise NotFound("invitación no encontrada")
            if invitation.status is not InvitationStatus.PENDING:
                raise NotFound("invitación no encontrada")
            user = uow.users.get(actor_id)
            if not user or user.email.lower() != invitation.email:
                raise NotFound("invitación no encontrada")
            if now >= invitation.expires_at:
                invitation.status = InvitationStatus.EXPIRED
                uow.invitations.save(invitation)
                uow.audit.add(
                    now, actor_id, "invitation.expired", "invitation",
                    invitation.id,
                )
                expired = True
            else:
                league = uow.leagues.get(invitation.league_id, for_update=True)
                if not league:
                    raise NotFound("liga no encontrada")
                existing = uow.memberships.get(league.id, actor_id)
                if existing and existing.removed_at is None:
                    raise NotFound("invitación no encontrada")
                active_members = uow.memberships.count_active(league.id)
                if league.plan == "free" \
                        and active_members >= self.FREE_MAX_MEMBERS:
                    raise PlanLimitExceeded("la liga Free ya está completa")
                membership = Membership(league.id, actor_id, invitation.role, now)
                uow.memberships.save(membership)
                for competition in uow.competitions.list_for_league(league.id):
                    if competition.status is CompetitionStatus.ACTIVE \
                            and competition.rules_snapshot \
                            and uow.trading.get(competition.id, actor_id) is None:
                        initial = Decimal(str(
                            competition.rules_snapshot["rules"]["initial_capital"]
                        ))
                        uow.trading.add(TradingAccount(
                            competition.id, actor_id, now, True,
                            Portfolio(self._id(), initial),
                        ))
                        uow.audit.add(
                            now, actor_id, "competition.joined_late",
                            "competition", competition.id,
                            {"initial_capital": str(money(initial))},
                        )
                invitation.status = InvitationStatus.ACCEPTED
                invitation.accepted_by = actor_id
                uow.invitations.save(invitation)
                uow.audit.add(
                    now, actor_id, "invitation.accepted", "league", league.id
                )
        if expired:
            raise NotFound("invitación no encontrada")
        assert membership is not None
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

    def _view(
        self, uow, league: League, actor: Membership, now: datetime
    ) -> LeagueView:
        members = []
        role_order = {Role.OWNER: 0, Role.ADMIN: 1, Role.MEMBER: 2}
        active_members = sorted(
            uow.memberships.list_active_for_league(league.id),
            key=lambda membership: (
                role_order[membership.role], membership.joined_at,
                membership.user_id,
            ),
        )
        for membership in active_members:
            profile = uow.profiles.get(membership.user_id)
            members.append(LeagueMemberView(
                membership.user_id,
                profile.display_name if profile else "",
                membership.role,
                membership.joined_at,
            ))
        invitations = ()
        if actor.role in {Role.OWNER, Role.ADMIN}:
            invitations = tuple(
                LeagueInvitationView(
                    invitation.id, invitation.email, invitation.role,
                    invitation.expires_at, invitation.status,
                )
                for invitation in uow.invitations.list_for_league(league.id)
                if invitation.status is InvitationStatus.PENDING
                and invitation.expires_at > now
            )
        return LeagueView(
            league.id, league.name, league.owner_id, league.created_at,
            league.active, league.plan, actor.role, self.FREE_MAX_MEMBERS,
            tuple(members), invitations,
        )

    @staticmethod
    def _normalize_email(email: str) -> str:
        normalized = email.strip().lower()
        if len(normalized) > 254 or normalized.count("@") != 1 \
                or any(character.isspace() for character in normalized):
            raise InvalidInput("el email de la invitación no es válido")
        local, domain = normalized.split("@", 1)
        if not local or not domain or "." not in domain:
            raise InvalidInput("el email de la invitación no es válido")
        return normalized


class CompetitionService:
    """Gestiona borradores y fija las reglas vigentes al comenzar."""

    def __init__(
        self, store, id_factory: Callable[[], str],
        rules_factory: Callable[[Competition, League], dict[str, object]] | None = None,
    ) -> None:
        self.store = store
        self._id = id_factory
        self._rules_factory = rules_factory or self._current_rules

    def create(
        self, actor_id: str, league_id: str, name: str,
        starts_at: datetime, ends_at: datetime, now: datetime,
    ) -> CompetitionView:
        self._validate_schedule(starts_at, ends_at)
        with self.store.transaction() as uow:
            actor = LeagueService._membership(uow, actor_id, league_id)
            if actor.role not in {Role.OWNER, Role.ADMIN}:
                raise Forbidden("el rol no permite crear competiciones")
            league = uow.leagues.get(league_id)
            if not league or not league.active:
                raise NotFound("liga no encontrada")
            competition = Competition(
                self._id(), league_id, name.strip(), starts_at, ends_at,
            )
            if not competition.name:
                raise InvalidInput("el nombre de competición es obligatorio")
            uow.competitions.add(competition)
            uow.audit.add(
                now, actor_id, "competition.created", "competition",
                competition.id, {"league_id": league_id},
            )
            return self._view(competition)

    def list_for(self, actor_id: str, league_id: str) -> list[CompetitionView]:
        with self.store.transaction() as uow:
            LeagueService._membership(uow, actor_id, league_id)
            if not uow.leagues.get(league_id):
                raise NotFound("liga no encontrada")
            return [self._view(item) for item in uow.competitions.list_for_league(league_id)]

    def get(
        self, actor_id: str, league_id: str, competition_id: str,
    ) -> CompetitionView:
        with self.store.transaction() as uow:
            LeagueService._membership(uow, actor_id, league_id)
            competition = uow.competitions.get(competition_id)
            if not competition or competition.league_id != league_id:
                raise NotFound("competición no encontrada")
            return self._view(competition)

    def start(
        self, actor_id: str, league_id: str, competition_id: str, now: datetime,
    ) -> CompetitionView:
        with self.store.transaction() as uow:
            actor = LeagueService._membership(uow, actor_id, league_id)
            league = uow.leagues.get(league_id, for_update=True)
            competition = uow.competitions.get(competition_id, for_update=True)
            if not league or not competition or competition.league_id != league_id:
                raise NotFound("competición no encontrada")
            if actor.role not in {Role.OWNER, Role.ADMIN}:
                raise Forbidden("el rol no permite iniciar competiciones")
            if competition.status is not CompetitionStatus.DRAFT:
                raise Conflict("la competición ya se ha iniciado")
            # El snapshot se materializa aquí, no al crear el borrador. La copia
            # profunda evita compartir referencias con la configuración vigente.
            competition.rules_snapshot = copy.deepcopy(
                self._rules_factory(competition, league)
            )
            competition.status = CompetitionStatus.ACTIVE
            competition.started_at = now
            uow.competitions.save(competition)
            initial_cash = Decimal(str(
                competition.rules_snapshot["rules"]["initial_capital"]
            ))
            for membership in uow.memberships.list_active_for_league(league_id):
                uow.trading.add(TradingAccount(
                    competition.id, membership.user_id, now, False,
                    Portfolio(self._id(), initial_cash),
                ))
            uow.audit.add(
                now, actor_id, "competition.started", "competition",
                competition.id, {"league_id": league_id, "rules_version": "1"},
            )
            return self._view(competition)

    @classmethod
    def _current_rules(
        cls, competition: Competition, league: League,
    ) -> dict[str, object]:
        return build_rules_snapshot(
            competition.starts_at, competition.ends_at, league.plan,
        )

    @staticmethod
    def _validate_schedule(starts_at: datetime, ends_at: datetime) -> None:
        if starts_at.tzinfo is None or ends_at.tzinfo is None:
            raise InvalidInput("el calendario necesita zona horaria")
        if ends_at <= starts_at:
            raise InvalidInput("el fin debe ser posterior al inicio")

    @staticmethod
    def _view(competition: Competition) -> CompetitionView:
        return CompetitionView(
            competition.id, competition.league_id, competition.name,
            competition.starts_at, competition.ends_at, competition.status,
            copy.deepcopy(competition.rules_snapshot), competition.started_at,
        )


class TradingService:
    """Carteras privadas y ejecución reproducible con mercado inyectado."""

    def __init__(self, store, id_factory: Callable[[], str], market) -> None:
        self.store = store
        self._id = id_factory
        self.market = market

    def portfolio(
        self, actor_id: str, league_id: str, competition_id: str, now: datetime,
    ) -> PortfolioView:
        with self.store.transaction() as uow:
            competition, account = self._account(
                uow, actor_id, league_id, competition_id, now, for_update=True,
            )
            self._process_available_quotes(account, competition, now)
            uow.trading.save(account)
            self._finish_if_ended(uow, competition, actor_id, now)
            return self._portfolio_view(account, competition, now)

    def submit_order(
        self, actor_id: str, league_id: str, competition_id: str,
        symbol: str, side: str, quantity_value: str, order_type: str,
        allow_extended_hours: bool, limit_price: str | None, now: datetime,
        client_order_id: str | None = None,
    ) -> PortfolioView:
        with self.store.transaction() as uow:
            competition, account = self._account(
                uow, actor_id, league_id, competition_id, now, for_update=True,
            )
            self._within_calendar(competition, now)
            order_id = (
                f"{account.portfolio.id}-{client_order_id}"
                if client_order_id else self._id()
            )
            existing = account.portfolio.orders.get(order_id)
            normalized_quantity = quantity(quantity_value)
            if existing:
                expected = (
                    existing.symbol, existing.side.value, existing.quantity,
                    existing.order_type.value, existing.allow_extended_hours,
                    str(existing.limit_price) if existing.limit_price is not None else None,
                )
                requested = (
                    symbol.strip().upper(), side, normalized_quantity, order_type,
                    allow_extended_hours,
                    str(price(limit_price)) if limit_price is not None else None,
                )
                if expected != requested:
                    raise Conflict("la clave idempotente ya pertenece a otra orden")
            else:
                order = Order(
                    order_id, symbol.strip(), OrderSide(side), normalized_quantity,
                    OrderType(order_type), allow_extended_hours, now,
                    price(limit_price) if limit_price is not None else None,
                )
                self._engine(competition).submit(account.portfolio, order)
                uow.audit.add(
                    now, actor_id, "order.submitted", "order", order.id,
                    {"competition_id": competition.id},
                )
            self._process_available_quotes(account, competition, now)
            uow.trading.save(account)
            return self._portfolio_view(account, competition, now)

    def report_trade(
        self, actor_id: str, league_id: str, competition_id: str, *,
        occurred_at: datetime, symbol: str, side: str, quantity_value: str,
        price_per_share: str, total_amount: str, currency: str, fx_rate: str,
        client_trade_id: str, now: datetime,
    ) -> PortfolioView:
        with self.store.transaction() as uow:
            competition, account = self._account(
                uow, actor_id, league_id, competition_id, now,
                for_update=True,
            )
            order_id = f"{account.portfolio.id}-reported-{client_trade_id}"
            normalized_symbol = symbol.strip().upper()
            normalized_quantity = quantity(quantity_value)
            normalized_price = price(price_per_share)
            normalized_total = money(total_amount)
            normalized_currency = currency.strip().upper()
            normalized_fx = decimal(fx_rate)
            requested_side = OrderSide(side)
            existing_order = account.portfolio.orders.get(order_id)
            if existing_order:
                existing_execution = next(
                    (item for item in account.portfolio.executions
                     if item.order_id == order_id), None
                )
                if existing_execution is None or (
                    existing_order.symbol, existing_order.side,
                    existing_order.quantity, existing_execution.price,
                    existing_execution.total_amount, existing_execution.currency,
                    existing_execution.fx_rate, existing_execution.executed_at,
                ) != (
                    normalized_symbol, requested_side, normalized_quantity,
                    normalized_price, normalized_total, normalized_currency,
                    normalized_fx, occurred_at,
                ):
                    raise Conflict(
                        "la clave idempotente ya pertenece a otra operación"
                    )
                return self._portfolio_view(account, competition, now)

            self._validate_reported_date(competition, account, occurred_at, now)
            if normalized_currency != "USD" or normalized_fx != Decimal("1"):
                raise InvalidInput("v1 solo admite USD con FX Rate 1")
            commissions = competition.rules_snapshot["rules"]["commissions"]
            gross = money(normalized_price * normalized_quantity)
            matching = []
            for session, configured in (
                (Session.REGULAR, commissions["regular"]),
                (Session.EXTENDED, commissions["extended"]),
            ):
                fee = money(Decimal(str(configured)))
                expected = money(
                    gross + fee if requested_side is OrderSide.BUY else gross - fee
                )
                if expected == normalized_total:
                    matching.append((session, fee))
            if not matching:
                raise InvalidInput(
                    "el total no coincide al céntimo con precio, cantidad y comisión"
                )
            session, commission = matching[0]
            order = Order(
                order_id, normalized_symbol, requested_side, normalized_quantity,
                OrderType.MARKET, session is Session.EXTENDED, occurred_at,
            )
            try:
                self._engine(competition).record_reported(
                    account.portfolio, order, execution_price=normalized_price,
                    commission=commission, total_amount=normalized_total,
                    executed_at=occurred_at, session=session,
                    currency=normalized_currency, fx_rate=normalized_fx,
                )
            except ValueError as exc:
                if str(exc) in {"saldo insuficiente", "posición insuficiente"}:
                    raise Conflict(str(exc)) from exc
                raise InvalidInput(str(exc)) from exc
            uow.trading.save(account)
            uow.audit.add(
                now, actor_id, "reported_trade.created", "order", order.id,
                {"competition_id": competition.id, "source": "reported",
                 "executed_at": occurred_at.isoformat()},
            )
            return self._portfolio_view(account, competition, now)

    def correct_reported_trade(
        self, actor_id: str, league_id: str, competition_id: str,
        execution_id: str, *, occurred_at: datetime, client_trade_id: str,
        now: datetime,
    ) -> PortfolioView:
        with self.store.transaction() as uow:
            competition, account = self._account(
                uow, actor_id, league_id, competition_id, now, for_update=True,
            )
            original = next(
                (item for item in account.portfolio.executions
                 if item.id == execution_id), None
            )
            if original is None or original.source is not ExecutionSource.REPORTED \
                    or original.correction_of is not None:
                raise NotFound("operación no encontrada")
            order_id = f"{account.portfolio.id}-correction-{client_trade_id}"
            existing = account.portfolio.orders.get(order_id)
            if existing:
                correction = next(
                    (item for item in account.portfolio.executions
                     if item.order_id == order_id), None
                )
                if correction is None or correction.correction_of != original.id \
                        or correction.executed_at != occurred_at:
                    raise Conflict(
                        "la clave idempotente ya pertenece a otra corrección"
                    )
                return self._portfolio_view(account, competition, now)
            self._validate_reported_date(competition, account, occurred_at, now)
            opposite = (
                OrderSide.SELL if original.side is OrderSide.BUY else OrderSide.BUY
            )
            order = Order(
                order_id, original.symbol, opposite, original.quantity,
                OrderType.MARKET, original.session is Session.EXTENDED,
                occurred_at,
            )
            try:
                self._engine(competition).correct_reported(
                    account.portfolio, original, order, corrected_at=occurred_at,
                )
            except ValueError as exc:
                raise Conflict(str(exc)) from exc
            uow.trading.save(account)
            uow.audit.add(
                now, actor_id, "reported_trade.corrected", "execution", original.id,
                {"competition_id": competition.id,
                 "compensating_order_id": order.id},
            )
            return self._portfolio_view(account, competition, now)

    def cancel_order(
        self, actor_id: str, league_id: str, competition_id: str,
        order_id: str, now: datetime,
    ) -> PortfolioView:
        with self.store.transaction() as uow:
            competition, account = self._account(
                uow, actor_id, league_id, competition_id, now, for_update=True,
            )
            order = account.portfolio.orders.get(order_id)
            if not order:
                raise NotFound("orden no encontrada")
            try:
                self._engine(competition).cancel(account.portfolio, order_id)
            except ValueError as exc:
                raise Conflict(str(exc)) from exc
            uow.trading.save(account)
            uow.audit.add(now, actor_id, "order.cancelled", "order", order_id)
            return self._portfolio_view(account, competition, now)

    def ranking(
        self, actor_id: str, league_id: str, competition_id: str, now: datetime,
    ) -> RankingView:
        with self.store.transaction() as uow:
            competition, _ = self._account(
                uow, actor_id, league_id, competition_id, now, for_update=True,
            )
            snapshots = []
            for account in uow.trading.list_for_competition(competition_id):
                self._process_available_quotes(account, competition, now)
                uow.trading.save(account)
                prices = self._valuation_prices(account, competition, now)
                snapshots.append((
                    account.user_id, account.portfolio.snapshot(prices, now),
                    account.joined_late,
                ))
            snapshot = build_ranking(competition_id, now, snapshots)
            uow.trading.save_ranking(snapshot)
            self._finish_if_ended(uow, competition, actor_id, now)
            rows = tuple({
                "rank": row.rank, "user_id": row.user_id,
                "portfolio_id": row.portfolio_id,
                "cumulative_return": row.cumulative_return,
                "joined_late": row.joined_late,
                "display_name": self._display_name(uow, row.user_id),
            } for row in snapshot.rows)
            return RankingView(competition_id, now, rows, snapshot.digest)

    def _account(
        self, uow, actor_id: str, league_id: str, competition_id: str,
        now: datetime, *, for_update: bool,
    ) -> tuple[Competition, TradingAccount]:
        membership = LeagueService._membership(uow, actor_id, league_id)
        competition = uow.competitions.get(competition_id, for_update=for_update)
        if not competition or competition.league_id != league_id \
                or competition.status is CompetitionStatus.DRAFT \
                or not competition.rules_snapshot or not competition.started_at:
            raise NotFound("competición no encontrada")
        account = uow.trading.get(competition_id, actor_id, for_update=for_update)
        if account is None:
            initial = Decimal(str(
                competition.rules_snapshot["rules"]["initial_capital"]
            ))
            account = TradingAccount(
                competition_id, actor_id, membership.joined_at, True,
                Portfolio(self._id(), initial),
            )
            uow.trading.add(account)
            uow.audit.add(
                now, actor_id, "competition.joined_late", "competition",
                competition_id, {"initial_capital": str(money(initial))},
            )
        return competition, account

    @staticmethod
    def _within_calendar(competition: Competition, now: datetime) -> None:
        calendar = competition.rules_snapshot["calendar"]
        starts_at = datetime.fromisoformat(str(calendar["starts_at"]))
        ends_at = datetime.fromisoformat(str(calendar["ends_at"]))
        if competition.status is not CompetitionStatus.ACTIVE \
                or now < starts_at or now > ends_at:
            raise Conflict("la competición no admite órdenes en este momento")

    @staticmethod
    def _validate_reported_date(
        competition: Competition, account: TradingAccount, occurred_at: datetime,
        now: datetime,
    ) -> None:
        if occurred_at.tzinfo is None:
            raise InvalidInput("la fecha necesita zona horaria")
        calendar = competition.rules_snapshot["calendar"]
        starts_at = datetime.fromisoformat(str(calendar["starts_at"]))
        ends_at = datetime.fromisoformat(str(calendar["ends_at"]))
        if competition.status is not CompetitionStatus.ACTIVE:
            raise Conflict("la competición no admite operaciones declaradas")
        if occurred_at > now:
            raise Conflict("la fecha de la operación no puede ser futura")
        if occurred_at < starts_at or occurred_at > ends_at:
            raise Conflict("la fecha queda fuera del calendario fijado")
        if occurred_at < account.joined_at:
            raise Conflict("la fecha precede a la incorporación del participante")
        latest = max(
            (item.executed_at for item in account.portfolio.executions),
            default=None,
        )
        if latest is not None and occurred_at < latest:
            raise Conflict("las operaciones deben registrarse cronológicamente")

    @staticmethod
    def _engine(competition: Competition) -> TradingEngine:
        commissions = competition.rules_snapshot["rules"]["commissions"]
        return TradingEngine(
            Decimal(str(commissions["regular"])),
            Decimal(str(commissions["extended"])),
        )

    def _process_available_quotes(
        self, account: TradingAccount, competition: Competition, now: datetime,
    ) -> None:
        calendar = competition.rules_snapshot["calendar"]
        starts_at = datetime.fromisoformat(str(calendar["starts_at"]))
        ends_at = datetime.fromisoformat(str(calendar["ends_at"]))
        upper = min(now, ends_at)
        engine = self._engine(competition)
        symbols = sorted({order.symbol for order in account.portfolio.orders.values()
                          if order.status is OrderStatus.PENDING})
        for symbol in symbols:
            if self.market.definitively_suspended(symbol, upper):
                for order_id, order in tuple(account.portfolio.orders.items()):
                    if order.symbol == symbol and order.status is OrderStatus.PENDING:
                        account.portfolio.orders[order_id] = replace(
                            order, status=OrderStatus.CANCELLED,
                            rejection_reason="instrument_suspended",
                        )
                continue
            for quote in sorted(
                self.market.quotes(symbol, starts_at, upper),
                key=lambda item: item.observed_at,
            ):
                engine.process_quote(account.portfolio, quote)
        if now >= ends_at:
            engine.close_pending(account.portfolio, "competition_ended")

    def _valuation_prices(
        self, account: TradingAccount, competition: Competition, now: datetime,
    ) -> dict[str, Decimal]:
        calendar = competition.rules_snapshot["calendar"]
        starts_at = datetime.fromisoformat(str(calendar["starts_at"]))
        ends_at = datetime.fromisoformat(str(calendar["ends_at"]))
        result = {}
        for symbol in account.portfolio.positions:
            quotes = sorted(self.market.quotes(symbol, starts_at, min(now, ends_at)),
                            key=lambda item: item.observed_at)
            if quotes:
                result[symbol] = quotes[-1].value
                continue
            executions = [item for item in account.portfolio.executions
                          if item.symbol == symbol]
            if not executions:
                raise Conflict(f"no existe cotización para {symbol}")
            result[symbol] = executions[-1].price
        return result

    @staticmethod
    def _finish_if_ended(uow, competition: Competition, actor_id: str, now: datetime) -> None:
        ends_at = datetime.fromisoformat(str(
            competition.rules_snapshot["calendar"]["ends_at"]
        ))
        if now >= ends_at and competition.status is CompetitionStatus.ACTIVE:
            competition.status = CompetitionStatus.FINISHED
            uow.competitions.save(competition)
            uow.audit.add(
                now, actor_id, "competition.finished", "competition",
                competition.id,
            )

    def _portfolio_view(
        self, account: TradingAccount, competition: Competition, now: datetime,
    ) -> PortfolioView:
        prices = self._valuation_prices(account, competition, now)
        portfolio = account.portfolio
        positions = tuple(PositionView(
            symbol, str(quantity),
            str(prices[symbol]) if symbol in prices else None,
            str(money(prices[symbol] * quantity)) if symbol in prices else None,
        ) for symbol, quantity in sorted(portfolio.positions.items()))
        orders = tuple(OrderView(
            item.id, item.symbol, item.side.value, str(item.quantity),
            item.order_type.value, item.allow_extended_hours,
            str(item.limit_price) if item.limit_price is not None else None,
            item.status.value, item.rejection_reason, item.submitted_at,
        ) for item in sorted(portfolio.orders.values(), key=lambda item: (item.submitted_at, item.id)))
        executions = tuple(ExecutionView(
            item.id, item.order_id, item.symbol, item.side.value, str(item.quantity),
            str(item.price), str(item.commission), item.session.value,
            item.executed_at, item.source.value,
            str(item.total_amount) if item.total_amount is not None else None,
            item.currency, str(item.fx_rate), item.correction_of,
        ) for item in sorted(portfolio.executions, key=lambda item: (item.executed_at, item.id)))
        return PortfolioView(
            portfolio.id, competition.id, account.user_id, "USD",
            str(portfolio.initial_cash), str(portfolio.cash), account.joined_at,
            account.joined_late, positions, orders, executions,
            str(portfolio.equity(prices)), str(portfolio.cumulative_return(prices)),
        )

    @staticmethod
    def _display_name(uow, user_id: str) -> str:
        profile = uow.profiles.get(user_id)
        return profile.display_name if profile else user_id
