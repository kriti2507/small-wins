"""The five Small Wins tools. Pure helpers do the filtering and validation so
they can be tested without HTTP; the tools glue them to the Flask API."""
from datetime import date as Date

from mcp.types import ToolAnnotations

from flask_client import SmallWinsError

READ = ToolAnnotations(read_only_hint=True, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)


def parse_date(value, name="date"):
    try:
        return Date.fromisoformat(value)
    except (TypeError, ValueError):
        raise SmallWinsError(f"{name} must be YYYY-MM-DD, got {value!r}.") from None


def summarize_topic(topic):
    return {
        "slug": topic["slug"],
        "name": topic["name"],
        "fields": [{"key": f["key"], "label": f["label"], "type": f["type"]} for f in topic["fields"]],
    }


def filter_entries(entries, from_date=None, to_date=None):
    """Entries in the inclusive date range, without their (large) post bodies."""
    start = parse_date(from_date, "from_date") if from_date else None
    end = parse_date(to_date, "to_date") if to_date else None
    out = []
    for entry in entries:
        if start or end:
            try:
                day = Date.fromisoformat(entry.get("date") or "")
            except ValueError:
                continue  # an undated entry can't match a date filter
            if (start and day < start) or (end and day > end):
                continue
        slim = {k: v for k, v in entry.items() if k != "body"}
        slim["has_post"] = "body" in entry
        out.append(slim)
    return out


def check_values(topic, values):
    """Flask silently drops unknown keys; fail loudly so a typo isn't lost."""
    valid = {f["key"] for f in topic["fields"]}
    unknown = sorted(set(values) - valid)
    if unknown:
        raise SmallWinsError(
            f"Unknown field(s) for {topic['slug']}: {', '.join(unknown)}. "
            f"Valid keys: {', '.join(sorted(valid))}."
        )


def register_tools(mcp, make_client):
    """make_client() returns a fresh FlaskClient; each tool call gets its own."""

    async def with_client(run):
        client = make_client()
        try:
            return await run(client)
        finally:
            await client.aclose()

    @mcp.tool(annotations=READ)
    async def list_topics() -> list[dict]:
        """List Small Wins topics (e.g. books, runs) with their field keys and
        types. Call this first: the other tools take a topic slug and field keys."""
        async def run(c):
            return [summarize_topic(t) for t in await c.list_topics()]
        return await with_client(run)

    @mcp.tool(annotations=READ)
    async def get_entries(topic: str, from_date: str | None = None, to_date: str | None = None) -> list[dict]:
        """Entries for one topic. Optional from_date / to_date (YYYY-MM-DD,
        inclusive) narrow the range. Post bodies are left out; has_post says
        whether an entry has one (read it with get_entry)."""
        async def run(c):
            return filter_entries(await c.list_entries(topic), from_date, to_date)
        return await with_client(run)

    @mcp.tool(annotations=READ)
    async def get_entry(topic: str, entry_id: int) -> dict:
        """One entry, including its post body if it has one."""
        async def run(c):
            return await c.get_entry(topic, entry_id)
        return await with_client(run)

    @mcp.tool(annotations=WRITE)
    async def add_entry(topic: str, date: str, values: dict) -> dict:
        """Add an entry. date is YYYY-MM-DD. values maps field keys (from
        list_topics) to values, e.g. {"title": "Dune", "author": "Frank Herbert"};
        number fields take numbers."""
        parse_date(date)

        async def run(c):
            check_values(await c.get_topic(topic), values)
            return await c.add_entry(topic, {**values, "date": date})
        return await with_client(run)

    @mcp.tool(annotations=WRITE)
    async def update_entry(topic: str, entry_id: int, date: str | None = None, values: dict | None = None) -> dict:
        """Change an entry's date and/or field values; only what you pass
        changes. Posts and images can't be edited here."""
        values = values or {}
        if date is None and not values:
            raise SmallWinsError("Nothing to update: pass date and/or values.")
        if date is not None:
            parse_date(date)

        async def run(c):
            check_values(await c.get_topic(topic), values)
            payload = dict(values) if date is None else {**values, "date": date}
            return await c.update_entry(topic, entry_id, payload)
        return await with_client(run)
