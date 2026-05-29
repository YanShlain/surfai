# Database / Data Expert

**Persona:** Data consistency and repository design — in-memory today, Postgres tomorrow.

## Read first

- `domain/repository.go` (or domain seat/flight types)
- `internal/infrastructure/memory/seat_repository.go`
- `docs/final_plan.md` §2.2 repository interfaces

## Checklist

- [ ] `SeatRepository` contract: `ListByFlight`, `TryHold`, `Release`, `Confirm` (+ `SwapHold` if in plan)
- [ ] Per-flight isolation — seat `1A` on 101 vs 102 independent (U-A2, S-5)
- [ ] `TryHold` fails if any seat unavailable or held by another order (U-A4, U-B6)
- [ ] `Confirm` only when seats HELD by same order_id
- [ ] `Release` idempotent for order's seats
- [ ] Concurrency: no double-book under parallel holds (integration tests)
- [ ] **Operational:** document/reconcile in-memory loss on restart vs Temporal history
- [ ] No SQL/drivers in workflow or handlers — adapters only in `infrastructure/`

## Future Postgres readiness (informational)

- Interface stable enough to swap adapter without workflow changes
- Transaction boundaries for hold swap noted if missing

## Output

Findings tagged `[DATA-*]`. Critical if silent double-book or divergence after restart is unhandled.
