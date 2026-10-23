# Deploying Small Wins (Vercel + Supabase)

The frontend and Flask API deploy together as one Vercel project; data lives in
Supabase (Postgres + Storage). Do the one-time setup once, then deploys are
`git push` (or `vercel --prod`).

## 1. Supabase setup (once)

1. Create a Supabase project. Use a second, separate project for local dev —
   see [Local development](#local-development).
2. **SQL Editor** → run the contents of `backend/schema.sql` (all tables, with
   RLS on).
3. **Storage** → new bucket `uploads`, **Private** (leave "Public bucket" off).
   Flask signs short-lived read URLs for each user's own images.
4. Collect these values:
   - `DATABASE_URL` — **Transaction pooler** string (port 6543) for Vercel.
   - `SUPABASE_URL` — project URL.
   - `SUPABASE_SERVICE_KEY` — the **service_role** key (server-side only).

## 2. Google sign-in (once)

1. Google Cloud Console → **APIs & Services → OAuth consent screen**: user type
   **External**, app name `Small Wins`, your email as support/developer
   contact. Then **Audience → Publish app** so it's **In production**: in
   Testing, only listed Test users (100 at most) can sign in. The app asks
   only for `openid email profile`, which need no Google review.
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
| `SECRET_KEY` | from step 2 |
| `TRUST_PROXY` | `1` |

Never commit these or expose the service key to the frontend.

## 4. Deploy

```sh
vercel --prod
```

Verify: `curl -s -o /dev/null -w "%{http_code}\n" https://yourdomain/api/topics`
→ `401`. Open the site → you land on the sign-in page → **Sign in with Google**
→ your topics.

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
and posts into Postgres under that user. It still writes old public-bucket
URLs, so afterwards run `backend/migrate_storage_003.py` as in
[Upgrading to private storage](#upgrading-to-private-storage-phase-3-part-a),
or those images won't load from the private bucket.

## MCP server (optional)

Lets MCP clients (claude.ai, ChatGPT, Cursor, Claude Code, …) read entries and
add/edit them. Code in `mcp_server/`, served by `api/mcp_endpoint.py`. For
connecting apps, troubleshooting, and reusing this in another project, see
`MCP.md`.

Generate a secret:

```sh
.venv/bin/python -c "import secrets; print(secrets.token_hex(32))"   # MCP_TOKEN_SECRET
```

Add to Vercel (Production and Preview):

| Var | Value |
|-----|-------|
| `APP_BASE_URL` | Public origin, e.g. `https://yourdomain` (no trailing slash) |
| `MCP_TOKEN_SECRET` | from above; signs OAuth clients and tokens, and encrypts the grant inside them |

Redeploy.

Connect a client with the URL `https://yourdomain/mcp`. The client opens a
Small Wins page showing where you'll be sent afterwards. Check that it's the
app you just came from, sign in with Google if asked, and click **Allow** —
this stores a grant for that connection, so it shows up on the Connected apps
page (`/apps`) and can be revoked there.

**Kill switch:** replace `MCP_TOKEN_SECRET` and redeploy, then run
`delete from mcp_grants;` in the Supabase SQL editor. Every connected client
is logged out, and Connected apps is cleared (rotating alone leaves the dead
connections listed there until each is revoked). To cut off a single client
instead, revoke it on the Connected apps page. Access tokens last 1 hour;
clients refresh silently for up to 30 days.

Local run (Flask on :5000, MCP on :8000). Sign in on `http://localhost:5173`
first: cookies are per host, not per port, so the consent page on :8000 sees
that session.

```sh
APP_BASE_URL=http://localhost:8000 SMALL_WINS_API_URL=http://localhost:5000 \
MCP_TOKEN_SECRET=dev-token-secret \
.venv/bin/python -m uvicorn --app-dir api mcp_endpoint:app --port 8000
```

## Upgrading to private storage (Phase 3, Part A)

Existing deployments created the bucket public with flat keys. To move to
private per-user storage:

1. Deploy. New uploads go to `users/<id>/`; old public URLs keep loading
   because the bucket is still public.
2. From the repo root, with production's `DATABASE_URL`, `SUPABASE_URL` and
   `SUPABASE_SERVICE_KEY` in the environment (Pillow installed via
   `backend/requirements.txt`):
   `.venv/bin/python backend/migrate_storage_003.py --dry-run`, check the
   plan, then run it without `--dry-run`. Keep the dry-run output: it's the
   record for reversing the DB rewrite. Look for `skip`/`warn` lines in the
   output: a missing object is skipped and picked up by a later rerun, and a
   name it won't touch automatically is printed as `skip (unsafe name,
   migrate by hand)` for you to move yourself.
3. Spot-check the app: tiles show thumbnails, entry pages full images. In
   Supabase → Storage → `uploads`, open a newly uploaded image's object and
   confirm its `cache-control` header is `max-age=31536000`.
4. Rerun `migrate_storage_003.py` (it's idempotent) to catch any old URL a
   still-open editor tab saved back after the first run.
5. Supabase → Storage → `uploads` → edit bucket → turn **Public** off.
6. Later, once nothing references the old flat objects:
   `migrate_storage_003.py --delete-old --dry-run` to see what would go, then
   `migrate_storage_003.py --delete-old` to report a count (it still deletes
   nothing), then add `--yes` to actually delete. (`--delete-old` aborts
   instead of guessing if it finds a URL that looks like it serves the
   configured bucket but doesn't match `SUPABASE_URL` — check
   `SUPABASE_URL`/`SUPABASE_BUCKET` and rerun.)

Steps 1–5 are reversible: flip the bucket back to public, and undo the DB
rewrite from the dry-run log. Between steps 1 and 2, deleting an entry with
an old URL leaves its object behind; step 6 cleans it up.

## Upgrading to MCP grants (Phase 3, Part B)

1. Run `backend/migrations/004_mcp_grants.sql` in the Supabase SQL editor.
2. Deploy.
3. Each user reconnects each app once: old tokens carry no grant, so the app
   gets a 401 on its next call and re-runs sign-in.
4. Remove `MCP_SERVICE_TOKEN` from Vercel and redeploy.

Rollback: redeploy the previous build and re-add `MCP_SERVICE_TOKEN`; the
`mcp_grants` table is harmless to leave.

## Signing everyone out

Regenerate `SECRET_KEY`, update it in Vercel, redeploy. Every browser session
ends. To also disconnect MCP apps, use the kill switch above (rotate
`MCP_TOKEN_SECRET` and `delete from mcp_grants;`).

## Who can sign in

Anyone with a Google account whose email Google has verified. Each new user
starts with a default "Runs" topic and sees only their own data. They see and
revoke their own connected MCP apps on the Connected apps page (`/apps`) —
nobody else can.

To stop one account from filling the database or bucket, each user is capped
(constants at the top of `backend/app.py`): 50 topics, 5,000 entries, 2,000
images, 100 KB of field values per entry and 1 MB per post body. Hitting a cap
shows "You've reached the limit of …". The image count lists the user's
storage folder on each upload, so uploads abandoned before saving count too;
deleting entries frees their images.

Users can delete their own account from the account menu ("Delete account"):
that removes their users row (and with it their data and MCP apps), their
images under `users/<id>/`, and signs them out. Signing in again with the same
Google account starts a fresh, empty account.

To remove someone yourself: `delete from users where id = <id>;` in the Supabase SQL
editor deletes their account, data and MCP apps (their session ends on its
next `/api/auth/me`). Their images stay in the bucket under `users/<id>/`
until you delete that folder. Nothing yet stops them signing in again as a
new user.

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
- `004_mcp_grants.sql` — Phase 3 Part B, adds the `mcp_grants` table. See
  "Upgrading to MCP grants" above.
- `006_analytics.sql` — adds `entries.created_at`/`via` and
  `users.signup_source`/`last_seen_at`. Only adds columns, so it's safe to
  run any time before the analytics deploy (the live code ignores them) and
  never needs undoing if the code is rolled back. Then deploy. The queries
  are in `backend/analytics.sql`.

For any future migration: back up first, run it in the SQL Editor right before
the matching deploy (old code breaks against a new schema and vice versa), and
deploy the whole branch at once.
