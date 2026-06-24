# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link to specs/[###-feature-name]/spec.md]

**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

## Summary

[Technical approach only; do NOT restate Executive Summary from spec]

## Technical Context & Stack Verification

**Language/Version**: [e.g., Kotlin 2.0, Python 3.11, Swift 5.9 or NEEDS CLARIFICATION]
**Primary Dependencies**: [Specific libraries needed for implementation]
**Storage**: [Target database/tables affected, matching Spec § Data Model (ERD)]
**Testing Framework**: [e.g., JUnit, pytest, XCTest]
**Target Platform**: [e.g., iOS 17+, Linux, Web/WASM]
**Test/Build Commands**: [verbatim commands from repository manifest/scripts, e.g. `yarn test`, `yarn lint`]
**Constraints Honored**: [List CON-IDs from spec; flag any conflict]
**NFR Focus**: [List NFR-IDs critical during coding — reference only, do not copy text]
**Verified Against**: [list of files actually read: package.json, src/models/user.model.js, ...]

## Constitution Check

Each gate status is one of: PASS (verifiable now, cite evidence), DESIGN-OK (the plan's design complies; enforcement happens at implement), FAIL (violation — justify in Complexity Tracking). Never mark PASS for properties of files that do not exist yet.
[Gates determined based on constitution file]

## Feature Artifacts Layout

```text
specs/[###-feature]/
├── spec.md              # Truth Source: requirements, logical architecture, data model, API contract
├── plan.md              # This file: physical file mapping, stack verification, structure decisions
├── research.md          # CONDITIONAL: generated only if unresolved technology/design questions exist
└── tasks.md             # Generated later by /order.tasks: atomic execution order
```

If no research was needed, write below the tree:
`No research.md generated — all planning inputs were resolved from spec.md and repository reconnaissance.`

## Physical Project Structure (Source Code)

<!-- Flat path manifest — NOT a tree. One FILE per line, never directories.
     Format: <repo-relative-path>  [NEW]|[MOD]
       [NEW] = file does NOT exist on disk now.
       [MOD] = file DOES exist now and will be modified.
     This is a physical fact verified by `test -e`, not a role inference:
     do NOT tag [MOD] just because a file "logically should be touched" —
     confirm it is actually present first. A mechanical check
     (validate-traceability M9/M10) compares every line against the filesystem;
     a [MOD] on a missing path, a [NEW] on an existing one, an untagged line,
     or a listed directory is a blocking finding. `test -e` is the arbiter,
     not your judgement. Paths are forward-slash, repo-relative, no leading ./ -->

```pathmanifest
src/models/user.py                      [NEW]
src/services/auth_service.py            [NEW]
src/api/routes.py                       [MOD]
src/config/settings.py                  [MOD]
tests/integration/test_auth_flow.py     [NEW]
tests/unit/services/test_auth_service.py [NEW]
```

**Structure & Path Decisions**:

* **Target Folders:** [Which existing folders are affected; what new packages must be created]

* **File Naming Convention Evidence:**

| Layer | Observed Files | Convention | New Files |
| --- | --- | --- | --- |
| Models | [`...`] | [`...`] | [`...`] |
| Services | [`...`] | [`...`] | [`...`] |
| Controllers | [`...`] | [`...`] | [`...`] |
| Validations | [`...`] | [`...`] | [`...`] |
| Routes | [`...`] | [`...`] | [`...`] |
| Tests/Fixtures | [`...`] | [`...`] | [`...`] |

For multi-word entities: [same-layer precedent or explicit statement that no precedent exists, plus chosen convention and which rule fired].

* **Architectural Mapping:** [How Spec containers/components map to the folders above]

* **Component Diagram:** Internal physical design of the planned implementation:

```mermaid
graph TD
    Ctrl[Controller] --> Svc[Service] --> Repo[Repository]
```

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
|  |  |  |