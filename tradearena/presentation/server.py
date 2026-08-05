"""Factoría ASGI de producción conectada a PostgreSQL."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from tradearena.adapters.postgres import PostgresStore
from tradearena.application.services import AccountService, LeagueService, SessionService
from tradearena.presentation.api import Api
from tradearena.presentation.asgi import create_app


def create():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL es obligatorio para arrancar la API")
    store = PostgresStore(dsn)
    ids = lambda: str(uuid4())
    clock = lambda: datetime.now(timezone.utc)
    dispatcher = Api(
        SessionService(store, clock=clock),
        AccountService(store, ids),
        LeagueService(store, ids),
        clock,
    )
    return create_app(dispatcher, store.ready)
