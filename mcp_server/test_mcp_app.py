"""End to end over HTTP: discovery, registration, login, tokens, a tool call.
httpx's ASGITransport sends no lifespan events, just like a serverless host,
so passing here also proves create_app works without them."""
import base64
import hashlib
import json
import secrets
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from config import Config
from mcp_app import create_app
from oauth import SCOPE, SmallWinsOAuthProvider

pytestmark = pytest.mark.anyio

BASE = "https://sw.example.com"
CONFIG = Config(BASE, BASE, "tok-secret")
ME = {"id": 7, "email": "me@example.com", "name": "Me", "avatar_url": None}
SIGNED_IN = {"cookie": "session=ok"}
CRED = "swg_1." + "s" * 43
REDIRECT = "https://claude.ai/api/mcp/auth_callback"
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-06-18"}
BOOKS = {"slug": "books", "name": "Books", "color": "green", "layout": "photo-top",
         "fields": [{"key": "title", "label": "Title", "type": "text", "direction": "none"}]}


class FakeFlask:
    """Stands in for the whole Flask API: sign-in, grants, and two data routes."""
    def __init__(self):
        self.redeemed = 0
        self.revoked = False

    def __call__(self, request):
        path, method = request.url.path, request.method
        if path == "/api/auth/me":
            if request.headers.get("cookie") == SIGNED_IN["cookie"]:
                return httpx.Response(200, json={"user": ME})
            return httpx.Response(401, json={})
        if path == "/api/mcp/grants" and method == "POST":
            assert request.headers["cookie"] == SIGNED_IN["cookie"]
            assert json.loads(request.read()) == {"client_name": "Claude", "redirect_host": "claude.ai"}
            return httpx.Response(201, json={"credential": CRED})
        assert "x-acting-user" not in request.headers
        if self.revoked or request.headers.get("authorization") != f"Bearer {CRED}":
            return httpx.Response(401, json={"error": "Sign in to continue."})
        if path == "/api/mcp/grants/redeem":
            self.redeemed += 1
            return httpx.Response(200 if self.redeemed == 1 else 409, json={})
        if path == "/api/mcp/grants/self":
            return httpx.Response(200, json={"id": 1})
        if path == "/api/topics":
            return httpx.Response(200, json=[BOOKS])
        if path == "/api/topics/books/entries":
            return httpx.Response(200, json=[{"id": 1, "date": "2026-05-01", "image": None, "title": "Dune"}])
        return httpx.Response(404, json={"error": "Unknown topic."})


@pytest.fixture
def flask():
    return FakeFlask()


@pytest.fixture
async def http(flask):
    app = create_app(CONFIG, transport=httpx.MockTransport(flask))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE) as c:
        yield c


def rpc(method, params=None):
    return {"jsonrpc": "2.0", "id": 1, "method": method, **({"params": params} if params else {})}


async def connect(http):
    """Run the whole OAuth flow the way a client would; return the registration,
    the token response, and the code and PKCE verifier that got them."""
    reg = (await http.post("/register", json={
        "redirect_uris": [REDIRECT], "client_name": "Claude",
        "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
        "token_endpoint_auth_method": "client_secret_post",
    })).json()
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    res = await http.get("/authorize", params={
        "response_type": "code", "client_id": reg["client_id"], "redirect_uri": REDIRECT,
        "code_challenge": challenge, "code_challenge_method": "S256", "state": "xyz",
        "resource": f"{BASE}/mcp",
    })
    assert res.status_code == 302, res.text
    req = parse_qs(urlsplit(res.headers["location"]).query)["req"][0]
    res = await http.post("/oauth/login", data={"req": req}, headers=SIGNED_IN)
    assert res.status_code == 302, res.text
    code = parse_qs(urlsplit(res.headers["location"]).query)["code"][0]
    res = await http.post("/token", data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
        "code_verifier": verifier, "client_id": reg["client_id"], "client_secret": reg["client_secret"],
    })
    assert res.status_code == 200, res.text
    return reg, res.json(), code, verifier


async def test_mcp_requires_a_token_and_points_at_discovery(http):
    res = await http.post("/mcp", headers=MCP_HEADERS, json=rpc("tools/list"))
    assert res.status_code == 401
    assert f'resource_metadata="{BASE}/.well-known/oauth-protected-resource/mcp"' in res.headers["www-authenticate"]


async def test_discovery_metadata(http):
    resource = (await http.get("/.well-known/oauth-protected-resource/mcp")).json()
    assert resource["resource"] == f"{BASE}/mcp"
    assert resource["authorization_servers"] == [BASE]
    server = (await http.get("/.well-known/oauth-authorization-server")).json()
    assert server["registration_endpoint"] == f"{BASE}/register"
    assert server["code_challenge_methods_supported"] == ["S256"]
    assert "revocation_endpoint" not in server  # stateless tokens can't be revoked singly


