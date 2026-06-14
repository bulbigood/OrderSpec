---
description: Execute tasks.md phase by phase in sequential task order, respecting [P] parallel hints, story checkpoints, and the irreversible Contract GATE.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Execution Model

This command **executes** — it makes no design decisions. All decisions live in spec.md (WHAT) and plan.md (HOW); tasks.md defines ORDER. Properties:

- **Tasks are self-contained**: each task carries its file path and spec IDs with paraphrases. Execute from the task line; open spec.md ONLY if a paraphrase is insufficient to act — never re-read it wholesale.
- **Sequential by default, `[P]` is a hint**: tasks execute top-to-bottom in ID order. A `[P]` marker means a task is file-disjoint and independent of its adjacent `[P]` tasks, so adjacent `[P]` tasks MAY be run concurrently. There are no "waves". Sequential execution is always correct on its own.
- **Resumable**: tasks marked `[X]` are already done — skip them, never redo or "improve" them. A re-run continues from the first unchecked task.
- **No silent deviations**: if a task cannot be executed as written (missing path, contradiction with plan.md, broken dependency), apply the Deviation Rule below — do not improvise.

## Pre-Execution Checks

**Check for extension hooks (before implementation)**:

- If `.specify/extensions.yml` exists, read entries under `hooks.before_implement`. If missing or unparsable YAML, skip silently.
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

1. **Setup**: Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` from repo root; parse FEATURE_DIR and AVAILABLE_DOCS. All paths absolute. For single quotes in args use `'I'\''m Groot'` or double quotes.

2. **Checklists gate** (if `FEATURE_DIR/checklists/` exists):
   - For each checklist file count total (`- [ ]`, `- [x]`, `- [X]`), completed (`- [x]`/`- [X]`), incomplete (`- [ ]`) items; render a status table (Checklist | Total | Completed | Incomplete | Status).
   - If ALL checklists pass → display table, proceed.
   - If ANY is incomplete → display table, **STOP** and ask: "Some checklists are incomplete. Proceed with implementation anyway? (yes/no)". Continue only on explicit yes.

3. **Load execution context** (minimal by default):
   - **REQUIRED**: `tasks.md` — phases, tasks, `[P]` hints, Traceability Matrix, Files Touched, checkpoints, GATE.
   - **REQUIRED**: `plan.md` — tech stack, file structure, build/test commands.
   - **IF EXISTS**: `.specify/memory/constitution.md` — governance constraints.
   - **ON DEMAND ONLY**: `spec.md` — open a specific section only when a task's spec-ID paraphrase is insufficient to act. Do not preload.

