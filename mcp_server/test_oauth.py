import time
from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from mcp.server.auth.provider import AuthorizationParams, RegistrationError, TokenError
from mcp.shared.auth import OAuthClientInformationFull

from config import Config
from oauth import SCOPE, SmallWinsOAuthProvider, redirect_uri_allowed

pytestmark = pytest.mark.anyio

CONFIG = Config("https://sw.example.com", "https://sw.example.com", "tok-secret")
REDIRECT = "https://claude.ai/api/mcp/auth_callback"
CRED = "swg_7." + "s" * 43


class FakeGrants:
    """Flask's grant endpoints: redeem once, then 409; self 200 unless revoked."""
    def __init__(self):
        self.redeemed = 0
        self.revoked = False
        self.down = False
        self.paths = []

    def __call__(self, request):
        if self.down:
            raise httpx.ConnectError("down")
        self.paths.append(request.url.path)
        assert request.headers["authorization"] == f"Bearer {CRED}"
        if request.url.path == "/api/mcp/grants/redeem":
            self.redeemed += 1
            return httpx.Response(200 if self.redeemed == 1 else 409, json={})
        if request.url.path == "/api/mcp/grants/self":
            return httpx.Response(401 if self.revoked else 200, json={"id": 7})
        return httpx.Response(404, json={})


@pytest.fixture
def grants():
    return FakeGrants()


@pytest.fixture
def provider(grants):
    return SmallWinsOAuthProvider(CONFIG, transport=httpx.MockTransport(grants))


def rotated_provider():
    return SmallWinsOAuthProvider(replace(CONFIG, token_secret="rotated"))


def new_client(redirect=REDIRECT, auth_method="client_secret_post"):
    """What the SDK's /register handler passes in: a random id and secret."""
    return OAuthClientInformationFull(
        client_id="sdk-random-id",
        client_secret="sdk-random-secret" if auth_method != "none" else None,
        redirect_uris=[redirect],
        client_name="Claude",
        token_endpoint_auth_method=auth_method,
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        scope=SCOPE,
    )


async def registered(provider, **kwargs):
    info = new_client(**kwargs)
    await provider.register_client(info)
    return info


@pytest.mark.parametrize("uri,allowed", [
    ("https://claude.ai/api/mcp/auth_callback", True),
    ("https://chatgpt.com/connector_platform_oauth_redirect", True),
    ("http://localhost:6274/oauth/callback", True),
    ("http://127.0.0.1:33418/", True),
    ("http://[::1]:8080/cb", True),
    ("cursor://anysphere.cursor-mcp/oauth/callback", True),
    # App schemes that just open a web page in a browser.
    ("intent://evil.example.com/cb#Intent;scheme=https;end", False),
    ("x-safari-https://evil.example.com/cb", False),
    ("microsoft-edge:https://evil.example.com/cb", False),
    ("googlechromes://evil.example.com/cb", False),
    ("http://evil.example.com/cb", False),
    ("javascript:alert(1)", False),
    ("data:text/html,hi", False),
    ("file:///etc/passwd", False),
    ("https:///no-host", False),
])
def test_redirect_uri_allowed(uri, allowed):
    assert redirect_uri_allowed(uri) is allowed


async def test_register_replaces_sdk_id_with_a_decodable_one(provider):
    info = await registered(provider)
    assert info.client_id != "sdk-random-id"
    assert info.client_secret != "sdk-random-secret"
    client = await provider.get_client(info.client_id)
    assert client.client_secret == info.client_secret
    assert [str(u) for u in client.redirect_uris] == [REDIRECT]
    assert client.client_name == "Claude"
    assert client.scope == SCOPE


async def test_public_clients_get_no_secret(provider):
    info = await registered(provider, auth_method="none")
    assert info.client_secret is None
    assert (await provider.get_client(info.client_id)).client_secret is None


async def test_register_rejects_disallowed_redirects(provider):
    with pytest.raises(RegistrationError) as err:
        await provider.register_client(new_client(redirect="http://evil.example.com/cb"))
    assert err.value.error == "invalid_redirect_uri"


async def test_tampered_or_foreign_client_ids_are_unknown(provider):
    info = await registered(provider)
    assert await provider.get_client(info.client_id + "x") is None
    assert await provider.get_client("not-a-client") is None
    assert await rotated_provider().get_client(info.client_id) is None


def auth_params(state="xyz", scopes=None):
    return AuthorizationParams(
        state=state,
        scopes=scopes,
        code_challenge="challenge",
        redirect_uri=REDIRECT,
        redirect_uri_provided_explicitly=True,
        resource="https://sw.example.com/mcp",
    )


