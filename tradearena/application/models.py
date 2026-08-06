"""Modelos de aplicación independientes del motor SQL."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from tradearena.domain.trading import Portfolio


class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class InvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class CompetitionStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    FINISHED = "finished"


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
class LeagueMemberView:
    user_id: str
    display_name: str
    role: Role
    joined_at: datetime


@dataclass(frozen=True)
class LeagueInvitationView:
    id: str
    email: str
    role: Role
    expires_at: datetime
    status: InvitationStatus


@dataclass(frozen=True)
class LeagueView:
    id: str
    name: str
    owner_id: str
    created_at: datetime
    active: bool
    plan: str
    actor_role: Role
    max_members: int
    members: tuple[LeagueMemberView, ...]
    invitations: tuple[LeagueInvitationView, ...]


@dataclass(frozen=True)
class OwnInvitationView:
    id: str
    league_id: str
    league_name: str
    expires_at: datetime


@dataclass
class Competition:
    id: str
    league_id: str
    name: str
    starts_at: datetime
    ends_at: datetime
    status: CompetitionStatus = CompetitionStatus.DRAFT
    rules_snapshot: dict[str, object] | None = None
    started_at: datetime | None = None


@dataclass(frozen=True)
class CompetitionView:
    id: str
    league_id: str
    name: str
    starts_at: datetime
    ends_at: datetime
    status: CompetitionStatus
    rules_snapshot: dict[str, object] | None
    started_at: datetime | None


@dataclass
class TradingAccount:
    competition_id: str
    user_id: str
    joined_at: datetime
    joined_late: bool
    portfolio: Portfolio


@dataclass(frozen=True)
class PositionView:
    symbol: str
    quantity: str
    price: str | None
    market_value: str | None


@dataclass(frozen=True)
class OrderView:
    id: str
    symbol: str
    side: str
    quantity: str
    order_type: str
    allow_extended_hours: bool
    limit_price: str | None
    status: str
    rejection_reason: str | None
    submitted_at: datetime


@dataclass(frozen=True)
class ExecutionView:
    id: str
    order_id: str
    symbol: str
    side: str
    quantity: str
    price: str
    commission: str
    session: str
    executed_at: datetime
    source: str
    total_amount: str | None
    currency: str
    fx_rate: str
    correction_of: str | None


@dataclass(frozen=True)
class PortfolioView:
    id: str
    competition_id: str
    user_id: str
    currency: str
    initial_cash: str
    cash: str
    joined_at: datetime
    joined_late: bool
    positions: tuple[PositionView, ...]
    orders: tuple[OrderView, ...]
    executions: tuple[ExecutionView, ...]
    equity: str
    cumulative_return: str


@dataclass(frozen=True)
class RankingView:
    competition_id: str
    as_of: datetime
    rows: tuple[dict[str, object], ...]
    digest: str


@dataclass(frozen=True)
class AuditEvent:
    sequence: int
    occurred_at: datetime
    actor_id: str | None
    action: str
    resource_type: str
    resource_id: str
    metadata: dict[str, str] = field(default_factory=dict)
