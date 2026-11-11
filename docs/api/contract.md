# API contract v1.2

Base `/api/v1`. JSON. Later, `drf-spectacular` generates OpenAPI from the code and that becomes the source of truth. This file is the design-time contract, validated against all 12 screens by an FE-developer pass (v1 -> v1.1 -> v1.2, two passes).

## Conventions
- Money: integer paise (`fee_paise`). Times: ISO-8601 UTC. `date` and `HH:MM` fields are clinic-local (IST). The FE does all labelling ("Today", "Evening").
- Enums: `gender = male|female|other`. `languages` = display names from a fixed list (`English, Bengali, Hindi`). `registry_check = passed|failed|null` (null = not run yet).
- Auth: `Authorization: Bearer <access>` (JWT, 15 min, kept in memory by the FE). The refresh token is a rotating httpOnly cookie, `SameSite=Strict`, `Path=/api/v1/auth`. Refresh and logout also require the header `X-Requested-With: fetch` (CSRF guard). The FE serialises concurrent refreshes, and a 401 is retried once after refresh. 401 codes: `TOKEN_EXPIRED` (refresh then retry) and `TOKEN_INVALID` (log out). Wrong role: 403 `ROLE_FORBIDDEN`.
- Errors: `{"error":{"code","message","fields":{"name":["required"]},"details":{}}}`. `details` carries code-specific extras (see the error table). 400 validation, 401, 403, 404, 409 conflict, 429 throttled (`details.retry_after_seconds`).
- Lists: unbounded lists (`GET /doctors`, `GET /bookings`) are paginated `{items, page, page_size, total}`. Small bounded lists (specialities, councils, clinics, documents, conflicts, active holds, doctor slot lists) are `{items:[...]}` with no pagination fields. The public slot grid is `{days:[...]}`.
- Enums: `weekday` is ISO 1 (Mon) to 7 (Sun). `cancelled_by = patient|doctor|system`. `refund.status = pending|processed|failed`. `verification_status = draft|submitted|info_requested|approved|rejected|suspended`.
- Roles: `[P]` public, `[A]` any authenticated, `[PT]` patient, `[D]` doctor. Admin is not an API role: it is the Django admin site.
- Every `Booking` carries `server_time` so the FE computes `offset = server_time - Date.now()` for countdowns.

## Auth
| | |
|---|---|
| `POST /auth/otp/request` [P] | `{phone, role: patient|doctor}` -> 200 `{retry_after_seconds: 30}`. 429 includes `details.retry_after_seconds`. A new phone creates the account at verify (a doctor starts in `draft`). 409 `ROLE_MISMATCH` if the phone belongs to another role. |
| `POST /auth/otp/verify` [P] | `{phone, otp, role}` -> `{access, user}` and sets the refresh cookie. `user = {id, role, phone, name, profile_complete, doctor:{id, verification_status, status_reason}\|null}`. `doctor` is non-null for every doctor, and null for patients. **Doctor routing by status:** `draft`, `info_requested`, `rejected` -> editable Onboarding; `submitted` -> read-only Onboarding; `approved` -> Dashboard; `suspended` -> Dashboard with a banner. 400 `OTP_INVALID` / `OTP_EXPIRED`, 429 `OTP_LOCKED`. |
| `POST /auth/refresh` [P] | cookie -> `{access}`, rotates the refresh token. 401 if it is missing or invalid (the FE treats this as anonymous at boot). |
| `POST /auth/logout` [A] | 204, blacklists the refresh token |
| `GET /me` [A] | same `user` object plus `email`. Patient prefill uses `name` and `phone` only. |
| `PATCH /me` [A] | `{name?, email?}`. Email is optional and used only for notifications. |

