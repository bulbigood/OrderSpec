---
orderspec:
  artifact: command_prompt
  command: order.tasks
  phase: tasks
description: Generate a disposable, Expand-Migrate-Contract ordered tasks.md from spec.md (IDs) and plan.md (paths). Sequential phases are the backbone; parallelism is an optional annotation. Coverage is proven by the deterministic traceability tool, never hand-built.
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

- **Disposable & derived**: regenerated freely; overwrite without preserving prior content. You make NO design decisions — every choice already lives in `plan.md`. You only compose a spec ID with a file path and sequence the result. Invent nothing.
- **Weak-LLM-proof**: each task is executable without re-reading the spec — it carries its file path and spec IDs, while `/order.code` resolves those IDs into exact contract excerpts before execution.
- **Sequential by default**: structure is **Phases → Tasks**. Phases are hard sequential barriers; within a phase, tasks run top-to-bottom and that order MUST be correct on its own. `[P]` parallelism is an OPTIONAL annotation layered on top — never a precondition for correctness.
- **Coverage is proven, not asserted**: you do NOT hand-build, hand-count, or hand-fill any traceability matrix. `traceability.py extract-trace` projects coverage from your task lines and is the SOLE arbiter of completeness. Your job is correct task lines; the tool decides if they cover everything.
- **Environment actions are explicit**: preserve `plan.md` runtime prerequisites, readiness checks, recovery boundaries, and fallbacks. Never encode service startup, package installation, data reset, or another operator side effect as an implicit task.

---

## Global Execution Rules

1.  **Script Authority:** Framework scripts are deterministic. You MUST NOT second-guess, silently override, or manually repair successful script output. If a script fails, read the error and fix your input data.
2.  **Shell Variable Persistence:** Tool shell sessions may not preserve variables. You MUST rehydrate variables at the start of every new shell block by running:
    ```bash
    eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
    ```
    Do not assume variables like `$FEATURE_DIR` persist between separate shell calls.
3.  **Scope Lock:** You are sequencing `plan.md` into tasks. Do not invent new requirements, endpoints, fields, or permissions. If tasking strictly requires a new externally visible behavior not present in `spec.md`, STOP and report `TASKS_BLOCKED: contract decision required`.

---

## Execution Flow

Follow these steps in exact order. Do not skip steps.

### Step 1: Command Context Resolution

Resolve and load all required context files.

```bash
python3 .orderspec/framework/scripts/command_context.py resolve order.tasks --json
```

1.  If `ok` is `false` or `missing_required` is non-empty, STOP and report the missing context.
2.  Read every file returned in `to_read`, in returned order.
3.  Interpret each file according to its `usage` field (`apply`, `constrain`, `parse`, `inspect`, `reference`).

If required project contracts (`constitution.md`, `stack.md`, `architecture.md`, `conventions.md`) are missing, STOP and tell the user to run `/order.bootstrap` first.

### Step 2: Path Resolution

Resolve active feature paths.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
```

If this fails because no active feature directory can be resolved, STOP:
```text
TASKS_STOPPED: no active feature
  1. Create/select a feature with /order.spec
  2. Then run /order.plan
  3. Then run /order.tasks
```

### Step 3: Mode Detection

Determine mode before writing any file. State the mode in chat.

1.  **Regenerate** — active `plan.md` exists, and `tasks.md` needs to be recreated.
2.  **Refine** — active `tasks.md` exists, and `$ARGUMENTS` requests specific changes.
3.  **Refresh** — `tasks.md` already exists and `$ARGUMENTS` is empty → STOP:

```text
TASKS_STOPPED: tasks.md already exists
  - To verify the current tasks: /order.tasks-check
  - To regenerate from scratch: /order.tasks --force
  - To apply specific changes: /order.tasks "describe the change"
```

### Step 4: Upstream Gate Guard

Check the upstream plan gate.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

FORCE_FLAG=""
case "$ARGUMENTS" in
  *"--force"*) FORCE_FLAG="--force" ;;
esac

python3 .orderspec/framework/scripts/upstream_gate.py \
  --report        "$FEATURE_DIR/plan-report.md" \
  --artifact      "$FEATURE_DIR/plan.md" \
  --upstream-name "plan.md" \
  --this          "/order.tasks" \
  --build         "/order.plan" \
  --fix           "/order.plan" \
  --recheck       "/order.plan-check" \
  $FORCE_FLAG
```

