---
orderspec:
  artifact: command_prompt
  command: order.spec-check
  phase: check
description: Inspect spec.md for completeness, consistency, role purity, and testability; write spec-report.md and route defects.
---

## Role

`/order.spec-check` is the independent gate for `spec.md`. It answers whether the
spec is a complete, internally consistent, repository-independent, testable
WHAT-contract.

This gate is a **pure inspector**. It may overwrite only the resolved target's
`spec-report.md`. It MUST NOT edit `spec.md`, other feature artifacts, runtime
state, traceability state, project contracts, framework files, or source code.
After report finalization it may invoke only the loaded blocking-feedback
protocol's script-owned bookkeeping for a cross-owner route.
Mechanical evidence comes only from framework scripts; semantic judgment stays
bounded to the checks below. After context succeeds and a safe target exists, the
gate writes a report for an artifact precondition failure. Validator failure
before report initialization preserves prior evidence. A later setup or report
finalization failure blocks completion; the current report remains untrusted
until fresh setup or finalization succeeds. The gate never presents unvalidated
output as completed evidence and routes defects to owners.

## User Input

```text
$ARGUMENTS
```

This gate always targets active feature. Unflagged text is semantic inspection
guidance: it may add attention but never narrow checks or select another
feature. No controls are supported.

## Severity Model

Severity measures contract impact, not whether inspection can continue:

- **CRITICAL**: no coherent implementation can satisfy the core contract, or a
  contradiction creates systemic security, privacy, corruption, or irreversible
  data-loss risk.
- **HIGH**: a P1/core obligation is contradictory, unimplementable, or untestable.
- **MEDIUM**: a non-core contract defect or material ambiguity.
- **LOW**: informational sizing or minor clarity issue with no contract risk.

A missing prerequisite may require a BLOCK report without inflating its severity
to CRITICAL.

## 1. Resolve Context and Target

Run before other inspection or mutation:

```bash
python3 .orderspec/framework/scripts/command_context.py resolve order.spec-check \
  --arguments "$ARGUMENTS" --json
```

If `ok` is false, `missing_required` is non-empty, or target resolution failed,
stop in chat. When no safe feature directory was resolved, no report may be
written. Read every `to_read` entry once, in returned order, according to its
`usage` and `authority`.

Use only `target.feature_directory` and `target.feature_id` from resolver output;
do not resolve the target again. Use only resolver-parsed semantic input; do not
parse raw input again.

If `<target.feature_directory>/spec.md` is absent, initialize the report for that
literal target:

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py spec-check \
  --feature-dir "<target.feature_directory>" \
  --refresh-template --shell-vars)"
```

If setup fails, stop. Otherwise fill the report as BLOCK with operational finding
`S0-001 (HIGH): spec.md missing`, route it to `/order.spec`, replace every other
template placeholder with `(none)`, `—`, `0`, or `unavailable` as appropriate,
and stop. Do not fabricate validator JSON; deterministic finalization is
unavailable without it.

## 2. Mechanical Validation

Run the validator read-only:

```bash
MECHANICAL_RESULT_FILE="$(mktemp "${TMPDIR:-/tmp}/orderspec-spec-check.XXXXXX.json")" || exit 2
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" \
  --feature-dir "<target.feature_directory>" validate --stage spec --json \
  > "$MECHANICAL_RESULT_FILE"
MECHANICAL_RC=$?
```

Exit 0 or 1 is a completed validation; exit 1 means its JSON contains blocking
mechanical findings. Parse the file and require valid JSON. Its `findings`,
`summary`, `inventory`, `categories`, `matrices`, and `contradiction_grid` are
authoritative. Import every mechanical finding unchanged, including ID,
severity, disposition, location, and message. Never suppress, downgrade,
reinterpret, or duplicate one.

Any other exit, empty output, or invalid JSON is an authoritative framework
failure. Preserve any prior `spec-report.md`, stop without feature mutation, and
report the observed exit/error under `Framework concerns`. Do not invent
mechanical evidence or run the report finalizer against fabricated JSON.

After valid JSON is available, initialize a fresh report for the same literal
target:

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py spec-check \
  --feature-dir "<target.feature_directory>" \
  --refresh-template --shell-vars)"
```

If setup fails, stop with its result. Do not continue with a stale or partial
template. Because setup may already have refreshed the report, describe it as
untrusted and require a rerun; do not claim prior evidence was preserved.

## 3. Semantic Inspection

Use the already loaded `spec.md` only for semantic judgment. Do not manually count
IDs, generate matrices, or use prose parsing to override validator output.

