# Decisions and learnings

Newest at the bottom of each section. Format: what we chose, why, and what it costs.

## Architecture (backend)

| # | Decision | Why / trade-off |
|---|---|---|
| A1 | **Revised after review.** Layers: **ViewSet** (HTTP only) -> **serializer** (input validation, output shape) -> **service class** (business rules, owns the transaction) -> **repository class** (all ORM and cache calls) -> DB/Redis. Repos live at `apps/<app>/repo/<backend>/<name>_repo.py` (`repo/psql/user_repo.py`, `repo/redis/otp_repo.py`). Services take their repos by constructor argument, defaulting to the real ones. | My first proposal was services plus selectors with no repository classes, because a repo over the ORM mostly wraps `QuerySet`. The project owner prefers the explicit layer: services never import models or touch the cache, so unit tests can inject fakes and a backend can be swapped. Cost: more files. Rule to keep it cheap: a repo method is one query intent, no business rules. |
| A2 | Viewsets and one router (`config/api.py`). **Only default actions** (`list`, `retrieve`, `create`, `partial_update`, `destroy`); no `@action`. Verbs that are not CRUD are modelled as a resource you `create`: `POST /auth/otp/request` is `create` on an OTP-request viewset registered at that URL. `/me` is a viewset mapped with `as_view({...})` because a router would add a `{pk}`. | URLs stay exactly as in the API contract. Later verbs like pay, cancel and release will be nested create-only viewsets (`POST /bookings/{id}/pay` creates a payment order). |
| A3 | `ATOMIC_REQUESTS` is off. Services open `transaction.atomic` themselves. | Gateway calls (Razorpay, SMS) must never run inside a DB transaction holding a slot lock. |
| A4 | One error envelope. Services raise `ApiError(code, **details)`. The DRF exception handler maps everything to `{error:{code,message,fields,details}}`, translating DRF codes to the contract (`NotAuthenticated` -> `TOKEN_INVALID`, `Throttled` -> `THROTTLED` + `retry_after_seconds`). | The frontend branches on `code`, so codes must be stable and come from one place. |
| A5 | Business tunables (hold minutes, cutoff, refund window) live in `core.platform` with the defaults in code and an optional `PlatformSetting` row. | A fresh DB works with zero seed data, and admin can still override per key. |

| A7 | **Keyword arguments.** Repo and service methods with parameters are keyword-only (`def f(self, *, x, y)`) and every call site passes `x=x, y=y`. | Call sites read like sentences, and swapping two same-typed arguments (two ids, two strings) becomes a TypeError instead of a silent bug. |
| A6 | Enums live in `apps/<app>/enums.py`; models and services import from there. Constant groups tied to an enum (`OCCUPYING`, `ACTIVE` booking statuses) sit beside it. | One place to look, and services can use enums without importing models. |

## Stack and environment

| # | Decision | Why / trade-off |
|---|---|---|
| E1 | Poetry installed into its own venv (`~/.local/share/poetry-venv`, linked at `~/.local/bin/poetry`). The project venv is **in-project** (`backend/.venv`, `poetry.toml`). | The machine has no `pip` or `pipx`. In-project venv makes the activate alias a fixed path. |
| E2 | Dropped `django-redis`; Django's built-in `RedisCache` is enough for OTP keys and throttles. | One less dependency. |
| E3 | Settings are a single `config/settings.py` driven by env vars (`django-environ`), plus `config/test_settings.py` which swaps Redis for in-memory cache. | A `conftest.py` that set env vars ran too late (pytest-django loads settings first). A settings module is explicit. |
| E4 | Postgres and Redis could not be installed here: no root, and downloading a user-space binary (micromamba) was denied. They need `sudo apt install postgresql redis-server`. | **Consequence:** migrations are generated but **not yet applied**, and DB-level constraints are untested against a real Postgres. Only cache-only tests have run. **Update:** resolved. Postgres 16 and Redis installed (after `apt update`), role and DB created by the owner, migrations applied, DB tests run. |

## Data model

