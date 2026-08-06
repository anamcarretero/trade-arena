from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tradearena.adapters.market_data import FixtureMarketDataAdapter
from tradearena.adapters.memory import MemoryStore
from tradearena.application.models import Membership, Profile, Role, User
from tradearena.application.services import (
    CompetitionService, Conflict, LeagueService, NotFound, TradingService,
)
from tradearena.domain.trading import Quote, Session


T0 = datetime(2030, 1, 7, 14, 30, tzinfo=timezone.utc)


class Ids:
    def __init__(self):
        self.value = 0

    def __call__(self):
        self.value += 1
        return f"00000000-0000-0000-0000-{self.value:012d}"


@pytest.fixture
def context():
    store = MemoryStore()
    ids = Ids()
    owner = User(ids(), "owner@example.com", "email", "owner", T0)
    member = User(ids(), "member@example.com", "email", "member", T0)
    with store.transaction() as uow:
        uow.users.add(owner)
        uow.users.add(member)
        uow.profiles.save(Profile(owner.id, "Ana", "es", T0, date(1990, 1, 1)))
        uow.profiles.save(Profile(member.id, "Ben", "en", T0, date(1990, 1, 1)))
    leagues = LeagueService(store, ids)
    league = leagues.create(owner.id, "Liga", T0)
    with store.transaction() as uow:
        uow.memberships.save(Membership(league.id, member.id, Role.MEMBER, T0))
    competitions = CompetitionService(store, ids)
    competition = competitions.create(
        owner.id, league.id, "Invierno", T0, T0 + timedelta(days=1), T0,
    )
    competitions.start(owner.id, league.id, competition.id, T0)
    quotes = (
        Quote("AAPL", Decimal("100"), T0 - timedelta(seconds=1), Session.REGULAR),
        Quote("AAPL", Decimal("101"), T0 + timedelta(minutes=2), Session.REGULAR),
        Quote("MSFT", Decimal("200"), T0 + timedelta(minutes=2), Session.EXTENDED),
    )
    trading = TradingService(store, ids, FixtureMarketDataAdapter(quotes))
    return store, ids, owner, member, league, competition, trading


def test_start_materializes_every_active_member_with_exact_free_capital(context):
    store, _, owner, member, _, competition, _ = context
    with store.transaction() as uow:
        accounts = uow.trading.list_for_competition(competition.id)
    assert {item.user_id for item in accounts} == {owner.id, member.id}
    assert {item.portfolio.initial_cash for item in accounts} == {Decimal("3000.00")}
    assert all(not item.joined_late for item in accounts)


def test_order_execution_history_ledger_and_idempotency(context):
    store, _, owner, _, league, competition, trading = context
    submitted = trading.submit_order(
        owner.id, league.id, competition.id, "aapl", "buy", 2, "market",
        False, None, T0 + timedelta(minutes=1), "order-1",
    )
    assert submitted.orders[0].status == "pending"

    filled = trading.portfolio(
        owner.id, league.id, competition.id, T0 + timedelta(minutes=3)
    )
    assert filled.cash == "2796.85"
    assert filled.positions[0].quantity == "2"
    assert filled.executions[0].source == "fixture"
    assert filled.executions[0].price == "101.0000"
    assert filled.executions[0].commission == "1.15"

    repeated = trading.submit_order(
        owner.id, league.id, competition.id, "AAPL", "buy", 2, "market",
        False, None, T0 + timedelta(minutes=3), "order-1",
    )
    assert len(repeated.orders) == len(repeated.executions) == 1
    with store.transaction() as uow:
        account = uow.trading.get(competition.id, owner.id)
    assert all(sum(posting.amount for posting in entry.postings) == 0
               for entry in account.portfolio.ledger)


def test_idempotency_keys_are_scoped_to_each_portfolio(context):
    _, _, owner, member, league, competition, trading = context
    first = trading.submit_order(
        owner.id, league.id, competition.id, "NVDA", "buy", 1, "limit",
        False, "1", T0 + timedelta(minutes=1), "same-key",
    )
    second = trading.submit_order(
        member.id, league.id, competition.id, "NVDA", "buy", 1, "limit",
        False, "1", T0 + timedelta(minutes=1), "same-key",
    )
    assert first.orders[0].id != second.orders[0].id