## Public discovery
| | |
|---|---|
| `GET /policy` [P] | `{hold_minutes, cutoff_minutes, free_cancel_hours, late_cancel_refund_percent, default_slot_minutes, text}` |
| `GET /specialities` [P] | `{items:[{id, slug, name, blurb}]}` |
| `GET /councils` [P] | `{items:[{id, name}]}` for the onboarding dropdown (static seed list) |
| `GET /doctors` [P] | Query: `speciality` (slug), `city`, `area`, `pincode`, `lat`, `lng`, `date`, `available_today`, `fee_max`, `experience_min`, `gender`, `language`, `sort=earliest\|distance\|experience\|fee`, `page`. Only approved, unsuspended doctors with at least one future available slot. **One item per clinic** (a doctor with 2 clinics appears twice). Item: `{doctor:{id, name, degrees, experience_years, fee_paise, languages, verified:true}, clinic:{id, name, address, area, city, distance_km\|null}, availability:{date, day_state: open\|full\|off, slots_left, preview_slots:[{slot_id, start}], next_available_start\|null}}`. `availability.date` = the `date` filter, else today. `day_state` for that date: `open` (slots left), `full` (windows exist, none left: "Fully booked today"), `off` (no windows). `slots_left` and `preview_slots` (up to 4) cover that date only. `next_available_start` = first open slot overall ("Next: Wed 5:00 pm"). With a `date` filter, doctors whose `day_state` is not `open` are excluded. `distance_km` is null without `lat,lng`. The fee and experience filter options are static FE lists. |
| `GET /doctors/{id}` [P] | `{doctor:{id, name, degrees, remarks, registration_no, council, specialities:[{id,name}]}, clinics:[{id, name, address, area, city, pincode, lat, lng, phone, schedule_summary}]}`. 404 if not approved. |
| `GET /doctors/{id}/slots?clinic_id=&from=&days=7` [P, optional Bearer] | `clinic_id` required, `days` 1-14 (default 7). A Bearer token is optional and only enables `held_by_me` and `overlaps_mine`. Returns **every** date in range: `{days:[{date, weekday, windows:[{start_time, end_time, slot_minutes, slots:[{id, start, end, seq, window_total, token, available, held_by_me, overlaps_mine}]}]}]}`. An off day has `windows:[]`. `seq`/`window_total` ("Slot 3 of 5") are per window, and `token` is the day-wide ordinal shown to patients. `available=false` covers booked, held, blocked, and slots inside the cutoff. `held_by_me` is true if the caller holds it. `overlaps_mine` is true if the slot overlaps one of the caller's active bookings (the FE disables it; false for anonymous callers). `seq`, `window_total` and `token` count blocked slots too and are fixed at generation, so they never shift for a slot that has a booking. The FE shows a day's total as the sum of available slots. |

## Booking (patient)
Flow: pick slot -> `POST /bookings` (hold, countdown) -> `PATCH` details -> `POST pay` -> Razorpay Checkout -> `POST verify` (webhook may win) -> confirmed.

`Booking.status`: `pending_payment | confirmed | arrived | completed | no_show | cancelled | expired`.

| | |
|---|---|
| `POST /bookings` [PT] | `{slot_id}` -> 201 `Booking` (`pending_payment`, `hold_expires_at`). **Idempotent for the same slot and user** (returns the existing hold with 200). A new hold with the same doctor releases the patient's older hold with that doctor. Holds with different doctors may coexist, but the slot's time must not overlap any of the patient's other active bookings (`pending_payment`, `confirmed`, `arrived`): 409 `BOOKING_OVERLAP` with `details.conflicting_booking{id, ref, status, doctor_name, start, end, hold_expires_at}`. The same-doctor release is atomic with the new hold: the replaced hold is excluded from the overlap check, and if the check fails the old hold is kept. 409 `SLOT_TAKEN` with `details.alternatives:[Slot]` (nearest available slots of that doctor and clinic). 409 `TOO_LATE` inside the cutoff. |
| `GET /bookings/active-holds` [PT] | `{items:[Booking]}` sorted by `hold_expires_at` ascending: the caller's live `pending_payment` holds (one per doctor at most). A hold with `patient:null` is at the Details step, otherwise at Payment. Used to resume after a reload and from the header. |
| `PATCH /bookings/{id}` [PT] | `{patient:{is_self, name, age, gender, phone, reason?}}` -> `Booking`. 409 `HOLD_EXPIRED` once it has lapsed. |
| `POST /bookings/{id}/release` [PT] | -> 204 (user navigates away or the countdown ends). 409 `PAYMENT_IN_PROGRESS` if a payment on its order is already authorized or captured (it will confirm). An open order with no payment is fine and is voided. |
| `POST /bookings/{id}/pay` [PT] | -> `{razorpay_key_id, razorpay_order_id, amount_paise, currency, prefill:{name, contact}}`. The amount is server-computed. Idempotent: reuses the open order, so a Checkout retry is safe. 409 `HOLD_EXPIRED`, 409 `DETAILS_MISSING`. Allowed up to `hold_expires_at`. |
| `POST /bookings/{id}/payment/verify` [PT] | `{razorpay_order_id, razorpay_payment_id, razorpay_signature}` -> `Booking` (`confirmed`). **Idempotent** if the webhook already confirmed it. Accepted up to 2 minutes of grace after the hold expires, if the slot is still free and confirming would not overlap another active booking of the patient. 400 `SIGNATURE_INVALID`. 409 `SLOT_LOST_REFUNDED` if the slot went to someone else, the grace period has passed, or confirming would now overlap another booking (the reason is recorded, an automatic refund has started, and `GET` shows `cancelled`, `cancelled_by=system`, `cancel_reason=slot_lost`, with `refund`). |
| `GET /bookings/{id}` [PT] | `Booking`. The FE polls every 2 s for about 30 s after paying, then shows "we'll confirm by SMS". |
| `GET /bookings?tab=upcoming\|past\|cancelled&page=` [PT] | `upcoming` = `confirmed`/`arrived` with a future slot. `past` = `completed`, `no_show`, and `confirmed`/`arrived` whose slot has passed. `cancelled` = `cancelled`. `pending_payment` and `expired` never appear (live holds are `active-holds`). |
| `GET /bookings/{id}/cancel-preview` [PT] | `{refund_amount_paise, refund_percent, reason_text}` |
| `POST /bookings/{id}/cancel` [PT] | `{reason?}` -> `{booking, refund:{amount_paise, status}\|null}` |
| `POST /bookings/{id}/reschedule` [PT] | `{new_slot_id}` -> `Booking`. Same doctor, outside the free-cancel window, `reschedule_count < max`, and the new slot is available (atomic, no new payment). 409 `RESCHEDULE_NOT_ALLOWED` (`details.reason_code`), `SLOT_TAKEN`, or `BOOKING_OVERLAP` (with `details.conflicting_booking` as above). |

