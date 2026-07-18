---
orderspec:
  artifact: command_prompt
  command: order.plan
  phase: plan
description: Map the spec's logical architecture onto the current repository state — physical structure, verified stack, path manifest, and mechanism machine state.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding if not empty.

## Role of This Artifact

`plan.md` answers **WHERE and HOW**: it maps the stable contract in `spec.md`
onto the physical repository state observed at planning time. That state is the
baseline for one derived `tasks.md` work order.

Properties:
- **Regenerable before a work order**: derived from `spec.md` + actual
  repository state. Once `tasks.md` is generated, implementation applying
  `[NEW]`/`[DEL]` transitions does not stale or relabel the plan.
- **Non-duplicating**: reference resolved stable IDs instead of copying contract text.
- **Concrete**: exact repo-relative files, verified stack facts, and physical implementation mapping.
- **Mechanism-aware**: implementation mechanism decisions are written to machine state (`.state/mechanisms.tsv`) via scripts, not mirrored as Markdown tables in `plan.md`.

`spec.md` remains the source of truth for **WHAT**. `plan.md` is a planning
baseline for **WHERE/HOW**, not a live inventory rewritten after each task.

---

## Global Execution Rules

1.  **Shell Variable Persistence:** Tool shell sessions may not preserve variables. Rehydrate variables at the start of every new shell block:
    ```bash
    eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
    ```
    Do not assume variables like `$FEATURE_DIR` persist between separate shell calls.
2.  **Scope Lock:** You are mapping `spec.md` to code. Do not invent new requirements, endpoints, fields, or permissions. If implementation strictly requires a new externally visible behavior not present in `spec.md`, STOP and report `PLAN_BLOCKED: contract decision required`.

---

## Execution Flow

Follow these steps in exact order. Do not skip steps.

### Step 1: Command Context Resolution

Resolve and load all required context files.

```bash
python3 .orderspec/framework/scripts/command_context.py resolve order.plan \
  --arguments "$ARGUMENTS" --json
```

1.  If `ok` is `false` or `missing_required` is non-empty, STOP and report the missing context.
2.  Read every file returned in `to_read`, in returned order.
3.  Interpret each file according to its `usage` field (`apply`, `constrain`, `parse`, `inspect`, `reference`).
4.  Use only returned `input.controls` and `input.semantic_input`; do not parse raw input again.

### Step 2: Path Resolution

Resolve active feature paths.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
```

If this fails because no active feature directory can be resolved, STOP:
```text
PLAN_STOPPED: no active feature
  1. Create one with /order.spec, or select one with /order.feature --select
  2. Then run /order.plan
```

### Step 3: Mode Detection

Before selecting a mode, inspect the self-gate report. This check is read-only
and MUST happen before any `plan.md`-existence stop.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
SELF_REPORT="$FEATURE_DIR/plan-report.md"
test -e "$SELF_REPORT" && echo "SELF_REPORT_PRESENT" || echo "SELF_REPORT_ABSENT"
```

If `SELF_REPORT_PRESENT`, read it before mode selection.

Inspect persistent downstream feedback before mode selection:

```bash
python3 .orderspec/framework/scripts/workflow_feedback.py list \
  --feature-dir "$FEATURE_DIR" --target order.plan
```

Determine mode before writing any file. State the mode in chat.

1.  **Regenerate** — `plan.md` does not exist, or a standalone `--force` was explicitly supplied and no work-order baseline blocks regeneration.
2.  **Refine** — active `plan.md` exists and either `input.semantic_input` requests specific changes, the prior `plan-report.md` has a `⛔ BLOCK` or `🔀 ROUTING` finding targeting `/order.plan`, or open workflow feedback targets `order.plan`. A blocking self-gate or open feedback selects Refine even when `input.semantic_input` is empty.
If `plan.md` already exists, `input.semantic_input` is empty, and no self-gate or workflow feedback selects Refine, STOP:

```text
PLAN_STOPPED: plan.md already exists
  - To verify the current plan: /order.plan-check
  - To regenerate from scratch: /order.plan --force
  - To apply specific changes: /order.plan "describe the change"
```

If `tasks.md` exists, the derived work order is stale after any plan change.
Inspect task markers before selecting Regenerate or Refine. Any `[X]` marker
means implementation has started and the plan is a locked work-order baseline.
Do not regenerate it merely because planned
`[NEW]` paths now exist or `[DEL]` paths are gone. With only `--force` and no
specific mapping defect, STOP:

```text
PLAN_STOPPED: implementation baseline is active
  Applied pathmanifest transitions are not plan drift.
  Continue with /order.code --resume, or describe the actual mapping defect.
```

