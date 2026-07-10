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

The frontend and backend are served independently. `npm run build` compiles
the frontend to `frontend/dist/`, which any static host can serve; point it at
the backend by proxying `/api` to the Flask app (or set an API base URL).

```sh
cd frontend && npm run build
npm run preview              # locally preview the built frontend
```

## Admin access

Anyone can view the site; changing anything requires the admin session.
The backend reads two environment variables:

- `ADMIN_PASSWORD_HASH` — hash of the admin password. Generate it with:

  ```sh
  python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash(input('Password: ')))"
  ```

  (If Python complains about missing `scrypt` — e.g. macOS system
  Python 3.9 — add `, method='pbkdf2'` to the
  `generate_password_hash` call; the resulting hash works the same.)

- `SECRET_KEY` — a long random string used to sign the session cookie
  (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`).

Set both wherever the Flask app runs in production. Log in at `/login`
(the page is not linked anywhere); the session lasts 30 days per browser.

In production, run the backend with a real WSGI server (e.g. gunicorn)
rather than `python app.py`, and set `TRUST_PROXY=1` if it sits behind a
reverse proxy so the login rate limit sees real client IPs.

**If neither variable is set (local dev), every request is treated as
admin** — no login needed while developing. Never deploy without
`ADMIN_PASSWORD_HASH`, or the site is world-writable.
