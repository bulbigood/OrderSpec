---
orderspec:
  artifact: command_prompt
  command: order.spec-check
  phase: check
description: Per-stage gate validating spec.md for coverage, internal integrity, and contract completeness. Pure inspector; routes contractual changes to /order.spec and writes a report on every run.
---

## Role

`/order.spec-check` is the independent inspection gate for one artifact: `spec.md`.

It runs after `/order.spec` and answers:

> Is `spec.md` a complete, internally consistent, repo-independent, testable feature contract?

This command:

- inspects `spec.md`;
- imports deterministic findings from `traceability.py`;
- performs semantic consistency checks;
- may apply only strictly mechanical, meaning-preserving fixes;
- always writes a gate report.

This command does **not** author contract content.

Contract content is owned by `/order.spec`.

## User Input

```text
$ARGUMENTS
```

Consider the user input before proceeding if non-empty. It may identify a feature to check or provide inspection focus.

## Command Context Bootstrap

Before command-specific logic:

1. Resolve command context:

   ```bash
   python3 .orderspec/scripts/command_context.py resolve order.spec-check --json
   ```

2. If `ok` is `false` or `missing_required` is non-empty, STOP and report missing required context.
3. Read every file returned in `to_read`, in returned order.
4. Interpret each file by `usage`:
   - `apply`: apply as framework rules.
   - `constrain`: enforce as project constraints.
   - `parse`: parse as structured schema/state.
   - `inspect`: inspect as input/output artifact.
   - `reference`: use only as reference.
5. Do not manually load additional framework rules, schemas, project contracts, or runtime state.

Runtime state is accessed only through owner scripts such as `active_feature.py`; never read or parse runtime state files directly.

Project contracts constrain inspection, but do not override framework rules.

## Boundaries

### Owned by this command

- inspecting `spec.md`;
- mechanical validation orchestration;
- semantic consistency checking;
- report writing;
- strictly mechanical, meaning-preserving auto-fixes.

### Owned by `/order.spec`

Route to `/order.spec` for anything that changes or fills:

- requirement meaning;
- scope;
- thresholds;
- interface behaviour;
- invariant guarantees;
- acceptance criteria obligations;
- edge-case behaviour;
- decisions;
- assumptions;
- missing contract topics;
- decomposition.

### Out of scope

Do not:

- inspect application source code;
- inspect `plan.md` or `tasks.md` for semantic decisions;
- run repository tests;
- decide implementation mechanism adequacy;
- create new spec IDs;
- add missing requirements;
- answer open questions;
- decompose the spec.

## Non-Negotiable Invariants

### Mechanical script is ground truth

Every finding from:

```bash
python3 .orderspec/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" validate --stage spec --json
```

is a deterministic finding.

You MUST:

- import every spec-stage finding at its stated severity;
- never downgrade imported findings;
- never suppress imported findings;
- never remove imported findings from the report as false positives.

If a script pattern appears wrong:

- add `S0-002` with severity `MEDIUM`;
- still import the original script finding unchanged.

### Required traceability commands are mandatory

Manual reconstruction of traceability output is forbidden.

If required traceability commands fail:

- do not manually count IDs from `spec.md`;
- do not infer `spec-ids.tsv`;
- do not continue semantic passes unless the recovery path is explicitly defined here;
- write a non-PASS report.

### Script exit code is a verdict floor

For `traceability.py validate --stage spec --json`:

| Exit code | Meaning | Verdict floor |
|---:|---|---|
| `0` | no mechanical HIGH/CRITICAL findings | may still be ROUTING REQUIRED due to semantic findings |
| `1` | at least one mechanical HIGH/CRITICAL finding | cannot be PASS |
| `2` | required artifact or command failure | BLOCK |

Import all JSON findings, including LOW and MEDIUM.

### Explicit severity rules cannot be downgraded

If a rule says `Route (HIGH)`, final severity is at least `HIGH`.

You may raise severity. Never lower it.

