# PRD: Local Doctor Discovery & Appointment Booking Platform
Status: Draft v0.2  |  Date: 19 Oct 2026  |  Owner: Project owner
Project note: this is a dummy/demo software project, not a commercial launch. Razorpay runs in test mode, doctor verification is simulated, and there are no real payouts. Launch city: Durgapur. Language: English. Working name: ClinicSlot.
## 1. Overview
### 1.1 Summary
A web platform that connects patients with verified doctors in their locality. Doctors register with their credentials, set the clinic location and the hours they see patients, and the platform turns those hours into bookable time slots. Patients search by speciality and location, see real availability, pick a specific slot, and pay online (Razorpay) to confirm it.
### 1.2 Problem
Patients struggle to find a trustworthy specialist nearby and to know when that doctor is actually available.

Small clinics and solo practitioners rely on phone calls, walk-ins and long waiting queues. No-shows and overcrowding are common.

Existing large platforms are often dominated by big hospitals and metro cities; small-town and neighbourhood doctors are under-served.

### 1.3 Vision
The easiest way to find a verified local doctor and secure a time slot in under two minutes.
### 1.4 Goals
Let a doctor go live (verified, with schedule) in under 15 minutes.

Let a patient find a doctor and book a paid slot in under 2 minutes.

Eliminate double-booking: one slot, one patient.

Reduce no-shows through upfront payment and reminders.

### 1.5 Non-goals (MVP)
Video/tele-consultation (later phase).

Electronic health records, prescriptions, lab integrations.

Medicine delivery or pharmacy.

Hospital/multi-doctor clinic management software.

Insurance claims.

## 2. Users and Personas
Persona
 | Description
 | Key needs
 | Patient
 | Anyone seeking a local doctor for themselves or a family member
 | Find by speciality + area, see availability, trust signals, quick booking, reminders, easy cancel/reschedule
 | Doctor
 | Independent practitioner with one or more clinics
 | Easy onboarding, control over timings and slot size, fewer no-shows, timely payouts, simple daily view of appointments
 | Admin / Ops
 | Platform staff
 | Verify credentials, handle disputes and refunds, moderate content, monitor payments
 | ## 3. Scope (MVP)
### 3.1 In scope
Doctor registration, credential submission and admin verification

Clinic location and weekly schedule setup

Automatic slot generation

Patient search and filters (speciality, location, date, availability)

Slot selection, temporary hold and Razorpay payment

Booking confirmation, notifications, cancellation and refunds

Doctor dashboard (daily appointments) and admin console

### 3.2 Out of scope for MVP
See non-goals above. Reviews/ratings and family profiles are Phase 2.
## 4. Core User Flows
### 4.1 Doctor onboarding
Sign up with mobile number + OTP (email optional).

Fill profile: full name, photo, medical registration number and issuing council, degree(s), specialisation(s), years of experience, languages, consultation fee, and a short remarks/bio.

Upload supporting documents (registration certificate, degree certificate, ID).

Add clinic(s): name, address, map pin, city/area, contact number.

Set weekly schedule per clinic: days, start/end time, slot duration (or number of slots), and optional breaks.

Submit for verification. Profile stays hidden from search until admin approves.

After approval, the doctor goes live and slots become visible.

### 4.2 Patient search and booking
Land on home page, enter location (auto-detect or type area/pincode) and speciality (or symptom keyword).

See a list of verified doctors sorted by relevance, distance and earliest availability, with filters (date, fee, experience, gender, language, available today).

Open a doctor profile: credentials, experience, clinic address on a map, fee, remarks, and a calendar of available slots.

Pick a date, then a specific slot.

Enter patient details (name, age, gender, phone, optional reason for visit).

Slot is held for 8 minutes while the patient pays via Razorpay (UPI, cards, netbanking, wallets).

On successful payment, booking is confirmed and the patient receives SMS/WhatsApp/email with the details, clinic address and a token/slot number.

Patient can cancel or reschedule from a booking link, subject to policy.

### 4.3 Doctor daily use
View today's and upcoming appointments by slot.

