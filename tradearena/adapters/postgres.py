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
    Membership, Profile, Role, TradingAccount, User,
)
from tradearena.domain.ranking import RankingRow, RankingSnapshot
from tradearena.domain.trading import (
    Execution, ExecutionSource, JournalEntry, Order, OrderSide, OrderStatus, OrderType,
    Portfolio, Posting, Session,
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


class PostgresTrading(_Repository):
    def get(
        self, competition_id: str, user_id: str, *, for_update: bool = False,
    ) -> TradingAccount | None:
        suffix = " FOR UPDATE OF p" if for_update else ""
        row = self.connection.execute(
            """
            SELECT p.id, p.initial_cash, cp.joined_at, cp.joined_late, ca.balance
              FROM competition_participants cp
              JOIN portfolios p ON p.competition_id = cp.competition_id
               AND p.user_id = cp.user_id
              JOIN cash_accounts ca ON ca.portfolio_id = p.id
             WHERE cp.competition_id = %s AND cp.user_id = %s
            """ + suffix,
            (competition_id, user_id),
        ).fetchone()
        if row is None:
            return None
        portfolio = self._load_portfolio(str(row["id"]), row)
        return TradingAccount(
            competition_id, user_id, row["joined_at"], row["joined_late"], portfolio,
        )

    def _load_portfolio(self, portfolio_id: str, row) -> Portfolio:
        portfolio = Portfolio(portfolio_id, row["initial_cash"])
        portfolio.cash = row["balance"]
        position_rows = self.connection.execute(
            "SELECT symbol, quantity FROM portfolio_positions WHERE portfolio_id = %s",
            (portfolio_id,),
        ).fetchall()
        portfolio.positions = {item["symbol"]: item["quantity"] for item in position_rows}
        order_rows = self.connection.execute(
            """
            SELECT o.*, i.symbol FROM orders o JOIN instruments i ON i.id = o.instrument_id
             WHERE o.portfolio_id = %s ORDER BY o.submitted_at, o.id
            """,
            (portfolio_id,),
        ).fetchall()
        portfolio.orders = {str(item["id"]): Order(
            str(item["id"]), item["symbol"], OrderSide(item["side"]),
            item["quantity"], OrderType(item["order_type"]),
            item["allow_extended_hours"], item["submitted_at"],
            item["limit_price"], OrderStatus(item["status"]),
            item["rejection_reason"],
        ) for item in order_rows}
        execution_rows = self.connection.execute(
            """
            SELECT e.*, i.symbol, o.side FROM executions e
              JOIN orders o ON o.id = e.order_id
              JOIN instruments i ON i.id = o.instrument_id
             WHERE o.portfolio_id = %s ORDER BY e.executed_at, e.id
            """,
            (portfolio_id,),
        ).fetchall()
        portfolio.executions = [Execution(
            str(item["id"]), str(item["order_id"]), item["symbol"],
            OrderSide(item["side"]), item["quantity"], item["price"],
            item["commission"], item["executed_at"], Session(item["session"]),
            ExecutionSource(item["source"]), item["total_amount"],
            item["currency"].strip(), item["fx_rate"], item["correction_of"],
        ) for item in execution_rows]
        entry_rows = self.connection.execute(
            """
            SELECT le.sequence, le.occurred_at, le.kind, le.reference,
                   lp.account, lp.amount
              FROM ledger_entries le LEFT JOIN ledger_postings lp ON lp.entry_id = le.id
             WHERE le.portfolio_id = %s ORDER BY le.sequence, lp.id
            """,
            (portfolio_id,),
        ).fetchall()
        grouped: dict[int, dict] = {}
        for item in entry_rows:
            entry = grouped.setdefault(item["sequence"], {
                "occurred_at": item["occurred_at"], "kind": item["kind"],
                "reference": item["reference"], "postings": [],
            })
            if item["account"] is not None:
                entry["postings"].append(Posting(item["account"], item["amount"]))
        portfolio.ledger = [JournalEntry(
            sequence, item["occurred_at"], item["kind"], item["reference"],
            tuple(item["postings"]),
        ) for sequence, item in sorted(grouped.items())]
        return portfolio

    def add(self, account: TradingAccount) -> None:
        portfolio = account.portfolio
        self.connection.execute(
            """
            INSERT INTO competition_participants(
                competition_id, user_id, joined_at, joined_late
            ) VALUES (%s, %s, %s, %s)
            """,
            (account.competition_id, account.user_id, account.joined_at,
             account.joined_late),
        )
        self.connection.execute(
            """
            INSERT INTO portfolios(id, competition_id, user_id, currency, initial_cash)
            VALUES (%s, %s, %s, 'USD', %s)
            """,
            (portfolio.id, account.competition_id, account.user_id,
             portfolio.initial_cash),
        )
        self.connection.execute(
            "INSERT INTO cash_accounts(portfolio_id, balance) VALUES (%s, %s)",
            (portfolio.id, portfolio.cash),
        )
        self._save_details(portfolio)

    def save(self, account: TradingAccount) -> None:
        self.connection.execute(
            "UPDATE cash_accounts SET balance = %s WHERE portfolio_id = %s",
            (account.portfolio.cash, account.portfolio.id),
        )
        self._save_details(account.portfolio)

    def _instrument_id(self, symbol: str) -> str:
        row = self.connection.execute(
            """
            INSERT INTO instruments(symbol, kind, currency) VALUES (%s, 'stock', 'USD')
            ON CONFLICT (symbol) DO UPDATE SET symbol = EXCLUDED.symbol
            RETURNING id
            """,
            (symbol,),
        ).fetchone()
        return str(row["id"])

    def _save_details(self, portfolio: Portfolio) -> None:
        self.connection.execute(
            "DELETE FROM portfolio_positions WHERE portfolio_id = %s",
            (portfolio.id,),
        )
        for symbol, quantity in sorted(portfolio.positions.items()):
            self.connection.execute(
                "INSERT INTO portfolio_positions(portfolio_id, symbol, quantity) VALUES (%s, %s, %s)",
                (portfolio.id, symbol, quantity),
            )
        for order in portfolio.orders.values():
            instrument_id = self._instrument_id(order.symbol)
            self.connection.execute(
                """
                INSERT INTO orders(
                    id, portfolio_id, instrument_id, side, order_type, quantity,
                    limit_price, allow_extended_hours, status, submitted_at,
                    rejection_reason
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status,
                    rejection_reason = EXCLUDED.rejection_reason
                """,
                (order.id, portfolio.id, instrument_id, order.side.value,
                 order.order_type.value, order.quantity, order.limit_price,
                 order.allow_extended_hours, order.status.value,
                 order.submitted_at, order.rejection_reason),
            )
        for execution in portfolio.executions:
            existing = self.connection.execute(
                """
                SELECT e.*, i.symbol, o.side FROM executions e
                  JOIN orders o ON o.id = e.order_id
                  JOIN instruments i ON i.id = o.instrument_id
                 WHERE e.order_id = %s
                """,
                (execution.order_id,),
            ).fetchone()
            if existing is not None:
                stored = Execution(
                    str(existing["id"]), str(existing["order_id"]),
                    existing["symbol"], OrderSide(existing["side"]),
                    existing["quantity"], existing["price"],
                    existing["commission"], existing["executed_at"],
                    Session(existing["session"]),
                    ExecutionSource(existing["source"]), existing["total_amount"],
                    existing["currency"].strip(), existing["fx_rate"],
                    existing["correction_of"],
                )
                if stored != execution:
                    raise ValueError("las ejecuciones financieras son inmutables")
                continue
            self.connection.execute(
                """
                INSERT INTO executions(
                    id, order_id, quantity, price, commission, session, executed_at,
                    source, total_amount, currency, fx_rate, correction_of
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (order_id) DO NOTHING
                """,
                (execution.id, execution.order_id, execution.quantity,
                 execution.price, execution.commission, execution.session.value,
                 execution.executed_at, execution.source.value,
                 execution.total_amount, execution.currency, execution.fx_rate,
                 execution.correction_of),
            )
        for entry in portfolio.ledger:
            row = self.connection.execute(
                """
                INSERT INTO ledger_entries(
                    portfolio_id, sequence, kind, reference, occurred_at
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (portfolio_id, sequence) DO NOTHING
                RETURNING id
                """,
                (portfolio.id, entry.sequence, entry.kind, entry.reference,
                 entry.occurred_at),
            ).fetchone()
            if row is None:
                existing = self.connection.execute(
                    """
                    SELECT id, kind, reference, occurred_at
                      FROM ledger_entries
                     WHERE portfolio_id = %s AND sequence = %s
                    """,
                    (portfolio.id, entry.sequence),
                ).fetchone()
                postings = self.connection.execute(
                    """
                    SELECT account, amount FROM ledger_postings
                     WHERE entry_id = %s ORDER BY id
                    """,
                    (existing["id"],),
                ).fetchall()
                stored = tuple(
                    Posting(item["account"], item["amount"]) for item in postings
                )
                if (
                    existing["kind"], existing["reference"],
                    existing["occurred_at"], stored,
                ) != (
                    entry.kind, entry.reference, entry.occurred_at,
                    entry.postings,
                ):
                    raise ValueError("el ledger persistido es inmutable")
                continue
            for posting in entry.postings:
                self.connection.execute(
                    "INSERT INTO ledger_postings(entry_id, account, amount) VALUES (%s, %s, %s)",
                    (row["id"], posting.account, posting.amount),
                )

    def list_for_competition(self, competition_id: str) -> list[TradingAccount]:
        rows = self.connection.execute(
            "SELECT user_id FROM competition_participants WHERE competition_id = %s ORDER BY joined_at, user_id",
            (competition_id,),
        ).fetchall()
        return [self.get(competition_id, str(item["user_id"])) for item in rows]

    def save_ranking(self, snapshot: RankingSnapshot) -> None:
        existing = self.connection.execute(
            "SELECT digest FROM ranking_snapshots WHERE competition_id = %s AND as_of = %s",
            (snapshot.competition_id, snapshot.as_of),
        ).fetchone()
        if existing and existing["digest"] != snapshot.digest:
            raise ValueError("snapshot de ranking no reproducible")
        self.connection.execute(
            """
            INSERT INTO ranking_snapshots(competition_id, as_of, rows, digest)
            VALUES (%s, %s, %s, %s) ON CONFLICT (competition_id, as_of) DO NOTHING
            """,
            (snapshot.competition_id, snapshot.as_of,
             Jsonb([row.__dict__ for row in snapshot.rows]), snapshot.digest),
        )

    def latest_ranking(self, competition_id: str) -> RankingSnapshot | None:
        row = self.connection.execute(
            "SELECT * FROM ranking_snapshots WHERE competition_id = %s ORDER BY as_of DESC LIMIT 1",
            (competition_id,),
        ).fetchone()
        if row is None:
            return None
        rows = tuple(RankingRow(**item) for item in row["rows"])
        return RankingSnapshot(competition_id, row["as_of"], rows, row["digest"])


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
        self.trading = PostgresTrading(self)
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
