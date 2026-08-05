"""Cartera virtual y ejecución determinista de órdenes.

Todas las decisiones dependen de entradas explícitas (órdenes, cotizaciones y
eventos corporativos); no se consulta el reloj, la red ni el sistema de
archivos. Reproducir la misma secuencia produce el mismo estado y hash.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .money import decimal, money, price, rate


class Session(str, Enum):
    REGULAR = "regular"
    EXTENDED = "extended"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class CorporateActionKind(str, Enum):
    DIVIDEND = "dividend"
    SPLIT = "split"


@dataclass(frozen=True)
class Posting:
    account: str
    amount: Decimal


@dataclass(frozen=True)
class JournalEntry:
    sequence: int
    occurred_at: datetime
    kind: str
    reference: str
    postings: tuple[Posting, ...]

    def __post_init__(self) -> None:
        if sum((p.amount for p in self.postings), Decimal("0")) != 0:
            raise ValueError("el asiento debe estar balanceado")


@dataclass(frozen=True)
class Quote:
    symbol: str
    value: Decimal
    observed_at: datetime
    session: Session

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "value", price(self.value))
        if self.value <= 0:
            raise ValueError("el precio debe ser positivo")
        if self.observed_at.tzinfo is None:
            raise ValueError("la cotización necesita zona horaria")


@dataclass(frozen=True)
class Order:
    id: str
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    allow_extended_hours: bool
    submitted_at: datetime
    limit_price: Decimal | None = None
    status: OrderStatus = OrderStatus.PENDING
    rejection_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.upper())
        if self.quantity <= 0:
            raise ValueError("la cantidad debe ser un entero positivo")
        if self.submitted_at.tzinfo is None:
            raise ValueError("la orden necesita zona horaria")
        if self.order_type is OrderType.LIMIT and self.limit_price is None:
            raise ValueError("una orden límite necesita precio límite")
        if self.order_type is OrderType.MARKET and self.limit_price is not None:
            raise ValueError("una orden de mercado no admite precio límite")
        if self.limit_price is not None:
            object.__setattr__(self, "limit_price", price(self.limit_price))
            if self.limit_price <= 0:
                raise ValueError("el precio límite debe ser positivo")


@dataclass(frozen=True)
class Execution:
    id: str
    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: Decimal
    commission: Decimal
    executed_at: datetime
    session: Session


@dataclass(frozen=True)
class CorporateAction:
    id: str
    kind: CorporateActionKind
    symbol: str
    occurred_at: datetime
    amount_per_share: Decimal | None = None
    split_numerator: int | None = None
    split_denominator: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.upper())
        if self.occurred_at.tzinfo is None:
            raise ValueError("el evento corporativo necesita zona horaria")


@dataclass
class Portfolio:
    id: str
    initial_cash: Decimal
    cash: Decimal = field(init=False)
    positions: dict[str, int] = field(default_factory=dict)
    orders: dict[str, Order] = field(default_factory=dict)
    executions: list[Execution] = field(default_factory=list)
    ledger: list[JournalEntry] = field(default_factory=list)
    applied_actions: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.initial_cash = money(self.initial_cash)
        if self.initial_cash <= 0:
            raise ValueError("el capital inicial debe ser positivo")
        self.cash = self.initial_cash
        self._record(datetime.min.replace(tzinfo=_UTC), "initial_cash", self.id, (
            Posting("cash", self.initial_cash),
            Posting("equity:initial", -self.initial_cash),
        ))

    def _record(
        self,
        occurred_at: datetime,
        kind: str,
        reference: str,
        postings: tuple[Posting, ...],
    ) -> None:
        self.ledger.append(JournalEntry(
            sequence=len(self.ledger) + 1,
            occurred_at=occurred_at,
            kind=kind,
            reference=reference,
            postings=postings,
        ))

    def equity(self, prices: dict[str, Decimal]) -> Decimal:
        value = self.cash + sum(
            (decimal(qty) * price(prices[symbol]) for symbol, qty in self.positions.items()),
            Decimal("0"),
        )
        return money(value)

    def cumulative_return(self, prices: dict[str, Decimal]) -> Decimal:
        return rate((self.equity(prices) / self.initial_cash) - Decimal("1"))

    def snapshot(self, prices: dict[str, Decimal], as_of: datetime) -> "PortfolioSnapshot":
        if as_of.tzinfo is None:
            raise ValueError("el snapshot necesita zona horaria")
        normalized_prices = {key.upper(): price(value) for key, value in sorted(prices.items())}
        payload = {
            "as_of": as_of.isoformat(),
            "cash": str(self.cash),
            "executions": [execution.id for execution in self.executions],
            "portfolio_id": self.id,
            "positions": dict(sorted(self.positions.items())),
            "prices": {key: str(value) for key, value in normalized_prices.items()},
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return PortfolioSnapshot(
            portfolio_id=self.id,
            as_of=as_of,
            cash=self.cash,
            positions=tuple(sorted(self.positions.items())),
            equity=self.equity(normalized_prices),
            cumulative_return=self.cumulative_return(normalized_prices),
            digest=digest,
        )


@dataclass(frozen=True)
class PortfolioSnapshot:
    portfolio_id: str
    as_of: datetime
    cash: Decimal
    positions: tuple[tuple[str, int], ...]
    equity: Decimal
    cumulative_return: Decimal
    digest: str


class TradingEngine:
    REGULAR_COMMISSION = Decimal("0.99")
    EXTENDED_COMMISSION = Decimal("2.99")

    def submit(self, portfolio: Portfolio, order: Order) -> Order:
        if order.id in portfolio.orders:
            raise ValueError("id de orden duplicado")
        portfolio.orders[order.id] = order
        return order

    def cancel(self, portfolio: Portfolio, order_id: str) -> Order:
        order = portfolio.orders[order_id]
        if order.status is not OrderStatus.PENDING:
            raise ValueError("solo se puede cancelar una orden pendiente")
        cancelled = replace(order, status=OrderStatus.CANCELLED)
        portfolio.orders[order_id] = cancelled
        return cancelled

    def process_quote(self, portfolio: Portfolio, quote: Quote) -> tuple[Execution, ...]:
        results: list[Execution] = []
        for order_id in list(portfolio.orders):
            order = portfolio.orders[order_id]
            if order.status is not OrderStatus.PENDING or order.symbol != quote.symbol:
                continue
            if quote.observed_at < order.submitted_at:
                continue
            if quote.session is Session.EXTENDED and not order.allow_extended_hours:
                continue
            if not self._crosses(order, quote.value):
                continue
            execution = self._execute(portfolio, order, quote)
            if execution is not None:
                results.append(execution)
        return tuple(results)

    @staticmethod
    def _crosses(order: Order, quoted: Decimal) -> bool:
        if order.order_type is OrderType.MARKET:
            return True
        assert order.limit_price is not None
        if order.side is OrderSide.BUY:
            return quoted <= order.limit_price
        return quoted >= order.limit_price

    def _execute(self, portfolio: Portfolio, order: Order, quote: Quote) -> Execution | None:
        commission = money(
            self.REGULAR_COMMISSION if quote.session is Session.REGULAR
            else self.EXTENDED_COMMISSION
        )
        gross = money(quote.value * order.quantity)
        if order.side is OrderSide.BUY:
            if portfolio.cash < gross + commission:
                portfolio.orders[order.id] = replace(
                    order, status=OrderStatus.REJECTED,
                    rejection_reason="insufficient_cash",
                )
                return None
            portfolio.cash = money(portfolio.cash - gross - commission)
            portfolio.positions[order.symbol] = portfolio.positions.get(order.symbol, 0) + order.quantity
            postings = (
                Posting(f"asset:{order.symbol}", gross),
                Posting("expense:commission", commission),
                Posting("cash", -(gross + commission)),
            )
        else:
            if portfolio.positions.get(order.symbol, 0) < order.quantity:
                portfolio.orders[order.id] = replace(
                    order, status=OrderStatus.REJECTED,
                    rejection_reason="insufficient_position",
                )
                return None
            portfolio.cash = money(portfolio.cash + gross - commission)
            remaining = portfolio.positions[order.symbol] - order.quantity
            if remaining:
                portfolio.positions[order.symbol] = remaining
            else:
                del portfolio.positions[order.symbol]
            postings = (
                Posting("cash", gross - commission),
                Posting("expense:commission", commission),
                Posting(f"asset:{order.symbol}", -gross),
            )
        execution = Execution(
            id=f"execution:{order.id}", order_id=order.id, symbol=order.symbol,
            side=order.side, quantity=order.quantity, price=quote.value,
            commission=commission, executed_at=quote.observed_at,
            session=quote.session,
        )
        portfolio.executions.append(execution)
        portfolio.orders[order.id] = replace(order, status=OrderStatus.FILLED)
        portfolio._record(quote.observed_at, "execution", execution.id, postings)
        return execution

    def apply_corporate_action(self, portfolio: Portfolio, action: CorporateAction) -> None:
        if action.id in portfolio.applied_actions:
            return
        symbol = action.symbol.upper()
        quantity = portfolio.positions.get(symbol, 0)
        if action.kind is CorporateActionKind.DIVIDEND:
            if action.amount_per_share is None:
                raise ValueError("el dividendo necesita importe por acción")
            amount = money(price(action.amount_per_share) * quantity)
            portfolio.cash = money(portfolio.cash + amount)
            portfolio._record(action.occurred_at, "dividend", action.id, (
                Posting("cash", amount), Posting("income:dividend", -amount),
            ))
        else:
            numerator = action.split_numerator or 0
            denominator = action.split_denominator or 0
            if numerator <= 0 or denominator <= 0:
                raise ValueError("la proporción del split debe ser positiva")
            product = quantity * numerator
            if product % denominator:
                raise ValueError("el split produciría unidades fraccionarias")
            portfolio.positions[symbol] = product // denominator
            portfolio._record(action.occurred_at, "split", action.id, ())
        portfolio.applied_actions.add(action.id)


from datetime import timezone

_UTC = timezone.utc