Mark a patient as arrived / completed / no-show.

Block specific slots or whole days (leave, emergency).

View earnings and payout status.

## 5. The Slot Model
The slot is the central object, so its rules are defined precisely.
Example: On a given date a doctor sees patients from 4:00 pm to 5:00 pm with 5 slots. The system generates 5 equal slots of 12 minutes each:
Slot
 | Time
 | 1
 | 4:00 – 4:12 pm
 | 2
 | 4:12 – 4:24 pm
 | 3
 | 4:24 – 4:36 pm
 | 4
 | 4:36 – 4:48 pm
 | 5
 | 4:48 – 5:00 pm
 | A patient who picks the third slot reserves 4:24 – 4:36 pm.
Rules
Doctor defines a window and either the slot duration or the slot count; the system computes the rest.

A doctor may define multiple windows per day (e.g. 10–1 and 4–7) and different schedules per clinic.

Slots are generated on a rolling horizon (e.g. 30 days ahead) from the weekly template, with date-specific overrides (holidays, extra hours).

Slot states: Available → Held → Booked, plus Blocked (by doctor) and Expired (past). Held reverts to Available if payment is not completed within the hold window.

A slot can have exactly one confirmed booking (enforced at the database level, not only in the UI).

Optional later setting: allow N patients per slot (capacity) for walk-in style clinics.

Past-cutoff rule: slots cannot be booked less than X minutes before start (configurable, default 30).

All times stored in UTC, displayed in the clinic's time zone (IST at launch).

## 6. Functional Requirements
Priority: P0 = MVP must-have, P1 = MVP if time permits / fast follow, P2 = later.
### 6.1 Authentication and accounts
ID
 | Requirement
 | Pri
 | A1
 | Mobile OTP login for patients and doctors
 | P0
 | A2
 | Role-based access (patient, doctor, admin)
 | P0
 | A3
 | Optional email login / Google sign-in
 | P2
 | ### 6.2 Doctor profile and verification
ID
 | Requirement
 | Pri
 | D1
 | Capture registration number, issuing medical council, degrees, specialisations, experience, fee, remarks, languages
 | P0
 | D2
 | Document upload (certificate, ID) with secure storage
 | P0
 | D3
 | Admin review queue: approve / reject / request more info, with reason and audit trail
 | P0
 | D4
 | Verify registration number through a simulated registry website that returns a random result (about 80% pass); no real council lookup
 | P0
 | D5
 | Verified badge shown on profile only after approval
 | P0
 | D6
 | Doctor can edit profile; changes to credentials re-trigger verification
 | P1
 | D7
 | Multiple clinics per doctor
 | P1
 | ### 6.3 Clinic and schedule management
ID
 | Requirement
 | Pri
 | S1
 | Set clinic address with map pin, city, area and pincode
 | P0
 | S2
 | Weekly recurring schedule with start/end time and slot duration or count
 | P0
 | S3
 | Multiple windows per day and breaks
 | P0
 | S4
 | Date-specific overrides: block a day/slot, add extra hours
 | P0
 | S5
 | Auto-generation of slots on a rolling horizon
 | P0
 | S6
 | Changing a schedule must not silently cancel existing bookings; conflicts are flagged and the doctor must resolve them (reschedule/cancel with auto-refund)
 | P0
 | ### 6.4 Search and discovery
ID
 | Requirement
 | Pri
 | F1
 | Search by speciality and location (city, area, pincode, or current location)
 | P0
 | F2
 | Show only verified doctors with at least one available future slot (toggle to show others)
 | P0
 | F3
 | Filter by date, available today/tomorrow, fee range, experience, gender, language
 | P0
 | F4
 | Sort by earliest availability, distance, experience, fee
 | P0
 | F5
 | Doctor profile page with slot calendar and map
 | P0
 | F6
 | Symptom-to-speciality suggestions ("fever, cough" → General Physician)
 | P2
 | F7
 | SEO-friendly pages per speciality + city (e.g. "Dermatologist in Durgapur")
 | P1
 | ### 6.5 Booking
