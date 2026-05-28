# Final QA Review — Flight Booking System

**Reviewer:** QA Engineer (AI)
**Date:** 2026-05-28
**Source of truth:** `docs/initial_requirements.md` + `docs/final_requierments.md` (LOCKED)
**Verdict:** ❌ NOT READY TO DELIVER — 3 failing tests + 1 significant requirements gap

---

## Executive Summary

The system implements the core booking flow correctly: Temporal workflow, 15-minute seat hold, payment validation with retry, real-time SSE, multi-flight isolation, and graceful failure handling. However, **3 integration tests are currently failing** and there is **one significant mismatch** between the locked final requirements and the implementation regarding the multi-method payment model.

---

## Test Execution Results

### Run: `go test ./... -timeout 120s`

| Package | Result | Tests |
|---------|--------|-------|
| `neon/internal/workflow/booking` | ✅ PASS | 17/17 |
| `neon/internal/infrastructure/memory` | ✅ PASS | all |
| `neon/internal/api` | ❌ FAIL | 3 failures |

### Failing Tests

| Test | File | Root Cause |
|------|------|------------|
| `TestI_D7_NewMethodRejected` | `order_integration_test.go:762` | `POST /payment/new-method` returns **404** (route deleted), test expects **400** |
| `TestI_D8_NewMethodRejectedAfterFailures` | `order_integration_test.go:786` | Same — 404 vs expected 400 |
| `TestI_D10_NewMethodBeforeFirstPaymentRejected` | `order_integration_test.go:830` | Same — 404 vs expected 400 |

**Root cause:** The `/api/v1/orders/:order_id/payment/new-method` route was removed from the router (see `requirements_mismatches.md` Fix 2), but the three integration tests that assert this endpoint must reject with HTTP 400 were never updated. They now receive a gin 404 instead.

---

## Requirements Verification

### Initial Requirements (`initial_requirements.md`)

| Req | Description | Met? | How Verified |
|-----|-------------|------|--------------|
| R-1 | Create flight order | ✅ | `POST /api/v1/orders` starts `BookingWorkflow`; `TestI_B0_TimerStartsOnOrderCreate` PASS |
| R-2 | Select N seats | ✅ | `PATCH /api/v1/orders/:id/seats` triggers `UpdateSeats` update; `TestU_B1_FirstSeatUpdateStartsTimer` PASS |
| R-3 | 15-minute seat reservation hold | ✅ | `HoldDuration() = 15 * time.Minute` default; workflow timer verified in `TestU_B0` and `TestI_B0` |
| R-4 | Auto-release seats on timer expiry | ✅ | `expireOrder` calls `releaseHeldSeats`; `TestU_B5_TimerExpiryReleasesSeats` and `TestI_B4` PASS |
| R-5 | Timer refreshes on seat selection change | ✅ | `applySeatUpdate` resets `TimerDeadline`; `TestU_B2_SeatChangeResetsTimer` and `TestI_B1` PASS |
| R-6 | Real-time status updates in browser | ✅ | SSE endpoint `GET /api/v1/orders/:id/stream` at 1 s interval; `EventSource` in `payment.js` and `seats.js` with 2 s polling fallback |
| R-7 | Seat timer display in web UI | ✅ | `timer_remaining_seconds` rendered in both seats and payment pages; JS countdown confirmed in source |
| R-8 | 5-digit numeric payment code | ✅ | `isValidPaymentCode` enforced at API layer (400) and workflow layer (`format_invalid` event); `TestI_C4`, `TestI_C5`, `TestU_C5`, `TestU_C6` PASS |
| R-9 | 10-second payment validation timeout | ✅ | `paymentActivityTimeout = 10 * time.Second` as `StartToCloseTimeout`; `TestU_C4_AwaitingPaymentWhileValidationRuns` PASS |
| R-10 | 15% simulated payment failure rate | ✅ | `paymentFailureRate = 0.15` in `payment.go`; `simulatePaymentFailure(rng)` called in `ValidatePayment` activity |
| R-11 | Successful payment confirms booking | ✅ | `ConfirmSeats` sets seats → `BOOKED`, status → `CONFIRMED`; `TestI_C1_PaymentHappyPath` verifies seat status PASS |
| R-12 | 3 failures → order fails with clear message | ✅ (partial — see gap below) | `failOrderPaymentExhausted` sets `PAYMENT_FAILED`; releases seats; audit event `attempts_exhausted`; `TestU_C3`, `TestI_D1`, `TestI_D6` PASS |
| R-13 | Seat inventory managed internally | ✅ | `memory.SeatRepository` with per-flight mutex; no external service dependency |
| R-14 | Graceful failure handling with user messages | ✅ | Terminal states display descriptive UI panels; `terminalMessage()` in `payment.js` |
| R-15 | Single Temporal workflow per order | ✅ | `BookingWorkflow` owns timer, seats, payment end-to-end; one workflow execution per `order_id` |
| R-16 | Temporal worker executes activities | ✅ | `cmd/worker/main.go` registers `Activities`; all four activities wired |
| R-17 | Go-based RESTful server | ✅ | Gin router in `internal/api/router.go`; all endpoints in Go |

