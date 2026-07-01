---
orderspec:
  artifact: command_prompt
  command: order.tasks
  phase: tasks
description: Generate a disposable, Expand-Migrate-Contract ordered tasks.md from spec.md (IDs) and plan.md (paths). Sequential phases are the backbone; parallelism is an optional annotation. Coverage is proven by the deterministic traceability tool, never hand-built.
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

`tasks.md` answers **ORDER**: a disposable, mechanically executable checklist that sequences the work as **Expand → Migrate → Contract** (E-M-C).

- **Expand** — additive, non-breaking changes (scaffolding, stubs, additive migrations).
- **Migrate** — behavior implemented story by story, each independently verifiable.
- **Contract** — irreversible cleanup (remove flags, deprecated code, obsolete schema).

Core principles:

- **Disposable & derived**: regenerated freely; overwrite without preserving prior content. You make NO design decisions — every choice already lives in plan.md. You only compose a spec ID with a file path and sequence the result. Invent nothing.
- **Weak-LLM-proof**: each task is executable without re-reading the spec — it carries its file path, the spec IDs that define "done", and a ≤15-word paraphrase of the asserted criteria.
- **Sequential by default**: structure is **Phases → Tasks**. Phases are hard sequential barriers; within a phase, tasks run top-to-bottom and that order MUST be correct on its own. `[P]` parallelism is an OPTIONAL annotation layered on top — never a precondition for correctness.
- **Coverage is proven, not asserted**: you do NOT hand-build, hand-count, or hand-fill any traceability matrix. `traceability.py extract-trace` projects coverage from your task lines and is the SOLE arbiter of completeness. Your job is correct task lines; the tool decides if they cover everything.

## Pre-Execution Checks

Run the **`before_tasks`** phase per `.orderspec/memory/hooks-protocol.md`.

## Upstream Gate Guard

Tasks must not be derived without an approved plan. Resolve the feature, then run
the deterministic guard (it checks that `plan.md` exists and reads its gate verdict):

```bash
FEATURE_DIR="$(jq -r '.feature_directory' .orderspec/feature.json)"
FEATURE="$(basename "$FEATURE_DIR")"

python3 .orderspec/scripts/upstream_gate.py \
  --report        "$FEATURE_DIR/plan-report.md" \
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

Act by exit code / `status`:

- **exit 2, `status: stop`** → **STOP. Produce NO tasks.** No `plan.md` to derive from.
  `--force` does NOT override this. Print the STOP message and end.
- **exit 1, `status: halt`** → **STOP. Produce NO tasks.** The plan has unresolved gate
  findings. Print the HALT message and end.
- **exit 0, `status: forced`** → emit a prominent warning AND stamp at the very top of
  `tasks.md`: `> ⚠ Built over non-PASS plan gate (verdict: {verdict}) via --force` — then proceed.
- **exit 0, `status: advisory`** → emit `reason` as a one-line ⚠ warning, then proceed.
- **exit 0, `status: ok`** → plan approved; proceed silently.

**STOP message (exit 2):**

```text
TASKS_STOPPED: no plan to derive tasks from
There is no plan.md in this feature ({FEATURE_DIR}).
Tasks break down an existing plan — the plan must exist first.
  1. Create the plan:  /order.plan "I am building with <stack>"
  2. (recommended) Verify it: /order.plan-check
  3. Then run /order.tasks
--force does NOT bypass this — there is genuinely nothing to break down.
```

**HALT message (exit 1):**

```text
TASKS_BLOCKED: plan gate not passed
Plan gate verdict: {verdict} (from plan-report.md, dated {date})
The plan has unresolved findings. Resolve them first:
  1. Action each Routing block in plan-report.md via /order.plan "..."
  2. Re-run /order.plan-check until the verdict is ✅ PASS
  3. Then re-run /order.tasks