## Target Feature Resolution

Determine the target feature before inspection.

### Read active feature state

Run:

```bash
python3 .orderspec/scripts/active_feature.py get --json
python3 .orderspec/scripts/active_feature.py validate --json
```

If active state validation fails, write a BLOCK report to:

```text
.orderspec/state/spec-check-report.md
```

with `S0-003 (HIGH): active feature state invalid`, then stop.

### Explicit feature reference

If `$ARGUMENTS` contains an explicit feature reference, resolve it read-only:

```bash
python3 .orderspec/scripts/active_feature.py get --json
python3 .orderspec/scripts/active_feature.py list --json
```

Match the feature reference against the active feature state and the feature list.

If the reference is ambiguous (matches multiple features), write BLOCK report with `S0-004 (HIGH): ambiguous feature reference`.

If the reference matches no feature, write BLOCK report with `S0-005 (HIGH): feature not found`.

Do not use `active_feature.py select` in this gate. This gate must not mutate runtime state merely to inspect.

### Default target

If no explicit feature reference is supplied, use active feature state.

If there is no active feature, write BLOCK report to:

```text
.orderspec/state/spec-check-report.md
```

with `S0-000 (CRITICAL): no active feature`, and instruct the user to run `/order.spec` or provide a feature reference.

### Derived variables

After target resolution:

```text
FEATURE_ID=<feature_id>
FEATURE_DIR=<feature_directory>
SPEC=<feature_directory>/spec.md
REPORT=<feature_directory>/spec-report.md
```

If `SPEC` does not exist, write BLOCK report with `S0-001 (CRITICAL): spec.md missing`, then stop.

## Report Persistence

This command always writes a report.

Feature-local report path:

```text
$FEATURE_DIR/spec-report.md
```

Fallback report path when no feature can be resolved:

```text
.orderspec/state/spec-check-report.md
```

A missing report means this gate did not run or failed before report rendering.

## Dispositions

Each finding has one disposition:

| Disposition | Meaning |
|---|---|
| `Auto-fix` | mechanical, meaning-preserving correction applied |
| `Route` | contractual issue owned by `/order.spec` |
| `Deferred to Plan` | belongs to `/order.plan` or later checks |
| `Informational` | report-only observation |

## Auto-Fix Boundary

Auto-fix is allowed only when all conditions hold:

1. defect is mechanical;
2. exactly one valid correction exists;
3. correction is meaning-preserving;
4. correction does not change scope, threshold, behaviour, acceptance obligations, or ID inventory;
5. no new contract content is created;
6. no new ID is created.

Allowed examples:

- whitespace normalization in an already-correct table;
- AC formatting into Given/When/Then when the same conditions and outcome are already present;
- uniquely obvious broken local reference where target text already names the intended ID.

Forbidden examples:

- adding missing `REQ`;
- adding missing `AC`;
- deciding failure semantics;
- defining authorization;
- choosing status codes;
- writing missing EDGE behaviour;
- creating or removing IDs;
- changing MUST/SHOULD;
- changing interface response shape.

When in doubt, Route.

## Routing Block Format

Render one block per routed finding.

```markdown
### Routing Required: {short title}

**Finding**: {what is wrong or missing}
**Location**: {ID / section / missing category}
**Why owner, not gate**: {why this changes contract meaning/scope/test obligation}
**Impact if unresolved**: {downstream impact}
**Suggested direction**: {advisory only}
**Run**: `/order.spec "{ready-to-run refinement request}"`
```

## Execution Steps

### Step 1 — Initialize

1. Resolve command context.
2. Resolve target feature.
3. Derive `FEATURE_DIR`, `SPEC`, and `REPORT`.
4. Create report directory:

   ```bash
   mkdir -p "$(dirname "$REPORT")"
   ```

5. If `spec.md` is missing, write BLOCK report and stop.

### Step 2 — Traceability Initialization

Run:

