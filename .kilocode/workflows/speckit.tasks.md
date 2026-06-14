---
description: Generate a disposable, Expand-Migrate-Contract ordered tasks.md from spec.md (IDs) and plan.md (paths). Sequential phases are the backbone; parallelism is an optional, safe annotation.
handoffs:
  - label: Analyze For Consistency
    agent: speckit.analyze
    prompt: Run a project analysis for consistency
    send: true
  - label: Implement Project
    agent: speckit.implement
    prompt: Start the implementation in phases
    send: true
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Role of This Artifact

`tasks.md` answers **ORDER**: a disposable, mechanically executable checklist sequencing the work as **Expand → Migrate → Contract** (E-M-C):

- **Expand** = additive, non-breaking changes (scaffolding, stubs, additive migrations).
- **Migrate** = behavior implemented story by story, each independently verifiable.
- **Contract** = irreversible cleanup (remove flags, deprecated code, obsolete schema).

Properties:

- **Disposable**: regenerated freely; overwrite without preserving previous content. Never encode design decisions here — only sequence them.
- **Derived, not creative**: every task is a composition of a spec ID (`UJ/AC/REQ/EDGE/INV`) and a file path from plan.md. Invent nothing.
- **Weak-LLM-proof**: each task must be executable without re-reading the whole spec — it carries its file path, the spec IDs that define "done", and a one-line paraphrase of the asserted criteria.
- **Sequential-by-default**: structure is **Phases → Tasks**. Phases are hard sequential barriers. Within a phase, tasks execute top-to-bottom; this ordering MUST be correct on its own. Parallelism is an OPTIONAL annotation layered on top — never a precondition for correctness.

## Pre-Execution Checks

**Check for extension hooks (before tasks generation)**:

- If `.specify/extensions.yml` exists, read entries under `hooks.before_tasks`. If missing or unparsable YAML, skip silently.
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

1. **Setup**: Run `.specify/scripts/bash/setup-tasks.sh --json` from repo root; parse FEATURE_DIR, TASKS_TEMPLATE, AVAILABLE_DOCS. FEATURE_DIR and TASKS_TEMPLATE are absolute paths. For single quotes in args use `'I'\''m Groot'` or double quotes.

2. **Load inputs** from FEATURE_DIR:
   - **Required**: `spec.md` (UJ priorities, AC, REQ, INV, EDGE, data model, contracts), `plan.md` (physical file mapping, stack, NEW/MODIFIED files, test/build commands).
   - **Optional**: `research.md` (decisions affecting setup).
   - **IF EXISTS**: `.specify/memory/constitution.md`.

3. **Build the traceability inventory** before writing any task:
   - List all `UJ-NNN` with priorities → these become user story phases (US1 ↔ UJ-001).
   - List all `AC-NNN`, `EDGE-NNN`, `INV-NNN` and assign each to a UJ (or to Setup/Contract if cross-cutting).
   - From plan.md, list every NEW/MODIFIED file and assign each to the phase that first touches it.
   - From plan.md, note the project's test command (used verbatim in verification and GATE tasks).
   - Read plan.md 'Mechanism Decisions'. Each mechanism BINDS the task that FIRST creates the affected function — include the mechanism in that task's paraphrase. NEVER schedule a later task that retrofits a mechanism into already-written code.

