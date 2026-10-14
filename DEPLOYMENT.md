# Deploying Small Wins (Vercel + Supabase)

The frontend and Flask API deploy together as one Vercel project; data lives in
Supabase (Postgres + Storage). Do the one-time setup once, then deploys are
`git push` (or `vercel --prod`).

## 1. Supabase setup (once)

1. Create a Supabase project (a second, separate project for local dev is
   recommended).
2. **SQL Editor** → run the contents of `backend/schema.sql`. (This now includes
   the users table. On an existing project, run just the `create table users
   (...)` statement.)
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

Never commit these or expose the service key to the frontend. Never set
`DEV_LOGIN_EMAIL` on Vercel — the app refuses to start if you do.

## 4. Deploy

```sh
vercel --prod
```

Verify: `curl -s -o /dev/null -w "%{http_code}\n" https://yourdomain/api/topics`
→ `401`. Open the site → you land on the sign-in page → **Sign in with Google**
→ your topics. A Google account not in `ALLOWED_EMAILS` sees "isn't invited".

## 5. Migrate existing data (once, fresh installs only)

`migrate_to_supabase.py` needs the owner's `users.id`, so sign in once as
above first, then look it up:

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
Testing, to its **Test users**), redeploy.

## Notes

- Local dev: set `DEV_LOGIN_EMAIL=you@example.com` in `backend/.env` and
  "Sign in with Google" signs you in as that email without contacting Google.

## Per-user data (Phase 2) — one-time upgrade

The Phase 2 code expects every topic/entry/post to have a `user_id`. Run the
migration **before** deploying it, then deploy right away — see
`backend/migrations/002_user_scoping.sql` for exact run instructions.

**Rollback:** prefer `backend/migrations/002_user_scoping_down.sql` — it
reverses the migration, but refuses once more than one user has data, so it's
only valid before any friend has used the app. Redeploy the pre-Phase-2 code
right after running it. Once friends have data, restoring a backup is the
fallback. If Supabase backups aren't available on your plan, take a quick
snapshot of the three tables first, e.g. `create table topics_pre2 as table
topics;` (and the same for `entries`, `posts`), or a Table Editor export.

1. Supabase → Database → Backups: confirm a recent backup exists, or take the
   snapshot above if not.
2. Make sure you have signed in to the live app at least once with your Google
   account (the migration looks your `users` row up by email).
3. Optional: confirm production's constraint names match what the migration
   drops —
   ```sql
   select conrelid::regclass, conname from pg_constraint
   where conrelid in ('topics'::regclass, 'entries'::regclass, 'posts'::regclass)
   order by 1, 2;
   ```
   Expect `topics_pkey`, `entries_pkey`, `entries_topic_slug_fkey`,
   `posts_pkey`, `posts_topic_slug_entry_id_fkey`. If they differ, stop —
   nothing has changed yet.
4. Any local/dev database with existing data needs this migration too (or
   just recreate it from `backend/schema.sql`) — otherwise local Flask fails
   against the old schema.
5. Supabase → SQL Editor → run `backend/migrations/002_user_scoping.sql`. Its
   header has the exact steps (what to replace, how to read success vs.
   failure). If Vercel auto-deploys the production branch on push/merge, run
   the migration right before merging, or have it queued up and run it the
   moment the deploy goes live — the new code fails even on reads until the
   migration has run.
6. Deploy the Phase 2 code immediately. The currently deployed code fails
   against the new keys and the new code fails against the old keys, so
   expect errors in the gap between migration and deploy. Deploy the whole
   branch together — from the first Phase 2 commit, Flask refuses the MCP
   service token unless the MCP server sends `X-Acting-User`, which only the
   later commits add, so a partial deploy breaks Claude's connection. If
   Preview deployments share the production `DATABASE_URL`, older preview
   builds will also break once the migration runs.
7. Check: your topics show up on the web; in Claude, `list_topics` works (if
   it says to reconnect, disconnect and reconnect Small Wins).
8. Only now add friends to `ALLOWED_EMAILS`. Each new user starts with a
   default "Runs" topic and sees only their own data. Note: uploaded images
   are still readable by anyone who has the URL until Phase 3. Removing
   someone from `ALLOWED_EMAILS` doesn't end their existing session (cookies
   last up to 30 days) or MCP connection — they just keep working, still
   scoped to only their own data.