def test_reported_fractional_trade_is_atomic_idempotent_and_auditable(context):
    store, _, owner, _, league, competition, trading = context
    occurred_at = T0 + timedelta(minutes=1)
    result = trading.report_trade(
        owner.id, league.id, competition.id, occurred_at=occurred_at,
        symbol="aapl", side="buy", quantity_value="0.12345678",
        price_per_share="100", total_amount="13.50", currency="usd",
        fx_rate="1.00000000", client_trade_id="reported-1",
        now=occurred_at,
    )
    assert result.cash == "2986.50"
    assert result.positions[0].quantity == "0.12345678"
    assert result.executions[0].source == "reported"
    assert result.executions[0].total_amount == "13.50"

    repeated = trading.report_trade(
        owner.id, league.id, competition.id, occurred_at=occurred_at,
        symbol="AAPL", side="buy", quantity_value="0.12345678",
        price_per_share="100.0000", total_amount="13.50", currency="USD",
        fx_rate="1", client_trade_id="reported-1", now=occurred_at,
    )
    assert len(repeated.orders) == len(repeated.executions) == 1
    with store.transaction() as uow:
        account = uow.trading.get(competition.id, owner.id)
        assert len(account.portfolio.ledger) == 2
        assert all(sum(posting.amount for posting in entry.postings) == 0
                   for entry in account.portfolio.ledger)
        assert any(event.action == "reported_trade.created"
                   for event in store._audit)


def test_reported_trade_validates_total_chronology_cash_position_and_usd(context):
    _, _, owner, _, league, competition, trading = context
    occurred_at = T0 + timedelta(minutes=1)
    common = dict(
        actor_id=owner.id, league_id=league.id,
        competition_id=competition.id, occurred_at=occurred_at,
        symbol="AAPL", side="buy", quantity_value="1",
        price_per_share="100", total_amount="101.15", currency="USD",
        fx_rate="1", client_trade_id="valid", now=occurred_at,
    )
    trading.report_trade(**common)
    with pytest.raises(Conflict, match="cronológicamente"):
        trading.report_trade(**{
            **common, "occurred_at": T0 + timedelta(seconds=1),
            "client_trade_id": "old", "now": occurred_at,
        })
    with pytest.raises(Exception, match="USD"):
        trading.report_trade(**{
            **common, "currency": "EUR", "client_trade_id": "eur",
        })
    with pytest.raises(Exception, match="total"):
        trading.report_trade(**{
            **common, "total_amount": "100.98", "client_trade_id": "bad-total",
        })
    with pytest.raises(Conflict, match="posición"):
        trading.report_trade(**{
            **common, "side": "sell", "quantity_value": "2",
            "total_amount": "198.85", "client_trade_id": "short",
            "occurred_at": T0 + timedelta(minutes=2),
            "now": T0 + timedelta(minutes=2),
        })


def test_reported_trade_correction_is_compensating_not_destructive(context):
    store, _, owner, member, league, competition, trading = context
    first_at = T0 + timedelta(minutes=1)
    result = trading.report_trade(
        owner.id, league.id, competition.id, occurred_at=first_at,
        symbol="AAPL", side="buy", quantity_value="0.5",
        price_per_share="100", total_amount="51.15", currency="USD",
        fx_rate="1", client_trade_id="mistake", now=first_at,
    )
    original_id = result.executions[0].id
    corrected_at = T0 + timedelta(minutes=2)
    with pytest.raises(NotFound):
        trading.correct_reported_trade(
            member.id, league.id, competition.id, original_id,
            occurred_at=corrected_at, client_trade_id="foreign-correction",
            now=corrected_at,
        )
    corrected = trading.correct_reported_trade(
        owner.id, league.id, competition.id, original_id,
        occurred_at=corrected_at, client_trade_id="undo-mistake",
        now=corrected_at,
    )
    assert corrected.cash == "3000.00"
    assert corrected.positions == ()
    assert len(corrected.executions) == 2
    assert corrected.executions[1].correction_of == original_id
    with store.transaction() as uow:
        account = uow.trading.get(competition.id, owner.id)
        assert {entry.kind for entry in account.portfolio.ledger} == {
            "initial_cash", "reported_execution", "reported_execution_correction"
        }