-   **exit 2 (stop)** or **exit 1 (halt)** → STOP. Do not produce tasks.
-   **exit 64 (error)** → STOP. Report: `TASKS_STOPPED: upstream gate invocation error (empty shell variables — re-run setup.py paths)`. Do not produce tasks.
-   **exit 0 (forced)** → Proceed, but insert this warning at the top of `tasks.md`:
    `> ⚠ Built over non-PASS plan gate (verdict: {verdict}) via --force`
-   **exit 0 (advisory)** → Proceed, but warn the user in chat: "Upstream plan gate report is stale or absent. It is recommended to re-run `/order.plan-check` before relying on these tasks."
-   **exit 0 (ok)** → Proceed.

**STOP message (exit 2):**

```text
TASKS_STOPPED: no plan to derive tasks from
There is no plan.md in this feature ($FEATURE_DIR).
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
  1. Report each Routing block in plan-report.md as human/orchestrator work for `/order.plan "..."`.
  2. Stop. Human or orchestrator runs `/order.plan`, then `/order.plan-check` until the verdict is ✅ PASS.
  3. Human or orchestrator starts `/order.tasks` again.
To derive tasks anyway (NOT recommended), re-run with --force.
```

### Step 5: Self Gate Report Intake

Check for a prior `/order.tasks-check` report.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
SELF_REPORT="$FEATURE_DIR/tasks-report.md"
test -e "$SELF_REPORT" && echo "SELF_REPORT_PRESENT" || echo "SELF_REPORT_ABSENT"
```

-   **ABSENT** → Proceed.
-   **PRESENT (✅ PASS)** → Ignore report; proceed with `$ARGUMENTS`.
-   **PRESENT (⛔ BLOCK / 🔀 ROUTING)** → This is your fix-list. Address every finding targeting `/order.tasks`. Route findings for other commands. Treat `$ARGUMENTS` as additional guidance, not a replacement.

### Step 6: Setup Tasks Artifact

Initialize the tasks file from the template.

```bash
python3 .orderspec/framework/scripts/setup.py tasks --json --refresh-template > /dev/null
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
```

### Step 7: Load Inputs

Read the following inputs from `$FEATURE_DIR`:

1.  **`spec.md`** — UJ priorities, AC, REQ, INV, EDGE, data model, contracts.
2.  **`plan.md`** — file mapping, stack, NEW/MOD files, test/build commands.
    Read `Environment Readiness` as the source for runtime prerequisites. Do not
    replace its checks or recovery options with guesses.
3.  **Coverage contract from `mechanisms.tsv`** — the IDs you must cover live here, not in your recollection of the spec:

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" get mechanisms
```

This emits `spec_id  coverage_kind  mechanism  primary_files  test_type`. Obey `coverage_kind` exactly (the tool rejects violations):

- **`direct`** → MUST be referenced by ≥1 task line. Uncovered → `extract-trace` fails.
- **`documented`** → MUST NOT appear in any task line (plan.md row only). Tasking it → fail.
- **`delegated:<ID>`** → do NOT task this ID; cover `<ID>` (its delegate) instead.

Each mechanism BINDS the task that FIRST creates the affected function — fold it into that task's paraphrase. NEVER schedule a later task that retrofits a mechanism into existing code.

**A direct ref means "this mechanism is realized OR exercised in THIS task's `path`" — not "this ID needed a home to satisfy coverage".** A direct mechanism whose `primary_files` is an implementation file (model/service/controller/route) belongs on the IMPLEMENTATION task that writes that file — NOT on a verification/GATE/test task. Do NOT move a direct ID onto an unrelated task merely to clear an "uncovered" rejection: that is ID-parking, and it makes `traceability.md` lie about where the behavior lives. If a direct ID has nowhere to go within the 3-ref cap, that is the signal to add a task for its primary_files, not to park it elsewhere (see Granularity: god-file split). This is now MACHINE-ENFORCED: `extract-trace` rejects (rc=3) any ref whose mechanism's `primary_files` does not contain that task's path, so ID-parking fails the build rather than silently corrupting `traceability.md`.

