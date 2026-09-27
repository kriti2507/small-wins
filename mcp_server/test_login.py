from urllib.parse import parse_qs, urlsplit

import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from werkzeug.security import generate_password_hash

import login
from config import Config
from login import make_login_handlers
from oauth import SmallWinsOAuthProvider

CONFIG = Config("https://sw.example.com", "https://sw.example.com", "tok-secret", "svc",
                generate_password_hash("pw", method="pbkdf2"))


@pytest.fixture
def provider():
    return SmallWinsOAuthProvider(CONFIG)


@pytest.fixture
def client(provider, monkeypatch):
    monkeypatch.setattr(login, "_attempts", {})
    show, submit = make_login_handlers(provider, CONFIG.admin_password_hash)
    app = Starlette(routes=[Route("/oauth/login", show, methods=["GET"]), Route("/oauth/login", submit, methods=["POST"])])
    return TestClient(app, base_url="https://sw.example.com", follow_redirects=False)


def pending_req(provider, redirect="https://claude.ai/api/mcp/auth_callback", name="Claude"):
    return provider._dumps("pending", {
        "client_id": "cid", "client_name": name, "redirect_uri": redirect, "explicit": True,
        "code_challenge": "challenge", "state": "xyz", "scopes": ["smallwins"], "resource": None,
    })


def test_page_shows_where_you_will_be_sent(client, provider):
    res = client.get("/oauth/login", params={"req": pending_req(provider)})
    assert res.status_code == 200
    assert "<strong>claude.ai</strong>" in res.text
    assert "It calls itself “Claude”" in res.text
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["cache-control"] == "no-store"


def test_app_schemes_are_named_as_apps(client, provider):
    res = client.get("/oauth/login", params={"req": pending_req(provider, redirect="cursor://x/oauth/callback")})
    # The whole URI, not just "the cursor app": some schemes hand a web address to a browser.
    assert "<strong>cursor://x/oauth/callback</strong>" in res.text


def test_client_name_is_escaped(client, provider):
    res = client.get("/oauth/login", params={"req": pending_req(provider, name="<script>x</script>")})
    assert "<script>x" not in res.text
    assert "&lt;script&gt;" in res.text


def test_bad_or_missing_request_is_rejected(client):
    assert client.get("/oauth/login", params={"req": "garbage"}).status_code == 400
    assert client.get("/oauth/login").status_code == 400
    assert client.post("/oauth/login", data={"req": "garbage", "password": "pw"}).status_code == 400


def test_wrong_password_re_renders_with_an_error(client, provider):
    res = client.post("/oauth/login", data={"req": pending_req(provider), "password": "nope"})
    assert res.status_code == 401
    assert "Wrong password." in res.text


def test_right_password_redirects_back_with_code_and_state(client, provider):
    res = client.post("/oauth/login", data={"req": pending_req(provider), "password": "pw"})
    assert res.status_code == 302
    back = urlsplit(res.headers["location"])
    assert back.netloc == "claude.ai"
    query = parse_qs(back.query)
    assert query["state"] == ["xyz"] and query["code"][0]


def test_rate_limited_after_five_failures(client, provider):
    req = pending_req(provider)
    for _ in range(5):
        assert client.post("/oauth/login", data={"req": req, "password": "nope"}).status_code == 401
    assert client.post("/oauth/login", data={"req": req, "password": "nope"}).status_code == 429
    assert client.post("/oauth/login", data={"req": req, "password": "pw"}).status_code == 429


def test_rate_limit_is_per_forwarded_ip(client, provider):
    req = pending_req(provider)
    for _ in range(5):
        client.post("/oauth/login", data={"req": req, "password": "nope"}, headers={"x-forwarded-for": "1.1.1.1"})
    res = client.post("/oauth/login", data={"req": req, "password": "pw"}, headers={"x-forwarded-for": "2.2.2.2"})
    assert res.status_code == 302
