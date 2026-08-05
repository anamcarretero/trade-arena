"""Ejecutor incremental de migraciones SQL explícitas."""

from __future__ import annotations

from pathlib import Path

import psycopg


DEFAULT_DIRECTORY = Path(__file__).parents[1] / "migrations"


def applied_versions(connection) -> set[str]:
    exists = connection.execute(
        "SELECT to_regclass('schema_migrations') AS table_name"
    ).fetchone()[0]
    if exists is None:
        return set()
    return {
        row[0] for row in connection.execute(
            "SELECT version FROM schema_migrations"
        ).fetchall()
    }


def migrate(dsn: str, directory: Path = DEFAULT_DIRECTORY) -> list[str]:
    """Aplica en orden los scripts aún ausentes y devuelve sus versiones."""

    applied: list[str] = []
    with psycopg.connect(dsn, autocommit=True) as connection:
        known = applied_versions(connection)
        for path in sorted(directory.glob("[0-9][0-9][0-9]_*.sql")):
            version = path.stem
            if version in known:
                continue
            connection.execute(path.read_text(encoding="utf-8"))
            applied.append(version)
            known.add(version)
    return applied
