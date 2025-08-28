Agent Mojo — Frontend
=====================

Dev quickstart
--------------

Prereqs: Node 18+.

1. Install deps: `npm install`
2. Run dev server: `npm run dev`
3. Backend proxy: Vite proxies `/api` to `http://localhost:8000` (see `vite.config.ts`).

Structure
---------

- `src/App.tsx` — landing with 1P/2P panels.
- `src/pages/P1Run.tsx` — 1P run UI with SSE log.
- `src/pages/P2Interactive.tsx` — 2P chat UI using WebSocket.
- `src/lib/*` — `api`, `stream` (SSE), `ws` (WebSocket), `types`.
- `src/routes.tsx` — router wiring for `/`, `/p1`, `/p2`.
- Tailwind config and theme in `tailwind.config.js`, base styles in `src/styles/index.css`.

Endpoints expected
------------------

- `POST /api/p1/run` → `{ run_id }`
- `GET /api/p1/stream/{run_id}` → SSE of `RunEvent`
- `POST /api/p2/session` → `{ session_id }`
- `GET /api/p2/ws/{session_id}` → WebSocket
- `POST /api/upload` → `{ zip_token }` (optional)

