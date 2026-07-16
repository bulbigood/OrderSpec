---
orderspec:
  artifact: command_prompt
  command: order.spec-check
  phase: check
description: Per-stage gate validating spec.md for coverage, internal integrity, and contract completeness. Pure inspector; routes contractual changes to /order.spec and writes a report on every run.
---

# OrderSpec Spec Check

## Role

`/order.spec-check` is the independent inspection gate for `spec.md`.
It runs after `/order.spec` and answers: Is `spec.md` a complete, internally consistent, repo-independent, testable feature contract?

This command acts as **semantic glue** between deterministic scripts. It does not perform mechanical counting, matrix generation, or manual ID parsing. All such data is provided by `traceability.py`.

## Command Context Bootstrap

1. Resolve command context:
   ```bash
   python3 .orderspec/framework/scripts/command_context.py resolve order.spec-check --json
   ```
2. If `ok` is `false` or `missing_required` is non-empty, STOP and report missing required context.
3. Read every file returned in `to_read`, in returned order.
4. Interpret each file by `usage`.

## Target Feature Resolution

1. Initialize feature paths and report template:
   ```bash
   python3 .orderspec/framework/scripts/setup.py spec-check --json --refresh-template > /dev/null
   eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
   ```
   This resolves `$FEATURE_DIR`, `$FEATURE_ID`, and other path variables, and copies the report template to `$FEATURE_DIR/spec-report.md` for you to fill.

2. Validate active feature state:
   ```bash
   python3 .orderspec/framework/scripts/active_feature.py get --json
   python3 .orderspec/framework/scripts/active_feature.py validate --json
   ```
3. If active state validation fails, write BLOCK report with `S0-003 (HIGH): active feature state invalid`, then stop.
4. If `$ARGUMENTS` contains an explicit feature reference, resolve it read-only using `active_feature.py list --json`.
   - If ambiguous: `S0-004 (HIGH): ambiguous feature reference`.
   - If not found: `S0-005 (HIGH): feature not found`.
5. Do not use `active_feature.py select` in this gate.
6. If no target is resolved, write BLOCK report with `S0-000 (CRITICAL): no active feature`.

## Mechanical Validation

Run the deterministic validator:

```bash
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" init
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" extract-spec-ids
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" validate --stage spec --json
```

The JSON output is the **ground truth** for mechanical findings, inventory, categories, matrices, and contradiction grid data.
You MUST import all findings exactly as provided, including their `severity` and `disposition`.
You MUST NOT downgrade or suppress imported findings.

## Semantic Inspection

Read `spec.md`. Perform the following checks that require LLM judgment.
For any semantic finding, assign disposition `Route` and create a routing block.
Keep each mechanical finding's `severity` and `disposition` exactly as provided by
`traceability.py`; create a routing block for it only when its imported disposition
is `Route`.

**Important**: Semantic findings (S1-xxx) must be integrated into the report's Findings table alongside mechanical findings from traceability.py. Each semantic finding gets its own row with:
- `ID`: S1-NNN
- `Source`: "semantic"
- `Severity`: CRITICAL/HIGH/MEDIUM/LOW
- `Disposition`: "Route"
- `Location`: spec section or ID
- `Summary`: concise description

### S1-001 REQ Contradictions
Verify no REQ contradicts another REQ, INV, or project contract constraint.
MVP/core contradiction → Route (CRITICAL or HIGH).

### S1-002 AC vs REQ/IF
Verify ACs do not contradict covered REQs or IFs.
Contradiction → Route (HIGH).

### S1-003 Narrowing ASMs
For every `[narrowing REQ-NNN]` ASM, verify all REQ cases are still satisfied.
If narrowing silently excludes required action/state → Route (HIGH).

### S1-004 NFR vs Scope
NFR must not mandate behaviour excluded in §2 Out of Scope.
Contradiction → Route (HIGH).

### S1-005 Quantitative NFR Hallucination
For each quantitative NFR threshold, verify it appears in user input or project contracts.
Threshold without source → Route (HIGH).

### S1-006 Qualitative NFR Oracle
Every NFR needs an oracle (sourced threshold, named standard, or qualitative SHOULD).
MUST-level qualitative NFR without oracle → Route (MEDIUM or HIGH).

### S1-007 REQ Testability
Every REQ must be observable and verifiable.
Untestable MVP/core REQ → Route (HIGH). Untestable non-core → Route (MEDIUM).

### S1-008 Scope Sizing
Assess cohesion. Oversized but coherent → Route (MEDIUM) recommending `/order.spec --split`.

### S1-009 Cross-Section Contradictions
Compare REQ/INV/IF wording with EDGE, DEC, ASM, information-model fields, and
out-of-scope statements. Do not limit contradiction review to the §10 grid:
for example, an EDGE claiming an empty post-create history conflicts with a
REQ that mandates a create audit entry, and a DEC choosing full snapshots may
conflict with a REQ that promises changed-field deltas.
Contradiction affecting P1 behaviour → Route (HIGH or CRITICAL).

### S1-010 Multi-Entity Failure Semantics
When one user operation writes more than one entity or persistence record and
the contract says exactly one, every, or MUST produce, verify that the
contract specifies atomic, best-effort, compensating, or partial-failure
semantics and the observable result of failure. Missing semantics → Route
(HIGH). Do not leave this as an unrecorded ASM.

