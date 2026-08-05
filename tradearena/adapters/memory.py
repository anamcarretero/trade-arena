"""Adaptador transaccional en memoria para desarrollo y pruebas de contrato."""

from __future__ import annotations

import copy
import threading
from contextlib import contextmanager

from tradearena.application.models import (
    AuditEvent, Invitation, League, Membership, Profile, User,
)


class MemoryStore:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.users_by_identity: dict[tuple[str, str], str] = {}
        self.users_by_email: dict[str, str] = {}
        self.profiles: dict[str, Profile] = {}
        self.leagues: dict[str, League] = {}
        self.memberships: dict[tuple[str, str], Membership] = {}
        self.invitations: dict[str, Invitation] = {}
        self.sessions: dict[str, tuple[str, object]] = {}
        self.audit: list[AuditEvent] = []
        self._lock = threading.RLock()

    @contextmanager
    def transaction(self):
        with self._lock:
            state = copy.deepcopy({
                "users": self.users,
                "users_by_identity": self.users_by_identity,
                "users_by_email": self.users_by_email,
                "profiles": self.profiles,
                "leagues": self.leagues,
                "memberships": self.memberships,
                "invitations": self.invitations,
                "sessions": self.sessions,
                "audit": self.audit,
            })
            try:
                yield self
            except Exception:
                for name, value in state.items():
                    setattr(self, name, value)
                raise

    def record_audit(
        self, occurred_at, actor_id, action, resource_type, resource_id, metadata=None
    ) -> None:
        self.audit.append(AuditEvent(
            len(self.audit) + 1, occurred_at, actor_id, action, resource_type,
            resource_id, metadata or {},
        ))
