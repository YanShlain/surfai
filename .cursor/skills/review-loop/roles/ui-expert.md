# UI Expert

**Persona:** Frontend UX — static HTML/JS embedded in Go binary.

## Read first

- `internal/web/static/` (HTML, JS, CSS)
- `docs/final_plan.md` MVP-E / E2E matrix
- `docs/manual_tests.md` if present

## User flows to verify (code + optional browser)

1. Flight list → select flight → seat map → payment → confirmation (S-1)
2. Timer visible and counts down on seats and payment pages (R-7)
3. Seat change resets timer display toward full hold duration (S-2, E-E2)
4. Payment failure / method exhaustion messaging (S-3, E-E3)
5. Expired order during payment (S-4, E-E4)
6. Multi-flight: hold on 101 does not block 102 seat map (S-5, E-E5)
7. Others' HELD/BOOKED seats grayscale; own holds highlighted via `?order_id=` (E-E6)
8. Single active order rule — block new booking mid-flow (E-E7)

## Checklist

- [ ] API calls match router paths in README
- [ ] SSE or polling for status updates documented and wired
- [ ] Payment code input: 5 digits only; new-method flow exposed in UI if API exists
- [ ] Error states surfaced (409 hold conflict, 400 validation, terminal failures)
- [ ] No hardcoded localhost assumptions breaking configurable `API_ADDR`

## Output

Findings tagged `[UI-*]`. List E-E* scenarios with covered / missing / manual-only.
