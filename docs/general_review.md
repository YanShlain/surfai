# Engineering Manager Code Review — Neon Flight Booking System

**Reviewer:** Engineering Manager (SWE Audit)
**Date:** 2026-05-29
**Codebase state:** As-is at time of review — `final_review.md` referenced as QA baseline

---

## Engineering Manager Evaluation Matrix

| Dimension | Grade | Notes |
|---|---|---|
| **Concurrency Safety** | B | Per-flight mutex granularity is correct. The `TryHold` read→write phase split under two different lock levels introduces manual unlock calls on every early-return path — a latent maintenance landmine. No deadlock in current code, but one missed `RUnlock()` in a future change will silently freeze the service. |
| **Architectural Decoupling** | A- | `domain.SeatRepository` interface is clean. The three-tier layer separation (domain / infrastructure / presentation) is well-executed. Minor leak: `isValidPaymentCode` is duplicated between the booking package and the HTTP handler. Not a structural break, but a DRY violation in a place that matters. |
| **State Reliability** | C+ | This is the weakest point. In-memory state with Temporal history diverges completely after a worker restart. No compensating mechanism exists. The Signal+polling pattern for payment is the wrong Temporal primitive and generates up to 480 `QueryWorkflow` calls per payment attempt. |
| **Go Idiomatic Quality** | B+ | Solid overall. `workflow.Now`, `workflow.NewTimer`, typed sentinel errors, injected RNG for test determinism — these are all correct. Deducted for: `time.Sleep` ignoring context in the payment activity, `applySeatUpdate` setting `SEATS_HELD` on an empty seat list, and the `maxFailuresPerCode` name lying about its actual semantics. |

**Overall verdict: Senior Engineer — not Tech Lead.** The architecture is sound and the Temporal integration is mostly correct. What keeps it from Tech Lead grade is a combination of patterns that create silent failure modes rather than explicit, defensive ones, plus at least one wrong Temporal primitive choice.

---

## Ruthless Code Review Findings

### CRITICAL — C1: `TryHold` manual unlock pattern is a time-bomb

**File:** `internal/infrastructure/memory/seat_repository.go`, lines 100–128

```go
r.mu.RLock()
seats, ok := r.flights[flightID]
if !ok {
    r.mu.RUnlock()   // exit path 1
    return fmt.Errorf(...)
}
for _, seatID := range seatIDs {
    seat, found := seats[seatID]
    if !found {
        r.mu.RUnlock()   // exit path 2
        return fmt.Errorf(...)
    }
    if seat.Status != domain.SeatStatusAvailable {
        r.mu.RUnlock()   // exit path 3
        return ErrHoldConflict
    }
}
r.mu.RUnlock()   // happy path exit

r.mu.Lock()
defer r.mu.Unlock()
```

There are **four manual `r.mu.RUnlock()` calls** protecting three early returns and one fall-through. This is not how Go mutex hygiene works. The idiomatic pattern is to encapsulate the read-check phase in a closure that uses `defer r.mu.RUnlock()`, then return to the write phase. As-is, any future contributor adding one more early return inside that loop — which is the most natural place to add validation — silently locks the global RWMutex forever. This will manifest as the entire service hanging with zero error messages, and the root cause will be invisible in stack traces.

The underlying logic is actually correct (per-flight mutex prevents concurrent writes, so the gap between `RUnlock` and `Lock` is safe), but the implementation is fragile by construction.

Additionally: the `seats` variable captured under `r.mu.RLock()` is a `map[string]domain.Seat` reference. The write phase then does `r.flights[flightID][seatID]` — it re-indexes into the exact same map. The double-lookup is unnecessary; you could write directly to `seats[seatID]` in the write phase since it's the same map.

---

### CRITICAL — C2: Worker crash causes permanent state divergence with no detection

**Files:** `internal/infrastructure/memory/seat_repository.go` (entire), `internal/app/bootstrap.go`

