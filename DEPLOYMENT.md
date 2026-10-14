# Deploying Small Wins (Vercel + Supabase)

The frontend and Flask API deploy together as one Vercel project; data lives in
Supabase (Postgres + Storage). Do the one-time setup once, then deploys are
`git push` (or `vercel --prod`).

## 1. Supabase setup (once)

1. Create a Supabase project. Use a second, separate project for local dev —
   see [Local development](#local-development).
2. **SQL Editor** → run the contents of `backend/schema.sql` (all tables, with
   RLS on).
3. **Storage** → new bucket `uploads`, **Public**.
4. Collect these values:
   - `DATABASE_URL` — **Transaction pooler** string (port 6543) for Vercel.
   - `SUPABASE_URL` — project URL.
   - `SUPABASE_SERVICE_KEY` — the **service_role** key (server-side only).

## 2. Google sign-in (once)

1. Google Cloud Console → **APIs & Services → OAuth consent screen**: user type
   **External**, app name `Small Wins`, your email as support/developer
   contact. Leave it in **Testing** and add your Google account under
   **Test users** (Testing allows up to 100 listed users).
2. **Credentials → Create credentials → OAuth client ID** → *Web application*.
   Authorized redirect URIs (exact; Google allows no wildcards, so preview
   deployments can't sign in):
   - `https://small-wins-live.vercel.app/api/auth/google/callback`
   - `http://localhost:5173/api/auth/google/callback`
3. Copy the client ID and secret. Generate a session secret:

```sh
.venv/bin/python -c "import secrets; print(secrets.token_hex(32))"
```

## 3. Vercel environment variables

In the Vercel project → Settings → Environment Variables, set:

| Var | Value |
|-----|-------|
| `DATABASE_URL` | Supabase transaction-pooler string (6543) |
| `SUPABASE_URL` | `https://PROJECT.supabase.co` |
| `SUPABASE_SERVICE_KEY` | service_role key |
| `SUPABASE_BUCKET` | `uploads` |
| `GOOGLE_CLIENT_ID` | from step 2 |
| `GOOGLE_CLIENT_SECRET` | from step 2 |
| `ALLOWED_EMAILS` | comma-separated emails allowed to sign in, e.g. `you@gmail.com` |
| `SECRET_KEY` | from step 2 |
| `TRUST_PROXY` | `1` |
| `MCP_SERVICE_TOKEN` | only if using the MCP server, see below |

Never commit these or expose the service key to the frontend.

## 4. Deploy

```sh
vercel --prod
```

Verify: `curl -s -o /dev/null -w "%{http_code}\n" https://yourdomain/api/topics`
→ `401`. Open the site → you land on the sign-in page → **Sign in with Google**
→ your topics. A Google account not in `ALLOWED_EMAILS` sees "isn't invited".

## 5. Import the original data (optional)

`migrate_to_supabase.py` loads the old JSON-file data in `backend/data/` into
whichever project `DATABASE_URL` points at — handy for filling a dev project.
It needs the owner's `users.id`, so sign in once as above first, then look it
up:

```sql
select id from users where email = 'you@example.com';
```

With the same env vars exported locally, from the repo root:

```sh
.venv/bin/python backend/migrate_to_supabase.py --owner-user-id <id>
```

This uploads `backend/data/uploads/*` to Storage and loads all topics, entries,
and posts into Postgres under that user.

## MCP server (optional)

Lets MCP clients (claude.ai, ChatGPT, Cursor, Claude Code, …) read entries and
add/edit them. Code in `mcp_server/`, served by `api/mcp_endpoint.py`. For
connecting apps, troubleshooting, and reusing this in another project, see
`MCP.md`.

Generate two secrets:

```sh
.venv/bin/python -c "import secrets; print(secrets.token_hex(32))"   # MCP_TOKEN_SECRET
.venv/bin/python -c "import secrets; print(secrets.token_hex(32))"   # MCP_SERVICE_TOKEN
```

Add to Vercel (Production and Preview):

| Var | Value |
|-----|-------|
| `APP_BASE_URL` | Public origin, e.g. `https://yourdomain` (no trailing slash) |
| `MCP_TOKEN_SECRET` | from above; signs OAuth clients and tokens |
| `MCP_SERVICE_TOKEN` | from above; identifies the MCP function to the API — it also needs `X-Acting-User` to say which signed-in user it's acting for |

Redeploy.

Connect a client with the URL `https://yourdomain/mcp`. The client opens a
Small Wins page showing where you'll be sent afterwards. Check that it's the
app you just came from, sign in with Google if asked, and click **Allow**.

**Kill switch:** replace `MCP_TOKEN_SECRET` and redeploy. Every connected
client is logged out. There's no per-client revoke (tokens aren't stored).
Access tokens last 1 hour; clients refresh silently for up to 30 days.

Local run (Flask on :5000, MCP on :8000). Put the same `MCP_SERVICE_TOKEN` in
`backend/.env` so Flask accepts the MCP server's calls. Sign in on
`http://localhost:5173` first: cookies are per host, not per port, so the
consent page on :8000 sees that session.

```sh
APP_BASE_URL=http://localhost:8000 SMALL_WINS_API_URL=http://localhost:5000 \
MCP_TOKEN_SECRET=dev-token-secret MCP_SERVICE_TOKEN=dev-service-token \
.venv/bin/python -m uvicorn --app-dir api mcp_endpoint:app --port 8000
```

## Signing everyone out

Regenerate `SECRET_KEY`, update it in Vercel, redeploy. Every browser session
ends. To also disconnect MCP apps, rotate `MCP_TOKEN_SECRET`.

## Inviting someone

Add their Google email to `ALLOWED_EMAILS` (and, while the consent screen is in
Testing, to its **Test users**), redeploy. Each new user starts with a default
"Runs" topic and sees only their own data.

- Uploaded images are readable by anyone who has the URL (public bucket) until
  Phase 3.
- Removing someone from `ALLOWED_EMAILS` doesn't end their existing session
  (cookies last up to 30 days) or MCP connection — they keep working, still
  scoped to only their own data. Rotate `SECRET_KEY` / `MCP_TOKEN_SECRET` to cut
  them off immediately.

## Local development

Local dev uses its own Supabase project, so your laptop never holds
production's keys or touches its data.

1. Create a second Supabase project (e.g. `small-wins-dev`) and do steps 2–3 of
   [Supabase setup](#1-supabase-setup-once) on it.
2. Copy `backend/.env.example` to `backend/.env`:
   - `DATABASE_URL` — the dev project's **Session pooler** string (port 5432)
   - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` — the dev project's
   - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — same OAuth client as
     production
   - `SECRET_KEY` — a new one, not production's
   - `ALLOWED_EMAILS` — your Google email
3. Add `http://localhost:5173/api/auth/google/callback` to the OAuth client's
   authorized redirect URIs.
4. Run Flask (`.venv/bin/python backend/app.py`, port 5000) and Vite (`npm run
   dev` in `frontend/`), then open **http://localhost:5173** — not :5000, which
   is the API only. Restart Flask after editing `.env`.

Tests use a third, throwaway database: `TEST_DATABASE_URL` pointing at a local
Postgres (e.g. Docker). The test setup drops every table, so it refuses to run
against a Supabase URL.

## Database migrations

`backend/schema.sql` is the current schema; a new project only needs that.
`backend/migrations/` holds one-off upgrades for existing databases:

- `002_user_scoping.sql` — Phase 2, adds `user_id` to topics/entries/posts.
  Applied to production 2026-10-14. Its header has the run steps.

For any future migration: back up first, run it in the SQL Editor right before
the matching deploy (old code breaks against a new schema and vice versa), and
deploy the whole branch at once.
