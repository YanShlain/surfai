# Agent Handoff — Neon Flight Booking

**Purpose:** Onboard a new AI agent to continue this project from the current stopping point.  
**Last updated:** 2026-05-26  
**Branch:** `dev` (synced with `origin/dev`)

---

## Quick start (paste this to the agent)

```
Continue the Neon flight booking project on branch dev.

Read first:
  docs/handoff.md          (this file)
  docs/final_plan.md       (canonical architecture + phased MVPs)
  docs/final_requierments.md
  docs/progress.md         (phase checklist)

Status: MVP-A and MVP-B are DONE and user-signed-off. Implement MVP-C ONLY.

MVP-C = payment happy path:
  - ValidatePayment + ConfirmSeats activities
  - SubmitPayment signal in BookingWorkflow
  - POST /api/v1/orders/{id}/payment
  - payment_events in GetStatus query
  - Payment UI (5-digit code, submit, confirmation)
  - Tests U-C1–U-C6, I-C1–I-C3 — all must pass (go test ./...)

Rules:
  - One phase at a time; manual test checklist when done
  - Do NOT start MVP-D until user confirms
  - Presentation → Temporal only; side effects in activities → repos
  - Commit when tests green if user asks
```

---

## Project summary

**Neon** is a multi-flight seat reservation system:

- **Stack:** Go (Gin API), Temporal workflows, static HTML/JS UI, in-memory repos (Postgres deferred)
- **Flow:** Pick flight → hold seats (15m refreshable timer) → pay with 5-digit code → seats BOOKED
- **Repo:** https://github.com/YanShlain/Neon

Phases are defined in [final_plan.md](final_plan.md). UI is built **incrementally per phase** (not all at the end).

---

## What is done

### MVP-A — Flight catalog & read-only seat map ✅

- `GET /api/v1/flights`, `GET /api/v1/flights/{id}/seats`
- Domain + in-memory repos, seed flights **101** / **102** (10×6 seats)
- Static UI at `/` and `/seats?flight_id=`
- Tests: U-A1–U-A6, I-A1–I-A4

### MVP-B — Holds, timer, cancel, booking UI ✅

- `BookingWorkflow` with hold timer, cancel, auto-expiry
- Activities: `HoldSeats`, `ReleaseSeats`
- Order API: `POST/PATCH/GET /orders`, `POST .../cancel`
- Workflow updates (sync HTTP): `UpdateSeats`, `CancelOrder`
- Hold conflict → non-retryable → **HTTP 409**
- Booking UI: seat selection, timer, cancel, `localStorage`, single-order guard
- Embedded Temporal dev server (`TEMPORAL_AUTO_DEV=1` default)
- Tests: U-B1–U-B7, I-B1–I-B5
- **User manual sign-off:** 2026-05-26

**Key commits:**

| Commit | Description |
|--------|-------------|
| `e18edbf` | MVP-A + read UI |
| `6f79c25` | MVP-B backend + booking UI |
| `6754980` | Updated progress doc |

---

## What to build next — MVP-C only

**Do not implement MVP-D/E yet** (no new-method button, no method exhaustion, no Playwright E2E).

### Backend deliverables

| Item | Details |
|------|---------|
| `ValidatePayment` activity | Exactly 5 digits; 10s timeout; 15% simulated failure (injectable RNG for tests) |
| `ConfirmSeats` activity | HELD → BOOKED via `SeatRepository.Confirm` |
| `SubmitPayment` signal | Handled in workflow selector; **timer keeps running** during payment |
| Workflow states | `SEATS_HELD` → `AWAITING_PAYMENT` → `CONFIRMED` |
| `payment_events[]` | Append events to query state; expose via `GetStatus` |
| API | `POST /api/v1/orders/{order_id}/payment` body `{ "code": "12345" }` |

**Out of scope for MVP-C** (MVP-D):

- `StartNewPaymentMethod` signal / `POST .../payment/new-method`
- `RejectInFlightPayment` / timer-vs-payment race (S-4)
- 3 methods × 3 attempts exhaustion (S-3)

### UI deliverables (MVP-C)

- Payment screen after seats held (5-digit input + validation)
- Submit → call payment API; show success/failure inline
- Order status strip: `SEATS_HELD` → `AWAITING_PAYMENT` → `CONFIRMED`
- Confirmation view on success; refetch seat map (BOOKED seats grayscale)

See [final_plan.md](final_plan.md) § MVP-C UI deliverables.

### Acceptance tests (must all pass)

**Unit (Temporal test suite)** — [final_plan.md](final_plan.md) § MVP-C:

| ID | Scenario |
|----|----------|
| U-C1 | Pay success → `CONFIRMED`, seats BOOKED |
| U-C2 | Fail once, retry same code → `CONFIRMED` |
| U-C3 | 3 failures same code → 4th rejected |
| U-C4 | Payment running → query shows `AWAITING_PAYMENT`, timer running |
| U-C5 | Code `1234` → format error, stays `SEATS_HELD` |
| U-C6 | Code `abcde` → format error |

**Integration:**

| ID | Scenario |
|----|----------|
| I-C1 | **S-1** Happy path → `CONFIRMED`, seat BOOKED |
| I-C2 | Retry then succeed → 3 events, `CONFIRMED` |
| I-C3 | Timer > 0 while `AWAITING_PAYMENT` |

Run: `go test ./...`

---

## Repository map

