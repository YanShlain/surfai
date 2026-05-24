# Requirements: Flight Booking System (Temporal Interview Exercise)

**Status:** REVIEW
**Last updated:** 2026-05-24
**Owner:** Interview candidate
**Confidence:** 95% — Timer resume rule confirmed; minor gaps on flight catalog size and alternative-payment limits remain (low severity).

**Source:** Enriched from `docs/initial_requirements.md`

---

## 1. Summary

Build a **multi-flight seat reservation and payment system** orchestrated by **Temporal**, with a **Go REST API**, **Go Temporal workers**, and a **web frontend**. A user selects a **flight**, creates an order, selects seats (triggering a **15-minute hold** that **refreshes on each selection change**), reviews the order while watching a **live countdown**, then pays with a **5-digit code** validated within **10 seconds** with **up to 3 attempts per payment method** and a **simulated 15% failure rate**. The **hold timer pauses during payment validation**. If all 3 attempts fail for a payment method, the user is **notified** and may **provide an alternative payment method** while seats remain held and the hold timer **resumes with the time remaining before the user first clicked Pay**. The system exposes **real-time order and timer status**, handles failures gracefully, and releases seats when holds expire.

This is a **coding interview exercise**, not a production launch. Requirements prioritize **demonstrating Temporal workflow design** (timeouts, pauses, retries, state) over production scale or compliance.

---

## 2. Problem & goals

### Problem statement

Flight booking involves **time-bound inventory** (seats per flight), **long-running user sessions** (browse flights → select → pay), and **unreliable payment steps**. Without orchestration, seat holds, payment retries, timer pause/resume, and expiry are easy to get wrong (double booking, orphaned holds, stuck orders).

### Success metrics (interview context)

| Metric | Target | How measured |
|--------|--------|--------------|
| Multi-flight booking | User selects flight A vs B with isolated seat maps | Demo / test |
| End-to-end booking works | User completes happy path on chosen flight | Manual demo / E2E |
| Seat hold expires correctly | Held seats return to available after 15 min idle | Timer test + inventory check |
| Timer refresh on change | Each seat update resets 15 min window | Modify selection; verify new expiry |
| Timer pause on payment | Countdown stops during validation activity | UI + workflow history |
| Payment retry behavior | 3 attempts per method; 15% simulated failure | Mock payment activity |
| Alternative payment flow | After 3 fails, user prompted; timer restored; seats held | Scenario S-5b |
| Temporal orchestration | Single workflow owns full order lifecycle | Code review + Temporal UI |
| Real-time UX | User sees countdown + order status | Polling or push |
| Failure clarity | User gets indicative messages at each failure point | Scenario tests |

### Non-goals (out of scope)

- Flight **search** (filters, ranking, pricing engines), loyalty, refunds, cancellations after confirmation
- Real payment gateway integration (PCI, tokenization, multiple card networks)
- Production auth (OAuth, SSO), RBAC beyond a single anonymous or stub user
- Multi-region deployment, HA Temporal cluster tuning
- Email/SMS delivery infrastructure (confirmation may be **simulated** in-app or logged)
- External seat-inventory microservice (inventory is **internal** per initial spec)
- Load testing at production scale

---

## 3. Users & context

| Persona / actor | Need | Notes |
|-----------------|------|-------|
| **Customer (User)** | Browse flights, book seats, hold while deciding, pay, get confirmation | Primary actor |
| **Web App** | Flight list/detail, seat map per flight, timer, order status, payment form | Must reflect workflow state |
| **REST API (Go)** | Flight catalog, order/seat ops; start/signal/query workflows | Bridge between UI and Temporal |
| **Temporal Server** | Durable workflow execution, timers, retries | Dev: `temporal server start-dev` |
| **Temporal Workers (Go)** | Activities: reserve/release seats, validate payment, send confirmation | Business logic + workflow |

### Constraints

- **Stack:** Go REST server, Go Temporal workers, Temporal for orchestration, web frontend (framework unspecified)
- **Multi-flight:** System supports **multiple flights**, each with its own seat inventory
- **Seat inventory:** Managed internally per flight; implementation approach is **implementer's choice**
- **Temporal:** At minimum, **one workflow implements the entire order** lifecycle
- **Payment:** 5-digit code per payment method, 10 s validation timeout, **3 attempts per method**, 15% random failure (simulated)
- **Seat hold:** 15 minutes, **refresh on every seat selection update**; **pause during payment validation**; **resume remaining time (from first Pay click) on payment-method exhaustion**