```bash
python3 .orderspec/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" init
python3 .orderspec/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" extract-spec-ids
```

If either command fails:

- record `S0-010 (HIGH): traceability initialization failed`;
- write BLOCK report;
- stop semantic passes.

### Step 3 — Mechanical Validation

Run:

```bash
python3 .orderspec/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" validate --stage spec --json
```

Parse JSON output.

If no valid JSON is returned:

- record `S0-011 (HIGH): traceability validation did not return valid JSON`;
- write BLOCK report;
- stop semantic passes.

Import every finding emitted for stage `spec`.

Keep script severities unchanged.

### Step 4 — Spec ID Inventory

Use script-generated ID projection only.

Primary path:

```bash
python3 .orderspec/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" get "" spec-ids
```

If this command is unsupported by the local script but `extract-spec-ids` succeeded, read:

```text
$FEATURE_DIR/.state/spec-ids.tsv
```

This is allowed only as reading the script-generated projection artifact. Do not count IDs directly from `spec.md`.

If neither path succeeds:

- record `S0-012 (HIGH): unable to read script-generated spec ID inventory`;
- write BLOCK report;
- stop semantic passes.

Parse inventory and count these prefixes:

```text
REQ, NFR, SC, INV, EDGE, UJ, AC, Q, ASM, DEC, IF
```

Do not count project contract IDs as feature spec IDs.

### Step 5 — Load Spec

Read `spec.md`.

Build a lightweight inspection model:

- frontmatter;
- section headings;
- ID inventory from script projection;
- REQ texts;
- NFR texts;
- SC texts;
- INV texts;
- EDGE texts;
- UJ blocks;
- AC lines and inline `[Covers: ...]`;
- IF records and Field/Value tables;
- §6 project constraint references;
- §8 entity/structure/value-set fields;
- §9 payload schemas/examples;
- §10 contradiction grid;
- DEC entries;
- ASM entries;
- Q entries.

Do not inspect source code, `plan.md`, or `tasks.md`.

## Detection Passes

Run all passes unless a required script/setup failure stopped semantic inspection.

Limit report to 30 findings using this policy:

1. always include all CRITICAL/HIGH findings;
2. always include all imported mechanical findings;
3. include MEDIUM by downstream impact;
4. suppress LOW first;
5. group duplicates when possible.

Finding ID namespaces:

| Namespace | Source |
|---|---|
| `S0-NNN` | setup/script/process |
| `M...` | imported mechanical finding |
| `C1-NNN` | mechanical-semantic finding |
| `C2-NNN` | semantic consistency finding |
| `C3-NNN` | coverage/quality finding |

## Pass 1 — Mechanical-Semantic Checks

These checks are close to mechanical. Enumerate every instance when practical.

### C1.1 Status code coherence

Compare status codes in:

- IF `Success`;
- IF `Failure`;
- EDGE prose;
- AC prose;
- nearby normative prose.

If EDGE/AC asserts a status code absent from the corresponding IF:

- Route (MEDIUM);
- Route (HIGH) if it contradicts IF behaviour.

### C1.2 Authorization coverage

For every mutating IF or cross-tenant read IF:

- Actor must be meaningful;
- Actor must not be placeholder text;
- Authorization subsection, if present, must align with IF Actor;
- scope/ownership statements must not contradict §2 Out of Scope.

Partial or ambiguous authorization → Route (MEDIUM).

Conflict with constitution MUST principle → Route (CRITICAL).

### C1.3 AC field alignment — logical model

If an AC asserts a field exists or has a value, verify the field appears in one of:

- §8 entity table;
- §8 structure table;
- §9 shared response structure;
- §9 IF payload schema;
- explicitly defined error body.

Missing field → Route (MEDIUM).

### C1.4 AC field alignment — response schemas

If an AC says the response includes, returns, has, or contains a field, verify the corresponding IF response schema includes it.

If payload block is explicitly an example, missing fields are informational.

If schema vs example is unclear and affects testability → Route (MEDIUM).

