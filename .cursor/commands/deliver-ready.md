# Deliver until ready

Run the Neon **delivery loop** until all gates pass. Read and follow `.cursor/skills/review-loop/SKILL.md` section **Deliver-ready loop** in full.

## One iteration (this command)

1. **Reconcile** — Read `docs/final_review.md` Issues Summary and Edge Cases. For each item, verify against current code and `go test ./... -count=1 -timeout 120s`. Import still-open items into `docs/review_loop_state.md` Open findings (use IDs `FR-[N]` from final_review or new IDs). Mark resolved items in state with evidence.
2. **Fix** — Resolve every open **Critical** and **High** finding using `.cursor/skills/review-loop/roles/developer-fix.md` and `/developer` (one finding → minimal fix → green tests → commit). Update `docs/final_review.md` when a documented issue is fully resolved.
3. **Review** — Launch **seven dedicated read-only subagents** (Task tool, one per expert role). Do not perform expert passes inline; delegate each role to its own subagent. Merge findings, triage, update `docs/review_loop_state.md`.
4. **Verify** — `go test ./... -count=1 -timeout 120s`; map S-1..S-5 to passing tests; set verdict in state.
5. **Decide** — If all delivery gates pass, report **READY**, refresh `docs/final_review.md` verdict, and **stop**. Otherwise report **NOT READY**, list blocking items, and tell the user to run `/loop /deliver-ready` to continue.

## Loop until ready

```
/loop /deliver-ready
```

Self-paced: after each NOT READY cycle, fix what you can, then re-arm the next wake (see `/loop` skill). Stop when verdict is READY or the user says stop.

## Gates (all required)

- `go test ./...` exits 0
- No Critical/High open findings in `docs/review_loop_state.md`
- S-1..S-5 each have ≥1 passing automated test
- README and design docs match implementation
- `docs/final_review.md` verdict aligned with expert review (docs expert updates on READY)
