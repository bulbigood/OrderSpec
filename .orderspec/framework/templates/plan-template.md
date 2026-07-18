# Implementation Plan: [FEATURE]

**Date**: [DATE]  
**Spec**: [`spec.md`](spec.md)

**Input**: Feature specification from `spec.md`

## Summary

[Technical approach only. Do NOT restate the Executive Summary from `spec.md`. Reference Spec IDs where useful.]

---

## Delivery Strategy

| Mode | Evidence | Required Final Phase |
|------|----------|----------------------|
| [migration-emc / incremental] | [Compatibility, replacement, feature-flag, schema-contraction, or `[DEL]` evidence; otherwise state no migration transition] | [Contract / Final Verification] |

- `migration-emc` requires plan-declared compatibility or cleanup work and uses Expand → Migrate → Contract.
- `incremental` uses Setup → User Stories → Final Verification and MUST NOT invent cleanup work.

---

## Technical Context & Stack Verification

| Item | Verified Value |
|------|----------------|
| **Language/Version** | [Verified runtime/language version, or "No runtime version found in inspected manifests"] |
| **Primary Dependencies** | [Specific libraries/frameworks already present or planned because of `CON-NNN`] |
| **Storage** | [Target storage layer/tables/collections/files affected; reference Spec §8 logical model or IDs only] |
| **Testing Framework** | [Verified test framework and style] |
| **Target Platform** | [Verified platform/runtime target] |
| **Test/Build Commands** | [`command` from repository manifest/scripts, or "No command found in inspected manifests"] |
| **Constraints Honored** | [`CON-NNN`, `CON-NNN`; flag any conflict] |
| **NFR Focus** | [`NFR-NNN`, `NFR-NNN`; IDs only, no copied text] |
| **Verified Against** | [`file1`, `file2`, ... files actually read that changed a planning decision] |

---

## Environment Readiness

<!--
Declare runtime prerequisites before implementation. This is operational
planning, not feature behavior: do not copy it into spec.md.

- Check MUST be read-only and exact.
- Recovery MUST state side effect, scope, and approval requirement.
- Safe fallback MUST say how implementation proceeds without recovery, or
  explicitly say that the dependent task cannot proceed.
- If no prerequisite exists, keep one `None` row with repository evidence.
-->

| Prerequisite / Applicable Tasks or Spec IDs | Scope | Read-only Check | Expected Result | Repository Evidence | Recovery Option, Side Effect, and Approval | Safe Fallback |
|---------------------------------------------|-------|-----------------|-----------------|---------------------|---------------------------------------------|---------------|
| [MongoDB / T001 / REQ-001] | [host / cluster / external service] | [`command`] | [observable result] | [`file`, setting, or test harness] | [`command`; starts local service; user approval required] | [mock / skip / stop with route] |

---

## Mechanism Evidence & Runtime Closure

<!--
Add one row for each material mechanism whose correctness depends on an existing
project abstraction, runtime/deployment capability, external service, or
concurrency scope. Group Spec IDs only when they share the same mechanism.

Evidence rules:
- Prefer an existing project mechanism. If it is not reused, state the concrete mismatch.
- Library/API documentation proves API semantics, not repository runtime readiness.
- Runtime prerequisites need repository evidence from manifests, configuration,
  deployment files, or the test harness.
- Every file needed to establish the prerequisite must also appear in the pathmanifest.
- Operational scope must be explicit: process, host, cluster, external service,
  or not applicable.

If no material mechanism needs closure, retain the table and write one `None`
row with a short repository-evidence statement.
-->

| Mechanism / Spec IDs | Existing Project Mechanism / Reuse Decision | Runtime Prerequisites | Repository Evidence | Required Paths | Operational Scope |
|----------------------|---------------------------------------------|-----------------------|---------------------|----------------|-------------------|
| [`REQ-001`, `INV-001`] | [Reuse `...`, or justify why observed mechanism does not fit] | [Required capability, or none] | [`file`, setting, test setup] | [`pathmanifest` entries, or none] | [process / host / cluster / external service / not applicable] |

---

## Constitution Check

<!--
Status values:
- PASS: verifiable against existing repository state right now.
- DESIGN-OK: planned implementation complies, but files/code do not exist yet or enforcement happens during implementation.
- FAIL: plan violates a constitution gate; justify in Complexity Tracking or STOP if unjustified.

Granularity:
- One row per top-level constitution principle.
- Split sub-clauses only when their status differs from the principle's majority status.
-->

| Principle | Status | Evidence | Notes |
|-----------|--------|----------|-------|
| [Principle I] | [PASS / DESIGN-OK / FAIL] | [Repo evidence or planned design evidence] | [Short note] |

