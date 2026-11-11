# ClinicSlot

Local doctor discovery + paid appointment slot booking. Demo project (Razorpay test mode, simulated doctor verification, no payouts). Launch city: Durgapur. English only. Mobile-first responsive web, no native app.

## Links (private claude.ai artifacts)
- PRD (Claude Doc): https://claude.ai/code/artifact/7dfc2a5a-01eb-4947-851e-f9bbf557f482 — local snapshot: `docs/PRD.md` (v0.2, 19 Oct 2026; Claude's own text export, so tables are flattened)
- Screens (Design canvas, 12 artboards): https://claude.ai/artifact/UFDUeXJ8sRbDVbXsUECvgQ

## Stack (decided)
Django + DRF + Poetry · PostgreSQL 16 · JWT (SimpleJWT: 15 min access in memory, rotating refresh in httpOnly cookie) · Redis (OTP + throttling only) · React + TypeScript + Vite (SPA) · Razorpay test mode. Celery + beat (Redis broker) for periodic jobs; OTP/confirmation sends stay synchronous, backed by a notification outbox table. Admin = Django admin (not an app role; staff users have no JWT). No PostGIS: Haversine on plain lat/lng. Design docs: `docs/db-design.md`, `docs/api/contract.md`.

## Dev shortcuts
- `csenv` activates the backend virtualenv (alias in `~/.bashrc`; if missing: `alias csenv='source /home/krishnendu/Desktop/Codes/clinic-slot/backend/.venv/bin/activate'`). More commands in `backend/CLAUDE.md`.
- Living docs while coding: `docs/decisions.md` (choices, learnings, challenges) and `docs/flow.md` (flow between layers). Update both whenever behaviour or structure changes.

## Layout
- `backend/` — API, DB schema/migrations, jobs, payment/notification integrations. Role: owns all business rules.
- `frontend/` — web app. Role: presentation only; amount, slot state and eligibility are never trusted from the client.
- `docs/` — PRD snapshot, DB design, API contract (`docs/api/`), added as we go.

## Decisions fixed by the PRD (section 15)
Full fee paid online at booking · no guest booking (OTP account required) · 1 patient per slot in MVP · individual doctors only · all specialities · registry check is a fake site, ~80% random pass · payouts post-MVP · refund gateway-fee policy is dummy.

## Non-negotiable rules
- Per patient account: one live hold per doctor; active bookings (held or confirmed) must never overlap in time. This also stops booking yourself and a family member at the same time.
- One slot, one confirmed booking: enforced by DB constraints, not UI.
- Hold 8 min (configurable), cutoff 30 min before start, all times UTC, shown in IST.
- Amount computed server-side. Booking confirmed only via verified signature or webhook; webhooks idempotent.
- Unverified doctors never appear in search or public URLs.
- Schedule changes never silently cancel bookings; conflicts are flagged.
- Cancel >=4h before: refund; <4h: none/partial (configurable); doctor cancels: full refund; no-show: none.

## Screens (artboard -> purpose)
Patient: Home/search, Login (OTP, Patient/Doctor toggle), Search results (filters + sort), Doctor profile + slot calendar, Patient details (self/family, 8-min hold countdown), Payment (Razorpay placeholder), Booking confirmed (token, booking ID CS-xxxxxx, directions, calendar, reschedule/cancel), My bookings (Upcoming/Past/Cancelled).
Doctor: Onboarding (profile + 3 documents, submit/draft), Clinic and schedule (weekly windows, slot preview, block day/slot), Dashboard (today's slots, arrived/completed/no-show, earnings).
Admin: design exists (verification queue, refunds, reconciliation, suspend) but is replaced by Django admin; not built in React.

## Workflow
Step-by-step with the sole developer: design (DB + API) -> FE subagent validates contract against screens -> build BE -> build FE. Small incremental commits, push at checkpoints. Commit/push only when asked.

## Status
- [x] PRD + screens read, repo scaffolded
- [x] Stack decision
- [x] DB design + API contract drafted (v1.2)
- [x] FE-subagent validation of contract vs screens (two passes, v1.2)
- [x] BE step 1: project, settings, all models + migrations (generated, not applied), OTP + JWT auth
- [x] Postgres + Redis installed, migrations applied, 18 tests pass (OTP, auth API, DB constraints)
- [ ] BE next: doctors/schedule/slots, booking + payments services, notifications, Django admin
- [ ] FE
