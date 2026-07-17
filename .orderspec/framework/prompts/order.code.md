---
orderspec:
  artifact: command_prompt
  command: order.code
  phase: implement
description: Execute every tasks.md task phase by phase, delegating only when user constraints permit it and using bounded local execution otherwise.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Role of This Artifact

`order.code` **executes** — it makes no design decisions. All decisions live in `spec.md` (WHAT) and `plan.md` (HOW); `tasks.md` defines ORDER.

- **Tasks are self-contained**: each task carries its file path, coverage refs,
  optional support-path `contract_refs`, and a ≤15-word paraphrase. Execute
  from the resolved packet; never preload `spec.md`.
- **Delegation is conditional and user-controllable**: explicit user instructions
  to avoid sub-agents or keep all work in one agent session MUST select local
  execution, even when dispatch is available. Otherwise, in `DELEGATED`, every
  unchecked task uses its own sub-agent. In local execution, coordinator runs
  the same bounded task packet itself. Coordinator always validates results,
  updates `[X]` markers through the deterministic script, and reports.
- **Sequential by default, `[P]` is a hint**: tasks execute top-to-bottom in ID order. `[P]` means a task is file-disjoint from adjacent `[P]` tasks, so their sub-agents MAY run concurrently. Sequential execution remains the fallback for any task that is not proven safe to parallelize.
- **Resumable**: tasks marked `[X]` are done — skip them, never redo or "improve". A re-run continues from the first unchecked task. Never remove `[X]` markers.
- **No silent deviations**: if a task cannot be executed as written (missing path, contradiction with `plan.md`, broken dependency), apply the Deviation Rule below — do not improvise.

### Frozen Baseline and Pathmanifest Semantics

For this work order, `plan.md` is the planning baseline, not a live filesystem
inventory. Its tags describe transitions from that baseline:

- `[NEW]` means implementation is expected to create the path. Presence after a
  completed task is success. Presence for the first unchecked task may be an
  interrupted partial write; inspect, complete, verify, and mark that task.
- `[DEL]` means implementation is expected to remove the path. Absence after a
  completed task is success. Absence for the first unchecked task may be an
  interrupted partial deletion; verify the task outcome before marking it.
- `[MOD]` means the baseline path existed and remains a modification target.

Never relabel `[NEW]` to `[MOD]`, regenerate `plan.md`, or report plan drift only
because earlier tasks applied these transitions. Do not run `check-plan` or
`validate --stage plan` from `/order.code`; those are plan-authoring baseline
checks. A contradiction is an actual disagreement in required behavior,
physical mapping, or task prerequisites—not an expected manifest transition.

## Global Execution Rules

1. **Script Authority:** Framework scripts are deterministic. You MUST NOT second-guess, silently override, or manually repair successful script output. If a script exits non-zero or returns invalid JSON, read the error and fix your input data.
2. **Shell Variable Persistence:** Tool shell sessions may not preserve variables. You MUST rehydrate variables at the start of every new shell block:
   ```bash
   eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
   ```
3. **Scope Lock:** You execute `tasks.md`. Do not invent new requirements, endpoints, fields, or permissions. If execution strictly requires a new externally visible behavior not present in `spec.md`, STOP and report `CODE_BLOCKED: contract decision required`.
4. **Environment Boundary:** Apply `environment-block.md`. The coordinator diagnoses runtime blockers and asks for approval before mutating recovery actions; workers never mutate the environment.

---

## Execution Flow

Follow these steps in exact order. Do not skip steps.

### Step 1: Command Context Resolution

Resolve and load all required context files.

```bash
python3 .orderspec/framework/scripts/command_context.py resolve order.code --json
```

1. If `ok` is `false` or `missing_required` is non-empty, STOP and report the missing context.
2. Read every file returned in `to_read`, in returned order.
3. Interpret each file according to its `usage` field (`apply`, `constrain`, `parse`, `inspect`, `reference`).

