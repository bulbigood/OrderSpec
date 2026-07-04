---
orderspec:
  artifact: command_prompt
  command: order.plan-check
  phase: check
description: Per-stage gate validating plan.md as a faithful, complete, role-pure physical mapping of spec.md onto the current repository. Pure inspector; routes plan defects to /order.plan and contract defects to /order.spec; writes plan-report.md on every run.
handoffs:
  - label: "Proceed to Tasks"
    agent: "order.tasks"
    prompt: "/order.tasks"
  - label: "Fix Plan"
    agent: "order.plan"
    prompt: "/order.plan"
  - label: "Fix Spec"
    agent: "order.spec"
    prompt: "/order.spec"
---

# OrderSpec Plan Check

## Role

`/order.plan-check` is the independent inspection gate for `plan.md`.
It runs after `/order.plan` and answers: Is `plan.md` a faithful, complete, physically grounded, role-pure mapping of the stable `spec.md` contract onto the current repository state?

This command acts as **semantic glue** between deterministic scripts. It does not perform mechanism counting, pathmanifest parsing, or ID validation manually. All such data is provided by `traceability.py`.

This gate is a **pure inspector**. It writes only `plan-report.md`. It MUST NOT edit `spec.md`, `plan.md`, `tasks.md`, `.state/*.tsv`, or source code.

## Command Context Bootstrap

1. Resolve command context:
   ```bash
   python3 .orderspec/framework/scripts/command_context.py resolve order.plan-check --json
   ```
2. If `ok` is `false` or `missing_required` is non-empty, STOP and report missing required context.
3. Read every file returned in `to_read`, in returned order.
4. Interpret each file by `usage`.

## Target Feature Resolution

1. Initialize feature paths and report template:
   ```bash
   python3 .orderspec/framework/scripts/setup.py plan-check --json --refresh-template > /dev/null
   eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
   ```
   This resolves `$FEATURE_DIR`, `$FEATURE_ID`, and other path variables, and copies the report template to `$FEATURE_DIR/plan-report.md` for you to fill.

2. Validate active feature state:
   ```bash
   python3 .orderspec/framework/scripts/active_feature.py get --json
   python3 .orderspec/framework/scripts/active_feature.py validate --json
   ```
3. If active state validation fails, write BLOCK report with `P0-003 (HIGH): active feature state invalid`, then stop.
4. If `$ARGUMENTS` contains an explicit feature reference, resolve it read-only using `active_feature.py list --json`.
   - If ambiguous: `P0-004 (HIGH): ambiguous feature reference`.
   - If not found: `P0-005 (HIGH): feature not found`.
5. Do not use `active_feature.py select` in this gate.
6. If no target is resolved, write BLOCK report with `P0-000 (CRITICAL): no active feature`.

## Upstream Gate Guard

A plan-check MUST NOT issue PASS over a known failed spec gate.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

python3 .orderspec/framework/scripts/upstream_gate.py \
  --report        "$FEATURE_DIR/spec-report.md" \
  --artifact      "$FEATURE_SPEC" \
  --upstream-name "spec.md" \
  --this          "/order.plan-check" \
  --build         "/order.spec" \
  --fix           "/order.spec" \
  --recheck       "/order.spec-check"
```

Interpret exit codes:
- **exit 2 (stop)** — upstream artifact (`spec.md`) missing. Write BLOCK report with `P0-006 (CRITICAL): upstream spec.md missing`, route to `/order.spec`, then stop.
- **exit 1 (halt)** — spec gate report exists and is non-PASS. Write BLOCK report with `P0-007 (HIGH): upstream spec gate non-PASS (verdict: {verdict})`, route to `/order.spec` then `/order.spec-check`, then stop.
- **exit 0 (advisory)** — spec gate report absent or stale. Proceed, but record `P0-008 (LOW): spec gate advisory ({reason})`.
- **exit 0 (ok)** — Proceed.
- **exit 64 (error)** — invocation error (empty arguments). Write BLOCK report with `P0-009 (HIGH): upstream_gate invocation error`.

Do not use `--force` in this gate. If the operator wants to plan over a failed spec gate, they do that via `/order.plan --force`; this gate still records the upstream condition.

## Mechanical Validation

Run the deterministic validator:

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" init
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" extract-spec-ids
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" lint
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" check-plan
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" check-mechanisms
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" validate --stage plan --json
```

The JSON output of `validate --stage plan --json` is the **ground truth** for mechanical findings, inventory, categories, matrices, and contradiction grid data.
You MUST import all findings exactly as provided, including their `severity` and `disposition`.
You MUST NOT downgrade or suppress imported findings.

If a script crashes or returns unparseable output, record `P0-001 (HIGH): mechanical validator unavailable` and route to maintainer/tooling. If a script reports a finding you suspect is a script bug, record `P0-002 (MEDIUM): suspected script-pattern bug` alongside the original finding — never suppress the original.

## Semantic Inspection

Read `plan.md`, `spec.md`, and `.state/mechanisms.tsv` (via `traceability.py get` / `summarize-mechanisms --json`). Perform the following checks that require LLM judgment.
For any finding, assign disposition `Route` and create a routing block.

