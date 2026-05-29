---
name: review-loop
description: >-
  Multi-expert review loop for Neon: architect, Go, Temporal, database, UI, QA,
  and docs experts verify requirements, tests, and documentation. Runs fix-verify
  cycles until gates pass. Use with /review-loop, /deliver-ready, /loop, or when
  the user asks for expert review, quality gate, delivery-ready loop, or review loop.
---

# Neon Review Loop

Orchestrates sequential expert reviews, triage, optional fixes, and re-verification until delivery gates pass.

## Source of truth (read first)

| Document | Purpose |
|----------|---------|
| [docs/final_requierments.md](../../docs/final_requierments.md) | Locked functional requirements, scenarios S-1..S-5 |
| [docs/final_plan.md](../../docs/final_plan.md) | Architecture, API contract, test matrix §9 |
| [docs/final_review.md](../../docs/final_review.md) | Prior QA audit — reconcile before fix phase |
| [docs/review_loop_state.md](../../docs/review_loop_state.md) | Loop state, open findings, coverage map |
| [README.md](../../README.md) | Public overview — must match implementation |

## Invocation

| Command | Behavior |
|---------|----------|
| `/deliver-ready` | **Delivery loop (one cycle):** reconcile `final_review.md` → fix Critical/High → dedicated subagent review → verify |
| `/loop /deliver-ready` | Repeat `/deliver-ready` until READY or user stops |
| `/review-loop` | Full cycle once (review → triage → fix if asked → verify) |
| `/review-loop fix` | Triage open findings and fix via [developer-fix](roles/developer-fix.md) |
| `/review-loop verify` | Re-run tests + QA matrix only; update state |
| `/loop 30m /review-loop` | Fixed interval loop (adapt shell for Windows) |
| `/loop /review-loop` | Dynamic self-paced loop — re-run when findings remain or tests fail |

## Delivery gates (all must pass to exit)

- [ ] `go test ./...` exits 0
- [ ] No **Critical** or **High** open findings in `docs/review_loop_state.md`
- [ ] Every scenario **S-1..S-5** has at least one passing automated test (unit, integration, or workflow)
- [ ] Test matrix rows in `final_plan.md` §9 marked covered or explicitly deferred with user approval
- [ ] README and design docs reflect current API, states, and env vars

## Cycle workflow

Copy this checklist and update each run:

```
Review loop progress:
- [ ] 0. Orient (diff, state, tests baseline)
- [ ] 1. Architect
- [ ] 2. Go expert
- [ ] 3. Temporal expert
- [ ] 4. Database / data expert
- [ ] 5. UI expert
- [ ] 6. QA expert
- [ ] 7. Docs expert
- [ ] 8. Triage
- [ ] 9. Fix (if requested or Critical/High remain)
- [ ] 10. Verify + update state
- [ ] 11. Loop decision
```

### 0. Orient

1. Read `docs/review_loop_state.md` — note open findings and last commit reviewed.
2. Run `git log -5 --oneline` and `git diff` (or diff since `last_reviewed_commit` in state).
3. Run `go test ./... -count=1` — record pass/fail baseline in state.

### 1–7. Expert passes

Run **in order**. Each expert reads their role file, produces findings, appends to state.

| Step | Role file | Focus |
|------|-----------|-------|
| 1 | [roles/architect.md](roles/architect.md) | 3-tier boundaries, design vs code |
| 2 | [roles/go-expert.md](roles/go-expert.md) | Idioms, concurrency, errors, tests |
| 3 | [roles/temporal-expert.md](roles/temporal-expert.md) | Workflow lifecycle, updates vs signals, timer |
| 4 | [roles/database-expert.md](roles/database-expert.md) | Repository contracts, consistency, holds |
| 5 | [roles/ui-expert.md](roles/ui-expert.md) | Static UI flows, timer display, seat map UX |
| 6 | [roles/qa-expert.md](roles/qa-expert.md) | Requirements traceability, test matrix §9 |
| 7 | [roles/docs-expert.md](roles/docs-expert.md) | README, plan, handoff accuracy |

**Finding format** (every expert uses this):

```markdown
### [ROLE]-[N] [Critical|High|Medium|Low] — short title
- **File(s):** path:line
- **Requirement:** S-N / U-B3 / etc. or "design doc §X"
- **Issue:** one sentence
- **Evidence:** test name, grep, or behavior observed
- **Suggested fix:** one sentence (reviewers do not implement unless fix phase)
```

Use Task subagents (`subagent_type: explore`, `readonly: true`) for large diffs when a single pass cannot cover all packages.

### 8. Triage

1. Deduplicate findings across roles.
2. Sort by severity; Critical/High block delivery.
3. Update `docs/review_loop_state.md` — Open findings table + Expert summary grades.

### 9. Fix phase

Only when user asked for fixes, or Critical/High findings exist:

1. Follow [roles/developer-fix.md](roles/developer-fix.md).
2. Pair with user skill `/developer` — **one finding, one minimal commit** after green tests.
3. Do not batch fixes or edit unrelated code.

### 10. Verify

1. `go test ./... -count=1 -timeout 120s`
2. QA expert spot-check: map each **S-1..S-5** to a passing test name.
3. Move resolved findings to **Resolved** in state with commit/test evidence.
4. Set `last_reviewed_commit` to current HEAD.

### 11. Loop decision

