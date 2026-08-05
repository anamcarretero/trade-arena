"""Factoría ASGI de producción conectada a PostgreSQL."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from tradearena.adapters.identity import Auth0IdentityAdapter
from tradearena.adapters.postgres import PostgresStore
from tradearena.application.services import (
    AccountService, AuthService, LeagueService, SessionService,
)
from tradearena.presentation.api import Api
from tradearena.presentation.asgi import create_app


def create():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL es obligatorio para arrancar la API")
    required = ["AUTH0_DOMAIN", "AUTH0_CLIENT_ID", "BFF_SHARED_SECRET"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"variables obligatorias ausentes: {', '.join(missing)}")
    store = PostgresStore(dsn)
    ids = lambda: str(uuid4())
    clock = lambda: datetime.now(timezone.utc)
    sessions = SessionService(store, clock=clock)
    accounts = AccountService(store, ids)
    auth = AuthService(
        Auth0IdentityAdapter(os.environ["AUTH0_DOMAIN"], os.environ["AUTH0_CLIENT_ID"]),
        accounts,
        sessions,
    )
    dispatcher = Api(
        sessions,
        accounts,
        LeagueService(store, ids),
        clock,
        auth,
        os.environ["BFF_SHARED_SECRET"],
    )
    return create_app(dispatcher, store.ready)
