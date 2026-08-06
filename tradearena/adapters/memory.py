"""Unidad de trabajo transaccional en memoria para desarrollo y contratos."""

from __future__ import annotations

import copy
import threading
from contextlib import contextmanager
from datetime import datetime

from tradearena.application.models import (
    AuditEvent, Competition, Invitation, InvitationStatus, League, Membership,
    Profile, TradingAccount, User,
)
from tradearena.domain.ranking import RankingSnapshot


class MemoryUsers:
    def __init__(self, store: "MemoryStore") -> None:
        self.store = store

    def get(self, user_id: str, *, for_update: bool = False) -> User | None:
        return self.store._users.get(user_id)

    def get_by_identity(self, provider: str, subject: str) -> User | None:
        user_id = self.store._users_by_identity.get((provider, subject))
        return self.get(user_id or "")

    def get_by_email(self, email: str) -> User | None:
        user_id = self.store._users_by_email.get(email.lower())
        return self.get(user_id or "")

    def add(self, user: User) -> None:
        self.store._users[user.id] = user
        self.store._users_by_email[user.email.lower()] = user.id

    def save(self, user: User) -> None:
        self.store._users[user.id] = user
        self.store._users_by_email = {
            email: user_id for email, user_id in self.store._users_by_email.items()
            if user_id != user.id
        }
        self.store._users_by_email[user.email.lower()] = user.id

    def link_identity(
        self, provider: str, subject: str, user_id: str, email_verified: bool
    ) -> None:
        self.store._users_by_identity[(provider, subject)] = user_id

    def delete_identities(self, user_id: str) -> None:
        self.store._users_by_identity = {
            identity: linked_id
            for identity, linked_id in self.store._users_by_identity.items()
            if linked_id != user_id
        }


class MemoryProfiles:
    def __init__(self, store: "MemoryStore") -> None:
        self.store = store

    def get(self, user_id: str) -> Profile | None:
        return self.store._profiles.get(user_id)

    def save(self, profile: Profile) -> None:
        self.store._profiles[profile.user_id] = profile

    def delete(self, user_id: str) -> None:
        self.store._profiles.pop(user_id, None)


class MemorySessions:
    def __init__(self, store: "MemoryStore") -> None:
        self.store = store

    def get(self, token_hash: str) -> tuple[str, datetime] | None:
        return self.store._sessions.get(token_hash)

    def add(
        self, token_hash: str, user_id: str, created_at: datetime, expires_at: datetime
    ) -> None:
        self.store._sessions[token_hash] = (user_id, expires_at)

    def revoke(self, token_hash: str, revoked_at: datetime) -> None:
        self.store._sessions.pop(token_hash, None)

    def revoke_for_user(self, user_id: str, revoked_at: datetime) -> None:
        self.store._sessions = {
            token: session for token, session in self.store._sessions.items()
            if session[0] != user_id
        }


class MemoryLeagues:
    def __init__(self, store: "MemoryStore") -> None:
        self.store = store

    def get(self, league_id: str, *, for_update: bool = False) -> League | None:
        return self.store._leagues.get(league_id)

    def add(self, league: League) -> None:
        self.store._leagues[league.id] = league

    def list_for_user(self, user_id: str) -> list[League]:
        allowed = {
            league_id for (league_id, member_id), membership
            in self.store._memberships.items()
            if member_id == user_id and membership.removed_at is None
        }
        return [league for league in self.store._leagues.values() if league.id in allowed]

    def count_active_free_owned(self, owner_id: str) -> int:
        return sum(
            1 for league in self.store._leagues.values()
            if league.owner_id == owner_id and league.active and league.plan == "free"
        )


class MemoryMemberships:
    def __init__(self, store: "MemoryStore") -> None:
        self.store = store

    def get(self, league_id: str, user_id: str) -> Membership | None:
        return self.store._memberships.get((league_id, user_id))

    def save(self, membership: Membership) -> None:
        self.store._memberships[(membership.league_id, membership.user_id)] = membership

    def list_for_user(self, user_id: str) -> list[Membership]:
        return [
            membership for membership in self.store._memberships.values()
            if membership.user_id == user_id
        ]

    def list_active_for_league(self, league_id: str) -> list[Membership]:
        return sorted(
            (
                membership for membership in self.store._memberships.values()
                if membership.league_id == league_id
                and membership.removed_at is None
            ),
            key=lambda membership: (membership.joined_at, membership.user_id),
        )

    def count_active(self, league_id: str) -> int:
        return sum(
            1 for membership in self.store._memberships.values()
            if membership.league_id == league_id and membership.removed_at is None
        )

    def remove_active_for_user(self, user_id: str, removed_at: datetime) -> None:
        for membership in self.store._memberships.values():
            if membership.user_id == user_id and membership.removed_at is None:
                membership.removed_at = removed_at