If the worker pod restarts (OOM kill, deploy, crash), the in-memory `SeatRepository` is wiped clean. Temporal will **not** re-execute activities that already have results in workflow history. The result:

- Temporal history says: `HoldSeats(NA4821, 1A, order-xyz)` → succeeded
- In-memory repo says: seat 1A → `AVAILABLE`
- A new user can now hold seat 1A on a different order
- When the original workflow eventually calls `ConfirmSeats`, the `Confirm` method checks `seat.OrderID != orderID` and returns `ErrInvalidConfirm` — which is a **non-retryable application error** that terminates the workflow with an error, not a clean `PAYMENT_FAILED` state
- Seats for the original order are never released (the `releaseHeldSeats` call inside `completePaymentValidation` only runs on success, and the error path returns immediately)

There is **no startup replay, no health check that verifies repo/workflow consistency, and no warning log that the system is operating without persistence**. This isn't just a known limitation — it's a silent double-booking vector under any operational condition that causes a restart.

---

### HIGH — H1: Payment uses Signal + polling instead of Workflow Update

**File:** `internal/infrastructure/temporal/order_service.go`, lines 110–165

Payment submission is implemented as:
1. Pre-check `GetStatus`
2. `SignalWorkflow` (fire-and-forget)
3. Polling loop at **25ms** intervals with a 12-second deadline

At 25ms per query, this is up to **480 `QueryWorkflow` RPCs per payment request**. Under concurrent load (say 50 users simultaneously paying), that is 24,000 Temporal query RPCs per second from a single API pod. Temporal's query path is not designed for this polling frequency.

The correct primitive here is `workflow.Update`, which is already used for seat management. An Update is synchronous, returns a typed result, and requires exactly one RPC round-trip. The seat management path demonstrates the candidate knows how to use Updates — the choice to use Signal for payment is inconsistent and architecturally inferior.

The polling convergence logic (`paymentProcessingSettled`) is also fragile: it counts `PaymentEvents` and compares status transitions. It works because the state machine prevents concurrent payment submissions (AWAITING_PAYMENT guard), but it breaks if that guard is ever relaxed.

---

### HIGH — H2: `maxFailuresPerCode` is a naming lie

**File:** `internal/workflow/booking/payment.go`, line 12; `workflow.go`, line 295

```go
const maxFailuresPerCode = 3
```

The name implies per-code attempt tracking. The actual behavior is a **global total failure counter** (`state.PaymentFailures`) that never resets regardless of which code is submitted. Submit code `11111` twice, then submit code `22222` → third failure → `PAYMENT_FAILED`. This is confirmed in `final_review.md` as a requirements gap (S-3 cannot be demonstrated).

The name `maxFailuresPerCode` was almost certainly chosen during an early design phase when per-code tracking was planned, then the implementation was simplified without renaming the constant. The constant name actively misleads any engineer reading the code, including the candidate themselves during debugging.

Rename it `maxPaymentFailures` to match its actual semantics, or implement the 3-attempts-per-method × 3-methods model as the locked requirements specify.

---

### HIGH — H3: `time.Sleep` ignores activity context

**File:** `internal/workflow/booking/activities.go`, lines 58–62

```go
if raw := os.Getenv("PAYMENT_VALIDATION_DELAY"); raw != "" {
    if delay, err := time.ParseDuration(raw); err == nil && delay > 0 {
        time.Sleep(delay)
    }
}
```

`time.Sleep` cannot be interrupted by context cancellation. The `ValidatePayment` activity has a `StartToCloseTimeout` of 10 seconds. If `PAYMENT_VALIDATION_DELAY=15s` is set (a natural choice for integration testing), the activity will time out at 10 seconds but the goroutine remains blocked in `time.Sleep` for 5 more seconds. Under load, this creates goroutine accumulation in the activity worker. In a container environment this silently inflates memory.

---

### MEDIUM — M1: `isValidPaymentCode` duplicated across package boundary

