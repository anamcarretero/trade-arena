"""Unidad de trabajo mínima usada por los casos de uso de Fase 2."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol


class Store(Protocol):
    def transaction(self) -> AbstractContextManager["Store"]: ...
