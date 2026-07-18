---
orderspec:
  artifact: command_prompt
  command: order.tasks
  phase: tasks
description: Compile a disposable, sequential tasks.md from spec.md IDs and plan.md paths without adding design decisions. Expand-Migrate-Contract is used only when the plan requires a migration/cleanup transition. Deterministic tools prove structure and coverage.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Role of This Artifact

`tasks.md` answers **ORDER**: a disposable, mechanically executable checklist
that sequences decisions already present in `plan.md`. It MUST NOT introduce a
delivery strategy that the plan does not require.

It is derived from the planning baseline. Generating it freezes `plan.md` and
task content for the implementation run; checkbox changes do not change that
baseline.

- **Migration work orders** use **Expand → Migrate → Contract** when `plan.md`
  declares replacement, compatibility, feature-flag, schema contraction, or
  `[DEL]` work.
- **Non-migration work orders** use Setup → independently verifiable story
  phases → Final Verification. They MUST NOT invent a cleanup/Contract phase.

Core principles:

- **Disposable & derived, but progress-safe**: a new work order may be regenerated from scratch. Refine is a surgical repair of the current work order and MUST preserve completed tasks, their IDs, their task-context, and unrelated content. You make NO design decisions — every choice already lives in `plan.md`.
- **Weak-LLM-proof**: each task is executable without re-reading the spec — it carries its file path and spec IDs, while `/order.code` resolves those IDs into exact contract excerpts before execution.
- **Sequential by default**: structure is **Phases → Tasks**. Phases are hard sequential barriers; within a phase, tasks run top-to-bottom and that order MUST be correct on its own. `[P]` parallelism is an OPTIONAL annotation layered on top — never a precondition for correctness.
- **Coverage is proven, not asserted**: you do NOT hand-build, hand-count, or hand-fill any traceability matrix. `traceability.py extract-trace` projects coverage from your task lines and is the SOLE arbiter of completeness. Your job is correct task lines; the tool decides if they cover everything.
- **Environment actions are explicit**: preserve `plan.md` runtime prerequisites, readiness checks, recovery boundaries, and fallbacks. Never encode service startup, package installation, data reset, or another operator side effect as an implicit task.

---

## Global Execution Rules

1.  **Script Authority:** Framework scripts are deterministic. You MUST NOT
    second-guess, silently override, or manually repair their output. On
    failure, follow the reported disposition: fix only `/order.tasks`-owned
    input; route plan/spec/runtime defects to their owner.
2.  **Shell Variable Persistence:** Tool shell sessions may not preserve variables. You MUST rehydrate variables at the start of every new shell block by running:
    ```bash
    eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
    ```
    Do not assume variables like `$FEATURE_DIR` persist between separate shell calls.
3.  **Scope Lock:** You are sequencing `plan.md` into tasks. Do not invent new requirements, endpoints, fields, permissions, files, mechanisms, test topology, or delivery strategy. If tasking requires a missing decision, STOP and route it to the owning `/order.spec` or `/order.plan` command.

---

## Execution Flow

Follow these steps in exact order. Do not skip steps.

### Step 1: Command Context Resolution

Resolve and load all required context files.

```bash
python3 .orderspec/framework/scripts/command_context.py resolve order.tasks \
  --arguments "$ARGUMENTS" --json
```

1.  If `ok` is `false` or `missing_required` is non-empty, STOP and report the missing context.
2.  Read every file returned in `to_read`, in returned order.
3.  Interpret each file according to its `usage` field (`apply`, `constrain`, `parse`, `inspect`, `reference`).
4.  Use only returned `input.controls` and `input.semantic_input`; do not parse raw input again.

Apply the resolved tooling protocol before making library-specific task claims.

If required project contracts (`constitution.md`, `stack.md`, `architecture.md`, `conventions.md`) are missing, STOP and tell the user to run `/order.bootstrap` first.

### Step 2: Path Resolution

