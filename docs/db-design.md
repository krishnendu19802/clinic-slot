# DB design (PostgreSQL 16, Django ORM)

## Conventions

| Topic | Rule |
|---|---|
| Primary keys | `bigint` identity. Authorisation is checked on every object access, so sequential ids are not an enumeration risk. |
| Money | Integer **paise** (`*_paise`). Currency is INR. |
| Time | `timestamptz`, stored in UTC, shown in IST (clinic time zone). `date` and `time` columns on clinic tables are clinic-local. |
| Enums | `text` + `CHECK` (Django `TextChoices`). |
| Audit columns | Every table has `created_at`. Mutable tables also have `updated_at`. |
| Booking ref | `CS-` + booking id zero-padded to 6 digits. Derived, not stored. |
| Admin | **Not an app role.** Staff use the Django admin. See [Admin](#admin-django-admin). |

## Table overview

| Group | Tables |
|---|---|
| Identity | `users`, `patient_profile`, `doctor_profile`, `council`, `speciality`, `doctor_speciality`, `doctor_document` |
| Clinic and schedule | `clinic`, `schedule_template`, `schedule_exception`, `slot` |
| Booking and payments | `booking`, `payment_order`, `payment`, `refund`, `webhook_event`, `reconciliation_issue` |
| Cross-cutting | `notification`, `platform_setting`, `audit_log` |
| Library tables | `token_blacklist_*` (SimpleJWT), Celery beat schedule, Django auth and admin tables |

## Relationships

| From | To | Cardinality | Note |
|---|---|---|---|
| `users` | `patient_profile` | 1 : 0..1 | role = patient |
| `users` | `doctor_profile` | 1 : 0..1 | role = doctor |
| `doctor_profile` | `speciality` | M : N | via `doctor_speciality` |
| `doctor_profile` | `doctor_document` | 1 : N | one current row per type |
| `doctor_profile` | `clinic` | 1 : N | MVP UI uses one, schema allows many |
| `clinic` | `schedule_template`, `schedule_exception`, `slot` | 1 : N | |
| `slot` | `booking` | 1 : 0..1 active | enforced by a partial unique index |
| `users` (patient) | `booking` | 1 : N | |
| `booking` | `payment_order` | 1 : N | one order per attempt |
| `payment_order` | `payment` | 1 : N | several attempts per Razorpay order |
| `payment` | `refund` | 1 : N | partial refunds allowed |

## Identity

### `users`
Auth core only. Patients and doctors sign in by OTP (JWT). Staff sign in to the Django admin with email and password and cannot get a JWT.

| Column | Type | Constraints / notes |
|---|---|---|
| `id` | bigint | PK |
| `phone` | text | `UNIQUE`, **nullable**, E.164. Postgres allows many NULLs, so staff need no phone. |
| `email` | text | nullable. Required for staff (admin login). |
| `role` | text | `patient` \| `doctor`, nullable for staff. One phone = one role. |
| `password` | text | Django hash. Unused for patients and doctors. |
| `is_staff`, `is_superuser` | bool | Admin site access. Set with `createsuperuser`. |
| `is_active` | bool | Checked on every request, so suspension and bans take effect immediately. |
| `last_login` | timestamptz | Django's own field |
| | | `CHECK (is_staff OR (phone IS NOT NULL AND role IS NOT NULL))` |

### `patient_profile`

| Column | Type | Constraints / notes |
|---|---|---|
| `user_id` | bigint | PK, FK `users` |
| `full_name` | text | nullable until first booking |

Booking-time patient details are snapshotted on `booking`. Saved family profiles are P2.

### `doctor_profile`

| Column | Type | Constraints / notes |
|---|---|---|
| `user_id` | bigint | PK, FK `users` |
| `full_name` | text | |
| `gender` | text | `male` \| `female` \| `other` |
| `registration_no` | text | `UNIQUE (council_id, registration_no)` |
| `council_id` | bigint | FK `council` |
| `degrees` | text[] | |
| `experience_years` | int | `>= 0` |
| `fee_paise` | int | `> 0` |
| `languages` | text[] | display names from a fixed list |
| `remarks` | text | public bio |
| `verification_status` | text | `draft` \| `submitted` \| `info_requested` \| `approved` \| `rejected` \| `suspended` |
| `registry_check` | text | `passed` \| `failed` \| NULL. Set at submit by the simulated registry (random, ~80% pass). |
| `status_reason` | text | reason for `info_requested`, `rejected`, `suspended` |
| `submitted_at`, `verified_at` | timestamptz | |

### `council`, `speciality`, `doctor_speciality`

| Table | Columns | Notes |
|---|---|---|
| `council` | `id`, `name` | Seeded list for the onboarding dropdown. |
| `speciality` | `id`, `slug` UNIQUE, `name`, `blurb` | Seeded: general physician, paediatrics, dermatology, gynaecology, dentistry, and more. |
| `doctor_speciality` | `doctor_id`, `speciality_id` | Composite PK. |

### `doctor_document`

| Column | Type | Constraints / notes |
|---|---|---|
| `id` | bigint | PK |
| `doctor_id` | bigint | FK `doctor_profile` |
| `type` | text | `registration` \| `degree` \| `id`. One current row per `(doctor_id, type)` (a new upload replaces it). |
| `file_ref` | text | private storage key, never a public URL |
| `original_name`, `content_type` | text | |
| `size_bytes` | int | `<= 5 MB` |
| `uploaded_at` | timestamptz | |

## Clinic and schedule

### `clinic`

| Column | Type | Constraints / notes |
|---|---|---|
| `id` | bigint | PK |
| `doctor_id` | bigint | FK `doctor_profile` |
| `name`, `address`, `city`, `area`, `pincode`, `phone` | text | |
| `lat`, `lng` | numeric(9,6) | Distance = Haversine in SQL (no PostGIS at this volume) |
| `is_active` | bool | |

### `schedule_template` (weekly recurring windows)

| Column | Type | Constraints / notes |
|---|---|---|
| `id` | bigint | PK |
| `clinic_id` | bigint | FK `clinic` |
| `weekday` | smallint | ISO 1 = Mon … 7 = Sun (same as the API) |
| `start_time`, `end_time` | time | `CHECK (end_time > start_time)`. No overlapping windows per `(clinic_id, weekday)`, checked in the service (see `decisions.md` D3). |
| `slot_minutes` | int | default 12. If the doctor enters a slot *count*, the API converts it (`(end - start) / count`, which must divide evenly). Breaks are simply gaps between windows. |

### `schedule_exception` (date-specific overrides)

| Column | Type | Constraints / notes |
|---|---|---|
| `id` | bigint | PK |
| `clinic_id` | bigint | FK `clinic` |
| `date` | date | clinic-local |
| `type` | text | `blocked` \| `extra` |
| `start_time`, `end_time` | time | NULL on `blocked` = whole day off |
| `slot_minutes` | int | for `extra` windows |

### `slot` (the central object)
Materialised on a rolling 30-day horizon from the templates and exceptions.

| Column | Type | Constraints / notes |
|---|---|---|
| `id` | bigint | PK |
| `clinic_id` | bigint | FK `clinic` |
| `start_ts`, `end_ts` | timestamptz | `UNIQUE (clinic_id, start_ts)` |
| `seq`, `window_total` | int | position within the window ("slot 3 of 5") |
| `token` | int | day-wide ordinal shown to patients. Blocked slots count in `seq`, `window_total` and `token`. Fixed at generation, never renumbered for a slot that has a booking. |
| `status` | text | `available` \| `held` \| `booked` \| `blocked` |
| `held_until` | timestamptz | NULL unless `held` |
| `held_by` | bigint | FK `users`, NULL unless `held` |
| `capacity` | int | default 1 (fixed in MVP) |

"Expired" is derived (`start_ts < now()`), never stored. A slot with `status = 'held' AND held_until < now()` is treated as available everywhere (lazy expiry), so correctness never depends on the sweeper job.

## Booking and payments

### `booking`

| Column | Type | Constraints / notes |
|---|---|---|
| `id` | bigint | PK |
| `slot_id` | bigint | FK `slot` |
| `patient_user_id` | bigint | FK `users` |
| `status` | text | `pending_payment` \| `confirmed` \| `arrived` \| `completed` \| `no_show` \| `cancelled` \| `expired` |
| `patient_name`, `patient_gender`, `patient_phone`, `reason` | text | snapshot of the details entered at booking |
| `patient_age` | smallint | |
| `is_self` | bool | booking for self or a family member |
| `fee_paise` | int | snapshot at hold time |
| `platform_fee_paise` | int | default 0 |
| `hold_expires_at` | timestamptz | NULL once confirmed |
| `reschedule_count` | smallint | default 0, limit from `platform_setting` |
| `cancelled_by` | text | `patient` \| `doctor` \| `system` |
| `cancel_reason`, `cancelled_at` | text, timestamptz | |

**The double-booking guarantee:** unique index on `(slot_id)` where `status IN ('pending_payment','confirmed','arrived','completed','no_show')`. `cancelled` and `expired` release the slot. A reschedule moves `slot_id` on the same booking, with both slots locked in id order. The payment follows the booking, and the move is written to `audit_log`.

### `payment_order` (one Razorpay order per attempt)

| Column | Type | Constraints / notes |
|---|---|---|
| `id` | bigint | PK |
| `booking_id` | bigint | FK `booking` |
| `razorpay_order_id` | text | `UNIQUE` |
| `amount_paise` | int | copied from `booking.fee_paise`, never from the client |
| `currency` | text | `INR` |
| `status` | text | `created` \| `paid` \| `expired` |

### `payment`

| Column | Type | Constraints / notes |
|---|---|---|
| `id` | bigint | PK |
| `order_id` | bigint | FK `payment_order` |
| `razorpay_payment_id` | text | `UNIQUE` |
| `status` | text | `authorized` \| `captured` \| `failed` |
| `amount_paise` | int | |
| `method` | text | upi, card, netbanking, wallet |
| `signature_verified` | bool | |
| `raw` | jsonb | gateway payload |

### `refund`

| Column | Type | Constraints / notes |
|---|---|---|
| `id` | bigint | PK |
| `payment_id`, `booking_id` | bigint | FKs |
| `razorpay_refund_id` | text | `UNIQUE`, nullable until created at the gateway |
| `amount_paise` | int | |
| `reason` | text | `patient_cancel` \| `doctor_cancel` \| `slot_conflict` \| `admin_manual` \| `schedule_change` |
| `status` | text | `pending` \| `processed` \| `failed` |
| `initiated_by` | bigint | FK `users`, NULL for system |

### `webhook_event`

| Column | Type | Constraints / notes |
|---|---|---|
| `id` | bigint | PK |
| `razorpay_event_id` | text | `UNIQUE`. Insert-first gives idempotency. |
| `type` | text | |
| `payload` | jsonb | |
| `processed_at`, `error` | timestamptz, text | NULL until handled |

### `reconciliation_issue`

| Column | Type | Constraints / notes |
|---|---|---|
| `id` | bigint | PK |
| `kind` | text | `paid_no_booking` \| `booking_no_payment` \| `amount_mismatch` \| `refund_stuck` |
| `booking_id`, `payment_id` | bigint | FKs, nullable |
| `detail` | text | |
| `status` | text | `open` \| `resolved` |
| `resolved_by`, `resolved_at` | FK `users`, timestamptz | |

Schedule conflicts are **not a table**. A conflict is an active booking whose slot is blocked, no longer in the template, or whose doctor is suspended, found by query (`GET /doctor/conflicts`).

## Cross-cutting

### `notification` (outbox)

| Column | Type | Constraints / notes |
|---|---|---|
| `id` | bigint | PK |
| `user_id` | bigint | FK `users` |
| `booking_id` | bigint | nullable FK |
| `channel` | text | `sms` \| `whatsapp` \| `email` |
| `template` | text | e.g. `booking_confirmed`, `reminder_24h`, `refund_processed` |
| `payload` | jsonb | |
| `status` | text | `pending` \| `sent` \| `failed` |
| `attempts`, `error` | int, text | |
| `send_at`, `sent_at` | timestamptz | reminders are rows with a future `send_at` |

Confirmation messages are sent synchronously after commit, with a short timeout. A failure stays `pending` or `failed`, and a Celery beat task retries it.

### `platform_setting`

| Key | Default | Meaning |
|---|---|---|
| `hold_minutes` | 8 | slot hold during checkout |
| `payment_grace_minutes` | 2 | extra window to honour a verified payment if the slot is still free |
| `booking_cutoff_minutes` | 30 | cannot book closer to start than this |
| `free_cancel_hours` | 4 | full refund if cancelled at least this long before the slot |
| `late_cancel_refund_percent` | 0 | refund for cancels inside the window |
| `horizon_days` | 30 | slot generation horizon |
| `max_reschedules` | 1 | per booking |
| `default_slot_minutes` | 12 | when a window gives neither minutes nor count (also in `GET /policy`) |

### `audit_log`

| Column | Type | Notes |
|---|---|---|
| `id` | bigint | PK |
| `actor_id` | bigint | FK `users`, NULL for system |
| `action` | text | e.g. `doctor.approve`, `booking.reschedule`, `refund.manual`, `schedule.update` |
| `entity_type`, `entity_id` | text, bigint | |
| `data` | jsonb | before/after, reasons |
| `at` | timestamptz | |

## Indexes and constraints that matter

| Purpose | Definition |
|---|---|
| One slot per clinic and start | `UNIQUE (slot.clinic_id, slot.start_ts)` |
| **No double booking** | partial `UNIQUE (booking.slot_id) WHERE status IN ('pending_payment','confirmed','arrived','completed','no_show')` |
| Fast search of open slots | partial index on `slot (start_ts) WHERE status = 'available'`, plus `(clinic_id, start_ts)` |
| No overlapping weekly windows | service-layer validation (no built-in `timerange`, so no exclusion constraint) |
| Idempotent webhooks | `UNIQUE webhook_event.razorpay_event_id` |
| One gateway id, one row | `UNIQUE` on `razorpay_order_id`, `razorpay_payment_id`, `razorpay_refund_id` |
| Unverified never public | all public queries filter `doctor_profile.verification_status = 'approved'` and `users.is_active` |
| Per-patient lookups | `booking (patient_user_id, status)` |
| Admin search | `users (phone)` unique, `booking (id)`, trigram or `ILIKE` on `patient_name` |

## Critical transactions

| Operation | Steps | Failure |
|---|---|---|
| **Place hold** | 1. `SELECT … FOR UPDATE` on the patient's `users` row. 2. `SELECT … FOR UPDATE` on the `slot`. 3. Require the slot to be `available` or expired-held, and `start_ts > now + cutoff`. 4. Same-doctor older hold: release it. 5. **Overlap check:** none of the patient's other *active bookings* (`pending_payment`, `confirmed`, `arrived`) may overlap `[start_ts, end_ts)`. 6. Set the slot `held`, `held_until = now + hold_minutes`. 7. Insert the booking `pending_payment`. | 409 `SLOT_TAKEN`, `TOO_LATE`, `BOOKING_OVERLAP` |
| **Confirm** (verify endpoint or webhook, both idempotent) | Lock the booking. If `pending_payment`: set `confirmed`, slot `booked`, order `paid`, payment `captured`. If the hold lapsed but the slot is still free for this booking and within the payment grace: confirm anyway. If someone else took it: auto-refund (`slot_conflict`) and notify. | 409 `SLOT_LOST_REFUNDED` |
| **Cancel** | Lock the booking. Compute the refund from the policy. Booking `cancelled`, slot back to `available` (unless blocked). Insert `refund`, then call the Razorpay refund. | Gateway down: refund stays `pending`, retried by beat |
| **Reschedule** | Lock the booking and both slots (id order). Require the same doctor, `reschedule_count < max`, outside the free-cancel window, and **no overlap with the patient's other active bookings**. Move `slot_id`, free the old slot, mark the new one `booked`. | 409 `RESCHEDULE_NOT_ALLOWED`, `SLOT_TAKEN`, `BOOKING_OVERLAP` |
| **Schedule save** | Replace the templates (a window not divisible by the slot length is rejected), regenerate future slots. Slots that hold active bookings are kept and surface as conflicts, and no new slot is generated overlapping a kept one. Nothing is cancelled silently. | |

The overlap rule is per account, so one account cannot book itself and a family member at the same time with different doctors. That limitation is accepted for the MVP.

## Redis

| Key | Value | TTL / limits |
|---|---|---|
| `otp:{phone}` | hash of the OTP + attempt counter | 5 min. Max 5 attempts, then locked until expiry. |
| `otp_send:{phone}` | resend cooldown + sends this hour | 30 s cooldown, 5 sends per hour |
| DRF throttles | per-IP and per-user counters | OTP and booking endpoints |
| Celery | broker | |

Dev mode: the SMS provider is the console, the OTP is logged, and `123456` is always accepted.

## Scheduled tasks (Celery beat)

| Task | Schedule | Does |
|---|---|---|
| `tick` | every minute | releases expired holds, sends due notifications and reminders (24 h, 2 h), retries failed notifications, retries pending refunds |
| `generate_slots` | nightly, and on schedule save or doctor approval | extends the rolling horizon |
| `reconcile` | nightly, and as a Django admin action | matches Razorpay payments to bookings, writes `reconciliation_issue` |

Processes: web, Celery worker, Celery beat (one each), PostgreSQL, Redis.

## Admin (Django admin)

| Need | Django admin implementation |
|---|---|
| Doctor verification queue | `DoctorProfile` list filtered by status. Actions: approve, reject, request info, suspend, unsuspend, each asking for a reason and writing `audit_log`. |
| View documents | Admin-only file view (inline links on the doctor page). |
| Bookings and refunds | `Booking` search by ref, phone, name. A "manual refund" action. |
| Reconciliation | `ReconciliationIssue` list with a resolve action, plus a "run reconcile now" action. |
| Platform settings | `PlatformSetting` editable in the admin (covers the P1 settings screen for free). |

Every action calls the same service functions as the REST API, so the business rules live in one place. There is no custom admin UI and no `/admin` API.
