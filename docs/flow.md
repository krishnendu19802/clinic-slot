# Flow

Legend: **built** = in code now, **planned** = designed, not yet written.

## 1. Request path through the layers (built, shape fixed)

```mermaid
flowchart LR
    C[React client] -->|HTTP JSON + Bearer JWT| R[config/api.py router]
    R --> V[ViewSet<br/>auth, permission, throttle]
    V --> S[Serializer<br/>validate input / shape output]
    V --> SV[Service class<br/>business rules + transaction]
    SV --> RP[Repo classes<br/>repo/psql and repo/redis]
    RP --> M[(PostgreSQL)]
    RP --> RC[(Redis<br/>OTP, throttles)]
    SV --> EXT[Razorpay / SMS<br/>never inside a DB transaction]
    V -->|ApiError| H[core.exceptions.handler<br/>error envelope]
    H --> C
    DA[Django admin actions] --> SV
```

## 2. OTP login (built)

```mermaid
sequenceDiagram
    participant FE as React
    participant API as AuthViewSet
    participant OTP as OtpService -> OtpRepo (Redis)
    participant SVC as AccountService -> repos
    participant DB as PostgreSQL
    FE->>API: POST /auth/otp/request {phone, role}
    API->>SVC: AccountService.assert_role_free (ROLE_MISMATCH / ACCOUNT_DISABLED)
    API->>OTP: request(phone): cooldown, hourly cap, store HMAC, send SMS
    API-->>FE: 200 {retry_after_seconds}
    FE->>API: POST /auth/otp/verify {phone, role, otp}
    API->>OTP: verify(phone, otp): attempts cap, single use
    API->>SVC: get_or_create_user (+ patient or doctor profile)
    SVC->>DB: INSERT user + profile
    API->>SVC: issue_tokens (SimpleJWT)
    API-->>FE: 200 {access, user} + Set-Cookie refresh (httpOnly)
    FE->>API: POST /auth/refresh (cookie + X-Requested-With)
    API-->>FE: new access, rotated refresh cookie
```

## 3. Booking: hold -> pay -> confirm (built; gateway is a stub)

```mermaid
flowchart TD
    A[POST /bookings slot_id] --> B[service.place_hold<br/>lock user row, lock slot row]
    B -->|slot taken / too late| E1[409 SLOT_TAKEN / TOO_LATE]
    B -->|overlaps my active booking| E2[409 BOOKING_OVERLAP + conflicting_booking]
    B --> C[slot HELD, booking pending_payment<br/>same-doctor older hold released]
    C --> D[PATCH details]
    D --> P[POST pay: server computes amount,<br/>Razorpay order created OUTSIDE the transaction]
    P --> K[Razorpay Checkout in browser]
    K -->|handler| V[POST payment/verify<br/>signature check]
    K -.browser closed.-> W[Webhook payment.captured]
    V --> CF[service.confirm idempotent<br/>lock booking]
    W --> CF
    CF -->|hold valid or within grace, no overlap| OK[booking confirmed, slot BOOKED<br/>notify patient + doctor]
    CF -->|slot gone / overlap| RF[auto refund, SLOT_LOST_REFUNDED]
    C -->|8 min, no payment| X[expired: lazy in queries,<br/>swept by beat tick]
```

## 4. Background work (nightly slots built, `tick` sweeps holds; reminders/reconcile planned)

```mermaid
flowchart LR
    BEAT[Celery beat] -->|every minute| T[tick: sweep holds,<br/>send due notifications and reminders,<br/>retry failed sends and refunds]
    BEAT -->|nightly| G[generate_slots: extend 30-day horizon]
    BEAT -->|nightly| RC[reconcile: payments vs bookings]
    T --> N[(notification outbox)]
    RC --> I[(reconciliation_issue)]
    I --> ADM[Django admin]
```

## 5. Schedule change -> slots (built)

```mermaid
flowchart TD
    A[PUT schedule / POST exception / nightly task] --> L[lock clinic row]
    L --> N[ScheduleService: normalise + validate windows]
    N --> G[SlotGenerationService.generate]
    G --> AP{doctor approved?}
    AP -->|no| Z[nothing generated]
    AP -->|yes| D[desired slots for next 30 days<br/>windows + extra - blocked]
    D --> R[compare with existing future slots]
    R --> K[same start and end: keep, renumber if unbooked]
    R --> X[no longer wanted]
    X --> U{has active booking?}
    U -->|no| DEL[delete under row lock]
    U -->|yes| C[keep + report conflict<br/>window_removed / day_blocked]
    R --> NEW[missing: create unless it overlaps a kept slot]
```
