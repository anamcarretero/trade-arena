"""Contratos de proveedor reservados por el monolito modular."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Protocol

from tradearena.domain.trading import CorporateAction, Quote


class MarketDataPort(Protocol):
    def quotes(self, symbol: str, start: datetime, end: datetime) -> Iterable[Quote]: ...

    def corporate_actions(
        self, symbol: str, start: datetime, end: datetime
    ) -> Iterable[CorporateAction]: ...


class BillingPort(Protocol):
    def verify_event(self, payload: bytes, signature: str) -> object: ...


class QueuePort(Protocol):
    def enqueue(self, kind: str, payload: dict, idempotency_key: str) -> None: ...


class NotificationPort(Protocol):
    def publish(self, user_id: str, kind: str, payload: dict) -> None: ...