### C1.5 Contradiction grid staleness

For each row in §10 Contradiction Grid:

- referenced IDs must exist;
- row summary must match current ID text;
- verdict must match rationale.

Stale or inconsistent row → Route (MEDIUM).

### C1.6 Grid completeness — INV × weakening NFR/ASM

For each absolute INV, identify weakening NFR/ASM candidates.

Absolute indicators include:

```text
exactly, always, never, must, only if, if and only if, every, no update, no deletion
```

Weakening indicators include:

```text
SHOULD, MAY, best effort, reasonable, under normal load, unless practical
```

Note: The `[default]` tag on an ASM does not by itself indicate weakening. Only check if the ASM text actually qualifies or limits an INV guarantee.

If omitted pair is a real conflict → Route (HIGH).

If omitted pair is compatible → report in Contradiction Grid section, not necessarily as a finding.

### C1.7 Grid completeness — REQ × narrowing ASM

For each ASM tagged `[narrowing REQ-NNN]`:

- target REQ must exist;
- ASM must not defeat any required case;
- report the pair in the report grid.

If ASM contradicts or defeats REQ → Route (HIGH).

If spec falsely states no narrowing pairs while narrowing ASMs exist → Route (MEDIUM).

## Pass 2 — Semantic Consistency

This pass is mandatory when setup succeeds.

### C2.1 REQ contradictions

Verify no REQ contradicts another REQ, INV, or project contract constraint.

MVP/core contradiction → Route (CRITICAL or HIGH).

### C2.2 AC vs REQ/IF

Verify ACs do not contradict covered REQs or IFs.

Examples:

- AC expects one status code while IF defines another;
- AC allows behaviour REQ forbids;
- AC tests different actor/resource state than REQ requires.

Contradiction → Route (HIGH).

### C2.3 Narrowing ASMs

For every `[narrowing REQ-NNN]` ASM, verify all REQ cases are still satisfied.

If narrowing silently excludes required action/state → Route (HIGH).

### C2.4 NFR vs scope

NFR must not mandate behaviour excluded in §2 Out of Scope.

Contradiction → Route (HIGH).

### C2.5 AC traces

Every AC must include at least one `REQ-NNN` in inline `[Covers: ...]`.

IF-only coverage is insufficient.

No REQ coverage → Route (MEDIUM).

Claimed REQ not directly tested → Route (MEDIUM).

Only coverage for P1/core REQ is invalid → Route (HIGH).

### C2.6 Multi-operation AC validity

For ACs covering multiple IFs or mutation types:

- Given must apply to all covered operations;
- When must apply to all covered operations;
- Then must be testable for all covered operations.

Invalid for some covered operations → Route (MEDIUM).

If only coverage for P1/core requirement → Route (HIGH).

### C2.7 Exception scoping for state-transition specs

If the spec defines a state transition (e.g., soft-delete to restore, draft to published), broad prohibition statements about a state MUST explicitly list exceptions or be scoped to non-exception operations.

Example: if "mutations on soft-deleted entities are rejected" is a REQ, and restore is allowed, the REQ must say "non-restore mutations on soft-deleted entities are rejected" or equivalent.

If not scoped:

- Route (HIGH) for REQ/INV;
- Route (MEDIUM) for summary/SC.

### C2.8 Quantitative NFR hallucination

For each quantitative NFR threshold:

- exact value must appear in user input quoted in the spec; or
- exact value must appear in constitution/project contracts.

Threshold without source → Route (HIGH).

Quantitative threshold examples:

- latency units;
- percentages;
- request rates;
- storage/memory limits;
- availability values;
- absolute numeric limits.

### C2.9 Qualitative NFR oracle

Every NFR needs an oracle:

- sourced quantitative threshold;
- named project standard;
- qualitative SHOULD advisory wording.

MUST-level qualitative NFR without oracle → Route (MEDIUM or HIGH depending on criticality).

## Pass 3 — Coverage and Quality

