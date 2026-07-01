---
orderspec:
  artifact: command_prompt
  command: order.plan-check
  phase: check
description: Inspect plan.md as a correct, complete, role-pure physical mapping of spec.md onto the current repository. Pure inspector: detects and routes defects; writes plan-report.md every run using the shared report-template.md; does not author or edit plan/spec/tasks content.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding if not empty.

## Role In The Pipeline

This is the gate for `/order.plan`.

It runs after `/order.plan` and answers:

> Is `plan.md` a faithful, complete, physically grounded mapping of the stable `spec.md` contract onto the current repository state?

This gate is a **pure inspector**.

It writes only its own report:

```text
<feature-dir>/plan-report.md
```

It MUST NOT edit:

- `spec.md`;
- `plan.md`;
- `tasks.md`;
- `.state/spec-ids.tsv`;
- `.state/mechanisms.tsv`;
- source code.

All plan content changes are owned by `/order.plan`.  
All spec contract changes are owned by `/order.spec`.

This gate detects and routes. Owners fix.

## Artifact Roles

OrderSpec uses three distinct artifacts:

| Artifact | Role | Lifecycle |
|---|---|---|
| `spec.md` | WHAT contract and logical architecture | Stable source of truth |
| `plan.md` | WHERE/HOW mapping to current repo state | Regenerable |
| `tasks.md` | ORDER of implementation | Disposable |

This gate validates only `plan.md` as derived from:

- `spec.md`;
- repository reconnaissance;
- machine state in `.state/`.

It does not validate task ordering, implementation code, or repo drift over time.

## Configuration B Assumptions

This prompt assumes Configuration B:

- `spec-ids.tsv` is machine state.
- `mechanisms.tsv` is machine state.
- `plan.md` contains a `pathmanifest`.
- `plan.md` does **not** contain a Markdown mechanism matrix.
- Mechanism decisions are written only through:

  ```bash
  python3 .orderspec/framework/scripts/traceability.py put-mechanisms <feature>
  ```

- This gate reads mechanisms from:

  ```text
  <feature-dir>/.state/mechanisms.tsv
  ```

Do not ask the user to manually edit `.state/*.tsv`.

## Boundaries

### This gate owns detection for

- plan/spec ID consistency;
- `pathmanifest` correctness;
- mechanism completeness and semantic adequacy;
- misuse of `documented`;
- suspicious or excessive `ASM` mechanism rows;
- route path preservation for `IF-NNN`;
- test topology consistency;
- physical grounding against repository conventions;
- stack and constraint consistency;
- direct constitution conflicts and important constitution planning gaps;
- role purity of `plan.md`;
- report persistence through the shared report template.

### This gate does not own

- authoring missing mechanism rows;
- choosing physical files;
- changing stack decisions;
- changing API contracts;
- changing acceptance criteria;
- task ordering or E-M-C sequencing;
- implementation/code correctness;
- repo drift after planning.

Route defects to the owning command.

## Routing Ownership

Use these routes:

| Root cause | Owner |
|---|---|
| Missing/inadequate plan mapping | `/order.plan` |
| Missing/wrong mechanism row | `/order.plan` |
| Wrong pathmanifest entry | `/order.plan` |
| Contract drift introduced by plan | `/order.plan` to remove it, or `/order.spec` to promote it |
| Spec contradiction or missing contract decision | `/order.spec` |
| Task ordering / parallelism / E-M-C concern | `/order.tasks` or later `/order.tasks-check` |
| Code does not implement plan/spec | `/order.code` or `/order.code-check` |
| Merge/rebase/temporal artifact drift | `/order.sync-check` |

When unsure whether a defect is plan-owned or spec-owned:

- If `spec.md` is clear and `plan.md` deviates → `/order.plan`.
- If `spec.md` is contradictory, incomplete, or impossible to map → `/order.spec`.

## Verdicts

Use exactly one verdict:

| Verdict | Meaning |
|---|---|
| ✅ PASS | No blocking or routed findings. Plan is ready for `/order.tasks`. |
| 🔀 ROUTING REQUIRED | Findings exist and must be resolved by `/order.plan` or `/order.spec`, but no MVP-blocking defect was found. |
| ⛔ BLOCK | A critical or MVP-blocking defect exists. Do not proceed to `/order.tasks` until resolved. |

