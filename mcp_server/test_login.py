import re
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from config import Config
from grant_api import GrantError
from login import SignInCheckFailed, make_login_handlers, signed_in_user
from oauth import SmallWinsOAuthProvider

CONFIG = Config("https://sw.example.com", "https://sw.example.com", "tok-secret")
ME = {"id": 7, "email": "me@example.com", "name": "Me", "avatar_url": None}
CRED = "swg_7." + "s" * 43


@pytest.fixture
def provider():
    return SmallWinsOAuthProvider(CONFIG)


class Who:
    """What the fake Flask says about the browser's cookie."""
    def __init__(self):
        self.user = None
        self.fail = False
        self.cookies = []
        self.grants = []
        self.grant_fails = False


@pytest.fixture
def who():
    return Who()


@pytest.fixture
def client(provider, who):
    async def check_user(cookie):
        who.cookies.append(cookie)
        if who.fail:
            raise SignInCheckFailed()
        return who.user

    async def create_grant(cookie, client_name, redirect_host):
        who.grants.append((cookie, client_name, redirect_host))
        if who.grant_fails:
            raise GrantError()
        return CRED

    show, submit = make_login_handlers(provider, check_user, create_grant)
    app = Starlette(routes=[Route("/oauth/login", show, methods=["GET"]), Route("/oauth/login", submit, methods=["POST"])])
    return TestClient(app, base_url="https://sw.example.com", follow_redirects=False)


def pending_req(provider, redirect="https://claude.ai/api/mcp/auth_callback", name="Claude"):
    return provider._dumps("pending", {
        "client_id": "cid", "client_name": name, "redirect_uri": redirect, "explicit": True,
        "code_challenge": "challenge", "state": "xyz", "scopes": ["smallwins"], "resource": None,
    })


# --- page basics (unchanged behaviour) ---------------------------------------

def test_page_shows_where_you_will_be_sent(client, provider):
    res = client.get("/oauth/login", params={"req": pending_req(provider)})
    assert res.status_code == 200
    assert "<strong>claude.ai</strong>" in res.text
    assert "It calls itself “Claude”" in res.text
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["cache-control"] == "no-store"


def test_app_schemes_are_named_as_apps(client, provider):
    res = client.get("/oauth/login", params={"req": pending_req(provider, redirect="cursor://x/oauth/callback")})
    assert "<strong>cursor://x/oauth/callback</strong>" in res.text


def test_client_name_is_escaped(client, provider):
    res = client.get("/oauth/login", params={"req": pending_req(provider, name="<script>x</script>")})
    assert "<script>x" not in res.text
    assert "&lt;script&gt;" in res.text


def test_bad_or_missing_request_is_rejected(client):
    assert client.get("/oauth/login", params={"req": "garbage"}).status_code == 400
    assert client.get("/oauth/login").status_code == 400
    assert client.post("/oauth/login", data={"req": "garbage"}).status_code == 400


# --- signed out ----------------------------------------------------------------

def test_signed_out_page_offers_google_and_comes_back_here(client, provider):
    req = pending_req(provider)
    res = client.get("/oauth/login", params={"req": req})
    href = re.search(r'href="([^"]+)">Continue with Google', res.text).group(1).replace("&amp;", "&")
    parts = urlsplit(href)
    assert parts.path == "/api/auth/google"
    back = parse_qs(parts.query)["next"][0]
    assert back.startswith("/oauth/login?")
    assert parse_qs(urlsplit(back).query)["req"] == [req]
    assert "Allow</button>" not in res.text


def test_post_while_signed_out_is_refused(client, provider):
    res = client.post("/oauth/login", data={"req": pending_req(provider)})
    assert res.status_code == 401
    assert "Sign in with Google first." in res.text
    assert "location" not in res.headers


# --- signed in -----------------------------------------------------------------

