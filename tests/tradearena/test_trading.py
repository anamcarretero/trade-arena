from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tradearena.adapters.market_data import FixtureMarketDataAdapter
from tradearena.domain.ranking import build_ranking
from tradearena.domain.trading import (
    CorporateAction, CorporateActionKind, Order, OrderSide, OrderStatus,
    OrderType, Portfolio, Quote, Session, TradingEngine,
)

UTC = timezone.utc
T0 = datetime(2026, 8, 3, 14, 30, tzinfo=UTC)


def order(
    order_id="o1", *, side=OrderSide.BUY, quantity=2,
    kind=OrderType.MARKET, limit=None, extended=False,
):
    return Order(order_id, "AAPL", side, quantity, kind, extended, T0, limit)


def quote(value="100", *, session=Session.REGULAR, minute=1):
    return Quote("AAPL", Decimal(value), T0 + timedelta(minutes=minute), session)


def test_regular_market_execution_is_complete_and_charges_099():
    portfolio = Portfolio("p1", Decimal("1000"))
    engine = TradingEngine()
    engine.submit(portfolio, order())
    executions = engine.process_quote(portfolio, quote())

    assert len(executions) == 1
    assert executions[0].quantity == 2
    assert executions[0].commission == Decimal("0.99")
    assert portfolio.cash == Decimal("799.01")
    assert portfolio.positions == {"AAPL": 2}
    assert portfolio.orders["o1"].status is OrderStatus.FILLED
    assert all(sum((p.amount for p in entry.postings), Decimal("0")) == 0
               for entry in portfolio.ledger)


def test_order_outside_allowed_session_remains_pending():
    portfolio = Portfolio("p1", Decimal("1000"))
    engine = TradingEngine()
    engine.submit(portfolio, order())
    assert engine.process_quote(portfolio, quote(session=Session.EXTENDED)) == ()
    assert portfolio.orders["o1"].status is OrderStatus.PENDING


def test_extended_execution_costs_299_when_enabled():
    portfolio = Portfolio("p1", Decimal("1000"))
    engine = TradingEngine()
    engine.submit(portfolio, order(extended=True))
    execution, = engine.process_quote(portfolio, quote(session=Session.EXTENDED))
    assert execution.commission == Decimal("2.99")
    assert portfolio.cash == Decimal("797.01")


@pytest.mark.parametrize(
    ("side", "quoted", "crosses"),
    [
        (OrderSide.BUY, "99", True),
        (OrderSide.BUY, "101", False),
        (OrderSide.SELL, "101", True),
        (OrderSide.SELL, "99", False),
    ],
)
def test_limit_crossing_rules(side, quoted, crosses):
    portfolio = Portfolio("p1", Decimal("1000"))
    engine = TradingEngine()
    if side is OrderSide.SELL:
        portfolio.positions["AAPL"] = 2
    engine.submit(portfolio, order(
        side=side, kind=OrderType.LIMIT, limit=Decimal("100")
    ))
    assert bool(engine.process_quote(portfolio, quote(quoted))) is crosses


def test_insufficient_cash_rejects_without_execution_or_commission():
    portfolio = Portfolio("p1", Decimal("100"))
    engine = TradingEngine()
    engine.submit(portfolio, order(quantity=1))
    assert engine.process_quote(portfolio, quote("100")) == ()
    assert portfolio.cash == Decimal("100.00")
    assert portfolio.orders["o1"].rejection_reason == "insufficient_cash"


def test_dividend_is_idempotent_and_split_requires_whole_units():
    portfolio = Portfolio("p1", Decimal("1000"))
    portfolio.positions["AAPL"] = 3
    engine = TradingEngine()
    dividend = CorporateAction(
        "d1", CorporateActionKind.DIVIDEND, "AAPL", T0,
        amount_per_share=Decimal("0.50"),
    )
    engine.apply_corporate_action(portfolio, dividend)
    engine.apply_corporate_action(portfolio, dividend)
    assert portfolio.cash == Decimal("1001.50")

    split = CorporateAction(
        "s1", CorporateActionKind.SPLIT, "AAPL", T0,
        split_numerator=2, split_denominator=1,
    )
    engine.apply_corporate_action(portfolio, split)
    assert portfolio.positions["AAPL"] == 6


def _replay():
    portfolio = Portfolio("p1", Decimal("1000"))
    engine = TradingEngine()
    engine.submit(portfolio, order())
    engine.process_quote(portfolio, quote())
    return portfolio.snapshot({"AAPL": Decimal("110")}, T0.replace(hour=20))


def test_same_inputs_produce_identical_portfolio_and_ranking_snapshots():
    first = _replay()
    second = _replay()
    assert first == second
    ranking_a = build_ranking("c1", first.as_of, [("u1", first, False)])
    ranking_b = build_ranking("c1", second.as_of, [("u1", second, False)])
    assert ranking_a == ranking_b
    assert first.cumulative_return == Decimal("0.019010000000")


def test_float_money_is_rejected_to_avoid_platform_rounding():
    with pytest.raises(TypeError):
        Portfolio("p1", 1000.0)


def test_fixture_market_adapter_is_deterministic_and_bounded():
    q1 = quote("100", minute=1)
    q2 = quote("101", minute=2)
    adapter = FixtureMarketDataAdapter((q2, q1))
    assert adapter.quotes("aapl", T0, T0 + timedelta(minutes=1)) == (q1,)