If required project contracts (`constitution.md`, `stack.md`, `architecture.md`, `conventions.md`) are missing, STOP and tell the user to run `/order.bootstrap` first.

### Step 2: Path Resolution

Resolve active feature paths.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
```

If this fails because no active feature directory can be resolved, STOP:

```text
CODE_STOPPED: no active feature
  1. Create/select a feature with /order.spec
  2. Then run /order.plan
  3. Then run /order.tasks
  4. Then run /order.code
```

### Step 3: Execution Mode Detection

Determine execution strategy before writing any file. State the selected mode in chat.

Execution modes:

1. **DELEGATED** — user input permits delegation and runtime explicitly exposes
   sub-agent dispatch and wait. Dispatch every unchecked task according to Step 9.
2. **LOCAL_PHASE** — local execution was explicitly requested, or dispatch is
   unavailable. Coordinator executes every unchecked task in the first
   incomplete phase sequentially, then stops at the phase barrier. This is not
   a block.
3. **LOCAL_ALL** — local execution was explicitly requested, or dispatch is
   unavailable, and `$ARGUMENTS` contains `--all`. Coordinator executes every
   unchecked task in every remaining phase sequentially.

Additional controls:

- **RESUME** — `$ARGUMENTS` is empty or contains `--resume`; skip tasks already marked `[X]` in every selected execution mode.
- **`--local` / `--no-subagents`** — force local execution. Do not inspect,
  configure, dispatch, or wait for a worker.
- **Explicit natural-language local constraint** — instructions such as “do not
  use sub-agents”, “without delegation”, “single agent”, or requiring all work
  to remain in one/single agent session are equivalent to `--local`, including
  equivalent wording in another language. A request for one run alone does not
  imply local execution unless it also constrains the agent/session boundary.
- **`--force`** — upstream gate override only. It never selects an execution mode and must be recorded in the Completion Report.
- Missing `tasks.md` remains a hard stop handled by Step 4. It is not a fallback case.

Mode precedence:

1. Resolve command context and paths.
2. Parse explicit user execution constraints before capability detection.
3. If local execution is requested, select `LOCAL_ALL` with `--all`, otherwise
   `LOCAL_PHASE`. Do not inspect dispatch capability or resolve a worker.
4. Otherwise detect actual dispatch capability in the current runtime; do not
   infer it from `agents.json` or adapter detection.
5. Select `DELEGATED` when dispatch is available. Otherwise select `LOCAL_ALL`
   with `--all`, or `LOCAL_PHASE` without it.
6. State mode before the first task mutation. User prohibition of delegation
   always overrides runtime capability and worker defaults.

### Step 3.5: Worker Resolution

Apply `sub-agent-rules.md` before the first delegated task. Build this request:

```yaml
caller: order.code
role: implementation-worker
preferred_name: worker
reasoning_effort: medium
scope: project
```

User input may override the execution mode, `preferred_name`,
`reasoning_effort`, or `scope`. An explicit local constraint is resolved in
Step 3 and skips this worker request entirely.

If the selected mode is `DELEGATED`:

1. Identify the current runtime agent. Do not infer it from
   `.orderspec/state/agents.json` when multiple agents are enabled.
2. Inspect the requested worker through the matching adapter:
   ```bash
   python3 .orderspec/framework/scripts/agents_sync.py subagents inspect \
     --agent <runtime-agent> --name <worker-name> --scope <scope> --json
   ```
3. Continue only when the report says `configured: true` and `valid: true`.
   A built-in worker is usable only when the adapter reports it.
4. If the worker is missing or invalid, stop before dispatch and ask the user
   for a worker name and reasoning level. After the user chooses, configure it
   through the adapter, defaulting to project scope:
   ```bash
   python3 .orderspec/framework/scripts/agents_sync.py subagents configure \
     --agent <runtime-agent> --name <worker-name> \
     --reasoning <level> --scope project --json
   ```
   Re-run `inspect` and dispatch only after it reports readiness. Do not
   silently write global configuration or invent a worker name.

If the selected mode is `LOCAL_PHASE` or `LOCAL_ALL`, do not configure a
worker. Execute the bounded packet locally according to the selected fallback.

### Step 4: Upstream Gate Guard

Run the deterministic guard. `$FORCE_FLAG` is `--force` iff `$ARGUMENTS` contains `--force`; otherwise empty.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

FORCE_FLAG=""
case "$ARGUMENTS" in
  *"--force"*) FORCE_FLAG="--force" ;;
esac

python3 .orderspec/framework/scripts/upstream_gate.py \
  --report        "$FEATURE_DIR/tasks-report.md" \
  --artifact      "$FEATURE_DIR/tasks.md" \
  --upstream-name "tasks.md" \
  --this          "/order.code" \
  --build         "/order.tasks" \
  --fix           "/order.tasks" \
  --recheck       "/order.tasks-check" \
  $FORCE_FLAG
```