To derive tasks anyway (NOT recommended), re-run with --force.
```

## Self Gate Report Intake

If a gate report from a previous run exists at `tasks-report.md`, it is the
cited input for refinement (written by the optional `/order.tasks-check` gate; this
command only reads it if present):

```bash
SELF_REPORT="$FEATURE_DIR/tasks-report.md"
test -e "$SELF_REPORT" && echo "SELF_REPORT_PRESENT" || echo "SELF_REPORT_ABSENT"
```

- **SELF_REPORT_ABSENT** → proceed normally; `$ARGUMENTS` is the only refinement signal.
- **SELF_REPORT_PRESENT** → read it and parse the header verdict:
  - **✅ PASS** → previous tasks.md was clean; ignore as fix-source, proceed with `$ARGUMENTS`.
  - **⛔ BLOCK / 🔀 ROUTING REQUIRED** → this is the authoritative defect list. You MUST:
    1. Address **every** finding whose `Run` line targets `/order.tasks` — each becomes a concrete change.
    2. Findings targeting a DIFFERENT command are NOT yours: do not silently compensate. If an
       unresolved upstream finding blocks a fix, STOP and report
       `TASKS_BLOCKED: upstream finding must be resolved first`, listing the IDs and owning command.
    3. Treat `$ARGUMENTS` as ADDITIONAL guidance, never a replacement. If `$ARGUMENTS` is vague
       ("fix the errors" / "исправь ошибки"), the report findings ARE "the errors": action them by ID.

  Record in the Completion Report which finding IDs you addressed.

## Documentation Evidence Check

Before deriving tasks:

1. Check `plan.md` for `## Library Documentation Evidence`.
2. If missing or stale, and Context7 is available, run Context7 lookup for affected libraries.
3. If Context7 is unavailable and no configured skill/user docs exist, create a blocking task or stop with a routing note to `/order.plan`.
4. Tasks that implement library-specific behavior must reference the relevant evidence row from `plan.md`.

## Outline

1. **Setup**: Run `python3 .orderspec/scripts/setup.py tasks --json` from repo root; parse
   FEATURE_DIR, TASKS_TEMPLATE, AVAILABLE_DOCS (absolute paths). For single quotes in args
   use `'I'\''m Groot'` or double quotes.

2. **Load inputs** from FEATURE_DIR:
   - **Required**: `spec.md` (UJ priorities, AC, REQ, INV, EDGE, data model, contracts),
     `plan.md` (file mapping, stack, NEW/MOD files, test/build commands).
   - **Optional**: `research.md`; **if exists**: `.orderspec/memory/constitution.md`.

3. **Read the coverage contract from the tool — never from memory.** The IDs you must
   cover live in `mechanisms.tsv`, not in your recollection of the spec:

   ```bash
   python3 .orderspec/scripts/traceability.py get "$FEATURE" mechanisms
   ```

   This emits `spec_id  coverage_kind  mechanism  primary_files  test_type`. Obey `coverage_kind`
   exactly (the tool rejects violations):

   - **`direct`** → MUST be referenced by ≥1 task line. Uncovered → `extract-trace` fails.
   - **`documented`** → MUST NOT appear in any task line (plan.md row only). Tasking it → fail.
   - **`delegated:<ID>`** → do NOT task this ID; cover `<ID>` (its delegate) instead.

   Each mechanism BINDS the task that FIRST creates the affected function — fold it into that
   task's paraphrase. NEVER schedule a later task that retrofits a mechanism into existing code.

   **A direct ref means "this mechanism is realized OR exercised in THIS task's `path`" — not
   "this ID needed a home to satisfy coverage".** A direct mechanism whose `primary_files` is an
   implementation file (model/service/controller/route) belongs on the IMPLEMENTATION task that
   writes that file — NOT on a verification/GATE/test task. Do NOT move a direct ID onto an
   unrelated task merely to clear an "uncovered" rejection: that is ID-parking, and it makes
   `traceability.md` lie about where the behavior lives. If a direct ID has nowhere to go within
   the 3-ref cap, that is the signal to add a task for its primary_files, not to park it
   elsewhere (see Granularity: god-file split). This is now MACHINE-ENFORCED: extract-trace
   rejects (rc=3) any ref whose mechanism's primary_files does not contain that task's path,
   so ID-parking fails the build rather than silently corrupting traceability.md.