| # | Decision | Why / trade-off |
|---|---|---|
| D1 | `User.USERNAME_FIELD = email` (unique, nullable); `phone` is unique and nullable. A `CHECK` requires phone and role unless `is_staff`. | The Django admin logs in by email and staff have no phone. Patients and doctors have a phone and never an email unless they add one. |
| D2 | Django's own `last_login` is used. The design doc said `last_login_at`. | No point fighting `AbstractBaseUser`. |
| D3 | **No exclusion constraint** for overlapping weekly windows. Postgres has no built-in `timerange`, so the window overlap check goes in the scheduling service. | The design doc assumed a `btree_gist` exclusion constraint; that only works with a custom range type. Service validation plus tests is the cheaper route at this scale. Slots still have `UNIQUE(clinic, start_ts)`. |
| D4 | A `DoctorProfile` row is created at a doctor's first OTP verify, with every field optional while `draft`. Completeness is checked at submit. | Guarantees `user.doctor` is never null for a doctor (the contract needs it) and makes "Save draft" a plain partial update. |
| D5 | `profile_complete`: patients = a name is set; doctors = left `draft`. | The FE only needs a routing hint. |
| D6 | `Booking.ref` (`CS-000123`) is a property derived from the id, not a column. | Nothing to keep in sync. |
| D7 | Documents use a `FileField` in a private `MEDIA_ROOT` that is never mapped to a URL. Access goes through authenticated views. | Matches "encrypted/private storage, signed access". Swap to S3 later via storage settings. |

## Auth

| # | Decision | Why / trade-off |
|---|---|---|
| U1 | OTP is stored as an HMAC of `phone:code`, never plaintext, in Redis with a TTL. A separate counter key caps attempts. Dev mode (`OTP_DEV_FIXED`) just changes the generated code to `123456`, so the verify path is identical in dev and prod. | No special-case branch to forget in production. |
| U2 | The role mismatch (one phone, one role) is checked at both OTP request and verify. | Request-time check gives the user the error before an SMS is sent. Verify-time check closes the race. |
| U3 | Refresh and logout read the refresh token from the httpOnly cookie and require `X-Requested-With: fetch`. | CSRF guard on cookie-only endpoints, in addition to `SameSite=Strict`. |

## Learnings and challenges

| # | What happened | Takeaway |
|---|---|---|
| L1 | `apt install` failed with 404s. | The package index was stale; `sudo apt update` first. |
| L2 | A 9-byte `SECRET_KEY` made PyJWT warn (`InsecureKeyLengthWarning`) because SimpleJWT signs with it (HS256). | Dev and example secrets must be 32+ bytes. Production must set a real one. |
| L3 | The DB constraint tests (second occupying booking, phone/role check) pass against real Postgres, including for each of the five occupying statuses, while `cancelled` and `expired` free the slot. | The double-booking guarantee holds at the DB level with no service code involved. |
| L4 | Refresh-token rotation is verified end to end: the rotated-out token is rejected on replay, and a logged-out token cannot refresh. | The blacklist tables from SimpleJWT work as wired. |
| L5 | DRF's `ModelSerializer` auto-adds a `UniqueTogetherValidator` for a `UniqueConstraint`, which made `council_id` and `registration_no` required on every partial PATCH, breaking "Save draft". Fix: `validators = []` on the serializer, duplicate check in `ProfileService`, DB constraint kept as the backstop. | When a serializer behaves oddly on partial updates, look at validators generated from model constraints first. |
| L6 | Registry simulation takes an injectable `rng`, so tests force a pass and a fail instead of relying on the 80% randomness. | Randomness in a service gets a seam. |
| L7 | Reference data (councils, specialities) is seeded by a data migration, so every environment, including the test DB, has it. | No fixtures or management commands to forget. |

## Scheduling and slots

| # | Decision | Why / trade-off |
|---|---|---|
| S1 | Slot generation **reconciles** instead of regenerating: it compares desired slots (from windows + exceptions) with the existing future slots and only creates, renumbers or deletes the difference. It runs on every schedule/exception change and nightly (Celery). | Idempotent (a second run creates nothing), cheap, and safe to run any time. |
| S2 | A slot with an active booking is **never deleted, moved or overlapped**. It is kept and reported as a conflict (`window_removed` or `day_blocked`). New slots that would overlap a kept one are skipped (a slot-length change leaves a gap rather than a double booking). | Rule S6 of the PRD: a schedule change must not silently cancel bookings. |
| S3 | Slots exist only for **approved** doctors. Before approval the schedule is saved but nothing is generated; approval (Django admin action, later) calls the same generator. | Unverified doctors must never show up anywhere public. |
| S4 | Schedule saves, exceptions and the nightly job hold a `SELECT ... FOR UPDATE` on the clinic row. Deleting slots re-locks them and re-checks for bookings that raced in. | A hold placed during a schedule save can never hit an FK error or lose its slot. |
| S5 | A partial block (exception with a window) skips those slots but they still count in `seq` and `token`. | Numbers stay stable for the patients and the doctor. |
| S6 | Unblocking is `DELETE /doctor/slots/{id}/block`; blocking is `POST` on the same resource. | Default viewset actions only (A2); contract updated. |
| S7 | Windows are normalised in the service: slot length comes from minutes, or from count (must divide evenly), or the platform default; windows that do not divide are rejected, never truncated. Overlaps on the same weekday are rejected (D3). | A doctor never gets a silent half-slot. |