Resolve active feature paths.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
```

If this fails because no active feature directory can be resolved, STOP:
```text
TASKS_STOPPED: no active feature
  1. Create one with /order.spec, or select one with /order.feature --select
  2. Then run /order.plan
  3. Then run /order.tasks
```

### Step 3: Mode Detection

Before selecting a mode, inspect the self-gate report. This check is read-only
and MUST happen before any `tasks.md`-existence stop.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
SELF_REPORT="$FEATURE_DIR/tasks-report.md"
test -e "$SELF_REPORT" && echo "SELF_REPORT_PRESENT" || echo "SELF_REPORT_ABSENT"
```

If `SELF_REPORT_PRESENT`, read it before mode selection.

Also inspect downstream workflow feedback before mode selection:

```bash
python3 .orderspec/framework/scripts/workflow_feedback.py list \
  --feature-dir "$FEATURE_DIR" --target order.tasks
```

Determine mode before writing any file. State the mode in chat.

For empty `input.semantic_input` without an explicit control, run:

```bash
python3 .orderspec/framework/scripts/default_mode.py resolve \
  --command order.tasks --feature-dir "$FEATURE_DIR" \
  --semantic-input "<input.semantic_input>"
```

Obey its mode. `GENERATE` creates the missing work order. `REFINE` repairs only
unchecked tasks and their context. `INSPECT` preserves current content, reports
progress, and succeeds without rewriting. Empty input never stops merely because
`tasks.md` exists.

1.  **Regenerate** — `tasks.md` is absent, or `input.controls.force` is true. This discards task design only; if any task is `[X]`, STOP and require `/order.code --reset` first.
2.  **Refine** — active `tasks.md` exists and either `input.semantic_input` requests specific changes, the prior `tasks-report.md` has a `⛔ BLOCK` or `🔀 ROUTING` finding targeting `/order.tasks`, or open workflow feedback targets `order.tasks`. A blocking self-gate or open feedback selects Refine even when `input.semantic_input` is empty.
3.  **Inspect** — `tasks.md` exists and neither feedback nor upstream drift
    requires Refine. Report current progress without rewriting task design.

### Step 4: Upstream Gate Guard

Check the upstream plan gate.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

Set `FORCE_FLAG=--force` only when `input.controls.force_upstream` is true;
otherwise leave it empty.

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
    `> ⚠ Built over non-PASS plan gate (verdict: {verdict}) via --force-upstream`
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
To derive tasks anyway (NOT recommended), re-run with --force-upstream.
```

### Step 5: Self Gate Report Intake

Use self-gate result read in Step 3. Do not perform a second check.

-   **ABSENT** → Proceed.
-   **PRESENT (✅ PASS)** → Ignore report; proceed with `input.semantic_input`.
-   **PRESENT (`CONSUMED_STALE`)** → Previous verdict is inactive. Proceed with `input.semantic_input`; a fresh `/order.tasks-check` is required for new PASS evidence.
-   **PRESENT (⛔ BLOCK / 🔀 ROUTING)** → This is your fix-list. Address every finding targeting `/order.tasks`. Route findings for other commands. Treat `input.semantic_input` as additional guidance, not a replacement.

Use the workflow feedback result already loaded in Step 3. Every open item is
additional mandatory refine input. Do not consume it yet.

### Step 6: Setup Tasks Artifact

Initialize a new work order, or protect the existing file before Refine.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
```

- **Regenerate only**:
  ```bash
  python3 .orderspec/framework/scripts/setup.py tasks --json --refresh-template > /dev/null
  ```
- **Refine only**: MUST NOT pass `--refresh-template`, copy the template, rewrite
  the whole file, renumber tasks, or clear any checkbox. Start the transactional
  guard before editing:
  ```bash
  python3 .orderspec/framework/scripts/setup.py tasks --json > /dev/null
  python3 .orderspec/framework/scripts/task_refine.py begin \
    --tasks "$FEATURE_DIR/tasks.md" \
    --snapshot "$FEATURE_DIR/.state/tasks-refine-snapshot.json"
  ```
  Edit only lines and task-context entries required by the findings. Previously
  completed task lines and their task-context entries are immutable. If the
  correct fix would change completed work, STOP and route to `/order.code --reset`
  followed by a new work order.

