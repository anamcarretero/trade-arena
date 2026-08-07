from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import yaml

from tradearena.adapters.market_data import FixtureMarketDataAdapter
from tradearena.adapters.memory import MemoryStore
from tradearena.application.dashboard import _replay, project_account, sessions_between
from tradearena.application.models import (
    Competition, CompetitionStatus, Profile, TradingAccount, User,
)
from tradearena.application.services import CompetitionService, DashboardService, LeagueService
from tradearena.domain.competition import build_rules_snapshot
from tradearena.domain.trading import (
    Execution, ExecutionSource, OrderSide, Portfolio, Session,
)


def test_xnys_sessions_exclude_weekend_and_market_holiday():
    start = datetime(2026, 7, 2, tzinfo=timezone.utc)
    end = datetime(2026, 7, 7, 23, tzinfo=timezone.utc)
    sessions = sessions_between(start, end, end)
    assert [item[0].isoformat() for item in sessions] == ["2026-07-02", "2026-07-06", "2026-07-07"]


def test_projection_never_invents_missing_position_price():
    start = datetime(2026, 7, 6, tzinfo=timezone.utc)
    end = start + timedelta(days=2)
    competition = Competition("c", "l", "C", start, end, CompetitionStatus.ACTIVE,
                              build_rules_snapshot(start, end, "free"), start)
    portfolio = Portfolio("00000000-0000-0000-0000-000000000001", Decimal("3000"))
    portfolio.executions.append(Execution(
        "e", "o", "AAPL", OrderSide.BUY, Decimal("1"), Decimal("100"),
        Decimal("0"), start + timedelta(hours=1), Session.REGULAR,
        ExecutionSource.REPORTED, Decimal("100"),
    ))
    account = TradingAccount("c", "u", start, False, portfolio)
    points = project_account(account, competition, FixtureMarketDataAdapter(), end)
    assert points
    assert all(point.equity is None and point.missing == ("AAPL",) for point in points)


def test_projection_prefetches_one_market_window_per_symbol():
    start = datetime(2026, 7, 6, tzinfo=timezone.utc)
    end = start + timedelta(days=2)
    competition = Competition("c", "l", "C", start, end, CompetitionStatus.ACTIVE,
                              build_rules_snapshot(start, end, "free"), start)
    portfolio = Portfolio("00000000-0000-0000-0000-000000000001", Decimal("3000"))
    portfolio.executions.append(Execution(
        "e", "o", "AAPL", OrderSide.BUY, Decimal("1"), Decimal("100"),
        Decimal("0"), start + timedelta(hours=1), Session.REGULAR,
        ExecutionSource.REPORTED, Decimal("100"),
    ))
    account = TradingAccount("c", "u", start, False, portfolio)

    class CountingMarket(FixtureMarketDataAdapter):
        calls = 0

        def quotes(self, symbol, quote_start, quote_end):
            self.calls += 1
            return super().quotes(symbol, quote_start, quote_end)

    market = CountingMarket()
    project_account(account, competition, market, end)

    assert market.calls == 1


def test_projection_does_not_require_a_quote_for_a_closed_position():
    start = datetime(2026, 7, 6, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    competition = Competition("c", "l", "C", start, end, CompetitionStatus.ACTIVE,
                              build_rules_snapshot(start, end, "free"), start)
    portfolio = Portfolio("00000000-0000-0000-0000-000000000001", Decimal("3000"))
    portfolio.executions.extend((
        Execution(
            "buy", "buy-order", "SMCI", OrderSide.BUY, Decimal("1"),
            Decimal("100"), Decimal("0"), start + timedelta(minutes=1),
            Session.REGULAR, ExecutionSource.REPORTED, Decimal("100"),
        ),
        Execution(
            "sell", "sell-order", "SMCI", OrderSide.SELL, Decimal("1"),
            Decimal("110"), Decimal("0"), start + timedelta(minutes=2),
            Session.REGULAR, ExecutionSource.REPORTED, Decimal("110"),
        ),
    ))
    account = TradingAccount("c", "u", start, False, portfolio)

    points = project_account(account, competition, FixtureMarketDataAdapter(), end)

    assert points
    assert all(point.equity == Decimal("3010.00") for point in points)
    assert all(point.missing == () for point in points)


def test_projection_replays_compensation_with_the_original_declared_total():
    at = datetime(2026, 7, 6, 15, tzinfo=timezone.utc)
    original = Execution(
        "original", "order-original", "MU", OrderSide.BUY, Decimal("1"),
        Decimal("100"), Decimal("1.15"), at, Session.REGULAR,
        ExecutionSource.REPORTED, Decimal("101.15"),
    )
    correction = Execution(
        "correction", "order-correction", "MU", OrderSide.SELL, Decimal("1"),
        Decimal("100"), Decimal("1.15"), at + timedelta(minutes=1), Session.REGULAR,
        ExecutionSource.REPORTED, Decimal("101.15"), correction_of=original.id,
    )
    cash, positions = _replay(Decimal("3000"), (original, correction))
    assert cash == Decimal("3000.00")
    assert positions["MU"] == 0


def test_dashboard_openapi_contract_has_no_foreign_financial_fields():
    document = yaml.safe_load(Path("tradearena/presentation/openapi.yaml").read_text())
    schemas = document["components"]["schemas"]
    dashboard_names = set()
    for name in ("CompetitionDashboard", "DashboardPlayer", "DashboardTrade",
                 "DashboardSeriesPoint", "DashboardAllocation"):
        dashboard_names.update(schemas[name].get("properties", {}))
    assert dashboard_names.isdisjoint({
        "quantity", "price", "total_amount", "commission", "cash", "equity",
        "ledger", "orders", "idempotency_key", "portfolio_id",
    })


def test_dashboard_service_persists_canonical_projections_idempotently():
    store = MemoryStore()
    values = iter(f"id-{index}" for index in range(20))
    ids = lambda: next(values)
    started = datetime(2026, 7, 6, 13, tzinfo=timezone.utc)
    now = datetime(2026, 7, 7, 21, tzinfo=timezone.utc)
    owner = User(ids(), "owner@example.com", "email", "owner", started)
    with store.transaction() as uow:
        uow.users.add(owner)
        uow.profiles.save(Profile(owner.id, "Ana", "es", started, date(1990, 1, 1)))
    league = LeagueService(store, ids).create(owner.id, "Liga", started)
    competitions = CompetitionService(store, ids)
    draft = competitions.create(owner.id, league.id, "Verano", started,
                                datetime(2026, 7, 8, 23, tzinfo=timezone.utc), started)
    competitions.start(owner.id, league.id, draft.id, started)
    dashboard = DashboardService(store, FixtureMarketDataAdapter())

    first = dashboard.get(owner.id, league.id, draft.id, now)
    second = dashboard.get(owner.id, league.id, draft.id, now)

    assert first == second
    assert first["data_status"] == "complete"
    with store.transaction() as uow:
        account = uow.trading.get(draft.id, owner.id)
        assert len(uow.trading.list_portfolio_projections(account.portfolio.id)) == 2
        assert len(uow.trading.list_ranking_projections(draft.id)) == 2