---

## Feature Artifacts Layout

```text
[feature-directory]/
├── spec.md              # Source of truth: WHAT contract and logical architecture
├── plan.md              # This file: physical mapping to current repository state
└── tasks.md             # Generated later by /order.tasks
```

---

## Physical Project Structure

<!--
Flat path manifest — NOT a tree.

Rules:
- One FILE per line.
- Never list directories.
- Format: <repo-relative-path>  [NEW]|[MOD]|[DEL]
- [NEW] = file does NOT exist on disk now.
- [MOD] = file DOES exist on disk now.
- [DEL] = file DOES exist on disk now and will be deleted.
- Paths are repo-relative, forward-slash, no leading ./.
- This block is machine-checked by traceability.py check-plan and validate --stage plan.
-->

```pathmanifest
src/example/new_file.py      [NEW]
src/example/existing.py      [MOD]
src/example/old_file.py      [DEL]
tests/example/test_new.py    [NEW]
```

---

## Structure & Path Decisions

### Target Folders

- **[Folder / Layer]**: [Why this folder/layer is affected]
- **[Folder / Layer]**: [Why this folder/layer is affected]

### File Naming Convention Evidence

<!--
Use only observed filenames as evidence.
Do not cite variable names, schema field names, class names, or single-word files as multi-word naming evidence.
-->

| Layer | Observed Files | Convention | New Files | Rule Fired |
|-------|----------------|------------|-----------|------------|
| Models / Entities | [`...`, `...`] | [case/suffix pattern] | [`...`] | [1 same-layer / 2 cross-layer / 3 config casing / 4 ecosystem default] |
| Services / Business Logic | [`...`, `...`] | [case/suffix pattern] | [`...`] | [rule] |
| Controllers / Handlers | [`...`, `...`] | [case/suffix pattern] | [`...`] | [rule] |
| Routes / Interface Registration | [`...`, `...`] | [case/suffix pattern] | [`...`] | [rule] |
| Tests / Fixtures | [`...`, `...`] | [case/suffix pattern] | [`...`] | [rule] |

For multi-word new filenames: [State same-layer precedent or "No same-layer multi-word precedent found; rule fired: N; chosen convention: ..."].

### Architectural Mapping

<!--
Map logical roles / Spec IDs to physical files.
Do not copy requirement text from spec.md.
-->

| Spec Role / ID | Physical Location | Rationale |
|----------------|-------------------|-----------|
| [`REQ-001`, `IF-001`] | `src/example/new_file.py` | [How this file realizes the logical contract] |
| [`AC-001`] | `tests/example/test_new.py` | [How this file verifies the acceptance path] |

### Interface Fidelity

<!-- One row per IF-NNN. Preserve contract values; do not copy full contracts. -->

| Interface ID | Method / Mounted Path | Input / Response Semantics | Failure Statuses | Realizing Boundaries |
|--------------|-----------------------|----------------------------|------------------|----------------------|
| `IF-001` | [`METHOD /mounted/path`] | [ID-referenced input, response, nullability, pagination/filter obligations] | [`4xx`, `5xx` from spec] | [`route`, `controller/serializer`, `integration test`] |

### Internal Component Diagram

<!--
Only physical/internal decomposition belongs here.
Do not redraw spec.md logical diagrams.
Use quoted Mermaid labels.
-->

```mermaid
graph TD
    A["Interface adapter / route"] --> B["Application service"]
    B --> C["Persistence adapter"]
    B --> D["Validation / policy helper"]
```

---

## Mechanism Matrix

The machine-readable mechanism matrix is **not authored in this document**.

Mechanism decisions for `REQ`, `IF`, `AC`, `EDGE`, `INV`, and `NFR` IDs are stored in:

```text
<FEATURE_DIR>/.state/mechanisms.tsv  # .orderspec/features/<feature>/.state/mechanisms.tsv
```

This file is written only by:

```bash
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" put-mechanisms
```

and checked by:

```bash
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" lint
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" check-mechanisms
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" validate --stage plan
```

Do not mirror the mechanism matrix as a Markdown table in `plan.md`.

---

## Library Documentation Evidence

<!--
Required by global policy (orderspec-rules.md: Documentation Evidence and Tooling Policy).
- For each library-specific claim, cite the evidence source (skill name, documentation source name, or user-provided reference).
- If no library-specific claims were made, write exactly: "No library-specific claims."
-->

[For each library-specific claim: cite skill name / docs source name / user reference. Or: "No library-specific claims."]

---

## Complexity Tracking

<!-- Fill ONLY if Constitution Check has FAIL rows or justified complexity exceptions. -->

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| [Violation / principle] | [Reason] | [Reason] |