---

## 4. Functional requirements

### 4.1 Core flows

| ID | Flow | Description |
|----|------|-------------|
| F-0 | Browse flights | User views available **flights** (id, route, departure time, etc.); selects one to book |
| F-1 | Create flight order | User starts booking for a **specific flight**; system creates **Order** in `CREATED` and starts order workflow |
| F-2 | Select N seats | User picks seats on that flight; system **holds** them and starts/refreshes **15-minute timer** |
| F-3 | Modify seat selection | User adds/removes/changes seats before confirmation; timer **resets**; released seats return to `AVAILABLE` on that flight |
| F-4 | Review order | User sees flight, seats, order status, and **countdown** before paying |
| F-5 | Submit payment | User submits **5-digit payment code**; workflow enters validation; **hold timer pauses** |
| F-6 | Payment success | On valid charge (~85%), seats → `BOOKED`, order → `CONFIRMED`, confirmation shown; timer stopped |
| F-7 | Payment retry (same method) | On failure (~15%), retry up to **3 attempts total for current payment method**; timer remains **paused** during each validation |
| F-8 | Payment method exhausted | After 3 failures for current method: notify user, offer **alternative payment method**; order → `AWAITING_NEW_PAYMENT_METHOD`; **resume timer with remaining time from before first Pay click**; **seats stay held** |
| F-9 | Submit alternative payment | User provides new 5-digit code; attempt counter resets for new method; timer **pauses** again during validation |
| F-10 | Hold expiry | If 15 minutes elapse in a **running-timer** state without successful payment, release holds → order `EXPIRED` |
| F-11 | Real-time status | UI shows countdown (running or paused), order status, and payment prompts |

### 4.2 Entities, states & rules

#### Flight

| Field / rule | Requirement |
|--------------|-------------|
| Identity | Unique `flight_id` |
| Seat map | Fixed set of seats per flight (e.g. `1A`–`6F`); inventory isolated per flight |
| Listing | API returns flights available for booking (minimal metadata: id, origin/destination or label, departure time) |

**Rules**

- **R-F1:** Seat holds and bookings are scoped to **one flight per order**; changing flight requires a new order (or explicit cancel + recreate).
- **R-F2:** A seat on flight X is independent of the same seat label on flight Y.

#### Order

| State | Meaning | Timer | Legal next states |
|-------|---------|-------|-------------------|
| `CREATED` | Order exists for a flight; no seats held | — | `SEATS_HELD`, `CANCELLED` |
| `SEATS_HELD` | Seats held; user selecting/reviewing | **Running** (15 min) | `SEATS_HELD`, `AWAITING_PAYMENT`, `EXPIRED`, `CANCELLED` |
| `AWAITING_PAYMENT` | Payment validation in progress | **Paused** | `CONFIRMED`, `SEATS_HELD` (retry), `AWAITING_NEW_PAYMENT_METHOD`, `EXPIRED`* |
| `AWAITING_NEW_PAYMENT_METHOD` | Current method failed 3×; user must decide | **Running** (remaining time from first Pay click) | `AWAITING_PAYMENT`, `SEATS_HELD`, `EXPIRED`, `CANCELLED` |
| `CONFIRMED` | Payment succeeded | Stopped | Terminal |
| `EXPIRED` | Hold timer elapsed | Stopped | Terminal |
| `CANCELLED` | User abandoned booking | Stopped | Terminal |

\* Timer does not expire while paused in `AWAITING_PAYMENT`; expiry applies once timer resumes in `AWAITING_NEW_PAYMENT_METHOD` — see R-T4.

**Rules**

- **R-O1:** One active booking workflow per order (1:1 order ↔ workflow).
- **R-O2:** Terminal states (`CONFIRMED`, `EXPIRED`, `CANCELLED`) reject seat changes and payment.
- **R-O3:** Successful payment only while seats remain held and order non-terminal.
- **R-O4:** Order records `flight_id` and selected seat ids for that flight.