### Test Topology Binding

Treat each direct mechanism's test_type as a binding, not a hint:

- unit → create a unit-test path in the plan manifest and a test-writing task for that mechanism;
- integration → create an integration-test path and a test-writing task for the endpoint/flow;
- documented → do not create a test task unless a separate direct mechanism requires it;
- delegated → task the delegate's declared test topology, not the delegated row.

A generic GATE task never satisfies a unit or integration mechanism. If the
plan declares a unit mechanism but has no unit-test path, stop and route the
defect to /order.plan; do not relabel the mechanism as integration to make
coverage pass.

### Step 7.5: Get Task Suggestions (Deterministic Pre-flight)

Get deterministic task line skeletons from the tool. This reduces iterations in Step 10 by pre-grouping direct mechanisms by `primary_files` and pre-splitting god-files (>3 mechanisms per path).

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" suggest-tasks --json
```

The JSON output contains `suggestions` — each with:
- `path` — a file from `plan.md` pathmanifest
- `refs` — ≤3 direct spec IDs whose `primary_files` equals this `path`
- `gloss_hint` — mechanism summaries for gloss inspiration
- `needs_split` — `true` if the path has >3 direct mechanisms (god-file); multiple sequential tasks on the same path are expected

Use these as building blocks for Step 9 (Write `tasks.md`):
1. Sort suggestions into phases (Expand → Migrate → Contract).
2. Add `[P]` and `[USn]` markers based on file-disjointness and user story mapping.
3. Refine `gloss_hint` into a ≤15-word gloss.
4. Add a GATE task at the end (path = test file from manifest, refs = empty, gloss = "GATE: run [test command]...").
5. Add any missing infra tasks (barrels, fixtures) that the tool didn't suggest.

### Step 8: Build Sequencing Inventory

This is ordering, not coverage bookkeeping — coverage is the tool's job in Step 10.

1.  List `UJ-NNN` by priority → user story phases (US1 ↔ UJ-001).
2.  Place each `AC/EDGE/INV` under a UJ (or Setup/Contract if cross-cutting).
3.  Place each buildable Success Criterion (load, security, performance, or other executable evidence) under its owning UJ or cross-cutting phase; post-launch/business KPI criteria need no task.
4.  From `plan.md`, list every NEW/MOD file; assign each to the phase that first touches it.
5.  Note the project's test command from `plan.md` (used verbatim in verification/GATE tasks).
6.  Carry each required environment readiness check into the relevant phase
    verification or implementation preflight. Add a task only when readiness
    requires a repository artifact or code/config change listed in the plan.

### Step 9: Write `tasks.md`

Rewrite `$TASKS_FILE` (which was initialized from `tasks-template.md` in Step 6).

**Phase mapping (E-M-C)** — include items ONLY if applicable; never invent:

- **Phase 1 — Setup & Expand** (all changes non-breaking):
  - *if persistent storage*: additive migrations with rollback scripts (Spec § Data Model).
  - *if interfaces (API/CLI/UI)*: contract/route/DTO/command stubs (Spec § Contracts).
  - passive model entities; feature flags only if `plan.md` defines them.
  - environment setup only when `plan.md` declares a repository-owned artifact
    such as a compose file, fixture, or configuration. Operator recovery actions
    remain approval-gated implementation preflight, not hidden tasks.
- **Phase 2+ — Migrate**: US1 (P1, MVP) first, then one phase per remaining UJ in priority order.
  Within each story phase:
  1. Test-writing tasks first (carry that story's `AC-NNN` refs; MUST fail before implementation). Split into multiple sequential test tasks on the same file if ACs exceed the 3-ref cap (see test-file split rule).
  2. Data layer → service logic → wiring to contracts.
  3. `EDGE-NNN` for this story.
  4. Emit a **Verification** prose line with the exact permitted test command and asserted AC/INV IDs, then a **Checkpoint** prose line: story independently functional and backwards-compatible. Neither line is a task; `/order.code` executes the declared Verification command at the phase barrier.
  Omit test tasks only if the user or constitution explicitly opts out.
- **Final Phase — Contract**: start with a GATE task (run the test command verbatim; verify all `AC-*` pass, `INV-*` hold, `NFR-*` met; STOP on failure — contraction is irreversible). Then remove flags, delete deprecated code/routes, drop obsolete columns, lint/format, update docs.
  **Greenfield rule**: if nothing pre-exists to deprecate, Contract only removes scaffolding/flags.
  **GATE task path**: the GATE task's `path` field MUST be a test file path listed in `plan.md` pathmanifest (e.g. `tests/integration/task.test.js`). The test command (e.g. `npm test`) goes in the gloss. This keeps `path` machine-valid against the manifest (check M8) without special-casing commands as paths.

**Task format (STRICT — pipe-delimited, machine-parsed).** `extract-trace` splits each task line on " | " (space-pipe-space). A line with fewer than 2 " | " separators is treated as a non-task line (infra prose) and contributes NO coverage. Emit EXACTLY:

```text
- [ ] T012 [P] [US1] | src/models/user.py | REQ-001,AC-002 | user has unique email, hashed password
```

1. "- [ ] T012 [P] [US1]" — checkbox + sequential ID + optional [P] + optional [USn].
2. file path — one exact path from `plan.md`. No spaces. Raw path only — do NOT wrap it in backticks or any markdown. `extract-trace` matches the literal path; backticks make the field not match `plan.md` and silently drop the line's coverage.
3. refs — OPTIONAL. Comma-separated spec IDs, NO SPACES (`REQ-001,AC-002`, never `REQ-001, AC-002`). An infrastructure task (barrel/index registration, route wiring, test fixtures, GATE/verification scaffolding) carries NO refs — write `... | path |  | gloss` (empty field 3) or omit field 3. This is LEGAL and contributes no coverage by design. The contract is "every DIRECT mechanism is covered by ≥1 task" — it is NOT "every task has a ref". NEVER invent a ref to give a task a home.
  **AC refs belong on test-WRITING tasks** (the task that writes the test code exercising that AC), NOT on verification/GATE tasks. Verification/GATE tasks carry EMPTY refs and list asserted AC/INV IDs in the gloss. Coverage of an AC is proven by the test-writing task that creates its test, not by the verification task that runs the suite.
  A story-phase task may also have empty refs when no direct mechanism has this task's exact path in `primary_files` (for example, unit evidence tasks, controller support tasks, or wiring tasks). Do not invent or park a ref only to satisfy the `[USn]` marker; ref presence is required only on story tasks that own a direct mechanism path.
4. gloss — ≤15-word paraphrase. Free text, never grepped (so prose like "see AC-999" is safe).

**Constraints the tool ENFORCES** (any violation fails `extract-trace` with rc=3, file untouched):

- `primary_files` in `mechanisms.tsv` is a single path per row (TSV, same format as `spec-ids.tsv`). A declared ref is valid iff the ref's `primary_files` equals this task's exact `path`.
- Subset binding: a DECLARED ref MUST be a direct mechanism whose `primary_files` (in `mechanisms.tsv`) CONTAINS this task's exact path. A ref attached to a path that does not realize/exercise it (e.g. `REQ-001` on `src/models/index.js` when `REQ-001`'s `primary_files` is `task.model.js`) is a filler/mis-attribution and is REJECTED. This makes ID-parking structurally impossible — you cannot satisfy coverage by relocating a ref onto a barrel/verify/GATE line.
- `documented` IDs MUST NOT appear as refs (`plan.md` row only). Tasking one → rejected.
- `delegated:<ID>` IDs MUST NOT appear as refs — task `<ID>` (the delegate) instead → rejected.
- Atomicity cap: at most 3 spec IDs in field 3. 4+ refs = kitchen-sink defect, REJECTED. No GATE exemption — assert extra IDs in the gloss or split lines.
- No duplicate ref within a task (`REQ-001,REQ-001` rejected). No spaces in refs or path.

**Examples:**

- OK:  `- [ ] T012 [P] [US1] | src/models/user.py | REQ-001 | user has unique email, hashed password`
- OK:  `- [ ] T015 [US1] | tests/test_auth.py | AC-002 | invalid credentials return 401`
- OK:  `- [ ] T003 | src/models/index.js |  | register new model in barrel` (empty refs, LEGAL infra task)
- BAD: `- [ ] Create User model` (no ID/path/refs; not a task line)
- BAD: `- [ ] T012 [US1] | src/a.js | REQ-001, AC-002 | ...` (space in refs → rejected)
- BAD: `- [ ] T020 [US1] | src/x.js | REQ-003,REQ-004,REQ-005,REQ-006 | does everything` (4 refs → rejected)
- BAD: `- [ ] T003 | src/models/index.js | REQ-001 | barrel` (`REQ-001`'s `primary_files` is the model file, NOT `index.js` → filler/mis-attributed ref → rejected rc=3; leave refs EMPTY instead)

`[USn]` is required on story-phase tasks (1:1 with `UJ-00n`), including valid no-ref support tasks; omitted in Setup/Expand and Contract. A no-ref story task is valid when its exact path is not a direct mechanism's `primary_files` path.
For endpoint tasks, fold non-2xx semantics from Spec § API Contracts into the gloss (e.g. `404 if task never existed including soft-deleted`).

### Task Context Block

After composing all task lines, replace the template's `task-context` block
with exactly one machine-readable JSON block:

````text
```task-context
{
  "version": 1,
  "tasks": {
    "T001": {"read": ["src/existing.py", "src/shared.py"], "target_state": "mod"}
  }
}
```
````

This block is the sole source of truth for task worker file context. Build one
entry for every task ID. For each task, `target_state` MUST copy the status of
its path from `plan.md` (`new` for `[NEW]`, `mod` for `[MOD]`, `del` for
`[DEL]`). `read` MUST contain the exact existing repo-relative files the worker
needs to inspect, in read order, including a `mod` or `del` task write target.
A `[NEW]` write target is not included until it exists. Do not list
directories, globs, or broad repository scans.
Do not include Markdown unless it is the task's own write target. Derive the
list from the task objective, `plan.md`, and targeted source inspection. An
exact `[NEW]` path written by an earlier task may be listed as a dependency even
before it exists on disk; sequential execution guarantees it is available when
the later task runs. If a required dependency cannot be stated as an exact
file, route the defect to `/order.plan`; do not leave worker context implicit.

`task_context.py` owns parsing, validation, file-existence checks, and resolver
output. `/order.code` consumes its output verbatim. Do not hand-author a
second whitelist in a prompt, packet, or coordinator note.

`task_contract_context.py` owns deterministic resolution of task refs to exact
ID blocks from `spec.md`, relevant `mechanisms.tsv` rows, and the current phase
Goal/Verification context. `/order.code` MUST run it for every task and pass
its output verbatim to the worker. Task glosses remain short execution hints;
they are not substitutes for the resolved contract excerpts.

**Prose to fill by hand** (NOT machine state): the Execution Order line (Phase 1 → US1 → STOP & VALIDATE → US2.. → GATE → Contract), and each story phase's Goal and Verification lines (from Spec § Acceptance Criteria).

> Do **NOT** hand-write a Traceability Matrix or a Files Touched table in `tasks.md`. Those are derived: `extract-trace` projects coverage into `traceability.tsv`, and `render` produces the human-readable mirror. A hand-built matrix is exactly the drift this system removes — if the template contains such placeholder sections, leave them empty or delete them.

**Granularity rules (semantic — yours; the tool only enforces the 3-ref cap):**

- **One task = one file** (or one atomic, independently verifiable change). More than one file → split.
- **No stub-then-implement**: never create a file with empty/stub methods early to fill later; its FIRST task carries real implementation. (Exception: contract boundaries `plan.md` explicitly marks as stubs.) A file appearing in two phases where the earlier says "stub"/"skeleton" is a defect.
- **God-file split (resolves cap-vs-coverage pressure)**: when one `primary_files` carries MORE than 3 direct mechanisms (a "god file" like a central service), do NOT cram them into one task and do NOT park the overflow on verify/GATE tasks. Split into several IMPLEMENTATION tasks on the SAME path, each grouping ≤3 cohesive mechanisms by behavior (e.g. one task for create+list+get, another for update+soft-delete, another for atomic-audit+error-wrapping). These same-file tasks are sequential (NOT `[P]` — they share a file) and each carries the direct IDs it actually implements. This keeps every direct ID on the task that realizes it AND stays under the cap.
- **Test-file split (mirror of god-file split, for test files)**: when one test `primary_files` carries MORE than 3 direct ACs, do NOT cram them into one task. Split into several TEST-WRITING tasks on the SAME test path, each carrying ≤3 ACs grouped by behavior (e.g. one task for create+list tests, another for update tests, another for soft-delete tests). These same-file test tasks are sequential (NOT `[P]` — they share a file) and each carries the AC IDs it actually exercises.
- **Barrel/index exception**: registering multiple same-phase entities into barrel/index files is ONE task listing all of them — not one per file.
- **Cross-cutting test tasks**: tests spanning multiple UJs (e.g. shared unauthenticated-access tests) omit the `[USn]` marker. Place them in the phase of their primary UJ or in the Final Phase before GATE. They carry AC refs normally (≤3 per line). A cross-cutting AC (e.g. AC-018 covering both GET and PATCH 404) is covered by placing its ref on ONE test-writing task whose path equals the AC's `primary_files` — no duplication needed; double coverage is not penalized.
- Task IDs MAY have gaps (e.g. T005, T010, T015) — gaps are legal and reduce churn when inserting tasks. Only duplicate IDs are rejected.
- Soft limit 3–15 tasks per story phase. If a story exceeds 15, do NOT silently continue — flag the UJ as too large in the Completion Report and recommend splitting it in `spec.md`.

### Step 10: Prove Coverage

After writing `tasks.md`, prove coverage with the tool — do not eyeball it.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" extract-trace
```

