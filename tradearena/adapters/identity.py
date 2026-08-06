"""Identidad local: enlaces HMAC y verificación de claims Google.

El adaptador Google recibe claims que ya han sido verificados criptográficamente
por la capa del proveedor. El contrato obliga a comprobar audiencia, emisor y
email verificado antes de crear una sesión propia.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from typing import Mapping

import jwt
from jwt import PyJWKClient

from tradearena.ports.identity import IdentityAssertion


class IdentityError(ValueError):
    pass


class LocalIdentityAdapter:
    GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

    def __init__(self, signing_key: bytes, google_client_id: str) -> None:
        if len(signing_key) < 32:
            raise ValueError("la clave de identidad debe tener al menos 32 bytes")
        self._key = signing_key
        self._google_client_id = google_client_id
        self._used_nonces: set[str] = set()

    @staticmethod
    def _b64(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

    @staticmethod
    def _unb64(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    def begin_email_login(self, email: str, expires_at: datetime) -> str:
        if expires_at.tzinfo is None:
            raise ValueError("expires_at necesita zona horaria")
        payload = {
            "email": email.strip().lower(),
            "exp": int(expires_at.timestamp()),
            "nonce": secrets.token_urlsafe(24),
        }
        encoded = self._b64(json.dumps(payload, sort_keys=True).encode())
        signature = self._b64(hmac.new(self._key, encoded.encode(), hashlib.sha256).digest())
        return f"{encoded}.{signature}"

    def verify_email_token(self, token: str, now: datetime) -> IdentityAssertion:
        try:
            encoded, supplied_signature = token.split(".", 1)
            expected = self._b64(hmac.new(
                self._key, encoded.encode(), hashlib.sha256
            ).digest())
            if not hmac.compare_digest(expected, supplied_signature):
                raise IdentityError("firma inválida")
            payload = json.loads(self._unb64(encoded))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise IdentityError("token inválido") from exc
        if now.tzinfo is None:
            raise ValueError("now necesita zona horaria")
        if int(now.timestamp()) >= int(payload["exp"]):
            raise IdentityError("token caducado")
        nonce = str(payload["nonce"])
        if nonce in self._used_nonces:
            raise IdentityError("token ya utilizado")
        self._used_nonces.add(nonce)
        email = str(payload["email"])
        return IdentityAssertion("email", email, email, True)

    def verify_google_claims(self, claims: Mapping[str, object]) -> IdentityAssertion:
        if claims.get("iss") not in self.GOOGLE_ISSUERS:
            raise IdentityError("emisor Google inválido")
        if claims.get("aud") != self._google_client_id:
            raise IdentityError("audiencia Google inválida")
        verified = claims.get("email_verified") in (True, "true")
        if not verified or not claims.get("email") or not claims.get("sub"):
            raise IdentityError("identidad Google no verificada")
        return IdentityAssertion(
            "google", str(claims["sub"]), str(claims["email"]).lower(), True
        )


UTC = timezone.utc


class Auth0IdentityAdapter:
    """Valida ID tokens OIDC contra las claves públicas del tenant Auth0."""

    def __init__(self, domain: str, client_id: str, jwks_client=None) -> None:
        clean_domain = domain.removeprefix("https://").rstrip("/")
        if not clean_domain or not client_id:
            raise ValueError("AUTH0_DOMAIN y AUTH0_CLIENT_ID son obligatorios")
        self.issuer = f"https://{clean_domain}/"
        self.client_id = client_id
        self._jwks = jwks_client or PyJWKClient(f"{self.issuer}.well-known/jwks.json")

    def verify_id_token(self, token: str, nonce: str) -> IdentityAssertion:
        try:
            signing_key = self._jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "email"]},
            )
        except jwt.PyJWTError as exc:
            raise IdentityError("ID token de Auth0 inválido") from exc
        if not nonce or not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
            raise IdentityError("nonce de Auth0 inválido")
        if claims.get("email_verified") not in (True, "true"):
            raise IdentityError("el email de Auth0 debe estar verificado")
        return IdentityAssertion(
            "auth0", str(claims["sub"]), str(claims["email"]).lower(), True
        )
