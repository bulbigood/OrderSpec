---
description: Map the spec's logical architecture onto the current codebase — physical structure, verified stack, and constitution gates.
handoffs:
  - label: Create Tasks
    agent: speckit.tasks
    prompt: Break the plan into tasks
    send: true
  - label: Create Checklist
    agent: speckit.checklist
    prompt: Create a checklist for the following domain...
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Role of This Artifact

`plan.md` answers **WHERE and HOW**: it maps the stable contract in `spec.md` onto the **current physical state of the repository**. Properties:

- **Regenerable**: derived from spec.md + actual codebase. If the repo changes, re-run this command; never edit spec.md to fit the code.
- **Non-duplicating**: reference spec IDs (`REQ-`, `NFR-`, `CON-`, `INV-`) — do NOT copy their text, do NOT restate the Executive Summary, do NOT re-draw spec diagrams. The only diagram here is the internal Component Diagram (physical decomposition of spec containers).
- **Concrete**: exact files, folders, versions, and verified facts from the repo — no aspirational placeholders.

## Contract Drift Guard

`spec.md` is the stable contract. During planning, you MUST NOT introduce new externally visible behavior unless it is explicitly present in `spec.md`.

Forbidden additions unless already specified:

- new API endpoints, request/response shapes, status codes, fields, enums, permissions, roles, RBAC rules, authorization semantics, retention policies, TTLs, background jobs, feature flags, environment variables, or user-visible semantics;
- new non-functional targets or scale numbers not stated in `spec.md`;
- alternative error semantics that differ from acceptance criteria or clarifications.

Allowed additions:

- internal implementation mechanisms needed to satisfy existing `REQ-`, `NFR-`, `CON-`, `INV-`, `EDGE-`, or `AC-` IDs;
- physical file/module mapping;
- test file mapping;
- verified dependency/version facts from the repository.

If a necessary implementation decision would change the contract, STOP and report:
`PLAN_BLOCKED: contract decision required`, followed by the conflicting Spec IDs and the proposed decision.

## Pre-Execution Checks

**Check for extension hooks (before planning)**:

- If `.specify/extensions.yml` exists, read entries under `hooks.before_plan`. If missing or unparsable YAML, skip silently.
- Filter out hooks with `enabled: false` (absent `enabled` = enabled).
- Do **not** evaluate hook `condition` expressions: hooks with no/empty `condition` are executable; hooks with a non-empty `condition` are skipped (left to HookExecutor).
- For each executable hook, output by `optional` flag:
  - **Optional hook** (`optional: true`):

    ```text
    ## Extension Hooks

    **Optional Pre-Hook**: {extension}
    Command: `/{command}`
    Description: {description}

    Prompt: {prompt}
    To execute: `/{command}`
    ```

  - **Mandatory hook** (`optional: false`):

    ```text
    ## Extension Hooks

    **Automatic Pre-Hook**: {extension}
    Executing: `/{command}`
    EXECUTE_COMMAND: {command}

    Wait for the result of the hook command before proceeding to the Outline.
    ```

## Outline

1. **Setup**: Run `.specify/scripts/bash/setup-plan.sh --json` from repo root; parse FEATURE_SPEC, IMPL_PLAN, SPECS_DIR, BRANCH. For single quotes in args use `'I'\''m Groot'` or double quotes.

2. **Load context**: Read FEATURE_SPEC (the SDD) and `.specify/memory/constitution.md`. Load the IMPL_PLAN template (already copied).

