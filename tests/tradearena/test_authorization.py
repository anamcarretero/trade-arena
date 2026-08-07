from datetime import datetime, timedelta, timezone

import pytest

from tradearena.adapters.memory import MemoryStore
from tradearena.application.models import InvitationStatus
from tradearena.application.services import (
    AccountService, Forbidden, LeagueService, NotificationService, NotFound,
    PlanLimitExceeded, SessionService,
)
from tradearena.ports.identity import IdentityAssertion
from tradearena.presentation.api import Api

UTC = timezone.utc
NOW = datetime(2026, 8, 4, 12, tzinfo=UTC)


class Ids:
    def __init__(self):
        self.value = 0

    def __call__(self):
        self.value += 1
        return f"id-{self.value}"


@pytest.fixture
def app():
    store = MemoryStore()
    ids = Ids()
    accounts = AccountService(store, ids)
    leagues = LeagueService(store, ids)
    tokens = iter(["token-owner", "token-outsider", "token-member"])
    sessions = SessionService(store, lambda: next(tokens), lambda: NOW)

    def user(email):
        return accounts.login(IdentityAssertion("email", email, email, True), NOW)

    owner = user("owner@example.com")
    outsider = user("outsider@example.com")
    member = user("member@example.com")
    token_owner = sessions.issue(owner.id)
    token_outsider = sessions.issue(outsider.id)
    token_member = sessions.issue(member.id)
    api = Api(sessions, accounts, leagues, lambda: NOW)
    return store, accounts, leagues, api, owner, outsider, member, \
        token_owner, token_outsider, token_member


def test_direct_api_cannot_read_another_private_league(app):
    _, _, _, api, _, _, _, owner_token, outsider_token, _ = app
    created = api.handle("POST", "/api/v1/leagues", owner_token, {"name": "Privada"})
    league_id = created.body["id"]

    assert api.handle("GET", f"/api/v1/leagues/{league_id}", owner_token).status == 200
    hidden = api.handle("GET", f"/api/v1/leagues/{league_id}", outsider_token)
    assert hidden.status == 404
    assert hidden.body == {"error": "not_found"}


def test_direct_api_cannot_invite_or_remove_in_another_league(app):
    _, _, _, api, _, _, member, owner_token, outsider_token, _ = app
    league_id = api.handle(
        "POST", "/api/v1/leagues", owner_token, {"name": "Privada"}
    ).body["id"]
    assert api.handle(
        "POST", f"/api/v1/leagues/{league_id}/invitations", outsider_token,
        {"email": "member@example.com"},
    ).status == 404
    assert api.handle(
        "DELETE", f"/api/v1/leagues/{league_id}/members/{member.id}",
        outsider_token,
    ).status == 404


def test_invitation_is_bound_to_email_and_grants_membership(app):
    _, _, _, api, owner, _, member, owner_token, outsider_token, member_token = app
    league_id = api.handle(
        "POST", "/api/v1/leagues", owner_token, {"name": "Privada"}
    ).body["id"]
    invitation = api.handle(
        "POST", f"/api/v1/leagues/{league_id}/invitations", owner_token,
        {"email": "member@example.com"},
    )
    invitation_id = invitation.body["id"]
    assert invitation.body["expires_at"] == (NOW + timedelta(days=7)).isoformat()

    detail = api.handle("GET", f"/api/v1/leagues/{league_id}", owner_token)
    assert detail.body["actor_role"] == "owner"
    assert detail.body["members"][0]["user_id"] == owner.id
    assert detail.body["invitations"][0]["email"] == member.email
    assert api.handle("GET", "/api/v1/invitations", outsider_token).body == []
    assert api.handle("GET", "/api/v1/invitations", member_token).body[0]["id"] \
        == invitation_id

    assert api.handle(
        "POST", f"/api/v1/invitations/{invitation_id}", outsider_token
    ).status == 404
    assert api.handle(
        "POST", f"/api/v1/invitations/{invitation_id}", member_token
    ).status == 200
    member_detail = api.handle(
        "GET", f"/api/v1/leagues/{league_id}", member_token
    )
    assert member_detail.status == 200
    assert member_detail.body["actor_role"] == "member"
    assert member_detail.body["invitations"] == []


