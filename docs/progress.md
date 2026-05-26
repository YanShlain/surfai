# Neon — Implementation Progress

**Last updated:** 2026-05-24  
**Branch:** `dev` (tracking `origin/dev`)  
**Canonical plan:** [docs/final_plan.md](docs/final_plan.md)

---

## Overall strategy

Implement phases **MVP-A → MVP-E** one at a time. After each phase:

1. All phase tests must pass (`go test ./...`)
2. User manually tests via UI/API
3. **Do not start the next phase until the user confirms**

---

## Phase status summary


| Phase     | Name                             | Status                        | Tests                  |
| --------- | -------------------------------- | ----------------------------- | ---------------------- |
| **MVP-A** | Flight catalog + read-only UI    | **Done** (committed)          | U-A1–U-A6, I-A1–I-A4 ✅ |
| **MVP-B** | Holds, timer, cancel, booking UI | **In progress** (uncommitted) | U-B6 ❌, I-B5 ❌; rest ✅ |
| **MVP-C** | Payment happy path               | Not started                   | —                      |
| **MVP-D** | Payment edge cases               | Not started                   | —                      |
| **MVP-E** | E2E polish                       | Not started                   | —                      |


---

## MVP-A — Complete ✅

**Last commit:** `e18edbf` — `feat(ui): add MVP-A read-only web UI and per-phase UI plan`

### Delivered

- Domain: `Seat`, `Flight`, `SeatRepository`, `FlightRepository`
- In-memory repos + seed (flights **101**, **102**, 10×6 grid)
- API: `GET /api/v1/flights`, `GET /api/v1/flights/{id}/seats`
- Static UI: flight list, read-only seat map, legend, refresh, departed banner
- Embedded static files via `internal/web/`

### How to run (still works on `dev` after pulling committed code)

```powershell
$env:Path = "C:\Program Files\Go\bin;" + $env:Path
go run ./cmd/api
# → http://localhost:8080
```

---

## MVP-B — In progress (~95%)

**State:** Implemented locally, **not committed**. Large uncommitted diff on `dev`.

### Delivered (code present, uncommitted)

#### Backend / Temporal


| Area            | Files                               | Notes                                                   |
| --------------- | ----------------------------------- | ------------------------------------------------------- |
| Order domain    | `domain/order.go`                   | `OrderStatus` + `IsTerminal()`                          |
| Workflow        | `internal/workflow/booking/`        | `BookingWorkflow`, hold timer, cancel, expiry           |
| Activities      | `.../activities.go`                 | `HoldSeats`, `ReleaseSeats`                             |
| Temporal client | `internal/infrastructure/temporal/` | `OrderService`, embedded dev server                     |
| App bootstrap   | `internal/app/application.go`       | Wires repos + Temporal worker in-process                |
| Order API       | `internal/api/handler/orders.go`    | POST/PATCH/GET orders, cancel                           |
| Worker binary   | `cmd/worker/main.go`                | Standalone worker (API embeds worker for in-memory MVP) |
| Dependencies    | `go.mod`                            | `go.temporal.io/sdk`, `github.com/google/uuid`          |


**API endpoints added:**

- `POST /api/v1/orders` — start workflow
- `PATCH /api/v1/orders/{id}/seats` — workflow update `UpdateSeats`
- `POST /api/v1/orders/{id}/cancel` — workflow update `CancelOrder`
- `GET /api/v1/orders/{id}` — query `GetStatus`

**Design choices:**

- Workflow ID == `order_id` (UUID)
- Sync seat changes via **Temporal workflow updates** (not async signals) so HTTP can return status/timer immediately
- `HOLD_DURATION` env (default `15m`; tests use `30s` or `2s`)
- `TEMPORAL_AUTO_DEV=1` (default in bootstrap) starts embedded Temporal dev server if nothing is on `TEMPORAL_HOST`
- API and worker share in-memory repos **in the same process** (`go run ./cmd/api`)

#### UI (MVP-B features)


| Feature                           | File(s)                             | Status |
| --------------------------------- | ----------------------------------- | ------ |
| Start booking on flight click     | `internal/web/static/js/flights.js` | Done   |
| `localStorage` order tracking     | `internal/web/static/js/api.js`     | Done   |
| Single active order guard         | `flights.js`, `index.html`          | Done   |
| Interactive seat selection        | `seats.js`                          | Done   |
| Confirm seats → PATCH             | `seats.js`                          | Done   |
| Hold timer countdown              | `seats.js`, `seats.html`            | Done   |
| Cancel order                      | `seats.js`                          | Done   |
| Own-hold highlight (`?order_id=`) | `seats.js` + API                    | Done   |


### Test results (last run: 2026-05-24)

```text
# MVP-A (still passing with MVP-B code)
I-A1 … I-A4                          PASS

# MVP-B unit (Temporal test suite)
U-B1 … U-B5, U-B7                    PASS
U-B6 HoldConflictSameFlight          FAIL

# MVP-B integration (httptest + embedded Temporal)
I-B1 … I-B4                          PASS
I-B5 HoldConflictReturns409          FAIL
```

