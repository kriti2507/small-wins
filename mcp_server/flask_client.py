"""Talks to the Small Wins Flask API. The MCP server never touches the
database; everything goes through these calls, so the API's rules apply."""
import httpx
from mcp.server.mcpserver.exceptions import ToolError


class SmallWinsError(ToolError):
    """A failure whose message is safe and useful to show the model."""


class FlaskClient:
    def __init__(self, base_url, service_token, transport=None):
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {service_token}"},
            timeout=15,
            transport=transport,
        )

    async def aclose(self):
        await self._http.aclose()

    async def _request(self, method, path, json=None):
        try:
            resp = await self._http.request(method, path, json=json)
        except httpx.HTTPError:
            raise SmallWinsError("Small Wins is unavailable, try again.") from None
        if resp.status_code >= 500:
            raise SmallWinsError("Small Wins is unavailable, try again.")
        if resp.status_code >= 400:
            try:
                message = resp.json().get("error")
            except ValueError:
                message = None
            raise SmallWinsError(message or f"Request failed ({resp.status_code}).")
        return resp.json()

    async def list_topics(self):
        return await self._request("GET", "/api/topics")

    async def get_topic(self, slug):
        for topic in await self.list_topics():
            if topic["slug"] == slug:
                return topic
        raise SmallWinsError(f"Unknown topic '{slug}'. Call list_topics to see the valid slugs.")

    async def list_entries(self, slug):
        return await self._request("GET", f"/api/topics/{slug}/entries")

    async def get_entry(self, slug, entry_id):
        return await self._request("GET", f"/api/topics/{slug}/entries/{entry_id}")

    async def add_entry(self, slug, payload):
        return await self._request("POST", f"/api/topics/{slug}/entries", json=payload)

    async def update_entry(self, slug, entry_id, payload):
        return await self._request("PATCH", f"/api/topics/{slug}/entries/{entry_id}", json=payload)
