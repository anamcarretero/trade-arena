from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest

from tradearena.adapters.memory import MemoryStore
from tradearena.adapters.postgres import PostgresStore
from tradearena.application.models import User
from tradearena.application.services import (
    AccountService, Forbidden, LeagueService, PlanLimitExceeded, SessionService,
)
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
    invitation = leagues.invite(
        owner.id, league.id, member.email, NOW + timedelta(days=1), NOW
    )
    with pytest.raises(PlanLimitExceeded):
        leagues.invite(
            owner.id, league.id, "third@example.com", NOW + timedelta(days=1), NOW
        )
    leagues.accept(member.id, invitation.id, NOW)

    assert leagues.get(member.id, league.id).name == "Privada"
    assert [item.id for item in leagues.list_for(member.id)] == [league.id]
    assert accounts.export(member.id, member.id)["memberships"][0]["league_id"] \
        == league.id


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


@pytest.fixture
def postgres_store():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL no está configurada")
    schema = f"tradearena_test_{uuid4().hex}"
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    dsn = make_conninfo(TEST_DATABASE_URL, options=f"-c search_path={schema}")
    try:
        assert migrate(dsn) == ["001_initial", "002_auth0_identity"]
        assert migrate(dsn) == []
        yield PostgresStore(dsn)
    finally:
        with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )


def test_postgres_store_passes_same_application_contract(postgres_store):
    _exercise_application_contract(postgres_store)


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
        assert migrate(previous_dsn) == ["002_auth0_identity"]
        assert migrate(previous_dsn) == []
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
            leagues.invite(
                owner.id, league.id, email, NOW + timedelta(days=1), NOW
            )
            return "created"
        except PlanLimitExceeded:
            return "limited"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(invite, ["one@example.com", "two@example.com"]))

    assert sorted(results) == ["created", "limited"]
