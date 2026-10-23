"""The page a person sees mid-OAuth: who is asking, where they'll be sent,
and which account is signed in. Signing in is the web app's Google login:
both apps share an origin, so the browser's Flask session cookie arrives here
too, and Flask says whose it is. On Allow, Flask creates a grant (a revocable
record of this connection) for that user, and the browser goes back to the
client with an authorization code carrying it."""
import html
from urllib.parse import urlencode, urlsplit

import httpx
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from grant_api import GrantError

CHECK_FAILED = "Couldn't check your sign-in. Try again."
CONNECT_FAILED = "Couldn't connect the app. Try again."

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


# Same paper-journal look as the web app (frontend/src/styles/style.css).
STYLE = """
  :root { --paper: #faf5ec; --card: #fffdf8; --border: #e7dcc9; --border-soft: #efe5d3;
    --ink: #3d3229; --ink-strong: #3b3128; --ink-muted: #8a7a63; --accent: #b3654a; --danger: #a4442d; }
  * { box-sizing: border-box; }
  body { margin: 0; min-height: 100vh; display: flex; flex-direction: column; align-items: center;
    justify-content: center; padding: 2rem 1rem; background: var(--paper); color: var(--ink);
    font-family: "Lora", Georgia, serif; line-height: 1.6; }
  .brand { font-family: "Caveat", cursive; font-size: 1.6rem; color: var(--accent); margin: 0 0 .75rem; }
  .card { width: 100%; max-width: 28rem; background: var(--card); border: 1px solid var(--border);
    border-radius: 18px; padding: 2rem; box-shadow: 0 12px 32px -16px rgba(93, 78, 55, .3); }
  h1 { margin: 0 0 1.25rem; font-family: "Fraunces", Georgia, serif; font-weight: 600;
    font-size: 1.75rem; line-height: 1.2; letter-spacing: -.015em; color: var(--ink-strong); }
  p { margin: 0 0 1rem; }
  .dest { margin-bottom: 1.25rem; padding: .9rem 1rem; border-radius: 12px; background: var(--paper);
    border: 1px solid var(--border-soft); }
  .dest strong { display: block; font-size: 1.2rem; color: var(--ink-strong); word-break: break-all; }
  .dest .muted { margin: .25rem 0 0; font-size: .9rem; }
  .muted { color: var(--ink-muted); }
  .note { font-size: .9rem; color: var(--ink-muted); }
  .error { color: var(--danger); font-size: .95rem; }
  .who { margin: 1.5rem 0 0; padding-top: 1.25rem; border-top: 1px dashed var(--border);
    font-size: .95rem; word-break: break-word; }
  button, .button { display: block; width: 100%; margin-top: .75rem; padding: .7rem 1rem;
    font: inherit; font-weight: 500; text-align: center; text-decoration: none; cursor: pointer;
    color: var(--card); background: var(--accent); border: 1px solid var(--accent); border-radius: 999px;
    transition: transform .2s ease, box-shadow .2s ease; }
  button:hover, .button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px -4px rgba(179, 101, 74, .5); }
  button:active, .button:active { transform: scale(.98); box-shadow: none; }
  button:focus-visible, .button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
"""

FONTS = (
    "https://fonts.googleapis.com/css2?family=Caveat:wght@500"
    "&family=Fraunces:opsz,wght@9..144,600&family=Lora:wght@400;500&display=swap"
)


def shell(title, body, status):
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="{html.escape(FONTS)}">
<style>{STYLE}</style></head>
<body>
  <p class="brand">Small Wins</p>
  <main class="card">
  {body}
  </main>
</body></html>"""
    return HTMLResponse(page, status_code=status, headers=HEADERS)


def render(pending, req, user, error=None, status=200):
    dest = html.escape(destination(pending["redirect_uri"]))
    name = pending.get("client_name")
    claims = f'<p class="muted">It calls itself “{html.escape(name)}”.</p>' if name else ""
    # quote=False: this text lands inside a <p>, not an attribute, and
    # escaping quotes would mangle contractions like "Couldn't".
    err = f'<p class="error">{html.escape(error, quote=False)}</p>' if error else ""
    if user:
        action = f"""<p class="who">Signed in as <strong>{html.escape(user["email"])}</strong>.</p>
  <form method="post" action="/oauth/login">
    <input type="hidden" name="req" value="{html.escape(req)}">
    <button type="submit">Allow</button>
  </form>"""
    else:
        action = f'<a class="button" href="{html.escape(google_link(req))}">Continue with Google</a>'
    body = f"""<h1>Connect an app</h1>
  <div class="dest">After you allow, you'll be sent to <strong>{dest}</strong>{claims}</div>
  <p>It will be able to read your entries and add or edit them.</p>
  <p class="note">Only continue if you started this from that app just now.</p>
  {err}
  {action}"""
    return shell("Connect to Small Wins", body, status)


def invalid_request():
    return shell(
        "Connect to Small Wins",
        "<p>This login link is invalid or has expired. Start again from your app.</p>",
        400,
    )


def make_login_handlers(provider, check_user, create_grant):
    """check_user(cookie_header) -> user dict, None if signed out, or raises
    SignInCheckFailed. create_grant(cookie, client_name, redirect_host) ->
    credential, or raises GrantError."""

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
        try:
            credential = await create_grant(
                request.headers.get("cookie"), pending.get("client_name"), destination(pending["redirect_uri"])
            )
        except GrantError:
            return render(pending, req, user, CONNECT_FAILED, status=502)
        return RedirectResponse(provider.approve(pending, credential), status_code=302, headers=HEADERS)

    return show, submit