### Step 7: Load Inputs

Read the following inputs from `$FEATURE_DIR`:

1.  **`spec.md`** — UJ priorities, AC, REQ, INV, EDGE, data model, contracts.
2.  **`plan.md`** — file mapping, stack, `[NEW]`/`[MOD]`/`[DEL]`
    transitions, migration/cleanup evidence, and test/build commands.
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

**A direct ref means "this mechanism is realized OR exercised in THIS task's `path`" — not "this ID needed a home to satisfy coverage".** A direct mechanism whose `primary_files` is an implementation file (model/service/controller/route) belongs on the IMPLEMENTATION task that writes that file — NOT on a verification/GATE/test task. Do NOT move a direct ID onto an unrelated task merely to clear an "uncovered" rejection: that is ID-parking, and it corrupts the trace projection. If a direct ID has nowhere to go within the 3-ref cap, that is the signal to add a task for its `primary_files`, not to park it elsewhere (see Granularity: god-file split). This is MACHINE-ENFORCED: `extract-trace` rejects (rc=3) any ref whose single `primary_files` value does not equal that task's path.

### Test Topology Binding

Treat each direct mechanism's test_type as a binding, not a hint:

- unit → require and use the unit-test path declared by the plan;
- integration → require and use the integration-test path declared by the plan;
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
1. Sort suggestions into the plan-derived phase strategy: E-M-C for migration
   work orders; Setup → stories → Final Verification otherwise.
2. Add `[USn]` from user-story mapping. Omit `[P]` by default; add it only when
   the plan explicitly establishes both file-disjointness and dependency independence.
3. Refine `gloss_hint` into a ≤15-word gloss.
4. Add a read-only GATE task at the end (`path = @verify`, refs empty, gloss
   `GATE: run [test command]...`).
5. Add any missing infra tasks (barrels, fixtures) that the tool didn't suggest.

### Step 8: Build Sequencing Inventory

This is ordering, not coverage bookkeeping — coverage is the tool's job in Step 10.

1.  List `UJ-NNN` by priority → user story phases (US1 ↔ UJ-001).
2.  Place each `AC/EDGE/INV` under a UJ (or Setup/final phase if cross-cutting).
3.  Place each buildable Success Criterion (load, security, performance, or other executable evidence) under its owning UJ or cross-cutting phase; post-launch/business KPI criteria need no task.
4.  From `plan.md`, list every `[NEW]`, `[MOD]`, and `[DEL]` path; assign each
    transition to exactly one or more tasks. No pathmanifest transition may be omitted.
    For each behavior-bearing path, copy its exact bounded obligation and
    relevant Spec IDs from Architectural Mapping. If the mapping does not say
    which required fields, operations, or interface values the path must
    establish, STOP and route to `/order.plan`; do not infer them later.
5.  Note the project's test command from `plan.md` (used verbatim in verification/GATE tasks).
6.  Carry each required environment readiness check into the relevant phase
    verification or implementation preflight. Add a task only when readiness
    requires a repository artifact or code/config change listed in the plan.

### Step 9: Write `tasks.md`

In Regenerate, rewrite `$TASKS_FILE` initialized from the template. In Refine,
apply a minimal patch to the existing file; never reconstruct it from the
template or from memory.

**Phase mapping** — choose from plan evidence; never invent:

- **Phase 1 — Setup & Expand** (all changes non-breaking):
  - *if persistent storage*: additive migrations with rollback scripts (Spec § Data Model).
  - *if interfaces (API/CLI/UI)*: contract/route/DTO/command stubs (Spec § Contracts).
  - passive model entities only when their placement agrees with plan Evidence
    Sequencing. In `red-first`, do not establish behavior a later test must
    observe as absent. In `characterization-first`, preserve the baseline the
    earlier test records. In `implementation-first`, cite the plan's explicit
    constraint before placing implementation ahead of evidence.
  - environment setup only when `plan.md` declares a repository-owned artifact
    such as a compose file, fixture, or configuration. Operator recovery actions
    remain approval-gated implementation preflight, not hidden tasks.
- **Phase 2+ — Migrate**: US1 (P1, MVP) first, then one phase per remaining UJ in priority order.
  Within each story phase:
  1. Apply the plan's Evidence Sequencing mode. In `red-first`, test-writing
     tasks precede implementation and their gloss states the expected failure.
     In `characterization-first`, baseline tests precede change and state the
     expected baseline result. In `implementation-first`, tests follow the
     implementation and carry the plan's justification. Split test tasks when
     ACs exceed the 3-ref cap.
  2. Data layer → service logic → wiring to contracts.
  3. `EDGE-NNN` for this story.
  4. Emit a **Verification** prose line with the exact permitted test command and asserted AC/INV IDs, then a **Checkpoint** prose line: story independently functional and backwards-compatible. Neither line is a task; `/order.code` executes the declared Verification command at the phase barrier.
  Omit test tasks only if the user or constitution explicitly opts out.
- **Final Phase — Contract**: include only when the plan declares irreversible
  cleanup. Start with a GATE task (run the test command verbatim; verify all
  `AC-*` pass, `INV-*` hold, `NFR-*` met; STOP on failure). Then perform only
  the cleanup transitions declared by the plan.
- **Final Verification**: for a non-migration work order, end with the same
  read-only GATE/VERIFY evidence but no invented cleanup task.
  **Read-only task target**: `GATE:` and command-only `VERIFY:` tasks use the
  reserved field-2 target `@verify`, empty refs, and `target_state: "none"`.
  `@verify` is a task type marker, not a repository path; its packet has
  `write_paths: []`.
  **Verification-only command task**: prefix gloss with `VERIFY:` and use the
  `@verify` target. This task is read-only and reports `changed_files: []`. Its command MUST NOT use an
  autofix/write option. On failure, `/order.code` stops; it never edits files
  or disguises changes under the binding path. Formatting compliance must be
  achieved by each earlier file-owning implementation task.

**Task format (STRICT — pipe-delimited, machine-parsed).** Every task line has
exactly four fields and exactly three ` | ` separators. Emit EXACTLY:

```text
- [ ] T012 [P] [US1] | src/models/user.py | REQ-001,AC-002 | user has unique email, hashed password
```

1. "- [ ] T012 [P] [US1]" — checkbox + sequential ID + optional [P] + optional [USn].
2. file path — one exact path from `plan.md`. No spaces. Raw path only — do NOT wrap it in backticks or any markdown. `extract-trace` matches the literal path; backticks make the field not match `plan.md` and silently drop the line's coverage.
3. refs — OPTIONAL in meaning but never omitted as a field. Use comma-separated
   spec IDs with NO SPACES. An infrastructure/GATE/`VERIFY:` task uses an empty
   third field: `... | path |  | gloss`. NEVER invent a ref to give a task a home.
  **AC refs belong on test-WRITING tasks** (the task that writes the test code exercising that AC), NOT on verification/GATE tasks. Verification/GATE tasks carry EMPTY refs and list asserted AC/INV IDs in the gloss. Coverage of an AC is proven by the test-writing task that creates its test, not by the verification task that runs the suite.
  A story-phase task may also have empty refs when no direct mechanism has this task's exact path in `primary_files` (for example, unit evidence tasks, controller support tasks, or wiring tasks). Do not invent or park a ref only to satisfy the `[USn]` marker; ref presence is required only on story tasks that own a direct mechanism path.