class MemoryInvitations:
    def __init__(self, store: "MemoryStore") -> None:
        self.store = store

    def get(self, invitation_id: str) -> Invitation | None:
        return self.store._invitations.get(invitation_id)

    def save(self, invitation: Invitation) -> None:
        self.store._invitations[invitation.id] = invitation

    def list_for_email(self, email: str) -> list[Invitation]:
        return [
            invitation for invitation in self.store._invitations.values()
            if invitation.email == email.lower()
        ]

    def list_pending_for_email(
        self, email: str, now: datetime
    ) -> list[Invitation]:
        return [
            invitation for invitation in self.list_for_email(email)
            if invitation.status is InvitationStatus.PENDING
            and invitation.expires_at > now
        ]

    def list_for_league(self, league_id: str) -> list[Invitation]:
        return sorted(
            (
                invitation for invitation in self.store._invitations.values()
                if invitation.league_id == league_id
            ),
            key=lambda invitation: (invitation.created_at, invitation.id),
        )

    def count_pending(self, league_id: str, now: datetime) -> int:
        return sum(
            1 for invitation in self.store._invitations.values()
            if invitation.league_id == league_id
            and invitation.status is InvitationStatus.PENDING
            and invitation.expires_at > now
        )


class MemoryCompetitions:
    def __init__(self, store: "MemoryStore") -> None:
        self.store = store

    def get(
        self, competition_id: str, *, for_update: bool = False
    ) -> Competition | None:
        competition = self.store._competitions.get(competition_id)
        return copy.deepcopy(competition)

    def add(self, competition: Competition) -> None:
        self.store._competitions[competition.id] = copy.deepcopy(competition)

    def save(self, competition: Competition) -> None:
        current = self.store._competitions.get(competition.id)
        if current and current.rules_snapshot is not None \
                and current.rules_snapshot != competition.rules_snapshot:
            raise ValueError("rules_snapshot es inmutable")
        self.store._competitions[competition.id] = copy.deepcopy(competition)

    def list_for_league(self, league_id: str) -> list[Competition]:
        return sorted(
            (
                copy.deepcopy(item) for item in self.store._competitions.values()
                if item.league_id == league_id
            ),
            key=lambda item: (item.starts_at, item.id),
        )


class MemoryTrading:
    def __init__(self, store: "MemoryStore") -> None:
        self.store = store

    def get(
        self, competition_id: str, user_id: str, *, for_update: bool = False,
    ) -> TradingAccount | None:
        return copy.deepcopy(self.store._trading.get((competition_id, user_id)))

    def add(self, account: TradingAccount) -> None:
        key = (account.competition_id, account.user_id)
        if key in self.store._trading:
            raise ValueError("la cartera ya existe")
        self.store._trading[key] = copy.deepcopy(account)

    def save(self, account: TradingAccount) -> None:
        self.store._trading[(account.competition_id, account.user_id)] = copy.deepcopy(account)

    def list_for_competition(self, competition_id: str) -> list[TradingAccount]:
        return sorted(
            (copy.deepcopy(item) for item in self.store._trading.values()
             if item.competition_id == competition_id),
            key=lambda item: (item.joined_at, item.user_id),
        )

    def save_ranking(self, snapshot: RankingSnapshot) -> None:
        key = (snapshot.competition_id, snapshot.as_of)
        current = self.store._rankings.get(key)
        if current and current.digest != snapshot.digest:
            raise ValueError("snapshot de ranking no reproducible")
        self.store._rankings[key] = copy.deepcopy(snapshot)

    def latest_ranking(self, competition_id: str) -> RankingSnapshot | None:
        items = [item for (candidate, _), item in self.store._rankings.items()
                 if candidate == competition_id]
        return copy.deepcopy(max(items, key=lambda item: item.as_of)) if items else None


class MemoryAudit:
    def __init__(self, store: "MemoryStore") -> None:
        self.store = store

    def add(
        self, occurred_at: datetime, actor_id: str | None, action: str,
        resource_type: str, resource_id: str, metadata: dict[str, str] | None = None,
    ) -> None:
        self.store._audit.append(AuditEvent(
            len(self.store._audit) + 1, occurred_at, actor_id, action,
            resource_type, resource_id, metadata or {},
        ))


class MemoryStore:
    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._users_by_identity: dict[tuple[str, str], str] = {}
        self._users_by_email: dict[str, str] = {}
        self._profiles: dict[str, Profile] = {}
        self._leagues: dict[str, League] = {}
        self._memberships: dict[tuple[str, str], Membership] = {}
        self._invitations: dict[str, Invitation] = {}
        self._competitions: dict[str, Competition] = {}
        self._trading: dict[tuple[str, str], TradingAccount] = {}
        self._rankings: dict[tuple[str, datetime], RankingSnapshot] = {}
        self._sessions: dict[str, tuple[str, datetime]] = {}
        self._audit: list[AuditEvent] = []
        self._lock = threading.RLock()
        self.users = MemoryUsers(self)
        self.profiles = MemoryProfiles(self)
        self.sessions = MemorySessions(self)
        self.leagues = MemoryLeagues(self)
        self.memberships = MemoryMemberships(self)
        self.invitations = MemoryInvitations(self)
        self.competitions = MemoryCompetitions(self)
        self.trading = MemoryTrading(self)
        self.audit = MemoryAudit(self)

    @contextmanager
    def transaction(self):
        with self._lock:
            names = (
                "_users", "_users_by_identity", "_users_by_email", "_profiles",
                "_leagues", "_memberships", "_invitations", "_sessions", "_audit",
                "_competitions", "_trading", "_rankings",
            )
            state = copy.deepcopy({name: getattr(self, name) for name in names})
            try:
                yield self
            except Exception:
                for name, value in state.items():
                    setattr(self, name, value)
                raise

    def ready(self) -> bool:
        return True

    @property
    def audit_events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._audit)