async def test_full_flow_then_tool_call(http):
    _, tokens, *_ = await connect(http)
    res = await http.post("/mcp", headers={**MCP_HEADERS, "Authorization": f"Bearer {tokens['access_token']}"},
                          json=rpc("tools/call", {"name": "get_entries", "arguments": {"topic": "books"}}))
    assert res.status_code == 200, res.text
    result = res.json()["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["result"][0]["title"] == "Dune"


async def test_refresh_token_gets_a_new_access_token(http):
    reg, tokens, *_ = await connect(http)
    res = await http.post("/token", data={
        "grant_type": "refresh_token", "refresh_token": tokens["refresh_token"],
        "client_id": reg["client_id"], "client_secret": reg["client_secret"],
    })
    assert res.status_code == 200, res.text
    res = await http.post("/mcp", headers={**MCP_HEADERS, "Authorization": f"Bearer {res.json()['access_token']}"},
                          json=rpc("tools/list"))
    assert res.status_code == 200


async def test_forged_tokens_are_refused(http):
    res = await http.post("/mcp", headers={**MCP_HEADERS, "Authorization": "Bearer forged"}, json=rpc("tools/list"))
    assert res.status_code == 401


async def test_registration_rejects_web_http_redirects(http):
    res = await http.post("/register", json={
        "redirect_uris": ["http://evil.example.com/cb"], "grant_types": ["authorization_code"],
        "response_types": ["code"],
    })
    assert res.status_code == 400
    assert res.json()["error"] == "invalid_redirect_uri"


async def test_answers_lifespan_events_itself():
    app = create_app(CONFIG)
    incoming = iter([{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}])
    sent = []

    async def receive():
        return next(incoming)

    async def send(message):
        sent.append(message["type"])

    await app({"type": "lifespan"}, receive, send)
    assert sent == ["lifespan.startup.complete", "lifespan.shutdown.complete"]


async def test_tokens_from_the_full_flow_carry_the_grant(http):
    _, tokens, *_ = await connect(http)
    access = await SmallWinsOAuthProvider(CONFIG).load_access_token(tokens["access_token"])
    assert access.grant == CRED


async def test_pre_grant_access_tokens_are_refused(http):
    # Minted before grants existed (they named a user in "subject"): there's
    # no grant to act through, so the SDK must treat it as invalid and the
    # client re-authenticates.
    provider = SmallWinsOAuthProvider(CONFIG)
    token = provider._dumps("access", {"client_id": "c", "scopes": [SCOPE], "resource": f"{BASE}/mcp",
                                       "subject": "7"})
    res = await http.post("/mcp", headers={**MCP_HEADERS, "Authorization": f"Bearer {token}"}, json=rpc("tools/list"))
    assert res.status_code == 401


async def test_consent_post_without_a_session_is_refused(http):
    reg = (await http.post("/register", json={
        "redirect_uris": [REDIRECT], "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code"], "response_types": ["code"],
    })).json()
    res = await http.get("/authorize", params={
        "response_type": "code", "client_id": reg["client_id"], "redirect_uri": REDIRECT,
        "code_challenge": "x" * 43, "code_challenge_method": "S256", "state": "s",
    })
    req = parse_qs(urlsplit(res.headers["location"]).query)["req"][0]
    res = await http.post("/oauth/login", data={"req": req})
    assert res.status_code == 401


async def test_a_replayed_code_is_refused(http):
    reg, _, code, verifier = await connect(http)
    res = await http.post("/token", data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
        "code_verifier": verifier, "client_id": reg["client_id"], "client_secret": reg["client_secret"],
    })
    assert res.status_code == 400
    assert res.json()["error"] == "invalid_grant"


async def test_revoking_cuts_off_tool_calls_and_refresh(http, flask):
    reg, tokens, *_ = await connect(http)
    flask.revoked = True
    res = await http.post("/mcp", headers={**MCP_HEADERS, "Authorization": f"Bearer {tokens['access_token']}"},
                          json=rpc("tools/call", {"name": "list_topics", "arguments": {}}))
    result = res.json()["result"]
    assert result["isError"] is True
    assert "revoked or has expired" in result["content"][0]["text"]

    res = await http.post("/token", data={
        "grant_type": "refresh_token", "refresh_token": tokens["refresh_token"],
        "client_id": reg["client_id"], "client_secret": reg["client_secret"],
    })
    assert res.status_code == 400