- **exit 0** → coverage is closed deterministically (every direct covered, no documented tasked, every delegated satisfied, no cap/duplicate violation). `traceability.tsv` written atomically.

- **exit ≠ 0** → read the tool's stderr; it names the exact defect, e.g.:
  - `coverage: direct INV-001 uncovered` → add `INV-001` to the task whose `path` equals its `primary_files` (the task that realizes/exercises it) — NOT to a convenient verify/GATE task just to silence the rejection. If that implementation task is already at the 3-ref cap, split it (see god-file rule) rather than parking the ID on an unrelated line.
  - `extract-trace`: ref REQ-001 on T003 not in its `primary_files` (path=...) → you parked a ref on a path that does not realize it. Either (a) move that ref to the task whose path IS its `primary_files`, or (b) if T003 is genuine infra (barrel/wiring/fixture), leave its refs EMPTY. Do NOT swap in a different ID to keep the line "covered".
  - `coverage: documented NFR-001 must NOT have a task` → remove `NFR-001` from its task line.
  - `extract-trace: task T020 drives 4 spec ids (cap 3)` → split that task.
  - `extract-trace: spaces in refs` / `bad ref id` / `duplicate ref` → fix that line's field 3.

  Fix the task lines and re-run `extract-trace`; iterate to exit 0. **Never** hand-edit `traceability.tsv` — it is rebuilt every run and your edit will vanish. Correct task lines are the only way to pass.

