from datetime import datetime, timedelta, timezone

import pytest

from tradearena.adapters.memory import MemoryStore
from tradearena.application.models import CompetitionStatus
from tradearena.application.services import (
    AccountService, CompetitionService, Conflict, LeagueService, NotFound,
    SessionService,
)
from tradearena.ports.identity import IdentityAssertion
from tradearena.presentation.api import Api
from tradearena.domain.competition import build_rules_snapshot


NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


class Ids:
    def __init__(self):
        self.value = 0

    def __call__(self):
        self.value += 1
        return f"id-{self.value}"


def test_domain_snapshot_is_versioned_and_free_capital_is_fixed():
    snapshot = build_rules_snapshot(
        NOW + timedelta(days=1), NOW + timedelta(days=2), "free",
    )
    assert snapshot["version"] == "1"
    assert snapshot["calendar"]["starts_at"] \
        == (NOW + timedelta(days=1)).isoformat()
    assert snapshot["rules"]["initial_capital"] == "3000.00"
    assert snapshot["rules"]["currency"] == "USD"
    assert snapshot["rules"]["whole_shares_only"] is False
    assert snapshot["rules"]["commissions"]["regular"] == "1.15"


@pytest.fixture
def context():
    store = MemoryStore()
    ids = Ids()
    accounts = AccountService(store, ids)
    leagues = LeagueService(store, ids)
    competitions = CompetitionService(store, ids)
    sessions = SessionService(store, ids, lambda: NOW)

    def user(email):
        return accounts.login(IdentityAssertion("email", email, email, True), NOW)

    owner = user("owner@example.com")
    outsider = user("outsider@example.com")
    member = user("member@example.com")
    owner_token = sessions.issue(owner.id)
    outsider_token = sessions.issue(outsider.id)
    member_token = sessions.issue(member.id)
    league = leagues.create(owner.id, "Privada", NOW)
    invitation = leagues.invite(owner.id, league.id, member.email, NOW)
    leagues.accept(member.id, invitation.id, NOW)
    api = Api(
        sessions, accounts, leagues, lambda: NOW, competitions=competitions,
    )
    return {
        "store": store, "ids": ids, "leagues": leagues,
        "competitions": competitions, "api": api, "owner": owner,
        "outsider": outsider, "member": member, "league": league,
        "owner_token": owner_token, "outsider_token": outsider_token,
        "member_token": member_token,
    }


def test_creation_is_draft_and_start_fixes_free_rules(context):
    service = context["competitions"]
    league = context["league"]
    created = service.create(
        context["owner"].id, league.id, "Otoño",
        NOW + timedelta(days=1), NOW + timedelta(days=31), NOW,
    )
    assert created.status is CompetitionStatus.DRAFT
    assert created.rules_snapshot is None

    started = service.start(context["owner"].id, league.id, created.id, NOW)
    assert started.status is CompetitionStatus.ACTIVE
    assert started.rules_snapshot["calendar"]["timezone"] == "America/New_York"
    assert started.rules_snapshot["rules"]["initial_capital"] == "3000.00"
    with pytest.raises(Conflict):
        service.start(context["owner"].id, league.id, created.id, NOW)


def test_snapshot_copies_rules_at_start_and_remains_immutable(context):
    current = {"value": "before"}

    def rules(competition, league):
        return {
            "version": "test", "calendar": {"value": current["value"]},
            "rules": {"initial_capital": "3000.00", "currency": "USD"},
        }

    service = CompetitionService(context["store"], context["ids"], rules)
    created = service.create(
        context["owner"].id, context["league"].id, "Snapshot",
        NOW + timedelta(days=1), NOW + timedelta(days=2), NOW,
    )
    current["value"] = "at-start"
    started = service.start(
        context["owner"].id, context["league"].id, created.id, NOW,
    )
    current["value"] = "after-start"
    started.rules_snapshot["calendar"]["value"] = "tampered-view"

    persisted = service.get(
        context["owner"].id, context["league"].id, created.id,
    )
    assert persisted.rules_snapshot["calendar"]["value"] == "at-start"

    with context["store"].transaction() as uow:
        stored = uow.competitions.get(created.id)
        stored.rules_snapshot["calendar"]["value"] = "tampered-store"
        with pytest.raises(ValueError, match="inmutable"):
            uow.competitions.save(stored)


def test_foreign_league_and_competition_are_hidden_by_api(context):
    api = context["api"]
    league_id = context["league"].id
    created = api.handle(
        "POST", f"/api/v1/leagues/{league_id}/competitions",
        context["owner_token"], {
            "name": "Privada",
            "starts_at": (NOW + timedelta(days=1)).isoformat(),
            "ends_at": (NOW + timedelta(days=2)).isoformat(),
        },
    )
    assert created.status == 201
    competition_id = created.body["id"]
    paths = [
        f"/api/v1/leagues/{league_id}/competitions",
        f"/api/v1/leagues/{league_id}/competitions/{competition_id}",
        f"/api/v1/leagues/{league_id}/competitions/{competition_id}/start",
    ]
    for path in paths:
        method = "POST" if path.endswith("/start") else "GET"
        hidden = api.handle(method, path, context["outsider_token"])
        assert hidden.status == 404
        assert hidden.body == {"error": "not_found"}

    assert api.handle(
        "GET", f"/api/v1/leagues/wrong/competitions/{competition_id}",
        context["member_token"],
    ).status == 404

    other_league = context["leagues"].create(
        context["outsider"].id, "Otra", NOW,
    )
    other_competition = context["competitions"].create(
        context["outsider"].id, other_league.id, "Ajena",
        NOW + timedelta(days=1), NOW + timedelta(days=2), NOW,
    )
    assert api.handle(
        "POST",
        f"/api/v1/leagues/{league_id}/competitions/{other_competition.id}/start",
        context["member_token"],
    ).status == 404


def test_member_can_read_but_cannot_create_or_start(context):
    api = context["api"]
    league_id = context["league"].id
    payload = {
        "name": "No permitida",
        "starts_at": (NOW + timedelta(days=1)).isoformat(),
        "ends_at": (NOW + timedelta(days=2)).isoformat(),
    }
    assert api.handle(
        "POST", f"/api/v1/leagues/{league_id}/competitions",
        context["member_token"], payload,
    ).status == 403
    assert api.handle(
        "GET", f"/api/v1/leagues/{league_id}/competitions",
        context["member_token"],
    ).body == []