3. **Codebase reconnaissance** (mandatory — `plan.md` must reflect repository reality):

   Perform a focused repository scan before filling the plan. Use the smallest file set sufficient to map `spec.md` onto the current codebase.

   ### Reconnaissance Read Budget

   **Hard cap**: read at most 1 dependency manifest + 1 entrypoint/route-registration file + 1 exemplar per touched implementation layer + the shared utilities/middlewares/plugins explicitly named by `spec.md` constraints. If the total exceeds ~12 files, you are over-reading. In `Verified Against`, list ONLY files whose content actually changed a planning decision.

   Default maximum: read no more than:
   - dependency manifest(s): `package.json`, `pyproject.toml`, `go.mod`, `build.gradle`, `Cargo.toml`, etc.;
   - application entrypoint or route registration file(s);
   - one existing exemplar per touched implementation layer, when available:
     - model/entity/schema layer;
     - validation/request schema layer;
     - route/API registration layer;
     - controller/handler layer;
     - service/business logic layer;
     - repository/data access layer, if the project uses one;
   - shared utilities, middlewares, plugins, or framework helpers explicitly named by `spec.md` constraints;
   - test setup/configuration and one analogous test file per relevant test type.

   Do not recursively inspect whole directories unless first-pass evidence is insufficient. If additional files are needed, read only the specific files required and record them in `Verified Against` with a short reason, e.g. `+ src/db/migrations/... because migration convention was not inferable from manifest/examples`.

   Prefer representative exemplars over exhaustive reading.

   ### What to Verify

   - **Stack and commands**: actual language/runtime versions, framework/library versions, package manager, test/lint/build scripts.
   - **Source layout**: existing top-level structure, module boundaries, layer names, route mounting style, config organization, migration/tooling conventions if relevant.
   - **Touched files vs. gaps**:
     - identify existing files that must be modified and mark them `[MOD]`;
     - identify missing files that must be created and mark them `[NEW]`;
     - every `[MOD]` path MUST exist at plan time;
     - every `[NEW]` path MUST NOT exist at plan time.
   - **Spec constraints**: verify every `CON-NNN` against repository evidence; flag conflicts explicitly.
   - **Testing conventions**: test folder layout, naming pattern, fixtures/helpers, integration vs. unit test style, command used to run tests.
   - **Implementation mechanisms**: inspect enough analogous code to choose concrete mechanisms for relevant `AC-`, `INV-`, `EDGE-`, and `NFR-` items.

   ### Naming Convention Verification

   Record naming conventions from actual files in each affected target folder.

   Requirements:
   - Cite at least 2 observed filenames per affected layer when available.
   - Record case style and suffix pattern, e.g. `kebab-case`, `camelCase`, `PascalCase`, `*.service.js`, `*.controller.ts`.
   - Do not claim a convention as verified unless there is direct repository evidence.
   - Every `[NEW]` path MUST follow the verified or explicitly justified convention.

   For multi-word new filenames (e.g. `auditLog` / `audit-log`), choose the case style by applying the FIRST matching rule below, and record which rule fired:
   1. Same-layer multi-word filename precedent.
   2. Cross-layer multi-word filename precedent.
   3. Repo config-filename casing (e.g. config files with multiple words).
   4. Ecosystem default (camelCase for JS/TS source files).

   When no same-layer precedent exists (rule 1 fails), explicitly write:
   `No same-layer multi-word precedent found; rule fired: <N>; chosen convention: ...`.

   The rationale MUST NOT cite a single-word filename, a schema field name, a variable name, or a function name as evidence — none of these carry a multi-word filename-case signal. Use only the rule that actually fired. This fixed order keeps filenames stable across plan regenerations.

   ### Required Output in `plan.md`

   The plan MUST include:
   - `Technical Context & Stack Verification` with verified versions, dependencies, commands, constraints honored, NFR IDs, and `Verified Against`.
   - `Physical Project Structure` with exact project-relative paths annotated `[NEW]` or `[MOD]`.
   - `Structure & Path Decisions` with:
     - target folders.
     - file naming convention evidence.
     - architectural mapping from spec containers/components to physical files.
     - mechanism decisions for relevant `REQ-`, `AC-`, `INV-`, `EDGE-`, and `NFR-` IDs. Mechanism decisions MUST include `Spec ID(s)`, `Mechanism`, `Primary Files`, and `Test Type`.
     - `Test Type` is one of `unit`, `integration`, or `—` only. Do NOT name concrete test files or describe assertions here — that is owned by `/speckit.tasks`.
     - Group Spec IDs that share one mechanism into a single row with comma-separated IDs. Emit one row per distinct mechanism, NOT one row per requirement. A grouped row automatically carries the strongest mechanism among its IDs.
     - For every spec Clarification that constrains a STORED shape or persisted value (not just behavior), emit a Mechanism Decisions row capturing the concrete persistence decision (e.g. "store full post-action entity snapshot, not a diff").
     - one internal component diagram showing physical decomposition.

   If repository evidence contradicts `spec.md`, STOP and report the contradiction. Do not silently adapt the contract to the codebase.

4. **Fill the plan template**:
   - **Summary**: technical approach only (2-4 sentences).
   - **Technical Context & Stack Verification**: verified facts from step 3. Mark genuinely unresolvable items as "NEEDS CLARIFICATION". List CON-IDs honored and NFR-IDs critical during coding (IDs only).
   - **Constitution Check**: evaluate gates from the constitution.

   Granularity rule:
     - Emit ONE row per top-level constitution principle (e.g. I, II, III, IV), NOT one row per sub-clause.
     - Merge sub-clauses with the same status into a short list inside the `Evidence` cell.
     - Split a sub-clause into its own row ONLY if its status differs from the principle's majority status.

   Gate status rules:
     - `PASS` = verifiable against existing repository state right now. Use only when the relevant code/config already exists or the feature does not change that area.
     - `DESIGN-OK` = planned implementation complies, but the relevant files/code do not exist yet or enforcement happens during implementation.
     - `FAIL` = current plan violates a constitution gate; justify in Complexity Tracking or STOP if unjustified.

   Never mark `PASS` for properties of planned `[NEW]` files. For new controllers, services, validations, routes, models, tests, indexes, or response behavior, use `DESIGN-OK` unless already implemented.

   - **Phase 0 — Research (conditional)**: only if NEEDS CLARIFICATION items or unverified technology choices remain. For each, research and record in `research.md`: Decision / Rationale / Alternatives considered. Skip the file entirely if nothing to resolve. All NEEDS CLARIFICATION must be resolved before Phase 1.
   - **Phase 1 — Physical Structure**:
     - Feature Artifacts Layout (per template).
     - Physical Project Structure: exact directories and files, each annotated NEW or MODIFIED. The tree MUST be valid ASCII: use `├──` for every non-last entry in a directory and `└──` ONLY for the last entry; never emit two `└──` in a row within the same directory. `[MOD]` files (e.g. index.js) sit alongside `[NEW]` files inside their parent directory in the correct branch order.
     - Each new service/business-logic file must have a corresponding planned unit test file shown as an exact path in `Physical Project Structure`, unless explicitly justified. Mentions in Constitution Check or Mechanism Decisions do not count unless the test file appears in the structure.
     - Structure & Path Decisions: target folders, architectural mapping (which spec container/component → which folder/module), Component Diagram showing internal design of spec containers.
     - Do NOT generate `data-model.md`, `contracts/`, or `quickstart.md` — the data model and API contracts live in `spec.md`; reference their section headings or Spec IDs instead of duplicating them.
     - Scan spec ACs/INVs/EDGEs for cases requiring a concrete mechanism (atomicity, concurrency, idempotency, cascading). For each, record a one-line decision in Structure & Path Decisions (e.g., `AC-008 → atomic conditional update, not read-modify-write`). The plan owns HOW; do not defer mechanism choices to implement.
   - **Re-evaluate Constitution Check** after Phase 1 layout.

