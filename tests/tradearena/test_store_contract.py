from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from uuid import uuid4
from decimal import Decimal

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest

from tradearena.adapters.memory import MemoryStore
from tradearena.adapters.postgres import PostgresStore
from tradearena.adapters.market_data import FixtureMarketDataAdapter
from tradearena.application.models import User
from tradearena.application.services import (
    AccountService, CompetitionService, Forbidden, LeagueService,
    NotificationService, PlanLimitExceeded, SessionService, TradingService,
)
from tradearena.domain.trading import Quote, Session
from tradearena.migrations import migrate
from tradearena.ports.identity import IdentityAssertion


NOW = datetime(2026, 8, 5, 12, tzinfo=timezone.utc)
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def _exercise_application_contract(store):
    accounts = AccountService(store, lambda: str(uuid4()))
    leagues = LeagueService(store, lambda: str(uuid4()))
    sessions = SessionService(store, lambda: f"token-{uuid4()}", lambda: NOW)

    owner = accounts.login(
        IdentityAssertion("email", "owner@example.com", "owner@example.com", True),
        NOW,
    )
    member = accounts.login(
        IdentityAssertion("email", "member@example.com", "member@example.com", True),
        NOW,
    )
    token = sessions.issue(owner.id, NOW)
    assert sessions.authenticate(token) == owner.id

    league = leagues.create(owner.id, "Privada", NOW)
    competitions = CompetitionService(store, lambda: str(uuid4()))
    competition = competitions.create(
        owner.id, league.id, "Agosto", NOW + timedelta(days=1),
        NOW + timedelta(days=31), NOW,
    )
    started = competitions.start(owner.id, league.id, competition.id, NOW)
    assert started.rules_snapshot["rules"]["initial_capital"] == "3000.00"
    invitation = leagues.invite(owner.id, league.id, member.email, NOW)
    with pytest.raises(PlanLimitExceeded):
        leagues.invite(owner.id, league.id, "third@example.com", NOW)
    assert leagues.list_invitations(member.id, NOW)[0].id == invitation.id
    leagues.accept(member.id, invitation.id, NOW)
    assert competitions.get(member.id, league.id, competition.id).id \
        == competition.id

    detail = leagues.get(member.id, league.id, NOW)
    assert detail.name == "Privada"
    assert [item.user_id for item in detail.members] == [owner.id, member.id]
    assert detail.invitations == ()
    assert [item.id for item in leagues.list_for(member.id, NOW)] == [league.id]
    assert accounts.export(member.id, member.id)["memberships"][0]["league_id"] \
        == league.id
    quote_time = NOW + timedelta(days=1, minutes=1)
    trading = TradingService(store, lambda: str(uuid4()), FixtureMarketDataAdapter((
        Quote("AAPL", Decimal("100"), quote_time, Session.REGULAR),
    )))
    portfolio = trading.portfolio(member.id, league.id, competition.id, NOW)
    assert portfolio.initial_cash == portfolio.cash == "3000.00"
    assert portfolio.joined_late is True
    trading.submit_order(
        owner.id, league.id, competition.id, "AAPL", "buy", 1, "market",
        False, None, NOW + timedelta(days=1, seconds=1), str(uuid4()), "0.75",
    )
    filled = trading.portfolio(owner.id, league.id, competition.id, quote_time)
    assert filled.cash == "2899.25"
    assert filled.orders[0].commission == "0.75"
    assert filled.executions[0].commission == "0.75"
    reported = trading.report_trade(
        member.id, league.id, competition.id, occurred_at=quote_time,
        symbol="MSFT", side="buy", quantity_value="0.12345678",
        price_per_share="50", total_amount="7.32", currency="USD",
        fx_rate="1", client_trade_id=str(uuid4()), now=quote_time,
    )
    assert reported.positions[0].quantity == "0.12345678"
    assert reported.executions[0].source == "reported"
    with store.transaction() as uow:
        persisted = uow.trading.get(competition.id, member.id)
        assert persisted.portfolio.positions["MSFT"] == Decimal("0.12345678")
        assert persisted.portfolio.executions[0].total_amount == Decimal("7.32")
    with store.transaction() as uow:
        account = uow.trading.get(competition.id, owner.id)
        assert all(sum(posting.amount for posting in entry.postings) == 0
                   for entry in account.portfolio.ledger)
    ranking = trading.ranking(owner.id, league.id, competition.id, quote_time)
    assert len(ranking.rows) == 2
    assert trading.ranking(owner.id, league.id, competition.id, quote_time) == ranking

    notifications = NotificationService(store, lambda: str(uuid4()))
    created_notification = notifications.create(
        member.id, "trade.recorded", {
            "competition_id": competition.id, "session_token": "must-not-leak",
        }, quote_time,
    )
    assert notifications.list_for(member.id)[0]["payload"] == {
        "competition_id": competition.id,
    }
    assert notifications.mark_read(
        member.id, created_notification.id, quote_time,
    )["read_at"] == quote_time
    exported = accounts.export(member.id, member.id)
    assert accounts.export(member.id, member.id) == exported
    assert exported["schema_version"] == "1"
    assert exported["financial_history"][0]["portfolio"]["executions"][0]["source"] \
        .value == "reported"
    assert "identity_subject" not in exported["user"]
    assert "session_token" not in str(exported)


