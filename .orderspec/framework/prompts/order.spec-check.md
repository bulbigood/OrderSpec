---
orderspec:
  artifact: command_prompt
  command: order.spec-check
  phase: check
description: Per-stage gate validating spec.md for coverage, internal integrity, and contract completeness. Pure inspector; routes contractual changes to /order.spec and writes a report on every run.
handoffs:
  - label: "Proceed to Plan"
    agent: "order.plan"
    prompt: "/order.plan"
  - label: "Fix Spec"
    agent: "order.spec"
    prompt: "/order.spec"
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

1. Run:
   ```bash
   python3 .orderspec/framework/scripts/active_feature.py get --json
   python3 .orderspec/framework/scripts/active_feature.py validate --json
   ```
2. If active state validation fails, write BLOCK report with `S0-003 (HIGH): active feature state invalid`, then stop.
3. If `$ARGUMENTS` contains an explicit feature reference, resolve it read-only using `active_feature.py list --json`.
   - If ambiguous: `S0-004 (HIGH): ambiguous feature reference`.
   - If not found: `S0-005 (HIGH): feature not found`.
4. Do not use `active_feature.py select` in this gate.
5. If no target is resolved, write BLOCK report with `S0-000 (CRITICAL): no active feature`.

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
For any finding, assign disposition `Route` and create a routing block.

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

## Report Generation

You MUST render the final report strictly using the `report-template.md` loaded via Command Context. 
Do not invent report sections, table structures, or alter the YAML frontmatter schema. 
Fill the template variables exactly as specified in the template file using the data from `traceability.py` JSON output and your semantic findings.

Write the Markdown report to `$FEATURE_DIR/spec-report.md`.

Map the JSON output from `traceability.py validate` to the template variables:
- **Inventory & Metrics**: Use the `inventory` object directly.
- **Coverage Taxonomy**: Use the `categories` object. `missing` MVP/core category → Route (HIGH). `empty`/`partial` → Route (MEDIUM).
- **Contradiction Grid**: Use the `contradiction_grid` array.
- **Journey Coverage Matrix**: Use the `matrices.uj_coverage` array.
- **IF Coverage Matrix**: Use the `matrices.if_coverage` array.
- **Findings**: Combine imported mechanical findings (from the script's `findings` array) with your semantic findings (S1-xxx). 

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
- Next action:
  - PASS -> proceed to `/order.plan`
  - ROUTING_REQUIRED/BLOCK -> run routed `/order.spec` request(s), then rerun `/order.spec-check`