5. **Agent context update**: update the plan reference between `<!-- SPECKIT START -->` and `<!-- SPECKIT END -->` markers in `.kilocode/rules/specify-rules.md` to point to IMPL_PLAN.

## Key Rules

- Absolute paths for filesystem operations; project-relative paths inside documents.
- ERROR on gate failures or unresolved NEEDS CLARIFICATION.
- If the plan reveals a contradiction in spec.md, STOP and report — do not silently "fix" the contract.
- Every file path in the plan must be real (existing) or explicitly marked NEW.

## Mandatory Post-Execution Hooks

**You MUST complete this section before reporting completion.**

- If `.specify/extensions.yml` is missing, unparsable, or has no `hooks.after_plan` entries, skip to Completion Report.
- Filter out `enabled: false` hooks (absent = enabled). Do **not** evaluate `condition`: no/empty condition = executable; non-empty condition = skip (left to HookExecutor).
- For each executable hook:
  - **Mandatory** (`optional: false`) — **MUST emit `EXECUTE_COMMAND:`**:

    ```text
    ## Extension Hooks

    **Automatic Hook**: {extension}
    Executing: `/{command}`
    EXECUTE_COMMAND: {command}
    ```

  - **Optional** (`optional: true`):

    ```text
    ## Extension Hooks

    **Optional Hook**: {extension}
    Command: `/{command}`
    Description: {description}

    Prompt: {prompt}
    To execute: `/{command}`
    ```

## Completion Report

Report: branch, IMPL_PLAN path, whether `research.md` was generated, constitution gate status, count of NEW vs MODIFIED files, and readiness for `/speckit.tasks`.

## Done When

The following self-check is for the generator only. Do NOT copy this checklist, "Done When", or any "Completion Checklist" block into `plan.md`. The artifact ends at Complexity Tracking.

Before reporting completion, run this blocking self-check against the generated `plan.md`.

If any item fails, fix `plan.md` and repeat the self-check.  
If it cannot be fixed without changing `spec.md`, STOP and report `PLAN_BLOCKED`.

- [ ] **No contract drift**
  - `plan.md` does not add externally visible behavior absent from `spec.md`.
  - No new endpoints, status codes, response shapes, fields, enums, permissions, roles, RBAC rules, authorization semantics, retention policies, TTLs, background jobs, feature flags, environment variables, or NFR targets were added unless specified.

- [ ] **Repo mapping is complete**
  - Technical context, test/build commands, constitution gates, physical file mapping, naming evidence, architectural mapping, mechanism decisions, and component diagram are filled.
  - Every planned file is marked `[NEW]` or `[MOD]`.
  - Required registration/export files are included.
  - The Physical Project Structure tree is valid: exactly one `└──` (last entry) per directory; all other entries use `├──`; no orphan/duplicate `└──`.

- [ ] **Tests are mapped**
  - Every new service/business-logic file has a corresponding planned unit test shown as an exact path in `Physical Project Structure`, unless explicitly justified.
  - Every API endpoint from `spec.md` has planned integration test coverage.
  - Every Mechanism Decisions row has a `Test Type` (`unit`/`integration`/`—`); concrete test files are left to `/speckit.tasks`.

- [ ] **Mechanisms are consistent**
  - Mechanism Decisions include Spec ID(s), mechanism, primary files, and test type.
  - Spec IDs sharing one mechanism are grouped into a single row; there is no row whose mechanism duplicates another row.
  - No operation is described with two conflicting implementation mechanisms.

- [ ] **Ready for `/speckit.tasks`**
  - `/speckit.tasks` should not need to invent missing architecture decisions.
  - Completion report includes branch, `plan.md` path, whether `research.md` was generated, constitution status, count of `[NEW]` vs `[MOD]` files, and readiness for `/speckit.tasks`.