ID
 | Requirement
 | Pri
 | B1
 | Select a specific slot and enter patient details
 | P0
 | B2
 | Temporary hold on the selected slot during checkout (default 8 min) with a visible countdown
 | P0
 | B3
 | Guarantee against double booking under concurrent requests
 | P0
 | B4
 | Booking confirmation page, booking ID and token/slot number
 | P0
 | B5
 | Cancel and reschedule by the patient within policy
 | P0
 | B6
 | Book for a family member (separate patient details per booking)
 | P0
 | B7
 | Saved family profiles
 | P2
 | B8
 | Doctor-initiated cancellation with automatic full refund and patient notification
 | P0
 | ### 6.6 Payments (Razorpay)
ID
 | Requirement
 | Pri
 | P1
 | Create a Razorpay order server-side for the held slot; amount is computed on the server, never trusted from the client
 | P0
 | P2
 | Razorpay Checkout for UPI, cards, netbanking, wallets
 | P0
 | P3
 | Verify payment signature on the server before confirming a booking
 | P0
 | P4
 | Webhook handling (payment captured/failed, refund processed) with idempotency, so a booking is confirmed even if the user closes the browser after paying
 | P0
 | P5
 | Reconciliation job that matches Razorpay payments to bookings and flags mismatches
 | P0
 | P6
 | Refunds: automatic per cancellation policy via Razorpay refunds API; status shown to the user
 | P0
 | P7
 | Split payments and payouts to doctors (platform commission + doctor share), likely via Razorpay Route or equivalent; requires doctor bank/KYC onboarding
 | P2
 | P8
 | GST-compliant invoice/receipt for the platform fee
 | P1
 | What is charged (decision): patients pay the full consultation fee online at booking. There is no pay-at-clinic option and no separate booking fee in this project.
Failure handling
Payment fails or times out → slot returns to Available after the hold expires.

Payment succeeds but the hold already expired and the slot was taken by someone else → automatic refund and an apology message; this must be rare given webhook handling and a short grace period.

### 6.7 Notifications
ID
 | Requirement
 | Pri
 | N1
 | SMS/WhatsApp + email on booking confirmation, cancellation, reschedule
 | P0
 | N2
 | Reminder to the patient (e.g. 24 hours and 2 hours before)
 | P0
 | N3
 | New-booking and cancellation alerts to the doctor
 | P0
 | N4
 | Post-visit feedback request
 | P2
 | ### 6.8 Cancellation and refund policy (dummy default, simulated in test mode)
Cancel 4+ hours before the slot: full refund of the amount paid, minus payment gateway charges if they are non-refundable (decide and state clearly in the UI).

Cancel within 4 hours: no refund or partial refund (configurable by platform).

Doctor cancels: always a full refund.

No-show: no refund.

Policy is shown before payment and in the confirmation message.

### 6.9 Admin console
ID
 | Requirement
 | Pri
 | M1
 | Doctor verification queue with documents and decision log
 | P0
 | M2
 | View, search and manage bookings, patients and doctors
 | P0
 | M3
 | Manual refund and dispute handling
 | P0
 | M4
 | Payment reconciliation dashboard
 | P0
 | M5
 | Suspend/unlist a doctor
 | P0
 | M6
 | Content/review moderation
 | P2
 | M7
 | Configurable platform settings (hold time, cancellation window, commission)
 | P1
 | ### 6.10 Reviews and trust (Phase 2)
Ratings and reviews only from patients with a completed (attended) booking.

Doctor response to reviews; moderation tooling.

Note: rules around advertising and testimonials for medical practitioners are restrictive in India; legal review is needed before showing ratings or marketing language.

## 7. Data Model (high level)
User (id, role, name, phone, email)

DoctorProfile (user_id, registration_no, council, degrees, specialisations, experience_years, fee, remarks, languages, verification_status, verified_at)

Document (doctor_id, type, file_ref, status)

Clinic (id, doctor_id, name, address, city, area, pincode, lat, lng, phone)

ScheduleTemplate (clinic_id, weekday, start_time, end_time, slot_minutes or slot_count, break rules)

