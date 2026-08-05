"""Modelos de aplicación independientes del motor SQL."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class InvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


@dataclass
class User:
    id: str
    email: str
    identity_provider: str
    identity_subject: str
    created_at: datetime
    deleted_at: datetime | None = None


@dataclass
class Profile:
    user_id: str
    display_name: str
    locale: str
    accepted_terms_at: datetime
    birth_date: date


@dataclass
class League:
    id: str
    name: str
    owner_id: str
    created_at: datetime
    active: bool = True
    plan: str = "free"


@dataclass
class Membership:
    league_id: str
    user_id: str
    role: Role
    joined_at: datetime
    removed_at: datetime | None = None


@dataclass
class Invitation:
    id: str
    league_id: str
    email: str
    role: Role
    created_by: str
    created_at: datetime
    expires_at: datetime
    status: InvitationStatus = InvitationStatus.PENDING
    accepted_by: str | None = None


@dataclass(frozen=True)
class AuditEvent:
    sequence: int
    occurred_at: datetime
    actor_id: str | None
    action: str
    resource_type: str
    resource_id: str
    metadata: dict[str, str] = field(default_factory=dict)
