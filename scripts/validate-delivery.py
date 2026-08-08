#!/usr/bin/env python3
"""Valida sintaxis y fronteras mínimas de IaC, workflows y scripts."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def fail(message: str) -> None:
    raise SystemExit(f"Error de entrega: {message}")


def main() -> None:
    for path in sorted(WORKFLOWS.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "jobs" not in data:
            fail(f"{path.relative_to(ROOT)} no es un workflow válido")
        permissions = data.get("permissions")
        if permissions is None:
            fail(f"{path.relative_to(ROOT)} debe declarar permissions explícitos")
        if permissions == "write-all":
            fail(f"{path.relative_to(ROOT)} no puede usar write-all")

    staging = (WORKFLOWS / "staging.yml").read_text(encoding="utf-8")
    if "id-token: write" not in staging:
        fail("staging.yml necesita id-token: write para OIDC")
    if re.search(r"(?i)(service.account|google).*key", staging):
        fail("staging.yml no puede usar claves persistentes de servicio")
    for forbidden in ("--prod", "production_environment", "MARKET_DATA_PROVIDER: yahoo"):
        if forbidden in staging:
            fail(f"staging.yml contiene capacidad prohibida: {forbidden}")

    terraform = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "infra" / "staging").glob("*.tf"))
    )
    required = (
        '"europe-west3"',
        '"aws-eu-central-1"',
        'min_instance_count = 0',
        'assertion.ref == \'refs/heads/main\'',
        'value = "fixture"',
    )
    for contract in required:
        if contract not in terraform:
            fail(f"falta contrato de staging en Terraform: {contract}")
    for forbidden in ("google_cloud_scheduler_job", "massive", "stripe"):
        if forbidden in terraform.lower():
            fail(f"Terraform invade una fase posterior: {forbidden}")

    print("OK sintaxis YAML, permisos, OIDC y límites de fase")


if __name__ == "__main__":
    main()