A report is written for every verdict.

## Pre-Execution Checks

Run the **`before_plan_check`** phase per `.orderspec/memory/hooks-protocol.md`.

If hooks are absent or not configured, skip silently per the hook protocol.

## Shell Variable Persistence Warning

Tool shell sessions may not preserve variables across separate invocations.

Every shell block that uses `FEATURE_DIR`, `FEATURE_SPEC`, `IMPL_PLAN`, `REPO_ROOT`, `FEATURE`, or `REPORT` MUST rehydrate them from:

```bash
python3 .orderspec/framework/scripts/setup.py paths --json
```

Do not assume variables from previous shell commands still exist.

## Execution Steps

### 1. Resolve feature paths

Run from repository root:

```bash
PATHS_JSON="$(python3 .orderspec/framework/scripts/setup.py paths --json)"
FEATURE_DIR="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["FEATURE_DIR"])' <<< "$PATHS_JSON")"
FEATURE_SPEC="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["FEATURE_SPEC"])' <<< "$PATHS_JSON")"
IMPL_PLAN="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["IMPL_PLAN"])' <<< "$PATHS_JSON")"
REPO_ROOT="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["REPO_ROOT"])' <<< "$PATHS_JSON")"
CURRENT_BRANCH="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("CURRENT_BRANCH",""))' <<< "$PATHS_JSON")"
FEATURE="$(basename "$FEATURE_DIR")"
REPORT="$FEATURE_DIR/plan-report.md"
mkdir -p "$FEATURE_DIR"
```

If this fails because no active feature can be resolved, STOP and report to chat only:

```text
PLAN_CHECK_STOPPED: no active feature
No feature directory is active. Run /order.spec or select an existing feature first.
```

In this case no report file can be reliably written.

### 2. Required artifact checks

Check:

```bash
PATHS_JSON="$(python3 .orderspec/framework/scripts/setup.py paths --json)"
FEATURE_DIR="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["FEATURE_DIR"])' <<< "$PATHS_JSON")"
FEATURE_SPEC="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["FEATURE_SPEC"])' <<< "$PATHS_JSON")"
IMPL_PLAN="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["IMPL_PLAN"])' <<< "$PATHS_JSON")"

test -f "$FEATURE_SPEC" && echo "SPEC_PRESENT" || echo "SPEC_MISSING"
test -f "$IMPL_PLAN" && echo "PLAN_PRESENT" || echo "PLAN_MISSING"
```

If `spec.md` is missing:

- write `plan-report.md` with verdict `⛔ BLOCK`;
- finding owner: `/order.spec`;
- stop after writing the report.

If `plan.md` is missing:

- write `plan-report.md` with verdict `⛔ BLOCK`;
- finding owner: `/order.plan`;
- stop after writing the report.

### 3. Upstream spec gate guard

A plan-check must not issue PASS over a known failed spec gate.

Run:

```bash
PATHS_JSON="$(python3 .orderspec/framework/scripts/setup.py paths --json)"
FEATURE_DIR="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["FEATURE_DIR"])' <<< "$PATHS_JSON")"
FEATURE_SPEC="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["FEATURE_SPEC"])' <<< "$PATHS_JSON")"

python3 .orderspec/framework/scripts/upstream_gate.py \
  --report        "$FEATURE_DIR/spec-report.md" \
  --artifact      "$FEATURE_SPEC" \
  --upstream-name "spec.md" \
  --this          "/order.plan-check" \
  --build         "/order.spec" \
  --fix           "/order.spec" \
  --recheck       "/order.spec-check"
```

Interpret:

- `status: ok` → proceed.
- `status: advisory` → proceed, but record a LOW note that `/order.spec-check` was not run or is stale.
- `status: halt` → continue only enough to write `plan-report.md` with verdict `⛔ BLOCK`; route to `/order.spec` / `/order.spec-check`.
- `status: stop` → write `⛔ BLOCK`; route to `/order.spec`.
- `status: error` → write `⛔ BLOCK`; report tooling invocation problem.