ScheduleException (clinic_id, date, type: blocked/extra, window)

Slot (id, clinic_id, start_ts, end_ts, status, held_until, capacity) with a unique constraint on (clinic_id, start_ts)

Booking (id, slot_id, patient_user_id, patient_details, status, fee_amount, platform_fee, created_at) with at most one active booking per slot

Payment (id, booking_id, razorpay_order_id, razorpay_payment_id, status, amount, signature_verified)

Refund (id, payment_id, razorpay_refund_id, amount, reason, status)

Notification (id, user_id, channel, template, status)

AuditLog (actor, action, entity, timestamp)

## 8. Non-Functional Requirements
Correctness: zero double bookings; every payment ends in exactly one terminal state (confirmed booking, or refunded/failed).

Performance: search results in under 2 seconds at p95; slot availability reflected within 5 seconds of a change.

Availability: 99.5% at MVP; graceful behaviour if Razorpay or SMS providers are down.

Mobile-first: most patients will use phones; responsive web, fast on low-end devices and slow networks; consider a PWA.

Security: HTTPS everywhere, encrypted storage for documents, role-based access, rate limiting on OTP and booking endpoints, no card data stored (handled by Razorpay).

Accessibility and language: English only at MVP.

Auditability: logs for verification decisions, payments, refunds and schedule changes.

## 9. Legal, Privacy and Compliance (needs professional review)
This is a dummy project, so none of this blocks the build. These items apply only if it ever goes live with real users, and are not legal advice.
Doctor credentials: verify registration with the relevant medical council/national register; display only verified information. Impersonation risk is the single biggest trust threat.

Personal data: patient name, age, phone and visit reason are personal (and arguably sensitive) data. Plan for compliance with India's Digital Personal Data Protection Act, 2023: clear consent, purpose limitation, data minimisation, retention limits, and a way to access and delete data.

Platform positioning: present the platform as a scheduling/discovery marketplace, with a clear disclaimer that it does not provide medical advice and is not for emergencies (show an emergency number prominently).

Advertising rules: restrictions on how doctors can be promoted and on testimonials/ratings; confirm what the platform can display.

Payments: marketplace payout flows involve KYC, GST and TDS considerations; confirm structure with an accountant and with Razorpay.

Tele-consultation (future): has its own national guidelines; defer until the in-clinic model is stable.

Terms and policies: terms of use, privacy policy, cancellation/refund policy, and doctor agreement.

## 10. Success Metrics
Metric
 | Target (illustrative; dummy project)
 | Verified doctors onboarded in launch city
 | 100+
 | Doctor onboarding time (signup → live)
 | < 48 hours incl. verification; < 15 min of doctor effort
 | Search → booking conversion
 | > 8%
 | Booking completion rate (held → paid)
 | > 70%
 | Double bookings
 | 0
 | No-show rate on paid bookings
 | < 10%
 | Payment-to-booking reconciliation mismatches
 | < 0.1%
 | Repeat patients within 90 days
 | > 25%
 | Doctor 30-day retention
 | > 80%
 | ## 11. Suggested Technical Approach
A starting point, to be validated with the engineering team.
Frontend: responsive web app (React/Next.js) with server-rendered pages for SEO on speciality + city pages.

Backend: Node.js or Python (Django/FastAPI) with PostgreSQL.

Slot integrity: database transactions with a unique constraint on slot booking and row-level locking when placing a hold; a background job to release expired holds.

Search: PostgreSQL with PostGIS for distance queries at MVP; move to a dedicated search engine only if needed.

Maps and geocoding: Google Maps or an open alternative.

Payments: Razorpay Orders API + Checkout, signature verification, webhooks, Refunds API; Route for payouts.

Messaging: an OTP/SMS provider and WhatsApp Business API provider, plus transactional email.

Storage: private object storage for documents with signed URLs.

Observability: error tracking, structured logs, payment event dashboard.