**Important**: Semantic findings (P1-xxx) must be integrated into the report's Findings table alongside mechanical findings. Each semantic finding gets its own row with:
- `ID`: P1-NNN
- `Source`: "semantic"
- `Severity`: CRITICAL/HIGH/MEDIUM/LOW
- `Disposition`: "Route"
- `Location`: plan section, Spec ID, or mechanism row
- `Summary`: concise description

### P1-001 Artifact Hygiene
Check `plan.md` for template residue, placeholder tokens, stale comments from `plan-template.md`, a Markdown mechanism table, or copied self-check checklists.
Residue present → Route (HIGH for template placeholders / mechanism table; MEDIUM/LOW for minor comments).

### P1-002 Role Purity — Spec Duplication
Verify `plan.md` does not restate the Executive Summary, duplicate full interface contracts, or redraw spec logical diagrams.
Duplication → Route (MEDIUM).

### P1-003 Role Purity — New Behavior Invented
Verify `plan.md` does not add new product behavior, status codes, fields, roles, permissions, TTLs, jobs, or NFR numbers absent from `spec.md`.
Externally visible contract drift → Route (CRITICAL if MVP/P1, else HIGH). Non-behavioral overreach → Route (MEDIUM).

### P1-004 Mechanism Adequacy — Documented Misuse
For each `mechanisms.tsv` row with `coverage_kind=documented`, verify:
- `primary_files` is `plan.md` or a repo-relative documentation artifact in the `pathmanifest` — not a source file (`.js`, `.ts`, `.py`, `.go`, `.java`, `.rb`, `.php`, `.cs`).
- MUST-level NFRs are not marked `documented` without justification.
- Required behavior is not marked `documented` to avoid testing.
Violation → Route (HIGH; CRITICAL if MVP/P1 behavior evades testing).

### P1-005 Mechanism Adequacy — Delegation Semantics
For each `coverage_kind=delegated:<ID>` row, verify the delegation target semantically covers the source ID (e.g., an AC delegated to an IF that actually verifies that criterion; an EDGE delegated to a generic endpoint without explicit edge coverage is invalid).
Invalid delegation → Route (HIGH).

### P1-006 Route / Interface Preservation
For every `IF-NNN` in `spec.md`, verify `plan.md` preserves method, externally visible path, mounted route prefix, and status codes. No extra endpoint should appear unless present in `spec.md`.
Route drift (e.g., spec `GET /v1/tasks/:taskId/audit` mapped to a file mounted under unrelated prefix without explicit note) → Route (HIGH; CRITICAL if MVP/P1).

### P1-007 Test Topology
Compare `mechanisms.tsv` test claims with `pathmanifest`:
- `test_type=unit` rows have plausible unit test files in the relevant layer.
- Service/model mechanisms marked `unit` have corresponding unit tests or explicit justification.
- Every `IF-NNN` has integration coverage.
- Delegated `AC-NNN` rows point to an executable path that can actually verify the AC.
Implausible topology → Route (HIGH for missing IF integration; MEDIUM/HIGH for service/model unit gaps).

### P1-008 Physical Grounding & Naming
Use focused reconnaissance (hard cap ~10 files: one manifest, route registration, exemplars per touched layer, barrel/index files, test exemplar).
Verify:
- `[MOD]` files exist; `[NEW]` files are plausible in repo structure.
- Barrel/index files planned when needed; route mount files planned when new endpoints exist.
- Multi-word filename naming cites actual same-layer precedent or fallback rules.
- Branch field is accurate; if `setup.py paths` returned empty branch, `plan.md` must say `not detected` — not invent a branch.
Violation → Route (MEDIUM; LOW for minor naming).

### P1-009 Stack, Constraints & Constitution
Check against `CON-NNN` in `spec.md`, `Technical Context & Stack Verification` in `plan.md`, and project contracts (`constitution.md`, `stack.md`, `architecture.md`, `conventions.md`):
- Verified facts have evidence (runtime/package versions found in manifests; test commands real).
- `CON` constraints honored by stack and mapping decisions.
- Constitution `MUST` obligations reflected (e.g., route + validation files planned when constitution mandates them).
Violation → Route (CRITICAL for constitution MUST; HIGH for direct CON violation; LOW/MEDIUM for unverified version claims).

### P1-010 Spec-Rooted Defect
If `plan.md` cannot be correct because `spec.md` is the root problem (contradictions, missing status codes needed by ACs, impossible constraints, measurable NFR without target), route upward.
Route to `/order.spec` (CRITICAL if blocks MVP/P1; HIGH/MEDIUM otherwise). Do not "fix" the plan around a spec defect.

### P1-011 Conditional ASM Overuse
For `ASM-NNN` rows in `mechanisms.tsv`: if the ASM is `[default]` and merely restates normal behavior without implementation significance, flag unnecessary mechanism row. If `[narrowing ...]` and materially affects implementation, a mechanism row is appropriate.
Unjustified default ASM mechanism → Route (MEDIUM).

## Report Generation

