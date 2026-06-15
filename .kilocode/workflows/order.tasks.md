---
description: Generate a disposable, Expand-Migrate-Contract ordered tasks.md from spec.md (IDs) and plan.md (paths). Sequential phases are the backbone; parallelism is an optional, safe annotation.
handoffs:
  - label: Analyze For Consistency
    agent: order.analyze
    prompt: Run a project analysis for consistency
    send: true
  - label: Implement Project
    agent: order.code
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

- **Expand** — additive, non-breaking changes (scaffolding, stubs, additive migrations).
- **Migrate** — behavior implemented story by story, each independently verifiable.
- **Contract** — irreversible cleanup (remove flags, deprecated code, obsolete schema).

Properties:

- **Disposable**: regenerated freely; overwrite without preserving previous content. Sequence decisions here — never make them. Every design choice already lives in plan.md.
- **Derived, not creative**: every task composes a spec ID (`UJ/AC/REQ/EDGE/INV`) with a file path from plan.md. Invent nothing.
- **Weak-LLM-proof**: each task is executable without re-reading the whole spec — it carries its file path, the spec IDs that define "done", and a ≤15-word paraphrase of the asserted criteria.
- **Sequential-by-default**: structure is **Phases → Tasks**. Phases are hard sequential barriers. Within a phase, tasks execute top-to-bottom; this ordering MUST be correct on its own. Parallelism is an OPTIONAL annotation layered on top — never a precondition for correctness.

## Pre-Execution Checks

Run the **`before_tasks`** phase per `.orderspec/memory/hooks-protocol.md`.

## Upstream Gate Guard

Tasks must not be derived without an approved plan. First resolve the feature
directory, then run the deterministic guard (it only checks that `plan.md` exists
and reads its gate verdict):

```bash
FEATURE_DIR="$(jq -r '.feature_directory' .orderspec/feature.json)"

.orderspec/scripts/bash/check-upstream-gate.sh \
  --report        "$FEATURE_DIR/checklists/plan-report.md" \
  --artifact      "$FEATURE_DIR/plan.md" \
  --upstream-name "plan.md" \
  --this          "/order.tasks" \
  --build         "/order.plan" \
  --fix           "/order.plan" \
  --recheck       "/order.plan-check" \
  $FORCE_FLAG
```

`$FORCE_FLAG` is `--force` iff the user input explicitly contains `--force` (or an
unambiguous "derive tasks anyway despite ROUTING/BLOCK"); otherwise empty.

Act on the result by exit code / `status`:

- **exit 2, `status: stop`** → **STOP. Produce NO tasks.** There is no `plan.md` to
  derive from. `--force` does NOT override this. Print the STOP message and end.
- **exit 1, `status: halt`** → **STOP. Produce NO tasks.** The plan has unresolved
  gate findings. Print the HALT message and end. Do not generate any task.
- **exit 0, `status: forced`** → emit a prominent warning AND stamp this line at
  the very top of `tasks.md`:
  `> ⚠ Built over non-PASS plan gate (verdict: {verdict}) via --force` — then proceed.
- **exit 0, `status: advisory`** → emit the `reason` as a one-line ⚠ warning, then
  proceed (gate is optional, or plan changed after PASS — not a hard stop).
- **exit 0, `status: ok`** → plan approved; proceed silently.

**STOP message (exit 2 — missing artifact):**

```text
TASKS_STOPPED: no plan to derive tasks from
There is no plan.md in this feature ({FEATURE_DIR}).
Tasks break down an existing plan — the plan must exist first.
  1. Create the plan:  /order.plan "I am building with <stack>"
  2. (recommended) Verify it: /order.plan-check
  3. Then run /order.tasks
--force does NOT bypass this — there is genuinely nothing to break down.
```

**HALT message (exit 1 — gate not passed):**

