from __future__ import annotations

import logging
import os
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import jwt
from fastmcp.server.auth.auth import ClientRegistrationOptions
from fastmcp.server.auth.providers.in_memory import (
    DEFAULT_ACCESS_TOKEN_EXPIRY_SECONDS,
    InMemoryOAuthProvider,
)
from mcp.server.auth.provider import (
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Route
from starlette.templating import Jinja2Templates

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="app/templates")

PENDING_AUTH_TTL_SECONDS = 15 * 60
DEFAULT_AUTH_CODE_EXPIRY_SECONDS = 5 * 60


def _oauth_secret() -> str:
    return os.environ.get("OAUTH_SECRET", "dev-only-change-me-on-railway")


def _normalize_resource_url(url: str) -> str:
    parsed = urlparse(str(url))
    path = parsed.path.rstrip("/") or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"


@dataclass
class PendingAuth:
    client_id: str
    params: AuthorizationParams
    created_at: float


class EducationalOAuthProvider(InMemoryOAuthProvider):
    """Open educational OAuth provider with a simple login button."""

    def __init__(self, base_url: str):
        super().__init__(
            base_url=base_url,
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                default_scopes=["blog:write"],
                valid_scopes=["blog:write"],
            ),
            required_scopes=[],
        )
        self._pending_auth: dict[str, PendingAuth] = {}

    def _get_resource_url(self, path: str | None = None) -> AnyHttpUrl | None:
        """Advertise resource URL without trailing slash for client compatibility."""
        url = super()._get_resource_url(path)
        if url is None:
            return None
        return AnyHttpUrl(str(url).rstrip("/"))

    def _expected_resource_url(self) -> str:
        resource = self._get_resource_url("/")
        if resource is None:
            return str(self.base_url).rstrip("/")
        return str(resource).rstrip("/")

    def _validate_resource(self, params: AuthorizationParams) -> None:
        client_resource = getattr(params, "resource", None)
        if not client_resource:
            return
        expected = _normalize_resource_url(self._expected_resource_url())
        received = _normalize_resource_url(str(client_resource))
        if received != expected:
            logger.warning("Resource mismatch: got %s expected %s", received, expected)
            raise AuthorizeError(
                error="invalid_target",
                error_description=(
                    f"Resource {client_resource} does not match this server ({expected})"
                ),
            )

    def _issue_jwt(self, client_id: str, scopes: list[str]) -> tuple[str, int]:
        expires_at = int(time.time()) + DEFAULT_ACCESS_TOKEN_EXPIRY_SECONDS
        token = jwt.encode(
            {
                "sub": client_id,
                "client_id": client_id,
                "scope": " ".join(scopes),
                "exp": expires_at,
            },
            _oauth_secret(),
            algorithm="HS256",
        )
        return token, expires_at

    async def authorize(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> str:
        if client.client_id not in self.clients:
            raise AuthorizeError(
                error="unauthorized_client",
                error_description=f"Client '{client.client_id}' not registered.",
            )

        self._validate_resource(params)

        txn_id = secrets.token_urlsafe(32)
        self._pending_auth[txn_id] = PendingAuth(
            client_id=client.client_id,
            params=params,
            created_at=time.time(),
        )
        return f"{str(self.base_url).rstrip('/')}/login?txn_id={txn_id}"

    def _resolve_scopes(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> list[str]:
        """Resolve scopes for the auth code, defaulting to client/default scopes."""
        requested = list(params.scopes) if params.scopes else []
        if client.scope:
            allowed = set(client.scope.split())
            if requested:
                return [s for s in requested if s in allowed]
            return list(allowed)

        if requested:
            return requested

        options = self.client_registration_options
        if options and options.default_scopes:
            return list(options.default_scopes)

        return []

    def _issue_authorization_code(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> str:
        scopes_list = self._resolve_scopes(client, params)

        if client.client_id is None:
            raise AuthorizeError(
                error="invalid_client", error_description="Client ID is required"
            )

        auth_code_value = f"auth_code_{secrets.token_hex(16)}"
        auth_code = AuthorizationCode(
            code=auth_code_value,
            client_id=client.client_id,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            scopes=scopes_list,
            expires_at=time.time() + DEFAULT_AUTH_CODE_EXPIRY_SECONDS,
            code_challenge=params.code_challenge,
        )
        self.auth_codes[auth_code_value] = auth_code

        return construct_redirect_uri(
            str(params.redirect_uri), code=auth_code_value, state=params.state
        )

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: AuthorizationCode,
    ) -> OAuthToken:
        if authorization_code.code not in self.auth_codes:
            raise TokenError(
                "invalid_grant", "Authorization code not found or already used."
            )
        del self.auth_codes[authorization_code.code]

        if client.client_id is None:
            raise TokenError("invalid_client", "Client ID is required")

        scopes = authorization_code.scopes
        access_token, _expires_at = self._issue_jwt(client.client_id, scopes)
        refresh_token_value = f"refresh_{secrets.token_hex(32)}"
        self.refresh_tokens[refresh_token_value] = RefreshToken(
            token=refresh_token_value,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=None,
        )

        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=DEFAULT_ACCESS_TOKEN_EXPIRY_SECONDS,
            refresh_token=refresh_token_value,
            scope=" ".join(scopes),
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        original_scopes = set(refresh_token.scopes)
        if not set(scopes).issubset(original_scopes):
            raise TokenError(
                "invalid_scope",
                "Requested scopes exceed those authorized by the refresh token.",
            )

        del self.refresh_tokens[refresh_token.token]

        if client.client_id is None:
            raise TokenError("invalid_client", "Client ID is required")

        access_token, _expires_at = self._issue_jwt(client.client_id, scopes)
        new_refresh = f"refresh_{secrets.token_hex(32)}"
        self.refresh_tokens[new_refresh] = RefreshToken(
            token=new_refresh,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=None,
        )

        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=DEFAULT_ACCESS_TOKEN_EXPIRY_SECONDS,
            refresh_token=new_refresh,
            scope=" ".join(scopes),
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        try:
            payload = jwt.decode(token, _oauth_secret(), algorithms=["HS256"])
        except jwt.PyJWTError:
            return None

        client_id = payload.get("client_id") or payload.get("sub")
        if not client_id:
            return None

        scope_str = payload.get("scope", "")
        scopes = scope_str.split() if scope_str else []
        expires_at = int(payload["exp"])
        from mcp.server.auth.provider import AccessToken

        return AccessToken(
            token=token,
            client_id=str(client_id),
            scopes=scopes,
            expires_at=expires_at,
        )

    def _get_pending(self, txn_id: str) -> PendingAuth | None:
        pending = self._pending_auth.get(txn_id)
        if pending is None:
            return None
        if pending.created_at + PENDING_AUTH_TTL_SECONDS < time.time():
            del self._pending_auth[txn_id]
            return None
        return pending

    async def _handle_login(self, request: Request):
        txn_id = request.query_params.get("txn_id") or (
            (await request.form()).get("txn_id") if request.method == "POST" else None
        )

        if not txn_id or not isinstance(txn_id, str):
            return HTMLResponse("Missing transaction ID", status_code=400)

        pending = self._get_pending(txn_id)
        if pending is None:
            return templates.TemplateResponse(
                request,
                "oauth_login.html",
                {"txn_id": txn_id, "error": "Session expired. Please try connecting again."},
                status_code=400,
            )

        if request.method == "GET":
            return templates.TemplateResponse(
                request, "oauth_login.html", {"txn_id": txn_id, "error": None}
            )

        client = await self.get_client(pending.client_id)
        if client is None:
            return templates.TemplateResponse(
                request,
                "oauth_login.html",
                {"txn_id": txn_id, "error": "Client not found."},
                status_code=400,
            )

        del self._pending_auth[txn_id]
        redirect_url = self._issue_authorization_code(client, pending.params)
        return RedirectResponse(url=redirect_url, status_code=302)

    def get_routes(self, mcp_path: str | None = None) -> list[Route]:
        routes = super().get_routes(mcp_path)
        routes.append(
            Route(
                "/login",
                endpoint=self._handle_login,
                methods=["GET", "POST"],
            )
        )
        return routes

    def get_well_known_routes(self, mcp_path: str | None = None) -> list[Route]:
        routes = super().get_well_known_routes(mcp_path)
        extra: list[Route] = []
        for route in routes:
            if route.path.endswith("/mcp"):
                extra.append(
                    Route(
                        f"{route.path}/",
                        endpoint=route.endpoint,
                        methods=route.methods,
                    )
                )
        return routes + extra


def _get_public_url() -> str:
    if public_url := os.environ.get("PUBLIC_URL"):
        return public_url.rstrip("/")
    if domain := os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
        return f"https://{domain}".rstrip("/")
    return "http://localhost:8000"


def create_oauth_provider() -> EducationalOAuthProvider:
    public_url = _get_public_url()
    logger.info("MCP OAuth public URL: %s/mcp", public_url)
    return EducationalOAuthProvider(base_url=f"{public_url}/mcp")