Even a specific mapping defect MUST NOT change `plan.md` while any task is
`[X]`: changing the plan would invalidate the safe rollback baseline. STOP and
require `/order.code --reset` first. After reset, refine the plan, then run
`/order.plan-check`, `/order.tasks --force`, and `/order.tasks-check`. Never absorb
partial implementation into `[NEW]` to `[MOD]` relabeling.

If `tasks.md` exists but has no `[X]` markers, Regenerate/Refine may proceed,
but record that the work order is invalidated. Completion MUST require
`/order.plan-check`, `/order.tasks --force`, and `/order.tasks-check` before
`/order.code`.

### Step 4: Upstream Gate Guard

Check the upstream spec gate.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

Set `FORCE_FLAG=--force` only when `input.controls.force` is true; otherwise
leave it empty.

python3 .orderspec/framework/scripts/upstream_gate.py \
  --report        "$FEATURE_DIR/spec-report.md" \
  --artifact      "$FEATURE_DIR/spec.md" \
  --upstream-name "spec.md" \
  --this          "/order.plan" \
  --build         "/order.spec" \
  --fix           "/order.spec" \
  --recheck       "/order.spec-check" \
  $FORCE_FLAG
```

Interpret the JSON `status` field and exit code:

-   **exit 2 (stop)** or **exit 1 (halt)** → STOP. Do not produce a plan.
-   **exit 64 (error)** → STOP. Report: `PLAN_STOPPED: upstream gate invocation error (empty shell variables — re-run setup.py paths)`. Do not produce a plan.
-   **exit 0 (forced)** → Proceed, but insert this warning at the top of `plan.md`:
    `> ⚠ Built over non-PASS spec gate (verdict: {verdict}) via --force`
-   **exit 0 (advisory)** → Proceed, but warn the user in chat: "Upstream spec gate report is stale or absent. It is recommended to re-run `/order.spec-check` before relying on this plan."
-   **exit 0 (ok)** → Proceed.

### Step 5: Self Gate Report Intake

Use self-gate result read in Step 3. Do not perform a second check.

-   **ABSENT** → Proceed.
-   **PRESENT (✅ PASS)** → Ignore report; proceed with `input.semantic_input`.
-   **PRESENT (`CONSUMED_STALE`)** → Previous verdict is inactive. Proceed with `input.semantic_input`; a fresh `/order.plan-check` is required for new PASS evidence.
-   **PRESENT (⛔ BLOCK / 🔀 ROUTING)** → This is your fix-list. Address every finding targeting `/order.plan`. Route findings for other commands. Treat `input.semantic_input` as additional guidance, not a replacement.

Treat every open `order.plan` workflow feedback item loaded in Step 3 as an
additional mandatory fix-list item. Do not consume it yet.

### Step 6: Tooling Validation

Apply the resolved `tooling-protocol.md` and parsed tooling configuration.
Verify configured skills deterministically.

```bash
python3 .orderspec/framework/scripts/validate_tooling.py -C "$PWD" --json
```

Store the JSON and interpret every status exactly according to the loaded
tooling protocol. Match referenced `STACK-NNN` IDs through the loaded stack
contract and tooling configuration. Do not infer availability or inspect skill
directories to discover it.

### Step 7: Setup Plan Artifact

Initialize according to the selected mode. Regenerate refreshes from the current
template. Refine preserves the existing plan and edits it in place.

```bash
# Regenerate only:
python3 .orderspec/framework/scripts/setup.py plan --json --refresh-template > /dev/null