async def login_and_get_code(provider, client, state="xyz"):
    login_url = await provider.authorize(client, auth_params(state))
    assert login_url.startswith("https://sw.example.com/oauth/login?req=")
    pending = provider.load_pending(parse_qs(urlsplit(login_url).query)["req"][0])
    back = urlsplit(provider.approve(pending, CRED))
    assert f"{back.scheme}://{back.netloc}{back.path}" == REDIRECT
    query = parse_qs(back.query)
    assert query["state"] == [state]
    return query["code"][0]


async def test_authorization_code_round_trip(provider):
    client = await provider.get_client((await registered(provider)).client_id)
    code = await login_and_get_code(provider, client)
    loaded = await provider.load_authorization_code(client, code)
    assert loaded.client_id == client.client_id
    assert loaded.code_challenge == "challenge"
    assert str(loaded.redirect_uri) == REDIRECT
    assert loaded.scopes == [SCOPE]  # none requested -> the one scope
    assert loaded.resource == "https://sw.example.com/mcp"
    assert loaded.expires_at > time.time()


async def test_each_code_is_unique(provider):
    client = await provider.get_client((await registered(provider)).client_id)
    assert await login_and_get_code(provider, client) != await login_and_get_code(provider, client)


async def test_tokens_round_trip_and_keep_their_kind(provider):
    client = await provider.get_client((await registered(provider)).client_id)
    code = await provider.load_authorization_code(client, await login_and_get_code(provider, client))
    tokens = await provider.exchange_authorization_code(client, code)
    assert tokens.expires_in == 3600 and tokens.scope == SCOPE

    access = await provider.load_access_token(tokens.access_token)
    assert access.client_id == client.client_id and access.scopes == [SCOPE]
    refresh = await provider.load_refresh_token(client, tokens.refresh_token)
    assert refresh.client_id == client.client_id

    # A refresh token is not an access token, nor a code, and vice versa.
    assert await provider.load_access_token(tokens.refresh_token) is None
    assert await provider.load_refresh_token(client, tokens.access_token) is None
    assert await provider.load_authorization_code(client, tokens.access_token) is None

    renewed = await provider.exchange_refresh_token(client, refresh, [SCOPE])
    assert (await provider.load_access_token(renewed.access_token)).client_id == client.client_id


async def test_expired_tokens_are_rejected(provider, monkeypatch):
    client = await provider.get_client((await registered(provider)).client_id)
    code = await provider.load_authorization_code(client, await login_and_get_code(provider, client))
    tokens = await provider.exchange_authorization_code(client, code)
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 3601)
    assert await provider.load_access_token(tokens.access_token) is None
    assert await provider.load_refresh_token(client, tokens.refresh_token) is not None
    monkeypatch.setattr(time, "time", lambda: real_time() + 31 * 24 * 3600)
    assert await provider.load_refresh_token(client, tokens.refresh_token) is None


async def test_rotating_the_secret_invalidates_tokens(provider):
    client = await provider.get_client((await registered(provider)).client_id)
    code = await provider.load_authorization_code(client, await login_and_get_code(provider, client))
    tokens = await provider.exchange_authorization_code(client, code)
    assert await rotated_provider().load_access_token(tokens.access_token) is None


def test_pending_requests_expire(provider, monkeypatch):
    req = provider._dumps("pending", {"x": 1})
    assert provider.load_pending(req) == {"x": 1}
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 601)
    assert provider.load_pending(req) is None
    assert provider.load_pending("garbage") is None


async def tokens_for(provider, client):
    code = await provider.load_authorization_code(client, await login_and_get_code(provider, client))
    return await provider.exchange_authorization_code(client, code)


async def test_the_grant_rides_along_from_code_to_tokens_and_refresh(provider, grants):
    client = await provider.get_client((await registered(provider)).client_id)
    code = await provider.load_authorization_code(client, await login_and_get_code(provider, client))
    assert code.grant == CRED

    tokens = await provider.exchange_authorization_code(client, code)
    assert grants.paths == ["/api/mcp/grants/redeem"]
    assert (await provider.load_access_token(tokens.access_token)).grant == CRED
    refresh = await provider.load_refresh_token(client, tokens.refresh_token)
    assert refresh.grant == CRED
    assert grants.paths[-1] == "/api/mcp/grants/self"

    renewed = await provider.exchange_refresh_token(client, refresh, [SCOPE])
    assert (await provider.load_access_token(renewed.access_token)).grant == CRED


