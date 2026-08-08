#!/usr/bin/env python3
"""Verifica migraciones en un esquema vacío y desde la versión anterior."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).parents[1]
MIGRATIONS = ROOT / "migrations"
sys.path.insert(0, str(ROOT))

from tradearena.migrations import migrate  # noqa: E402


def schema_dsn(base_dsn: str, schema: str) -> str:
    return make_conninfo(base_dsn, options=f"-c search_path={schema}")


def main() -> None:
    base_dsn = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not base_dsn:
        raise SystemExit("TEST_DATABASE_URL o DATABASE_URL es obligatorio")

    migrations = sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql"))
    if not migrations:
        raise SystemExit("No se encontraron migraciones")

    empty_schema = f"ta_empty_{uuid4().hex}"
    previous_schema = f"ta_previous_{uuid4().hex}"
    with psycopg.connect(base_dsn, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{empty_schema}"')
        connection.execute(f'CREATE SCHEMA "{previous_schema}"')

    try:
        applied = migrate(schema_dsn(base_dsn, empty_schema))
        if applied != [path.stem for path in migrations]:
            raise SystemExit("La migración sobre esquema vacío no aplicó la serie completa")

        with tempfile.TemporaryDirectory(prefix="tradearena-previous-") as directory:
            previous = Path(directory)
            for path in migrations[:-1]:
                shutil.copy2(path, previous / path.name)
            migrate(schema_dsn(base_dsn, previous_schema), previous)
            upgraded = migrate(schema_dsn(base_dsn, previous_schema))
            expected = [migrations[-1].stem]
            if upgraded != expected:
                raise SystemExit(
                    f"Upgrade desde versión anterior inesperado: {upgraded!r} != {expected!r}"
                )
        print("OK migraciones: esquema vacío y versión anterior")
    finally:
        with psycopg.connect(base_dsn, autocommit=True) as connection:
            connection.execute(f'DROP SCHEMA IF EXISTS "{empty_schema}" CASCADE')
            connection.execute(f'DROP SCHEMA IF EXISTS "{previous_schema}" CASCADE')


if __name__ == "__main__":
    main()
