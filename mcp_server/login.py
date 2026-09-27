"""The page a person sees mid-OAuth: who is asking, where they'll be sent,
and the admin password. On success the browser goes back to the client with
an authorization code."""
import html
import time
from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from werkzeug.security import check_password_hash

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 60
# Best-effort per-IP limit; resets on cold starts, like the Flask login's.
_attempts = {}

# Nothing on this page should ever be framed or cached.
HEADERS = {
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "frame-ancestors 'none'",
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
}


def client_ip(request):
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def too_many_attempts(ip, now=None):
    now = time.time() if now is None else now
    recent = [t for t in _attempts.get(ip, []) if now - t < WINDOW_SECONDS]
    _attempts[ip] = recent
    return len(recent) >= MAX_ATTEMPTS


def record_failure(ip):
    _attempts.setdefault(ip, []).append(time.time())


def destination(redirect_uri):
    """What to show as 'you'll be sent to': the web host, or else the whole
    URI, since an app scheme can still hand a web address to a browser."""
    parts = urlsplit(redirect_uri)
    if parts.scheme in ("http", "https"):
        return parts.hostname or redirect_uri
    return redirect_uri


def render(pending, req, error=None, status=200):
    dest = html.escape(destination(pending["redirect_uri"]))
    name = pending.get("client_name")
    claims = f'<p class="muted">It calls itself “{html.escape(name)}”.</p>' if name else ""
    err = f'<p class="error">{html.escape(error)}</p>' if error else ""
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Connect to Small Wins</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 26rem; margin: 4rem auto; padding: 0 1rem; color: #222; }}
  .dest {{ font-size: 1.15rem; }}
  .muted {{ color: #666; }}
  .error {{ color: #b3261e; }}
  input, button {{ font: inherit; padding: .6rem; width: 100%; box-sizing: border-box; margin-top: .5rem; }}
</style></head>
<body>
  <h1>Connect an app to Small Wins</h1>
  <p class="dest">After you allow, you'll be sent to <strong>{dest}</strong>.</p>
  {claims}
  <p>It will be able to read your entries and add or edit them. Only continue if you started this from that app just now.</p>
  {err}
  <form method="post" action="/oauth/login">
    <input type="hidden" name="req" value="{html.escape(req)}">
    <label>Admin password<input type="password" name="password" autofocus required></label>
    <button type="submit">Allow</button>
  </form>
</body></html>"""
    return HTMLResponse(page, status_code=status, headers=HEADERS)


def invalid_request():
    return HTMLResponse(
        "<p>This login link is invalid or has expired. Start again from your app.</p>",
        status_code=400,
        headers=HEADERS,
    )


def make_login_handlers(provider, password_hash):
    async def show(request: Request):
        req = request.query_params.get("req", "")
        pending = provider.load_pending(req)
        if pending is None:
            return invalid_request()
        return render(pending, req)

    async def submit(request: Request):
        form = await request.form()
        req = str(form.get("req", ""))
        pending = provider.load_pending(req)
        if pending is None:
            return invalid_request()
        ip = client_ip(request)
        if too_many_attempts(ip):
            return render(pending, req, "Too many attempts. Wait a minute and try again.", status=429)
        if not check_password_hash(password_hash, str(form.get("password", ""))):
            record_failure(ip)
            return render(pending, req, "Wrong password.", status=401)
        return RedirectResponse(provider.approve(pending), status_code=302, headers=HEADERS)

    return show, submit