Run tests:

```powershell
$env:Path = "C:\Program Files\Go\bin;" + $env:Path
cd c:\Users\YanSh\Dev\Neon
go test ./...
```

### Known issues — fix these first when resuming

#### 1. Hold conflict not surfaced as 409 (blocks I-B5, likely U-B6)

**Symptom:** Second order trying to hold an already-held seat gets **200** after ~30s instead of immediate **409**.

**Cause:** `HoldSeats` activity returns `memory.ErrHoldConflict`, but Temporal **retries** the activity (default retry policy). While retrying, the first order’s timer can expire and release the seat, so the second hold eventually succeeds.

**Fix direction:**

- Mark hold conflict as **non-retryable** in the activity/workflow, e.g. `temporal.NewNonRetryableApplicationError(..., "hold_conflict", err)` from the activity or map in workflow before returning to the update handler
- Ensure `OrderService.mapTemporalError` maps `hold_conflict` → `ErrHoldConflict` → HTTP **409** (handler already has this mapping)

**Relevant files:**

- `internal/workflow/booking/activities.go`
- `internal/workflow/booking/workflow.go` (`applySeatUpdate`)
- `internal/infrastructure/temporal/order_service.go` (`mapTemporalError`)
- `internal/api/handler/orders.go` (`writeOrderError`)

#### 2. U-B6 parallel workflow test

**Symptom:** `TestU_B6_HoldConflictSameFlight` fails (timing / two test envs / shared repo).

**Fix direction:** After (1) is fixed, assert update returns error immediately; simplify test to sequential workflows on shared `SeatRepository` without goroutine race.

### MVP-B exit criteria (from plan)

- U-B1–U-B7 all green
- I-B1–I-B5 all green
- Manual demo: create order → pick seats → timer → cancel/expiry via UI
- Commit MVP-B on `dev`
- User sign-off before MVP-C

---

## Git state (as of stop)

```text
Branch: dev (up to date with origin/dev)
Last commit: e18edbf (MVP-A only)

Uncommitted:
  Modified:  cmd/api/main.go, go.mod, go.sum, router, bootstrap, UI files, integration_test.go
  Untracked: cmd/worker/, domain/order.go, workflow/, temporal/, orders handler/dto/tests, application.go
```

**Important:** MVP-B work exists only in the working tree. Commit or stash before switching branches.

---

## Environment notes (Windows)

### Go on PATH

If `go` is not recognized:

```powershell
$env:Path = "C:\Program Files\Go\bin;" + $env:Path
# or permanently added to user PATH during setup
```

### Port 8080 in use

```powershell
netstat -ano | findstr ":8080"
Stop-Process -Id <PID> -Force
# or
$env:API_ADDR = ":8081"
```

### Run MVP-B locally

```powershell
$env:Path = "C:\Program Files\Go\bin;" + $env:Path
cd c:\Users\YanSh\Dev\Neon

# Optional: faster timer for manual testing
$env:HOLD_DURATION = "2m"

go run ./cmd/api
# → http://localhost:8080
```

Embedded Temporal dev server starts automatically (`TEMPORAL_AUTO_DEV=1` default in bootstrap). First start may download Temporal CLI (~1 min).

### Manual test checklist (MVP-B)

1. Open [http://localhost:8080](http://localhost:8080) — flight list loads
2. Click a flight — order created, redirect to seat map with timer
3. Select seats → **Confirm seat selection** — seats show as held (blue highlight)
4. Timer counts down from ~15:00 (or `HOLD_DURATION`)
5. **Refresh map** — own holds highlighted; others grayscale
6. **Cancel order** — seats released, `localStorage` cleared
7. Start second booking on same flight while first is active — blocked on flight list
8. Open two browsers — second user cannot hold same seat (409 once fixed)

---

## Next steps (ordered)

1. **Fix hold conflict → non-retryable + 409** (unblocks I-B5, U-B6)
2. **Re-run** `go test ./...` until all green
3. **Manual test** MVP-B via UI (checklist above)
4. **Wait for user confirmation** — do not start MVP-C
5. **Commit** MVP-B on `dev` with clear message, push when ready
6. **MVP-C:** payment activities, `SubmitPayment`, payment UI (see `docs/final_plan.md` § MVP-C)

---

## Future phases (not started)


| Phase     | Backend                                               | UI                                             |
| --------- | ----------------------------------------------------- | ---------------------------------------------- |
| **MVP-C** | `ValidatePayment`, `ConfirmSeats`, `POST .../payment` | Payment form, status strip, confirmation       |
| **MVP-D** | New-method signal, attempt tracking, S-4 race         | New-method button, events list, failure states |
| **MVP-E** | —                                                     | Playwright E2E, responsive polish              |


See [docs/final_plan.md](docs/final_plan.md) §8 for per-phase UI deliverables.

---

## Conversation / process notes

- User requested phased delivery with manual gate between phases
- User asked about parallel server/UI development — feasible from MVP-C onward once API contract is stable; MVP-B was built as one vertical slice
- Multitask subagent was started for MVP-B completion but did not finish before end of session

