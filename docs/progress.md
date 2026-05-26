# Neon — Implementation Progress

**Last updated:** 2026-05-26  
**Branch:** `dev` (1 commit ahead of `origin/dev` as of last update)  
**Canonical plan:** [docs/final_plan.md](final_plan.md)  
**Requirements:** [docs/final_requierments.md](final_requierments.md)

---

## Overall strategy

Implement phases **MVP-A → MVP-E** one at a time. After each phase:

1. All phase tests must pass (`go test ./...`)
2. User manually tests via UI/API
3. **Do not start the next phase until the user confirms**

---

## Phase status summary

| Phase | Name | Status | Tests |
|-------|------|--------|-------|
| **MVP-A** | Flight catalog + read-only UI | **Done** | U-A1–U-A6, I-A1–I-A4 ✅ |
| **MVP-B** | Holds, timer, cancel, booking UI | **Done** (user signed off) | U-B1–U-B7, I-B1–I-B5 ✅ |
| **MVP-C** | Payment happy path | **Next** | U-C1–U-C6, I-C1–I-C3 |
| **MVP-D** | Payment edge cases | Not started | U-D1–U-D5, I-D1–I-D4 |
| **MVP-E** | E2E polish | Not started | E-E1–E-E7 |

---

## MVP-A — Complete ✅

**Commit:** `e18edbf` — `feat(ui): add MVP-A read-only web UI and per-phase UI plan`

- Domain, in-memory repos, seed (flights **101**, **102**, 10×6 grid)
- `GET /api/v1/flights`, `GET /api/v1/flights/{id}/seats`
- Read-only UI: flight list, seat map, legend, refresh, departed banner

---

## MVP-B — Complete ✅

**Commit:** `6f79c25` — `feat(mvp-b): add seat holds, timer, cancel, and booking UI`  
**Manual sign-off:** 2026-05-26 (including two-browser hold conflict / grayscale check)

### Backend

| Area | Location | Notes |
|------|----------|-------|
| Order domain | `domain/order.go` | `OrderStatus`, `IsTerminal()` |
| Workflow | `internal/workflow/booking/` | Holds, 15m timer, cancel, expiry |
| Activities | `activities.go` | `HoldSeats`, `ReleaseSeats` |
| Temporal | `internal/infrastructure/temporal/` | `OrderService`, embedded dev server |
| Bootstrap | `internal/app/application.go` | Repos + worker in-process |
| Order API | `internal/api/handler/orders.go` | CRUD + cancel |
| Worker | `cmd/worker/main.go` | Standalone (API embeds worker for in-memory MVP) |

**API endpoints:**

- `POST /api/v1/orders`
- `PATCH /api/v1/orders/{id}/seats`
- `POST /api/v1/orders/{id}/cancel`
- `GET /api/v1/orders/{id}`

**Design notes:**

- Workflow ID == `order_id` (UUID)
- Seat changes via **Temporal workflow updates** (`UpdateSeats`, `CancelOrder`) for sync HTTP responses
- Hold conflicts are **non-retryable** → HTTP **409**
- `HOLD_DURATION` env (default `15m`; tests use `30s` / `2s`)
- `TEMPORAL_AUTO_DEV=1` (default) embeds Temporal dev server when `TEMPORAL_HOST` is unavailable
- In-memory repos shared in **one process** (`go run ./cmd/api`)

### UI

- Flight click → `POST /orders` → `localStorage`
- Interactive seat map, confirm → `PATCH .../seats`
- Hold timer countdown (client-side)
- Own holds highlighted (blue); others' HELD/BOOKED grayscale
- Cancel order; single active order guard on flight list

### Tests

All MVP-B tests pass (`go test ./...`).

---

## MVP-C — Next (not started)

See [final_plan.md](final_plan.md) § MVP-C.

**Backend:** `ValidatePayment`, `ConfirmSeats`, `SubmitPayment` signal, `POST .../payment`, `payment_events` in query.

**UI:** Payment form (5-digit code), submit, status strip, confirmation view.

**Tests:** U-C1–U-C6, I-C1–I-C3 (scenario **S-1** happy path via UI/API).

---

## Run locally (Windows)

```powershell
$env:Path = "C:\Program Files\Go\bin;" + $env:Path
cd c:\Users\YanSh\Dev\Neon
go run ./cmd/api
# → http://localhost:8080
```

Optional: `$env:HOLD_DURATION = "2m"` for faster timer testing.

If port 8080 is busy: `netstat -ano | findstr ":8080"` then `Stop-Process -Id <PID> -Force`, or `$env:API_ADDR = ":8081"`.

---

## Agent handoff — copy to next AI agent

Use this block when onboarding a new agent:

> **Continue Neon on branch `dev`.** MVP-A and MVP-B are complete; user signed off MVP-B manually.  
> **Next task: MVP-C (payment happy path) only** per `docs/final_plan.md` § MVP-C.  
> Read `docs/progress.md`, `docs/final_plan.md`, and `docs/final_requierments.md` first.  
> Extend `BookingWorkflow` with `ValidatePayment`, `ConfirmSeats`, `SubmitPayment`; add `POST /api/v1/orders/{id}/payment` and payment UI.  
> Implement tests **U-C1–U-C6** and **I-C1–I-C3**; run `go test ./...` before finishing.  
> **Layering:** Gin handlers → Temporal client only; seat/payment side effects in activities → repository interfaces.  
> **Process:** one phase at a time; provide manual test steps; **do not start MVP-D until user confirms.**  
> Commit when tests are green (user will request push separately).

### Suggested first steps

1. Read `internal/workflow/booking/workflow.go` and `docs/final_plan.md` §2.5 (workflow signals, payment rules).
2. Add payment activities with injectable RNG for 15% failure (plan §9 test tooling).
3. Wire `POST .../payment` in `internal/api/handler/orders.go`.
4. Add payment page/flow in `internal/web/static/` (after seat confirmation).
5. Update this file when MVP-C starts/completes.

### Architecture reminders

| Layer | Path | Must not |
|-------|------|----------|
| Presentation | `internal/api/`, `internal/web/` | Mutate seats directly; business rules |
| Service | `internal/workflow/booking/` | HTTP types |
| Data | `internal/infrastructure/memory/` | HTTP, workflow signals |

Temporal: namespace `flight-booking`, task queue `booking-task-queue`.

---

## Git state

```text
Branch: dev
Latest commits:
  6f79c25 feat(mvp-b): add seat holds, timer, cancel, and booking UI
  e18edbf feat(ui): add MVP-A read-only web UI and per-phase UI plan
```

Push when ready: `git push origin dev`

---

## Future phases (after MVP-C)

| Phase | Focus |
|-------|-------|
| **MVP-D** | Payment edge cases (3 methods, timer/payment race S-3/S-4) |
| **MVP-E** | Playwright E2E, responsive polish |

See [final_plan.md](final_plan.md) §8 for per-phase UI deliverables.
