"""Comandos operativos separados de TradeArena."""

from __future__ import annotations

import argparse
import os

from tradearena.migrations import migrate


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m tradearena")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="aplica migraciones PostgreSQL pendientes")
    commands.add_parser("serve", help="arranca la API FastAPI")
    args = parser.parse_args()

    if args.command == "migrate":
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            parser.error("DATABASE_URL es obligatorio")
        versions = migrate(dsn)
        if versions:
            print("Migraciones aplicadas: " + ", ".join(versions))
        else:
            print("No hay migraciones pendientes")
    elif args.command == "serve":
        import uvicorn

        uvicorn.run(
            "tradearena.presentation.server:create",
            factory=True,
            host="0.0.0.0",
            port=int(os.environ.get("PORT", "8080")),
            access_log=False,
        )


if __name__ == "__main__":
    main()
