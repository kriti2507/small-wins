import httpx
import pytest

from flask_client import FlaskClient, SmallWinsError

pytestmark = pytest.mark.anyio


def client_for(handler):
    return FlaskClient("https://sw.example.com", "svc-token", transport=httpx.MockTransport(handler))


async def test_sends_the_service_token_and_returns_json():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["authorization"]
        seen["url"] = str(request.url)
        return httpx.Response(200, json=[{"slug": "books"}])

    assert await client_for(handler).list_topics() == [{"slug": "books"}]
    assert seen == {"auth": "Bearer svc-token", "url": "https://sw.example.com/api/topics"}


async def test_writes_send_json_bodies():
    seen = {}

    def handler(request):
        seen[request.method] = (request.url.path, request.read())
        return httpx.Response(200, json={"id": 3})

    c = client_for(handler)
    await c.add_entry("books", {"date": "2026-09-01"})
    await c.update_entry("books", 3, {"title": "Dune"})
    assert seen["POST"] == ("/api/topics/books/entries", b'{"date":"2026-09-01"}')
    assert seen["PATCH"] == ("/api/topics/books/entries/3", b'{"title":"Dune"}')


async def test_client_errors_carry_flasks_message():
    c = client_for(lambda r: httpx.Response(404, json={"error": "Unknown entry."}))
    with pytest.raises(SmallWinsError, match="Unknown entry."):
        await c.get_entry("books", 99)


async def test_client_errors_without_json_still_explain():
    c = client_for(lambda r: httpx.Response(403, text="nope"))
    with pytest.raises(SmallWinsError, match=r"Request failed \(403\)"):
        await c.list_topics()


async def test_server_errors_and_network_failures_are_generic():
    c = client_for(lambda r: httpx.Response(500, json={"error": "psycopg traceback"}))
    with pytest.raises(SmallWinsError, match="unavailable"):
        await c.list_topics()

    def down(request):
        raise httpx.ConnectError("boom")

    with pytest.raises(SmallWinsError, match="unavailable"):
        await client_for(down).list_topics()


async def test_get_topic_finds_by_slug_or_says_how_to_recover():
    c = client_for(lambda r: httpx.Response(200, json=[{"slug": "books"}, {"slug": "runs"}]))
    assert (await c.get_topic("runs")) == {"slug": "runs"}
    with pytest.raises(SmallWinsError, match="list_topics"):
        await c.get_topic("hikes")


async def test_slugs_cannot_escape_the_entries_path():
    paths = []

    def handler(request):
        paths.append(request.url.raw_path.decode())
        return httpx.Response(200, json=[])

    await client_for(handler).list_entries("../auth/me#")
    assert paths == ["/api/topics/..%2Fauth%2Fme%23/entries"]