4. **Generate tasks.md** using TASKS_TEMPLATE structure (fallback: `.specify/templates/tasks-template.md`). Sample tasks in the template are placeholders — replace them entirely, renumber T001..TNNN sequentially.

   **Phase mapping (E-M-C)**:
   - **Phase 1 — Setup & Expand**: project layout/config changes per plan.md. Include each item ONLY if applicable to this project — skip inapplicable items, do not invent them:
     - *If the project has persistent storage*: additive DB/schema migrations with rollback scripts (Spec: "Data Model").
     - *If the project exposes interfaces (API/CLI/UI)*: contract/route/DTO/command stubs (Spec: "Contracts").
     - Passive model entities; feature flags if plan.md defines them.
     All changes must be non-breaking.
   - **Phase 2 — Migrate: User Story 1 (P1, MVP)**, then one phase per remaining UJ in priority order. Within each story phase:
     1. Test tasks first (integration/contract tests asserting that story's `AC-NNN`; written first, must fail before implementation),
     2. Data layer → service logic → wiring to contracts,
     3. `EDGE-NNN` handling relevant to this story,
     4. Verification task: run the project's test command from plan.md; assert all the story's AC pass and `INV-NNN` hold, with no regressions on earlier stories.
     End each story phase with a **Checkpoint** line: story is independently functional and backwards-compatible.
     Test tasks may be omitted only if the user or constitution explicitly opts out of tests.
   - **Final Phase — Contract**: starts with a GATE task (run the project's test command verbatim; verify all `AC-*` pass, `INV-*` hold, `NFR-*` targets met; STOP on failure — contraction is irreversible). Then: remove feature flags, delete deprecated code/routes, drop obsolete DB columns/tables, lint/format/polish, update docs. **Greenfield rule**: if nothing pre-exists to deprecate, Contract only removes scaffolding/flags — do NOT invent legacy code to delete.

   **Parallelism annotation (OPTIONAL — never required for correctness)**:
   - The backbone is sequential: Phases are barriers; tasks within a phase execute top-to-bottom by default. The top-to-bottom order MUST already be correct on its own, with NO `[P]` marks present.
   - ADDITIONALLY, you MAY mark a task with `[P]` ONLY when it is mutually file-disjoint with every other `[P]`-marked task that is adjacent to it (no non-`[P]` task between them), AND none of them depends on another. An orchestrator MAY run such an adjacent `[P]` group concurrently; running them sequentially instead MUST produce an identical result.
   - Do NOT invent parallelism. When in doubt, omit `[P]` — sequential is always safe. A phase with no provably-safe parallel group carries NO `[P]` marks.
   - Never mark two tasks `[P]` if they touch the same file path.
   - Do NOT emit wave numbers, wave tables, or any parallelism structure beyond the optional `[P]` flag. There are no "waves".

   **Granularity rules (REQUIRED)**:
   - One task = one file (or one atomic, independently verifiable change). If a task needs more than one file, split it.
   - **No stub-then-implement**: NEVER create a controller/service/route file containing only stub/empty methods in an early phase to fill later. The file's FIRST task already contains real implementation. (Exception: only contract boundaries explicitly listed as stubs in plan.md.) A file appearing in two phases where the earlier task says "stub"/"skeleton"/"stubs" is a defect.
   - **Barrel/index exception**: registration of multiple entities created in the SAME phase into barrel/index files MUST be ONE task listing all such files — not one task per file. Example: a single task `Register Task model, taskService, taskController, taskValidation, and task route in their respective src/**/index.js barrel files`.
   - Soft limits: 3–15 tasks per story phase. If a story would exceed 15 tasks, do NOT silently generate more — flag the UJ as too large in the Completion Report and recommend splitting it in spec.md.
   - Each task must be completable by an LLM in a single pass without intermediate decisions left open.

   **Task format (STRICT)**:

   ```text
   - [ ] T012 [P] [US1] Create User model in src/models/user.py (REQ-001: user has unique email, hashed password)
   ```

   - Checkbox `- [ ]` always; sequential ID `T001..TNNN` in execution order.
   - `[P]` is OPTIONAL — present only when the parallelism rules above are satisfied; absent otherwise.
   - `[USn]` required for story-phase tasks only (maps 1:1 to UJ-00n); no story label in Setup/Expand or Contract phases.
   - Every implementation task names an exact file path from plan.md.
   - A task implementing or wiring an endpoint MUST include its non-2xx semantics from Spec § API Contracts in the paraphrase (e.g., '404 only if task never existed, including soft-deleted').
   - Every test/verification task names the `AC-`/`EDGE-`/`INV-` IDs it asserts, each with a ≤15-word paraphrase so the implementer need not re-open spec.md.
   - ✅ `- [ ] T012 [P] [US1] Create User model in src/models/user.py (REQ-001: user has unique email, hashed password)`
   - ✅ `- [ ] T015 [US1] Integration test in tests/test_auth.py (AC-002: invalid credentials return 401)`
   - ❌ `- [ ] Create User model` (no ID/label/path); ❌ `T013 [US1] ...` (no checkbox); ❌ `- [ ] T014 [US1] Implement service` (no path); ❌ `- [ ] T016 [US1] Test login (AC-002)` (ID without paraphrase).

   **Also fill**: the Execution Order line (Phase 1 → US1 → STOP & VALIDATE → US2.. → GATE → Contract), each story phase's Goal and Verification lines (from spec § Acceptance Criteria), and the single **Traceability Matrix** at the end of the file.

5. **Validate coverage** before writing the file:
   - Every `AC-NNN` asserted by ≥1 test/verification task.
   - Every `EDGE-NNN` and `INV-NNN` handled by ≥1 task.
   - Every NEW/MODIFIED file from plan.md appears in ≥1 task; no task references a path absent from plan.md.
   - No two `[P]`-marked adjacent tasks touch the same file path.
   - Every task's prerequisites precede it in document order (no forward references).
   - Each story phase is an independently testable increment; US1 alone is a viable MVP.
   - Fix gaps, re-order, and renumber before finalizing.

## Mandatory Post-Execution Hooks

**You MUST complete this section before reporting completion.**

- If `.specify/extensions.yml` is missing, unparsable, or has no `hooks.after_tasks` entries, skip to Completion Report.
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

Output the tasks.md path and:

- Total task count; count per phase and per user story.
- Parallelism: number of `[P]`-marked tasks and the largest adjacent `[P]` group (0 if none — that is acceptable and expected for strictly sequential features).
- Coverage summary: AC/EDGE/INV → tasks (flag any unmapped IDs).
- Oversized stories flagged (any UJ exceeding the 15-task soft limit, with split recommendation).
- Suggested MVP scope (US1) and the STOP & VALIDATE checkpoint.
- Format validation: ALL tasks follow checkbox + ID + optional `[P]` + labels + file path + spec-ID-with-paraphrase format.

Context for task generation: $ARGUMENTS

## Done When

- [ ] tasks.md generated in E-M-C order with sequential IDs, file paths, and spec ID references with paraphrases.
- [ ] Sequential backbone is correct with all `[P]` marks stripped; `[P]` applied only to provably file-disjoint independent tasks.
- [ ] Coverage validated: all AC/EDGE/INV mapped, all plan.md files touched, no same-file conflict within an adjacent `[P]` group.
- [ ] Single Traceability Matrix and Files-touched table filled; hooks dispatched or skipped per rules above; completion reported.
