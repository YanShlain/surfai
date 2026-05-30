# Grade A+ until all experts agree

Run the Neon **grade loop** until every expert role scores **A+**. Read and follow `.cursor/skills/review-loop/SKILL.md` section **Grade A+ loop** in full.

## One iteration (this command)

1. **Baseline** — Confirm delivery gates pass (`go test ./... -count=1 -timeout 120s`, S-1..S-5 covered, no Critical/High open). If not, run `/deliver-ready` reconcile + fix first, then continue here.
2. **Review** — Launch **seven dedicated read-only subagents** (Task tool, one per expert role). Each must return grade **A+ / A / B / C / D / F** using [grading-rubric.md](../skills/review-loop/roles/grading-rubric.md). Do not perform expert passes inline.
3. **Triage** — Merge findings; list roles below A+ and the findings blocking each grade. Update `docs/review_loop_state.md` Expert summary and Open findings.
4. **Enhance** — For every role below A+, resolve blocking findings using [developer-fix.md](../skills/review-loop/roles/developer-fix.md) and `/developer` (one finding → minimal enhancement → green tests → commit). Fix **Critical, High, and Medium** that block A+; address Low when trivial. Re-run targeted tests for the touched area.
5. **Re-review (partial)** — Re-launch subagents **only for roles that were below A+** this cycle (read-only). Full seven-way review every 3 cycles or when any role was F/D/C.
6. **Verify** — `go test ./... -count=1 -timeout 120s`; refresh grades in state.
7. Update status - update `docs/final_review.md` summary with the current status.
8. **Decide** — If all seven experts grade **A+**, report **A+ READY** and **stop**.
9. **Permission gate** — If any grade is still below **A+**, end the turn with the grade summary and **ask the user for permission** to run one more cycle. Do **not** start the next cycle, re-arm `/loop`, or schedule a background wake until the user explicitly approves (e.g. "yes", "continue", `/loop /grade-a-plus`). If the user declines or does not reply, stop and leave current grades/blockers in `docs/review_loop_state.md`.

## Loop until all A+

```
/loop /grade-a-plus
```

Self-paced: each approved cycle runs steps 1–8, then step 9 (permission gate). After the user approves, run the next cycle; do not auto-continue without approval. Stop when all grades are A+, the user declines, or the user says stop.

## Exit gates (all required)

- `go test ./...` exits 0
- No Critical or High open findings
- **All seven Expert summary grades = A+** in `docs/review_loop_state.md`
- S-1..S-5 each have ≥1 passing automated test
- README and design docs match implementation (Docs expert A+)

## Grading reference

See `.cursor/skills/review-loop/roles/grading-rubric.md` for role-specific A+ criteria. **A+** means: zero Medium-or-higher findings from that role, exemplary quality for a Senior+ take-home, no doc/code drift in that role's domain.