## 12. Phasing and Roadmap
Phase
 | Scope
 | Rough duration
 | 0. Validation
 | Skipped for this dummy project; seed test doctors and slots instead
 | 2–3 weeks
 | 1. MVP (pilot city)
 | Onboarding + verification, schedules and slots, search, booking, Razorpay, notifications, admin console
 | 10–14 weeks
 | 2. Growth
 | Reviews, family profiles, payouts automation, SEO pages, doctor mobile app/PWA improvements, analytics
 | 8–10 weeks
 | 3. Expansion
 | Additional cities, tele-consultation, clinics with multiple doctors, reminders for follow-ups
 | TBD
 | ## 13. Risks and Mitigations
Risk
 | Impact
 | Mitigation
 | Fake or unverified doctors
 | Severe trust and legal damage
 | Mandatory document + registry verification; verified-only listing; fast takedown process
 | Doctors don't keep schedules accurate or don't honour slots
 | Poor patient experience
 | Simple schedule tools, doctor-side cancellation penalties/flags, reminders, quality monitoring
 | Clinics run late, so fixed slots don't match reality
 | Frustration
 | Allow "expected wait" updates by the doctor; start with realistic slot lengths; show arrival window
 | Chicken-and-egg (needs doctors and patients)
 | Slow growth
 | Launch in one city/neighbourhood cluster; onboard doctors first with a field team; free for doctors initially
 | Doctors or patients bypass the platform
 | Revenue leakage
 | Provide real value (no-show reduction, discovery) rather than only taking commission; keep fees low
 | Patients distrust paying online
 | Lower conversion
 | Start with a small booking fee; clear refund policy; trusted payment brands
 | Regulatory/advertising constraints
 | Delays or penalties
 | Early legal review; conservative content policy
 | Payment/booking inconsistencies
 | Refund disputes
 | Webhooks, idempotency, reconciliation, clear audit logs
 | ## 14. Business Model (out of scope: dummy project)
Per-booking commission or convenience fee charged to the patient.

Doctor subscription (monthly) for listing and tools, with no commission.

Hybrid: small booking fee + premium doctor plans (featured placement, analytics). Check advertising rules before selling "featured" positions.

Not needed for this project; the options above are kept for reference only.
## 15. Open Questions 
Launch city/region and languages? DHRGAPUR, ENG

Is the consultation fee paid fully online, only a booking fee online, or doctor's choice? FULL, ONLINE

Should patients be allowed to book without an account (phone OTP only at checkout)? NO

Fixed number of patients per slot, or can doctors allow overbooking/capacity per slot? FIXED IN MVP

Who handles payouts and doctor KYC at launch, and what is the settlement cycle? PAYOUTS IN POST MVP

Do we include only individual doctors, or also small clinics/diagnostic centres, at MVP? INDIVIDUAL 

Which specialities first (e.g. general physician, paediatrics, dermatology, gynaecology, dentistry)? MOST

Is there an official registry/API we can use to verify registration numbers automatically? DUMMY WEBSITE, SO RANDOM VERIFICATION RESULT WITH 80 PERCENT SUCCESS

Refund policy details: who bears gateway charges on cancellations? DUMMY

Brand name and whether a mobile app is needed at MVP or a mobile web/PWA suffices. YOU CAN DECIDE SINCE THIS IS A DUMMY PROJECT. Claude's pick: working name ClinicSlot; mobile-first responsive web, no native app.

## 16. Appendix: Example Acceptance Criteria
Slot booking
Given a doctor window of 4–5 pm with 5 slots, when the patient opens the date, then 5 slots are listed with correct times, and booked/held slots are shown as unavailable.

Given two patients select slot 3 at the same moment, then exactly one receives the hold and the other sees a "slot just taken" message and is shown alternatives.

Given a patient holds slot 3 and does not pay within the hold window, then slot 3 returns to Available automatically.

Payment
Given a successful Razorpay payment, then the booking is confirmed only after server-side signature verification or a valid webhook, and the patient receives a confirmation within 1 minute.

Given the user closes the browser after paying, then the webhook still confirms the booking.

Given a patient cancels 6 hours before the slot, then a refund is initiated automatically and its status is visible to the patient.

Doctor verification
Given a doctor with unverified status, then the profile and slots do not appear in any search or public URL.

