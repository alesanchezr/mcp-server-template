from __future__ import annotations

import os
import secrets
import time
from dataclasses import dataclass

from fastmcp.server.auth.auth import ClientRegistrationOptions
from fastmcp.server.auth.providers.in_memory import (
    DEFAULT_AUTH_CODE_EXPIRY_SECONDS,
    InMemoryOAuthProvider,
)
from mcp.server.auth.provider import (
    AuthorizationParams,
    AuthorizeError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Route
from starlette.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")

PENDING_AUTH_TTL_SECONDS = 15 * 60


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
            required_scopes=["blog:write"],
        )
        self._pending_auth: dict[str, PendingAuth] = {}

    def _get_resource_url(self, path: str | None = None) -> AnyHttpUrl | None:
        """Advertise resource URL without trailing slash for client compatibility."""
        url = super()._get_resource_url(path)
        if url is None:
            return None
        return AnyHttpUrl(str(url).rstrip("/"))

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
        """Resolve scopes for the auth code, defaulting to client/default scopes.

        Claude.ai often omits scope on /authorize; without a fallback the issued
        token has no scopes and MCP requests fail with 403 insufficient_scope.
        """
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
        from mcp.server.auth.provider import AuthorizationCode

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


def _get_public_url() -> str:
    if public_url := os.environ.get("PUBLIC_URL"):
        return public_url.rstrip("/")
    if domain := os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
        return f"https://{domain}".rstrip("/")
    return "http://localhost:8000"


def create_oauth_provider() -> EducationalOAuthProvider:
    return EducationalOAuthProvider(base_url=f"{_get_public_url()}/mcp")
