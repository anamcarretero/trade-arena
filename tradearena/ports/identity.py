"""Contrato estable para proveedores de identidad."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Protocol


@dataclass(frozen=True)
class IdentityAssertion:
    provider: str
    subject: str
    email: str
    email_verified: bool


class IdentityPort(Protocol):
    def begin_email_login(self, email: str, expires_at: datetime) -> str: ...

    def verify_email_token(self, token: str, now: datetime) -> IdentityAssertion: ...

    def verify_google_claims(self, claims: Mapping[str, object]) -> IdentityAssertion: ...
