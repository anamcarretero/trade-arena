"""Repositorios PostgreSQL síncronos sobre una unidad de trabajo psycopg 3."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import datetime

import psycopg
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from tradearena.application.models import (
    Competition, CompetitionStatus, Invitation, InvitationStatus, League,
    Membership, Profile, Role, User,
)
from tradearena.ports.store import StoreConflict


def _user(row) -> User | None:
    if row is None:
        return None
    return User(
        str(row["id"]), row["email"], row["identity_provider"],
        row["identity_subject"], row["created_at"], row["deleted_at"],
    )


def _league(row) -> League | None:
    if row is None:
        return None
    return League(
        str(row["id"]), row["name"], str(row["owner_id"]), row["created_at"],
        row["active"], row["plan"],
    )


def _competition(row) -> Competition | None:
    if row is None:
        return None
    return Competition(
        str(row["id"]), str(row["league_id"]), row["name"], row["starts_at"],
        row["ends_at"], CompetitionStatus(row["status"]), row["rules_snapshot"],
        row["started_at"],
    )


class _Repository:
    def __init__(self, store: "PostgresStore") -> None:
        self.store = store

    @property
    def connection(self):
        connection = getattr(self.store._local, "connection", None)
        if connection is None:
            raise RuntimeError("el repositorio requiere una transacción activa")
        return connection


class PostgresUsers(_Repository):
    _SELECT = """
        SELECT u.id, u.email, u.created_at, u.deleted_at,
               COALESCE(i.provider, 'email') AS identity_provider,
               COALESCE(i.subject, u.email) AS identity_subject
          FROM users u
          LEFT JOIN LATERAL (
              SELECT provider, subject FROM identities
               WHERE user_id = u.id ORDER BY provider, subject LIMIT 1
          ) i ON true
    """

    def get(self, user_id: str, *, for_update: bool = False) -> User | None:
        suffix = " FOR UPDATE OF u" if for_update else ""
        row = self.connection.execute(
            self._SELECT + " WHERE u.id = %s" + suffix, (user_id,)
        ).fetchone()
        return _user(row)

    def get_by_identity(self, provider: str, subject: str) -> User | None:
        row = self.connection.execute(
            """
            SELECT u.id, u.email, u.created_at, u.deleted_at,
                   i.provider AS identity_provider, i.subject AS identity_subject
              FROM identities i JOIN users u ON u.id = i.user_id
             WHERE i.provider = %s AND i.subject = %s
            """,
            (provider, subject),
        ).fetchone()
        return _user(row)

    def get_by_email(self, email: str) -> User | None:
        row = self.connection.execute(
            self._SELECT + " WHERE lower(u.email) = lower(%s)", (email,)
        ).fetchone()
        return _user(row)

    def add(self, user: User) -> None:
        self.connection.execute(
            """
            INSERT INTO users(id, email, status, created_at, deleted_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user.id, user.email, "deleted" if user.deleted_at else "active",
             user.created_at, user.deleted_at),
        )

    def save(self, user: User) -> None:
        self.connection.execute(
            """
            UPDATE users SET email = %s, status = %s, deleted_at = %s
             WHERE id = %s
            """,
            (user.email, "deleted" if user.deleted_at else "active",
             user.deleted_at, user.id),
        )

    def link_identity(
        self, provider: str, subject: str, user_id: str, email_verified: bool
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO identities(provider, subject, user_id, email_verified)
            VALUES (%s, %s, %s, %s)
            """,
            (provider, subject, user_id, email_verified),
        )

    def delete_identities(self, user_id: str) -> None:
        self.connection.execute("DELETE FROM identities WHERE user_id = %s", (user_id,))


class PostgresProfiles(_Repository):
    def get(self, user_id: str) -> Profile | None:
        row = self.connection.execute(
            "SELECT * FROM profiles WHERE user_id = %s", (user_id,)
        ).fetchone()
        if row is None:
            return None
        return Profile(
            str(row["user_id"]), row["display_name"], row["locale"],
            row["accepted_terms_at"], row["birth_date"],
        )

    def save(self, profile: Profile) -> None:
        self.connection.execute(
            """
            INSERT INTO profiles(
                user_id, display_name, locale, birth_date, accepted_terms_at
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                locale = EXCLUDED.locale,
                birth_date = EXCLUDED.birth_date,
                accepted_terms_at = EXCLUDED.accepted_terms_at
            """,
            (profile.user_id, profile.display_name, profile.locale,
             profile.birth_date, profile.accepted_terms_at),
        )

    def delete(self, user_id: str) -> None:
        self.connection.execute("DELETE FROM profiles WHERE user_id = %s", (user_id,))


class PostgresSessions(_Repository):
    def get(self, token_hash: str) -> tuple[str, datetime] | None:
        row = self.connection.execute(
            """
            SELECT user_id, expires_at FROM sessions
             WHERE token_hash = %s AND revoked_at IS NULL
            """,
            (bytes.fromhex(token_hash),),
        ).fetchone()
        return (str(row["user_id"]), row["expires_at"]) if row else None

    def add(
        self, token_hash: str, user_id: str, created_at: datetime, expires_at: datetime
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO sessions(user_id, token_hash, created_at, expires_at)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, bytes.fromhex(token_hash), created_at, expires_at),
        )

    def revoke(self, token_hash: str, revoked_at: datetime) -> None:
        self.connection.execute(
            """
            UPDATE sessions SET revoked_at = %s
             WHERE token_hash = %s AND revoked_at IS NULL
            """,
            (revoked_at, bytes.fromhex(token_hash)),
        )

    def revoke_for_user(self, user_id: str, revoked_at: datetime) -> None:
        self.connection.execute(
            """
            UPDATE sessions SET revoked_at = %s
             WHERE user_id = %s AND revoked_at IS NULL
            """,
            (revoked_at, user_id),
        )


class PostgresLeagues(_Repository):
    def get(self, league_id: str, *, for_update: bool = False) -> League | None:
        suffix = " FOR UPDATE" if for_update else ""
        row = self.connection.execute(
            "SELECT * FROM leagues WHERE id = %s" + suffix, (league_id,)
        ).fetchone()
        return _league(row)

    def add(self, league: League) -> None:
        self.connection.execute(
            """
            INSERT INTO leagues(id, owner_id, name, plan, active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (league.id, league.owner_id, league.name, league.plan,
             league.active, league.created_at),
        )

    def list_for_user(self, user_id: str) -> list[League]:
        rows = self.connection.execute(
            """
            SELECT l.* FROM leagues l
              JOIN league_memberships m ON m.league_id = l.id
             WHERE m.user_id = %s AND m.removed_at IS NULL
             ORDER BY l.created_at, l.id
            """,
            (user_id,),
        ).fetchall()
        return [_league(row) for row in rows]

    def count_active_free_owned(self, owner_id: str) -> int:
        row = self.connection.execute(
            """
            SELECT count(*) AS total FROM leagues
             WHERE owner_id = %s AND active AND plan = 'free'
            """,
            (owner_id,),
        ).fetchone()
        return row["total"]


class PostgresMemberships(_Repository):
    def get(self, league_id: str, user_id: str) -> Membership | None:
        row = self.connection.execute(
            """
            SELECT * FROM league_memberships WHERE league_id = %s AND user_id = %s
            """,
            (league_id, user_id),
        ).fetchone()
        if row is None:
            return None
        return Membership(
            str(row["league_id"]), str(row["user_id"]), Role(row["role"]),
            row["joined_at"], row["removed_at"],
        )

    def save(self, membership: Membership) -> None:
        self.connection.execute(
            """
            INSERT INTO league_memberships(
                league_id, user_id, role, joined_at, removed_at
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (league_id, user_id) DO UPDATE SET
                role = EXCLUDED.role,
                joined_at = EXCLUDED.joined_at,
                removed_at = EXCLUDED.removed_at
            """,
            (membership.league_id, membership.user_id, membership.role.value,
             membership.joined_at, membership.removed_at),
        )

    def list_for_user(self, user_id: str) -> list[Membership]:
        rows = self.connection.execute(
            """
            SELECT * FROM league_memberships WHERE user_id = %s
             ORDER BY joined_at, league_id
            """,
            (user_id,),
        ).fetchall()
        return [Membership(
            str(row["league_id"]), str(row["user_id"]), Role(row["role"]),
            row["joined_at"], row["removed_at"],
        ) for row in rows]

    def list_active_for_league(self, league_id: str) -> list[Membership]:
        rows = self.connection.execute(
            """
            SELECT * FROM league_memberships
             WHERE league_id = %s AND removed_at IS NULL
             ORDER BY joined_at, user_id
            """,
            (league_id,),
        ).fetchall()
        return [Membership(
            str(row["league_id"]), str(row["user_id"]), Role(row["role"]),
            row["joined_at"], row["removed_at"],
        ) for row in rows]

    def count_active(self, league_id: str) -> int:
        row = self.connection.execute(
            """
            SELECT count(*) AS total FROM league_memberships
             WHERE league_id = %s AND removed_at IS NULL
            """,
            (league_id,),
        ).fetchone()
        return row["total"]

    def remove_active_for_user(self, user_id: str, removed_at: datetime) -> None:
        self.connection.execute(
            """
            UPDATE league_memberships SET removed_at = %s
             WHERE user_id = %s AND removed_at IS NULL
            """,
            (removed_at, user_id),
        )


class PostgresInvitations(_Repository):
    @staticmethod
    def _map(row) -> Invitation | None:
        if row is None:
            return None
        return Invitation(
            str(row["id"]), str(row["league_id"]), row["email"],
            Role(row["role"]), str(row["created_by"]), row["created_at"],
            row["expires_at"], InvitationStatus(row["status"]),
            str(row["accepted_by"]) if row["accepted_by"] else None,
        )

    def get(self, invitation_id: str) -> Invitation | None:
        row = self.connection.execute(
            "SELECT * FROM league_invitations WHERE id = %s FOR UPDATE",
            (invitation_id,),
        ).fetchone()
        return self._map(row)

    def save(self, invitation: Invitation) -> None:
        self.connection.execute(
            """
            INSERT INTO league_invitations(
                id, league_id, email, role, created_by, created_at, expires_at,
                status, accepted_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status, accepted_by = EXCLUDED.accepted_by,
                expires_at = EXCLUDED.expires_at
            """,
            (invitation.id, invitation.league_id, invitation.email,
             invitation.role.value, invitation.created_by, invitation.created_at,
             invitation.expires_at, invitation.status.value, invitation.accepted_by),
        )

    def list_for_email(self, email: str) -> list[Invitation]:
        rows = self.connection.execute(
            """
            SELECT * FROM league_invitations WHERE lower(email) = lower(%s)
             ORDER BY created_at, id
            """,
            (email,),
        ).fetchall()
        return [self._map(row) for row in rows]

    def list_pending_for_email(
        self, email: str, now: datetime
    ) -> list[Invitation]:
        rows = self.connection.execute(
            """
            SELECT * FROM league_invitations
             WHERE lower(email) = lower(%s)
               AND status = 'pending' AND expires_at > %s
             ORDER BY created_at, id
            """,
            (email, now),
        ).fetchall()
        return [self._map(row) for row in rows]

    def list_for_league(self, league_id: str) -> list[Invitation]:
        rows = self.connection.execute(
            """
            SELECT * FROM league_invitations WHERE league_id = %s
             ORDER BY created_at, id
            """,
            (league_id,),
        ).fetchall()
        return [self._map(row) for row in rows]

    def count_pending(self, league_id: str, now: datetime) -> int:
        row = self.connection.execute(
            """
            SELECT count(*) AS total FROM league_invitations
             WHERE league_id = %s AND status = 'pending' AND expires_at > %s
            """,
            (league_id, now),
        ).fetchone()
        return row["total"]


class PostgresCompetitions(_Repository):
    def get(
        self, competition_id: str, *, for_update: bool = False
    ) -> Competition | None:
        suffix = " FOR UPDATE" if for_update else ""
        row = self.connection.execute(
            "SELECT * FROM competitions WHERE id = %s" + suffix,
            (competition_id,),
        ).fetchone()
        return _competition(row)

    def add(self, competition: Competition) -> None:
        self.connection.execute(
            """
            INSERT INTO competitions(
                id, league_id, name, starts_at, ends_at, status,
                rules_snapshot, started_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                competition.id, competition.league_id, competition.name,
                competition.starts_at, competition.ends_at,
                competition.status.value,
                Jsonb(competition.rules_snapshot)
                if competition.rules_snapshot is not None else None,
                competition.started_at,
            ),
        )

    def save(self, competition: Competition) -> None:
        self.connection.execute(
            """
            UPDATE competitions
               SET name = %s, starts_at = %s, ends_at = %s, status = %s,
                   rules_snapshot = %s, started_at = %s
             WHERE id = %s
            """,
            (
                competition.name, competition.starts_at, competition.ends_at,
                competition.status.value,
                Jsonb(competition.rules_snapshot)
                if competition.rules_snapshot is not None else None,
                competition.started_at, competition.id,
            ),
        )

    def list_for_league(self, league_id: str) -> list[Competition]:
        rows = self.connection.execute(
            """
            SELECT * FROM competitions WHERE league_id = %s
             ORDER BY starts_at, id
            """,
            (league_id,),
        ).fetchall()
        return [_competition(row) for row in rows]


class PostgresAudit(_Repository):
    def add(
        self, occurred_at: datetime, actor_id: str | None, action: str,
        resource_type: str, resource_id: str, metadata: dict[str, str] | None = None,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO access_audit(
                occurred_at, actor_id, action, resource_type, resource_id, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (occurred_at, actor_id, action, resource_type, resource_id,
             Jsonb(metadata or {})),
        )


class PostgresStore:
    """Abre una conexión por unidad de trabajo, segura entre hilos ASGI."""

    def __init__(self, dsn: str, connect=psycopg.connect) -> None:
        self.dsn = dsn
        self._connect = connect
        self._local = threading.local()
        self.users = PostgresUsers(self)
        self.profiles = PostgresProfiles(self)
        self.sessions = PostgresSessions(self)
        self.leagues = PostgresLeagues(self)
        self.memberships = PostgresMemberships(self)
        self.invitations = PostgresInvitations(self)
        self.competitions = PostgresCompetitions(self)
        self.audit = PostgresAudit(self)

    @contextmanager
    def transaction(self):
        if getattr(self._local, "connection", None) is not None:
            raise RuntimeError("las unidades de trabajo anidadas no están permitidas")
        connection = self._connect(self.dsn, row_factory=dict_row)
        self._local.connection = connection
        try:
            with connection:
                yield self
        except UniqueViolation as exc:
            raise StoreConflict(exc.diag.constraint_name) from exc
        finally:
            self._local.connection = None
            connection.close()

    def ready(self) -> bool:
        try:
            with self._connect(self.dsn, row_factory=dict_row) as connection:
                connection.execute("SELECT 1").fetchone()
            return True
        except psycopg.Error:
            return False