```
cmd/
  api/main.go              # HTTP server + embedded worker (use this for dev)
  worker/main.go           # Standalone worker (future Postgres; not needed for in-memory MVP)

domain/
  seat.go, repository.go   # Seat, Flight, repo interfaces
  order.go                 # OrderStatus enum

internal/
  api/
    handler/orders.go      # Order HTTP handlers (extend for payment)
    handler/flights.go
    dto/orders.go          # Extend response with payment fields
    router.go
    order_integration_test.go
  app/application.go       # BootstrapApp: repos + Temporal + worker
  infrastructure/
    memory/                # In-memory SeatRepository, FlightRepository
    temporal/              # OrderService, dev server, client wiring
  workflow/booking/
    workflow.go            # BookingWorkflow — extend selector for SubmitPayment
    activities.go          # Add ValidatePayment, ConfirmSeats
    types.go               # Extend StatusResponse (payment_events, etc.)
    workflow_test.go
  web/static/              # UI: index, seats, css, js — add payment page/flow

docs/
  final_plan.md            # Architecture + phases (LOCKED)
  final_requierments.md    # Business requirements
  progress.md              # Phase status tracker — update when MVP-C done
  handoff.md               # This file
```

---

## Architecture rules

| Layer | May call | Must NOT |
|-------|----------|----------|
| **Presentation** (`internal/api/`, `internal/web/`) | Temporal client, repos for **read-only** seat map | Direct seat mutation, payment logic |
| **Service** (`internal/workflow/booking/`) | Activities, workflow APIs | Gin, HTTP types |
| **Data** (`internal/infrastructure/memory/`) | Storage | Business rules, HTTP |

**Locked decisions:**

- Temporal namespace: `flight-booking`
- Task queue: `booking-task-queue`
- Workflow ID = `order_id` (UUID)
- Seat map reads bypass Temporal: `GET .../seats` → `SeatRepository`
- Seat writes only via activities
- Timer **never pauses** during payment (even in MVP-C)
- `HOLD_DURATION` env overrides hold timer (default 15m; use `30s` in tests)

---

## Key files to read before coding

1. [final_plan.md](final_plan.md) §2.5 — workflow state, signals, selector loop, activities
2. [final_plan.md](final_plan.md) §4 — REST API surface + error codes
3. `internal/workflow/booking/workflow.go` — current MVP-B workflow (updates + timer loop)
4. `internal/infrastructure/temporal/order_service.go` — how HTTP calls Temporal
5. `internal/api/handler/orders.go` — existing order handlers pattern
6. `internal/web/static/js/seats.js` — current booking UI flow

---

## Development setup (Windows)

```powershell
$env:Path = "C:\Program Files\Go\bin;" + $env:Path
cd c:\Users\YanSh\Dev\Neon

go test ./...          # must pass before finishing MVP-C
go run ./cmd/api       # http://localhost:8080
```

**Environment variables:**

| Variable | Default | Purpose |
|----------|---------|---------|
| `TEMPORAL_AUTO_DEV` | `1` in bootstrap | Embed Temporal dev server |
| `TEMPORAL_HOST` | `127.0.0.1:7233` | External Temporal if set |
| `HOLD_DURATION` | `15m` | Hold timer length |
| `API_ADDR` | `:8080` | HTTP listen address |

**First run** may download Temporal CLI (~5–10s).  
**Port conflict:** `netstat -ano | findstr ":8080"` → `Stop-Process -Id <PID> -Force`

---

## Suggested implementation order for MVP-C

1. Extend `StatusResponse` / `GetStatus` with `payment_events`, attempt counters (read plan §2.5)
2. Implement `ValidatePayment` activity (format check, timeout, injectable failure RNG)
3. Implement `ConfirmSeats` activity
4. Add `SubmitPayment` signal handler to workflow selector (timer branch still active)
5. Extend `OrderService` + `orders.go` handler for `POST .../payment`
6. Unit tests U-C1–U-C6 in `workflow_test.go`
7. Integration tests I-C1–I-C3 in `order_integration_test.go`
8. Payment UI page or modal in `internal/web/static/`
9. Manual test checklist → ask user to confirm → update `docs/progress.md`

---

## Process rules (mandatory)

1. **One MVP phase at a time** — currently MVP-C only
2. **`go test ./...` green** before declaring done
3. **Manual test steps** for the user at phase end
4. **Wait for user confirmation** before MVP-D
5. **Surgical changes** — match existing style; don't refactor unrelated code
6. **Commit** when user asks (they push separately)

---

## Manual test checklist (after MVP-C)

1. Start server → hold seats on flight 101
2. Navigate to payment → enter valid 5-digit code → **CONFIRMED**
3. Seat map shows seats **BOOKED** (grayscale)
4. Enter invalid code (4 digits / letters) → error, stays `SEATS_HELD`
5. Use test hook to force payment failure → retry same code → success
6. Confirm timer still visible during `AWAITING_PAYMENT`

---

## After MVP-C (do not start without user OK)

| Phase | Focus |
|-------|-------|
| **MVP-D** | `StartNewPaymentMethod`, 3×3 attempt rules, S-3/S-4, edge-case UI |
| **MVP-E** | Playwright E2E (E-E1–E-E7), responsive polish |

---

## Related docs

- [final_plan.md](final_plan.md) — canonical architecture
- [final_requierments.md](final_requierments.md) — locked requirements
- [progress.md](progress.md) — living phase status (update when MVP-C completes)