#### Seat (per flight)

| State | Meaning |
|-------|---------|
| `AVAILABLE` | Selectable on that flight |
| `HELD` | Reserved for an order until expiry, release, or booking |
| `BOOKED` | Confirmed after successful payment |

**Rules**

- **R-S1:** A seat in `HELD` or `BOOKED` for order A **must not** be holdable by order B on the **same flight**.
- **R-S2:** On hold expiry or cancel, seats return to `AVAILABLE` unless `BOOKED`.
- **R-S3:** On successful payment, held seats atomically become `BOOKED`.
- **R-S4:** **Payment method failure does not release seats** (decision O-4).

#### Payment method & attempts

| Field / rule | Requirement |
|--------------|-------------|
| Payment method | Represented by a user-submitted **5-digit code** (simulated); each distinct submission session counts as a **method attempt group** |
| Code format | Exactly **5 digits**; reject non-numeric or wrong length **before** validation — **does not** consume a retry |
| Validation timeout | **10 seconds** per attempt |
| Max attempts | **3 per payment method** |
| Failure simulation | **15%** random failure per validation call |
| Success | Simulated charge → confirmation → `CONFIRMED` |
| 3 failures on method | Notify user: *payment method failed*; prompt for **alternative payment method**; transition to `AWAITING_NEW_PAYMENT_METHOD` |
| Alternative method | New 5-digit code; fresh **3-attempt** counter; user may accept or continue browsing seats (timer running) |

**Rules**

- **R-P1:** Attempt counter is **per payment method**, not global per order.
- **R-P2:** While in `AWAITING_PAYMENT`, hold timer is **paused** (O-3).
- **R-P3:** On **first** transition to `AWAITING_PAYMENT`, workflow **snapshots** `hold_remaining_at_first_pay`. On transition to `AWAITING_NEW_PAYMENT_METHOD`, timer **resumes from that snapshot** (O-4).
- **R-P4:** There is **no terminal `FAILED` state from payment alone**; order ends in `EXPIRED` or `CANCELLED` if user never succeeds.

#### Timer (seat hold)

| Rule | Requirement |
|------|-------------|
| Duration | **15 minutes** from last seat selection update |
| Refresh trigger | Any change to selected seats while in `SEATS_HELD` or `AWAITING_NEW_PAYMENT_METHOD` (resets to full 15 min and clears first-Pay snapshot) |
| **Pause trigger** | Entering `AWAITING_PAYMENT` (payment validation started) — **O-3**; snapshot remaining time on **first** Pay click only |
| **Resume / restore** | Retries on same method: timer stays paused; entering `AWAITING_NEW_PAYMENT_METHOD`: **resume from `hold_remaining_at_first_pay`** — **O-4** |
| Expiry action | Release all holds for that order on that flight; order → `EXPIRED`; notify UI |
| UI | Show timer as **paused** during payment validation (e.g. frozen countdown + label) |

**Rules**

- **R-T1:** Paused time does **not** count against the hold while in `AWAITING_PAYMENT`.
- **R-T2:** After payment-method exhaustion, timer resumes with **`hold_remaining_at_first_pay`** — the countdown value at the moment the user **first** clicked Pay, not a fresh 15 minutes.
- **R-T3:** Seat selection change after exhaustion **refreshes** timer to full 15 min and clears the first-Pay snapshot (same as any seat update).
- **R-T4:** If resumed timer expires in `AWAITING_NEW_PAYMENT_METHOD` without successful payment, order → `EXPIRED`.

### 4.3 Permissions & authorization

| Actor | Action | Allowed? | On deny |
|-------|--------|----------|---------|
| Customer | List/view flights | Yes | N/A |
| Customer | Create order for a flight | Yes | 404 if flight unknown |
| Customer | Select/modify seats on **own** order | Yes, if non-terminal and valid state | 409 / 400 |
| Customer | Submit / retry payment | Yes, if seats held and attempts remain for current method | 400 / 409 |
| Customer | Submit alternative payment method | Yes, in `AWAITING_NEW_PAYMENT_METHOD` | 400 / 409 |
| Customer | Act on another user's order | No | 404 or 403 |
| System (workflow) | Release/book seats | Yes | N/A |