**Files:** `internal/workflow/booking/payment.go` line 70; `internal/api/handler/orders.go` line 275

Identical logic, different packages, no shared reference. The HTTP handler validates the payment code format before signaling the workflow. The workflow activity validates it again. The domain rule "5 numeric digits" lives in two places. When the requirements change (e.g., 6-digit codes for business customers), a developer will find one and miss the other. This belongs in the `domain` package or at minimum in a single shared utility.

---

### MEDIUM — M2: `applySeatUpdate` sets `SEATS_HELD` on empty seat list

**File:** `internal/workflow/booking/workflow.go`, lines 330–356

```go
func applySeatUpdate(ctx workflow.Context, state *workflowState, seatIDs []string) error {
    // ...releases old seats...
    // ...holds new seats (if non-empty)...
    state.HeldSeatIDs = cloneStrings(seatIDs)
    state.Status = domain.OrderStatusSeatsHeld  // always SEATS_HELD
    state.TimerDeadline = workflow.Now(ctx).Add(state.HoldDuration)
    return nil
}
```

If `PATCH /seats` is called with `{"seat_ids": []}`, all current seats are released, `HeldSeatIDs` becomes nil, and `Status` is set to `SEATS_HELD`. The state machine should transition back to `CREATED` when no seats are held. The timer reset is also questionable here — why reset to 15 minutes when the user just released all seats? The design doc says timer refresh happens on seat updates, but the spirit of that rule is "when seats are being held."

This is currently benign (you can still submit payment to `SEATS_HELD` with empty `HeldSeatIDs` and the activity `ConfirmSeats` returns early with no-op) but it creates an inconsistent state that will surprise future engineers.

---

### MEDIUM — M3: `RejectInFlightPayment` activity is a no-op

**File:** `internal/workflow/booking/activities.go`, lines 70–75

```go
func (a *Activities) RejectInFlightPayment(ctx context.Context, in PaymentValidationInput) error {
    if !isValidPaymentCode(in.Code) {
        return temporal.NewNonRetryableApplicationError(...)
    }
    return nil
}
```

This activity:
1. Validates the payment code format — by the time it is called, `state.CurrentCode` was already validated by `startPaymentValidation`, so this check always passes.
2. Does nothing else. Returns nil.

The comment says it "simulates refund when the hold timer wins over in-flight validation." There is no refund simulation. The activity is a Temporal round-trip (serialized into history, dispatched to worker, executed, result recorded) that accomplishes nothing. Remove the activity and inline the state update directly in `rejectInFlightPayment` in the workflow. This is a Temporal history bloat for zero value.

---

### MEDIUM — M4: Scattered manual logging instead of middleware

**File:** `internal/api/handler/orders.go`

Every handler has two manual `slog.Info` calls: one on entry and one at each exit point. The `CreateOrder` handler has THREE logging sites for the error path alone (bind error, create failure, and success). The `writeOrderError` helper logs with `slog.Error` and then the handler also logs the response code separately.

This pattern prevents adding cross-cutting concerns (request IDs, latency, trace context) without touching every handler. The standard pattern is a single Gin middleware:

```go
func RequestLogger() gin.HandlerFunc {
    return func(c *gin.Context) {
        start := time.Now()
        c.Next()
        slog.Info("http",
            "method", c.Request.Method,
            "path", c.Request.URL.Path,
            "status", c.Writer.Status(),
            "latency_ms", time.Since(start).Milliseconds(),
            "request_id", c.GetHeader("X-Request-ID"),
        )
    }
}
```

The current logging approach would require touching every handler file to add a `request_id` field. That is not production-ready observability infrastructure.

---

### LOW — L1: `domain.ErrInvalidRelease` is not in the domain package

**File:** `internal/infrastructure/memory/seat_repository.go`, line 21

```go
ErrInvalidRelease = errors.New("seat not held by order")
```

