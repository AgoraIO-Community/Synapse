from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from fastapi import HTTPException, Request, WebSocket
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

from newbro.runtime import Settings


CLOUDFLARE_ACCESS_JWT_HEADER = "cf-access-jwt-assertion"
AUTHORIZATION_HEADER = "authorization"
CF_ACCESS_CLIENT_ID_HEADER = "cf-access-client-id"
CF_ACCESS_CLIENT_SECRET_HEADER = "cf-access-client-secret"


@dataclass(slots=True)
class AuthenticatedPrincipal:
    subject: str
    auth_type: str
    email: str | None = None


@dataclass(slots=True)
class AuthState:
    enabled: bool
    allow_unauthenticated_websockets: bool


@dataclass(slots=True)
class CloudflareAccessVerifier:
    team_domain: str
    audience: str
    _jwk_client: PyJWKClient | None = None

    def __post_init__(self) -> None:
        normalized_domain = self.team_domain.strip().lower().rstrip("/")
        if normalized_domain.startswith("https://"):
            normalized_domain = normalized_domain.removeprefix("https://")
        elif normalized_domain.startswith("http://"):
            normalized_domain = normalized_domain.removeprefix("http://")
        self.team_domain = normalized_domain

    @property
    def certs_url(self) -> str:
        return f"https://{self.team_domain}/cdn-cgi/access/certs"

    def verify(self, token: str) -> AuthenticatedPrincipal:
        if self._jwk_client is None:
            self._jwk_client = PyJWKClient(self.certs_url)
        signing_key = self._jwk_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=self.audience,
        )
        subject = _coerce_claim(payload.get("sub")) or _coerce_claim(payload.get("email"))
        if not subject:
            raise InvalidTokenError("Missing subject.")
        return AuthenticatedPrincipal(
            subject=subject,
            email=_coerce_claim(payload.get("email")),
            auth_type="cloudflare-access",
        )


def build_auth_state(settings: Settings) -> AuthState:
    return AuthState(
        enabled=settings.api_auth_required,
        allow_unauthenticated_websockets=settings.allow_unauthenticated_session_websockets,
    )


def install_auth_state(app, settings: Settings) -> None:
    verifier: CloudflareAccessVerifier | None = None
    if settings.cloudflare_access_team_domain and settings.cloudflare_access_audience:
        verifier = CloudflareAccessVerifier(
            team_domain=settings.cloudflare_access_team_domain,
            audience=settings.cloudflare_access_audience,
        )
    app.state.auth_state = build_auth_state(settings)
    app.state.cloudflare_access_verifier = verifier


def require_http_api_auth(request: Request) -> AuthenticatedPrincipal | None:
    return _require_scope_auth(
        carrier=request,
        auth_state=getattr(request.app.state, "auth_state", AuthState(False, False)),
        verifier=getattr(request.app.state, "cloudflare_access_verifier", None),
        expected_api_token=request.app.state.runtime_container.settings.api_bearer_token,
        access_client_id=request.app.state.runtime_container.settings.cloudflare_access_service_client_id,
        access_client_secret=request.app.state.runtime_container.settings.cloudflare_access_service_client_secret,
        unauthorized_status=401,
        missing_error="API authentication required.",
        invalid_error="Invalid API credentials.",
    )


def require_websocket_api_auth(
    websocket: WebSocket,
    *,
    allow_unauthenticated: bool = False,
) -> AuthenticatedPrincipal | None:
    auth_state = getattr(websocket.app.state, "auth_state", AuthState(False, False))
    if allow_unauthenticated and auth_state.allow_unauthenticated_websockets:
        return None
    return _require_scope_auth(
        carrier=websocket,
        auth_state=auth_state,
        verifier=getattr(websocket.app.state, "cloudflare_access_verifier", None),
        expected_api_token=websocket.app.state.runtime_container.settings.api_bearer_token,
        access_client_id=websocket.app.state.runtime_container.settings.cloudflare_access_service_client_id,
        access_client_secret=websocket.app.state.runtime_container.settings.cloudflare_access_service_client_secret,
        unauthorized_status=4401,
        missing_error="WebSocket authentication required.",
        invalid_error="Invalid WebSocket credentials.",
    )


def require_executor_control_auth(websocket: WebSocket) -> AuthenticatedPrincipal | None:
    settings = websocket.app.state.runtime_container.settings
    if not settings.executor_control_ws_auth_enabled:
        return None
    return require_websocket_api_auth(websocket)


def build_browser_auth_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Headers": ", ".join(
            [
                "Authorization",
                "Content-Type",
                "Cf-Access-Jwt-Assertion",
                "CF-Access-Client-Id",
                "CF-Access-Client-Secret",
            ]
        )
    }


