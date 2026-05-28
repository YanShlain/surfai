# Code Review Summary

**Reviewer:** Senior Software Engineer / Tech Lead  
**Date:** 2026-05-28  
**Scope:** Booking Order Flow — all modified and new files in this diff  
**Files reviewed:** `internal/api/handler/orders.go`, `internal/api/order_integration_test.go`, `internal/api/router.go`, `internal/web/static/js/payment.js`, `internal/web/static/js/seats.js`, `internal/web/static/payment.html`, `internal/workflow/booking/payment.go`, `internal/workflow/booking/workflow.go`, `internal/workflow/booking/workflow_test.go`, `internal/api/dto/orders.go`, `internal/infrastructure/temporal/order_service.go`, `internal/workflow/booking/config.go`, `internal/workflow/booking/types.go`

---

## Overall Assessment

The implementation is **well-structured at a high level**. The Temporal workflow correctly models the order state machine, the test suites are broad, and the handler/service layering is sensible for an MVP. However there are **5 critical issues** that must be resolved before this can be considered production-ready, along with a cluster of high-severity gaps in logging, DIP compliance, and test correctness.

---

## Architecture & S.O.L.I.D. Compliance

### ✅ What is done well

- **Single Responsibility** — `OrderHandler`, `OrderService`, `BookingWorkflow`, and `Activities` each have a clear, distinct responsibility.
- **Open/Closed** — `PaymentRNG` interface enables injecting test doubles without modifying `Activities.ValidatePayment`.
- **Interface Segregation** — `domain.SeatRepository` and `domain.FlightRepository` are small and correctly segregated.
- **Liskov Substitution** — All repository interface implementations are interchangeable.
- 3-tier layout (Presentation → `OrderService` → Workflow/Activities) is present and generally respected.

### ❌ Dependency Inversion violations

**[CRITICAL] `workflow.go` imports `memory.ErrHoldConflict` directly**

```go
// internal/workflow/booking/workflow.go  line 11-12
import (
    ...
    "neon/internal/infrastructure/memory"
)
...
if errors.Is(err, memory.ErrHoldConflict) {   // line 351
```

The workflow (service layer) is importing a concrete infrastructure implementation. This couples the business logic to the in-memory store. If the seat store is swapped to Postgres, `memory.ErrHoldConflict` must be replaced everywhere it is referenced.

**Fix:** Move `ErrHoldConflict` (and `ErrFlightNotFound`, `ErrInvalidConfirm`) to the `domain` package. Have `memory` wrap or return those domain errors; the workflow never needs to import `memory`.

---

**[HIGH] `OrderHandler` and `NewRouter` accept `*temporal.OrderService` (concrete type)**

```go
// internal/api/handler/orders.go  line 20-21
type OrderHandler struct {
    orders *temporal.OrderService   // concrete, not an interface
}
```

```go
// internal/api/router.go  line 13
func NewRouter(flights domain.FlightRepository, seats domain.SeatRepository, orders *temporal.OrderService) *gin.Engine {
```

The handler is untestable in isolation — any unit test of the handler must stand up a real (or fake embedded) Temporal server. The `flights` and `seats` parameters correctly take interfaces; `orders` should too.

**Fix:** Define an `OrderService` interface in `internal/api/handler` (or `domain`) with the five methods (`CreateOrder`, `UpdateSeats`, `CancelOrder`, `SubmitPayment`, `GetStatus`). The concrete `temporal.OrderService` satisfies it automatically.

---

## Logging Gaps

### Inbound request logging (all handlers)

Current state — handlers log method + path on entry, and log errors on failure. What is missing:

| What | Status |
|------|--------|
| Method + path on entry | ✅ |
| Request body (redacted) on entry | ❌ Missing |
| Response status code on success | ❌ Missing |

**[HIGH]** POST `/api/v1/orders` (CreateOrder), PATCH `/api/v1/orders/:id/seats` (UpdateSeats), and POST `/api/v1/orders/:id/payment` (SubmitPayment) all accept a JSON body. None of them log that body before processing. Per the developer logging standard, every inbound external call must log URL, body (redacted), and the response status code returned.

Recommended pattern:
```go
slog.Info("inbound request",
    "method", c.Request.Method,
    "path",   c.Request.URL.Path,
    "body",   req,          // struct is safe — no secrets in these payloads
)
// ... handle ...
slog.Info("inbound response", "method", c.Request.Method, "path", c.Request.URL.Path, "status", statusCode)
```

### Outbound Temporal logging

All five Temporal operations (StartWorkflow, UpdateWorkflow ×2, SignalWorkflow, QueryWorkflow) have an entry-level `slog.Info` — ✅.

**[HIGH]** `CancelOrder.handle.Get()` error path has no log before returning:

```go
// internal/infrastructure/temporal/order_service.go  lines 99-103
var resp booking.StatusResponse
if err := handle.Get(ctx, &resp); err != nil {
    return booking.StatusResponse{}, mapTemporalError(err)  // ← no slog.Error!
}
```

All other `handle.Get()` calls in this file log the error. This one silently swallows it.

**[HIGH]** Payment processing timeout (line 147) is returned without logging:

```go
return last, fmt.Errorf("payment processing timeout")  // no slog.Error
```

This makes it invisible in production logs.

---

## Dead Code

**[HIGH] `IsTerminalStatus` in `handler/orders.go` (lines 215–218)**

```go
// IsTerminalStatus reports whether an order status cannot be modified.
func IsTerminalStatus(status string) bool {
    return domain.OrderStatus(status).IsTerminal()
}
```

This exported function is never called within the handler package, by the router, or by any test. The JavaScript uses its own local `isTerminalStatus` function. Remove it.

---

**[HIGH] `DescribeOrderStatus` in `order_service.go` (lines 255–258)**

```go
func DescribeOrderStatus(status domain.OrderStatus) string {
    return string(status)
}
```

A one-liner wrapper that is never called anywhere in the codebase. Remove it.

---

**[HIGH] `paymentActivityLimit = 10` in `payment.go` (line 13)**

```go
const (
    paymentFailureRate   = 0.15
    maxFailuresPerCode   = 3
    paymentActivityLimit = 10   // ← never referenced
)
```

`paymentActivityLimit` is defined but never used — not in `workflow.go`, not in `activities.go`. Remove it.

---

**[CRITICAL] Dead UI elements in `payment.html` + `payment.js`**

`payment.html` exposes two counters:
```html
<span>Methods used: <strong id="methods-used">0</strong></span>
<span>Methods remaining: <strong id="methods-remaining">0</strong></span>
```

`payment.js` populates them from `order.methods_used` and `order.methods_remaining`:
```js
const methodsUsed = order.methods_used ?? 0;
const methodsRemaining = order.methods_remaining ?? 0;
```

`OrderResponse` (and its backing `StatusResponse`) has **no** `methods_used` or `methods_remaining` fields. These counters always display `0` and provide misleading information to the user. Either remove the UI elements or wire them to real data.

---

## Resource Leak — `StreamOrder` never terminates for terminal orders

**[CRITICAL]**

```go
// internal/api/handler/orders.go  lines 161–174
for {
    select {
    case <-ctx.Done():
        return
    case <-ticker.C:
        status, err = h.orders.GetStatus(ctx, orderID)
        if err != nil {
            return
        }
        if !sendStatus(status) {
            return
        }
    }
}
```

Once an order reaches a terminal state (`CONFIRMED`, `EXPIRED`, `CANCELLED`, `PAYMENT_FAILED`), the SSE loop continues polling Temporal every second indefinitely. It only stops when the client disconnects. Under load this means one goroutine + one Temporal query per second per connected SSE client for the lifetime of each connection. The fix is one line:

```go
case <-ticker.C:
    status, err = h.orders.GetStatus(ctx, orderID)
    if err != nil { return }
    if !sendStatus(status) { return }
    if status.Status.IsTerminal() { return }   // ← add this
```

---

## Payment Polling — `time.Sleep` is not context-aware

**[HIGH]**

```go
// internal/infrastructure/temporal/order_service.go  lines 135–148
deadline := time.Now().Add(12 * time.Second)
var last booking.StatusResponse
for time.Now().Before(deadline) {
    last, err = s.GetStatus(ctx, orderID)
    ...
    time.Sleep(25 * time.Millisecond)   // ← blocks goroutine, ignores ctx
}
```

If the HTTP client cancels the request (`ctx.Done()`), `time.Sleep` does not unblock. The goroutine continues polling for up to 12 seconds after the request is gone, holding a connection to Temporal. Replace with a select:

```go
timer := time.NewTimer(12 * time.Second)
defer timer.Stop()
tick := time.NewTicker(25 * time.Millisecond)
defer tick.Stop()
for {
    select {
    case <-ctx.Done():
        return last, ctx.Err()
    case <-timer.C:
        slog.Error("payment processing timeout", "order_id", orderID)
        return last, fmt.Errorf("payment processing timeout")
    case <-tick.C:
        last, err = s.GetStatus(ctx, orderID)
        ...
    }
}
```

---

## Test Coverage Gaps

### Integration tests — false-positive tests for non-existent endpoint

**[CRITICAL]**

`TestI_D7_NewMethodRejected`, `TestI_D8_NewMethodRejectedAfterFailures`, and `TestI_D10_NewMethodBeforeFirstPaymentRejected` all call `startNewPaymentMethod`, which posts to:

```go
srv.URL + "/api/v1/orders/" + orderID + "/payment/new-method"
```