If Pass 1 and Pass 2 already contain 3 or more HIGH findings:

- suppress LOW findings;
- cap MEDIUM findings to top 5 by downstream impact;
- still run HIGH-producing checks.

### C3.1 Incompleteness markers

Every `[NEEDS CLARIFICATION]` marker → Route (HIGH).

Every unresolved `Q-NNN` affecting scope, security, acceptance, IF, INV, REQ, NFR, or testability → Route (HIGH).

Non-blocking deferred Q may be Route (MEDIUM).

### C3.2 Coverage taxonomy

Verify presence and adequacy of:

- Functional Requirements;
- Non-Functional Requirements;
- Project Constraints Applied;
- Architecture & Behaviour;
- Information Model;
- Interface Contracts;
- Invariants;
- Edge Cases;
- Acceptance Criteria & User Journeys;
- Open Questions;
- Decisions;
- Assumptions;
- Glossary;
- Success Criteria;
- Changelog.

Missing MVP/core category → Route (HIGH).

Partial category → Route (MEDIUM).

### C3.3 REQ testability

Every REQ must be observable and verifiable.

Untestable MVP/core REQ → Route (HIGH).

Untestable non-core REQ → Route (MEDIUM).

### C3.4 AC form

Every AC must be checkable Given/When/Then with observable result.

Invalid AC form → Route (MEDIUM).

If sole coverage for P1/core REQ → Route (HIGH).

### C3.5 Journey completeness

Verify:

- every UJ has priority;
- every UJ has Covers;
- every UJ has Independent Test;
- every UJ has Done when;
- every P1 UJ has enough ACs to test Done condition;
- every AC traces to specific REQ.

Gap → Route (MEDIUM or HIGH by P1/core impact).

### C3.6 Failure-path coverage — EDGE

For each EDGE describing failure, verify at least one AC tests that specific failure.

Failure indicators:

```text
4xx, 5xx, fail, failure, error, rollback, reject, denied, conflict, not found, non-existent, unauthorized, unauthenticated, forbidden, invalid, already, cannot
```

Missing AC for feature-specific failure path → Route (HIGH).

Do not downgrade.

### C3.7 Failure-path coverage — IF failures

For each IF failure outcome representing feature-specific behaviour, verify AC coverage.

Generic authorization failures need AC only if authorization is in feature scope.

Feature-specific examples:

- hidden soft-deleted resource;
- state conflict;
- feature-specific validation;
- rollback/audit failure;
- domain-specific not-found.

Missing P1/core failure AC → Route (HIGH).

Missing non-core failure AC → Route (MEDIUM).

Deduplicate with EDGE findings when same operation, state, and status code are involved. Track reported (operation, state, status_code) tuples in a local set. Skip a C3.7 finding if the same tuple was already reported under C3.6 EDGE coverage.

### C3.8 Repo-independence and purity

Outside §6 Project Constraints Applied and §9 interface addresses, `spec.md` must not contain:

- source file paths;
- class names;
- framework/library/tool names;
- database/query syntax;
- plugin names;
- implementation tasks.

Allowed:

- HTTP paths in §9;
- logical role names;
- project contract IDs: `STACK-NNN`, `ARCH-NNN`, `CONV-NNN`;
- neutral references to project constraints.

Physical mechanism leak outside allowed areas → Route (MEDIUM).

If contract behaviour depends on unstated physical mechanism → Route (MEDIUM).

### C3.9 Project constraint references

In §6, every referenced project contract ID must exist in loaded project contracts:

```text
STACK-NNN
ARCH-NNN
CONV-NNN
```

Missing ID → Route (MEDIUM) to `/order.spec` or targeted `/order.bootstrap` routing.

Do not invent or amend project contract IDs.

### C3.10 Scope sizing

Assess cohesion.

Oversized indicators:

- unrelated entities;
- unrelated workflows;
- independent goals that can ship separately;
- more than 2 weakly related P1 journeys;
- separate actors/domains with minimal shared contract.