4. gloss — ≤15-word paraphrase. Free text. Test-writing tasks state the expected
   result required by plan Evidence Sequencing. A command-only lint/typecheck
   task begins with `VERIFY:`, forbids automatic writes/autofix, and routes or
   stops on violations.

**Constraints the tool ENFORCES** (any violation fails `extract-trace` with rc=3, file untouched):

- `primary_files` in `mechanisms.tsv` is a single path per row (TSV, same format as `spec-ids.tsv`). A declared ref is valid iff the ref's `primary_files` equals this task's exact `path`.
- Exact binding: a DECLARED ref MUST be a direct mechanism whose single
  `primary_files` value EQUALS this task's exact path. A ref attached elsewhere
  is rejected as filler/mis-attribution.
- `documented` IDs MUST NOT appear as refs (`plan.md` row only). Tasking one → rejected.
- `delegated:<ID>` IDs MUST NOT appear as refs — task `<ID>` (the delegate) instead → rejected.
- Atomicity cap: at most 3 spec IDs in field 3. 4+ refs = kitchen-sink defect, REJECTED. No GATE exemption — assert extra IDs in the gloss or split lines.
- No duplicate ref within a task (`REQ-001,REQ-001` rejected). No spaces in refs or path.

**Examples:**

- OK:  `- [ ] T012 [P] [US1] | src/models/user.py | REQ-001 | user has unique email, hashed password`
- OK:  `- [ ] T015 [US1] | tests/test_auth.py | AC-002 | expect failure before implementation: invalid credentials return 401`
- OK:  `- [ ] T003 | src/models/index.js |  | register new model in barrel` (empty refs, LEGAL infra task)
- BAD: `- [ ] Create User model` (no ID/path/refs; not a task line)
- BAD: `- [ ] T012 [US1] | src/a.js | REQ-001, AC-002 | ...` (space in refs → rejected)
- BAD: `- [ ] T020 [US1] | src/x.js | REQ-003,REQ-004,REQ-005,REQ-006 | does everything` (4 refs → rejected)
- BAD: `- [ ] T003 | src/models/index.js | REQ-001 | barrel` (`REQ-001`'s `primary_files` is the model file, NOT `index.js` → filler/mis-attributed ref → rejected rc=3; leave refs EMPTY instead)
- OK:  `- [ ] T099 | @verify |  | VERIFY: run project lint command; no autofix`

`[USn]` is required on story-phase tasks (1:1 with `UJ-00n`), including valid no-ref support tasks; omitted in Setup/Expand and Contract. A no-ref story task is valid when its exact path is not a direct mechanism's `primary_files` path.
For interface tasks, fold contracted failure semantics into the gloss.

### Task Context Block

After composing all task lines, replace only the JSON payload in the template's
fixed-position `task-context` block with exactly one machine-readable JSON
block. The heading and fence stay in their template position, before the first
horizontal rule and before `## Execution Order`:

````text
```task-context
{
  "version": 1,
  "tasks": {
    "T001": {"read": ["src/existing.py", "src/shared.py"], "target_state": "mod", "contract_refs": ["REQ-001"]}
  }
}
```
````

This block is the sole source of truth for task worker file context. Build one
entry for every task ID. For each task, `target_state` MUST copy the status of
its path from `plan.md` (`new` for `[NEW]`, `mod` for `[MOD]`, `del` for
`[DEL]`). `read` MUST contain the exact existing repo-relative files the worker
needs to inspect, in read order, including a `mod` or `del` task write target.
A `[NEW]` write target is not included until it exists. A read-only `@verify`
entry uses `target_state: "none"`. Do not list
directories, globs, or broad repository scans.
Do not include Markdown unless it is the task's own write target. Derive the
list from the task objective, `plan.md`, and targeted source inspection. An
exact `[NEW]` path written by an earlier task may be listed as a dependency even
before it exists on disk; sequential execution guarantees it is available when
the later task runs. If a required dependency cannot be stated as an exact
file, route the defect to `/order.plan`; do not leave worker context implicit.

`contract_refs` is optional and does not participate in traceability coverage.
Use it when a task's field-3 refs do not supply every exact contract excerpt the
worker needs. This is mandatory for behavior-bearing support tasks with empty
field-3 refs and for cross-boundary tasks whose traceability mechanism is owned
by another file. Include the smallest relevant canonical Spec ID set. For
example, a model task that must persist audit `actorId`, identifiers, and
`before`/`after` snapshots receives the IDs that define those values even when
the service is the mechanism's `primary_files` owner. Do not use
`contract_refs` to fake coverage; field 3 remains the only coverage source.

`task_context.py` owns parsing, fixed-position validation, file-existence
checks, and resolver output. `/order.code` consumes its output verbatim. Do not
hand-author a second whitelist in a prompt, packet, or coordinator note.

`task_contract_context.py` owns deterministic resolution of task refs to exact
ID blocks from `spec.md`, relevant `mechanisms.tsv` rows, and the current phase
Goal/Verification context. `/order.code` MUST run it for every task and pass
its output verbatim to the worker. Task glosses remain short execution hints;
they are not substitutes for the resolved contract excerpts.

**Prose to fill by hand** (NOT machine state): the plan-derived Execution
Order line and each story phase's Goal and Verification lines (from Spec §
Acceptance Criteria). Mention Contract only for a migration work order.

