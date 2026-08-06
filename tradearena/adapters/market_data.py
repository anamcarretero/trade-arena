"""Datos de mercado deterministas para desarrollo y pruebas."""

from __future__ import annotations

from datetime import datetime

from tradearena.domain.trading import CorporateAction, Quote


class FixtureMarketDataAdapter:
    def __init__(
        self, quotes: tuple[Quote, ...] = (),
        actions: tuple[CorporateAction, ...] = (),
        suspended_symbols: tuple[str, ...] = (),
    ) -> None:
        self._quotes = quotes
        self._actions = actions
        self._suspended_symbols = {item.upper() for item in suspended_symbols}

    def quotes(self, symbol: str, start: datetime, end: datetime):
        normalized = symbol.upper()
        return tuple(
            item for item in self._quotes
            if item.symbol == normalized and start <= item.observed_at <= end
        )

    def corporate_actions(self, symbol: str, start: datetime, end: datetime):
        normalized = symbol.upper()
        return tuple(
            item for item in self._actions
            if item.symbol.upper() == normalized and start <= item.occurred_at <= end
        )

    def definitively_suspended(self, symbol: str, as_of: datetime) -> bool:
        return symbol.upper() in self._suspended_symbols