4. **Build the sequencing inventory** (this is ordering, not coverage bookkeeping — coverage
   is the tool's job in step 6):
   - List `UJ-NNN` by priority → user story phases (US1 ↔ UJ-001).
   - Place each `AC/EDGE/INV` under a UJ (or Setup/Contract if cross-cutting).
   - From plan.md, list every NEW/MOD file; assign each to the phase that first touches it.
   - Note the project's test command from plan.md (used verbatim in verification/GATE tasks).

5. **Generate tasks.md** from TASKS_TEMPLATE (fallback `.orderspec/templates/tasks-template.md`).
   Template samples are placeholders — replace entirely, renumber T001..TNNN sequentially.

   **Phase mapping (E-M-C)** — include items ONLY if applicable; never invent:
   - **Phase 1 — Setup & Expand** (all changes non-breaking):
     - *if persistent storage*: additive migrations with rollback scripts (Spec § Data Model).
     - *if interfaces (API/CLI/UI)*: contract/route/DTO/command stubs (Spec § Contracts).
     - passive model entities; feature flags only if plan.md defines them.
   - **Phase 2+ — Migrate**: US1 (P1, MVP) first, then one phase per remaining UJ in priority order.
     Within each story phase:
     1. Test tasks first (assert that story's `AC-NNN`; MUST fail before implementation).
     2. Data layer → service logic → wiring to contracts.
     3. `EDGE-NNN` for this story.
     4. Verification task: run the test command; assert the story's AC pass, `INV-NNN` hold, no regressions.
     End with a **Checkpoint** line: story independently functional and backwards-compatible.
     Omit test tasks only if the user or constitution explicitly opts out.
   - **Final Phase — Contract**: start with a GATE task (run the test command verbatim; verify all
     `AC-*` pass, `INV-*` hold, `NFR-*` met; STOP on failure — contraction is irreversible). Then
     remove flags, delete deprecated code/routes, drop obsolete columns, lint/format, update docs.
     **Greenfield rule**: if nothing pre-exists to deprecate, Contract only removes scaffolding/flags.

   **Task format (STRICT — pipe-delimited, machine-parsed).** extract-trace splits each task
   line on " | " (space-pipe-space). A line with fewer than 2 " | " separators is treated as a
   non-task line (infra prose) and contributes NO coverage. Emit EXACTLY:

   [```]text
   - [ ] T012 [P] [US1] | src/models/user.py | REQ-001,AC-002 | user has unique email, hashed password
   [```]

   1. "- [ ] T012 [P] [US1]" — checkbox + sequential ID + optional [P] + optional [USn].
   2. file path — one exact path from plan.md. No spaces. Raw path only — do NOT wrap it in
      backticks or any markdown. extract-trace matches the literal path; backticks make the
      field not match plan.md and silently drop the line's coverage.
   3. refs — OPTIONAL. Comma-separated spec IDs, NO SPACES (REQ-001,AC-002, never
      REQ-001, AC-002). An infrastructure task (barrel/index registration, route wiring, test
      fixtures, GATE/verification scaffolding) carries NO refs — write
      "... | path |  | gloss" (empty field 3) or omit field 3. This is LEGAL and contributes
      no coverage by design. The contract is "every DIRECT mechanism is covered by >=1 task" — it
      is NOT "every task has a ref". NEVER invent a ref to give a task a home.
   4. gloss — <=15-word paraphrase. Free text, never grepped (so prose like "see AC-999" is safe).

   Constraints the tool ENFORCES (any violation fails extract-trace with rc=3, file untouched):
   - Subset binding (Variant C): a DECLARED ref MUST be a direct mechanism whose
     primary_files (in mechanisms.tsv) CONTAINS this task's exact path. A ref attached to a
     path that does not realize/exercise it (e.g. REQ-001 on src/models/index.js when REQ-001's
     primary_files is task.model.js) is a filler/mis-attribution and is REJECTED. This makes
     ID-parking structurally impossible — you cannot satisfy coverage by relocating a ref onto a
     barrel/verify/GATE line.
   - documented IDs MUST NOT appear as refs (plan.md row only). Tasking one -> rejected.
   - delegated:<ID> IDs MUST NOT appear as refs — task <ID> (the delegate) instead -> rejected.
   - Atomicity cap: at most 3 spec IDs in field 3. 4+ refs = kitchen-sink defect, REJECTED.
     No GATE exemption — assert extra IDs in the gloss or split lines.
   - No duplicate ref within a task (REQ-001,REQ-001 rejected). No spaces in refs or path.

   Examples:
   - OK:  - [ ] T012 [P] [US1] | src/models/user.py | REQ-001 | user has unique email, hashed password
   - OK:  - [ ] T015 [US1] | tests/test_auth.py | AC-002 | invalid credentials return 401
   - OK:  - [ ] T003 | src/models/index.js |  | register new model in barrel  (empty refs, LEGAL infra task)
   - BAD: - [ ] Create User model  (no ID/path/refs; not a task line)
   - BAD: - [ ] T012 [US1] | src/a.js | REQ-001, AC-002 | ...  (space in refs -> rejected)
   - BAD: - [ ] T020 [US1] | src/x.js | REQ-003,REQ-004,REQ-005,REQ-006 | does everything  (4 refs -> rejected)
   - BAD: - [ ] T003 | src/models/index.js | REQ-001 | barrel  (REQ-001's primary_files is the
     model file, NOT index.js -> filler/mis-attributed ref -> rejected rc=3; leave refs EMPTY instead)

   `[USn]` is required on story-phase tasks (1:1 with UJ-00n), omitted in Setup/Expand and Contract.
   For endpoint tasks, fold non-2xx semantics from Spec § API Contracts into the gloss
   (e.g. `404 if task never existed including soft-deleted`).

   **Prose to fill by hand** (NOT machine state): the Execution Order line
   (Phase 1 → US1 → STOP & VALIDATE → US2.. → GATE → Contract), and each story phase's Goal and
   Verification lines (from Spec § Acceptance Criteria).

   > Do **NOT** hand-write a Traceability Matrix or a Files Touched table in `tasks.md`. Those are
   > derived: `extract-trace` projects coverage into `traceability.tsv`, and `render` produces the
   > human-readable mirror. A hand-built matrix is exactly the drift this system removes — if the
   > template contains such placeholder sections, leave them empty or delete them.

   **Granularity rules (semantic — yours; the tool only enforces the 3-ref cap)**:
   - **One task = one file** (or one atomic, independently verifiable change). More than one file → split.
   - **No stub-then-implement**: never create a file with empty/stub methods early to fill later; its
     FIRST task carries real implementation. (Exception: contract boundaries plan.md explicitly marks
     as stubs.) A file appearing in two phases where the earlier says "stub"/"skeleton" is a defect.
   - **God-file split (resolves cap-vs-coverage pressure)**: when one `primary_files` carries MORE
     than 3 direct mechanisms (a "god file" like a central service), do NOT cram them into one task
     and do NOT park the overflow on verify/GATE tasks. Split into several IMPLEMENTATION tasks on the
     SAME path, each grouping ≤3 cohesive mechanisms by behavior (e.g. one task for create+list+get,
     another for update+soft-delete, another for atomic-audit+error-wrapping). These same-file tasks
     are sequential (NOT `[P]` — they share a file) and each carries the direct IDs it actually
     implements. This keeps every direct ID on the task that realizes it AND stays under the cap.
   - **Barrel/index exception**: registering multiple same-phase entities into barrel/index files is
     ONE task listing all of them — not one per file.
   - Soft limit 3–15 tasks per story phase. If a story exceeds 15, do NOT silently continue — flag the
     UJ as too large in the Completion Report and recommend splitting it in spec.md.

6. **Prove coverage with the tool — do not eyeball it.** After writing `tasks.md`:

   ```bash
   python3 .orderspec/scripts/traceability.py extract-trace "$FEATURE"
   rc=$?
   ```

   - **rc = 0** → coverage is closed deterministically (every direct covered, no documented tasked,
     every delegated satisfied, no cap/duplicate violation). `traceability.tsv` written atomically.
     Then render the human mirror:

     ```bash
     python3 .orderspec/scripts/traceability.py render "$FEATURE"
     ```

   - **rc ≠ 0** → read the tool's stderr; it names the exact defect, e.g.:
     - `coverage: direct INV-001 uncovered` → add `INV-001` to the task whose `path` equals its `primary_files` (the task that realizes/exercises it) — NOT to a convenient verify/GATE task just to silence the rejection. If that implementation task is already at the 3-ref cap, split it (see god-file rule) rather than parking the ID on an unrelated line.
     - `extract-trace`: ref REQ-001 on T003 not in its `primary_files` (path=...) -> you parked a ref on a path that does not realize it. Either (a) move that ref to the task whose path IS its `primary_files`, or (b) if T003 is genuine infra (barrel/wiring/fixture), leave its refs EMPTY. Do NOT swap in a different ID to keep the line "covered".
     - `coverage: documented NFR-001 must NOT have a task` → remove `NFR-001` from its task line.
     - `extract-trace: task T020 drives 4 spec ids (cap 3)` → split that task.
     - `extract-trace: spaces in refs` / `bad ref id` / `duplicate ref` → fix that line's field 3.

     Fix the task lines and re-run `extract-trace`; iterate to rc = 0. **Never** hand-edit
     `traceability.tsv` — it is rebuilt every run and your edit will vanish. Correct task lines are
     the only way to pass.

   **Placement checks (yours, not the tool's)**: every NEW/MOD file from plan.md appears in ≥1 task;
   no task references a path absent from plan.md; no two adjacent `[P]` tasks touch the same file;
   each task's prerequisites precede it; US1 alone is a viable, independently testable MVP. If you
   change any task line, re-run `extract-trace` (then `render`).

## Post-Execution Checks

Run the **`after_tasks`** phase per `.orderspec/memory/hooks-protocol.md`.

## Completion Report

Output the tasks.md path and:

- Total task count; per phase and per user story.
- Parallelism: number of `[P]` tasks and largest adjacent `[P]` group (0 is fine and expected
  for strictly sequential features).
- **`extract-trace` result**: final exit code (MUST be 0) and, if iterations were needed, a one-line
  note of what was fixed. Cite the tool's success — do not paste a coverage matrix.
- **`render` result**: confirm `traceability.md` was written.
- Oversized stories flagged (any UJ over the 15-task soft limit).
- Suggested MVP scope (US1) and the STOP & VALIDATE checkpoint.
- If a prior tasks-report.md drove this run: which finding IDs were addressed.

Context for task generation: $ARGUMENTS

## Done When

- [ ] **Upstream gate respected**: guard returned `ok`/`advisory`/`forced` (not `halt`/`stop`); on
      `forced`, a `--force` warning was stamped atop the artifact.
- [ ] **Prior gate report consumed (if present)**: a ⛔/🔀 `tasks-report.md` had every `/order.tasks`-owned
      finding addressed and listed; upstream-owned findings were routed/STOPped, not silently patched.
      ✅ PASS or absent → N/A.
- [ ] tasks.md generated in E-M-C order with sequential IDs and pipe-delimited task lines
      (T### [P] [US] | path | refs? | gloss); refs are OPTIONAL (infra tasks carry empty refs),
      comma-joined with NO spaces when present, each declared ref's mechanism lists this task's path
      in primary_files (no filler/parked refs), and the path field a raw plan.md path with NO backticks.
- [ ] **Coverage proven by tool**: `extract-trace "$FEATURE"` exited 0 (no uncovered direct, no tasked
      documented, no dangling delegated, no cap/duplicate violation).
- [ ] **Human mirror rendered**: `render "$FEATURE"` wrote `traceability.md`.
- [ ] **No hand-built matrix**: no Traceability Matrix or Files Touched table authored by hand in tasks.md.
- [ ] Sequential backbone correct with all `[P]` marks stripped; `[P]` only on provably file-disjoint,
      independent, adjacent tasks; no stub-then-implement.
- [ ] Placement validated: all plan.md files touched, no path outside plan.md, no same-file conflict
      within an adjacent `[P]` group; hooks dispatched or skipped; completion reported.
