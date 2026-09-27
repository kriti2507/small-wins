import json

import httpx
import pytest
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from flask_client import FlaskClient, SmallWinsError
from tools import check_values, filter_entries, parse_date, register_tools

pytestmark = pytest.mark.anyio

BOOKS = {"slug": "books", "name": "Books", "color": "green", "layout": "photo-top", "fields": [
    {"key": "title", "label": "Title", "type": "text", "direction": "none"},
    {"key": "rating", "label": "Rating", "type": "number", "direction": "higher"},
]}
ENTRIES = [
    {"id": 1, "date": "2026-04-08", "image": None, "title": "A", "rating": 4.0},
    {"id": 2, "date": "2026-05-07", "image": None, "title": "B", "rating": None, "body": {"type": "doc"}},
    {"id": 3, "date": "", "image": None, "title": "C", "rating": None},
]


# --- pure helpers -----------------------------------------------------------

def test_parse_date():
    assert str(parse_date("2026-09-01")) == "2026-09-01"
    for bad in ("09/01/2026", "", None, "2026-13-01"):
        with pytest.raises(SmallWinsError, match="YYYY-MM-DD"):
            parse_date(bad)


def test_filter_entries_without_range_keeps_all_and_strips_bodies():
    out = filter_entries(ENTRIES)
    assert [e["id"] for e in out] == [1, 2, 3]
    assert all("body" not in e for e in out)
    assert [e["has_post"] for e in out] == [False, True, False]


def test_filter_entries_range_is_inclusive_and_skips_undated():
    assert [e["id"] for e in filter_entries(ENTRIES, "2026-04-08", "2026-05-07")] == [1, 2]
    assert [e["id"] for e in filter_entries(ENTRIES, from_date="2026-05-01")] == [2]
    assert [e["id"] for e in filter_entries(ENTRIES, to_date="2026-04-30")] == [1]


def test_filter_entries_rejects_bad_range_dates():
    with pytest.raises(SmallWinsError, match="from_date"):
        filter_entries(ENTRIES, from_date="last week")


def test_check_values_names_unknown_and_valid_keys():
    check_values(BOOKS, {"title": "Dune"})
    with pytest.raises(SmallWinsError, match="Unknown field\\(s\\) for books: auther. Valid keys: rating, title."):
        check_values(BOOKS, {"title": "Dune", "auther": "Herbert"})


# --- tools, through the MCP server ------------------------------------------

@pytest.fixture
def flask():
    """A fake Flask API that records write requests."""
    calls = []

    def handler(request):
        path, method = request.url.path, request.method
        if path == "/api/topics":
            return httpx.Response(200, json=[BOOKS])
        if path == "/api/topics/books/entries" and method == "GET":
            return httpx.Response(200, json=ENTRIES)
        if path == "/api/topics/books/entries/2" and method == "GET":
            return httpx.Response(200, json=ENTRIES[1])
        if method in ("POST", "PATCH"):
            calls.append((method, path, json.loads(request.read())))
            return httpx.Response(201 if method == "POST" else 200, json={"id": 9})
        return httpx.Response(404, json={"error": "Unknown topic."})

    handler.calls = calls
    return handler


@pytest.fixture
def server(flask):
    mcp = MCPServer(name="test")
    register_tools(mcp, lambda: FlaskClient("https://sw.example.com", "svc", transport=httpx.MockTransport(flask)))
    return mcp


async def call(server, name, **arguments):
    """A tool's return value. Lists come back as structured content; dicts as JSON text."""
    result = await server.call_tool(name, arguments)
    if result.structured_content is not None:
        return result.structured_content["result"]
    return json.loads(result.content[0].text)


async def call_error(server, name, **arguments):
    """The message a failing tool sends the model."""
    with pytest.raises(ToolError) as err:
        await server.call_tool(name, arguments)
    return str(err.value)


async def test_tools_are_listed_with_read_and_write_hints(server):
    tools = {t.name: t for t in await server.list_tools()}
    assert set(tools) == {"list_topics", "get_entries", "get_entry", "add_entry", "update_entry"}
    for name in ("list_topics", "get_entries", "get_entry"):
        assert tools[name].annotations.read_only_hint is True
    for name in ("add_entry", "update_entry"):
        assert tools[name].annotations.read_only_hint is False
        assert tools[name].annotations.destructive_hint is False


async def test_list_topics_summarizes(server):
    assert await call(server, "list_topics") == [{"slug": "books", "name": "Books", "fields": [
        {"key": "title", "label": "Title", "type": "text"},
        {"key": "rating", "label": "Rating", "type": "number"},
    ]}]


async def test_get_entries_filters_and_strips_bodies(server):
    out = await call(server, "get_entries", topic="books", from_date="2026-05-01")
    assert out == [{"id": 2, "date": "2026-05-07", "image": None, "title": "B", "rating": None, "has_post": True}]


async def test_get_entry_includes_body(server):
    assert (await call(server, "get_entry", topic="books", entry_id=2))["body"] == {"type": "doc"}


async def test_add_entry_posts_values_with_date(server, flask):
    await call(server, "add_entry", topic="books", date="2026-09-01", values={"title": "Dune", "rating": 5})
    assert flask.calls == [("POST", "/api/topics/books/entries", {"title": "Dune", "rating": 5, "date": "2026-09-01"})]


async def test_add_entry_rejects_unknown_fields_without_writing(server, flask):
    msg = await call_error(server, "add_entry", topic="books", date="2026-09-01", values={"titel": "Dune"})
    assert "Unknown field(s) for books: titel" in msg
    assert flask.calls == []


async def test_add_entry_rejects_bad_dates_and_topics(server, flask):
    assert "YYYY-MM-DD" in await call_error(server, "add_entry", topic="books", date="yesterday", values={})
    assert "list_topics" in await call_error(server, "add_entry", topic="hikes", date="2026-09-01", values={})
    assert flask.calls == []


async def test_update_entry_patches_only_what_was_passed(server, flask):
    await call(server, "update_entry", topic="books", entry_id=2, values={"rating": 3})
    await call(server, "update_entry", topic="books", entry_id=2, date="2026-05-08")
    assert flask.calls == [
        ("PATCH", "/api/topics/books/entries/2", {"rating": 3}),
        ("PATCH", "/api/topics/books/entries/2", {"date": "2026-05-08"}),
    ]


async def test_update_entry_needs_something_to_change(server, flask):
    assert "Nothing to update" in await call_error(server, "update_entry", topic="books", entry_id=2)
    assert flask.calls == []


async def test_flask_errors_reach_the_model(server):
    assert "Unknown topic." in await call_error(server, "get_entries", topic="nope")
