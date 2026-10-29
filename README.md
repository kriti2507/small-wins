# Small Wins

Track small wins across the aspects of your life. A React SPA (Vite +
TypeScript) talking to a Flask JSON API over `/api/*`.

## Layout

```
backend/    Flask JSON API + JSON-file storage (API only)
frontend/   Vite + React + TypeScript single-page app
```

The two communicate only over the HTTP `/api/*` contract.

## Development

Run the backend and the Vite dev server in two terminals.

**Backend** (Flask API on :5000):

The backend talks to Supabase (Postgres + Storage). Copy
`backend/.env.example` to `backend/.env` and fill in `DATABASE_URL`,
`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and `SUPABASE_BUCKET` (use a
**separate dev Supabase project** so local work never touches prod data).
Sign-in uses Google locally too: set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
and `SECRET_KEY`, and add the local callback URL to the
OAuth client's authorized redirect URIs.
Optionally set `TYPESAFE_API_KEY` so the Home quick-add bar can guess the
topic and fill in fields from plain text (`backend/quick_add.py`).

```sh
pip install -r backend/requirements.txt
python backend/app.py
```

`:5000` serves only `/api/*` — it has no UI. Open the app at the Vite URL below.

**Frontend** (Vite dev server on :5173, hot reload):

```sh
cd frontend
npm install
npm run dev
```

Vite proxies `/api` to `http://localhost:5000`, so the browser sees a single
origin (no CORS). Open http://localhost:5173.

## Tests

Unit tests cover the pure logic in `frontend/src/lib/` (pace, scoring, dates,
palette):

```sh
cd frontend
npm test
```

## Production build

The app deploys to Vercel as one project: the Vite build is served as static
assets and the Flask API runs as a Python serverless function (`api/index.py`,
routed via `vercel.json`). Data lives in Supabase (Postgres + Storage). See
`DEPLOYMENT.md` for the full deploy + env setup.

```sh
cd frontend && npm run build
npm run preview              # locally preview the built frontend
```

## Sign-in

Everything is private: every page and API route needs a signed-in user.
Sign-in is Google only, open to any account with a verified email; each user
sees only their own data, within per-user caps (see `DEPLOYMENT.md`, "Who can
sign in"). Production needs `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and
`SECRET_KEY` (signs the 30-day session cookie); see `DEPLOYMENT.md` step 2.
Behind a reverse proxy, set `TRUST_PROXY=1` so the Google callback URL is built
with `https`.
