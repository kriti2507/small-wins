import time
from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

import pytest
from mcp.server.auth.provider import AuthorizationParams, RegistrationError
from mcp.shared.auth import OAuthClientInformationFull

from config import Config
from oauth import SCOPE, SmallWinsOAuthProvider, redirect_uri_allowed

pytestmark = pytest.mark.anyio

CONFIG = Config("https://sw.example.com", "https://sw.example.com", "tok-secret", "svc", "hash")
REDIRECT = "https://claude.ai/api/mcp/auth_callback"


@pytest.fixture
def provider():
    return SmallWinsOAuthProvider(CONFIG)


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
    back = urlsplit(provider.approve(pending))
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
