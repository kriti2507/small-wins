import json

import httpx
import pytest

from grant_api import GrantError, create_grant, grant_alive, redeem_grant

pytestmark = pytest.mark.anyio

API = "https://sw.example.com"
CRED = "swg_1." + "s" * 43


def flask_answering(status, body=None, seen=None):
    def handler(request):
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=body)
    return httpx.MockTransport(handler)


def down():
    def handler(request):
        raise httpx.ConnectError("down")
    return httpx.MockTransport(handler)


async def test_create_grant_forwards_the_cookie_and_returns_the_credential():
    seen = []
    cred = await create_grant(API, "session=abc", "Claude", "claude.ai",
                              transport=flask_answering(201, {"credential": CRED}, seen))
    assert cred == CRED
    req = seen[0]
    assert (req.method, req.url.path) == ("POST", "/api/mcp/grants")
    assert req.headers["cookie"] == "session=abc"
    assert "authorization" not in req.headers
    assert json.loads(req.read()) == {"client_name": "Claude", "redirect_host": "claude.ai"}


@pytest.mark.parametrize("status,body", [(401, {}), (400, {}), (500, {}), (201, {"nope": 1}), (200, {"credential": CRED})])
async def test_create_grant_raises_unless_flask_created_one(status, body):
    with pytest.raises(GrantError):
        await create_grant(API, "session=abc", "Claude", "claude.ai", transport=flask_answering(status, body))


async def test_create_grant_raises_when_flask_is_unreachable():
    with pytest.raises(GrantError):
        await create_grant(API, "session=abc", None, "claude.ai", transport=down())


async def test_redeem_sends_the_credential():
    seen = []
    assert await redeem_grant(API, CRED, transport=flask_answering(200, {"ok": True}, seen)) is True
    assert (seen[0].method, seen[0].url.path) == ("POST", "/api/mcp/grants/redeem")
    assert seen[0].headers["authorization"] == f"Bearer {CRED}"
    assert "cookie" not in seen[0].headers


@pytest.mark.parametrize("status", [401, 409])
async def test_redeem_is_false_for_replayed_or_unknown_grants(status):
    assert await redeem_grant(API, CRED, transport=flask_answering(status, {})) is False


@pytest.mark.parametrize("transport", [flask_answering(500, {}), down()])
async def test_redeem_raises_when_flask_fails(transport):
    with pytest.raises(GrantError):
        await redeem_grant(API, CRED, transport=transport)


async def test_grant_alive_asks_flask_with_the_credential():
    seen = []
    assert await grant_alive(API, CRED, transport=flask_answering(200, {"id": 1}, seen)) is True
    assert (seen[0].method, seen[0].url.path) == ("GET", "/api/mcp/grants/self")
    assert seen[0].headers["authorization"] == f"Bearer {CRED}"
    assert await grant_alive(API, CRED, transport=flask_answering(401, {})) is False


@pytest.mark.parametrize("transport", [flask_answering(502, {}), down()])
async def test_grant_alive_raises_when_flask_fails(transport):
    with pytest.raises(GrantError):
        await grant_alive(API, CRED, transport=transport)
