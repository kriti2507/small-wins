"""Stateless OAuth provider for the MCP SDK.

Nothing is stored: every client id, pending login, authorization code and
token is a payload signed with Config.token_secret, so rotating that secret
invalidates all of them at once. The SDK handlers do the protocol checks
(PKCE, redirect_uri matching, expiry, client secrets); this class only mints
and reads the signed values.
"""
import hashlib
import hmac
import secrets
from urllib.parse import urlencode, urlsplit

from itsdangerous import BadData, URLSafeTimedSerializer
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    RefreshToken,
    RegistrationError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

SCOPE = "smallwins"
PENDING_TTL = 10 * 60
CODE_TTL = 5 * 60
ACCESS_TTL = 60 * 60
REFRESH_TTL = 30 * 24 * 60 * 60
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
# Schemes a browser would run or load instead of handing to an app, and
# "app" schemes that just open a web address in a browser.
BLOCKED_SCHEMES = {
    "javascript", "data", "file", "vbscript", "about", "blob", "ftp", "ws", "wss",
    "intent", "x-safari-http", "x-safari-https", "microsoft-edge", "googlechrome", "googlechromes",
}


def redirect_uri_allowed(uri):
    """https anywhere; http only back to this machine; or a desktop app's own
    scheme (e.g. cursor://). The login page shows the destination either way."""
    parts = urlsplit(str(uri))
    scheme = parts.scheme.lower()
    if scheme == "https":
        return bool(parts.hostname)
    if scheme == "http":
        return parts.hostname in LOOPBACK_HOSTS
    return bool(scheme) and scheme not in BLOCKED_SCHEMES


class SmallWinsOAuthProvider:
    def __init__(self, config):
        self.config = config
        self._serializer = URLSafeTimedSerializer(config.token_secret)

    # --- signing helpers ---------------------------------------------------

    def _dumps(self, kind, payload):
        return self._serializer.dumps(payload, salt=kind)

    def _loads(self, kind, value, max_age=None):
        """(payload, issued_at) or (None, None) if tampered, expired or the wrong kind."""
        try:
            payload, issued = self._serializer.loads(value, salt=kind, max_age=max_age, return_timestamp=True)
        except BadData:
            return None, None
        return payload, issued.timestamp()

    def _client_secret_for(self, client_id):
        key = self.config.token_secret.encode()
        return hmac.new(key, f"client-secret:{client_id}".encode(), hashlib.sha256).hexdigest()

    # --- clients -----------------------------------------------------------

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        for uri in client_info.redirect_uris or []:
            if not redirect_uri_allowed(uri):
                raise RegistrationError("invalid_redirect_uri", f"Redirect URI not allowed: {uri}")
        # The SDK minted a random client_id and returns this same object as
        # the registration response, so rewriting it here hands the client a
        # self-describing id that get_client can decode later.
        metadata = client_info.model_dump(
            mode="json",
            exclude={"client_id", "client_secret", "client_id_issued_at", "client_secret_expires_at"},
            exclude_none=True,
        )
        client_info.client_id = self._dumps("client", metadata)
        if client_info.client_secret is not None:
            client_info.client_secret = self._client_secret_for(client_info.client_id)

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        metadata, _ = self._loads("client", client_id)
        if metadata is None:
            return None
        secret = None
        if metadata.get("token_endpoint_auth_method") != "none":
            secret = self._client_secret_for(client_id)
        return OAuthClientInformationFull(**metadata, client_id=client_id, client_secret=secret)

    # --- authorization -----------------------------------------------------

    async def authorize(self, client, params) -> str:
        pending = {
            "client_id": client.client_id,
            "client_name": client.client_name,
            "redirect_uri": str(params.redirect_uri),
            "explicit": params.redirect_uri_provided_explicitly,
            "code_challenge": params.code_challenge,
            "state": params.state,
            "scopes": params.scopes or [SCOPE],
            "resource": params.resource,
        }
        return f"{self.config.base_url}/oauth/login?{urlencode({'req': self._dumps('pending', pending)})}"

    def load_pending(self, req):
        pending, _ = self._loads("pending", req, max_age=PENDING_TTL)
        return pending

    def approve(self, pending):
        """URL to send the browser to once the admin has logged in."""
        code = self._dumps("code", {**pending, "nonce": secrets.token_urlsafe(16)})
        return construct_redirect_uri(pending["redirect_uri"], code=code, state=pending["state"])

    async def load_authorization_code(self, client, authorization_code: str) -> AuthorizationCode | None:
        data, issued = self._loads("code", authorization_code, max_age=CODE_TTL)
        if data is None:
            return None
        return AuthorizationCode(
            code=authorization_code,
            scopes=data["scopes"],
            expires_at=issued + CODE_TTL,
            client_id=data["client_id"],
            code_challenge=data["code_challenge"],
            redirect_uri=data["redirect_uri"],
            redirect_uri_provided_explicitly=data["explicit"],
            resource=data["resource"],
        )

    async def exchange_authorization_code(self, client, authorization_code) -> OAuthToken:
        return self._issue(client.client_id, authorization_code.scopes, authorization_code.resource)

    # --- tokens ------------------------------------------------------------

    def _issue(self, client_id, scopes, resource):
        claims = {"client_id": client_id, "scopes": scopes, "resource": resource}
        return OAuthToken(
            access_token=self._dumps("access", claims),
            expires_in=ACCESS_TTL,
            refresh_token=self._dumps("refresh", claims),
            scope=" ".join(scopes),
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        claims, issued = self._loads("access", token, max_age=ACCESS_TTL)
        if claims is None:
            return None
        return AccessToken(token=token, expires_at=int(issued + ACCESS_TTL), **claims)

    async def load_refresh_token(self, client, refresh_token: str) -> RefreshToken | None:
        claims, issued = self._loads("refresh", refresh_token, max_age=REFRESH_TTL)
        if claims is None:
            return None
        return RefreshToken(token=refresh_token, expires_at=int(issued + REFRESH_TTL), **claims)

    async def exchange_refresh_token(self, client, refresh_token, scopes) -> OAuthToken:
        return self._issue(client.client_id, scopes, refresh_token.resource)

    async def revoke_token(self, token) -> None:
        """Unreachable: revocation isn't advertised, since stateless tokens
        can't be revoked one at a time. Rotate MCP_TOKEN_SECRET instead."""