This route **does not exist in the router**. Gin returns HTTP 404. The tests assert `codeHTTP != http.StatusBadRequest` (400), so 404 satisfies the assertion and the tests pass — but for the wrong reason. These tests provide zero confidence about the intended behavior.

**Fix:** Either (a) add the endpoint to the router and implement the 400 rejection, or (b) delete these tests and document why the feature is out of scope.

---

### Integration test `TestI_D2` accepts HTTP 200 on an expired order

```go
// line 640
if result.code != http.StatusGone && result.code != http.StatusOK {
    t.Fatalf(...)
}
```

This assertion accepts a 200 response even after the order has expired. If a timing race causes payment to be processed before the expiry signal propagates, the test will silently pass with incorrect behavior. The assertion should be strict:

```go
if result.code != http.StatusGone {
    t.Fatalf("payment response on expired order = %d, want 410", result.code)
}
```

---

### Integration test `TestI_B2` uses fragile string matching

```go
// line 181
if !strings.Contains(string(raw), `"seat_id":"1A"`) && !strings.Contains(string(raw), `"seat_id": "1A"`) {
    t.Fatalf(...)
}
```

This only verifies the seat ID is present in the response, not that its status is `HELD` and assigned to the correct order. Decode the JSON properly to assert both presence and status, as done in `TestI_B3_CancelOrderReleasesSeats`.

---

### Missing workflow unit tests

| Scenario | Covered |
|----------|---------|
| `UpdateSeats` when `status == AWAITING_PAYMENT` → `payment_in_progress` error | ❌ |
| Payment signal when no seats held (`status == CREATED`) → `payment not allowed` event | ❌ |
| `UpdateSeats` after terminal status (e.g. `EXPIRED`) → `terminal_order` error | ❌ |
| Cancel of an already-cancelled order → should be idempotent (returns terminal state) | ❌ |

The `UpdateUpdateSeats` update handler explicitly guards `AWAITING_PAYMENT` and terminal states (lines 73–84 of `workflow.go`) but neither condition is tested by a unit test. `TestI_C6`/`TestI_C3` cover some of this at the integration level, but unit tests for these branches are missing.

---

### Missing unit tests for `isValidPaymentCode`

`isValidPaymentCode` is defined in both `payment.go` (workflow) and duplicated in `handler/orders.go` (see below). Neither file has a dedicated unit test for the function's edge cases (empty string, 4-digit, 6-digit, unicode digits, leading zero).

---

## Code Duplication

**[MEDIUM] `isValidPaymentCode` is defined twice**

```go
// internal/workflow/booking/payment.go  lines 71–80
func isValidPaymentCode(code string) bool { ... }

// internal/api/handler/orders.go  lines 220–229
func isValidPaymentCode(code string) bool { ... }
```

The handler validates the code before sending it to the workflow, and the workflow also validates it internally. This is a reasonable defense-in-depth pattern, but the function body is copy-pasted. Extract it to a shared location (e.g. `domain` or a new `internal/validation` package) with a single set of tests.

---

## Minor Issues

### `seqFailRNG` in tests is not mutex-protected

`seqPaymentRNG` (production, `payment.go` L36) has a `sync.Mutex`. The test-only `seqFailRNG` (`workflow_test.go` L320) does not. Temporal's test environment runs activities synchronously in a single goroutine so this is safe in practice, but the inconsistency is a maintenance trap.

---

### Redundant `exc_info` field in error logs

```go
slog.Error("create order failed", "flight_id", req.FlightID, "error", err, "exc_info", err)
```

The `error` and `exc_info` keys carry the same value. The `exc_info` naming is a Python convention (`exc_info=True` for stack traces). In Go/slog there is no stack-trace capture mechanism attached to a key name; both fields just stringify the error. Drop `"exc_info", err` from all log calls — it adds noise without value.

---

### `paymentActivityTimeout` (10 s) is at risk when `PAYMENT_VALIDATION_DELAY=10s`

`ValidatePayment` activity has a 10-second `StartToCloseTimeout` (workflow.go L17). Integration test `TestU_D4` sets `PAYMENT_VALIDATION_DELAY=10s`, which is exactly at the boundary. In a slow CI environment this will cause spurious timeouts. Either raise `paymentActivityTimeout` to `15s` or document that `PAYMENT_VALIDATION_DELAY` must be less than `paymentActivityTimeout`.

---

### PATCH semantics vs PUT semantics

`PATCH /api/v1/orders/:order_id/seats` performs a complete replacement of the seat set, not a partial update. Strictly speaking this is PUT semantics. This is a minor point, but the HTTP spec distinction matters for cache invalidation and idempotency semantics. Consider renaming to `PUT` or accepting a `delta` payload for true PATCH behavior.

---