def test_revoked_and_expired_invitation_links_are_hidden(app):
    store, _, leagues, api, owner, _, member, owner_token, _, member_token = app
    first = leagues.create(owner.id, "Privada", NOW)
    revoked = leagues.invite(owner.id, first.id, member.email, NOW)
    assert api.handle(
        "DELETE", f"/api/v1/leagues/{first.id}/invitations/{revoked.id}",
        owner_token,
    ).status == 204
    assert api.handle(
        "POST", f"/api/v1/invitations/{revoked.id}", member_token
    ).status == 404

    replacement = leagues.invite(owner.id, first.id, member.email, NOW)
    with pytest.raises(NotFound):
        leagues.accept(member.id, replacement.id, NOW + timedelta(days=8))
    with store.transaction() as uow:
        assert uow.invitations.get(replacement.id).status is InvitationStatus.EXPIRED
    assert store.audit_events[-1].action == "invitation.expired"


def test_removed_member_loses_access_but_history_remains(app):
    store, _, leagues, api, owner, _, member, owner_token, _, member_token = app
    league = leagues.create(owner.id, "Privada", NOW)
    invitation = leagues.invite(owner.id, league.id, member.email, NOW)
    leagues.accept(member.id, invitation.id, NOW)

    removed = api.handle(
        "DELETE", f"/api/v1/leagues/{league.id}/members/{member.id}", owner_token
    )
    assert removed.status == 204
    assert api.handle(
        "GET", f"/api/v1/leagues/{league.id}", member_token
    ).status == 404
    with store.transaction() as uow:
        assert uow.memberships.get(league.id, member.id).removed_at == NOW
    assert store.audit_events[-1].action == "member.removed"


def test_free_limits_are_transactional_and_count_pending_invites(app):
    _, _, leagues, _, owner, _, _, _, _, _ = app
    league = leagues.create(owner.id, "Uno", NOW)
    leagues.invite(owner.id, league.id, "member@example.com", NOW)
    with pytest.raises(PlanLimitExceeded):
        leagues.invite(owner.id, league.id, "third@example.com", NOW)
    with pytest.raises(PlanLimitExceeded):
        leagues.create(owner.id, "Dos", NOW)


def test_member_cannot_invite_and_deleted_session_is_revoked(app):
    _, accounts, leagues, _, owner, _, member, _, _, member_token = app
    league = leagues.create(owner.id, "Privada", NOW)
    invitation = leagues.invite(owner.id, league.id, member.email, NOW)
    leagues.accept(member.id, invitation.id, NOW)
    with pytest.raises(Forbidden):
        leagues.invite(member.id, league.id, "x@example.com", NOW)
    with pytest.raises(Forbidden):
        leagues.remove_member(member.id, league.id, owner.id, NOW)
    accounts.delete(member.id, member.id, NOW, confirmed=True)
    # La frontera HTTP no admite reutilizar la sesión tras borrar la cuenta.
    with pytest.raises(Forbidden):
        SessionService(leagues.store).authenticate(member_token)


def test_export_is_self_only_and_age_policy_is_server_side(app):
    _, accounts, _, _, owner, outsider, _, _, _, _ = app
    with pytest.raises(Forbidden):
        accounts.export(owner.id, outsider.id)
    with pytest.raises(Exception, match="18 años"):
        accounts.set_profile(
            owner.id, "Owner", "es", NOW.date().replace(year=NOW.year - 17), NOW, NOW
        )


def test_notification_resource_of_another_user_is_hidden_with_404(app):
    store, _, _, _, owner, outsider, _, _, _, _ = app
    notifications = NotificationService(store, lambda: "notification-owner")
    created = notifications.create(owner.id, "private", {"message": "Owner"}, NOW)

    assert notifications.list_for(outsider.id) == []
    with pytest.raises(NotFound):
        notifications.mark_read(outsider.id, created.id, NOW)
    first = notifications.mark_read(owner.id, created.id, NOW)
    second = notifications.mark_read(owner.id, created.id, NOW + timedelta(hours=1))
    assert first["read_at"] == second["read_at"] == NOW
    assert [item.action for item in store.audit_events].count("notification.read") == 1