---

### Final (Locked) Requirements (`final_requierments.md`)

| FR Ref | Description | Met? | How Verified |
|--------|-------------|------|--------------|
| §2.1 Multi-flight isolation | Seat `1A` on Flight A ≠ `1A` on Flight B | ✅ | `SeatRepository` keyed by `flightID`; `TestI_B2_MultiFlightHoldIsolation` and `TestU_B7` PASS |
| §2.1 Continuous timer | Timer starts at order creation, never pauses | ✅ | Timer starts in `BookingWorkflow` init (`workflow.Now(ctx).Add(HoldDuration)`); `TestI_D4_TimerDecrementsDuringPayment` PASS |
| §2.1 Timer refresh on seat change | Refreshes to full 15m on every seat update | ✅ | `applySeatUpdate` resets `TimerDeadline`; `TestI_B1` and `TestU_B2` PASS |
| §2.1 Expiry releases seats mid-payment | Timer wins over in-flight payment | ✅ | `handleTimerExpiry` calls `rejectInFlightPayment` before `expireOrder`; `TestU_D4` and `TestI_D2` PASS |
| §2.2 Code format — exactly 5 digits | Non-5-digit codes rejected | ✅ | Validated in handler (400) and workflow (`format_invalid` event); `TestI_C4`, `TestI_C5` PASS |
| §2.2 10-second validation timeout per attempt | Payment activity has 10s deadline | ✅ | `paymentActivityTimeout = 10s`; verified in `TestI_C3_TimerDuringPayment` PASS |
| §2.2 15% failure rate | Simulated randomly | ✅ | `paymentFailureRate = 0.15` |
| §2.2 CONFIRMED → seats BOOKED | Success transitions seat status | ✅ | `TestI_C1` verifies seat status in repo PASS |
| §2.2 **3 attempts per method / 3 methods per order** | Up to 3 codes × 3 attempts = 9 total max | ❌ **GAP** | See critical gap section below |
| §2.3 Race condition (S-4): timer expires mid-payment | Payment rejected, seats released | ✅ | `rejectInFlightPayment` + `expireOrder` path; `rejected_by_timer` event; `TestI_D2` and `TestU_D4` PASS |
| §2.3 Flight departure does not cancel active order | Order continues until timer or payment | ✅ | No workflow logic cancels on departure; frontend shows departed banner without blocking |
| §4 State machine: all 6 states present | CREATED, SEATS_HELD, AWAITING_PAYMENT, CONFIRMED, EXPIRED, CANCELLED | ✅ | All states defined in `domain/order.go`; `IsTerminal()` covers CONFIRMED, EXPIRED, CANCELLED, PAYMENT_FAILED |
| §5 S-1 Happy path | Select → Hold → Pay → CONFIRMED | ✅ | `TestI_C1_PaymentHappyPath` PASS |
| §5 S-2 Timer refresh | Hold at 8m → add seat → timer ≈15m | ✅ | `TestU_B2_SeatChangeResetsTimer` PASS |
| §5 S-3 Method exhaustion | Fail code A×3 → Fail code B×3 → Fail code C×3 → order fails | ❌ **GAP** | Current impl fails after 3 total attempts regardless of code changes (see below) |
| §5 S-4 Late payment | Payment starts at 14:55 → expires → rejected | ✅ | `TestI_D2_LatePaymentRejectedOnExpiry` and `TestU_D4` PASS |
| §5 S-5 Multi-flight | Seat `1A` on 101; `1A` on 102 still available | ✅ | `TestI_B2_MultiFlightHoldIsolation` PASS |