Do not use `--force` in this gate.

If the user wants to plan over a failed spec gate, they do that in `/order.plan --force`, but `/order.plan-check` still records the upstream condition.

### 4. Load context

Read:

- `spec.md`;
- `plan.md`;
- `.orderspec/memory/constitution.md` if present;
- `.orderspec/templates/report-template.md` if present;
- `.state/mechanisms.tsv` through scripts, not by hand-editing;
- `spec-ids.tsv` through scripts, not by hand-editing.

Run:

```bash
PATHS_JSON="$(python3 .orderspec/framework/scripts/setup.py paths --json)"
FEATURE_DIR="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["FEATURE_DIR"])' <<< "$PATHS_JSON")"
FEATURE="$(basename "$FEATURE_DIR")"

python3 .orderspec/framework/scripts/traceability.py get "$FEATURE" spec-ids
python3 .orderspec/framework/scripts/traceability.py summarize-mechanisms --json "$FEATURE"
```

If `spec-ids.tsv` or `mechanisms.tsv` is missing or unreadable:

- write a finding routed to `/order.plan`;
- do not synthesize the missing state manually.

### 5. Mechanical baseline

Run all mechanical checks.

Use a single shell block so exit codes are captured reliably:

```bash
PATHS_JSON="$(python3 .orderspec/framework/scripts/setup.py paths --json)"
FEATURE_DIR="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["FEATURE_DIR"])' <<< "$PATHS_JSON")"
FEATURE="$(basename "$FEATURE_DIR")"

set +e

python3 .orderspec/framework/scripts/traceability.py lint "$FEATURE"
LINT_RC=$?

python3 .orderspec/framework/scripts/traceability.py check-plan "$FEATURE"
CHECK_PLAN_RC=$?

python3 .orderspec/framework/scripts/traceability.py check-mechanisms "$FEATURE"
CHECK_MECH_RC=$?

python3 .orderspec/framework/scripts/traceability.py validate --stage plan "$FEATURE"
VALIDATE_RC=$?

python3 .orderspec/framework/scripts/traceability.py summarize-mechanisms --json "$FEATURE"
SUMMARY_RC=$?

echo "LINT_RC=$LINT_RC"
echo "CHECK_PLAN_RC=$CHECK_PLAN_RC"
echo "CHECK_MECH_RC=$CHECK_MECH_RC"
echo "VALIDATE_RC=$VALIDATE_RC"
echo "SUMMARY_RC=$SUMMARY_RC"
```

If `validate --json --stage plan` is supported, you may additionally run it:

```bash
python3 .orderspec/framework/scripts/traceability.py validate --json --stage plan "$FEATURE"
```

Mechanical findings are ground truth.

You MUST NOT:

- dismiss a mechanical finding as a false positive;
- downgrade a mechanical severity;
- claim PASS if blocking mechanical findings remain.

If a script fails due to missing command, crash, or unparseable output, record:

```text
P0-001 mechanical validator unavailable
```

Severity: HIGH.  
Disposition: Route to maintainer/tooling, not `/order.plan`.

If a script reports a finding you believe is caused by a bad script pattern, record:

```text
P0-002 suspected script-pattern bug
```

Severity: MEDIUM.  
Still import the original mechanical finding. Do not suppress it.

### 6. Mechanical finding ownership

Map common mechanical findings:

| Finding | Owner |
|---|---|
| Unknown ID cited by `plan.md` | `/order.plan` |
| Missing/malformed `pathmanifest` | `/order.plan` |
| `[NEW]`/`[MOD]` contradicts filesystem | `/order.plan` |
| Missing mechanism row | `/order.plan` |
| Unknown mechanism ID | `/order.plan` |
| Mechanism primary file missing from `pathmanifest` | `/order.plan` |
| Invalid delegation chain/cycle | `/order.plan` |
| Placeholder/template residue in `plan.md` | `/order.plan` |
| Missing `spec.md` | `/order.spec` |
| Missing `plan.md` | `/order.plan` |

### 7. Semantic inspection passes

Run these even if all mechanical checks pass.

