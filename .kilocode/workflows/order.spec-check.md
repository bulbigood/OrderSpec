---
description: Per-stage gate validating spec.md for coverage, internal integrity, and contract completeness. Pure inspector — detects defects, missing high-impact topics, and oversized scope, but NEVER authors contract content. Auto-fixes only strictly mechanical/meaning-preserving defects; routes everything contractual to /order.spec. ALWAYS writes a report file on every run.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Role In The Pipeline

This is a **per-stage gate** for one document: `spec.md`. It runs after `/order.spec` and answers:

> **Is spec.md a complete, internally consistent, testable contract — independent of how it will be built?**

It is the **root of the cascade**: no upstream artifact. A defect here originates in the spec text or user intent.

**Division of responsibility:**

- **Authoring contract content is owned by `/order.spec`**, not by this gate.
- **This gate is a pure inspector.** It verifies the contract and may perform only **mechanical/meaning-preserving** auto-fixes. Anything that changes requirement meaning, scope, thresholds, or fills a missing topic is surfaced as a **Routing block** telling the user exactly which `/order.spec` call will resolve it.

**Two content channels only:**

1. **Auto-Fixed** — mechanical defects silently corrected in place.
2. **Routing Required** — contractual findings with a ready-to-run `/order.spec` invocation.

**Persistence:** the gate **always** writes its report to a file (every run, every verdict). A missing report file means the gate did not run.

Boundaries:

- spec self-consistency, glossary, AC form, testability, purity, missing topics, scope sizing → **this gate** (detect only).
- authoring/filling spec content, elicitation, ID-routing, decomposition → `/order.spec`.
- plan↔spec completeness, mechanism adequacy → `plan-check`.
- tasks ordering/coverage → `tasks-check`.
- repo state, drift, whole-system sweep → `/order.analyze`.
- mechanical ID inventory, dangling references, numbering → `traceability.py`.

## The Two Non-Negotiable Invariants

1. **The mechanical script is ground truth; you may never overrule it.** Every finding from `traceability.py validate` is a deterministic fact. You MUST import each spec-internal finding at its stated severity. You MUST NOT downgrade, suppress, or call it a "false positive" on semantic grounds. If you believe the script's pattern is wrong, record it as **S0-002 (MEDIUM)** and STILL import the finding.

2. **The script exit code is a hard floor on the verdict.** Read it FIRST:
   - exit **1** → ≥1 mechanical CRITICAL/HIGH exists → verdict **cannot be ✅ PASS**. Floor is 🔀 ROUTING REQUIRED (⛔ BLOCK if any is MVP-affecting).
   - exit **0** → clean, full spec-stage scope. Normal.
   - exit **2** → `spec.md` missing → abort.

## When to Run

Recommended after every `/order.spec` run (especially with weaker models or large features). Can be wired as `hooks.after_spec` for automated workflows.

## Pre-Execution Checks

Run the **`before_spec_check`** phase per `.orderspec/memory/hooks-protocol.md`.

## Goal

Act as an **independent inspector with fresh context** over `spec.md`. You did not write it. Determine whether spec.md is a **sound, complete contract**:

- **Coverage**: no high-impact topic missing; explicit `[NEEDS CLARIFICATION]` markers and open `Q-NNN` flagged.
- **Testability**: every REQ verifiable; every AC in checkable Given/When/Then form.
- **Consistency**: no REQ contradicts another REQ, INV, or CON; no absolute INV contradicted by weakening NFR or ASM.
- **Journey completeness**: each UJ step backed by requirements; each AC traces to a specific REQ.
- **Authorization**: mutating endpoints have defined actor/auth rules.
- **Schema alignment**: ACs checking specific fields have those fields in API response schemas.
- **Purity**: spec states WHAT/WHY, not HOW — no paths/libraries outside §6.
- **Scope sizing**: contract is cohesive enough for one spec; oversized → route to decomposition.

## Out of Scope (do NOT do here)

- Authoring or filling spec content (adding REQ/NFR/CON/INV/EDGE/AC, defining terms, resolving markers) → `/order.spec`.
- Performing decomposition (`--split`) → `/order.spec`.
- Overruling the mechanical script.
- How the spec will be implemented → `plan-check` / `/order.plan`.
- Whether tasks cover the spec → `tasks-check`.
- Repo state, drift, whole-system sweep → `/order.analyze`.

