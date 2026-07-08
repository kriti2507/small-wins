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