```text
TASKS_BLOCKED: plan gate not passed
Plan gate verdict: {verdict} (from checklists/plan-report.md, dated {date})
The plan has unresolved findings. Resolve them first:
  1. Action each Routing block in plan-report.md via /order.plan "..."
  2. Re-run /order.plan-check until the verdict is ✅ PASS
  3. Then re-run /order.tasks
To derive tasks anyway (NOT recommended), re-run with --force.
```

## Self Gate Report Intake

Before regenerating `tasks.md`, check whether a gate report from a previous run
exists at `checklists/tasks-report.md`. If present, it is the cited input for any
refinement request — it carries the Routing blocks you must action. (The report is
written by the optional `/order.tasks-check` gate; this command does not require
that gate to exist — it only reads the file if it is there.)

```bash
SELF_REPORT="$FEATURE_DIR/checklists/tasks-report.md"
test -e "$SELF_REPORT" && echo "SELF_REPORT_PRESENT" || echo "SELF_REPORT_ABSENT"
```

- **SELF_REPORT_ABSENT** → no prior gate run for this artifact. Proceed normally; treat
  `$ARGUMENTS` as the only refinement signal.
- **SELF_REPORT_PRESENT** → read `$SELF_REPORT` and parse its header verdict
  (`✅ PASS` | `⛔ BLOCK` | `🔀 ROUTING REQUIRED`):
  - **verdict ✅ PASS** → the previous tasks.md was clean. Ignore the report as a
    fix-source; proceed with `$ARGUMENTS` only.
  - **verdict ⛔ BLOCK or 🔀 ROUTING REQUIRED** → this is the authoritative list of
    defects YOU must resolve. You MUST:
    1. Read the **Routing Required** section and the **Findings** table.
    2. Address **every** finding whose `Run` line targets `/order.tasks` — each becomes
       a concrete change in tasks.md.
    3. Findings whose `Run` line targets a DIFFERENT command (e.g. `/order.plan` or
       `/order.spec`) are NOT yours: do NOT silently compensate for them. If an
       unresolved upstream finding blocks a fix you must make, STOP and report
       `TASKS_BLOCKED: upstream finding must be resolved first`, listing the finding
       IDs and their owning command.
    4. Treat `$ARGUMENTS` as ADDITIONAL guidance layered on top of the report — never a
       replacement for it. If `$ARGUMENTS` is vague ("fix the errors" / "исправь
       ошибки"), the report findings ARE the definition of "the errors": action them by ID.

  Record in the Completion Report which report-finding IDs you addressed, so a follow-up
  `/order.tasks-check` can confirm closure.

## Outline

1. **Setup**: Run `.orderspec/scripts/bash/setup-tasks.sh --json` from repo root; parse FEATURE_DIR, TASKS_TEMPLATE, AVAILABLE_DOCS (absolute paths). For single quotes in args use `'I'\''m Groot'` or double quotes.

2. **Load inputs** from FEATURE_DIR:
   - **Required**: `spec.md` (UJ priorities, AC, REQ, INV, EDGE, data model, contracts), `plan.md` (file mapping, stack, NEW/MOD files, test/build commands).
   - **Optional**: `research.md`; **IF EXISTS**: `.orderspec/memory/constitution.md`.

3. **Build the traceability inventory** before writing any task:
   - List all `UJ-NNN` with priorities → these become user story phases (US1 ↔ UJ-001).
   - List all `AC-NNN`, `EDGE-NNN`, `INV-NNN` and assign each to a UJ (or to Setup/Contract if cross-cutting).
   - From plan.md, list every NEW/MOD file and assign each to the phase that first touches it.
   - Note the project's test command from plan.md (used verbatim in verification and GATE tasks).
   - Read plan.md 'Mechanism Decisions'. Each mechanism BINDS the task that FIRST creates the affected function — include the mechanism in that task's paraphrase. NEVER schedule a later task that retrofits a mechanism into already-written code.

4. **Generate tasks.md** using TASKS_TEMPLATE (fallback: `.orderspec/templates/tasks-template.md`). Template sample tasks are placeholders — replace entirely, renumber T001..TNNN sequentially.

   **Phase mapping (E-M-C)**:
   - **Phase 1 — Setup & Expand**: layout/config changes per plan.md. Include each item ONLY if applicable — skip inapplicable ones, never invent:
     - *If persistent storage exists*: additive DB/schema migrations with rollback scripts (Spec: "Data Model").
     - *If interfaces exist (API/CLI/UI)*: contract/route/DTO/command stubs (Spec: "Contracts").
     - Passive model entities; feature flags only if plan.md defines them.
     All changes non-breaking.
   - **Phase 2+ — Migrate**: User Story 1 (P1, MVP) first, then one phase per remaining UJ in priority order. Within each story phase:
     1. Test tasks first (integration/contract tests asserting that story's `AC-NNN`; written first, MUST fail before implementation).
     2. Data layer → service logic → wiring to contracts.
     3. `EDGE-NNN` handling relevant to this story.
     4. Verification task: run the project's test command; assert the story's AC pass and `INV-NNN` hold, no regressions on earlier stories.
     End each story phase with a **Checkpoint** line: story independently functional and backwards-compatible.
     Test tasks may be omitted only if the user or constitution explicitly opts out.
   - **Final Phase — Contract**: starts with a GATE task (run the test command verbatim; verify all `AC-*` pass, `INV-*` hold, `NFR-*` met; STOP on failure — contraction is irreversible). Then: remove flags, delete deprecated code/routes, drop obsolete columns/tables, lint/format/polish, update docs. **Greenfield rule**: if nothing pre-exists to deprecate, Contract only removes scaffolding/flags — do NOT invent legacy to delete.

   **Parallelism annotation (OPTIONAL — never required for correctness)**:
   - The sequential backbone must be correct with NO `[P]` marks present. `[P]` is layered on top, never a precondition.
   - Mark `[P]` ONLY when a task is mutually file-disjoint with every adjacent `[P]`-marked task (no non-`[P]` task between them) AND none depends on another. Running such a group sequentially MUST produce an identical result.
   - Never mark two tasks `[P]` if they touch the same file path. When in doubt, omit `[P]`.
   - Emit NO wave numbers, wave tables, or any parallelism structure beyond the `[P]` flag. There are no "waves".

   **Granularity rules (REQUIRED — these prevent both over-splitting and kitchen-sink tasks)**:
   - **One task = one file** (or one atomic, independently verifiable change). If a task needs more than one file, split it. (Barrel/index exception below.)
   - **Spec-ID cap (atomicity floor)**: an implementation task references **at most 3 spec IDs that drive distinct behaviors**. A task whose paraphrase enumerates many REQ/AC/EDGE/INV (e.g. "implement REQ-003..REQ-009, INV-001..INV-006") is a **kitchen-sink defect** — split it into one task per coherent behavior (e.g. list-filter, get-404, patch-400, create-audit-write, update-snapshot, soft-delete-audit are separate tasks). **Exception**: a verification/GATE task MAY list many IDs by reference only (no paraphrases), since it asserts, not implements.
   - **No stub-then-implement**: NEVER create a controller/service/route file with only stub/empty methods in an early phase to fill later. The file's FIRST task already contains real implementation. (Exception: contract boundaries explicitly listed as stubs in plan.md.) A file appearing in two phases where the earlier task says "stub"/"skeleton" is a defect.
   - **Barrel/index exception**: registering multiple entities created in the SAME phase into barrel/index files MUST be ONE task listing all such files — not one task per file.
   - Soft limit: 3–15 tasks per story phase. If a story would exceed 15, do NOT silently generate more — flag the UJ as too large in the Completion Report and recommend splitting it in spec.md.
   - Each task completable by an LLM in a single pass with no open decisions.

   **Task format (STRICT)**:

   ```text
   - [ ] T012 [P] [US1] Create User model in src/models/user.py (REQ-001: user has unique email, hashed password)
   ```

   - Checkbox `- [ ]` always; sequential ID `T001..TNNN` in execution order.
   - `[P]` OPTIONAL — present only when the parallelism rules hold; absent otherwise.
   - `[USn]` required for story-phase tasks only (maps 1:1 to UJ-00n); no story label in Setup/Expand or Contract phases.
   - Every implementation task names an exact file path from plan.md.
   - A task implementing/wiring an endpoint MUST include its non-2xx semantics from Spec § API Contracts in the paraphrase (e.g. '404 if task never existed, including soft-deleted').
   - Every test/verification task names the `AC-`/`EDGE-`/`INV-` IDs it asserts, each with a ≤15-word paraphrase.
   - ✅ `- [ ] T012 [P] [US1] Create User model in src/models/user.py (REQ-001: user has unique email, hashed password)`
   - ✅ `- [ ] T015 [US1] Integration test in tests/test_auth.py (AC-002: invalid credentials return 401)`
   - ❌ `- [ ] Create User model` (no ID/label/path)
   - ❌ `- [ ] T014 [US1] Implement service` (no path)

   **Also fill**: the Execution Order line (Phase 1 → US1 → STOP & VALIDATE → US2.. → GATE → Contract), each story phase's Goal and Verification lines (from spec § Acceptance Criteria), the **Traceability Matrix**, and the **Files Touched** table at the end of the file.

5. **Validate coverage** before writing the file:
   - Every `AC-NNN` asserted by ≥1 test/verification task; every `EDGE-NNN` and `INV-NNN` handled by ≥1 task.
   - Every NEW/MOD file from plan.md appears in ≥1 task; no task references a path absent from plan.md.
   - No implementation task exceeds the 3-spec-ID atomicity cap (verification/GATE tasks exempt).
   - No two adjacent `[P]`-marked tasks touch the same file path.
   - Every task's prerequisites precede it in document order (no forward references).
   - US1 alone is a viable, independently testable MVP.
   - Fix gaps, re-order, and renumber before finalizing.

## Post-Execution Checks

Run the **`after_tasks`** phase per `.orderspec/memory/hooks-protocol.md`.

## Completion Report

Output the tasks.md path and:

- Total task count; count per phase and per user story.
- Parallelism: number of `[P]`-marked tasks and largest adjacent `[P]` group (0 is acceptable and expected for strictly sequential features).
- Coverage summary: AC/EDGE/INV → tasks (flag any unmapped IDs).
- Atomicity: confirm no implementation task exceeds 3 driving spec IDs (or list offenders).
- Oversized stories flagged (any UJ exceeding the 15-task soft limit).
- Suggested MVP scope (US1) and the STOP & VALIDATE checkpoint.
- If a prior tasks-report.md drove this run: which finding IDs were addressed.

Context for task generation: $ARGUMENTS

## Done When

- [ ] **Upstream gate respected**: guard returned `ok`/`advisory`/`forced` (not `halt`); on `forced`, a `--force` warning was stamped atop the artifact.
- [ ] **Prior gate report consumed (if present)**: if `checklists/tasks-report.md` existed with a ⛔/🔀 verdict, every finding owned by `/order.tasks` was addressed and listed in the Completion Report; upstream-owned findings were routed/STOPped, not silently patched. ✅ PASS or absent → N/A.
- [ ] tasks.md generated in E-M-C order with sequential IDs, file paths, and spec-ID references with paraphrases.
- [ ] **Atomicity holds**: no implementation task exceeds 3 driving spec IDs; no kitchen-sink task; no stub-then-implement.
- [ ] Sequential backbone correct with all `[P]` marks stripped; `[P]` applied only to provably file-disjoint independent adjacent tasks.
- [ ] Coverage validated: all AC/EDGE/INV mapped, all plan.md files touched, no same-file conflict within an adjacent `[P]` group.
- [ ] Traceability Matrix and Files Touched table filled; hooks dispatched or skipped; completion reported.