| Condition | Next action |
|-----------|-------------|
| All gates pass | Stop loop; report **READY** summary |
| Critical/High open + user wants auto-fix | Run step 9 → 10 → 11 |
| Tests fail or Medium findings only | Report summary; if `/loop` active, schedule next wake (dynamic: after fix or 1h fallback) |
| User said review-only | Stop after step 8; do not fix |

## Deliver-ready loop

Use **`/deliver-ready`** (or **`/loop /deliver-ready`**) when the goal is submission-ready code. This mode **always fixes first, then reviews with dedicated subagents**.

Command file: [`.cursor/commands/deliver-ready.md`](../../commands/deliver-ready.md)

### Deliver-ready checklist

```
Deliver-ready progress:
- [ ] A. Reconcile final_review.md → state
- [ ] B. Fix Critical/High (developer-fix + /developer)
- [ ] C. Expert review via 7 dedicated subagents
- [ ] D. Triage + update state + final_review.md
- [ ] E. Verify (tests + S-1..S-5)
- [ ] F. Loop decision (READY / NOT READY)
```

### A. Reconcile `docs/final_review.md`

1. Read **Issues Summary** and **Edge Case Findings** in `docs/final_review.md`.
2. Run `go test ./... -count=1 -timeout 120s` — record baseline in state.
3. For each documented issue, **verify current behavior** (grep, read test, run targeted test). Do not trust stale prose.
4. **Resolved** → move to `Resolved findings` in state with test/commit evidence; note in `final_review.md` if editing that doc this cycle.
5. **Still open** → add to `Open findings` in state. Prefer IDs `FR-1`, `FR-2`, … matching final_review issue numbers; new gaps use `[ROLE]-[N]`.
6. If `final_review.md` verdict contradicts green tests and fixed code, treat reconciliation as the source of truth until step D refreshes the doc.

### B. Fix phase (mandatory for deliver-ready)

Unlike `/review-loop`, deliver-ready **always** runs fix when Critical/High exist:

1. Follow [roles/developer-fix.md](roles/developer-fix.md) + `/developer`.
2. Fix order: failing tests → requirements gaps → concurrency/data → architecture → docs/UI.
3. One finding → minimal diff → `go test ./...` → **commit** → update state → next finding.
4. After all Critical/High from reconciliation are addressed, proceed to review even if Medium/Low remain (report them; they do not block READY unless user says otherwise).

### C. Dedicated subagent review (mandatory)

**Do not** run all seven expert passes inline in the parent agent. Launch **seven parallel Task subagents** — one per role — then merge results.

| Subagent | Role file | `description` param |
|----------|-----------|---------------------|
| 1 | [roles/architect.md](roles/architect.md) | `Deliver review: architect` |
| 2 | [roles/go-expert.md](roles/go-expert.md) | `Deliver review: go expert` |
| 3 | [roles/temporal-expert.md](roles/temporal-expert.md) | `Deliver review: temporal expert` |
| 4 | [roles/database-expert.md](roles/database-expert.md) | `Deliver review: database expert` |
| 5 | [roles/ui-expert.md](roles/ui-expert.md) | `Deliver review: ui expert` |
| 6 | [roles/qa-expert.md](roles/qa-expert.md) | `Deliver review: qa expert` |
| 7 | [roles/docs-expert.md](roles/docs-expert.md) | `Deliver review: docs expert` |

**Subagent settings:** `subagent_type: generalPurpose`, `readonly: true`.

**Subagent prompt template** (fill `[ROLE]` and role file path):

```
You are the Neon [ROLE] expert for a delivery review.

1. Read your role file: .cursor/skills/review-loop/roles/<role>.md
2. Read docs/final_requierments.md, docs/final_plan.md, docs/review_loop_state.md, README.md
3. Review the codebase per your role focus. Run tests if your role requires it.
4. Return ONLY:
   - Grade: A/B/C/D/F
   - Findings list (use finding format from .cursor/skills/review-loop/SKILL.md)
   - One-line top issue
   - READY or NOT READY from your role's perspective

Do NOT implement fixes. Do NOT commit.
```

Parent agent: wait for all seven, dedupe in step D, update **Expert summary** table in state.

### D. Triage + doc refresh

1. Deduplicate findings; Critical/High block delivery.
2. Update `docs/review_loop_state.md` (open/resolved, scenarios, test matrix snapshot).
3. **Docs expert output** drives refresh of `docs/final_review.md` when verdict changes (new date, test results, verdict READY/NOT READY). Archive stale claims; do not leave contradictory failure lists.

### E–F. Verify and loop decision

Same as steps **10–11** above. On **READY**, set state `Verdict: READY`, update `final_review.md`, stop. On **NOT READY** with Critical/High, if `/loop /deliver-ready` is active: fix → verify → re-arm next wake (see `/loop` skill; PowerShell `Start-Sleep` on Windows).

## Parallel expert mode (optional for `/review-loop` only)

For `/review-loop` on large changes, you may launch read-only explore agents in parallel. **`/deliver-ready` always uses dedicated subagents (step C).** Sequential inline review remains the default for plain `/review-loop`.

## Reporting

End each cycle with:

```markdown
## Review loop summary — [date]

**Verdict:** READY | NOT READY
**Tests:** pass/fail counts
**Open:** N Critical, N High, N Medium, N Low
**Scenarios:** S-1..S-5 coverage table
**Docs drift:** yes/no — list items
**Next:** fix list or "none"
```

## Related skills

- `/developer` — implement fixes with layer rules and test gates
- `/senior-system-architect` — architecture changes only; not for routine review
- `/loop` — scheduling; see loop skill for Windows PowerShell sentinel pattern