---

## Critical Gap: Multi-Method Payment Model

### What the locked requirements specify (§2.2)

> 3 attempts per method: A user can try the same 5-digit code up to 3 times.
> 3 methods per order: A user can try up to 3 *different* 5-digit codes. Changing the code resets the attempt counter but consumes one of the 3 allowed method slots.
> Failure: If all 3 methods (9 total attempts max) fail, the order is terminated.

This means scenario S-3 should be: **fail code A three times → switch to code B (counter resets) → fail B three times → switch to code C → fail C three times → order fails**.

### What is actually implemented

`maxFailuresPerCode = 3` is the **total** failure counter across all submitted codes. After any 3 failures (whether same code or different), `failOrderPaymentExhausted` is triggered and the order enters `PAYMENT_FAILED`. There is no method concept, no per-method attempt counter, and no method slot tracking.

### Impact on observable behavior

| Action | Expected (requirements) | Actual (implementation) |
|--------|------------------------|------------------------|
| Fail code `11111` twice, then submit `22222` | Attempt counter resets to 0; 3 more tries on `22222` | Failure #3; order immediately PAYMENT_FAILED |
| Fail code `11111` three times | Order fails (code A exhausted, switch to B prompt) | Order fails ✅ same result |
| Fail 9 attempts across 3 codes | Order fails | Order fails after 3rd failure (9 attempts never reached) |

Scenario S-3 cannot pass end-to-end as written in the requirements — after failing code A three times, the order is terminal, not pending code B.

### UI impact

`payment.html` displays "Methods used: **0**" and "Methods remaining: **0**" because `methods_used` and `methods_remaining` are not fields in `dto.OrderResponse`. The JS reads `order.methods_used ?? 0` / `order.methods_remaining ?? 0`, which always resolves to `0`. These counters are always `0/0`, which is misleading rather than informative.

---

## Scenario Test Results

| Scenario | ID | Description | Result |
|----------|----|-------------|--------|
| S-1 | Happy path | Select → pay success → CONFIRMED | ✅ PASS (TestI_C1, TestU_C1) |
| S-2 | Timer refresh | Hold → add seat → timer resets to 15m | ✅ PASS (TestI_B1, TestU_B2) |
| S-3 | Method exhaustion | Fail 3 codes × 3 attempts | ❌ NOT MET — fails after 3 total |
| S-4 | Late payment | Payment racing against expiry | ✅ PASS (TestI_D2, TestU_D4) |
| S-5 | Multi-flight isolation | 1A on Flight 101 ≠ 1A on Flight 102 | ✅ PASS (TestI_B2, TestU_B7) |

---

## Edge Case Findings

### Edge Case 1 — Hold conflict (positive conflict detection)
- **Test:** `TestI_B5_HoldConflictReturns409` — two orders trying to hold the same seat
- **Result:** ✅ PASS — second order receives HTTP 409 Conflict

### Edge Case 2 — Timer expiry with no seats held
- **Test:** `TestU_B5b_TimerExpiryWithoutSeats` — order expires before any seat selection
- **Result:** ✅ PASS — order reaches EXPIRED even without any held seats

### Edge Case 3 — Payment without seats held (CREATED state)
- **Test:** `TestI_C9_PaymentWithoutSeatsHeldRejected`
- **Result:** ✅ PASS — HTTP 400; order remains CREATED

### Edge Case 4 — Payment on already-confirmed order
- **Test:** `TestI_C7_PaymentOnConfirmedOrderRejected`
- **Result:** ✅ PASS — HTTP 400; order remains CONFIRMED

### Edge Case 5 — Unknown order
- **Test:** `TestI_C8_PaymentUnknownOrder404`
- **Result:** ✅ PASS — HTTP 404

### Edge Case 6 — Missing/empty payment body
- **Test:** `TestI_C10_PaymentMissingBody400`
- **Result:** ✅ PASS — HTTP 400

