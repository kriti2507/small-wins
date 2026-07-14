# Deploying Small Wins (Vercel + Supabase)

The frontend and Flask API deploy together as one Vercel project; data lives in
Supabase (Postgres + Storage). Do the one-time setup once, then deploys are
`git push` (or `vercel --prod`).

## 1. Supabase setup (once)

1. Create a Supabase project (a second, separate project for local dev is
   recommended).
2. **SQL Editor** → run the contents of `backend/schema.sql`.
3. **Storage** → new bucket `uploads`, **Public**.
4. Collect these values:
   - `DATABASE_URL` — **Transaction pooler** string (port 6543) for Vercel.
   - `SUPABASE_URL` — project URL.
   - `SUPABASE_SERVICE_KEY` — the **service_role** key (server-side only).

## 2. Admin auth secrets (once)

The app stores only a hash of your password. Generate both:

```sh
.venv/bin/python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash(input('Password: '), method='pbkdf2'))"
.venv/bin/python -c "import secrets; print(secrets.token_hex(32))"
```

The first line is `ADMIN_PASSWORD_HASH`; the second is `SECRET_KEY`. Save the
password in your password manager — there is no reset flow (losing it costs no
data; just regenerate the hash).

## 3. Vercel environment variables

In the Vercel project → Settings → Environment Variables, set:

| Var | Value |
|-----|-------|
| `DATABASE_URL` | Supabase transaction-pooler string (6543) |
| `SUPABASE_URL` | `https://PROJECT.supabase.co` |
| `SUPABASE_SERVICE_KEY` | service_role key |
| `SUPABASE_BUCKET` | `uploads` |
| `ADMIN_PASSWORD_HASH` | from step 2 |
| `SECRET_KEY` | from step 2 |
| `TRUST_PROXY` | `1` |

Never commit these or expose the service key to the frontend.

## 4. Migrate existing data (once)

With the same env vars exported locally, from the repo root:

```sh
.venv/bin/python backend/migrate_to_supabase.py
```

This uploads `backend/data/uploads/*` to Storage and loads all topics, entries,
and posts into Postgres.

## 5. Deploy

```sh
vercel --prod
```

Verify: `curl -s https://yourdomain/api/auth/me` → `{"is_admin":false}`, then
open `/login`, enter the password, and confirm edit controls unlock. Login only
sticks over HTTPS (the session cookie is `Secure`); Vercel is HTTPS so this is
automatic.

## Changing the password later

Regenerate `ADMIN_PASSWORD_HASH` (step 2), update it in Vercel, redeploy.
Already-logged-in devices stay in for up to 30 days; to force everyone out
(e.g. suspected compromise), also regenerate and replace `SECRET_KEY`.

## Notes

- The login rate-limit is in-memory and best-effort on serverless (it resets on
  cold starts) — acceptable for a single admin.
- Local dev needs `backend/.env` (see `backend/.env.example`); with
  `ADMIN_PASSWORD_HASH` unset, every request is admin.
