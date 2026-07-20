---
orderspec:
  artifact: command_prompt
  command: order.tasks-check
  phase: check
description: Per-stage gate validating tasks.md as a faithful, path-complete, well-ordered projection of plan.md. Deterministic validation proves structure, coverage, path completeness, cap, binding, and ID legality. The LLM judges only semantic faithfulness, dependency order, plan-selected delivery and evidence sequencing, and SC buildability. Pure inspector: writes only tasks-report.md.
---

# OrderSpec Tasks Check

## User Input

```text
$ARGUMENTS
```

This gate always targets active feature. Unflagged text is semantic inspection
guidance: it may add attention but never narrow required checks or change
target. No controls are supported.

## Role

`/order.tasks-check` is the independent inspection gate for `tasks.md`.
It runs after `/order.tasks` and answers: Is `tasks.md` a faithful, well-ordered projection of the decisions already made in `plan.md`?

**What is already proven before this gate runs.** `/order.tasks` runs `extract-trace` as a hard write-gate (rc=3 rejects). Coverage, the ≤3-ref cap, exact binding (ref's single `primary_files` equals task path), documented/delegated legality — all settled facts. `validate --stage tasks --json` re-confirms them mechanically.

**This gate does NOT re-derive, re-count, or re-judge coverage, cap, subset-binding, or ID-legality.** Its entire value is the semantic layer no script can see:

- **T1 — faithfulness**: does any task invent a decision absent from spec/plan?
- **T2 — executable boundaries**: tasks are cohesive and `[P]` is justified.
- **T3 — delivery ordering**: E-M-C for migration plans; no invented Contract for non-migration plans.
- **T4 — evidence sequencing**: task order and expected results match the mode
  selected and justified by the plan.
- **T5 — SC buildability**: buildable success criteria have tasks.
- **T6 — evidence topology**: declared unit/integration evidence has executable test-writing tasks; a generic GATE is not evidence for a direct mechanism.
- **T7 — upstream reroute**: when the root defect lives in plan/spec, route up.
- **T8 — prerequisite closure**: worker context and cross-path prerequisites are complete.

This gate is a **pure inspector**. Its only inspection artifact is
`tasks-report.md`. It MUST NOT edit `spec.md`, `plan.md`, `tasks.md`, or source
code. After report finalization it may invoke only the loaded blocking-feedback
protocol's script-owned bookkeeping for a cross-owner route.

## Severity Model

Severity measures defect impact, not whether the command can continue:
- **CRITICAL**: constitution `MUST` violation; violated or unenforced invariant with a reachable write path; atomicity, security, data-loss, or data-corruption risk.
- **HIGH**: missing, contradicted, invented, or weakly evidenced P1/MVP obligation; missing required upstream artifact or implementation path; P1 ordering, evidence-sequencing, prerequisite, or evidence-topology failure; upstream non-PASS.
- **MEDIUM**: non-P1 defect or evidence gap; unavailable or invalid operational context; stale upstream evidence; task scope or sequencing defect without critical risk.
- **LOW**: cosmetic or organizational residue with no implementation, orchestration, or runtime impact.

A terminal precondition can require a BLOCK report and stop the command independently of finding severity. Do not inflate an operational/context finding to CRITICAL merely because inspection cannot continue. Unless a rule explicitly says otherwise, P1/MVP scope raises a material defect to HIGH and non-P1 scope is MEDIUM. Escalate to CRITICAL only when the defect meets the CRITICAL definition above.

## Command Context Bootstrap

1. Resolve command context and the read-only gate target together:
   ```bash
   python3 .orderspec/framework/scripts/command_context.py resolve order.tasks-check \
     --arguments "$ARGUMENTS" --json
   ```
2. If `ok` is `false` or `missing_required` is non-empty, treat this as the terminal precondition `T0-011 (MEDIUM): command context unavailable` and STOP. If a report target can be resolved safely from the available context, write a BLOCK report; otherwise report the finding in chat.
3. Read every file returned in `to_read`, in returned order.
4. Interpret each file by `usage`.
5. Use only resolver-parsed semantic input; do not parse raw input again.

## Target Feature Resolution

1. Use only `target.feature_directory` and `target.feature_id` returned by
   Command Context Bootstrap. On target failure, stop in chat; no safe report
   path exists. Never select or mutate active feature state.
2. Initialize the report for that exact target:
   ```bash
   TARGET_VARS="$(python3 .orderspec/framework/scripts/gate_target.py \
     --command order.tasks-check --arguments "$ARGUMENTS" --shell-vars)" || exit $?
   eval "$TARGET_VARS"
   eval "$(python3 .orderspec/framework/scripts/setup.py tasks-check \
     --feature-dir "$FEATURE_DIR_REL" --refresh-template --shell-vars)"
   ```
3. Missing `spec.md`, `plan.md`, or `tasks.md` is a terminal HIGH finding routed
   to its owner (`/order.spec`, `/order.plan`, or `/order.tasks`). Write BLOCK
   report and stop before upstream or semantic inspection.

## Upstream Gate Guard

A tasks-check MUST NOT issue PASS over a known failed plan gate.

```bash
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
- **exit 2 (stop)** — upstream artifact (`plan.md`) missing. Write BLOCK report with `T0-005 (HIGH): upstream plan.md missing`, route to `/order.plan`, then stop.
- **exit 1 (halt)** — plan gate report exists and is non-PASS. Write BLOCK report with `T0-006 (HIGH): upstream plan gate non-PASS (verdict: {verdict})`, route to `/order.plan` then `/order.plan-check`, then stop.
- **exit 0 (advisory)** — plan gate report absent or stale. Proceed and record
  `T0-007 (MEDIUM, Informational): plan gate advisory ({reason})`. This does not
  create a routing block or prevent PASS; recommend `/order.plan-check` in the
  completion response.
- **exit 0 (ok)** — Proceed.
- **exit 64 (error)** — invocation error. Write BLOCK report with `T0-008 (MEDIUM): upstream_gate invocation error`, then stop.

Do not use `--force` in this gate.

## Mechanical Validation

Run the deterministic validator:

```bash
MECHANICAL_RESULT_FILE="$(mktemp "${TMPDIR:-/tmp}/orderspec-tasks-check.XXXXXX.json")" || exit 2
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" \
  --feature-dir "$FEATURE_DIR" validate --stage tasks --json \
  > "$MECHANICAL_RESULT_FILE"
MECHANICAL_RC=$?
```

Exit 0 or 1 is a completed validation: exit 1 means the JSON contains blocking
mechanical findings. Any other exit, empty output, or invalid JSON means the
validator is unavailable. Read `$MECHANICAL_RESULT_FILE`; its JSON is the
ground truth described below. The temporary file is evidence transport only;
do not write inspection output into feature state.

Validate task worker context as a second deterministic gate:

```bash
python3 .orderspec/framework/scripts/task_context.py validate \
  --feature-dir "$FEATURE_DIR" --json
```

```bash
python3 .orderspec/framework/scripts/task_contract_context.py validate \
  --feature-dir "$FEATURE_DIR" --json
```

If `task_context.py validate` exits non-zero, import one blocking finding:
`T0-009: task context whitelist invalid`, include the script's exact validation
errors, assign HIGH when affected context belongs to P1/MVP and MEDIUM otherwise,
route to `/order.tasks`, and stop semantic inspection.

If `task_contract_context.py validate` exits non-zero, import one blocking finding:
`T0-010: task contract context invalid`, include the script's exact errors,
assign HIGH when affected context belongs to P1/MVP and MEDIUM otherwise, and
route an undefined spec ID to `/order.spec` or a missing phase context to
`/order.tasks`.

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
For every semantic T1–T8 finding, assign disposition `Route` and create a
routing block. Preserve each mechanical/T0 disposition exactly; informational
advisories do not receive routing blocks.

Semantic findings (T1-xxx through T8-xxx) must be integrated into the report's Findings table alongside mechanical findings. Each semantic finding gets its own row with:
- `ID`: T{n}-NNN (prefix by pass)
- `Source`: "semantic"
- `Severity`: CRITICAL/HIGH/MEDIUM/LOW
- `Disposition`: "Route"
- `Location`: task ID, section, or path
- `Summary`: concise description

Precondition, upstream-gate, or tooling findings use `Source: "operational"`
and a `T0-NNN` ID. They are not semantic findings and must not impersonate
mechanical output.

### T1. No New Decisions (faithfulness to plan)

- **T1a**: Any task introducing a design decision **absent from spec and plan** (file, mechanism, library, schema field, endpoint not derivable upstream) → **Route** (HIGH for P1/MVP, MEDIUM otherwise). The gate never silently keeps or deletes an invented decision. Escalate to CRITICAL only when the invented decision violates a constitution `MUST`, leaves an invariant unenforced, or creates atomicity, security, data-loss, or data-corruption risk.
- **T1b**: Any task referencing a plan mechanism/file/path **not in the current plan** (prose mention, not field-3 ref) → **Route** to `/order.tasks` (HIGH for P1/MVP, MEDIUM otherwise).

### T2. Operational Granularity (NOT a coverage or cap check)

- **T2a**: A task whose description bundles **unrelated** work sharing no coherent behavior (genuine grab-bag), such that `/order.code` cannot execute it as one discrete step → **Route** (MEDIUM). Do NOT raise this merely because a task lists several refs — that is legal and capped.
- **T2b**: A TEST task legitimately exercising one coherent multi-AC flow is NOT a defect. Flag only a test task bundling genuinely unrelated scenarios: MEDIUM when the bundle prevents discrete execution or diagnosis; LOW only when it is an organizational defect with no implementation or orchestration impact.
- **T2c**: `[P]` is valid only when `plan.md` provides evidence that the adjacent
  marked tasks are both file-disjoint and dependency-independent. Missing plan
  evidence or a dependency between marked tasks → Route to `/order.tasks`
  (MEDIUM). Do not infer safety from different paths alone.

### T3. Plan-Selected Delivery Ordering

- **T3a**: When the plan declares migration/compatibility/cleanup work, Phase 1
  (Expand) is additive only. A destructive step in Expand → Route to
  `/order.tasks`. A non-migration plan MUST NOT acquire an invented cleanup or
  Contract phase. Assign HIGH for P1/MVP and MEDIUM otherwise; use CRITICAL only
  for the risks defined by the Severity Model.
- **T3b**: Story phases follow UJ priority order from spec (P1 before P2). Out-of-order phases → **Route** to `/order.tasks` (HIGH if P1 ordering is affected, MEDIUM otherwise).
- **T3c**: If a Contract phase is required by the plan, it begins with a GATE
  task and no destructive task precedes it. A non-migration work order instead
  ends with read-only Final Verification. Missing GATE, destructive work before
  it, or invented cleanup → Route to `/order.tasks` (HIGH for P1/MVP, MEDIUM otherwise).

### T4. Evidence-Sequencing Discipline

- **T4a**: Ordering must match plan Evidence Sequencing. `red-first` and
  `characterization-first` place their evidence before implementation;
  `implementation-first` places it after and requires the plan's explicit
  justification. Mismatch → **Route** to `/order.tasks` (HIGH for P1, MEDIUM otherwise).
- **T4b**: Each story phase is closed by a **Checkpoint prose line** (per `/order.tasks` rules: "Checkpoint is prose, not a task"). Missing checkpoint → **Route** to `/order.tasks` (MEDIUM).
- **T4f**: The last executable task in every story phase MUST be a same-story
  `[USn] | @verify |  | VERIFY:` task containing the exact command, asserted
  IDs, and STOP-on-failure instruction. Missing or displaced phase gate →
  **Route** to `/order.tasks` (HIGH for P1/MVP, MEDIUM otherwise).
- **T4c**: Test tasks state the expected red, baseline, or post-implementation
  result selected by the plan. Missing/mismatched expectation → Route (MEDIUM).
- **T4d**: In `red-first`, inspect Setup/Expand and earlier phases for behavior already
  implemented before a later test-writing task that targets it. If that task
  cannot produce its declared red state because its model/schema/service/route
  prerequisite is already implemented, route to `/order.tasks` (HIGH for P1,
  MEDIUM otherwise). File placement in an earlier phase does not override TDD.
- **T4e**: A final command-only lint/typecheck task must use a `VERIFY:` gloss,
  declare no automatic write behavior, and remain read-only. A task that says
  "fix violations" under one arbitrary binding path is a scope defect; route
  to `/order.tasks` (HIGH when the task authorizes broad or P1/MVP-significant
  mutation; MEDIUM otherwise).

### T5. SC Buildability

- **T5a**: Each Success Criterion (spec) implying **buildable work** (load tests, security tooling, performance assertions) is reflected by ≥1 task. Post-launch/business KPIs exempt. A buildable SC with no task → **Route** (HIGH for P1/MVP, MEDIUM otherwise). Escalate to CRITICAL only when the omission leaves an invariant unenforced or creates atomicity, security, data-loss, or data-corruption risk. The gate never picks how the SC is realized.

### T6. Evidence Topology

- **T6a**: Read the feature state mechanisms.tsv and compare each direct row's test_type with actual test-writing task paths from plan.md. A direct unit mechanism must have a unit-test task; a direct integration mechanism must have an integration-test task. A generic GATE or checkpoint prose line does not provide evidence, and an integration test does not silently satisfy a unit claim. Route the root defect to /order.plan when mechanism topology is wrong, or /order.tasks when the plan is correct but the task list omits the test (HIGH for P1, MEDIUM otherwise). Escalate to CRITICAL only when an invariant with a reachable write path has no executable evidence or the gap creates atomicity, security, data-loss, or data-corruption risk.

### T7. Upstream Reroute

- **T7a**: Where tasks cannot be made faithful because the **root defect lives upstream** — a wrong/inadequate/mis-classified plan mechanism, or a spec ambiguity → **Route** to `/order.plan` or `/order.spec` describing the suspected root. Do NOT patch tasks around it. Severity is HIGH when it blocks P1/MVP and MEDIUM otherwise. Escalate to CRITICAL only for a constitution `MUST`, unenforced invariant with a reachable write path, atomicity, security, data-loss, or data-corruption defect.

### T8. Cross-Boundary Prerequisite Closure

- **T8a**: For each behavior-bearing support task with empty or insufficient
  field-3 refs, require minimal `contract_refs` in task-context so the worker
  receives exact contract excerpts. A model/schema task must include every
  required `ENT-NNN`, `STR-NNN`, and `VAL-NNN` Information Model reference;
  behavioural REQ/INV refs alone are insufficient when they do not define the
  fields or closed values. Missing context is `/order.tasks` (HIGH for
  P1/MVP, MEDIUM otherwise). Escalate to CRITICAL only when the missing context
  leaves an invariant unenforced or creates atomicity, security, data-loss, or
  data-corruption risk.
- **T8b**: Verify required model fields, schema operations, exports, routes,
  serializer values, and fixtures are established before their first consumer.
  If plan mapping is complete but task sequencing/content omits the prerequisite,
  route to `/order.tasks`. If plan mapping omitted it, route to `/order.plan`.
  Assign HIGH for P1/MVP and MEDIUM otherwise. Escalate to CRITICAL only when
  the missing prerequisite leaves an invariant unenforced or creates atomicity,
  security, data-loss, or data-corruption risk.
- **T8c**: A test or serializer/controller task that asserts a named model or
  service seam must include those exact dependency paths in task-context
  `read` and the Information Model/response contract IDs in `contract_refs`.
  A correct write path does not close this boundary. Missing context routes to
  `/order.tasks` (HIGH for P1/MVP, MEDIUM otherwise).

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
- `{gate_focus}`: `path completeness, ordering, faithfulness, evidence sequencing`
- `{routing_blocks}`: insert routing blocks for all findings with disposition `Route`
- `{deferred_rows}`: `| (none) | — | — |` — tasks-check defers nothing
- `{findings_rows}`: combine mechanical findings (from `findings` array) with semantic findings (T1-T8). Each value is a complete Markdown row: `| ID | Source | Severity | Disposition | Location | Summary |`. With no findings, use `| (none) | — | — | — | — | — |`.
- `{coverage_taxonomy_rows}`: from `categories` object. Each row: `| Category | § | Status | Disposition |`
- `{contradiction_grid_rows}`: from `contradiction_grid` array. Each row: `| Pair | Verdict | Reason |`
- `{journey_matrix_rows}`: from `matrices.uj_coverage` array. Each row: `| UJ | Priority | Covers REQs | ACs | ACs trace to REQs | Status |`
- `{if_matrix_rows}`: from `matrices.if_coverage` array. Each row: `| IF | Kind | Actor | Success | Failure | Covered by ACs | Status |`

**Metrics Section**:
- `{inventory_summary}`: formatted string from `inventory` object, e.g. `REQ=10 · NFR=2 · SC=3 · ... · Total=64`
- `{critical_count}`, `{high_count}`, `{medium_count}`, `{low_count}`: counts from combined findings
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
| BLOCK | any routed CRITICAL/HIGH; any terminal precondition explicitly requiring BLOCK; upstream plan gate non-PASS; required artifact missing; validator unavailable |
| ROUTING_REQUIRED | no BLOCK condition, but at least one routed MEDIUM/LOW |
| PASS | validator succeeded, no routed findings remain, no unresolved CRITICAL/HIGH |

MVP/P1 scope is determined by user journeys marked P1 in `spec.md`.

## Deterministic Report Finalization

After filling the report, validate that no mechanical finding was lost or
altered and that IDs, severities, dispositions, metrics, and verdict agree:

```bash
python3 .orderspec/framework/scripts/validate_gate_report.py \
  "$FEATURE_DIR/tasks-report.md" \
  --mechanical "$MECHANICAL_RESULT_FILE" --json
REPORT_RC=$?
if [ "$REPORT_RC" -eq 0 ]; then rm -f "$MECHANICAL_RESULT_FILE"; fi
```

Do not complete while `REPORT_RC` is non-zero. Correct only the report rendering
from the already collected mechanical and semantic evidence, then rerun the
finalizer. Never change an artifact under inspection to make the report pass.

Mechanical validation, context validation, report template refresh, and an
unfinalized report are internal states. Never produce a completion response at
any of them. Under an active supervisor, after successful finalization submit
exactly one bound transition:

```bash
python3 .orderspec/framework/scripts/workflow_supervisor.py advance \
  --run-file "$RUN_FILE" --source order.tasks-check
```

Obey its `terminal`, `continuation_required`, and `next_action` immediately.
While it remains `RUNNING`, the Completion Response below is not user-visible.
Before any final response, call `workflow_supervisor.py status`. Its
`final_response.permitted:false` is an absolute response ban: execute
`next_action` and do not emit a progress handoff or self-declare a host
interruption. A real host interruption produces no agent-authored final.

## Completion Response

Only after a permitted terminal boundary, respond in chat with:
- Verdict (BLOCK, ROUTING_REQUIRED, or PASS)
- Report path
- Number of findings by severity
- Number of routing blocks
- Manual/orchestrator next action:
  - PASS → human or orchestrator may start `/order.code`
  - ROUTING_REQUIRED/BLOCK → human or orchestrator may run routed `/order.tasks` and/or `/order.plan`/`/order.spec` request(s), then rerun `/order.tasks-check`
  - Plan gate advisory → additionally recommend `/order.plan-check`; do not route it through an artifact-author command
