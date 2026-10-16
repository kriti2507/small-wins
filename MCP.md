# Small Wins MCP server

Lets AI apps (claude.ai, Claude Code, ChatGPT, Cursor, VS Code, …) read your
Small Wins entries and add or edit them, after you approve them while signed in
with Google.

- **Live URL:** `https://small-wins-live.vercel.app/mcp`
- **Code:** `mcp_server/`, served by `api/mcp_endpoint.py`
- **Setup reference:** `DEPLOYMENT.md` → "MCP server"

Contents:
1. [How it works](#1-how-it-works)
2. [Connecting an app](#2-connecting-an-app)
3. [Day-to-day operations](#3-day-to-day-operations)
4. [Troubleshooting](#4-troubleshooting)
5. [Running and testing locally](#5-running-and-testing-locally)
6. [Building this for another app](#6-building-this-for-another-app)

---

## 1. How it works

```
AI app (MCP client) ──HTTPS──▶ small-wins-live.vercel.app
                                ├─ /mcp, /authorize, /token, /register,
                                │  /oauth/login, /.well-known/*   → api/mcp_endpoint.py (MCP server)
                                │        │ HTTPS + grant credential
                                │        ▼
                                ├─ /api/*                          → api/index.py (Flask API)
                                └─ everything else                 → React app
```

- **MCP** (Model Context Protocol) is an open standard. The AI app is the
  *client*, and this project is the *server*. The server offers **tools** the AI can call.
- **Tools:**

  | Tool | What it does | Changes data? |
  |---|---|---|
  | `list_topics` | Topics and their field names | no |
  | `get_entries(topic, from_date?, to_date?)` | Entries, optionally by date range (YYYY-MM-DD); post bodies left out | no |
  | `get_entry(topic, entry_id)` | One entry, including its post | no |
  | `add_entry(topic, date, values)` | New entry; unknown field names are rejected | yes |
  | `update_entry(topic, entry_id, date?, values?)` | Change fields/date; not posts or images | yes |

  There's no delete tool. Apps usually ask you before running a tool that changes data.
- **Charts** aren't a tool. The AI fetches the data and draws the chart itself.
- **The MCP server never touches the database.** It calls your own Flask API,
  so all the app's rules apply. On Allow, it forwards the browser's cookie to
  Flask `POST /api/mcp/grants`, which stores a grant (only a sha256 of its
  secret) and returns the credential `swg_<id>.<secret>`. The credential
  rides, encrypted, in the code and in the app's tokens: exchanging the code
  redeems the grant once (a replay deletes it), refreshing checks the grant
  with Flask, and every tool call sends `Authorization: Bearer <credential>`.
  Flask then scopes every call to that credential's user, as if they'd made
  it in the browser.
- **Login uses OAuth.** Apps get a pass (token) only after you approve them on
  the Small Wins consent page. The passes themselves aren't stored: they're
  signed with `MCP_TOKEN_SECRET`, so changing that secret cancels all of them
  at once. The one stored thing is the grant each pass carries — revocable
  per app on the Connected apps page.

---

## 2. Connecting an app

Every app uses the same URL: **`https://small-wins-live.vercel.app/mcp`**

### The consent page: what to check

When an app connects, your browser opens a Small Wins page:

> After you allow, you'll be sent to **claude.ai**.
> It calls itself "Claude".

- **Only approve if you started this from that app just now.** The bold part
  is where your browser will be sent after you allow. It should match the app
  you're connecting: `claude.ai`, `chatgpt.com`, `localhost` for desktop and
  editor apps, or a full `cursor://…` style address for desktop apps.
- The "calls itself" name is whatever the app says, so trust the bold part more.
- You approve while signed in to Small Wins with Google (the consent page
  offers **Continue with Google** if you aren't).

### claude.ai (web, desktop app, mobile)

1. **Settings** → **Connectors** → **Add custom connector**
2. Name `Small Wins`, URL `https://small-wins-live.vercel.app/mcp` → **Add** → **Connect**
3. Consent page shows **claude.ai** → sign in with Google if asked → **Allow**
4. In a chat, switch Small Wins on in the tools menu.

Once it's connected in claude.ai, it's also available in the Claude desktop and mobile apps
on the same account.

### Claude Code

```sh
claude mcp add --transport http small-wins https://small-wins-live.vercel.app/mcp
```

Then run `/mcp` inside Claude Code, pick `small-wins`, and authenticate.

### Other apps

Any app that supports **remote MCP servers over HTTP with OAuth** works the
same way: add the URL, approve on the consent page. Menu names change often,
so check the app's docs for "custom connector" or "remote MCP server":

- **ChatGPT:** developer mode → connectors → add custom connector with the URL.
- **Cursor:** add to `~/.cursor/mcp.json`:
  ```json
  { "mcpServers": { "small-wins": { "url": "https://small-wins-live.vercel.app/mcp" } } }
  ```
- **VS Code (Copilot):** "MCP: Add Server" command → HTTP → the URL.

### Seeing and revoking connected apps

The **Connected apps** page (`/apps`, linked from the home page header) lists
each app you've connected: its name, where it redirects to, when it
connected, and when it was last used. **Revoke** cuts an app off at its next
call. A connection unused for 30 days also stops working on its own;
reconnect it the same way.

### Reconnecting

Access passes last 1 hour and renew silently for up to 30 days. You only see
the consent page again if:
- you haven't used the app for 30 days,
- you rotated `MCP_TOKEN_SECRET`,
- you revoked it on the Connected apps page, or
- you removed and re-added the connector.

To reconnect, use the app's **Connect / Reconnect / Authenticate** button (in
claude.ai: Settings → Connectors → Small Wins), then approve again.

After upgrading to grants (Phase 3 Part B), every already-connected app needs
to reconnect once: tokens minted before the upgrade carry no grant, so the
app's next call gets a 401 and it re-runs sign-in.

---

## 3. Day-to-day operations

### Environment variables (Vercel → Settings → Environment Variables)

| Name | What it is |
|---|---|
| `APP_BASE_URL` | `https://small-wins-live.vercel.app`. **Must include `https://`**, no trailing `/` |
| `MCP_TOKEN_SECRET` | Random secret that signs app passes and encrypts the grant inside them. Changing it logs out every app |

Make a random secret with:

```sh
.venv/bin/python -c "import secrets; print(secrets.token_hex(32))"
```

**Environment variable changes only apply to new deployments.** After editing,
go to Deployments → latest → ⋯ → **Redeploy**.

### Disconnect every app (kill switch)

To stop a single app, revoke it on the **Connected apps** page (`/apps`) —
its next call fails right away.

To disconnect every app at once:

1. Replace `MCP_TOKEN_SECRET` with a new random value and redeploy. Every
   app's passes stop working immediately.
2. In the Supabase SQL editor, run `delete from mcp_grants;` (or
   `delete from mcp_grants where user_id = <id>;` for one person). Rotating
   alone leaves the dead connections listed on Connected apps until each is
   revoked.

Reconnect the apps you want.

### Signing everyone out

See `DEPLOYMENT.md` → "Signing everyone out". Apps that are already connected
stay connected; use the kill switch above too if you want them to re-approve.

### Check it's healthy

- `https://small-wins-live.vercel.app/.well-known/oauth-protected-resource/mcp`
  should return JSON containing `"resource": "https://small-wins-live.vercel.app/mcp"`.
- Logs: Vercel → project → **Logs**, filter by `mcp_endpoint`.

---

## 4. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `500 FUNCTION_INVOCATION_FAILED` on `/mcp` or `/.well-known/...` | The MCP function crashed on startup | Read Vercel Logs. Usually one of the next two rows |
| Log: `Input should be a valid URL ... input_value='small-wins-live.vercel.app'` | `APP_BASE_URL` missing `https://` | Set the full `https://…` value, redeploy |
| Log: `MCP server is missing env vars: ...` | A variable isn't set for this environment | Add it (Production), redeploy |
| Consent page: "Couldn't check your sign-in" | The MCP function can't reach /api/auth/me | Check the site loads; check Vercel logs |
| Consent page: "This login link is invalid or has expired" | Took over 10 minutes, or the secret was rotated mid-login | Start the connection again from the app |
| App connects but every tool fails with "unavailable" | MCP server can't reach Flask, or Flask is erroring | Check `/api/topics` works; check Flask logs |
| Tool error "This connection was revoked or has expired. Disconnect and reconnect Small Wins." | It was revoked on the Connected apps page, unused for 30 days, or you upgraded to Phase 3 Part B | Disconnect and reconnect the app |
| Tool error "Unknown field(s) …" | The AI used a wrong field name | Normal. The AI reads the valid keys from the error and retries |
| Consent page: "Couldn't connect the app. Try again." | Flask couldn't create the grant | Check Flask logs, and that `004_mcp_grants.sql` was run against this database |
| Registration fails "Redirect URI not allowed" | App uses a non-loopback `http://` or browser-type address | Deliberate; see [Security model](#security-model) |
| MCP Inspector: "Check if your MCP server is running and proxy token is correct" | Inspector opened without its session token | Open the full `http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=…` link from its terminal |
| MCP Inspector shows only 4 tools | The tool list box scrolls | Scroll inside the list |

---

## 5. Running and testing locally

### Automated tests (no database needed)

```sh
cd mcp_server && ../.venv/bin/python -m pytest -q
```

Backend tests are in `backend/` and need a throwaway test database. See the
README.

### Run it and connect the MCP Inspector

You need three terminals, all started from the repo root.
Sign in on `http://localhost:5173` first: cookies are per host, not per port,
so the consent page on :8000 sees that session. ⚠️ Write tools act on whatever
database `backend/.env` points to.

**Terminal 1: Flask**

```sh
.venv/bin/python backend/app.py
```

**Terminal 2: MCP server**

```sh
export APP_BASE_URL=http://localhost:8000
export SMALL_WINS_API_URL=http://localhost:5000
export MCP_TOKEN_SECRET=dev-token-secret
.venv/bin/python -m uvicorn --app-dir api mcp_endpoint:app --port 8000
```

Check: http://localhost:8000/.well-known/oauth-authorization-server shows JSON.

**Terminal 3: MCP Inspector**

```sh
npm_config_cache="$TMPDIR/npm-cache" npx @modelcontextprotocol/inspector
```

1. Open the **full link it prints** (with `MCP_PROXY_AUTH_TOKEN=…`).
2. Transport **Streamable HTTP**, URL `http://localhost:8000/mcp` → **Connect**.
3. Consent page says **localhost** → sign in on http://localhost:5173 first → **Allow**.
4. **Tools** → **List Tools** → run `list_topics`.

---

## 6. Building this for another app

A recipe for giving any web app with an HTTP API its own MCP server, with the
same approach and none of the problems we hit the first time.

### Decisions to make first

1. **What should the AI be able to do?** Start with reads. Add writes that
   can't destroy data (add/update). Leave out delete unless you really need it.
2. **Where does it run?** Next to the app, on the same domain. On Vercel,
   that means a second function in the same project.
3. **How does it get data?** Call the app's own API rather than the database,
   so its validation and rules stay in one place.
4. **Who can connect?** Anyone who can sign in to the web app: sign-in gated
   by an email allowlist, open app registration, and a consent page that shows
   the destination. Each app's token names the user who approved it, and the
   MCP server acts only as that user.

### What to copy, and what to change

| File | Reuse? | Notes |
|---|---|---|
| `mcp_server/oauth.py` | **Copy as-is** | Stateless OAuth provider + redirect policy. App-agnostic |
| `mcp_server/login.py` | Copy, reword | Change the page title/text ("Connect an app to Small Wins") |
| `mcp_server/config.py` | Copy, adjust | Rename `SMALL_WINS_API_URL`; keep the rest |
| `mcp_server/mcp_app.py` | Copy, adjust | Change `name` and `INSTRUCTIONS`; keep the auth settings and the lifespan wrapper |
| `mcp_server/flask_client.py` | **Rewrite** | One method per API call your tools need; keep `SmallWinsError(ToolError)` and the error mapping |
| `mcp_server/tools.py` | **Rewrite** | Your tools. Keep the pattern: pure helpers for validation, thin async tool functions |
| `api/mcp_endpoint.py` | Copy | Vercel entry point |
| `vercel.json` rewrites | Copy the 4 MCP lines | Put them **before** any catch-all SPA rewrite |
| Backend change | Re-implement | Store a grant per connected app (a table like `mcp_grants`), accept `Authorization: Bearer <grant credential>` in your auth check, and expose create (session only) / redeem / self endpoints — see `backend/grants.py` |
| Tests | Copy and adapt | `test_oauth.py` and `test_login.py` carry over nearly unchanged; `test_mcp_app.py` is the end-to-end template |

### Steps

1. **Python ≥ 3.10.** The `mcp` SDK v2 needs it. Pin with `.python-version`
   (`3.12`) and rebuild the venv (`uv venv -p 3.12 .venv`).
2. **Add dependencies:** `mcp==<exact version>` and `httpx`. Pin `mcp` exactly
   (see gotchas).
3. **Backend: store grants and accept the grant credential** (a few lines plus tests).
4. **Copy the reusable files**, then write your `*_client.py` and `tools.py`.
   Good tool descriptions matter: they're the only instructions the AI gets.
   Say which tool to call first, date formats, and what each field means.
5. **Run the tests**, then run locally and connect the MCP Inspector (section 5).
6. **Vercel:** add `api/mcp_endpoint.py`, the `functions` entry with
   `includeFiles`, and the rewrites. Set `APP_BASE_URL` (with `https://`),
   `MCP_TOKEN_SECRET`, and whatever your sign-in needs (e.g. OAuth client
   credentials). Deploy.
7. **Check** `/.well-known/oauth-protected-resource/mcp`, then connect a real app.

### Gotchas we hit, and their fixes

| Gotcha | What happens | Fix |
|---|---|---|
| mcp SDK v2 renamed `FastMCP` | v1 tutorials fail with `No module named 'mcp.server.fastmcp'` | Use `from mcp.server.mcpserver import MCPServer` |
| SDK needs Python ≥ 3.10 | Install fails on older venvs | Rebuild the venv on 3.12 |
| Serverless may skip ASGI lifespan | Every request: `Task group is not initialized` | `create_app` answers lifespan itself and runs the SDK lifespan per request (stateless mode makes that cheap) |
| SDK host check (DNS-rebinding protection) | Blocks your real domain or preview URLs | Disable it explicitly for a public, token-protected server |
| SDK's `/register` makes a random `client_id` that it expects you to store | Stateless design breaks | `register_client` rewrites `client_id`/`client_secret` on the object the SDK returns. **Pin the SDK version**; the e2e test catches breakage |
| Clients request scopes | `invalid_scope` if the server has none | One scope (`smallwins`), required, default for registrations |
| The app already has a `/login` page | Rewrite clash | Consent page lives at `/oauth/login` |
| Naming the Vercel file `api/mcp.py` | Would shadow the `mcp` package on import | Name it `api/mcp_endpoint.py` |
| `APP_BASE_URL` without `https://` | Function crashes at import (pydantic URL error) | Always the full origin |
| Env vars changed but not redeployed | Old values still in use | Redeploy after every change |
| "App" schemes that open web pages (`intent://`, `x-safari-https://`, `microsoft-edge:`) | Consent page showed "the intent app" while the code went to a website | Block those schemes; show the **full URI** for any non-web redirect |
| IDs from the AI put straight into API paths | A slug like `../auth` reaches other endpoints | URL-escape path parts (`quote(slug, safe="")`) |
| Backend silently ignores unknown fields | AI typos are lost without an error | Validate keys in the tool and return the valid ones in the error |

### Security model

- **Every MCP request needs a signed access token.** Tokens are HMAC-signed
  (`itsdangerous`), each kind with its own salt, with expiry (code 5 min,
  access 1 h, refresh 30 days) and tied to the client that got them.
- **Anyone can register an app.** Protection comes from:
  - sign-in restricted to an allowlist of emails;
  - the consent page showing where the code will go;
  - PKCE (required by the SDK);
  - the redirect policy: https anywhere, http only to localhost, no browser-type schemes.
- **Accepted trade-offs:**
  - the login rate limit resets on cold starts;
  - an `/authorize` request can redirect a browser to a registered https
    address with an error, which is standard OAuth behaviour when
    registration is open.
- Codes and tokens carry the grant credential encrypted (Fernet, with a key
  derived from `MCP_TOKEN_SECRET`), so neither the app nor anyone who sees
  the code in a browser URL can read it and call `/api/*` directly. Flask
  stores only the credential's hash, and refuses to redeem a grant more
  than 10 minutes old (codes last 5).

Design history: `docs/superpowers/specs/2026-09-24-mcp-server-design.md` and
`docs/superpowers/plans/2026-09-27-mcp-server.md` (local only, not in git).