Limit findings to 30 total. Never drop CRITICAL findings. If there are too many LOW/MEDIUM findings, aggregate them.

Use finding IDs:

- `P0-*` tooling/mechanical intake;
- `P1-*` artifact hygiene;
- `P2-*` role purity;
- `P3-*` mechanism completeness;
- `P4-*` mechanism adequacy;
- `P5-*` route/interface preservation;
- `P6-*` test topology;
- `P7-*` physical grounding/naming;
- `P8-*` stack/constraint/constitution;
- `P9-*` spec-rooted defects.

## P1. Artifact Hygiene

Check `plan.md` for:

- template residue;
- placeholder tokens;
- old scaffolding references;
- stale comments from `plan-template.md`;
- Markdown mechanism table;
- mention that mechanism rows are authored in `plan.md`;
- generated `data-model.md`, `contracts/`, or `quickstart.md` scaffolding;
- copied self-check checklist from the prompt.

Flag as `/order.plan`.

Examples:

| Problem | Severity |
|---|---|
| Template placeholder remains | HIGH |
| Markdown mechanism table present | HIGH |
| Old spec-kit scaffold required | MEDIUM |
| Minor harmless comment residue | LOW/MEDIUM |

Expected Configuration B text:

- `Mechanism Matrix` section is a notice only.
- It points to `.state/mechanisms.tsv`.
- It does not mirror mechanism rows.

## P2. Role Purity

Check that `plan.md`:

- maps Spec IDs to physical files;
- does not restate the Executive Summary;
- does not duplicate full interface contracts;
- does not redraw spec logical diagrams;
- does not add new product behavior;
- does not add new status codes, fields, roles, permissions, TTLs, jobs, or NFR numbers absent from `spec.md`.

Route:

- plan-only overreach → `/order.plan`;
- real missing/ambiguous contract → `/order.spec`.

Severity:

- contract drift on externally visible behavior → HIGH or CRITICAL;
- non-behavioral duplication → LOW/MEDIUM.

## P3. Mechanism Completeness

Use `spec-ids.tsv` as the ID source of truth.

Required mechanism rows:

- `REQ`
- `IF`
- `AC`
- `EDGE`
- `INV`
- `NFR`

Conditional mechanism rows:

- `ASM` only when it records a deferred implementation decision, a persisted shape decision, or a meaningful narrowing that must affect implementation.

Forbidden mechanism rows:

- `SC`
- `CON`
- `UJ`
- `Q`

Important:

- `CON` IDs do **not** require mechanism rows in Configuration B.
- `CON` IDs must be honored in `Technical Context`, `Constitution Check`, and mapping decisions.
- Default assumptions should usually not create mechanism rows.

Flag:

| Problem | Severity | Owner |
|---|---:|---|
| Missing `REQ`/`IF`/`AC`/`EDGE`/`INV`/`NFR` mechanism | HIGH/CRITICAL | `/order.plan` |
| `SC`/`CON`/`UJ`/`Q` mechanism row exists | HIGH | `/order.plan` |
| Default `ASM` rows are added without implementation significance | MEDIUM | `/order.plan` |
| `ASM` narrowing with no mechanism where implementation depends on it | MEDIUM/HIGH | `/order.plan` |

MVP/P1 obligations are CRITICAL if missing or unmapped.

MVP/P1 means covered by a user journey marked P1 in `spec.md`.

## P4. Mechanism Adequacy

Inspect `mechanisms.tsv`.

For each row, check whether the mechanism actually covers the ID.

### Coverage kind semantics

| coverage_kind | Acceptable when |
|---|---|
| `direct` | this ID has executable implementation/test coverage |
| `delegated:<ID>` | coverage is genuinely provided through another ID's executable path |
| `documented` | no executable behavior is expected; the decision is recorded as documentation |

### `documented` rules

For `documented` rows, expected values are:

```text
primary_files = plan.md
test_type = documented
```

A separate documentation file may be used only if it is a repo-relative Markdown/documentation artifact listed in the `pathmanifest`.

Do **not** accept `documented` rows pointing at implementation source files such as:

- `.js`
- `.ts`
- `.py`
- `.go`
- `.java`
- `.rb`
- `.php`
- `.cs`

Source files imply executable behavior. If the primary file is implementation code, the row should use `direct` or `delegated:<ID>`.

Flag suspicious cases:

| Problem | Severity |
|---|---:|
| Required behavior marked `documented` to avoid testing | HIGH |
| `documented` points to source file | MEDIUM/HIGH |
| NFR says `MUST` but mechanism is `documented` without justification | HIGH |
| Mechanism says “verified through X” but coverage_kind is `documented` instead of `delegated:X` | MEDIUM/HIGH |
| Delegation target does not semantically cover source ID | HIGH |
| Edge case delegated to a generic endpoint without explicit edge coverage | MEDIUM/HIGH |

### NFR handling

- Qualitative `SHOULD` NFRs may be `documented` if no practical executable assertion exists.
- `MUST` NFRs should usually be `direct` or `delegated`.
- If an NFR is verified through an invariant or interface path, prefer `delegated:<ID>`.

### ASM handling

Default assumptions should not be over-tasked.

If `ASM-NNN` is marked `[default]` in `spec.md` and merely restates normal behavior, flag an unnecessary mechanism row unless the plan explains why it affects implementation.

If `ASM-NNN` is `[narrowing ...]` and materially affects implementation, a mechanism row is appropriate.

## P5. Route and Interface Preservation

For every `IF-NNN` in `spec.md`:

- method must match;
- externally visible path must match;
- mounted route path must preserve prefix behavior;
- no extra endpoint should appear in `plan.md` unless present in `spec.md`;
- no status code changes should appear in `plan.md` unless present in `spec.md`.

Check route splitting carefully.

Example problem:

```text
spec: GET /v1/tasks/:taskId/audit
plan: src/routes/v1/audit-log.route.js mounted as /audit-logs
```

This is route drift unless the plan explicitly says the file is mounted under `/tasks/:taskId/audit`.

Flag route drift as HIGH or CRITICAL.

Owner:

- wrong physical mapping → `/order.plan`;
- missing/ambiguous interface contract → `/order.spec`.

## P6. Test Topology

Compare `mechanisms.tsv` test claims with `pathmanifest`.

Check:

- rows with `test_type=unit` have plausible unit test files in the relevant layer;
- service mechanisms marked `unit` have service unit tests or explicit justification;
- model mechanisms marked `unit` have model unit tests or explicit justification;
- validation mechanisms marked `unit` have validation unit tests or are intentionally covered through integration;
- every `IF-NNN` has integration coverage;
- delegated `AC-NNN` rows point to an executable route/interface path that can actually verify the acceptance criterion.

Flag:

| Problem | Severity |
|---|---:|
| Many unit claims but no unit tests planned | HIGH |
| Service unit claim without service unit test | MEDIUM/HIGH |
| Audit/model mechanism unit claim but no audit/model test | MEDIUM/HIGH |
| IF endpoint lacks integration coverage | HIGH |
| AC delegated to unrelated IF | HIGH |

Do not design the tests. Route to `/order.plan`.

## P7. Physical Grounding and Naming

Use focused repository reconnaissance.

Read at most:

- one dependency manifest;
- route registration file;
- one exemplar per touched layer;
- relevant barrel/index files;
- test exemplar files;
- docs location only if constitution/docs are relevant.

Check:

- `[MOD]` files exist;
- `[NEW]` files are plausible in repo structure;
- barrel/index files planned when needed;
- validation exports planned when route validation exists;
- route mount files planned when new endpoints exist;
- naming evidence in `plan.md` cites actual filenames;
- multi-word filenames are justified by same-layer precedent or fallback rules;
- branch field is accurate.

### Branch field

If `setup.py paths --json` returns empty `CURRENT_BRANCH` / `BRANCH`, `plan.md` must not invent a git branch.

Acceptable:

```markdown
**Branch**: `not detected`
```

or:

```markdown
**Branch**: `not detected (feature: 001-example)`
```

Suspicious:

```markdown
**Branch**: `001-example`
```

when the resolver returned no branch.

Severity: LOW/MEDIUM unless downstream tooling depends on branch identity.