def _exercise_account_deletion_contract(store):
    accounts = AccountService(store, lambda: str(uuid4()))
    sessions = SessionService(store, lambda: str(uuid4()), lambda: NOW)
    leagues = LeagueService(store, lambda: str(uuid4()))
    competitions = CompetitionService(store, lambda: str(uuid4()))
    notifications = NotificationService(store, lambda: str(uuid4()))
    user = accounts.login(
        IdentityAssertion("email", "delete@example.com", "delete@example.com", True),
        NOW,
    )
    inviter = accounts.login(
        IdentityAssertion("email", "inviter@example.com", "inviter@example.com", True),
        NOW,
    )
    accounts.set_profile(
        user.id, "Personal Name", "es", NOW.date().replace(year=1990), NOW, NOW,
    )
    first_token = sessions.issue(user.id, NOW)
    second_token = sessions.issue(user.id, NOW)
    owned = leagues.create(user.id, "Owned", NOW)
    competition = competitions.create(
        user.id, owned.id, "History", NOW, NOW + timedelta(days=2), NOW,
    )
    competitions.start(user.id, owned.id, competition.id, NOW)
    TradingService(store, lambda: str(uuid4()), FixtureMarketDataAdapter()).report_trade(
        user.id, owned.id, competition.id, occurred_at=NOW,
        symbol="AAPL", side="buy", quantity_value="1",
        price_per_share="100", total_amount="101.15", currency="USD",
        fx_rate="1", client_trade_id=str(uuid4()), now=NOW,
    )
    invited_league = leagues.create(inviter.id, "Invitation", NOW)
    invitation = leagues.invite(inviter.id, invited_league.id, user.email, NOW)
    notifications.create(user.id, "privacy.ready", {"message": "Ready"}, NOW)

    with pytest.raises(Exception, match="confirmación"):
        accounts.delete(user.id, user.id, NOW, confirmed=False)
    accounts.delete(user.id, user.id, NOW, confirmed=True)

    with pytest.raises(Forbidden):
        sessions.authenticate(first_token)
    with pytest.raises(Forbidden):
        sessions.authenticate(second_token)
    with store.transaction() as uow:
        deleted = uow.users.get(user.id)
        assert deleted.deleted_at == NOW
        assert deleted.email == f"deleted+{user.id}@invalid.local"
        assert uow.profiles.get(user.id) is None
        assert all(item.removed_at == NOW for item in uow.memberships.list_for_user(user.id))
        retained = uow.trading.list_for_user(user.id)
        assert len(retained) == 1
        assert retained[0].portfolio.executions
        assert retained[0].portfolio.ledger
        assert uow.audit.list_for_user(user.id)[-1].action == "account.deleted"
        assert uow.notifications.list_for_user(user.id) == []
        assert uow.invitations.get(invitation.id).email == deleted.email


