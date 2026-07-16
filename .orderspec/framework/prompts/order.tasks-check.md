---
orderspec:
  artifact: command_prompt
  command: order.tasks-check
  phase: check
description: Per-stage gate validating tasks.md as a faithful, well-ordered projection of plan.md. The deterministic traceability tool already proves coverage, cap, subset-binding, and ID legality at /order.tasks time. This gate spends LLM context only on semantic checks: faithfulness to plan, E-M-C ordering, test-first discipline, and SC buildability. Pure inspector: writes only tasks-report.md.
---

# OrderSpec Tasks Check

## Role

`/order.tasks-check` is the independent inspection gate for `tasks.md`.
It runs after `/order.tasks` and answers: Is `tasks.md` a faithful, well-ordered projection of the decisions already made in `plan.md`?

**What is already proven before this gate runs.** `/order.tasks` runs `extract-trace` as a hard write-gate (rc=3 rejects). Coverage, the ≤3-ref cap, subset-binding (ref's `primary_files` contains task path), documented/delegated legality — all settled facts. `validate --stage tasks --json` re-confirms them mechanically.

**This gate does NOT re-derive, re-count, or re-judge coverage, cap, subset-binding, or ID-legality.** Its entire value is the semantic layer no script can see:

- **T1 — faithfulness**: does any task invent a decision absent from spec/plan?
- **T3 — E-M-C ordering**: Expand additive-only; Contract opens with a GATE.
- **T4 — test-first**: tests precede impl within a story.
- **T5 — SC buildability**: buildable success criteria have tasks.
- **T6 — evidence topology**: declared unit/integration evidence has executable test-writing tasks; a generic GATE is not evidence for a direct mechanism.
- **T7 — upstream reroute**: when the root defect lives in plan/spec, route up.

This gate is a **pure inspector**. It writes only `tasks-report.md`. It MUST NOT edit `spec.md`, `plan.md`, `tasks.md`, or source code.

## Command Context Bootstrap

1. Resolve command context:
   ```bash
   python3 .orderspec/framework/scripts/command_context.py resolve order.tasks-check --json
   ```
2. If `ok` is `false` or `missing_required` is non-empty, STOP and report missing required context.
3. Read every file returned in `to_read`, in returned order.
4. Interpret each file by `usage`.

## Target Feature Resolution

1. Initialize feature paths and report template:
   ```bash
   python3 .orderspec/framework/scripts/setup.py tasks-check --json --refresh-template > /dev/null
   eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
   ```
   This resolves `$FEATURE_DIR`, `$FEATURE_ID`, and copies the report template to `$FEATURE_DIR/tasks-report.md`.

2. Validate active feature state:
   ```bash
   python3 .orderspec/framework/scripts/active_feature.py get --json
   python3 .orderspec/framework/scripts/active_feature.py validate --json
   ```
3. If active state validation fails, write BLOCK report with `T0-002 (HIGH): active feature state invalid`, then stop.
4. If `$ARGUMENTS` contains an explicit feature reference, resolve it read-only using `active_feature.py list --json`.
   - If ambiguous: `T0-003 (HIGH): ambiguous feature reference`.
   - If not found: `T0-004 (HIGH): feature not found`.
5. Do not use `active_feature.py select` in this gate.
6. If no target is resolved, write BLOCK report with `T0-000 (CRITICAL): no active feature`.

This gate MUST NOT modify `.orderspec/state/active-feature.json`.

## Upstream Gate Guard

A tasks-check MUST NOT issue PASS over a known failed plan gate.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

python3 .orderspec/framework/scripts/upstream_gate.py \
  --report        "$FEATURE_DIR/plan-report.md" \
  --artifact      "$FEATURE_DIR/plan.md" \
  --upstream-name "plan.md" \
  --this          "/order.tasks-check" \
  --build         "/order.plan" \
  --fix           "/order.plan" \
  --recheck       "/order.plan-check"
```

Interpret exit codes:
- **exit 2 (stop)** — upstream artifact (`plan.md`) missing. Write BLOCK report with `T0-005 (CRITICAL): upstream plan.md missing`, route to `/order.plan`, then stop.
- **exit 1 (halt)** — plan gate report exists and is non-PASS. Write BLOCK report with `T0-006 (HIGH): upstream plan gate non-PASS (verdict: {verdict})`, route to `/order.plan` then `/order.plan-check`, then stop.
- **exit 0 (advisory)** — plan gate report absent or stale. Proceed, but record `T0-007 (LOW): plan gate advisory ({reason})`.
- **exit 0 (ok)** — Proceed.
- **exit 64 (error)** — invocation error. Write BLOCK report with `T0-008 (HIGH): upstream_gate invocation error`.

Do not use `--force` in this gate.

## Mechanical Validation

Run the deterministic validator:

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" validate --stage tasks --json
```

Validate task worker context as a second deterministic gate:

```bash
python3 .orderspec/framework/scripts/task_context.py validate \
  --feature-dir "$FEATURE_DIR" --json
```

```bash
python3 .orderspec/framework/scripts/task_contract_context.py validate \
  --feature-dir "$FEATURE_DIR" --json
```

If this exits non-zero, import one blocking finding:
`T0-009 (HIGH): task context whitelist invalid`, include the script's exact
validation errors, route to `/order.tasks`, and stop semantic inspection.

If contract-context validation exits non-zero, import one blocking finding:
`T0-010 (HIGH): task contract context invalid`, include the script's exact
errors, and route an undefined spec ID to `/order.spec` or a missing phase
context to `/order.tasks`.

The JSON output is the **ground truth** for mechanical findings, inventory, categories, matrices, and contradiction grid data.
You MUST import all findings exactly as provided, including their `severity` and `disposition`.
You MUST NOT downgrade or suppress imported findings.

If a script crashes or returns unparseable output, record `T0-001 (HIGH): mechanical validator unavailable` and route to maintainer.

**Coverage is not re-litigated here.** The traceability tool already proved coverage at `/order.tasks` write time. You read the tool's output; you never re-derive or overrule it. There is no "uncovered ID" finding type in this gate.

M4 is path-scoped: it reports a missing spec ref only when a `[USn]` task's
exact path is the `primary_files` path of a `direct` mechanism. Empty refs are
valid for story support tasks whose paths have no direct mechanism, including
unit evidence, controller support, barrel, route-wiring, fixture, and GATE
tasks. Do not route such tasks merely because they carry `[USn]`.

## Semantic Inspection

Read `tasks.md`, `plan.md`, and `spec.md`. Perform the following checks that require LLM judgment.
For any finding, assign disposition `Route` and create a routing block.

Semantic findings (T1-xxx through T7-xxx) must be integrated into the report's Findings table alongside mechanical findings. Each semantic finding gets its own row with:
- `ID`: T{n}-NNN (prefix by pass)
- `Source`: "semantic"
- `Severity`: CRITICAL/HIGH/MEDIUM/LOW
- `Disposition`: "Route" (or "Auto-fixed" for mechanical/structural fixes)
- `Location`: task ID, section, or path
- `Summary`: concise description

### T1. No New Decisions (faithfulness to plan)

- **T1a**: Any task introducing a design decision **absent from spec and plan** (file, mechanism, library, schema field, endpoint not derivable upstream) → **Route** (CRITICAL if MVP/P1, else HIGH). The gate never silently keeps or deletes an invented decision.
- **T1b**: Any task referencing a plan mechanism/file/path **not in the current plan** (prose mention, not field-3 ref) → obvious typo → **Auto-fix** (correct the reference); genuinely absent → **Route** (HIGH).

### T2. Operational Granularity (NOT a coverage or cap check)

- **T2a**: A task whose description bundles **unrelated** work sharing no coherent behavior (genuine grab-bag), such that `/order.code` cannot execute it as one discrete step → **Route** (MEDIUM). Do NOT raise this merely because a task lists several refs — that is legal and capped.
- **T2b**: A TEST task legitimately exercising one coherent multi-AC flow is NOT a defect. Flag only a test task bundling genuinely unrelated scenarios (LOW/MEDIUM).

### T3. E-M-C Ordering

- **T3a**: Phase 1 (Expand) tasks are **additive only** (read descriptions). A destructive step in Expand → **Auto-fix** (move to correct phase) when unambiguous; else **Route** (HIGH if MVP/P1).
- **T3b**: Story phases follow UJ priority order from spec (P1 before P2). Out-of-order with a single correct ordering → **Auto-fix** (reorder).
- **T3c**: The Contract phase begins with a GATE task; no destructive task precedes it. Missing GATE → **Auto-fix** (insert it). Destructive task ahead → **Auto-fix** (move after GATE) if unambiguous; else **Route** (CRITICAL if ambiguous placement on MVP path).

### T4. Test-First Discipline

- **T4a**: Within each story phase, test tasks **precede** implementation. A clear test-after-impl pair → **Auto-fix** (swap order). HIGH if in a P1 story.
- **T4b**: Each story phase is closed by a **Checkpoint prose line** (per `/order.tasks` rules: "Checkpoint is prose, not a task"). Missing → **Auto-fix** (insert prose line). Do NOT insert per-story verification TASKS — those are owned by `/order.tasks`.
- **T4c**: Test tasks state the expectation to **fail first** (red). Missing red-state note → **Auto-fix** (add it) where intent is clear.

### T5. SC Buildability

- **T5a**: Each Success Criterion (spec) implying **buildable work** (load tests, security tooling, performance assertions) is reflected by ≥1 task. Post-launch/business KPIs exempt. A buildable SC with no task → **Route** (HIGH). The gate never picks how the SC is realized.

### T6. Evidence Topology

- **T6a**: Read the feature state mechanisms.tsv and compare each direct row's test_type with actual test-writing task paths from plan.md. A direct unit mechanism must have a unit-test task; a direct integration mechanism must have an integration-test task. A generic GATE or checkpoint prose line does not provide evidence, and an integration test does not silently satisfy a unit claim. Route the root defect to /order.plan when mechanism topology is wrong, or /order.tasks when the plan is correct but the task list omits the test (HIGH for P1, MEDIUM otherwise).

### T7. Upstream Reroute

- **T7a**: Where tasks cannot be made faithful because the **root defect lives upstream** — a wrong/inadequate/mis-classified plan mechanism, or a spec ambiguity → **Route** to `/order.plan` or `/order.spec` describing the suspected root. Do NOT patch tasks around it. Severity inherits MVP-scope (CRITICAL if blocks P1 story).

## Auto-Fix vs Route Boundary

- **Auto-fix** ONLY when ALL hold: (a) mechanical/structural per E-M-C/test-first rules, (b) exactly one valid form, (c) does NOT change scope or what a task *does*, (d) obvious/reversible. Examples: task numbering, test/impl ordering swap, inserting required Contract GATE, moving destructive step after GATE, fixing a `[US#]` tag resolvable from context, correcting an obvious path typo.
- **Route** for everything that creates or changes task content.
- **When in doubt, Route — never Auto-fix.**
- **You never touch field-3 refs.** Adding/removing/changing a task's spec-ID list is ref-attribution owned by `/order.tasks`.
- **Auto-fix touches task lines only**, never derived sections or the tool-owned `traceability.tsv`.

## Report Generation

The report template has already been copied to `$FEATURE_DIR/tasks-report.md` by `setup.py tasks-check --refresh-template`.

You MUST fill this template file in place. Do not invent report sections, table structures, or alter the YAML frontmatter schema. Fill the template variables exactly as specified using the data from `traceability.py` JSON output and your semantic findings.

### Data Source Rules
- Do NOT read `tasks.md`, `plan.md`, or `spec.md` to fill matrices, categories, or inventory. Use ONLY the JSON fields from `traceability.py`.
- If a JSON field is missing or empty, render the cell as `(none)` or `—`.
- Render booleans as text: `true` → `yes`, `false` → `no`.
- Join arrays with `, ` (comma + space).

### Template Variable Mapping

**YAML Frontmatter**:
- `{generator_cmd}`: `order.tasks-check`
- `{model_name}`: identifier of the AI model running this command
- `{DATE}`: current ISO 8601 timestamp
- `{VERDICT}`: computed from findings (see Verdict table below)
- `{FEATURE_ID}`: from `$FEATURE_ID` shell variable
- `{FEATURE_DIR}`: from `$FEATURE_DIR` shell variable

**HTML Comment Header** (second line of body):
- `{report_name}`: `tasks-report.md`
- All other variables same as frontmatter

**Body Section Variables** — map from `traceability.py validate --stage tasks` JSON:
- `{gate_title}`: `Tasks Check`
- `{target_doc}`: `tasks.md`
- `{gate_focus}`: `ordering, faithfulness, test-first discipline`
- `{auto_fixed_rows}`: one row per auto-fix applied this run. Format: `| ID | What was changed in tasks.md | Why meaning-preserving |`. `(none)` if none. NEVER a row that adds/alters refs.
- `{routing_blocks}`: insert routing blocks for all findings with disposition `Route`
- `{deferred_rows}`: `(none)` — tasks-check defers nothing
- `{findings_rows}`: combine mechanical findings (from `findings` array) with semantic findings (T1-T7). Each row: `| ID | Source | Severity | Disposition | Location | Summary |`
- `{coverage_taxonomy_rows}`: from `categories` object. Each row: `| Category | § | Status | Disposition |`
- `{contradiction_grid_rows}`: from `contradiction_grid` array. Each row: `| Pair | Verdict | Reason |`
- `{journey_matrix_rows}`: from `matrices.uj_coverage` array. Each row: `| UJ | Priority | Covers REQs | ACs | ACs trace to REQs | Status |`
- `{if_matrix_rows}`: from `matrices.if_coverage` array. Each row: `| IF | Kind | Actor | Success | Failure | Covered by ACs | Status |`

**Metrics Section**:
- `{inventory_summary}`: formatted string from `inventory` object, e.g. `REQ=10 · NFR=2 · SC=3 · ... · Total=64`
- `{critical_count}`, `{high_count}`, `{medium_count}`, `{low_count}`: counts from combined findings
- `{auto_fixed_count}`: count of auto-fixes applied this run
- `{routing_count}`: count of findings with disposition `Route`
- `{deferred_count}`: `0`
- `{exit_code}`: from `summary.exit_code`
- `{floor_status}`: `yes` if `verdict_floor` applied, `no` otherwise
- `{report_path}`: `$FEATURE_DIR/tasks-report.md`

### Routing Block Format
```markdown
### Routing Required: {short title}

**Finding**: {what is wrong or missing}
**Location**: {task IDs / section}
**Why owner, not gate**: {why this changes task content}
**Impact if unresolved**: {downstream impact}
**Suggested direction**: {advisory only}
**Run**: `/order.tasks "{ready-to-run refinement request}"`  OR  `/order.plan "..."`  OR  `/order.spec "..."`
```

Use `/order.tasks` for tasks-owned defects (ordering, content, granularity).
Use `/order.plan` for plan-rooted defects (mechanism mis-classification, missing mechanism).
Use `/order.spec` for spec-rooted defects (contract contradiction, missing decision).

## Verdict

| Verdict | Conditions |
|---|---|
| BLOCK | any routed CRITICAL; any routed HIGH that breaks MVP/P1 ordering or faithfulness; upstream plan gate non-PASS; required artifact missing; validator unavailable |
| ROUTING_REQUIRED | no BLOCK condition, but at least one routed MEDIUM/LOW |
| PASS | validator succeeded, no routed findings remain, no unresolved CRITICAL/HIGH |

MVP/P1 scope is determined by user journeys marked P1 in `spec.md`.

Auto-fixes applied and LOW notes are compatible with PASS.

## Completion Response

After writing the report, respond in chat with:
- Verdict (BLOCK, ROUTING_REQUIRED, or PASS)
- Report path
- Number of findings by severity
- Number of auto-fixes applied
- Number of routing blocks
- Manual/orchestrator next action:
  - PASS → human or orchestrator may start `/order.code`
  - ROUTING_REQUIRED/BLOCK → human or orchestrator may run routed `/order.tasks` and/or `/order.plan`/`/order.spec` request(s), then rerun `/order.tasks-check`