async def test_a_replayed_code_gets_no_tokens(provider):
    client = await provider.get_client((await registered(provider)).client_id)
    code = await provider.load_authorization_code(client, await login_and_get_code(provider, client))
    await provider.exchange_authorization_code(client, code)
    with pytest.raises(TokenError) as err:
        await provider.exchange_authorization_code(client, code)
    assert err.value.error == "invalid_grant"


async def test_no_tokens_when_flask_cant_redeem(provider, grants):
    client = await provider.get_client((await registered(provider)).client_id)
    code = await provider.load_authorization_code(client, await login_and_get_code(provider, client))
    grants.down = True
    with pytest.raises(TokenError):
        await provider.exchange_authorization_code(client, code)


async def test_refresh_is_refused_for_a_dead_grant_or_when_flask_is_down(provider, grants):
    client = await provider.get_client((await registered(provider)).client_id)
    tokens = await tokens_for(provider, client)
    grants.revoked = True
    assert await provider.load_refresh_token(client, tokens.refresh_token) is None
    grants.revoked, grants.down = False, True
    assert await provider.load_refresh_token(client, tokens.refresh_token) is None


def grantless(kind, provider, client_id="sdk-random-id", **extra):
    """A token or code without a grant, e.g. one minted before grants existed."""
    return provider._dumps(kind, {"client_id": client_id, "scopes": [SCOPE],
                                  "resource": "https://sw.example.com/mcp", **extra})


@pytest.mark.parametrize("extra", [{}, {"subject": "7"}, {"grant": ""}])
async def test_tokens_and_codes_without_a_grant_are_rejected(provider, extra):
    client = await provider.get_client((await registered(provider)).client_id)
    assert await provider.load_access_token(grantless("access", provider, **extra)) is None
    assert await provider.load_refresh_token(client, grantless("refresh", provider, client.client_id, **extra)) is None
    code = provider._dumps("code", {
        "client_id": client.client_id, "client_name": client.client_name,
        "redirect_uri": REDIRECT, "explicit": True, "code_challenge": "challenge",
        "state": "xyz", "scopes": [SCOPE], "resource": "https://sw.example.com/mcp", **extra,
    })
    assert await provider.load_authorization_code(client, code) is None


# --- the grant is encrypted, not just signed -----------------------------------

def unsigned_payload(provider, value):
    """What anyone holding a code or token can read without the secret."""
    _, payload = provider._serializer.loads_unsafe(value)
    return payload


async def test_codes_and_tokens_dont_reveal_the_grant(provider):
    client = await provider.get_client((await registered(provider)).client_id)
    raw_code = await login_and_get_code(provider, client)
    tokens = await provider.exchange_authorization_code(
        client, await provider.load_authorization_code(client, raw_code)
    )
    for value in (raw_code, tokens.access_token, tokens.refresh_token):
        payload = unsigned_payload(provider, value)
        assert payload["grant"]
        assert "swg_" not in repr(payload)


def code_with_grant(provider, client, grant):
    return provider._dumps("code", {
        "client_id": client.client_id, "client_name": client.client_name,
        "redirect_uri": REDIRECT, "explicit": True, "code_challenge": "challenge",
        "state": "xyz", "scopes": [SCOPE], "resource": "https://sw.example.com/mcp", "grant": grant,
    })


@pytest.mark.parametrize("grant", [CRED, "not-sealed", 7, ["x"]])
async def test_a_signed_but_unsealed_grant_is_rejected(provider, grant):
    client = await provider.get_client((await registered(provider)).client_id)
    assert await provider.load_access_token(grantless("access", provider, grant=grant)) is None
    assert await provider.load_refresh_token(
        client, grantless("refresh", provider, client.client_id, grant=grant)
    ) is None
    assert await provider.load_authorization_code(client, code_with_grant(provider, client, grant)) is None


async def test_a_grant_sealed_under_another_secret_does_not_open(provider):
    client = await provider.get_client((await registered(provider)).client_id)
    other = rotated_provider()
    sealed = other._seal(CRED)
    assert provider._open(sealed) is None
    assert other._open(sealed) == CRED
    assert await provider.load_access_token(grantless("access", provider, grant=sealed)) is None
    assert await provider.load_refresh_token(
        client, grantless("refresh", provider, client.client_id, grant=sealed)
    ) is None
    assert await provider.load_authorization_code(client, code_with_grant(provider, client, sealed)) is None


async def test_rotating_the_secret_invalidates_codes_and_refresh_tokens(provider):
    client = await provider.get_client((await registered(provider)).client_id)
    raw_code = await login_and_get_code(provider, client)
    tokens = await tokens_for(provider, client)
    rotated = rotated_provider()
    assert await rotated.load_authorization_code(client, raw_code) is None
    assert await rotated.load_refresh_token(client, tokens.refresh_token) is None