## Operating Constraints

- **INSPECTOR + MECHANIC**: you MAY modify `spec.md` ONLY for mechanical/meaning-preserving auto-fixes. You MUST NOT author, fill, or alter contract meaning.
- **Auto-fix boundary** (ALL must hold): (a) defect is mechanical or strictly meaning-preserving, (b) exactly one valid correction exists, (c) does NOT change meaning/threshold/scope, (d) obvious/reversible. Examples: glossary spelling normalization, broken internal ID cross-reference, AC reformatted into G/W/T without altering conditions.
- **Route for everything else** — anything touching requirement meaning, threshold, scope, term definition, EDGE behavior, or a missing topic. Emit a Routing block with a ready-to-run `/order.spec` invocation.
- **When in doubt, Route — never Auto-fix.**
- **Report file is separate from the spec.** Writing `spec-report.md` is a gate artifact, not a spec edit.
- **No Ask-and-apply**: the gate never asks the user a question whose answer it writes into the spec.
- **Constitution authority**: a spec goal directly conflicting with a constitution MUST principle is CRITICAL → Route.

## Routing Block Format

Batch all routing blocks together at the end:

```text
### Routing Required: {short title}

**Finding**: {what is wrong or missing}
**Location**: {spec ID / §section / "Missing: {category}"}
**Why owner, not gate**: {changes meaning/threshold/scope OR fills a missing topic}
**Impact if unresolved**: {what breaks downstream}
**Suggested direction**: {1–2 candidate resolutions; advisory only}
**Run**: `/order.spec "{ready-to-run refinement request}"`
```

## Execution Steps

### 1. Initialize

Run from repo root:

```bash
python3 .orderspec/scripts/setup.py spec --json
```

Parse JSON output for `FEATURE_DIR`, `FEATURE_SPEC`, `SPEC_EXISTS`. Derive:
- `SPEC` = `FEATURE_SPEC`
- `REPORT` = `{FEATURE_DIR}/checklists/spec-report.md`

If `SPEC_EXISTS` is false → abort with instructions to run `/order.spec` first.

If EXISTS, load `.orderspec/memory/constitution.md` for governance constraints.

### 2. Mechanical Validation (script — GROUND TRUTH)

Run:

```bash
python3 .orderspec/scripts/traceability.py validate --json --stage spec "$(basename $FEATURE_DIR)"
```

> Read `summary.exit_code` from JSON output. This is the verdict floor.

**Exit code interpretation:**
- **0** — clean, full spec-stage scope. Normal.
- **1** — ≥1 CRITICAL/HIGH mechanical finding. **Verdict floor is now non-PASS.** Import spec-internal findings (M1, M5 spec-side, M6, M13) at their stated severities. Most are Route (M1 Covers-gaps are Route — adding an ID to a `Covers` field is contractual).
- **2** — `spec.md` missing → abort.

**Import ONLY spec-internal findings** (ID inventory, internal dangling refs, numbering/format within spec, M1 Covers-gaps, M6 unresolved markers, M13 placeholders). Ignore plan/tasks/repo/timestamp findings.

**You may NOT overrule any imported finding (Invariant 1).** If you believe the script's pattern is faulty, record S0-002 (MEDIUM) and STILL import the finding.

### 3. Read Spec IDs (for inventory and traceability)

Run:

```bash
python3 .orderspec/scripts/traceability.py get "$(basename $FEATURE_DIR)" spec-ids
```

Parse the TSV output. Count IDs by prefix (REQ, NFR, CON, SC, INV, EDGE, UJ, AC, Q, ASM). These counts go into the Metrics section of the report. Also use this to verify:
- Every REQ appears in at least one UJ's `Covers` field (M1 from script already checks this, but you use the ID list for semantic checks).
- Every AC traces to a specific REQ.

### 4. Detection Passes (LLM — DETECT ONLY)

**Execution order is mandatory. Pass 2 is NEVER skipped.**

Load `spec.md`. Build a minimal internal model. Limit to 30 findings total (including imported M-findings). Use stable IDs prefixed by pass (C1-001, C2-001...). For each finding, classify disposition as **Auto-fix**, **Route**, or **defer-to-plan**.

#### Pass 1: Mechanical-Semantic (MANDATORY FIRST)