The `Release` function can return this error. Any caller that wants to distinguish "seat not found" from "seat held by wrong order" must import the `memory` package, breaking the domain abstraction. The `domain` package already has `ErrHoldConflict` and `ErrInvalidConfirm`; `ErrInvalidRelease` belongs there too. As written, activities silently propagate this error as a generic Temporal error because `HoldSeats` and `ReleaseSeats` only check for `domain.ErrHoldConflict` and `domain.ErrInvalidConfirm`.

---

### LOW — L2: Per-flight mutex blast radius under adversarial load

**File:** `internal/infrastructure/memory/seat_repository.go` (locking design)

The per-flight `sync.Mutex` (`flightMu[flightID]`) serializes all write operations on a single flight. There is no timeout. An attacker issuing high-frequency `PATCH /seats` requests against a single popular flight (`NA4821`) will queue activity goroutines behind this lock indefinitely. Temporal's default `MaxConcurrentActivityExecutionSize` is 1,000 — that's 1,000 goroutines potentially parked on one flight's mutex.

More critically: `TryHold`, `Release`, and `Confirm` all take `r.mu.Lock()` (the **global** write lock) during the mutation phase. A write on any flight blocks `ListByFlight` reads (which use `r.mu.RLock()`) for **all flights**. A targeted write DoS on one flight degrades the seat-map read latency for all flights in the system.

For a production system, the `r.mu.Lock()` in write methods should be removed entirely — the per-flight mutex is sufficient to protect the flight's map slice from concurrent modification, and map reads from other flights do not need to be blocked.

---

### LOW — L3: Three integration tests are failing

**File:** `internal/api/order_integration_test.go`, lines 762, 786, 830

`TestI_D7`, `TestI_D8`, `TestI_D10` assert HTTP 400 from `POST /payment/new-method`. The route was deleted; these tests now receive 404. The fix is one-line: update the expected status code to 404, or add a stub route. These tests should not exist in this state at submission time.

---

## Production Refactoring Prescription

### Fix 1 — `TryHold`: replace manual unlocks with a validation closure

The current pattern requires remembering to call `r.mu.RUnlock()` in every exit path. The correct pattern separates the read-check phase into a scoped closure where `defer` handles cleanup:

```go
func (r *SeatRepository) TryHold(ctx context.Context, flightID string, seatIDs []string, orderID string) error {
    mu, err := r.flightLock(flightID)
    if err != nil {
        return err
    }
    mu.Lock()
    defer mu.Unlock()

    // Read-check phase: validate all seats are available.
    // Scoped so defer handles the RUnlock on every exit.
    if err := r.checkAllAvailable(flightID, seatIDs); err != nil {
        return err
    }

    // Write phase: now safe to mutate — per-flight mu is held throughout,
    // so no other writer for this flight can have changed seat state.
    r.mu.Lock()
    defer r.mu.Unlock()
    for _, seatID := range seatIDs {
        seat := r.flights[flightID][seatID]
        seat.Status = domain.SeatStatusHeld
        seat.OrderID = orderID
        r.flights[flightID][seatID] = seat
    }
    return nil
}

func (r *SeatRepository) checkAllAvailable(flightID string, seatIDs []string) error {
    r.mu.RLock()
    defer r.mu.RUnlock()

    seats, ok := r.flights[flightID]
    if !ok {
        return fmt.Errorf("%w: %s", ErrFlightNotFound, flightID)
    }
    for _, seatID := range seatIDs {
        seat, found := seats[seatID]
        if !found {
            return fmt.Errorf("%w: %s", ErrSeatNotFound, seatID)
        }
        if seat.Status != domain.SeatStatusAvailable {
            return ErrHoldConflict
        }
    }
    return nil
}
```

---

### Fix 2 — Convert payment signal+poll to workflow Update

Remove the `SignalSubmitPayment` channel and replace with a synchronous Workflow Update. This eliminates the 480-query poll loop.