Process checks in numeric order, one bounded semantic judgment at a time. Finish
and record one check before starting the next; do not replace them with a combined
free-form review. Emit at most one row per semantic check ID; aggregate that
check's locations and summary, using the highest applicable severity. Do not
repeat a mechanical finding or report one defect under overlapping semantic
checks. Semantic findings use `Source: semantic` and disposition `Route`, except
S1-008's informational case. Operational findings use `Source: operational` and
`S0-NNN`.

### S1-001 — REQ contradictions

Compare each REQ with other REQs, INVs, and project constraints. Route HIGH for
P1/core and MEDIUM otherwise; use CRITICAL only under the severity model.

### S1-002 — Acceptance fidelity

Verify each AC agrees with every covered REQ and IF, including observable result
and failure. Route HIGH for P1/core, MEDIUM otherwise.

### S1-003 — Narrowing assumptions

For every `[narrowing REQ-NNN]` assumption, verify all required cases remain
satisfied. Silent exclusion is HIGH for P1/core and MEDIUM otherwise.

### S1-004 — NFR versus scope

Verify no NFR mandates out-of-scope behaviour. Route a MUST/core contradiction
HIGH and another material contradiction MEDIUM.

### S1-005 — Quantitative NFR provenance

Every quantitative threshold must cite `user-request` or a valid loaded
project-contract ID. Historical user intent cannot be reconstructed; missing or
contradictory provenance is the defect. Route MUST/core boundaries HIGH and
SHOULD/advisory thresholds MEDIUM.

### S1-006 — Qualitative NFR oracle

Every NFR needs a usable oracle: sourced threshold, named standard, or sufficiently
precise qualitative SHOULD. An unverifiable MUST is HIGH; a vague SHOULD is
MEDIUM.

### S1-007 — Requirement testability

Every REQ must expose a verifiable outcome. Route HIGH for P1/core and MEDIUM
otherwise.

### S1-008 — Scope cohesion

An oversized but cohesive contract is Informational (LOW) and may recommend
`/order.spec --split`; it does not block planning. Independently releasable or
conflicting scope groups are Route (MEDIUM).

### S1-009 — Cross-section contradictions

Compare REQ/INV/IF with EDGE, DEC, ASM, information fields, and Out of Scope.
S1-001 owns direct REQ-vs-REQ/INV/project conflicts; do not duplicate them here.
Route HIGH for P1/core and MEDIUM otherwise; use CRITICAL only under the severity
model.

### S1-010 — Multi-record failure semantics

When one operation must write multiple logical records, require an observable
atomic, partial, best-effort, or compensating guarantee and failure result.
Missing semantics is HIGH. Do not infer an implementation mechanism.

### S1-011 — Interface completeness

Reconcile every input option, optionality/nullability rule, authorization rule,
success shape, failure, and malformed identifier. Pagination needs bounds,
ordering, envelope, and empty-page semantics, defined locally or by a valid
project convention. Missing P1/core meaning is HIGH; otherwise MEDIUM.

### S1-012 — Absolute guarantee scope

For `exactly`, `every`, `always`, or `never`, verify the contract identifies the
supported operations and failure states covered. Ambiguous P1/core scope is HIGH;
otherwise MEDIUM.

### S1-013 — Applicable category completeness

Use validator `categories` only as inventory evidence; judge applicability from
the feature contract:

- missing/incomplete functional requirements, journeys/ACs, success outcomes, or
  applicable project constraints: HIGH;
- applicable information model or interfaces: HIGH for P1/core, MEDIUM otherwise;
- logical behaviour, invariants, or edges: MEDIUM, raised to HIGH only when P1/core
  becomes unimplementable or untestable;
- NFR, DEC, ASM, Q, glossary, or changelog: no finding when inapplicable or
  explicitly `None`/`N/A`.

The validator currently distinguishes `present...` and `missing`, not semantic
`empty` or `partial`; do not claim otherwise.

### S1-014 — Role purity

Verify normative contract content remains repository- and stack-independent.
Technology or library names, versions, repository paths, code symbols, physical
components, database/query syntax, and implementation mechanisms are defects.
Interface addresses such as HTTP paths, event names, and command syntax are
contract data, not repository paths. Route HIGH when impurity controls P1/core
meaning or makes the stable contract depend on one implementation; otherwise
MEDIUM. Do not duplicate a mechanical finding for the same text.

## 4. Render the Report

