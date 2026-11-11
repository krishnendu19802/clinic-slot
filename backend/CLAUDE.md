# backend
Django 6 + DRF, Poetry, PostgreSQL, Redis, Celery. Owns business rules, DB, jobs, Razorpay and SMS integrations. Rules: root `CLAUDE.md`. Why things are the way they are: `docs/decisions.md`. How a request flows: `docs/flow.md`.

## Daily commands
| What | Command |
|---|---|
| Activate the venv (alias, in `~/.bashrc`) | `csenv` (= `source backend/.venv/bin/activate`) |
| Install deps | `cd backend && poetry install` |
| Run API | `python manage.py runserver` |
| Migrate | `python manage.py migrate` |
| Create an admin (Django admin login is email + password) | `python manage.py createsuperuser` |
| Tests (cache-only ones run without services) | `pytest` |
| Lint | `ruff check .` |
| Worker / beat | `celery -A config worker -l info` / `celery -A config beat -l info` |

Needs Postgres 16 and Redis running locally; copy `.env.example` to `.env`. Dev OTP is always `123456` (`OTP_DEV_FIXED`). API docs at `/api/docs/`.

## Layout
`config/` settings, urls, celery · `apps/core` errors, pagination, permissions, platform settings, audit · `apps/accounts` users, OTP, JWT · `apps/doctors` profile, documents · `apps/scheduling` clinics, schedule, slots · `apps/bookings` booking rules · `apps/payments` Razorpay orders, payments, refunds, webhooks · `apps/notifications` outbox + SMS.
Pattern: ViewSet (default actions only) -> serializer -> service class -> repo class (`repo/psql`, `repo/redis`) -> DB. Enums in each app's `enums.py`.
