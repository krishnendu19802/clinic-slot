# frontend
React 18 + TypeScript + Vite 5 SPA, mobile-first, built from the screen designs (link in root `CLAUDE.md`). Talks to the backend only through the contract in `docs/api/contract.md`. Why things are the way they are: `docs/decisions.md` (F-series).

## Commands (run in `frontend/`)
| What | Command |
|---|---|
| Install | `npm install` |
| Dev server (proxies `/api` to Django on :8000) | `npm run dev` then open http://localhost:5173 |
| Type-check + production build | `npm run build` |
| Unit tests (formatting, countdown, API client refresh logic) | `npm test` |
| Browser end-to-end, 30 checks: doctor onboarding -> admin approval -> schedule -> patient booking (needs Postgres, Redis, Chrome; makes and drops its own DB, ~1 min) | `npm run e2e` |

Node 18 here, so tooling is pinned to Vite 5 / React Router 6 / Vitest 2 (newer majors need Node 20).

## Layout
`src/api` client, types, queries · `src/auth` session context + routing by role/status · `src/lib` format helpers + countdown hook · `src/components` layout and shared bits · `src/pages` one file per screen · `e2e/` browser test.

## Rules
- Access token lives in memory only; the refresh token is an httpOnly cookie (never read by JS). One shared refresh on 401, then one retry.
- Money is integer paise; format with `rupees()`. Times arrive as UTC and are shown in IST with `lib/format`.
- Countdowns use the server clock (`server_time` on every booking), never the device clock alone.
- Branch on `error.code`, not on message text.