## P8. Stack, Constraints, and Constitution

Check against:

- `CON-NNN` in `spec.md`;
- `Technical Context & Stack Verification`;
- `.orderspec/memory/constitution.md` if present.

### Stack evidence

Flag if plan claims verified facts without evidence:

- runtime version not found but stated as verified;
- package version not in manifests;
- test command invented;
- storage technology contradicts spec constraint;
- dependency absent but plan assumes it already exists.

Severity:

- direct `CON` violation → HIGH;
- constitution `MUST` violation → CRITICAL;
- unverified version claim → LOW/MEDIUM.

### Constitution checks

For API projects, inspect direct constitution obligations if visible.

Example:

- If constitution says route definitions and validation schemas MUST reflect API behavior:
  - plan must include route and validation files.
- If constitution says Swagger docs SHOULD be updated:
  - plan should include docs path or explicitly justify not updating docs.

Severity:

- ignored `MUST` → CRITICAL/HIGH;
- ignored important `SHOULD` without justification → MEDIUM;
- justified `SHOULD` omission → LOW/note.

Do not perform a full whole-system constitution sweep. Only inspect direct plan-relevant principles.

## P9. Spec-Rooted Defects

If the plan cannot be correct because `spec.md` is the root problem, route upward.

Examples:

- two spec requirements contradict;
- interface contract lacks status code needed by acceptance criteria;
- required behavior is impossible under stated constraints;
- NFR is measurable but has no target;
- acceptance criteria require behavior absent from requirements.

Do not “fix” the plan around this.

Route to:

```text
/order.spec "<refinement request>"
```

Severity inherits impact:

- blocks P1/MVP → CRITICAL;
- blocks non-MVP → HIGH/MEDIUM.

## Severity Rules

| Severity | Meaning |
|---|---|
| CRITICAL | MVP/P1 mapping broken; constitution MUST violation; required artifact missing; impossible/contradictory spec blocks planning |
| HIGH | Required non-MVP mapping missing/inadequate; route drift; `CON` violation; invalid mechanism semantics |
| MEDIUM | Important quality issue; risky documented/delegated choice; ignored constitution SHOULD; weak test topology |
| LOW | Advisory, minor hygiene, wording, non-blocking evidence issue |

MVP/P1 scope is determined by user journeys marked P1 in `spec.md`.

## Verdict Rules

Start with mechanical baseline:

- if any mechanical blocking finding exists → verdict cannot be PASS;
- if required artifact is missing → BLOCK;
- if upstream spec gate is known non-PASS → BLOCK;
- if only advisory upstream gate absence/staleness exists → may still PASS, but record note.

Then apply semantic findings:

- `⛔ BLOCK` if any CRITICAL exists.
- `⛔ BLOCK` if any HIGH breaks MVP/P1 mapping.
- `🔀 ROUTING REQUIRED` if any routed finding exists but no BLOCK condition exists.
- `✅ PASS` only if:
  - mechanical checks pass;
  - no routed findings remain;
  - no unresolved CRITICAL/HIGH;
  - plan is ready for `/order.tasks`.

A PASS report may contain LOW notes only if they do not require owner action.

## Routing Block Format

For every routed finding, emit this exact block in the report:

```markdown
### Routing Required: {short title}

**Finding**: {what is wrong or missing}  
**Location**: {Spec ID / mechanism row / plan section / path}  
**Owner**: `/order.plan` or `/order.spec`  
**Why owner, not gate**: {explain why this changes mechanism, mapping, stack, or contract}  
**Impact if unresolved**: {what breaks downstream}  
**Suggested direction**: {advisory, 1–2 concrete options}  
**Run**: `/order.plan "{ready-to-run refinement request}"`
```

For spec-rooted findings, use:

```markdown
**Run**: `/order.spec "{ready-to-run refinement request}"`
```

Do not interleave routing blocks with the Findings table. Put all routing blocks under `### Routing Required`.

## Report File

Always write:

```text
<feature-dir>/plan-report.md
```

Overwrite, never append.

A missing `plan-report.md` means the gate did not run.

## Shared Report Template Contract