> Do **NOT** hand-write a Traceability Matrix or a Files Touched table in `tasks.md`. `extract-trace` projects coverage into the machine-readable `traceability.tsv`; no hand-authored mirror is required. A hand-built matrix is exactly the drift this system removes — if the template contains such placeholder sections, leave them empty or delete them.

**Granularity rules (semantic — yours; the tool only enforces the 3-ref cap):**

- **One task = one write path and one atomic, independently verifiable change.**
  More than one write path → split.
- **Prerequisite closure**: before emitting a task, verify every contract-required
  model field, schema operation, export, route, serializer value, and test
  fixture it needs is established by this or an earlier task. A later service
  task discovering an incomplete earlier schema is a task decomposition defect.
- **No stub-then-implement**: never create a file with empty/stub methods early to fill later; its FIRST task carries real implementation. (Exception: contract boundaries `plan.md` explicitly marks as stubs.) A file appearing in two phases where the earlier says "stub"/"skeleton" is a defect.
- **God-file split (resolves cap-vs-coverage pressure)**: when one `primary_files` carries MORE than 3 direct mechanisms (a "god file" like a central service), do NOT cram them into one task and do NOT park the overflow on verify/GATE tasks. Split into several IMPLEMENTATION tasks on the SAME path, each grouping ≤3 cohesive mechanisms by behavior (e.g. one task for create+list+get, another for update+soft-delete, another for atomic-audit+error-wrapping). These same-file tasks are sequential (NOT `[P]` — they share a file) and each carries the direct IDs it actually implements. This keeps every direct ID on the task that realizes it AND stays under the cap.
- **Test-file split (mirror of god-file split, for test files)**: when one test `primary_files` carries MORE than 3 direct ACs, do NOT cram them into one task. Split into several TEST-WRITING tasks on the SAME test path, each carrying ≤3 ACs grouped by behavior (e.g. one task for create+list tests, another for update tests, another for soft-delete tests). These same-file test tasks are sequential (NOT `[P]` — they share a file) and each carries the AC IDs it actually exercises.
- **Evidence-sequencing closure**: in `red-first`, no Setup/Expand or earlier story task may
  establish behavior that a later test-writing task is supposed to prove
  missing. Move that test earlier or move implementation later. Every declared
  test-writing task must have an executable expected red state. Apply the
  distinct expectations recorded by `characterization-first` or
  `implementation-first` without inventing a red state.
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
- Every `[NEW]`, `[MOD]`, and `[DEL]` path from `plan.md` appears in ≥1 task.
- No task references a path absent from `plan.md`.
- `[P]` is absent unless the plan explicitly proves both file-disjointness and
  dependency independence; adjacent `[P]` tasks never touch the same path.
