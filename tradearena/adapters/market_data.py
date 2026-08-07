"""Adaptadores de mercado intercambiables para desarrollo y pruebas."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from tradearena.domain.trading import CorporateAction, Quote
from tradearena.domain.trading import Session


LOGGER = logging.getLogger(__name__)


class MarketDataProviderError(RuntimeError):
    """El proveedor configurado no pudo entregar datos utilizables."""


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


class YahooFinanceMarketDataAdapter:
    """Cierres diarios de Yahoo Finance para entornos de desarrollo.

    El adaptador implementa ``MarketDataPort`` sin filtrar detalles HTTP al
    dominio. No debe activarse en producción: Yahoo no ofrece aquí garantías
    de disponibilidad ni una licencia de redistribución para TradeArena.
    """

    _HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")

    def __init__(
        self,
        opener: Callable[..., Any] = urllib.request.urlopen,
        timeout: float = 15.0,
    ) -> None:
        self._opener = opener
        self._timeout = timeout
        self._cache: dict[tuple[str, int, int], tuple[Quote, ...]] = {}

    def quotes(self, symbol: str, start: datetime, end: datetime):
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("el rango de cotizaciones necesita zona horaria")
        if end < start:
            return ()
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("el símbolo es obligatorio")
        # Yahoo interpreta period2 como exclusivo. Se amplía un día para no
        # perder la vela de la última sesión solicitada.
        period1 = int(start.timestamp())
        period2 = int((end + timedelta(days=1)).timestamp())
        key = (normalized, period1, period2)
        if key not in self._cache:
            try:
                self._cache[key] = self._fetch(normalized, period1, period2)
            except MarketDataProviderError as exc:
                # La indisponibilidad del proveedor se expresa como ausencia de
                # cotización. El dashboard conservará la jornada incompleta.
                LOGGER.warning("Cotizaciones de desarrollo no disponibles: %s", exc)
                self._cache[key] = ()
        return tuple(
            quote for quote in self._cache[key]
            if start <= quote.observed_at <= end
        )

    def corporate_actions(self, symbol: str, start: datetime, end: datetime):
        # Las valoraciones de desarrollo consumen únicamente cierres. Eventos
        # corporativos exigirán un adaptador licenciado y persistencia en Fase 4.
        return ()

    def definitively_suspended(self, symbol: str, as_of: datetime) -> bool:
        # Una respuesta vacía o un error temporal de Yahoo nunca prueba una
        # suspensión definitiva.
        return False

    def _fetch(self, symbol: str, period1: int, period2: int) -> tuple[Quote, ...]:
        query = urllib.parse.urlencode({
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "history",
        })
        encoded_symbol = urllib.parse.quote(symbol, safe="")
        last_error: Exception | None = None
        for host in self._HOSTS:
            request = urllib.request.Request(
                f"https://{host}/v8/finance/chart/{encoded_symbol}?{query}",
                headers={
                    "Accept": "application/json",
                    "User-Agent": "TradeArena-development/1.0",
                },
            )
            try:
                with self._opener(request, timeout=self._timeout) as response:
                    payload = json.load(response)
                return self._parse(symbol, payload)
            except (OSError, TimeoutError, ValueError, urllib.error.URLError) as exc:
                last_error = exc
        raise MarketDataProviderError(
            f"Yahoo Finance no respondió para {symbol}: {last_error}"
        )

    @staticmethod
    def _parse(symbol: str, payload: dict[str, Any]) -> tuple[Quote, ...]:
        chart = payload.get("chart") or {}
        error = chart.get("error")
        results = chart.get("result") or []
        if error or not results:
            description = error.get("description") if isinstance(error, dict) else None
            raise MarketDataProviderError(
                f"Yahoo Finance no devolvió datos para {symbol}"
                + (f": {description}" if description else "")
            )
        result = results[0]
        timestamps = result.get("timestamp") or []
        quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
        closes = quotes.get("close") or []
        parsed = []
        for raw_timestamp, raw_close in zip(timestamps, closes):
            if raw_close is None:
                continue
            parsed.append(Quote(
                symbol,
                Decimal(str(raw_close)),
                datetime.fromtimestamp(raw_timestamp, timezone.utc),
                Session.REGULAR,
            ))
        return tuple(parsed)


def build_market_data_adapter(provider: str):
    """Compone el proveedor sin cambiar los casos de uso consumidores."""
    normalized = provider.strip().lower()
    if normalized == "fixture":
        return FixtureMarketDataAdapter()
    if normalized == "yahoo":
        return YahooFinanceMarketDataAdapter()
    raise ValueError(
        "MARKET_DATA_PROVIDER debe ser 'fixture' o 'yahoo'"
    )