**Booking** object: `{id, ref:"CS-000123", status, server_time, hold_expires_at\|null, token, slot:{id, start, end, seq, window_total}, doctor:{id, name}, clinic:{id, name, address, area, city, lat, lng, phone}, patient:{is_self, name, age, gender, phone, reason}\|null, fee_paise, can_cancel, can_reschedule, reschedule_blocked_reason:{code, text}\|null, payment_status:null\|paid\|refund_pending\|refunded, refund:{amount_paise, status}\|null, cancelled_by, cancel_reason}`. `reschedule_blocked_reason.code` is `not_confirmed\|within_free_cancel_window\|max_reschedules`. `cancel_reason` is free text for patient and doctor cancels, and `slot_lost` for system cancels. "Add to calendar" is generated by the FE from this object.

**Webhook** `POST /webhooks/razorpay` [signature header `X-Razorpay-Signature`, no JWT]. Handles `payment.captured`, `payment.failed`, `refund.processed` and `refund.failed`. It stores the event first (unique event id), so a duplicate returns 200 with no work done.

## Doctor [D]
**Gating:** profile, documents, clinics and schedule endpoints work in every status (a doctor sets everything up before approval). Slots are generated only on approval. `PUT`/`PATCH` of the profile, documents and submit are allowed only in `draft`, `info_requested` and `rejected` (re-edit and resubmit). In `submitted` and `approved` the profile is read-only (approved credential changes are P1). `suspended` can view everything but the doctor is hidden from search. The FE shows `status_reason` for `info_requested`, `rejected` and `suspended`.