These checks are almost mechanical. Enumerate EVERY instance. Do not sample.

1. **Status code coherence**: (Script M15a/M15b handles most). Verify any remaining mismatches between §9, §11, §12. Missing → Route (MEDIUM).
2. **Authorization coverage**: (Script M16 handles most). Verify all endpoints have auth rules. Partial → Route (MEDIUM).
3. **AC field alignment**: (Script M17 handles most). Verify AC-checked fields exist in §9. Missing → Route (LOW).
4. **Grid staleness**: For each row in §10 Contradiction Grid, verify the referenced ID's text matches the row's description. Stale → Route (MEDIUM).
5. **Grid completeness**: For each INV with absolute quantifier, verify rows exist for ALL weakening NFRs/ASMs. Missing weakening pair → Route (HIGH). Missing compatible pair → informational only, NOT a Route.

#### Pass 2: Semantic Consistency (MANDATORY — NEVER SKIP)

1. **Contradictions**: No REQ contradicts another REQ, INV, or CON. Contradiction → Route (CRITICAL/HIGH).
2. **AC vs REQ**: AC do not contradict parent REQ (especially status code mismatches like 410 vs 404). Contradiction → Route (HIGH).
3. **Narrowing ASMs**: Verify ASM tagged `[narrowing REQ-NNN]` satisfies the REQ for all cases. Defeat → Route (HIGH).
4. **NFR vs Scope**: Verify NFR does not mandate behavior excluded in §2. Contradiction → Route (HIGH).
5. **AC Traces**: Each AC directly tests a specific REQ's behavior. Unbacked → Route (MEDIUM).

#### Pass 3: Coverage & Quality (abbreviated if Pass 1+2 had ≥3 HIGH)

If Pass 1 and Pass 2 combined have ≥3 HIGH findings:
- **Suppress all LOW findings**.
- **Cap MEDIUM findings to top 5 by downstream impact**.
- Still run these checks, but only report HIGH/CRITICAL:
  1. Incompleteness Markers: Every `[NEEDS CLARIFICATION]` or unresolved `Q-NNN` → Route (HIGH).
  2. Coverage Taxonomy: Missing high-impact category → Route (HIGH).
  3. Testability: Untestable MVP requirement → Route (HIGH).

Otherwise (fewer than 3 HIGH in Pass 1+2), run all checks:
  1. Incompleteness Markers → Route (HIGH).
  2. Coverage Taxonomy sweep → Route (HIGH/MEDIUM).
  3. Testability of each REQ → Route (HIGH/MEDIUM).
  4. Journey Completeness → Route (MEDIUM).
  5. Purity → Route (MEDIUM).
  6. Glossary → Route (LOW).
  7. Scope Sizing → Route (MEDIUM).

### 5. Severity Assignment

- **CRITICAL**: a P1-journey step has no backing requirement; two requirements directly contradict on MVP behavior; an absolute-quantifier INV in genuine CONFLICT with a weakening NFR/ASM on MVP behavior; a spec goal violates a constitution MUST; an unresolved P0 marker blocking MVP correctness.
- **HIGH**: an untestable/unmeasurable MVP requirement; a P1 EDGE with no defined behavior; an AC contradicting its REQ; a Missing high-impact taxonomy category affecting MVP; an omitted grid pair that turns out to be a CONFLICT; every imported mechanical HIGH (M1 Covers-gap etc.) — these keep the script's severity, never downgraded.
- **MEDIUM**: undefined glossary term; non-MVP EDGE undefined; leaked physical detail; SC phrased as task; synonym drift requiring routing; defer-to-plan gaps; oversized scope; an omitted grid pair that resolves compatible; S0-002.
- **LOW**: cosmetic glossary/numbering; meaning-preserving AC reformatting; verbose phrasing; low-impact coverage gaps.

**MVP-scope**: requirements/steps tied to P1 priority in §12. A HIGH finding on MVP-scope blocks; the same class on non-MVP does not auto-block.

### 6. Determine Verdict

**Step 1 — apply the exit-code floor (Invariant 2):** if script returned exit 1, verdict is already non-PASS; you may only decide between 🔀 ROUTING REQUIRED and ⛔ BLOCK. If exit 0, the floor is open.

**Step 2 — apply semantic findings (can only raise severity):**