### `config.go` alignment

```go
const (
    WorkflowName        = "BookingWorkflow"
    TaskQueue            = "booking-task-queue"
    Namespace            = "flight-booking"
    QueryGetStatus       = "GetStatus"
    UpdateUpdateSeats    = "UpdateSeats"
    UpdateCancelOrder    = "CancelOrder"
    SignalSubmitPayment = "SubmitPayment"    // ← off-alignment
)
```

`SignalSubmitPayment` is one space short of the alignment. Minor, but `gofmt`/`goimports` would not flag this — it only matters for readability. Fix the alignment.

---

### `UpdateUpdateSeats` constant name is awkward

```go
UpdateUpdateSeats = "UpdateSeats"
```

The constant name `UpdateUpdateSeats` is a stutter. Rename to `UpdateSeats` (the constant) to match the string value, or `UpdateNameSeats` to clarify it is an update handler name.

---

## Summary of Findings by Severity

| # | Severity | File | Issue |
|---|----------|------|-------|
| 1 | 🔴 Critical | `workflow.go` | Imports `memory.ErrHoldConflict` — DIP violation |
| 2 | 🔴 Critical | `payment.html` / `payment.js` | `methods_used` / `methods_remaining` UI fields have no backing API data |
| 3 | 🔴 Critical | `handler/orders.go` | `StreamOrder` never exits for terminal orders — goroutine/resource leak |
| 4 | 🔴 Critical | `order_integration_test.go` | Tests I-D7, I-D8, I-D10 test a non-existent endpoint — false positives |
| 5 | 🔴 Critical | `handler/orders.go` + `router.go` | `OrderHandler` depends on concrete `*temporal.OrderService`, not an interface |
| 6 | 🟠 High | All handlers | Inbound request body not logged; response status not logged on success |
| 7 | 🟠 High | `order_service.go` | `CancelOrder.handle.Get()` error not logged |
| 8 | 🟠 High | `order_service.go` | Payment processing timeout not logged |
| 9 | 🟠 High | `order_service.go` | `SubmitPayment` uses `time.Sleep` — not context-aware, holds goroutine after client disconnect |
| 10 | 🟠 High | `handler/orders.go` | `IsTerminalStatus` — exported dead function |
| 11 | 🟠 High | `order_service.go` | `DescribeOrderStatus` — exported dead function |
| 12 | 🟠 High | `payment.go` | `paymentActivityLimit` constant — unused dead code |
| 13 | 🟡 Medium | `order_integration_test.go` | `TestI_D2` accepts HTTP 200 on expired order — assertion too lenient |
| 14 | 🟡 Medium | `order_integration_test.go` | `TestI_B2` uses fragile `strings.Contains` for seat status check |
| 15 | 🟡 Medium | `workflow_test.go` | Missing unit tests: `UpdateSeats` in `AWAITING_PAYMENT`, payment with no seats held, `UpdateSeats` after terminal |
| 16 | 🟡 Medium | `payment.go` / `handler/orders.go` | `isValidPaymentCode` duplicated in two packages with no shared tests |
| 17 | 🟡 Medium | `order_service.go` | 12-second payment polling deadline is hardcoded, not configurable |
| 18 | 🔵 Low | `workflow_test.go` | `seqFailRNG` not mutex-protected (unlike production counterpart) |
| 19 | 🔵 Low | `workflow.go` | `paymentActivityTimeout` (10s) at boundary risk with `PAYMENT_VALIDATION_DELAY=10s` |
| 20 | 🔵 Low | All log call sites | Redundant `"exc_info", err` field alongside `"error", err` |
| 21 | 🔵 Low | `config.go` | `SignalSubmitPayment` alignment; `UpdateUpdateSeats` stutter in constant name |
| 22 | 🔵 Low | `router.go` | `PATCH` used for full-replacement semantics (should be `PUT`) |

---

## Recommended Action Order

1. **Fix the false-positive tests (I-D7/D8/D10)** — they give misleading confidence before anything else is fixed.
2. **Add terminal-state exit to `StreamOrder`** — prevents goroutine leaks under any load.
3. **Move `ErrHoldConflict` to `domain`** — unblocks switching the seat store later.
4. **Remove dead code** (`IsTerminalStatus`, `DescribeOrderStatus`, `paymentActivityLimit`) — reduces noise before the next PR.
5. **Wire dead UI elements or remove them** (`methods_used`/`methods_remaining`).
6. **Replace `time.Sleep` with context-aware select in `SubmitPayment`**.
7. **Add missing log statements** (inbound bodies, success status codes, `CancelOrder.handle.Get`, payment timeout).
8. **Define `OrderService` interface** for the handler to depend on.
9. **Add missing unit tests** (AWAITING_PAYMENT guard, no-seats payment, terminal UpdateSeats).