Use the shared report template if present:

```text
.orderspec/templates/report-template.md
```

This template is the canonical gate-report shell used by OrderSpec gates.

If the template is present, render `plan-report.md` by filling its placeholders.

If the template is missing, use the embedded fallback structure in this prompt, but record a LOW finding:

```text
P0-003 shared report template missing; used embedded fallback
```

Do not invent a different report shape.

### Placeholder values for `/order.plan-check`

Fill template placeholders as follows:

| Placeholder | Value |
|---|---|
| `{report_name}` | `plan-report.md` |
| `{generator_cmd}` | `/order.plan-check` |
| `{DATE}` | current date |
| `{VERDICT}` | `✅ PASS`, `🔀 ROUTING REQUIRED`, or `⛔ BLOCK` |
| `{gate_title}` | `Plan Gate Report` |
| `{target_doc}` | `plan.md` |
| `{gate_focus}` | `spec.md + repo physical mapping` |
| `{owner_cmd}` | `/order.plan`, `/order.spec`, or `/order.plan or /order.spec` |
| `{auto_fixed_rows}` | `| — | — | — |` |
| `{routing_blocks}` | all routing blocks, or `None.` |
| `{findings_rows}` | all findings rows, or `| — | — | — | — | — | — |` |
| `{gate_specific_sections}` | plan-specific sections defined below |
| `{inventory_summary}` | pathmanifest/mechanism summary from scripts and inspection |
| `{exit_code}` | mechanical baseline exit/failure summary |
| `{floor_status}` | `none`, `non-PASS`, or `BLOCK` |
| `{report_path}` | `plan-report.md` |

The current shared `report-template.md` may use repeated generic `{n}` placeholders in Metrics.

When rendering, replace the Metrics section with concrete values by context:

```markdown
- Findings by severity: CRITICAL={critical_count} · HIGH={high_count} · MEDIUM={medium_count} · LOW={low_count}
- Auto-fixed: 0 · Routing required: {routing_count} · defer-to-plan: 0
```

For `/order.plan-check`, `defer-to-plan` is always `0` because plan-owned findings are routed, not deferred.

If there are tasking-time notes, put them in the plan-specific sections as:

```markdown
- defer-to-tasks notes: {defer_to_tasks_count}
```

### Owner command rendering

The template has one `{owner_cmd}` placeholder, but plan-check findings may route to multiple owners.

Use:

```text
/order.plan or /order.spec
```

when both owner types appear.

Use a single owner only if all routing blocks target the same command.

Each individual routing block MUST still name its exact owner.

## Gate-Specific Report Sections

Render these sections into `{gate_specific_sections}`.

```markdown
## Summary

- Mechanical baseline: {PASS / FAIL / DEGRADED}
- Semantic inspection: {PASS / FINDINGS}
- Upstream spec gate: {ok / advisory / blocked / missing}
- Ready for `/order.tasks`: {yes / no}

## Completeness Matrix

| Spec ID | Kind | Mechanism row | Coverage kind | Primary file | Test type | Adequacy | Finding |
|---------|------|---------------|---------------|--------------|-----------|----------|---------|
| REQ-001 | REQ | present | direct | `src/...` | unit | OK | — |

Include rows for:

- `REQ`
- `IF`
- `AC`
- `EDGE`
- `INV`
- `NFR`
- conditional `ASM` rows that exist or should exist

Do not include `SC`, `CON`, `UJ`, or `Q` as required mechanism rows.

## Constraint Mapping Notes

| CON ID | Honored in plan? | Evidence | Finding |
|--------|------------------|----------|---------|
| CON-001 | yes | `Technical Context` / physical files | — |

Include all `CON` IDs from `spec.md`.

Important: `CON` rows do not require mechanism rows, but they must be honored by stack and mapping decisions.

## Mechanism Summary

Paste values from:

```bash
python3 .orderspec/framework/scripts/traceability.py summarize-mechanisms --json "$FEATURE"
```

Render as:

```json
{...}
```

## Mechanical Checks

| Check | Result |
|-------|--------|
| `traceability.py lint` | PASS/FAIL |
| `traceability.py check-plan` | PASS/FAIL |
| `traceability.py check-mechanisms` | PASS/FAIL |
| `traceability.py validate --stage plan` | PASS/FAIL |
| `traceability.py summarize-mechanisms --json` | PASS/FAIL |

Include notable mechanical output if failing.

## Plan-Specific Inspector Notes

- Pathmanifest `[NEW]` count: {count or `unknown`}
- Pathmanifest `[MOD]` count: {count or `unknown`}
- Branch detected by resolver: `{CURRENT_BRANCH or "not detected"}`
- `documented` mechanism rows pointing to source files: {n}
- default `ASM` mechanism rows: {n}
- unit-test topology concerns: {n}
- route preservation concerns: {n}
- constitution concerns: {n}
- defer-to-tasks notes: {n}
```