- 🔀 **ROUTING REQUIRED** if any Routing block exists (mechanical or semantic).
- ⛔ **BLOCK** if any CRITICAL remains, or any HIGH affects MVP-scope. A routed CRITICAL/HIGH still BLOCKS until resolved ("⛔ BLOCK — routing required").
- ✅ **PASS** only if zero Routing blocks AND zero unresolved CRITICAL/HIGH AND script did NOT return exit 1.

> **MVP-blocking precision:** a HIGH blocks ONLY if it makes P1/MVP behavior incorrect, untestable, or unbuildable. An M1 Covers-gap is a traceability defect, never MVP-blocking on its own — Route it (HIGH), but verdict is 🔀 ROUTING REQUIRED, not ⛔ BLOCK, unless another CRITICAL/MVP-breaking finding coexists.

### 7. Produce Gate Report — ALWAYS WRITTEN

Write to `REPORT` on every run. Use the standard report structure (see `.orderspec/templates/report-template.md`).

**Mandatory gate-specific sections for spec-check:**

After the Findings table, always include:

#### Coverage Taxonomy (C1)
| Category | § | Status | Disposition |
|----------|---|--------|-------------|
(render every row: Clear / Partial / Missing → Route / defer-to-plan / LOW / —)

#### Contradiction Grid (C3c / C3d)
| Pair | Verdict | Reason |
|------|---------|--------|
(render every absolute-INV × weakening-NFR/ASM pair AND every REQ × narrowing-ASM pair)

#### Journey Coverage Matrix
| UJ | Priority | Covers REQs | ACs | ACs trace to REQs | Status |
|----|----------|-------------|-----|-------------------|--------|
(render every UJ)

**Template variable mapping:**
- `report_name`: spec-report.md
- `generator_cmd`: /order.spec-check
- `gate_title`: Spec Gate Report
- `target_doc`: spec.md
- `gate_focus`: coverage + internal integrity
- `owner_cmd`: /order.spec
- `gate_specific_sections`: Coverage Taxonomy + Contradiction Grid + Journey Coverage Matrix
- `routing_blocks`: Render each finding using the Routing Block Format. "None" if PASS.
- `findings_rows`: Include all mechanical (M-) and semantic (C-) findings.

After rendering, state in one line the `REPORT` path where the file was written.

### 8. Next Actions

- **Mechanical / meaning-preserving** → already auto-fixed; no user action.
- **Contractual** → see Routing blocks; user resolves by running suggested `/order.spec "..."`.
- **defer-to-plan** → noted, not routed to spec; carries forward to `/order.plan`.
- **Oversized scope (C9)** → user decomposes via `/order.spec --split`.
- **S0-002** → suspected script-pattern bug; report to maintainer, but finding still stands.

Recommended loop: run routed `/order.spec` calls, then **re-run `/order.spec-check`** to confirm clean. The gate is idempotent: a spec with no contractual findings yields ✅ PASS.

## Post-Execution Checks

Run the **`after_spec_check`** phase per `.orderspec/memory/hooks-protocol.md`.

## Operating Principles

- **Script is ground truth (Invariant 1)**: mechanical findings are deterministic facts, imported at severity, never overruled.
- **Exit code is verdict floor (Invariant 2)**: exit 1 → cannot PASS. Semantic findings raise severity, never lower it.
- **Always write the report**: every run, every verdict, including PASS. "No file" means "the gate did not run".
- **Semantic passes are mandatory and independent**: a clean script result never lets you skip C0–C9.
- **Detect oversize, never decompose**: C9 flags and routes; density alone is never a defect.
- **Pure inspector for content**: detect and route; NEVER author, fill, or alter contract meaning.
- **One narrow write permission**: auto-fix ONLY for mechanical/strictly meaning-preserving defects. When in doubt, Route.
- **Scan BOTH NFR and ASM for weakening qualifiers**: the contradiction grid is incomplete otherwise.
- **Verify narrowing ASMs against their REQs**: an ASM tagged `[narrowing REQ-NNN]` must be checked and appear in the grid.
- **Verify ACs trace to specific REQs**: not just to a UJ's Covers list.
- **Verify mutating endpoints have authorization rules**: POST/PATCH/DELETE must have actor/auth specified.
- **Verify AC-checked fields exist in response schemas**: no phantom fields.
- **Root stance**: never read repo, plan, or reason about time.

## Context

$ARGUMENTS