### 4.4 Data

| Data | Source | Retention | PII? |
|------|--------|-----------|------|
| Flight catalog | Internal seed/DB | Static for demo | No |
| Order (id, flight_id, status, seat ids, timestamps) | App DB / workflow | Persist for interview | Low |
| Seat inventory (per flight) | Internal store | Same | No |
| Payment code | User input | **Do not persist** after validation | Yes |
| Payment method attempt count | Workflow state | Ephemeral per method | No |
| `hold_remaining_at_first_pay` | Workflow state | Set on first Pay; cleared on seat refresh | No |
| Confirmation message | Generated on success | UI / log | No |

### 4.5 API & integration (requirement-level)

| Capability | Purpose |
|------------|---------|
| List / get flights | Multi-flight browse; seat map per flight |
| Create order (with `flight_id`) | Start booking on chosen flight |
| Get order status | Status + timer (remaining or `paused`) + seats + payment prompts |
| Update seat selection | Hold/release; refresh timer |
| Submit payment code | Start or retry validation; pause timer |
| Submit alternative payment method | New method after 3 failures; resets attempt counter |
| Optional: cancel order | User abandons booking |

**Temporal integration**

| Capability | Purpose |
|------------|---------|
| Start order workflow | On order creation (includes `flight_id`) |
| Signal: seat selection updated | Refresh holds and timer |
| Signal: payment submitted | Validate; pause timer; track per-method attempts |
| Signal: alternative payment submitted | New method; fresh 3 attempts |
| Query: order status / timer | UI: running remaining, paused, or state label |
| Activities | Reserve/release seats **for flight**, validate payment, send confirmation |

---

## 5. Non-functional requirements

### 5.1 Scalability

| Dimension | Now (interview) | 12-month (hypothetic) | Implication |
|-----------|-----------------|----------------------|-------------|
| Flights | Small catalog (e.g. 3–20) | Hundreds | Index by `flight_id` |
| Users | 1–5 concurrent | Thousands | — |
| Seats | ~30–200 per flight | Same pattern | Inventory keyed by `(flight_id, seat_id)` |

**Scaling strategy (deferred):** Partition seat inventory by `flight_id`; horizontal workers.

### 5.2 Resilience

| Dependency | Failure mode | Required behavior |
|------------|--------------|-------------------|
| Temporal Server | Down | API returns 503 |
| Worker | Crash mid-workflow | Workflow resumes; paused timer state preserved |
| Payment activity | Timeout (>10 s) | Failed attempt; retry if attempts remain on method |
| Payment activity | Simulated failure | Retry up to 3 per method; then alternative-payment path |
| API | Duplicate submit | Idempotent handling; no extra attempt consumption |

**Degraded mode:** If Temporal unavailable, booking cannot proceed.

### 5.3 Consistency

| Operation | Consistency need | User-visible guarantee |
|-----------|------------------|------------------------|
| Hold seat (per flight) | **Strong** | No double booking on same flight |
| Release on expiry | **Strong** | Seat selectable again |
| Confirm booking | **Strong** | No overlapping `BOOKED` on same flight |

**Priority:** Correctness over latency.

### 5.4 Other NFRs

- **Security:** Do not log payment codes.
- **Observability:** Log state transitions; Temporal history for demo.
- **Operability:** README for Temporal dev server, API, worker, UI.

---

## 6. Scenarios & acceptance criteria

### 6.1 Happy path

| ID | Trigger | Steps | Expected result | Acceptance |
|----|---------|-------|-----------------|------------|
| S-1 | Successful booking | Pick flight → create order → select 2 seats → pay → success | `CONFIRMED`; seats `BOOKED` on that flight only | E2E |
| S-1b | Multi-flight isolation | Hold seat `1A` on flight F1; verify `1A` on F2 still `AVAILABLE` | Independent inventories | Integration test |
| S-2 | Change seats | Hold A1,A2 → change to B3,B4 | A1,A2 released; B3,B4 held; timer reset 15 min | Inventory + timer |

### 6.2 Failure & edge cases