- Each task's prerequisites precede it.
- Every P1 journey and its declared dependencies form the minimal MVP; do not
  assume US1 alone is sufficient when multiple P1 journeys exist.

If you change any task line, re-run `extract-trace`.

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

In Refine, run the protection check after all edits and before consuming any
report. On failure the script restores the exact pre-refine tasks.md:

```bash
python3 .orderspec/framework/scripts/task_refine.py validate \
  --tasks "$FEATURE_DIR/tasks.md" \
  --snapshot "$FEATURE_DIR/.state/tasks-refine-snapshot.json"
```

In Regenerate, attempt to capture the clean Git-backed work-order baseline used
by the safe reset mode. Capture succeeds only when Git is available, planned
paths are clean, `[NEW]` paths are absent, and `[MOD]/[DEL]` paths are tracked.

```bash
python3 .orderspec/framework/scripts/work_order.py capture \
  --feature-dir "$FEATURE_DIR" --replace
```

Capture failure does not invalidate tasks.md or block implementation; record
the exact reason and report `/order.code --reset` as unavailable for this work
order. Never weaken capture checks or create an unsafe baseline to clear the
warning.

Blocking findings (`severity: HIGH` or `CRITICAL`) must be resolved by their
artifact owner. Fix tasks-owned data in `tasks.md`. Route any `mechanisms.tsv`,
pathmanifest, mechanism, or test-topology defect to `/order.plan`; never modify
plan-owned state from `/order.tasks`. Route contract defects to `/order.spec`.

### Step 12: Update Active Feature State

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

python3 .orderspec/framework/scripts/active_feature.py status \
  --feature-id "$FEATURE_ID" \
  --status tasks \
  --last-command order.tasks \
  --json
```

### Step 13: Consumed Report Marker

If a BLOCK/ROUTING `tasks-report.md` was used in Step 5, mark it consumed.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
python3 .orderspec/framework/scripts/traceability.py mark-consumed \
  --report "$FEATURE_DIR/tasks-report.md" \
  --consumer /order.tasks \
  --recheck /order.tasks-check
```

After successful validation, consume each open `order.tasks` workflow feedback
item that this run addressed:

```bash
python3 .orderspec/framework/scripts/workflow_feedback.py consume \
  --feature-dir "$FEATURE_DIR" --id "FB-NNN" --consumer order.tasks
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

- [ ] Context, feature paths, mode, self-gate, feedback, and upstream gate resolved before mutation
- [ ] Regenerate used the current template; Refine passed `task_refine.py` without changing completed or unrelated content
- [ ] Plan-selected delivery strategy is preserved; no files, mechanisms, topology, cleanup, or behavior were invented
- [ ] Every task has exactly four fields, one raw plan path, ≤3 valid direct refs, and a ≤15-word gloss
- [ ] Every `[NEW]`/`[MOD]`/`[DEL]` path is tasked; no task path lies outside the manifest
- [ ] `extract-trace` exited 0; no hand-built coverage/files matrix was authored
- [ ] Sequential execution is correct; `[P]` appears only with explicit plan evidence of path and dependency independence
- [ ] Test ordering follows plan Evidence Sequencing; checkpoints are prose; GATE/`VERIFY:` tasks use `@verify`, empty refs, and no write paths
- [ ] Buildable SCs, prerequisites, environment boundaries, and plan-declared recovery constraints are preserved
- [ ] `task_context.py` and `task_contract_context.py` passed with minimal exact read/contract context
- [ ] `validate --stage tasks` has no blocking findings
- [ ] Baseline capture/state update succeeded or reset unavailability was reported exactly
- [ ] Addressed reports/feedback were consumed only after validation
- [ ] Completion Report recommends `/order.tasks-check`
