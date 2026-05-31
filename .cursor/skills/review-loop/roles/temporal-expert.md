# Temporal / Service Expert

**Persona:** Workflow orchestration specialist — timers, updates, activity design.

## Read first

- `internal/workflow/booking/` (workflow, activities, types, config)
- `internal/infrastructure/temporal/order_service.go`
- `docs/final_requierments.md` §2.1 timer, §2.2 payment, §2.3 edge cases

## Checklist

- [ ] 15-minute timer starts on **first seat hold**; **refreshes** on every seat-set change (S-2)
- [ ] Timer **never pauses** during payment validation (S-4, I-D4)
- [ ] Timer expiry wins over in-flight payment — seats released, payment rejected (S-4, U-D4)
- [ ] Payment: Workflow **Update** (not signal+polling) for `SubmitPayment` only
- [ ] **3 consecutive** payment validation failures → `PAYMENT_FAILED` (S-3); no per-method switch
- [ ] Terminal states: `CONFIRMED`, `EXPIRED`, `CANCELLED`, `PAYMENT_FAILED` reachable and tested
- [ ] Activities idempotent where Temporal may retry
- [ ] `SwapHold` or equivalent atomic hold swap on seat change (U-B3)
- [ ] Workflow tests use time skipping / env hooks (`HOLD_DURATION`, payment RNG inject)

## Edge cases (requirements §2.3)

- [ ] Race: timer fires while payment activity running
- [ ] Multi-flight isolation in workflow + activities (S-5)

## Output

Findings tagged `[TEMP-*]`. Map each to scenario S-1..S-5 or test ID U-B*/I-C*/I-D*.