| ID | Trigger | Expected result | Acceptance |
|----|---------|-----------------|------------|
| S-3 | Hold expires | Select seats → 15 min idle (no payment pause covering full window) | `EXPIRED`; seats released | Timer test |
| S-4 | Payment fails once then succeeds | Fail attempt 1, succeed attempt 2 (same method) | Timer paused during validation; eventual `CONFIRMED` | Mock RNG |
| S-5a | Timer pause during payment | Submit payment; validation takes 5 s | UI shows paused timer; no countdown decrement | UI + query |
| S-5b | Payment method exhausted | 8 min left on hold → Pay → 3 failures on `12345` | Notify failure; offer alternative; `AWAITING_NEW_PAYMENT_METHOD`; **seats held**; **timer resumes at 8 min** | E2E |
| S-5c | Alternative method succeeds | After S-5b, submit new code `67890` → success | `CONFIRMED`; first method's failures irrelevant | E2E |
| S-6 | Payment timeout | Activity >10 s | Counts as failed attempt | Slow mock |
| S-7 | Invalid code format | `123` or `abcde` | API reject; no attempt consumed | Unit test |
| S-8 | Concurrent hold same seat | Two orders, same flight, seat C1 | One succeeds; one error | Concurrency test |
| S-9 | Expiry during alternative-payment window | 8 min restored after 3 fails → no action for 8 min | `EXPIRED`; seats released | Timer test |
| S-5d | Seat change after method exhaustion | After S-5b, user changes seats | Timer **refreshes to full 15 min**; first-Pay snapshot cleared | Timer test |
| S-10 | Modify seats after terminal state | PATCH on `CONFIRMED` | 409/400 | API test |
| S-11 | Worker restart mid-flow | Kill worker during paused payment | Timer still paused; state consistent | Temporal demo |

### 6.3 Abuse / misuse

| ID | Threat | Mitigation |
|----|--------|------------|
| S-12 | Rapid seat toggle | Optional rate limit |
| S-13 | Brute-force codes | 3 attempts per method; new method requires explicit user action |
| S-14 | Order ID guessing | Unguessable UUIDs |

---

## 7. Architecture reference

```
User → Web App → RESTful Server (Go) → Temporal Server → Workers (Go)
                      ↑___________________________|
                    (status / timer / results)
```

**Mandatory:** One Temporal workflow per order (hold timer with pause/restore, per-method payment retries, alternative-payment branch, terminal states).