def test_memory_store_passes_application_contract_and_rolls_back():
    store = MemoryStore()
    _exercise_application_contract(store)
    user_id = str(uuid4())

    with pytest.raises(RuntimeError):
        with store.transaction() as uow:
            uow.users.add(User(
                user_id, "rollback@example.com", "email", "rollback@example.com", NOW
            ))
            raise RuntimeError("rollback")

    with store.transaction() as uow:
        assert uow.users.get(user_id) is None


def test_memory_store_preserves_and_anonymizes_account_deletion_contract():
    _exercise_account_deletion_contract(MemoryStore())


@pytest.fixture
def postgres_store():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL no está configurada")
    schema = f"tradearena_test_{uuid4().hex}"
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    dsn = make_conninfo(TEST_DATABASE_URL, options=f"-c search_path={schema}")
    try:
        assert migrate(dsn) == [
            "001_initial", "002_auth0_identity", "003_league_reads",
            "004_competitions", "005_trading_ranking",
            "006_fractional_reported_trades", "007_user_commissions",
            "008_initial_participant_calendar_join",
            "009_notifications_privacy",
            "010_competition_dashboard",
        ]
        assert migrate(dsn) == []
        yield PostgresStore(dsn)
    finally:
        with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )


def test_postgres_store_passes_same_application_contract(postgres_store):
    _exercise_application_contract(postgres_store)