**In `workflow.go`:** Replace the `paymentCh` + `startPaymentValidation` / `completePaymentValidation` machinery:

```go
if err := workflow.SetUpdateHandler(ctx, UpdateSubmitPayment,
    func(updateCtx workflow.Context, req SubmitPaymentRequest) (StatusResponse, error) {
        if state.Status.IsTerminal() {
            return StatusResponse{}, temporal.NewApplicationError("order terminal", "terminal_order")
        }
        if state.Status != domain.OrderStatusSeatsHeld {
            return StatusResponse{}, temporal.NewApplicationError("payment not allowed", "payment_not_allowed")
        }
        if !isValidPaymentCode(req.Code) {
            return StatusResponse{}, temporal.NewApplicationError("invalid code", "invalid_payment_code")
        }

        state.CurrentCode = req.Code
        state.Status = domain.OrderStatusAwaitingPayment

        err := workflow.ExecuteActivity(paymentActivityCtx(updateCtx),
            (*Activities).ValidatePayment,
            PaymentValidationInput{Code: req.Code},
        ).Get(updateCtx, nil)

        // completePaymentValidation inline — no future tracking needed
        if err == nil {
            // ... confirm seats, set CONFIRMED
        } else {
            state.PaymentFailures++
            if state.PaymentFailures >= maxPaymentFailures {
                return StatusResponse{}, failOrderPaymentExhausted(activityCtx(updateCtx), &state, req.Code)
            }
            // ... append failure event, revert to SEATS_HELD
        }
        notifyTimerReset() // wake the selector loop to re-arm the timer
        return state.toResponse(workflow.Now(ctx)), nil
    },
); err != nil {
    return err
}
```

**In `order_service.go`:** Replace `SignalWorkflow` + polling with a single `UpdateWorkflow` call (same pattern as `UpdateSeats`).

This cuts payment RPC cost from ~480 queries to 1 update call.

---

### Fix 3 — Implement the 3-method × 3-attempts payment model

Rename the misleading constant and add per-method tracking to `workflowState`:

```go
const (
    maxAttemptsPerMethod = 3
    maxPaymentMethods    = 3
)

type workflowState struct {
    // ... existing fields ...
    CurrentCode         string
    CurrentCodeFailures int  // attempts on the current code
    MethodsUsed         int  // distinct codes attempted
    PaymentFailures     int  // total failures (informational)
    // ...
}
```

In `completePaymentValidation`, replace the total-failure check:

```go
state.PaymentFailures++
state.CurrentCodeFailures++

if state.CurrentCodeFailures >= maxAttemptsPerMethod {
    // Current code is exhausted — consume a method slot.
    state.MethodsUsed++
    state.CurrentCodeFailures = 0
    state.CurrentCode = ""

    if state.MethodsUsed >= maxPaymentMethods {
        return failOrderPaymentExhausted(ctx, state, code)
    }
    // Not yet exhausted — allow a new code (stay in SEATS_HELD).
    state.appendPaymentEvent(PaymentEvent{
        Type:    PaymentEventAttemptsExhausted,
        Code:    code,
        Message: fmt.Sprintf("code %s exhausted (%d/%d methods used)", code, state.MethodsUsed, maxPaymentMethods),
    })
}
```

Expose `MethodsUsed` and `MethodsRemaining` in `StatusResponse` and `dto.OrderResponse` so the UI counters stop showing 0/0.

---

### Fix 4 — Replace `time.Sleep` with context-aware wait in activity

```go
// Before (goroutine leak if ctx is cancelled):
time.Sleep(delay)

// After:
select {
case <-ctx.Done():
    return ctx.Err()
case <-time.After(delay):
}
```

---

### Fix 5 — Remove `RejectInFlightPayment` activity

The activity is a no-op Temporal round-trip. Replace the activity call with direct state mutation in the workflow:

