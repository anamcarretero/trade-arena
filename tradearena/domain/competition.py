"""Reglas versionadas que se materializan al iniciar una competición."""

from __future__ import annotations

from datetime import datetime


FREE_INITIAL_CAPITAL = "3000.00"


def build_rules_snapshot(
    starts_at: datetime, ends_at: datetime, plan: str,
) -> dict[str, object]:
    """Devuelve una nueva copia canónica de calendario y reglas v1."""

    if starts_at.tzinfo is None or ends_at.tzinfo is None:
        raise ValueError("el calendario necesita zona horaria")
    if ends_at <= starts_at:
        raise ValueError("el fin debe ser posterior al inicio")
    # Friends y Club aún no se activan. Mientras solo Free es operativo, ningún
    # dato de entrada puede alterar su capital inicial contractual.
    initial_capital = FREE_INITIAL_CAPITAL
    return {
        "version": "1",
        "calendar": {
            "market": "XNYS",
            "timezone": "America/New_York",
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
        },
        "rules": {
            "currency": "USD",
            "initial_capital": initial_capital,
            "whole_shares_only": True,
            "short_selling": False,
            "margin": False,
            "partial_executions": False,
            "commissions": {"regular": "0.99", "extended": "2.99"},
        },
    }