Act on exit code / `status`:

- **exit 2, `status: stop`** → STOP. Write NO code. Print the STOP message and end.
- **exit 1, `status: halt`** → STOP. Write NO code. Print the HALT message and end.
- **exit 64, `status: error`** → STOP. Report `CODE_STOPPED: upstream gate invocation error (empty shell variables — re-run setup.py paths)`.
- **exit 0, `status: forced`** → Proceed, but record in the Completion Report: `⚠ Implemented over non-PASS tasks gate (verdict: {verdict}) via --force`.
- **exit 0, `status: advisory`** → Emit `reason` as one-line ⚠ warning in chat; proceed.
- **exit 0, `status: ok`** → Proceed silently.

### Step 4.5: Deterministic Implementation Setup

After the upstream gate passes, validate the complete implementation input set:

```bash
python3 .orderspec/framework/scripts/setup.py code --json
```

If this exits non-zero, STOP and report the script output. Do not execute a
task with missing `plan.md` or `tasks.md`, and do not reconstruct either file
from `/order.code`.

**STOP message (exit 2):**

```text
CODE_STOPPED: no tasks to implement
There is no tasks.md in this feature ($FEATURE_DIR).
Implementation executes an existing task list — the tasks must exist first.
  1. Create the tasks:  /order.tasks
  2. (recommended) Verify them: /order.tasks-check
  3. Then run /order.code
--force does NOT bypass this — there is genuinely nothing to implement.
```

**HALT message (exit 1):**

```text
CODE_BLOCKED: tasks gate not passed
Tasks gate verdict: {verdict} (from tasks-report.md, dated {date})
The task list has unresolved findings. Resolve them first:
  1. Report each Routing block in tasks-report.md as human/orchestrator work for `/order.tasks "..."`.
  2. Stop. Human or orchestrator runs `/order.tasks`, then `/order.tasks-check` until the verdict is ✅ PASS.
  3. Human or orchestrator starts `/order.code` again.
To implement anyway (NOT recommended), re-run with --force.
```

### Step 5: Tooling Validation

If the current command loads `tooling-protocol.md` (check `to_read` from Step 1), verify library skills deterministically:

```bash
python3 .orderspec/framework/scripts/validate_tooling.py -C "$PWD" --json
```

Interpret the JSON `summary`:

| Field | Required Action |
|-------|-----------------|
| `summary.installed_and_verified` (non-empty) | Use these skills as evidence source |
| `summary.installed_but_missing` (non-empty) | Follow `tooling-protocol.md` rule 6: MUST NOT silently continue; ask user to install or proceed without library-specific claims |
| `summary.discovered_only` (non-empty) | Ask user before installing per `tooling-protocol.md` rule 4 |
| `summary.pending` (non-empty) | Treat as unavailable; do not use as evidence |