**Seat management (implementer's choice):** Key inventory by `(flight_id, seat_id)` — in-memory, DB, or entity workflows.

---

## 8. Decisions log

| Date | Decision | Rationale | Decided by |
|------|----------|-----------|------------|
| 2026-05-24 | Seat inventory internal per flight | Initial spec + multi-flight | Initial spec |
| 2026-05-24 | 15 min hold refreshes on seat update | Initial spec | Initial spec |
| 2026-05-24 | Payment: 5 digits, 10 s timeout, 3 attempts, 15% fail | Initial spec | Initial spec |
| 2026-05-24 | Invalid code format does not consume retry | Fair UX | PM enrichment |
| 2026-05-24 | Polling OK for real-time if WebSocket omitted | Interview pragmatism | PM enrichment |
| 2026-05-24 | **O-3: Timer pauses during payment validation** | User decision; avoids expiry mid-payment | User |
| 2026-05-24 | **O-4: After 3 fails, prompt alternative payment; keep seats** | User decision; no immediate release | User |
| 2026-05-24 | **Timer resume = remaining time before first Pay click** (not fresh 15 min) | User confirmation of derived rule | User |
| 2026-05-24 | **A-2: Multi-flight support required** | User decision | User |
| 2026-05-24 | No terminal `FAILED` from payment alone | Follows O-4; expiry/cancel ends unsuccessful orders | PM (derived) |

---

## 9. Assumptions

| ID | Assumption | Risk if wrong | Validate by |
|----|------------|---------------|-------------|
| A-1 | Real-time UI via polling (1–2 s) is acceptable | Interviewer wants WebSocket | Ask interviewer |
| A-3 | N ≥ 1 seat required before payment | Zero-seat edge case | Confirm if needed |
| A-4 | Unauthenticated user; order UUID is access token | Security model differs | Ask interviewer |
| A-5 | Confirmation in-app, not email | Email required | Ask interviewer |
| A-6 | 15% failure independent per attempt | Different model | Confirm |
| A-7 | Unlimited alternative payment methods until timer expires | Cap needed | Low risk; defer |
| A-8 | Flight catalog is pre-seeded (no admin UI) | Admin CRUD needed | Interview default |

---

## 10. Open issues

| ID | Issue | Severity | Owner |
|----|-------|----------|-------|
| O-1 | Exact seat labeling and flights in seed data | Low | Candidate |
| O-2 | Real-time transport: polling vs WebSocket/SSE | Low | Candidate |
| O-5 | Explicit cancel API | Low | Candidate |
| O-6 | Review step UI-only vs API gate | Low | Candidate |
| O-7 | Frontend stack mandated? | Low | Interviewer |
| O-8 | Max alternative payment methods per order | Low | Candidate |

*No blockers.*

---

## 11. Confidence breakdown

| Factor | Score | Notes |
|--------|-------|-------|
| Scope & goals | 98% | Multi-flight in scope; search/pricing out |
| Functional behavior | 97% | Timer pause/resume snapshot, alternative payment, states defined |
| NFRs | 88% | Interview-appropriate |
| Scenarios | 95% | Covers new payment and multi-flight paths |
| Open issues | 85% | All low severity |
| **Weighted total** | **95%** | 0.20×98 + 0.30×97 + 0.25×88 + 0.15×95 + 0.10×85 ≈ 95 |

---

## 12. Lock checklist

- [x] Success metrics defined
- [x] No blocker open issues
- [x] NFRs addressed at interview level
- [x] Critical scenarios have acceptance criteria
- [x] O-3, O-4, A-2 resolved per user
- [ ] User confirmed: **requirements LOCKED**

---

## Appendix A: Detailed user flow (canonical)

1. **Browse & pick flight** — User selects a flight from the catalog.
2. **Create flight order** — System creates order + workflow scoped to `flight_id`.
3. **Select N seats** — Holds seats; starts **15-minute** timer.
4. **Review** — User sees countdown; may modify seats (**timer refreshes** on change).
5. **Pay with 5-digit code** — Timer **pauses**; validation runs (**10 s** max per attempt).
   - **Success (~85%):** Charge → book seats → confirmation → `CONFIRMED`.
   - **Failure (~15%):** Retry up to **3 attempts** (timer stays paused during each try).
6. **Payment method exhausted (3 failures)** — Notify user; ask for **alternative payment method**; **resume timer at remaining time from before first Pay click**; **seats remain held** → `AWAITING_NEW_PAYMENT_METHOD`.
7. **Alternative payment** — User submits new code → timer **pauses** again; fresh 3 attempts (repeat from step 5).
8. **Real-time updates** — UI shows status and timer (running or paused).
9. **Expiry path** — If 15-minute timer expires in any **running-timer** state without success → release seats → `EXPIRED`.

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| Payment method | One 5-digit code submission group with up to 3 validation attempts |
| Timer pause | Hold countdown frozen while payment activity runs |
| Timer restore | Resume countdown from remaining time at **first** Pay click after payment-method exhaustion |
| First-Pay snapshot | `hold_remaining_at_first_pay` captured once when user first enters payment |
| Alternative payment method | New 5-digit code after prior method failed 3 times |

## Appendix C: Temporal design implications (for handoff to design)

These are **not** implementation commitments — they explain why the decisions matter for workflow design:

| Decision | Workflow implication |
|----------|---------------------|
| Timer pause (O-3) | Use cancellable timer or record `pause_at` / `remaining_ms` in workflow state; query exposes `paused: true` |
| Timer restore (O-4) | On 3rd failure, cancel pause, resume from stored `hold_remaining_at_first_pay`; await alternative payment or seat change |
| First-Pay snapshot | Set `hold_remaining_at_first_pay` only on first `AWAITING_PAYMENT` entry; clear on seat refresh |
| Alternative payment | Branch or sub-state; reset `attempt_count` on new method signal; UI driven by `AWAITING_NEW_PAYMENT_METHOD` |
| Multi-flight | Pass `flight_id` to all seat activities; inventory isolation in activity layer |

---

*Next step:* Confirm **requirements LOCKED** to proceed to system design, or name any remaining changes.