| | |
|---|---|
| `GET /doctor/profile` | `{full_name (shown publicly as `name`), gender, registration_no, council_id, degrees, specialities:[id], experience_years, fee_paise, languages, remarks, verification_status, status_reason, registry_check}`. No photo in MVP (initials avatar, as in the designs). |
| `PATCH /doctor/profile` | **Partial** (backs "Save draft"). Validation of completeness happens only at submit. |
| `POST /doctor/documents` | multipart `{type: registration\|degree\|id, file}` (PDF/image, max 5 MB) -> `{id, type, name, size_bytes, uploaded_at}`. One current document per type (a new upload replaces it). `GET /doctor/documents` -> `{items}`. `DELETE /doctor/documents/{id}`. |
| `POST /doctor/profile/submit` | requires every profile field and all three document types (400 with `fields` otherwise). Runs the **simulated registry check** (random, ~80% `passed`), then sets `submitted`. |
| `GET /doctor/clinics` / `POST` | `Clinic {id, name, address, area, city, pincode, lat, lng, phone}`. `PUT /doctor/clinics/{id}`. `DELETE` is 409 if it has future bookings. |
| `GET /doctor/clinics/{id}/schedule` | `{windows:[{id, weekday, start_time, end_time, slot_minutes, slot_count}], exceptions:[{id, date, type, start_time, end_time, slot_minutes}]}` |
| `PUT /doctor/clinics/{id}/schedule` | `{windows:[{weekday, start_time, end_time, slot_minutes\|slot_count}]}`. If neither is given, `slot_minutes` defaults to 12. The FE shows "N slots of M min". Replaces the weekly template and regenerates slots. -> `{slots_generated, conflicts:[Conflict]}`. 400 on overlapping windows, or a window not divisible by the slot length (never truncated). Slots with active bookings are **kept** and flagged, and no new slot is ever generated overlapping a kept one (it is skipped). |
| `POST /doctor/clinics/{id}/exceptions` / `DELETE .../exceptions/{eid}` | `{date, type: blocked\|extra, start_time?, end_time?, slot_minutes?}`. "Block day" = blocked with no window; a blocked exception with a window blocks only the slots starting inside it. -> `{slots_generated, conflicts}` (201 on create, 200 on delete). |
| `GET /doctor/clinics/{id}/slots?date=` | the owner's own view of that day in any status: `{items:[{id, start, end, seq, token, status: available\|held\|booked\|blocked}]}`. Used for "Block a slot" and for picking a replacement slot. |
| `POST /doctor/slots/{id}/block`, `DELETE /doctor/slots/{id}/block` | Block a slot / unblock it (block is a resource; DELETE removes it, so there is no `/unblock` verb). 409 `HAS_BOOKING` if booked. |
| `GET /doctor/conflicts` | `{items:[Conflict]}`, open ones that persist until resolved: `{booking_id, ref, patient_name, start, clinic_id, reason: window_removed\|day_blocked\|slot_blocked\|doctor_suspended}` |
| `GET /doctor/appointments?clinic_id=&date=` | `clinic_id` is required if the doctor has more than one clinic. `date` defaults to today. -> `{date, clinic, stats:{slots, booked, completed, earned_paise}, rows:[{slot:{id, start, end, seq, token}, state: available\|held\|booked\|blocked, booking:{id, ref, status, patient_name, patient_age, patient_gender, patient_phone, reason, needs_resolution}\|null}]}`. `stats.slots` excludes blocked slots. `stats.booked` counts bookings in `confirmed`, `arrived`, `completed` and `no_show`. `earned_paise` counts `completed` only. `held` rows are unpaid holds (shown as "being booked") and have `booking:null`. |
| `POST /doctor/bookings/{id}/status` | `{status}`. Legal: `confirmed->arrived`, `arrived->completed`, `confirmed\|arrived->no_show`. Anything else is 409 `INVALID_TRANSITION`. |
| `POST /doctor/bookings/{id}/cancel` | `{reason}`. Always a full automatic refund, and the patient is notified. |
| `POST /doctor/bookings/{id}/reschedule` | `{new_slot_id}`, same doctor, and the patient is notified. Used to resolve conflicts. 409 `BOOKING_OVERLAP` if the new time clashes with the patient's other bookings. |

## Admin
No API. Admins use the Django admin site (doctor verification with reasons, document viewing, booking search, manual refund, reconciliation issues, suspend). The Admin screen design is superseded by it and is not built in the React app. Reconciliation and verification logic live in service functions shared with the API.

## Error codes
| Code | Status | Raised by | `details` |
|---|---|---|---|
| `VALIDATION_ERROR` | 400 | any write | |
| `OTP_INVALID`, `OTP_EXPIRED` | 400 | verify OTP | |
| `SIGNATURE_INVALID` | 400 | payment verify | |
| `TOKEN_EXPIRED`, `TOKEN_INVALID` | 401 | any authed call | |
| `ROLE_FORBIDDEN`, `ACCOUNT_DISABLED` | 403 | any authed call | |
| `NOT_FOUND` | 404 | any (also for objects you do not own) | |
| `ROLE_MISMATCH` | 409 | OTP request | |
| `SLOT_TAKEN` | 409 | hold, reschedule | `alternatives:[Slot]` |
| `TOO_LATE` | 409 | hold, reschedule | |
| `BOOKING_OVERLAP` | 409 | hold, reschedule (patient and doctor) | `conflicting_booking{id, ref, status, doctor_name, start, end, hold_expires_at}` |
| `HOLD_EXPIRED` | 409 | details, pay | |
| `DETAILS_MISSING` | 409 | pay | |
| `INVALID_STATE` | 409 | cancel, pay, release or details on a booking in the wrong status | `status` |
| `PAYMENT_IN_PROGRESS` | 409 | release | |
| `SLOT_LOST_REFUNDED` | 409 | payment verify | |
| `RESCHEDULE_NOT_ALLOWED` | 409 | reschedule | `reason_code` |
| `PROFILE_LOCKED` | 409 | profile, document or submit writes while `submitted`, `approved` or `suspended` | `status` |
| `HAS_BOOKING` | 409 | block slot | |
| `CLINIC_HAS_BOOKINGS` | 409 | delete clinic | |
| `INVALID_TRANSITION` | 409 | doctor booking status | `from`, `to` |
| `OTP_LOCKED`, `THROTTLED` | 429 | OTP, booking endpoints | `retry_after_seconds` |

## Misc
`GET /healthz` [P] -> `{db, redis}` (ops only). Settings API deferred (P1; values are seeded in `platform_setting`). An earnings endpoint is deferred (the dashboard stat is enough for now).

Notifications have no API. They are sent server-side on: booking confirmed, cancelled (any party), rescheduled, refund processed, reminders at 24 h and 2 h, doctor alerts on a new booking and a cancellation, and the slot-lost refund.