### S1-011 Interface Input/Response Completeness
For every IF, reconcile every declared input option with success/failure
behaviour and response shape. Pagination requires an envelope or a referenced
project convention with bounds, ordering, and empty-page semantics. Filters,
optional fields, nullability, and malformed identifiers need explicit
observable outcomes. Missing contract detail → Route (HIGH for P1, MEDIUM
otherwise).

### S1-012 Absolute Guarantee Scope
For invariants using exactly, every, always, or never, identify all
supported write paths and failure states covered by the guarantee. If the
scope is only successful requests, or only HTTP routes, say so in the
contract; otherwise route the missing boundary/partial-failure decision.
Ambiguous P1 guarantee scope → Route (HIGH).

## Report Generation

The report template has already been copied to `$FEATURE_DIR/spec-report.md` by `setup.py spec-check --refresh-template` in the Target Feature Resolution step.

You MUST fill this template file in place. Do not invent report sections, table structures, or alter the YAML frontmatter schema. Fill the template variables exactly as specified using the data from `traceability.py` JSON output and your semantic findings.

### CRITICAL: Data Source Rules
- Do NOT read `spec.md` to fill matrices, categories, or inventory. Use ONLY the JSON fields from `traceability.py`.
- If a JSON field is missing or empty, render the cell as `(none)` or `—`.
- Render booleans as text: `true` → `yes`, `false` → `no`.
- Join arrays with `, ` (comma + space).

### Template Variable Mapping Guide

Map the JSON output from `traceability.py validate` to the template variables:

**YAML Frontmatter** (replace placeholders at top of file):
- `{generator_cmd}`: `order.spec-check`
- `{model_name}`: identifier of the AI model running this command
- `{DATE}`: current ISO 8601 timestamp
- `{VERDICT}`: computed from findings (see Verdict table below)
- `{FEATURE_ID}`: from `$FEATURE_ID` shell variable
- `{FEATURE_DIR}`: from `$FEATURE_DIR` shell variable

**HTML Comment Header** (second line of body):
- `{report_name}`: `spec-report.md`
- All other variables same as frontmatter

**Body Section Variables** — map from `traceability.py validate` JSON:
- `{gate_title}`: `Spec Check`
- `{target_doc}`: `spec.md`
- `{gate_focus}`: `completeness, consistency, testability`
- `{auto_fixed_rows}`: `(none)` — gates do not auto-fix
- `{routing_blocks}`: insert routing blocks for all findings with disposition `Route`
- `{deferred_rows}`: `(none)` — spec-check defers nothing to plan
- `{findings_rows}`: combine mechanical findings (from `findings` array) with semantic findings (S1-xxx). Each row: `| ID | Source | Severity | Disposition | Location | Summary |`
- `{coverage_taxonomy_rows}`: from `categories` object. Each row: `| Category | § | Status | Disposition |`. Use the `categories` value as the Status string. `missing` MVP/core → Route (HIGH); `empty`/`partial` → Route (MEDIUM)
- `{contradiction_grid_rows}`: from `contradiction_grid` array. Each row: `| Pair | Verdict | Reason |`. If `tension` is non-empty, render Reason as `{tension} — {reason}`. Example row: `| INV-001 × ASM-002 | compatible | ASM-002 narrows the mechanism — REQ-002 is a specific instance |`
- `{journey_matrix_rows}`: from `matrices.uj_coverage` array. Each row: `| UJ | Priority | Covers REQs | ACs | ACs trace to REQs | Status |`. Example row: `| UJ-001 | P1 | REQ-001, REQ-002 | AC-001, AC-002 | yes | ok |`
- `{if_matrix_rows}`: from `matrices.if_coverage` array. Each row: `| IF | Kind | Actor | Success | Failure | Covered by ACs | Status |`. Example row: `| IF-001 | HTTP endpoint | Authenticated user | 201 | 400, 401 | AC-001, AC-002 | ok |`

**Metrics Section**:
- `{inventory_summary}`: formatted string from `inventory` object, e.g. `REQ=10 · NFR=2 · SC=3 · ... · Total=64`
- `{critical_count}`, `{high_count}`, `{medium_count}`, `{low_count}`: counts from combined findings
- `{auto_fixed_count}`: `0`
- `{routing_count}`: count of findings with disposition `Route`
- `{deferred_count}`: `0`
- `{exit_code}`: from `summary.exit_code`
- `{floor_status}`: `yes` if `verdict_floor` applied, `no` otherwise
- `{report_path}`: `$FEATURE_DIR/spec-report.md`

### Routing Block Format
```markdown
### Routing Required: {short title}

**Finding**: {what is wrong or missing}
**Location**: {ID / section / missing category}
**Why owner, not gate**: {why this changes contract meaning/scope/test obligation}
**Impact if unresolved**: {downstream impact}
**Suggested direction**: {advisory only}
**Run**: `/order.spec "{ready-to-run refinement request}"`
```

### Verdict
| Verdict | Conditions |
|---|---|
| BLOCK | any routed CRITICAL/HIGH; traceability failure; spec missing |
| ROUTING_REQUIRED | no routed CRITICAL/HIGH, but at least one routed MEDIUM/LOW |
| PASS | traceability succeeded and no routed findings remain |

## Completion Response

After writing the report, respond in chat with:
- Verdict (BLOCK, ROUTING_REQUIRED, or PASS)
- Report path
- Number of findings by severity
- Manual/orchestrator next action:
  - PASS -> human or orchestrator may start `/order.plan`
  - ROUTING_REQUIRED/BLOCK -> human or orchestrator may run routed `/order.spec` request(s), then rerun `/order.spec-check`