For each `STACK-NNN` referenced in the feature spec that requires library-specific implementation:
1. Look up the technology in `.orderspec/contracts/stack.md`.
2. Search `tooling.json` `skills.bindings` for a binding where `match.stack_id` equals that `STACK-NNN`.
3. If a binding exists, use `validate_tooling.py` output to check `installed_and_verified`.
4. If no binding exists for a `STACK-NNN` requiring library-specific work, follow rule 6: do not silently proceed.

For each `docs_sources` source with `policy: "required_if_available"`:
1. Check if current command is in the source's `commands` array.
2. If yes and source is available as runtime tool, consult it before making library-specific claims.
3. If unavailable, apply `fallback_when_unavailable` (default: block library-specific claims).

Do NOT hardcode tool names in procedural logic — use only source names and policies from `tooling.json`. Record evidence in the Completion Report under `## Library Documentation Evidence`.

### Step 6: Self Gate Report Intake

Check for a prior `/order.tasks-check` report.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
SELF_REPORT="$FEATURE_DIR/tasks-report.md"
test -e "$SELF_REPORT" && echo "SELF_REPORT_PRESENT" || echo "SELF_REPORT_ABSENT"
```

- **ABSENT** → Proceed.
- **PRESENT (✅ PASS)** → Ignore report; proceed with `$ARGUMENTS`.
- **PRESENT (⛔ BLOCK / 🔀 ROUTING)** → This is your fix-list IF findings target `/order.code`. But `/order.code` executes a frozen `tasks.md`; findings targeting `/order.tasks` or upstream MUST NOT be patched here. If any finding targets `/order.code` execution behavior (e.g. "task Tnnn path missing"), STOP and route back to `/order.tasks`. Otherwise proceed — `tasks.md` was already gated in Step 4.

### Step 7: Load Execution Context

Read the following from `$FEATURE_DIR`:

1. **REQUIRED**: `tasks.md` — phases, task lines (`T### [P?] [US?] | path | refs? | gloss`), checkpoints, GATE.
2. **REQUIRED**: `plan.md` — tech stack, file structure (pathmanifest), build/test commands. Read `Environment Readiness` for runtime prerequisites, exact checks, recovery options, approval boundaries, and safe fallbacks.
3. `spec.md` is available to the coordinator for resolving contract IDs and preparing targeted excerpts. Workers receive those excerpts through `contract_context`; they do not open `spec.md` unless it is explicitly listed by the resolver.

Do NOT look for a hand-built Traceability Matrix or Files Touched table in `tasks.md` — those are derived artifacts; `order.tasks` does not author them. For file-disjointness verification (Step 9), use `plan.md` pathmanifest and task `path` fields directly.

### Step 8: Validate `tasks.md` Format