The report template has already been copied to `$FEATURE_DIR/plan-report.md` by `setup.py plan-check --refresh-template` in the Target Feature Resolution step.

You MUST fill this template file in place. Do not invent report sections, table structures, or alter the YAML frontmatter schema. Fill the template variables exactly as specified using the data from `traceability.py` JSON output and your semantic findings.

### CRITICAL: Data Source Rules
- Do NOT read `plan.md` or `spec.md` to fill matrices, categories, or inventory. Use ONLY the JSON fields from `traceability.py`.
- If a JSON field is missing or empty, render the cell as `(none)` or `—`.
- Render booleans as text: `true` → `yes`, `false` → `no`.
- Join arrays with `, ` (comma + space).

### Template Variable Mapping Guide

Map the JSON output from `traceability.py validate --stage plan` to the template variables:

**YAML Frontmatter** (replace placeholders at top of file):
- `{generator_cmd}`: `order.plan-check`
- `{model_name}`: identifier of the AI model running this command
- `{DATE}`: current ISO 8601 timestamp
- `{VERDICT}`: computed from findings (see Verdict table below)
- `{FEATURE_ID}`: from `$FEATURE_ID` shell variable
- `{FEATURE_DIR}`: from `$FEATURE_DIR` shell variable

**HTML Comment Header** (second line of body):
- `{report_name}`: `plan-report.md`
- All other variables same as frontmatter

**Body Section Variables** — map from `traceability.py validate` JSON:
- `{gate_title}`: `Plan Check`
- `{target_doc}`: `plan.md`
- `{gate_focus}`: `physical mapping, mechanism completeness, role purity`
- `{auto_fixed_rows}`: `(none)` — gates do not auto-fix
- `{routing_blocks}`: insert routing blocks for all findings with disposition `Route`
- `{deferred_rows}`: `(none)` — plan-check defers nothing
- `{findings_rows}`: combine mechanical findings (from `findings` array) with semantic findings (P1-xxx). Each row: `| ID | Source | Severity | Disposition | Location | Summary |`
- `{coverage_taxonomy_rows}`: from `categories` object. Each row: `| Category | § | Status | Disposition |`. Example row: `| Functional Requirements | §4 | present — 10 REQs | — |`. `missing` MVP/core → Route (HIGH); `empty`/`partial` → Route (MEDIUM)
- `{contradiction_grid_rows}`: from `contradiction_grid` array. Each row: `| Pair | Verdict | Reason |`. If `tension` is non-empty, render Reason as `{tension} — {reason}`.
- `{journey_matrix_rows}`: from `matrices.uj_coverage` array. Each row: `| UJ | Priority | Covers REQs | ACs | ACs trace to REQs | Status |`.
- `{if_matrix_rows}`: from `matrices.if_coverage` array. Each row: `| IF | Kind | Actor | Success | Failure | Covered by ACs | Status |`.

**Metrics Section**:
- `{inventory_summary}`: formatted string from `inventory` object, e.g. `REQ=10 · NFR=2 · SC=3 · ... · Total=64`
- `{critical_count}`, `{high_count}`, `{medium_count}`, `{low_count}`: counts from combined findings
- `{auto_fixed_count}`: `0`
- `{routing_count}`: count of findings with disposition `Route`
- `{deferred_count}`: `0`
- `{exit_code}`: from `summary.exit_code`
- `{floor_status}`: `yes` if `verdict_floor` applied, `no` otherwise
- `{report_path}`: `$FEATURE_DIR/plan-report.md`

### Routing Block Format
```markdown
### Routing Required: {short title}

**Finding**: {what is wrong or missing}
**Location**: {ID / section / mechanism row / path}
**Why owner, not gate**: {why this changes mechanism, mapping, stack, or contract}
**Impact if unresolved**: {downstream impact}
**Suggested direction**: {advisory only}
**Run**: `/order.plan "{ready-to-run refinement request}"`  OR  `/order.spec "{ready-to-run refinement request}"`
```

Use `/order.plan` for plan-owned defects (mapping, mechanism, pathmanifest, topology, grounding).
Use `/order.spec` for spec-rooted defects (contract contradiction, missing contract decision, impossible constraint).

### Verdict
| Verdict | Conditions |
|---|---|
| BLOCK | any routed CRITICAL; any routed HIGH that breaks MVP/P1 mapping; upstream spec gate non-PASS; required artifact missing; traceability failure |
| ROUTING_REQUIRED | no BLOCK condition, but at least one routed MEDIUM/LOW |
| PASS | traceability succeeded, no routed findings remain, no unresolved CRITICAL/HIGH |

MVP/P1 scope is determined by user journeys marked P1 in `spec.md`.

## Completion Response

After writing the report, respond in chat with:
- Verdict (BLOCK, ROUTING_REQUIRED, or PASS)
- Report path
- Number of findings by severity
- Number of routing blocks
- Next action:
  - PASS -> proceed to `/order.tasks`
  - ROUTING_REQUIRED/BLOCK -> run routed `/order.plan` and/or `/order.spec` request(s), then rerun `/order.plan-check`