4. **Validate tasks.md format** before executing:
   - Every task has a checkbox, a `Tnnn` ID, and a file path (or names the AC/EDGE/INV IDs it verifies, for test/verification tasks).
   - Task IDs are monotonically increasing (T001, T002, ... with no out-of-order insertions). Out-of-order IDs signal a hand-patched file — flag it but proceed in document order.
   - Structure follows the E-M-C skeleton: a Setup & Expand phase first, one phase per user story in the middle, and a Contract phase LAST whose first task is the GATE. Extra non-story phases (e.g. a dedicated unit-test phase) are allowed as long as they sit before the Contract GATE.
   - A `[P]` marker is OPTIONAL; its absence everywhere is valid (purely sequential plan). Do NOT require any parallel markers.
   - If the structure is invalid (no GATE, Contract not last, missing phases): **STOP** and suggest re-running `/speckit.tasks` (tasks.md is disposable — regenerate, don't hand-patch).

5. **Execute** phase by phase, in task-ID order:

   **The loop**:
   - Phases run strictly in order (hard sequential barriers). Within a phase, execute tasks top-to-bottom in ID order.
   - Skip tasks already marked `[X]` (resume support).
   - After completing each task: mark it `[X]` in tasks.md immediately, before starting the next task.

   **Parallelism (`[P]`) — opt-in, verified, never assumed**:
   - Default: execute sequentially. `[P]` is only a hint that adjacent marked tasks *may* be safe to run concurrently.
   - **Single-agent mode**: ignore `[P]` entirely — run everything sequentially in ID order. This is always correct.
   - **Orchestrator mode** (sub-agents available) — before dispatching any group of adjacent `[P]` tasks concurrently, VERIFY independence:
     - Cross-check the **Files Touched** table: if any two candidate tasks share a file, they are NOT parallel-safe — run them sequentially regardless of the `[P]` marker.
     - Only dispatch tasks concurrently when every pair in the group is file-disjoint per Files Touched. Wait for ALL to finish before continuing past the group.
     - When in doubt, fall back to sequential. Losing parallelism is harmless; a same-file race is not.

   **Per-task rules**:
   - Touch only the file named in the task. Need to change another file → that's a deviation (see Deviation Rule).
   - Never create a file as an empty stub to "fill later" — implement the task's real behavior now. If a task itself says to create a stub, that is its complete deliverable.
   - Test tasks (TDD): write the test, run it, **confirm it fails** before implementing the corresponding code. If it passes immediately, flag it — the test may be vacuous.
   - Verification tasks: run the project's test command from plan.md verbatim; report pass/fail per asserted AC/INV ID.

   **Checkpoint / STOP & VALIDATE** (end of each story phase):
   - Run the story's verification task; confirm the story works independently and earlier stories show no regressions.
   - On failure: **STOP within this phase**. Fix forward only the tasks of the current story; do not start the next story until the checkpoint passes.

   **GATE before Contract** (absolute barrier):
   - Run the full test command from plan.md verbatim; verify all AC pass, INV hold, NFR targets met.
   - **On any failure: HALT. Never proceed to Contract** — contraction (deleting code, dropping columns, removing flags, removing scaffolding) is irreversible. Report what failed and stop.

   **Failure handling summary**:

   | Level | On failure |
   |---|---|
   | Task (sequential) | Halt; report task ID, error, suspected cause |
   | Task (in a concurrent `[P]` group) | Finish sibling tasks already dispatched; report failed ones; do not advance past the group |
   | Checkpoint | Stay in current story phase; fix forward; re-verify |
   | GATE | HALT everything; Contract phase is forbidden until GATE passes |

   **Deviation Rule**:
   - Minor mechanical fixes (typo in a path with an obvious unique match, missing import) — apply, and log one line: `DEVIATION: Tnnn — what changed and why`.
   - Anything requiring a design decision (new file not in plan.md, contract change, schema change) — **do not decide**. Stop and report: the fix belongs in spec/plan/tasks, not here.
   - Collect all deviation lines for the Completion Report.

6. **Progress reporting** (keep it lean):
   - After each **phase**: one line — `Phase N: T010–T014 done (1 deviation)`.
   - After a concurrent `[P]` group: one line naming the task IDs run together.
   - After each **checkpoint/GATE**: verification result with AC/INV IDs pass/fail.
   - No per-task narration beyond errors and deviations.

## Mandatory Post-Execution Hooks

**You MUST complete this section before reporting completion.**

- If `.specify/extensions.yml` is missing, unparsable, or has no `hooks.after_implement` entries, skip to Completion Report.
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

- **Tasks**: completed / total, per phase; confirm all completed tasks are marked `[X]` in tasks.md.
- **Coverage check**: using the Traceability Matrix in tasks.md, confirm every Spec ID maps to at least one completed (`[X]`) task. List any ID whose tasks are not all complete.
- **Verification**: checkpoint results per story; GATE result; final test command output summary (pass/fail counts).
- **Deviations log**: all `DEVIATION:` lines (or "none").
- **If halted early**: exact stopping point (phase/task), reason, and the recommended next command (`/speckit.implement` to resume, or `/speckit.tasks` / `/speckit.plan` if the failure is a design gap).

Context for execution: $ARGUMENTS

## Done When

- [ ] All tasks executed in phase + task-ID order and marked `[X]`, or a precise stopping point reported
- [ ] `[P]` groups run concurrently ONLY after Files-Touched verification; otherwise sequential
- [ ] All story checkpoints passed; GATE passed before any Contract task ran
- [ ] Every Traceability-Matrix Spec ID covered by a completed task (or gaps reported)
- [ ] Deviations logged and reported; no silent design decisions made
- [ ] Hooks dispatched or skipped per rules above; completion reported