Before executing, validate structure. If invalid, STOP and suggest re-running `/order.tasks` (tasks.md is disposable — regenerate, don't hand-patch).

Run deterministic task-state validation first:

```bash
python3 .orderspec/framework/scripts/task_progress.py validate \
  --tasks "$FEATURE_DIR/tasks.md"
```

Non-zero exit is a STOP. Do not repair `tasks.md` from `/order.code`; route to `/order.tasks`.

Validate the machine-readable task context before executing any task:

```bash
python3 .orderspec/framework/scripts/task_context.py validate \
  --feature-dir "$FEATURE_DIR" --json
```

If this exits non-zero, STOP and route to `/order.tasks`. Do not construct a
replacement whitelist in `/order.code`.

Validate that every task's referenced spec IDs can be resolved into exact
contract excerpts and that its phase context is available:

```bash
python3 .orderspec/framework/scripts/task_contract_context.py validate \
  --feature-dir "$FEATURE_DIR" --json
```

If this exits non-zero, STOP and route to `/order.tasks` or `/order.spec` as
reported. Do not paraphrase missing contract IDs in the worker packet.

- Every task line matches: `- [ ] T### [P?] [US?] | path | refs? | gloss` (or `- [X] ...` for completed).
- Task IDs are monotonically non-decreasing (T001, T002, ...). Gaps ARE legal (T005, T010, T015). Duplicates and out-of-order IDs are rejected by `task_progress.py`; route invalid task structure to `/order.tasks`.
- Structure follows E-M-C: optional Setup/Expand phase first, one phase per user story in the middle, Contract phase LAST whose first task is the GATE. Extra non-story phases (e.g. dedicated unit-test phase) are allowed as long as they sit before the Contract GATE.
- `[P]` is OPTIONAL; absence everywhere is valid (purely sequential plan). Do NOT require any parallel markers.
- Verification/GATE tasks carry EMPTY refs (AC/INV IDs named in gloss, not in refs field).
- A Contract GATE task MUST exist and MUST be the first task of the Final Phase.

### Step 9: Execute Phase by Phase

Run phases strictly in order (hard sequential barriers). Within a phase, execute tasks top-to-bottom in ID order.

#### The Loop

1. Skip tasks already marked `[X]` (resume support — never redo).
2. Build the next execution unit from the current phase: one unchecked task, or one adjacent `[P]` group proven safe by the parallelism rules below.
3. In `DELEGATED`, dispatch every task in the execution unit to its own sub-agent. In `LOCAL_PHASE` and `LOCAL_ALL`, execute the same task packet in the coordinator.
4. Wait for the result, inspect allowed changes, run declared verification, then call `task_progress.py mark` with the worker result. Continue only after the marker script marks that exact task `[X]`.
5. Advance to the next unchecked task in ID order. Do not leave the phase until every task and its checkpoint are complete.

#### Task packet, worker boundary, and parallelism (`[P]`) — delegation when available

- Apply `sub-agent-execution.md` exactly. The coordinator MUST build one task packet per task.
- Before building the packet, resolve the exact task context:
  ```bash
  python3 .orderspec/framework/scripts/task_context.py resolve \
    --feature-dir "$FEATURE_DIR" --task-id "$TASK_ID" --json
  ```
- Resolve the task's contract context before dispatch:
  ```bash
  python3 .orderspec/framework/scripts/task_contract_context.py resolve \
    --feature-dir "$FEATURE_DIR" --task-id "$TASK_ID" --json
  ```
- The resolver output is authoritative. The coordinator MUST pass its `to_read` entries verbatim and its `write_paths` verbatim. The coordinator MUST NOT construct, expand, reorder, or replace this file list.
- Pass `contract_context` exactly as returned, including task-context
  `contract_refs`. Field-3 refs prove traceability ownership; `contract_refs`
  provide exact excerpts to support paths and MUST NOT be discarded merely
  because they do not own the mechanism row.
- The packet contains the exact task line, imperative objective, resolver `to_read`, resolver `write_paths`, exact `contract_context` output, inline context excerpts, verification requirement, and stop conditions.
- The coordinator may read command context, project contracts, feature artifacts, and relevant source files to prepare inline context. The worker receives only resolver-listed files and inline excerpts. The worker MUST NOT scan the repository or open files absent from resolver output.
- In `DELEGATED`, the worker MUST touch only the task `path`, must not edit `[X]`, start another worker, or advance to another task. It returns the protocol result object.
- In `LOCAL_PHASE`/`LOCAL_ALL`, the coordinator follows the same packet and result rules. It MUST NOT use local fallback as permission to broaden scope.
- Tasks without `[P]` run one at a time in ID order. Continue only after successful result validation and deterministic marker update.
- An adjacent group of `[P]` tasks MAY be dispatched concurrently, one sub-agent per task. `[P]` never overrides task order, phase barriers, dependencies, or the Contract GATE.
- Before dispatching any concurrent `[P]` group, VERIFY file-disjointness:
  - For each candidate task, read its `path` field (field 2 of the task line).
  - Cross-check against `plan.md` pathmanifest to resolve any path aliases.
  - If any two candidate tasks share a resolved path, they are NOT parallel-safe — dispatch them sequentially regardless of `[P]`.
  - If dependency, generated-output, test-fixture, or other shared-state safety is uncertain, dispatch sequentially.
  - Only dispatch concurrently when every pair is file-disjoint and independently executable. Wait for ALL sub-agents to finish before marking successful tasks `[X]` or continuing past the group.
- A `[P]` task not adjacent to another `[P]` task still runs in its own sub-agent, sequentially.
- If dispatch is unavailable, use the mode selected in Step 3. If a delegated worker returns no usable result, leave the task unchecked and STOP with `CODE_BLOCKED: unusable sub-agent result for Tnnn`; do not silently switch modes mid-phase.
- Never dispatch tasks from different phases concurrently. Never dispatch a later task while an earlier phase, story checkpoint, or GATE is incomplete.
- When in doubt, fall back to sequential. Losing parallelism is harmless; a same-file race is not.

#### Per-Task Rules

Worker result must match the protocol schema:

```json
{
  "task_id": "T###",
  "status": "SUCCESS|FAILED|BLOCKED|NEEDS_CONTEXT",
  "changed_files": ["repo/relative/path"],
  "verification": {"status": "PASS|NOT_RUN|FAIL", "evidence": "short result"},
  "deviation": null
}
```

After coordinator validation, mark only that task:

```bash
python3 .orderspec/framework/scripts/task_progress.py mark \
  --tasks "$FEATURE_DIR/tasks.md" \
  --result-file "$RESULT_FILE"
```

`RESULT_FILE` contains exactly the worker result JSON. A non-zero marker exit is a STOP. Never edit the checkbox manually.

Evidence rule: a test-writing, checkpoint, or GATE task is complete only
after its declared verification command or red-state check produced an
observable result. Do not mark such a task [X] from source inspection,
implementation intent, or a generic claim that tests should pass. If the
command is denied, unavailable, or its result cannot be reported, leave the
task unchecked and stop at that task with a precise route.

- Touch only the file named in the task's `path` field. Need to change another file → that's a deviation (see Deviation Rule).
- Never create a file as an empty stub to "fill later" — implement the task's real behavior now. If a task itself says to create a stub, that is its complete deliverable.
- **Test tasks** (TDD): write the test, run it, **confirm it fails** before coding the corresponding implementation. If it passes immediately, flag it — the test may be vacuous.
- **Verification/GATE tasks**: run the project's test command from `plan.md` verbatim; report pass/fail per asserted AC/INV ID named in the gloss. GATE tasks carry EMPTY refs.
- **Infra tasks** (barrels, fixtures, route wiring): carry EMPTY refs by design — execute the wiring/registration, no coverage expected.

#### Checkpoint / STOP & VALIDATE (end of each story phase)

- `order.tasks` represents a checkpoint as prose, not a task. Read the current
  phase's `**Verification**` line and use its declared command and asserted IDs.
  If that line is absent or has no executable command, STOP and route to
  `/order.tasks`; do not invent a verification task or command.
- Run the declared verification command when project governance permits it;
  confirm the story works independently and earlier stories show no regressions.
- On failure: **STOP within this phase**. Fix forward only the tasks of the current story; do not start the next story until the checkpoint passes.

#### GATE before Contract (absolute barrier)

- The GATE task is the first task of the Final Phase. Run the full test command from `plan.md` verbatim; verify all AC pass, INV hold, NFR targets met.
- **On any failure: HALT. Never proceed to Contract** — contraction (deleting code, dropping columns, removing flags, removing scaffolding) is irreversible. Report what failed and stop.

#### Environment Block Handling

Before dispatching or executing a task that depends on a runtime prerequisite,
the coordinator MUST apply `environment-block.md` and run the matching exact
read-only check from `plan.md` when constitution capabilities permit it.

- A passing check permits the task to proceed.
- A denied, unavailable, or failing check is not permission to guess. Stop the
  current task before code changes and before marking it `[X]`.
- Report the shortest decisive error, affected prerequisite, proposed bounded
  recovery option, exact action, side effect, scope, required approval, and
  safe fallback. Ask the user before executing any mutating action.
- Execute only the exact action approved in the current chat, then rerun the
  check. Resume the same task only after it passes. Approval for one action
  does not authorize another.
- If the user refuses or requests default continuation, use the declared safe
  fallback. If it cannot satisfy the task, leave it unchecked and stop with
  `CODE_BLOCKED: environment prerequisite`.
- If a worker reports an unanticipated environment blocker, do not retry it or
  switch execution modes silently. Handle recovery as coordinator work, then
  resume the same task according to the worker protocol.

#### Failure Handling Summary

| Level | On failure |
|---|---|
| Task sub-agent (sequential) | Halt; report task ID, error, suspected cause |
| Task sub-agent (in a concurrent `[P]` group) | Wait for sibling sub-agents already dispatched; mark only successful tasks `[X]`; report failed ones; do not advance past the group |
| Checkpoint | Stay in current story phase; fix forward; re-verify |
| GATE | HALT everything; Contract phase is forbidden until GATE passes |
| Environment prerequisite | Stop current task; ask approval for exact recovery; rerun check; resume only after pass |

#### Deviation Rule

- **Minor mechanical fixes** (typo in a path with an obvious unique match, missing import) — apply, and log one line: `DEVIATION: Tnnn — what changed and why`.
- **Task decomposition defect**: required behavior and every physical path
  already exist in `plan.md`, but the current task/write whitelist omits a
  needed path or an earlier task omitted its planned obligation — STOP and route
  to `/order.tasks`.
- **Plan mapping defect**: a required physical boundary or mechanism is absent
  or wrong in `plan.md` — STOP and route to `/order.plan`, then regenerate
  `tasks.md`.
- **Contract defect**: required externally visible behavior is absent or
  contradictory in `spec.md` — STOP and route to `/order.spec`, then rebuild
  downstream artifacts.
- Do not call a schema edit a plan defect merely because it is a schema edit.
  Classify it by the rules above: if the planned model path and obligation
  already require the fields, the defect is task decomposition; if not, it is
  plan mapping.
- Collect all deviation lines for the Completion Report.

### Step 10: Post-Execution Coverage Check

After all tasks complete (or on halt), run a mechanical coverage check:

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" check-mechanisms
```

- **exit 0** → mechanisms consistent; report success.
- **exit ≠ 0** → read stderr; report the defect. Do NOT silently patch `tasks.md` or `mechanisms.tsv` from `/order.code` — route back to `/order.tasks` if the defect is in task lines, or to `/order.spec` if a mechanism's `primary_files` is wrong.

Note: `extract-trace` validates task line coverage, not `[X]` execution state. Execution-state coverage is the job of `/order.code-check`. Do NOT run `extract-trace` here — it would re-project from task lines and ignore completion markers.

### Step 11: Update Active Feature State

On successful completion of all tasks (or on halt with partial progress), update the active feature status:

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

python3 .orderspec/framework/scripts/active_feature.py set \
  --feature-id "$FEATURE_ID" \
  --feature-directory "$FEATURE_DIR_REL" \
  --status implementing \
  --last-command order.code \
  --json
```

- If all tasks `[X]` and GATE passed → status `implementing` (final transition to `implemented` is the job of `/order.code-check`).
- If halted early → status `implementing` (partial progress preserved for resume).

### Step 12: Mark Gate Report Consumed

If a BLOCK/ROUTING `tasks-report.md` was used as a fix-list in Step 6, mark it consumed:

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
python3 .orderspec/framework/scripts/traceability.py mark-consumed --report "$FEATURE_DIR/tasks-report.md"
```

---

## Progress Reporting (keep it lean)

- After each **phase**: one line — `Phase N: T010–T014 done (1 deviation)`.
- After a concurrent `[P]` group: one line naming the task IDs run together.
- After each **checkpoint/GATE**: verification result with AC/INV IDs pass/fail.
- No per-task narration beyond errors and deviations.

---

## Completion Report

Report to chat:

- **Tasks**: completed / total, per phase; confirm all completed tasks are marked `[X]` by `task_progress.py`.
- **Execution mode**: `DELEGATED`, `LOCAL_PHASE`, or `LOCAL_ALL`; report fallback reason and concurrent `[P]` groups.
- **Sub-agents**: confirm delegated tasks and any local tasks; report sequential fallbacks.
- **Worker selection**: report runtime adapter, worker name, reasoning effort,
  scope, readiness result, and any user configuration step.
- **Coverage check**: `check-mechanisms` exit code (MUST be 0); one-line summary if defects found.
- **Verification**: checkpoint results per story; GATE result; final test command output summary (pass/fail counts).
- **Deviations log**: all `DEVIATION:` lines (or "none").
- **Environment blockers**: prerequisite, observed failure, user-approved recovery or fallback, and outcome (or "none").
- **Library Documentation Evidence**: for each library-specific claim, cite the evidence source (skill name, docs source name, or user-provided reference). If a required source was unavailable, record that and the fallback applied.
- **If halted early**: exact stopping point (phase/task), reason, and the recommended next command (`/order.code` to resume, or `/order.tasks` / `/order.plan` if the failure is a design gap).
- **Active feature status**: updated to `implementing` (or not, with reason).
- **Gate report consumed**: if `tasks-report.md` was marked consumed in Step 12.
- **Manual/orchestrator next step**: Run `/order.code-check` to verify the implementation before considering the feature done.

## Done When

- [ ] Command context resolved via `command_context.py`
- [ ] Every `to_read` file was read and interpreted by `usage`
- [ ] Execution mode detected and stated (`DELEGATED` / `LOCAL_PHASE` / `LOCAL_ALL`); `RESUME` and `--force` recorded separately
- [ ] Worker request resolved through `sub-agent-rules.md`; delegated worker inspected and ready, or local fallback used without configuration
- [ ] Feature paths resolved; `eval` used for shell vars
- [ ] Upstream gate respected: guard returned `ok`/`advisory`/`forced` (not `halt`/`stop`/`error`); on `forced`, a `--force` warning was recorded in the completion report; on `advisory`, user was warned in chat
- [ ] Tooling validated via `validate_tooling.py` (if `tooling-protocol.md` was loaded); missing required skills routed per rule 6, not silently continued
- [ ] Prior gate report consumed (if present and targeting `/order.code`): findings addressed or routed; `mark-consumed` run
- [ ] All tasks executed in phase + task-ID order; each successful marker written by `task_progress.py`, or a precise stopping point reported
- [ ] `[P]` groups run concurrently ONLY after path-disjoint verification via `plan.md` pathmanifest; otherwise sequential
- [ ] All story checkpoints passed; GATE passed before any Contract task ran
- [ ] Environment prerequisites checked before dependent tasks; recovery actions were approval-gated and documented
- [ ] `task_context.py validate` and `task_contract_context.py validate` passed before execution
- [ ] Resume treated applied `[NEW]`/`[DEL]` transitions as expected work-order state; no plan-authoring current-state check was run
- [ ] `check-mechanisms` exited 0 (no coverage defects); defects routed to `/order.tasks` or `/order.spec`, not silently patched
- [ ] Deviations logged and reported; no silent design decisions made
- [ ] Active feature status updated to `implementing`
- [ ] Completion Report provided, including Library Documentation Evidence and manual/orchestrator recommendation to run `/order.code-check`