# Refine only:
python3 .orderspec/framework/scripts/setup.py plan --json > /dev/null
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
```

### Step 8: Focused Reconnaissance

Start with repository manifests and project contracts so documentation lookup is
driven by observed stack facts. Before making any library-specific claim, apply
the documentation sources allowed by the resolved tooling protocol:

1.  **Skills:** Consult only skills reported `installed_and_verified`; use them
    as primary evidence for their bound technology.
2.  **Documentation Sources:** For every configured source whose policy applies
    to `order.plan`, determine runtime availability and follow its configured
    required/optional/disabled policy before making library-specific claims.
3.  **Evidence Recording:** Record consulted sources in the template's `Library Documentation Evidence` section.

Then perform focused reconnaissance to map `spec.md` onto the codebase.

**Read Budget:** Target at most 20 implementation/repository files. Context
files returned by the resolver do not count. Exceed the target only when needed
to close a named cross-boundary or runtime-evidence obligation; record the
reason in `Verified Against`. Prefer exemplars over exhaustive scans.
**Verify:**
-   Language/runtime/framework versions.
-   Test/lint/build commands.
-   Source layout and module boundaries.
-   Implementation mechanisms for Spec IDs.
-   Existing project abstractions relevant to the feature (for example shared plugins, middleware, base models, transaction helpers, locks, serializers, and pagination helpers).
-   Runtime and deployment capabilities required by candidate mechanisms (for example database topology, process count, external services, queues, and distributed coordination).
-   Environment readiness for every material prerequisite: exact read-only check, expected result, repository evidence, bounded recovery option, approval/side-effect boundary, and safe fallback. Do not defer an obvious prerequisite to `/order.code`.
-   Cross-boundary completeness for every planned behavior: persistence/schema,
    service, controller/serializer, route, export/wiring, and test boundaries
    that must cooperate. A later task MUST NOT discover that an earlier model,
    schema, DTO, or route is not planned to establish fields or operations
    already required by `spec.md`.

For each material mechanism, distinguish three evidence classes:

1. **Library/API evidence** proves only that an API or feature exists and how it behaves.
2. **Repository runtime evidence** proves that the required capability is configured or supplied by manifests, deployment files, runtime configuration, or the test harness.
3. **Operational scope evidence** proves the boundary within which the mechanism is correct: `process`, `host`, `cluster`, `external service`, or `not applicable`.

Library/API documentation alone is insufficient runtime evidence.
Do not treat library support as runtime readiness. For example, documentation that an ODM exposes transactions does not prove that the repository deploys a transaction-capable database topology. A process-local lock does not satisfy a cluster-wide concurrency invariant unless the repository proves single-process deployment or the spec limits the invariant to one process.

Prefer an existing project abstraction when it satisfies the contract. If the plan introduces a parallel mechanism, record the observed abstraction and the concrete mismatch that prevents reuse.

Missing feature implementation is expected. Stop only when repository/project
contract evidence makes the requested contract impossible or mutually
inconsistent; report `PLAN_BLOCKED: contract/repository decision required` and
route to the owning `/order.spec` or `/order.bootstrap` command.

### Step 9: Write `plan.md`

Fill `$IMPL_PLAN`. In Regenerate it was initialized from the current template;
in Refine preserve unaffected decisions and change only routed/requested scope.

Read and fill every canonical template section; its comments define field-level
syntax. Additional semantic rules:

- Replace `[DATE]`; remove all remaining placeholders and authoring residue.
- Keep Summary technical and role-pure. Select delivery strategy only from its
  template evidence rule.
- Select Evidence Sequencing from repository/project evidence. Do not require a
  red-first test when the relevant assertion cannot execute or is already
  satisfied; justify `characterization-first` or `implementation-first` instead.
- Record only verified stack/repository facts and exact evidence paths. A
  planned `[NEW]` file is `DESIGN-OK`, never present-state `PASS` evidence.
- Fill `Mechanism Evidence & Runtime Closure` from repository evidence and the
  operational-scope rules established during reconnaissance.
- For every behavior-bearing path, record complete bounded obligations and Spec
  IDs. Trace contract fields and values through persistence, mutation,
  serialization, routing/export, and tests.
- Fill one Interface Fidelity row per `IF-NNN`; preserve method, mounted path,
  input semantics, response/nullability, pagination/filter behavior, and
  failure statuses. Do not add interfaces.
- Apply the template's filename-precedence rules from observed filenames only.
- Apply the environment protocol. An unverified required prerequisite without a
  repository-supported alternative or safe fallback is
  `PLAN_BLOCKED: runtime prerequisite unverified`.
- Cite evidence for library-specific claims; a bare `STACK-NNN` reference is not
  such a claim. Keep Complexity Tracking only for actual justified deviations.
- Preserve the canonical Mechanism Matrix prose, resolving its feature-path
  placeholders. Do not add a Markdown mechanism table.

**Prohibitions:**
-   Do not duplicate §8 Information Model or §9 Interface Contracts from `spec.md`.
-   Do not include `TODO`, `???`, or placeholder paths.

### Step 10: Emit Pathmanifest

Fill the template's canonical flat `pathmanifest`. Determine `[MOD]`/`[NEW]`/
`[DEL]` from read-only existence checks and transition intent. Include every
file that must change, including prerequisite config/deployment/test-harness
files; never list directories.

### Step 11: Emit Mechanism Matrix

Before emitting rows, verify four bindings:

1. primary_files is the boundary that directly realizes the mechanism, not a
   nearby coordinator. For example, audit-log immutability belongs to the
   write boundary that blocks updates/deletes, not merely to an audit-create
   service. It is a single traceability owner, not an exhaustive dependency
   list. Supporting boundaries still require exact obligations and Spec IDs in
   Architectural Mapping and the pathmanifest.
2. test_type matches the evidence topology: unit mechanisms require a unit
   test path in the manifest; integration mechanisms require an integration
   test path. If the repository has no suitable path, add it to the plan
   manifest. Task-writing evidence is owned and checked by `/order.tasks` and
   `/order.tasks-check`; do not inspect or modify `tasks.md` in this command.
3. For `delegated:<ID>` rows, the target mechanism must semantically cover the
   source ID. Do not delegate an edge or acceptance criterion to a generic
   endpoint that does not explicitly verify it.
4. For `ASM-NNN` rows, emit a mechanism only when the assumption materially
   narrows implementation. Do not emit a mechanism for a `[default]`
   assumption that merely restates normal behavior.

Write mechanism decisions to machine state. You MUST NOT author a mechanism table in `plan.md`.

**1. Get Spec IDs:**
```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" get spec-ids
```
*(If this fails, try to recover by running:)*
```bash
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" init
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" extract-spec-ids
```
*(If recovery also fails — STOP and report:)*
```text
PLAN_STOPPED: spec-ids extraction failed
  The spec.md may be missing or malformed.
  Run /order.spec to create or fix the feature contract.
