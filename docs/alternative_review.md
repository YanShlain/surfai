# Engineering Manager Code Audit — Neon Flight Booking System

**Reviewer:** Engineering Manager (take-home evaluation)  
**Date:** 2026-05-29 (third pass — verified in code + tests)  
**Verification:** `go test ./... -count=1 -timeout 180s` — **all packages pass**

---

## Engineering Manager Evaluation Matrix

| Dimension | Grade | Score | Verdict |
|-----------|-------|-------|---------|
| **Concurrency Safety** | A− | 4.5/5 | Per-flight `flightInventory` locks; atomic `SwapHold`; value-copy reads; `TestU_A7` rollback proof |
| **Architectural Decoupling** | A− | 4.5/5 | `SeatRepository` interface with `SwapHold`/`ApplyHold`; workflow updates; bootstrap roles |
| **State Reliability** | B+ | 4.0/5 | `ReconcileHolds` on startup; split in-memory deploy still documented limitation |
| **Go Idiomatic Quality** | A− | 4.5/5 | Update validators, injectable RNG, `X-Request-ID`, context-aware payment delay |

**Overall rating: Senior+ (Tech Lead trajectory)**

This is submission-ready for a Senior/TL interview. Correctness gaps from the first audit are closed and tested. Remaining work is operational (Postgres, metrics, `-race` in CI) — appropriate post-MVP scope.

---

## Audit Checklist — All Prior Issues

| # | Original finding | Status | Proof |
|---|------------------|--------|-------|
| 1 | Non-atomic `Release` + `Hold` | **FIXED** | `applySeatUpdate` → `SwapSeats` → `SwapHold` (`workflow.go:374–398`, `seat_repository.go:111–141`) |
| 2 | Payment 3-total vs 3×3 | **FIXED** | `maxAttemptsPerMethod`/`maxPaymentMethods`; `TestI_D1`, `TestI_C6`, `TestU_C3` |
| 3 | Global `r.mu` cross-flight coupling | **FIXED** | `flightInventory` per-flight mutex only (`seat_repository.go`) |
| 4 | Split api/worker memory | **DOCUMENTED** | `DefaultAPIOptions`/`DefaultWorkerOptions`; startup warning; requires durable store for true split |
| 5 | No reconciliation | **FIXED** | `ReconcileHolds` + `ApplyHold` (`reconcile.go`) |
| 6 | Missing `new-method` route | **FIXED** | `router.go:55`; `UpdateStartNewPaymentMethod` with validator |
| 7 | Docs/UI drift | **FIXED** | `README.md`, `design_overview.md` §2.6, `payment.js`/`payment.html` |
| 8 | Observability | **IMPROVED** | `X-Request-ID` middleware (`router.go`) |
| 9 | `new_method_required` gate | **FIXED** (3rd pass) | SubmitPayment validator (`workflow.go:273–275`); `TestU_D6`, `TestI_D10` |

---

## Stand-Out Strengths (What Differentiates This Submission)

1. **Atomic seat swap with rollback test** — `TestU_A7_SwapHoldRollbackOnConflict` proves failed swaps do not orphan inventory (the exact bug a production EM would hunt).

2. **Temporal update validators** — Payment and new-method rejections happen in `UpdateHandlerOptions.Validator` before a workflow task is scheduled. Fail-fast, cheaper than activity round-trips.

3. **3×3 payment state machine** — Explicit `MethodsUsed`/`CurrentCodeFailures`, implicit switch after ≥1 failure (`TestI_D9`), explicit `new-method` for zero-failure code changes (`TestU_D6`), S-3 exhaustion (`TestI_D1`).

4. **Crash recovery path** — `ReconcileHolds` lists running workflows and re-applies holds. Honest about limits (conflicts logged, not silent).

5. **Clean layer boundaries** — Domain interface unchanged for callers; Postgres adapter drops in without workflow edits.

---

## Remaining Gaps (Honest, Post-MVP)

| Gap | Severity | Notes |
|-----|----------|-------|
| In-memory split deploy | Medium | API + worker as separate processes = two seat worlds. Use embedded worker (`EMBED_TEMPORAL_WORKER=1`) or Postgres. |
| No `-race` in CI | Low | Windows dev env lacks CGO; run in Linux CI with `CGO_ENABLED=1`. |
| No Prometheus/OTel | Low | Middleware hook exists; counters not wired. |
| Stale auxiliary docs | Low | `final_review.md`, `requirements_mismatches.md`, `code_review_summary.md` describe pre-fix state — archive or update if submitting. |
| `workflow.Await(AllHandlersFinished)` | Low | Test warning `[TMPRL1102]` on fast teardown; production should await handlers before terminal exit. |
| `HoldSeats` activity removed | Info | Only `SwapSeats`/`ReleaseSeats`/`ConfirmSeats` remain — correct; some plan docs still mention `HoldSeats`. |

---

## Production Next Steps (If This Were Real)

```go
// 1. Postgres SwapHold — single transaction, SELECT FOR UPDATE
// 2. Idempotency keys on activities (order_id + op_seq)
// 3. Metrics: hold_conflicts_total, reconcile_applied_total, payment_outcomes
// 4. Linux CI: go test -race ./internal/infrastructure/memory/...
```

---

## Interview Questions (Updated)

1. Why does `validateHoldAfterRelease` treat overlap seats (in both release and hold lists) differently?
2. When does `new_method_required` fire vs implicit code switch after `CurrentCodeFailures > 0`?
3. What happens if `ReconcileHolds` finds seat `1A` held by order B but workflow A claims it?
4. Why workflow **updates** for payment instead of signals?

---

*Third pass completed 2026-05-29. All critical audit items verified in source and tests.*