Oversized but coherent → Route (MEDIUM) recommending `/order.spec --split`.

Density alone is not a defect.

## Severity Assignment

Apply explicit rule severities first.

### CRITICAL

Use CRITICAL for:

- spec missing;
- no active feature and no explicit target;
- direct contradiction on MVP/core behaviour;
- constitution MUST conflict;
- unresolved marker blocking MVP correctness;
- absolute INV conflict on MVP/core behaviour.

### HIGH

Use HIGH for:

- imported mechanical HIGH;
- traceability setup failure;
- AC contradicts REQ/IF;
- untestable MVP/core REQ;
- missing high-impact category affecting MVP/core;
- feature-specific P1/core failure path without AC;
- quantitative NFR threshold without source;
- required inspection cannot be trusted.

### MEDIUM

Use MEDIUM for:

- ambiguous authorization;
- leaked physical detail;
- response-schema ambiguity;
- stale contradiction grid row;
- invalid non-core AC trace;
- oversized scope;
- missing project constraint ID;
- suspected script-pattern issue.

### LOW

Do not actively search for LOW findings. Import LOW findings from scripts if present.

## Auto-Fix Procedure

If auto-fix is applied:

1. Record exact change.
2. Confirm meaning, scope, IDs, thresholds, and test obligations did not change.
3. Rerun:

   ```bash
   python3 .orderspec/scripts/traceability.py --feature-dir "$FEATURE_DIR" extract-spec-ids
   python3 .orderspec/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" validate --stage spec --json
   ```

4. Refresh script-generated ID inventory.
5. Import new findings.
6. Use post-fix results in final report.

If post-fix validation fails with HIGH/CRITICAL, verdict follows the imported findings.

## Verdict

Final verdict is determined from imported mechanical findings, semantic findings, auto-fix results, and setup findings.

| Verdict | Conditions |
|---|---|
| BLOCK | any routed CRITICAL/HIGH; traceability failure preventing reliable inspection; `spec.md` missing |
| ROUTING_REQUIRED | no routed CRITICAL/HIGH, but at least one routed MEDIUM/LOW |
| PASS | traceability succeeded and no routed findings remain |

Do not downgrade severity during verdict determination.

## Report Format

Write Markdown report to `$REPORT` using `.orderspec/framework/templates/report-template.md` as the base template. Fill all template variables with actual values from the inspection.

Report order:

1. HTML comment header.
2. Title.
3. Verdict.
4. Auto-Fixed.
5. Routing Required.
6. Deferred to Plan.
7. Findings.
8. Coverage Taxonomy.
9. Contradiction Grid.
10. Journey Coverage Matrix.
11. IF Coverage Matrix.
12. Metrics.
13. Report path.

### Header

Use the template file `.orderspec/framework/templates/report-template.md` which contains the YAML frontmatter. Fill the variables with actual values.

The `generator.model` field MUST be set to the identifier of the AI model currently running this gate (e.g., `kilo/moe-medium`, `claude-3.5-sonnet`).

### Auto-Fixed

If none:

```markdown
None.
```

Otherwise:

```markdown
| ID | What was changed | Why meaning-preserving |
|----|------------------|------------------------|
```

### Routing Required

If none:

```markdown
None.
```

Otherwise render routing blocks.

### Deferred to Plan

If none:

```markdown
None.
```

Otherwise:

```markdown
| ID | Location | Why deferred |
|----|----------|--------------|
```

### Findings

Include all imported and semantic findings.

```markdown
| ID | Source | Severity | Disposition | Location | Summary |
|----|--------|----------|-------------|----------|---------|
```

### Coverage Taxonomy

Render every row:

```markdown
| Category | § | Status | Disposition |
|----------|---|--------|-------------|
```

Required categories:

- Functional Requirements;
- Non-Functional Requirements;
- Project Constraints Applied;
- Architecture & Behaviour;
- Information Model;
- Interface Contracts;
- Invariants;
- Edge Cases;
- Acceptance Criteria & User Journeys;
- Open Questions;
- Decisions;
- Assumptions;
- Glossary;
- Success Criteria;
- Changelog.

### Contradiction Grid

Render:

```markdown
| Pair | Verdict | Reason |
|------|---------|--------|
```

Include:

- absolute INV × weakening NFR/ASM pairs;
- REQ × narrowing ASM pairs;
- relevant existing spec grid pairs.

If no pairs exist:

```markdown
No contradiction-grid pairs detected.
```

### Journey Coverage Matrix

Render every UJ:

```markdown
| UJ | Priority | Covers REQs | ACs | ACs trace to REQs | Status |
|----|----------|-------------|-----|-------------------|--------|
```

### IF Coverage Matrix

Render every IF:

```markdown
| IF | Kind | Actor | Success | Failure | Covered by ACs | Status |
|----|------|-------|---------|---------|----------------|--------|
```

Mark IF as Partial if feature-specific failure status lacks AC coverage.

### Metrics

Include:

```markdown
- Inventory: SC=N · REQ=N · NFR=N · IF=N · INV=N · EDGE=N · UJ=N · AC=N · ASM=N · DEC=N · Q=N · Total=N
- Findings by severity: CRITICAL=N · HIGH=N · MEDIUM=N · LOW=N
- Auto-fixed: N · Routing required: N · Deferred to Plan: N
- Script exit code: N · verdict floor applied: PASS|ROUTING_REQUIRED|BLOCK
- Report file: path/to/spec-report.md
```

## Report Write Failure

If the report file cannot be written (permissions, disk full, path issues):

1. Print the full report content to chat as a fallback.
2. Include `S0-013 (HIGH): report file write failed` at the top.
3. Use the chat output as the report of record.
4. Do not silently swallow the write error.

## Report Self-Check

Before finalizing, verify:

1. Metrics counts match script-generated ID inventory.
2. Total inventory equals sum of prefix counts.
3. Findings by severity match Findings table.
4. Auto-fixed count matches Auto-Fixed section.
5. Routing count matches Routing Required blocks.
6. Every routed finding has a routing block.
7. Every auto-fix finding appears in Auto-Fixed.
8. Verdict matches highest routed severity.
9. No HIGH/CRITICAL Route finding has non-BLOCK verdict.
10. No manual inventory from `spec.md` was used.
11. Report path is stated.
12. If auto-fix occurred, post-fix validation was rerun.
13. Imported mechanical findings are present unchanged.

If self-check fails, fix the report before writing final output.

## Completion Response

After writing the report, respond in chat with:

- verdict (BLOCK, ROUTING_REQUIRED, or PASS);
- report path;
- number of findings by severity;
- number of routing blocks;
- number of auto-fixes;
- next action:
  - PASS -> proceed to `/order.plan`;
  - ROUTING_REQUIRED/BLOCK -> run routed `/order.spec` request(s), then rerun `/order.spec-check`.

## Operating Principles

- Inspect; do not author.
- Mechanical scripts are ground truth.
- Always write a report.
- Manual ID inventory from `spec.md` is forbidden.
- Clean mechanical validation never lets you skip semantic passes.
- Explicit severity rules cannot be downgraded.
- Failure-path coverage gaps marked HIGH remain HIGH.
- Auto-fix only strictly mechanical, meaning-preserving defects.
- When in doubt, Route.
- Do not inspect source code, `plan.md`, or `tasks.md`.
- Detect oversize; never decompose.
- Verify narrowing ASMs against their REQs.
- Verify ACs trace to REQs, not only IFs.
- Verify mutating interfaces have authorization.
- Verify response-specific AC field assertions against response schemas.
- HTTP endpoint paths in §9 are allowed and are not filesystem paths.
- Project constraint IDs are `STACK-NNN`, `ARCH-NNN`, and `CONV-NNN`.