```

**2. Prepare JSON:**
For each required Spec ID (`REQ`, `IF`, `AC`, `EDGE`, `INV`, `NFR`; conditional
`ASM`), construct one object with exactly five fields.

**Do NOT** emit rows for `UJ`, `DEC`, or `SC` IDs. They are not testable mechanisms and will be rejected by `put-mechanisms`.

```json
[{"spec_id":"REQ-001","coverage_kind":"direct","mechanism":"validate credentials","primary_files":"src/services/auth.js","test_type":"unit"}]
```

Allowed combinations: `direct` with `unit` or `integration`;
`delegated:<ID>` with the delegate's topology; `documented` with
`test_type: documented` and `primary_files: plan.md` or a planned documentation
artifact.

**3. Write Validated JSON:**
```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

python3 .orderspec/framework/scripts/traceability.py -C "$PWD" \
  --feature-dir "$FEATURE_DIR" put-mechanisms --json < "$MECHANISMS_RESULT_FILE"
```
If it exits non-zero, fix only the rejected JSON object and rerun. Never emit
literal TSV or hand-edit `mechanisms.tsv`.

**4. Lint & Check:**
```bash
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" lint
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" check-mechanisms
```
Both must pass.

### Step 12: Validate Plan

Run mechanical self-checks.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" check-plan
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" validate --stage plan --json
```

Blocking findings (`severity: HIGH` or `CRITICAL`) must be fixed. Fix the data in `plan.md` or `mechanisms.tsv` and re-run validation. Do not maintain a separate list of checks; trust the script output.

### Step 13: Update Active Feature State

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

python3 .orderspec/framework/scripts/active_feature.py status \
  --feature-id "$FEATURE_ID" \
  --status planned \
  --last-command order.plan \
  --json
```

### Step 14: Consumed Report Marker

If a BLOCK/ROUTING `plan-report.md` was used in Step 5, first account for every
routed finding by ID. Mark the report consumed only after all plan-owned
findings were changed and mechanical validation passed. Never consume a report
with an unaddressed plan-owned finding.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
python3 .orderspec/framework/scripts/traceability.py mark-consumed \
  --report "$FEATURE_DIR/plan-report.md" \
  --consumer /order.plan \
  --recheck /order.plan-check
```

After successful plan validation, consume each addressed workflow feedback item:

```bash
python3 .orderspec/framework/scripts/workflow_feedback.py consume \
  --feature-dir "$FEATURE_DIR" --id "FB-NNN" --consumer order.plan
```

---

## Completion Report

Report to chat:
-   `FEATURE_DIR`
-   Constitution status summary
-   `[NEW]` / `[MOD]` / `[DEL]` file counts
-   Delivery strategy (`migration-emc` or `incremental`) and its plan evidence
-   Mechanism matrix result (row counts from `summarize-mechanisms --json`)
-   Validation result (`validate --stage plan`)
-   **Manual/orchestrator next step:** Run `/order.plan-check`. If an existing
    unchecked `tasks.md` was invalidated, then run `/order.tasks --force` and
    `/order.tasks-check` after plan-check passes.
-   Readiness for `/order.tasks` (after plan-check passes)

## Done When

- [ ] Context, target, mode, upstream gate, self-report, and feedback resolved.
- [ ] Regenerate used current template; Refine preserved unaffected content.
- [ ] Plan is role-pure, evidence-bound, cross-boundary complete, and contains no placeholders.
- [ ] Pathmanifest, mechanism ownership/delegation, and test topology agree.
- [ ] Runtime prerequisites and operational scope are closed by repository evidence or safe fallback.
- [ ] Existing tasks baseline was respected; changed plan invalidates unchecked tasks.
- [ ] `lint`, `check-mechanisms`, `check-plan`, and plan validation pass without blocking findings.
- [ ] State and consumed markers update only after validation; completion names required gates/regeneration.