```go
func rejectInFlightPayment(state *workflowState) {
    state.appendPaymentEvent(PaymentEvent{
        Type:    PaymentEventRejectedByTimer,
        Code:    state.CurrentCode,
        Message: "payment rejected because hold timer expired",
    })
    state.Status = domain.OrderStatusSeatsHeld
    state.CurrentCode = ""
    state.LastError = ""
}
```

Remove `(*Activities).RejectInFlightPayment` from `activities.go` and update the activity registration in `cmd/worker/main.go`. One fewer Temporal history event per S-4 scenario.

---

### Fix 6 — Replace scattered handler logging with middleware

In `internal/api/router.go`, add a single structured logging middleware before route registration and remove all inline `slog.Info("inbound request/response", ...)` calls from every handler:

```go
func New(h *handler.OrderHandler, fh *handler.FlightHandler) *gin.Engine {
    r := gin.New()
    r.Use(requestLogger())
    // ... routes ...
}

func requestLogger() gin.HandlerFunc {
    return func(c *gin.Context) {
        start := time.Now()
        c.Next()
        slog.Info("http",
            "method",     c.Request.Method,
            "path",       c.Request.URL.Path,
            "status",     c.Writer.Status(),
            "latency_ms", time.Since(start).Milliseconds(),
        )
    }
}
```

When you add OpenTelemetry or Datadog APM later, you add trace injection in **one place** — this middleware — not in 10 handler functions.

---

## Architectural Verdict

### Domain interface longevity

`domain.SeatRepository` is clean and will survive a PostgreSQL migration without leaking database logic. The four methods (`ListByFlight`, `TryHold`, `Release`, `Confirm`) map directly to `SELECT`, `SELECT … FOR UPDATE` + `UPDATE`, `UPDATE`, `UPDATE` patterns. The `context.Context` parameter is already threaded through, which is required for `pgx` connection pool propagation. No changes needed to the interface, the workflow, or the activities to swap the implementation.

One note: `TryHold` with a slice of seat IDs implicitly requires the implementation to check-and-set all seats atomically. With PostgreSQL, that's a `SELECT … FOR UPDATE WHERE seat_id = ANY($1)` + validation loop inside a transaction. The interface does not express the atomicity requirement. A future implementer could write a non-atomic PostgreSQL version that has the same TOCTOU bug the in-memory version almost has. Consider documenting the atomicity contract in the interface comment.

### Observability readiness

Not ready. Logging is hard-coded in handlers (see M4). There is no request ID propagation, no latency histogram, no error rate counter. The code structure does not prevent adding these things — the `gin.Engine` assembly in `router.go` is the right injection point — but the current handler logging would need to be stripped out in the same PR that adds proper middleware. That is a non-trivial refactor across 5+ handler functions.

### Rating: **Senior Engineer**

The architecture decisions are defensible and the Temporal integration is mostly correct. The selector-based workflow loop, the cancel/update handlers, the per-flight mutex granularity, and the injected `PaymentRNG` for test determinism all demonstrate solid Go and Temporal knowledge.

What prevents Tech Lead grade:

1. The `TryHold` lock pattern creates silent failure modes instead of defensive code. A Tech Lead thinks about what happens when the next engineer touches that file.
2. Using Signal+polling for payment when the codebase already demonstrates correct Update usage for seat management is an inconsistency that suggests incomplete Temporal API fluency.
3. `maxFailuresPerCode` naming lies. A Tech Lead either implements what the name says or renames the constant to match reality — they don't leave the mismatch in a submission.
4. `time.Sleep` without context respect in an activity is a production goroutine leak. That's a category of bug that does not appear in code written by engineers with production on-call experience.
5. No acknowledgement or mitigation of the in-memory crash recovery gap in the codebase itself (even a `slog.Warn("in-memory mode: workflow state will diverge on restart")` in bootstrap would demonstrate awareness).

Fix items C1, H1, H2, H3, and M1, submit a clean test run, and this is a solid Senior take-home. The foundation is good enough to build on.