def test_dashboard_migration_upgrades_version_009(postgres_store, tmp_path):
    schema = f"tradearena_009_{uuid4().hex}"
    with psycopg.connect(postgres_store.dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    previous_dsn = make_conninfo(postgres_store.dsn, options=f"-c search_path={schema}")
    previous_migrations = tmp_path / "version-009"
    previous_migrations.mkdir()
    source = Path(__file__).parents[2] / "migrations"
    for version in range(1, 10):
        path = next(source.glob(f"{version:03d}_*.sql"))
        (previous_migrations / path.name).write_text(path.read_text())
    try:
        assert migrate(previous_dsn, previous_migrations)[-1] == "009_notifications_privacy"
        assert migrate(previous_dsn) == ["010_competition_dashboard"]
        with psycopg.connect(previous_dsn, row_factory=psycopg.rows.dict_row) as connection:
            columns = {row["column_name"] for row in connection.execute(
                """SELECT column_name FROM information_schema.columns
                     WHERE table_schema = current_schema()
                       AND table_name = 'portfolio_snapshots'"""
            ).fetchall()}
            assert {"trading_day", "provisional", "calculation_version"} <= columns
            assert connection.execute("SELECT to_regclass('competition_badges') AS value").fetchone()["value"]
    finally:
        with psycopg.connect(postgres_store.dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_postgres_store_preserves_and_anonymizes_account_deletion_contract(
    postgres_store,
):
    _exercise_account_deletion_contract(postgres_store)


def test_postgres_auth0_identity_and_individual_session_revocation(postgres_store):
    accounts = AccountService(postgres_store, lambda: str(uuid4()))
    sessions = SessionService(postgres_store, lambda: "opaque-auth0-session", lambda: NOW)
    user = accounts.login(
        IdentityAssertion("auth0", "auth0|user-1", "auth0@example.com", True), NOW
    )
    token = sessions.issue(user.id, NOW)
    assert sessions.authenticate(token) == user.id

    sessions.revoke(token, NOW)

    with pytest.raises(Forbidden):
        sessions.authenticate(token)


def test_auth0_migration_upgrades_the_previous_schema(postgres_store, tmp_path):
    schema = f"tradearena_previous_{uuid4().hex}"
    with psycopg.connect(postgres_store.dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    previous_dsn = make_conninfo(postgres_store.dsn, options=f"-c search_path={schema}")
    previous_migrations = tmp_path / "migrations"
    previous_migrations.mkdir()
    initial = Path(__file__).parents[2] / "migrations" / "001_initial.sql"
    (previous_migrations / initial.name).write_text(initial.read_text())
    try:
        assert migrate(previous_dsn, previous_migrations) == ["001_initial"]
        assert migrate(previous_dsn) == [
            "002_auth0_identity", "003_league_reads", "004_competitions",
            "005_trading_ranking", "006_fractional_reported_trades",
            "007_user_commissions",
            "008_initial_participant_calendar_join",
            "009_notifications_privacy",
            "010_competition_dashboard",
        ]
        assert migrate(previous_dsn) == []
    finally:
        with psycopg.connect(postgres_store.dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_trading_migration_upgrades_ta034_schema(postgres_store, tmp_path):
    schema = f"tradearena_ta034_{uuid4().hex}"
    with psycopg.connect(postgres_store.dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    previous_dsn = make_conninfo(postgres_store.dsn, options=f"-c search_path={schema}")
    previous_migrations = tmp_path / "ta034-migrations"
    previous_migrations.mkdir()
    source = Path(__file__).parents[2] / "migrations"
    for version in range(1, 5):
        path = next(source.glob(f"{version:03d}_*.sql"))
        (previous_migrations / path.name).write_text(path.read_text())
    try:
        assert migrate(previous_dsn, previous_migrations) == [
            "001_initial", "002_auth0_identity", "003_league_reads",
            "004_competitions",
        ]
        assert migrate(previous_dsn) == [
            "005_trading_ranking", "006_fractional_reported_trades",
            "007_user_commissions",
            "008_initial_participant_calendar_join",
            "009_notifications_privacy",
            "010_competition_dashboard",
        ]
    finally:
        with psycopg.connect(postgres_store.dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_fractional_reported_migration_upgrades_ta035_schema(postgres_store, tmp_path):
    schema = f"tradearena_ta035_{uuid4().hex}"
    with psycopg.connect(postgres_store.dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    previous_dsn = make_conninfo(postgres_store.dsn, options=f"-c search_path={schema}")
    previous_migrations = tmp_path / "ta035-migrations"
    previous_migrations.mkdir()
    source = Path(__file__).parents[2] / "migrations"
    for version in range(1, 6):
        path = next(source.glob(f"{version:03d}_*.sql"))
        (previous_migrations / path.name).write_text(path.read_text())
    try:
        assert migrate(previous_dsn, previous_migrations) == [
            "001_initial", "002_auth0_identity", "003_league_reads",
            "004_competitions", "005_trading_ranking",
        ]
        assert migrate(previous_dsn) == [
            "006_fractional_reported_trades", "007_user_commissions",
            "008_initial_participant_calendar_join",
            "009_notifications_privacy",
            "010_competition_dashboard",
        ]
        with psycopg.connect(previous_dsn, row_factory=psycopg.rows.dict_row) as connection:
            columns = connection.execute(
                """
                SELECT column_name, data_type, numeric_scale
                  FROM information_schema.columns
                 WHERE table_schema = current_schema()
                   AND table_name IN ('orders', 'executions', 'portfolio_positions')
                   AND column_name IN ('quantity', 'source', 'total_amount', 'commission')
                """
            ).fetchall()
        quantity_columns = [row for row in columns if row["column_name"] == "quantity"]
        assert len(quantity_columns) == 3
        assert all(row["data_type"] == "numeric" and row["numeric_scale"] == 8
                   for row in quantity_columns)
        assert {row["column_name"] for row in columns} >= {"source", "total_amount"}
        commission = next(row for row in columns if row["column_name"] == "commission")
        assert commission["data_type"] == "numeric"
        assert commission["numeric_scale"] == 2
    finally:
        with psycopg.connect(postgres_store.dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_notifications_privacy_migration_upgrades_008_schema(postgres_store, tmp_path):
    schema = f"tradearena_008_{uuid4().hex}"
    with psycopg.connect(postgres_store.dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    previous_dsn = make_conninfo(postgres_store.dsn, options=f"-c search_path={schema}")
    previous_migrations = tmp_path / "migrations-008"
    previous_migrations.mkdir()
    source = Path(__file__).parents[2] / "migrations"
    for version in range(1, 9):
        path = next(source.glob(f"{version:03d}_*.sql"))
        (previous_migrations / path.name).write_text(path.read_text())
    try:
        assert migrate(previous_dsn, previous_migrations)[-1] \
            == "008_initial_participant_calendar_join"
        assert migrate(previous_dsn) == [
            "009_notifications_privacy", "010_competition_dashboard",
        ]
        with psycopg.connect(previous_dsn) as connection:
            indexes = {row[0] for row in connection.execute(
                """
                SELECT indexname FROM pg_indexes
                 WHERE schemaname = current_schema()
                   AND indexname IN (
                       'notifications_by_user_created',
                       'access_audit_by_actor_sequence'
                   )
                """
            ).fetchall()}
        assert indexes == {
            "notifications_by_user_created", "access_audit_by_actor_sequence",
        }
    finally:
        with psycopg.connect(postgres_store.dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_postgres_transaction_rolls_back(postgres_store):
    user_id = str(uuid4())
    with pytest.raises(RuntimeError):
        with postgres_store.transaction() as uow:
            uow.users.add(User(
                user_id, "rollback@example.com", "email", "rollback@example.com", NOW
            ))
            raise RuntimeError("rollback")

    with postgres_store.transaction() as uow:
        assert uow.users.get(user_id) is None


def test_postgres_serializes_active_free_league_limit(postgres_store):
    accounts = AccountService(postgres_store, lambda: str(uuid4()))
    owner = accounts.login(
        IdentityAssertion("email", "owner@example.com", "owner@example.com", True),
        NOW,
    )

    def create(name):
        try:
            LeagueService(postgres_store, lambda: str(uuid4())).create(
                owner.id, name, NOW
            )
            return "created"
        except PlanLimitExceeded:
            return "limited"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(create, ["Una", "Dos"]))

    assert sorted(results) == ["created", "limited"]


def test_postgres_serializes_free_invitation_slots(postgres_store):
    accounts = AccountService(postgres_store, lambda: str(uuid4()))
    leagues = LeagueService(postgres_store, lambda: str(uuid4()))
    owner = accounts.login(
        IdentityAssertion("email", "owner@example.com", "owner@example.com", True),
        NOW,
    )
    league = leagues.create(owner.id, "Concurrente", NOW)

    def invite(email):
        try:
            leagues.invite(owner.id, league.id, email, NOW)
            return "created"
        except PlanLimitExceeded:
            return "limited"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(invite, ["one@example.com", "two@example.com"]))

    assert sorted(results) == ["created", "limited"]


def test_postgres_rejects_rules_snapshot_replacement(postgres_store):
    accounts = AccountService(postgres_store, lambda: str(uuid4()))
    owner = accounts.login(
        IdentityAssertion("email", "snapshot@example.com", "snapshot@example.com", True),
        NOW,
    )
    league = LeagueService(postgres_store, lambda: str(uuid4())).create(
        owner.id, "Snapshot", NOW,
    )
    competitions = CompetitionService(postgres_store, lambda: str(uuid4()))
    competition = competitions.create(
        owner.id, league.id, "Inmutable", NOW + timedelta(days=1),
        NOW + timedelta(days=2), NOW,
    )
    competitions.start(owner.id, league.id, competition.id, NOW)

    with pytest.raises(psycopg.errors.CheckViolation, match="inmutable"):
        with psycopg.connect(postgres_store.dsn) as connection:
            connection.execute(
                "UPDATE competitions SET rules_snapshot = %s WHERE id = %s",
                (psycopg.types.json.Jsonb({"tampered": True}), competition.id),
            )