**Placement checks (yours, not the tool's):**
- Every NEW/MOD file from `plan.md` appears in ≥1 task.
- No task references a path absent from `plan.md`.
- No two adjacent `[P]` tasks touch the same file.
- Each task's prerequisites precede it.
- US1 alone is a viable, independently testable MVP.

If you change any task line, re-run `extract-trace` (then `render`).

### Step 11: Validate Tasks

Run mechanical self-checks.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" check-mechanisms
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" validate --stage tasks --json
```

Validate task worker context as a separate deterministic input gate:

```bash
python3 .orderspec/framework/scripts/task_context.py validate \
  --feature-dir "$FEATURE_DIR" --json
```

```bash
python3 .orderspec/framework/scripts/task_contract_context.py validate \
  --feature-dir "$FEATURE_DIR" --json
```

If either command exits non-zero, stop and route to `/order.tasks` or
`/order.spec` as reported. Do not repair the block from `/order.code` or
bypass missing read files or contract IDs.

Blocking findings (`severity: HIGH` or `CRITICAL`) must be fixed. Fix the data in `tasks.md` or `mechanisms.tsv` and re-run validation. Do not maintain a separate list of checks; trust the script output.

### Step 12: Update Active Feature State

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

python3 .orderspec/framework/scripts/active_feature.py set \
  --feature-id "$FEATURE_ID" \
  --feature-directory "$FEATURE_DIR_REL" \
  --status tasks \
  --last-command order.tasks \
  --json
```

### Step 13: Consumed Report Marker

If a BLOCK/ROUTING `tasks-report.md` was used in Step 5, mark it consumed.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
python3 .orderspec/framework/scripts/traceability.py mark-consumed --report "$FEATURE_DIR/tasks-report.md"
```

---

## Completion Report

Report to chat:

- `FEATURE_DIR`
- Total task count; per phase and per user story.
- Parallelism: number of `[P]` tasks and largest adjacent `[P]` group (0 is fine and expected for strictly sequential features).
- **`extract-trace` result**: final exit code (MUST be 0) and, if iterations were needed, a one-line note of what was fixed. Cite the tool's success — do not paste a coverage matrix.
- **`validate --stage tasks` result**: no blocking findings.
- Oversized stories flagged (any UJ over the 15-task soft limit).
- Suggested MVP scope (US1) and the STOP & VALIDATE checkpoint.
- If a prior `tasks-report.md` drove this run: which finding IDs were addressed.
- **Manual/orchestrator next step:** Run `/order.tasks-check` to verify the tasks before starting `/order.code`

## Done When

- [ ] Command context resolved via `command_context.py`
- [ ] Every `to_read` file was read and interpreted by `usage`
- [ ] Mode detected and stated
- [ ] Feature paths resolved; `eval` used for shell vars
- [ ] Upstream gate respected: guard returned `ok`/`advisory`/`forced` (not `halt`/`stop`/`error`); on `forced`, a `--force` warning was stamped atop the artifact; on `advisory`, user was warned in chat
- [ ] Prior gate report consumed (if present): a ⛔/🔀 `tasks-report.md` had every `/order.tasks`-owned finding addressed and listed; upstream-owned findings were routed/STOPped, not silently patched. ✅ PASS or absent → N/A
- [ ] `tasks.md` generated from current template in E-M-C order with sequential IDs and pipe-delimited task lines (`T### [P] [US] | path | refs? | gloss`)
- [ ] Refs are OPTIONAL (infra tasks carry empty refs), comma-joined with NO spaces when present, each declared ref's mechanism lists this task's path in `primary_files` (no filler/parked refs)
- [ ] Path field is a raw `plan.md` path with NO backticks
- [ ] Coverage proven by tool: `extract-trace` exited 0 (no uncovered direct, no tasked documented, no dangling delegated, no cap/duplicate violation)
- [ ] No hand-built matrix: no Traceability Matrix or Files Touched table authored by hand in `tasks.md`
- [ ] Sequential backbone correct with all `[P]` marks stripped; `[P]` only on provably file-disjoint, independent, adjacent tasks; no stub-then-implement
- [ ] No per-story verification tasks (Checkpoint is prose, not a task); final GATE task has empty refs
- [ ] AC refs on test-writing tasks only (not on verification/GATE); cross-cutting test tasks omit `[USn]`
- [ ] Placement validated: all `plan.md` files touched, no path outside `plan.md`, no same-file conflict within an adjacent `[P]` group
- [ ] `validate --stage tasks` has no blocking findings
- [ ] Every story task whose path owns a direct mechanism carries at least one valid spec ref; no-ref support tasks are allowed only on paths without direct mechanisms
- [ ] Every buildable Success Criterion is represented by an executable task or verification path; KPI-only criteria are exempt
- [ ] Environment readiness checks and recovery boundaries are preserved from `plan.md`; no implicit operator side effects are hidden in tasks
- [ ] `task_context.py validate` passed; every task has a deterministic read whitelist
- [ ] `task_contract_context.py validate` passed; every task ref resolves to exact spec excerpts and phase context
- [ ] Active feature status updated to `tasks`
- [ ] Completion Report provided, including manual/orchestrator recommendation to run `/order.tasks-check`