### Edge Case 7 — Seat swap releases previous seats
- **Test:** `TestU_B3_SeatSwapReleasesPreviousSeats` — update from `1A` to `2A`; `1A` must become AVAILABLE
- **Result:** ✅ PASS

### Edge Case 8 — Cancel mid-hold releases seats
- **Test:** `TestI_B3_CancelOrderReleasesSeats` and `TestU_B4_CancelReleasesSeats`
- **Result:** ✅ PASS — status CANCELLED, seat status AVAILABLE confirmed in repo

### Edge Case 9 — `new-method` endpoint
- **Tests:** `TestI_D7`, `TestI_D8`, `TestI_D10`
- **Result:** ❌ FAIL — endpoint removed from router returns 404; tests expect 400

---

## Issues Summary

| # | Severity | Finding |
|---|----------|---------|
| 1 | **HIGH** | 3 integration tests fail: `TestI_D7`, `TestI_D8`, `TestI_D10` (404 vs 400 on deleted route) |
| 2 | **HIGH** | Multi-method payment model not implemented: §2.2 requires 3 codes × 3 attempts = 9 max; implementation uses 3 total failures |
| 3 | **MEDIUM** | Scenario S-3 cannot be demonstrated end-to-end as specified |
| 4 | **LOW** | UI counters "Methods used" and "Methods remaining" always display `0` (fields not in API response) |

---

## What Would Fix the Issues

### Fix for issues #1 (3 failing tests)
The three tests expect HTTP 400 from a no-op `/payment/new-method` endpoint. Since the requirement for multiple methods was removed from the implementation, the simplest fix is to update the tests to expect HTTP 404, matching the now-absent route. Alternatively, add a stub route that returns 404 or 400 explicitly.

### Fix for issue #2 (multi-method payment model)
The implementation must be extended to track:
- Current method (code string) with per-method failure counter
- Total methods used (max 3)
- On a new code submission: if failures for the current code are exhausted, consume a method slot and reset the counter; if method slots are also exhausted, fail the order
This requires changes to `workflowState`, `completePaymentValidation`, and the DTO layer.

### Fix for issue #4 (UI counters)
Remove or disable the "Methods used / remaining" counters from `payment.html` and `payment.js` since the backend does not implement the multi-method model.

---

## Positive Assessment

Despite the gaps above, the following are well-executed:

- **Temporal integration:** Workflow, activities, signals, updates, and queries are all used correctly and idiomatically.
- **Seat consistency:** Per-flight mutex in `memory.SeatRepository` correctly prevents double-booking without a database.
- **Timer race condition:** The `rejectInFlightPayment` path correctly handles the race between an in-flight payment activity and the expiry timer (S-4).
- **SSE real-time updates:** `StreamOrder` pushes status every 1 second; JS falls back to 2 s polling on SSE failure.
- **Test coverage:** 17 workflow unit tests and 22 integration tests cover most scenarios. Injectable `PaymentRNG` enables deterministic testing without mocking.
- **Code structure:** Clean separation between domain, workflow, infrastructure, and API layers. No business logic leaked into the HTTP handler.

---

## Verdict

| Dimension | Status |
|-----------|--------|
| Core booking flow (create → hold → pay → confirm) | ✅ |
| Timer lifecycle (start, refresh, expiry) | ✅ |
| Payment retry logic (3 total failures) | ✅ (but mismatches spec) |
| Multi-method payment (3 codes × 3 attempts) | ❌ Not implemented |
| Race condition handling (S-4) | ✅ |
| Multi-flight isolation (S-5) | ✅ |
| Real-time updates | ✅ |
| Test suite passes | ❌ 3/25 integration tests fail |

**The project is NOT ready to deliver.** Two issues must be resolved before submission:

1. Fix the 3 failing tests (update expected status codes from 400 → 404, or restore a stub endpoint returning 400).
2. Align the payment retry model with the locked final requirements (implement the 3-method × 3-attempts model, OR formally revise the locked requirements to match the simpler 3-total-failures model that is implemented).

Once these two issues are addressed and `go test ./...` passes clean, the project will be delivery-ready.
