from datetime import datetime, timedelta, timezone

import pytest
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from tradearena.adapters.identity import (
    Auth0IdentityAdapter, IdentityError, LocalIdentityAdapter,
)
from tradearena.adapters.memory import MemoryStore
from tradearena.application.models import User
from tradearena.application.services import (
    AccountService, AuthService, Forbidden, SessionService,
)

UTC = timezone.utc
NOW = datetime(2026, 8, 4, 12, tzinfo=UTC)


class StaticJwks:
    def __init__(self, key):
        self.key = key

    def get_signing_key_from_jwt(self, _token):
        return self


def adapter():
    return LocalIdentityAdapter(b"x" * 32, "google-client")


def test_magic_link_is_signed_expiring_and_single_use():
    identity = adapter()
    token = identity.begin_email_login("ANA@example.com", NOW + timedelta(minutes=10))
    assertion = identity.verify_email_token(token, NOW)
    assert assertion.email == "ana@example.com"
    with pytest.raises(IdentityError, match="utilizado"):
        identity.verify_email_token(token, NOW)


def test_magic_link_rejects_tampering_and_expiration():
    identity = adapter()
    token = identity.begin_email_login("ana@example.com", NOW)
    with pytest.raises(IdentityError, match="caducado"):
        identity.verify_email_token(token, NOW)
    with pytest.raises(IdentityError):
        identity.verify_email_token(token + "x", NOW - timedelta(seconds=1))


def test_google_requires_expected_issuer_audience_and_verified_email():
    identity = adapter()
    claims = {
        "iss": "https://accounts.google.com", "aud": "google-client",
        "sub": "google-1", "email": "ana@example.com", "email_verified": True,
    }
    assert identity.verify_google_claims(claims).subject == "google-1"
    with pytest.raises(IdentityError, match="audiencia"):
        identity.verify_google_claims({**claims, "aud": "attacker"})
    with pytest.raises(IdentityError, match="no verificada"):
        identity.verify_google_claims({**claims, "email_verified": False})


def test_auth_service_exchanges_verified_identity_for_revocable_session():
    store = MemoryStore()
    accounts = AccountService(store, lambda: "user-1")
    sessions = SessionService(store, lambda: "session-1", lambda: NOW)
    auth = AuthService(adapter(), accounts, sessions)
    link = auth.begin_email("ana@example.com", NOW)
    session = auth.finish_email(link, NOW)
    assert session == "session-1"
    assert sessions.authenticate(session) == "user-1"
    assert store.sessions.get("session-1") is None


def test_verified_email_and_google_identities_link_to_one_account():
    store = MemoryStore()
    ids = iter(["user-1", "should-not-be-used"])
    accounts = AccountService(store, lambda: next(ids))
    email_user = accounts.login(
        adapter().verify_email_token(
            adapter().begin_email_login("ana@example.com", NOW + timedelta(minutes=1)),
            NOW,
        ),
        NOW,
    )
    google_user = accounts.login(
        adapter().verify_google_claims({
            "iss": "accounts.google.com", "aud": "google-client", "sub": "g-1",
            "email": "ana@example.com", "email_verified": True,
        }),
        NOW,
    )
    assert google_user.id == email_user.id
    assert store.users.get_by_identity("email", "ana@example.com").id == email_user.id
    assert store.users.get_by_identity("google", "g-1").id == email_user.id


def test_application_session_expires_server_side():
    store = MemoryStore()
    with store.transaction() as uow:
        uow.users.add(User(
            "user-1", "ana@example.com", "email", "ana@example.com", NOW
        ))
    current = [NOW]
    sessions = SessionService(store, lambda: "session-1", lambda: current[0])
    token = sessions.issue("user-1")
    current[0] = NOW + timedelta(days=31)
    with pytest.raises(Forbidden):
        sessions.authenticate(token)


def test_auth0_adapter_validates_signature_issuer_audience_and_verified_email():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    identity = Auth0IdentityAdapter(
        "tenant.eu.auth0.com", "web-client", StaticJwks(private_key.public_key())
    )
    claims = {
        "iss": "https://tenant.eu.auth0.com/", "aud": "web-client",
        "sub": "auth0|user-1", "email": "ANA@example.com", "email_verified": True,
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
        "nonce": "expected-nonce-value",
    }
    token = jwt.encode(claims, private_key, algorithm="RS256")

    assertion = identity.verify_id_token(token, "expected-nonce-value")

    assert assertion.provider == "auth0"
    assert assertion.email == "ana@example.com"
    wrong_audience = jwt.encode({**claims, "aud": "attacker"}, private_key, algorithm="RS256")
    with pytest.raises(IdentityError, match="inválido"):
        identity.verify_id_token(wrong_audience, "expected-nonce-value")
    unverified = jwt.encode(
        {**claims, "email_verified": False}, private_key, algorithm="RS256"
    )
    with pytest.raises(IdentityError, match="verificado"):
        identity.verify_id_token(unverified, "expected-nonce-value")
    with pytest.raises(IdentityError, match="nonce"):
        identity.verify_id_token(token, "different-nonce-value")
