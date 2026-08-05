"""Convenciones decimales versionadas del dominio financiero."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN

CENT = Decimal("0.01")
PRICE_TICK = Decimal("0.0001")
RETURN_TICK = Decimal("0.000000000001")


def decimal(value: Decimal | str | int) -> Decimal:
    """Convierte sin pasar por binarios de coma flotante."""
    if isinstance(value, float):
        raise TypeError("los importes float no están permitidos")
    return value if isinstance(value, Decimal) else Decimal(str(value))


def money(value: Decimal | str | int) -> Decimal:
    return decimal(value).quantize(CENT, rounding=ROUND_HALF_EVEN)


def price(value: Decimal | str | int) -> Decimal:
    return decimal(value).quantize(PRICE_TICK, rounding=ROUND_HALF_EVEN)


def rate(value: Decimal | str | int) -> Decimal:
    return decimal(value).quantize(RETURN_TICK, rounding=ROUND_HALF_EVEN)
