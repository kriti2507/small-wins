"""Calls to Flask's /api/mcp/grants endpoints.

A grant is Flask's stored, revocable record of one connected app. Its
credential (`swg_<id>.<secret>`) is what this server sends Flask on that
app's behalf; it rides inside the app's authorization code and tokens.
"""
import httpx


class GrantError(Exception):
    """Flask couldn't be reached or answered unexpectedly."""


async def _call(api_url, method, path, headers, json=None, transport=None):
    try:
        async with httpx.AsyncClient(base_url=api_url, timeout=10, transport=transport) as http:
            return await http.request(method, path, headers=headers, json=json)
    except httpx.HTTPError:
        raise GrantError() from None


def _bearer(credential):
    return {"Authorization": f"Bearer {credential}"}


async def create_grant(api_url, cookie, client_name, redirect_host, transport=None):
    """A new grant for the user the browser's cookie signs in; returns its
    credential."""
    resp = await _call(
        api_url, "POST", "/api/mcp/grants", {"Cookie": cookie or ""},
        json={"client_name": client_name, "redirect_host": redirect_host}, transport=transport,
    )
    if resp.status_code != 201:
        raise GrantError()
    try:
        return resp.json()["credential"]
    except (ValueError, KeyError, TypeError):
        raise GrantError() from None


async def redeem_grant(api_url, credential, transport=None):
    """True the first time a grant's code is exchanged. False if the code was
    replayed (Flask has now deleted the grant) or the grant is unknown."""
    resp = await _call(api_url, "POST", "/api/mcp/grants/redeem", _bearer(credential), transport=transport)
    if resp.status_code == 200:
        return True
    if resp.status_code in (401, 409):
        return False
    raise GrantError()


async def grant_alive(api_url, credential, transport=None):
    """Whether Flask still accepts the credential (not revoked or stale)."""
    resp = await _call(api_url, "GET", "/api/mcp/grants/self", _bearer(credential), transport=transport)
    if resp.status_code == 200:
        return True
    if resp.status_code == 401:
        return False
    raise GrantError()
