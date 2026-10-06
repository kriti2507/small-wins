"""The page a person sees mid-OAuth: who is asking, where they'll be sent,
and which account is signed in. Signing in is the web app's Google login:
both apps share an origin, so the browser's Flask session cookie arrives here
too, and Flask says whose it is. On Allow, the browser goes back to the client
with an authorization code."""
import html
from urllib.parse import urlencode, urlsplit

import httpx
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

CHECK_FAILED = "Couldn't check your sign-in. Try again."

# Nothing on this page should ever be framed or cached.
HEADERS = {
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "frame-ancestors 'none'",
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
}


class SignInCheckFailed(Exception):
    """Flask couldn't say who is signed in (down, or an unexpected reply)."""


async def signed_in_user(api_url, cookie, transport=None):
    """The user the browser's Flask session belongs to, or None if signed out."""
    if not cookie:
        return None
    try:
        async with httpx.AsyncClient(base_url=api_url, timeout=10, transport=transport) as http:
            resp = await http.get("/api/auth/me", headers={"Cookie": cookie})
    except httpx.HTTPError:
        raise SignInCheckFailed() from None
    if resp.status_code == 401:
        return None
    if resp.status_code != 200:
        raise SignInCheckFailed()
    try:
        return resp.json()["user"]
    except (ValueError, KeyError, TypeError):
        raise SignInCheckFailed() from None


def destination(redirect_uri):
    """What to show as 'you'll be sent to': the web host, or else the whole
    URI, since an app scheme can still hand a web address to a browser."""
    parts = urlsplit(redirect_uri)
    if parts.scheme in ("http", "https"):
        return parts.hostname or redirect_uri
    return redirect_uri


def google_link(req):
    """Flask's Google sign-in, coming back to this same page afterwards."""
    back = f"/oauth/login?{urlencode({'req': req})}"
    return f"/api/auth/google?{urlencode({'next': back})}"


def render(pending, req, user, error=None, status=200):
    dest = html.escape(destination(pending["redirect_uri"]))
    name = pending.get("client_name")
    claims = f'<p class="muted">It calls itself “{html.escape(name)}”.</p>' if name else ""
    # quote=False: this text lands inside a <p>, not an attribute, and
    # escaping quotes would mangle contractions like "Couldn't".
    err = f'<p class="error">{html.escape(error, quote=False)}</p>' if error else ""
    if user:
        action = f"""<p>Signed in as <strong>{html.escape(user["email"])}</strong>.</p>
  <form method="post" action="/oauth/login">
    <input type="hidden" name="req" value="{html.escape(req)}">
    <button type="submit">Allow</button>
  </form>"""
    else:
        action = f'<a class="button" href="{html.escape(google_link(req))}">Continue with Google</a>'
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Connect to Small Wins</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 26rem; margin: 4rem auto; padding: 0 1rem; color: #222; }}
  .dest {{ font-size: 1.15rem; }}
  .muted {{ color: #666; }}
  .error {{ color: #b3261e; }}
  button, .button {{ display: block; font: inherit; padding: .6rem; width: 100%; box-sizing: border-box;
    margin-top: .5rem; text-align: center; border: 1px solid #888; border-radius: 6px;
    background: #f4f4f4; color: inherit; text-decoration: none; cursor: pointer; }}
</style></head>
<body>
  <h1>Connect an app to Small Wins</h1>
  <p class="dest">After you allow, you'll be sent to <strong>{dest}</strong>.</p>
  {claims}
  <p>It will be able to read your entries and add or edit them. Only continue if you started this from that app just now.</p>
  {err}
  {action}
</body></html>"""
    return HTMLResponse(page, status_code=status, headers=HEADERS)


def invalid_request():
    return HTMLResponse(
        "<p>This login link is invalid or has expired. Start again from your app.</p>",
        status_code=400,
        headers=HEADERS,
    )


def make_login_handlers(provider, check_user):
    """check_user(cookie_header) -> user dict, None if signed out, or raises
    SignInCheckFailed."""

    async def show(request: Request):
        req = request.query_params.get("req", "")
        pending = provider.load_pending(req)
        if pending is None:
            return invalid_request()
        try:
            user = await check_user(request.headers.get("cookie"))
        except SignInCheckFailed:
            return render(pending, req, None, CHECK_FAILED, status=502)
        return render(pending, req, user)

    async def submit(request: Request):
        form = await request.form()
        req = str(form.get("req", ""))
        pending = provider.load_pending(req)
        if pending is None:
            return invalid_request()
        try:
            # Checked again here, not trusted from the GET: the session cookie
            # is SameSite=Lax, so a POST forged by another site arrives without
            # it and lands in the "signed out" branch.
            user = await check_user(request.headers.get("cookie"))
        except SignInCheckFailed:
            return render(pending, req, None, CHECK_FAILED, status=502)
        if user is None:
            return render(pending, req, None, "Sign in with Google first.", status=401)
        return RedirectResponse(provider.approve(pending, user["id"]), status_code=302, headers=HEADERS)

    return show, submit