def test_signed_in_page_names_the_account_and_offers_allow(client, provider, who):
    who.user = {**ME, "email": "<b>me</b>@example.com"}
    res = client.get("/oauth/login", params={"req": pending_req(provider)})
    assert "Signed in as <strong>&lt;b&gt;me&lt;/b&gt;@example.com</strong>" in res.text
    assert "Allow</button>" in res.text
    assert "Continue with Google" not in res.text


def test_the_browser_cookie_is_what_gets_checked(client, provider, who):
    client.get("/oauth/login", params={"req": pending_req(provider)}, headers={"cookie": "session=abc"})
    assert who.cookies == ["session=abc"]


def test_allow_creates_a_grant_and_redirects_back_with_it(client, provider, who):
    who.user = ME
    res = client.post("/oauth/login", data={"req": pending_req(provider)}, headers={"cookie": "session=abc"})
    assert res.status_code == 302
    assert who.grants == [("session=abc", "Claude", "claude.ai")]
    back = urlsplit(res.headers["location"])
    assert back.netloc == "claude.ai"
    query = parse_qs(back.query)
    assert query["state"] == ["xyz"]
    payload, _ = provider._loads("code", query["code"][0])
    assert payload["grant"] == CRED
    assert "subject" not in payload


def test_app_schemes_are_recorded_as_the_whole_uri(client, provider, who):
    who.user = ME
    client.post("/oauth/login", data={"req": pending_req(provider, redirect="cursor://x/oauth/callback")})
    assert who.grants[0][2] == "cursor://x/oauth/callback"


def test_a_failed_grant_shows_an_error_not_a_code(client, provider, who):
    who.user, who.grant_fails = ME, True
    res = client.post("/oauth/login", data={"req": pending_req(provider)})
    assert res.status_code == 502
    assert "Couldn't connect the app. Try again." in res.text
    assert "location" not in res.headers


def test_no_grant_without_a_signed_in_user(client, provider, who):
    client.post("/oauth/login", data={"req": pending_req(provider)})
    who.fail = True
    client.post("/oauth/login", data={"req": pending_req(provider)})
    assert who.grants == []


# --- Flask unreachable -----------------------------------------------------------

def test_failed_sign_in_check_never_approves(client, provider, who):
    who.fail = True
    req = pending_req(provider)
    for res in (client.get("/oauth/login", params={"req": req}),
                client.post("/oauth/login", data={"req": req})):
        assert res.status_code == 502
        assert "Couldn't check your sign-in. Try again." in res.text
        assert "location" not in res.headers


# --- signed_in_user --------------------------------------------------------------

pytestmark_anyio = pytest.mark.anyio


def flask_answering(status, body=None, seen=None):
    def handler(request):
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=body)
    return httpx.MockTransport(handler)


@pytestmark_anyio
async def test_signed_in_user_forwards_the_cookie_and_returns_the_user():
    seen = []
    user = await signed_in_user("https://sw.example.com", "session=abc",
                                transport=flask_answering(200, {"user": ME}, seen))
    assert user == ME
    assert seen[0].url.path == "/api/auth/me"
    assert seen[0].headers["cookie"] == "session=abc"


@pytestmark_anyio
async def test_signed_in_user_is_none_without_a_cookie_or_on_401():
    seen = []
    assert await signed_in_user("https://sw.example.com", None, transport=flask_answering(200, {}, seen)) is None
    assert seen == []  # no cookie, no call
    assert await signed_in_user("https://sw.example.com", "session=x", transport=flask_answering(401, {})) is None


@pytestmark_anyio
@pytest.mark.parametrize("status,body", [(500, {}), (200, {"nope": 1}), (302, {})])
async def test_signed_in_user_raises_on_anything_unexpected(status, body):
    with pytest.raises(SignInCheckFailed):
        await signed_in_user("https://sw.example.com", "session=x", transport=flask_answering(status, body))


@pytestmark_anyio
async def test_signed_in_user_raises_when_flask_is_unreachable():
    def boom(request):
        raise httpx.ConnectError("down")
    with pytest.raises(SignInCheckFailed):
        await signed_in_user("https://sw.example.com", "session=x", transport=httpx.MockTransport(boom))