def test_extended_order_uses_snapshot_fee_and_rejection_has_no_commission(context):
    _, _, owner, _, league, competition, trading = context
    result = trading.submit_order(
        owner.id, league.id, competition.id, "MSFT", "buy", 15, "market",
        True, None, T0 + timedelta(minutes=1), "too-expensive",
    )
    result = trading.portfolio(
        owner.id, league.id, competition.id, T0 + timedelta(minutes=3)
    )
    assert result.orders[0].status == "rejected"
    assert result.orders[0].rejection_reason == "insufficient_cash"
    assert result.cash == "3000.00"
    assert result.executions == ()


def test_pending_order_can_be_cancelled_and_foreign_resources_are_404(context):
    _, _, owner, member, league, competition, trading = context
    result = trading.submit_order(
        owner.id, league.id, competition.id, "NVDA", "buy", 1, "limit",
        False, "1.0000", T0 + timedelta(minutes=1), "cancel-me",
    )
    assert result.orders[0].status == "pending"
    order_id = result.orders[0].id
    cancelled = trading.cancel_order(
        owner.id, league.id, competition.id, order_id, T0 + timedelta(minutes=2)
    )
    assert cancelled.orders[0].status == "cancelled"
    with pytest.raises(NotFound):
        trading.cancel_order(
            member.id, league.id, competition.id, order_id, T0 + timedelta(minutes=2)
        )


def test_gtc_order_closes_at_competition_end_or_definitive_suspension(context):
    store, ids, owner, _, league, competition, trading = context
    suspended = TradingService(
        store, ids, FixtureMarketDataAdapter(suspended_symbols=("NVDA",))
    )
    suspended.submit_order(
        owner.id, league.id, competition.id, "NVDA", "buy", 1, "limit",
        False, "1", T0 + timedelta(minutes=2), "suspended",
    )
    view = suspended.portfolio(
        owner.id, league.id, competition.id, T0 + timedelta(minutes=3)
    )
    order = next(item for item in view.orders if item.id.endswith("-suspended"))
    assert order.status == "cancelled"
    assert order.rejection_reason == "instrument_suspended"

    trading.submit_order(
        owner.id, league.id, competition.id, "NVDA", "buy", 1, "limit",
        False, "1", T0 + timedelta(minutes=4), "until-end",
    )
    ended = trading.portfolio(
        owner.id, league.id, competition.id, T0 + timedelta(days=1)
    )
    order = next(item for item in ended.orders if item.id.endswith("-until-end"))
    assert order.status == "cancelled"
    assert order.rejection_reason == "competition_ended"
    with store.transaction() as uow:
        assert uow.competitions.get(competition.id).status.value == "finished"


def test_late_member_gets_full_capital_and_is_marked_in_reproducible_ranking(context):
    store, ids, owner, _, league, competition, trading = context
    late = User(ids(), "late@example.com", "email", "late", T0)
    with store.transaction() as uow:
        uow.users.add(late)
        uow.profiles.save(Profile(late.id, "Late", "en", T0, date(1990, 1, 1)))
        uow.memberships.save(Membership(
            league.id, late.id, Role.MEMBER, T0 + timedelta(hours=1)
        ))
    portfolio = trading.portfolio(
        late.id, league.id, competition.id, T0 + timedelta(hours=1)
    )
    assert portfolio.initial_cash == portfolio.cash == "3000.00"
    assert portfolio.joined_late is True

    as_of = T0 + timedelta(hours=2)
    first = trading.ranking(owner.id, league.id, competition.id, as_of)
    second = trading.ranking(owner.id, league.id, competition.id, as_of)
    assert first == second
    late_row = next(row for row in first.rows if row["user_id"] == late.id)
    assert late_row["joined_late"] is True
