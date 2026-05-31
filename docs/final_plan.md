# Final Plan — Index

> **Architecture, API, and flows:** [design_overview.md](design_overview.md)  
> **Requirements (LOCKED):** [final_requierments.md](final_requierments.md)  
> **Live review state and scenario map:** [review_loop_state.md](review_loop_state.md)

The full phased plan and detailed Given/When/Then matrix lived here historically. That content is consolidated into `design_overview.md` (implementation) and `review_loop_state.md` (coverage snapshot below).

---

## 9. Test matrix snapshot (business perspective)

Maintained in lockstep with [review_loop_state.md](review_loop_state.md). MVP blocks map to requirement scenarios S-1..S-5.

| Block | Scope | Covered | Notes |
|-------|--------|---------|-------|
| **MVP-A** | Flights, seat map, repos, seed | yes | `TestU_A*`, memory repo tests |
| **MVP-B** | Holds, timer, cancel, expiry | yes | `TestU_B*`, `TestI_B*` |
| **MVP-C** | Payment happy path | yes | `TestU_C1`, `TestI_C1` |
| **MVP-D** | Payment edge cases (3× fail, timer race) | yes | `TestU_C3`, `TestU_D4`, `TestI_D*` |
| **MVP-E** | E2E / UI | yes | Playwright E-E1–E-E10, IR-1–IR-7 (`npm run test:e2e`) |

**Testability hooks:** Temporal time skipping in workflow tests; `HOLD_DURATION`, `PAYMENT_SUCCESS_RATE`, `PAYMENT_VALIDATION_DELAY` env vars; injectable payment RNG in activities.