## Embedded Fallback Report Structure

Use this only if `.orderspec/templates/report-template.md` is missing.

```markdown
<!-- plan-report.md — generated by /order.plan-check · {DATE} · verdict: {VERDICT} · overwritten each run -->

## Plan Gate Report (plan.md — spec.md + repo physical mapping)

**Verdict**: {VERDICT}

### Auto-Fixed (applied automatically — mechanical / meaning-preserving only)
| ID | What was changed | Why meaning-preserving |
|----|------------------|------------------------|
| — | — | — |

### Routing Required (owned by /order.plan or /order.spec — gate did NOT modify content)
{routing_blocks}

### Findings
| ID | Source | Severity | Disposition | Location | Summary |
|----|--------|----------|-------------|----------|---------|
{findings_rows}

{gate_specific_sections}

### Metrics
- Inventory: {inventory_summary}
- Findings by severity: CRITICAL={critical_count} · HIGH={high_count} · MEDIUM={medium_count} · LOW={low_count}
- Auto-fixed: 0 · Routing required: {routing_count} · defer-to-plan: 0
- Script exit code: {exit_code} · verdict floor applied: {floor_status}
- Report file: plan-report.md
```

## Writing the Report

Render `plan-report.md` from `.orderspec/templates/report-template.md` when available.

Steps:

1. Read `.orderspec/templates/report-template.md` if present.
2. Fill all placeholders defined in **Shared Report Template Contract**.
3. Insert the rendered plan-specific sections into `{gate_specific_sections}`.
4. Write the final report to:

   ```text
   <feature-dir>/plan-report.md
   ```

5. Overwrite, never append.

Use shell-safe write:

```bash
PATHS_JSON="$(python3 .orderspec/framework/scripts/setup.py paths --json)"
FEATURE_DIR="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["FEATURE_DIR"])' <<< "$PATHS_JSON")"
REPORT="$FEATURE_DIR/plan-report.md"
mkdir -p "$FEATURE_DIR"

cat > "$REPORT" <<'EOF'
<rendered report markdown here>
EOF
```

After writing, report to chat:

```text
Wrote plan gate report: <path>
Verdict: <verdict>
```

## Chat Response

After writing the report, respond briefly with:

- verdict;
- report path;
- number of findings by severity;
- number of routing blocks;
- whether `/order.tasks` is recommended;
- next command to run.

Do not paste the entire report to chat unless the user asks.

## Post-Execution Checks

Run the **`after_plan_check`** phase per `.orderspec/memory/hooks-protocol.md`.

If hooks are absent or not configured, skip silently per the hook protocol.

## Operating Principles

- Gates detect and route; owners fix.
- This gate writes only `plan-report.md`.
- Do not edit `plan.md`.
- Do not edit machine TSV files.
- Do not invent missing mechanisms.
- Do not overrule mechanical script findings.
- Do not duplicate the mechanism matrix into `plan.md`.
- Do not treat `CON` as requiring mechanism rows.
- Do inspect whether `CON` constraints are honored.
- Do inspect `ASM` rows for overuse.
- Do inspect documented coverage aggressively.
- Do inspect test topology.
- Do inspect route preservation.
- Do inspect direct constitution concerns.
- Do use `.orderspec/templates/report-template.md` when present.
- Do write a report every run.
- When in doubt, route rather than repair.

## Context

$ARGUMENTS