Fill the setup-created `$FEATURE_DIR/spec-report.md` in place. Preserve the
canonical template structure and frontmatter. Report rendering may format
validator JSON but MUST NOT reinterpret it. Escape Markdown table pipes and
collapse embedded newlines in cells.

Use these fixed values:

| Placeholder | Value |
|---|---|
| `{generator_cmd}` | `order.spec-check` |
| `{model_name}` | current model identifier |
| `{DATE}` | current ISO 8601 timestamp |
| `{VERDICT}` | combined verdict defined below |
| `{FEATURE_ID}` | `$FEATURE_ID` |
| `{FEATURE_DIR}` | `$FEATURE_DIR` |
| `{report_name}` | `spec-report.md` |
| `{gate_title}` | `Spec Check` |
| `{target_doc}` | `spec.md` |
| `{gate_focus}` | `completeness, consistency, testability` |
| `{routing_blocks}` | one block per routed finding, or `(none)` |
| `{deferred_rows}` | `| (none) | — | — |` |
| `{deferred_count}` | `0` |
| `{report_path}` | `$FEATURE_DIR/spec-report.md` |

Map validator JSON without adding evidence:

- `findings_rows`: all mechanical rows plus semantic/operational rows, each
  `| ID | Source | Severity | Disposition | Location | Summary |`; use the
  template's `(none)` row when empty.
- `coverage_taxonomy_rows`: one row per `categories` entry; disposition is the
  related S1-013 disposition or `—`. Canonical section labels are: Success=§2,
  Glossary=§3, Functional=§4, NFR=§5, Project=§6, Architecture=§7,
  Information=§8, Interface=§9, Invariants=§10, Edge=§11, Acceptance/UJ=§12,
  Questions=§13, Decisions=§14, Assumptions=§15, Changelog=§16.
- `contradiction_grid_rows`: `pair`, `verdict`, then `tension — reason` (omit
  the separator when tension is empty).
- `journey_matrix_rows`: each `matrices.uj_coverage` entry in the template's
  column order; render booleans as `yes`/`no` and arrays joined by `, `.
- `if_matrix_rows`: each `matrices.if_coverage` entry in the template's column
  order; arrays joined by `, `.
- `inventory_summary`: `inventory` entries as `KEY=value`, joined by ` · `.
- `{critical_count}`, `{high_count}`, `{medium_count}`, `{low_count}`, and
  `{routing_count}`: compute from combined report findings.
- `exit_code`: `summary.exit_code`.
- `floor_status`: `yes` when `summary.verdict_floor` is not `PASS`, else `no`.

Missing or empty JSON values render as `(none)` for a whole empty table and `—`
for an empty cell. Do not derive these tables from `spec.md`.

Create one routing block for every finding whose disposition is `Route`:

```markdown
### Routing Required: {short title}

**Finding**: {defect}
**Location**: {ID or section}
**Why owner, not gate**: {contract meaning the gate cannot choose}
**Impact if unresolved**: {downstream effect}
**Suggested direction**: {advisory only}
**Run**: `/order.spec "{bounded refinement request}"`
```

All completed-validation content findings route to `/order.spec`. Do not put an
informational finding in routing blocks.

Compute the combined verdict exactly:

| Verdict | Condition |
|---|---|
| `BLOCK` | any routed CRITICAL/HIGH, or mechanical `summary.exit_code != 0` |
| `ROUTING_REQUIRED` | no BLOCK condition and at least one routed finding |
| `PASS` | completed mechanical validation and no routed finding |

Use the same verdict in frontmatter, body, and metrics.

## 5. Finalize Deterministically

After completed mechanical validation, validate report fidelity:

```bash
python3 .orderspec/framework/scripts/validate_gate_report.py \
  "$FEATURE_DIR/spec-report.md" \
  --mechanical "$MECHANICAL_RESULT_FILE" --json
REPORT_RC=$?
if [ "$REPORT_RC" -eq 0 ]; then rm -f "$MECHANICAL_RESULT_FILE"; fi
```

Do not complete while `REPORT_RC` is non-zero. Correct only rendering from the
already collected evidence, then rerun. Never alter the inspected artifact to
make the report pass. On finalizer failure without a safe rendering correction,
stop, label the current report untrusted in chat, and report the framework
concern. Do not cite that report as completed gate evidence.

## Completion Response

Report verdict, report path, finding counts by severity, and next action:

- PASS: human/orchestrator may run `/order.plan`;
- content BLOCK or ROUTING_REQUIRED: run routed `/order.spec` request(s), then
  rerun `/order.spec-check`;
- framework failure: resolve the reported framework concern, then rerun the check.