def _require_scope_auth(
    *,
    carrier: Request | WebSocket,
    auth_state: AuthState,
    verifier: CloudflareAccessVerifier | None,
    expected_api_token: str | None,
    access_client_id: str | None,
    access_client_secret: str | None,
    unauthorized_status: int,
    missing_error: str,
    invalid_error: str,
) -> AuthenticatedPrincipal | None:
    if not auth_state.enabled:
        return None

    service_principal = _authenticate_service_token(
        carrier,
        expected_client_id=access_client_id,
        expected_client_secret=access_client_secret,
    )
    if service_principal is not None:
        return service_principal

    access_token = _header_value(carrier, CLOUDFLARE_ACCESS_JWT_HEADER)
    if access_token:
        if verifier is None:
            _raise_unauthorized(unauthorized_status, invalid_error)
        try:
            return verifier.verify(access_token)
        except (InvalidTokenError, httpx.HTTPError):
            _raise_unauthorized(unauthorized_status, invalid_error)

    bearer_token = _extract_bearer_token(_header_value(carrier, AUTHORIZATION_HEADER))
    if bearer_token:
        if expected_api_token and hmac.compare_digest(bearer_token, expected_api_token):
            return AuthenticatedPrincipal(subject="api-token", auth_type="bearer")
        _raise_unauthorized(unauthorized_status, invalid_error)

    _raise_unauthorized(unauthorized_status, missing_error)


def _authenticate_service_token(
    carrier: Request | WebSocket,
    *,
    expected_client_id: str | None,
    expected_client_secret: str | None,
) -> AuthenticatedPrincipal | None:
    if not expected_client_id or not expected_client_secret:
        return None
    client_id = _header_value(carrier, CF_ACCESS_CLIENT_ID_HEADER)
    client_secret = _header_value(carrier, CF_ACCESS_CLIENT_SECRET_HEADER)
    if not client_id and not client_secret:
        return None
    if not client_id or not client_secret:
        return _invalid_service_token()
    if not hmac.compare_digest(client_id, expected_client_id):
        return _invalid_service_token()
    if not hmac.compare_digest(client_secret, expected_client_secret):
        return _invalid_service_token()
    token_hash = hashlib.sha256(f"{client_id}:{client_secret}".encode("utf-8")).hexdigest()[:12]
    return AuthenticatedPrincipal(
        subject=f"service-token:{token_hash}",
        auth_type="cloudflare-service-token",
    )


def _invalid_service_token() -> None:
    raise HTTPException(status_code=401, detail="Invalid API credentials.")


def _header_value(carrier: Request | WebSocket, header_name: str) -> str | None:
    value = carrier.headers.get(header_name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _extract_bearer_token(raw_header: str | None) -> str | None:
    if raw_header is None:
        return None
    scheme, _, token = raw_header.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = token.strip()
    return token or None


def _coerce_claim(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _raise_unauthorized(status_code: int, detail: str) -> None:
    raise HTTPException(status_code=status_code, detail=detail)


def redact_auth_settings(settings: Settings) -> dict[str, Any]:
    return {
        "api_auth_required": settings.api_auth_required,
        "cloudflare_access_team_domain": settings.cloudflare_access_team_domain or None,
        "cloudflare_access_audience": _mask_value(settings.cloudflare_access_audience),
        "cloudflare_access_service_client_id": _mask_value(settings.cloudflare_access_service_client_id),
        "cloudflare_access_service_client_secret": _mask_value(
            settings.cloudflare_access_service_client_secret
        ),
        "api_bearer_token": _mask_value(settings.api_bearer_token),
    }


def _mask_value(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
    return f"configured:{digest}"


def encode_test_access_token(*, audience: str, subject: str, email: str | None = None) -> str:
    payload: dict[str, Any] = {"aud": audience, "sub": subject}
    if email:
        payload["email"] = email
    return jwt.encode(payload, "test-secret", algorithm="HS256")


class StaticCloudflareAccessVerifier(CloudflareAccessVerifier):
    def __init__(self, *, audience: str, secret: str = "test-secret") -> None:
        super().__init__(team_domain="test.cloudflareaccess.com", audience=audience)
        self._secret = secret

    def verify(self, token: str) -> AuthenticatedPrincipal:
        payload = jwt.decode(token, self._secret, algorithms=["HS256"], audience=self.audience)
        subject = _coerce_claim(payload.get("sub")) or _coerce_claim(payload.get("email"))
        if not subject:
            raise InvalidTokenError("Missing subject.")
        return AuthenticatedPrincipal(
            subject=subject,
            email=_coerce_claim(payload.get("email")),
            auth_type="cloudflare-access",
        )
