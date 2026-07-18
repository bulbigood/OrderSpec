---
orderspec:
  artifact: command_prompt
  command: order.code
  phase: implement
description: Execute a frozen work order through deterministic state transitions and bounded semantic task packets.
---

## User Input

```text
$ARGUMENTS
```

Apply non-empty input when selecting execution controls. User prohibition of delegation always wins.

## Contract

`/order.code` implements an existing work order. It makes no contract,
architecture, mapping, or task-decomposition decisions. Local coding choices
are allowed only inside the resolved task packet and project constraints.

- `spec.md` owns WHAT; `plan.md` owns WHERE/HOW; `tasks.md` owns ORDER.
- `code_workflow.py` owns mechanical preflight, task selection, packet
  construction, completeness, coverage, and status transitions.
- The executor performs one bounded semantic task and returns evidence.
- A change outside `task_context.write_paths` is a deviation, including a
  missing import or mechanical repair in another path.
- Framework script output is authoritative. On non-zero or malformed output,
  follow its reported action or route the input defect to its owner. Never
  repair an unowned input or rewrite a rejected result.
- Applied `[NEW]` and `[DEL]` transitions are expected work-order state. Never run plan-authoring current-state checks from this command.

## Step 1 — Resolve Context

Run first:

```bash
python3 .orderspec/framework/scripts/command_context.py resolve order.code --json
```

If `ok` is false or `missing_required` is non-empty, stop. Read every `to_read`
item in order and interpret its `usage` and `authority` literally. Reuse loaded
feature artifacts; do not reopen them.

Apply the resolved tooling protocol before library-specific implementation.

## Step 2 — Select Mode

State one mode before mutation:

- `RESET`: `--reset`; incompatible with every implementation mode.
- `LOCAL_PHASE`: `--phase`; execute the first incomplete phase.
- `DELEGATED`: `--delegated`, only when runtime dispatch and wait exist and the
  user permits delegation.
- `LOCAL_ALL`: default or `--all`; **`--local` / `--no-subagents`** and any
  natural-language single-agent constraint force it; delegated mode falls back
  to it when dispatch is unavailable.

`--force` affects only the upstream gate. `--resume` is the normal behavior in
every implementation mode: completed `[X]` tasks stay untouched.

Local constraints are resolved before capability detection. In local modes do
not inspect, configure, dispatch, or wait for a worker.

For `DELEGATED`, inspect the requested worker through the current runtime
adapter and continue only under the adapter-owned rules injected below by
`agents_sync.py sync`. Never infer runtime identity from `agents.json` or
silently create global configuration.

<!-- ORDERSPEC:ADAPTER_SUBAGENT_RULES -->

## Step 3 — Deterministic Preflight

Run, adding `--force` only when explicitly supplied:

```bash
python3 .orderspec/framework/scripts/code_workflow.py preflight \
  --mode "$MODE" $FORCE_FLAG
```

Obey `action`:

- `STOP`: write no code; report `error`, evidence, and `route`.
- `RESET_PREVIEW`: follow Reset below.
- `READY`: report task receipt from `total`, `first_unchecked`, and
  `phase_count`; retain `selected_phase` for `LOCAL_PHASE`.
- `COMPLETE`: skip execution and continue to terminal validation.

Preflight deterministically handles active paths, missing plan/tasks, upstream
gate state, task format, task context, and contract-context completeness. Do
not repeat those checks manually. Record a forced or advisory gate result in
the final report.

### Reset

Run the exact preview command returned by preflight. Show every restore/delete
action and obtain explicit operator approval. On approval, append `--apply` to
that exact command. On refusal, stop without writes. Never use broad Git cleanup,
checkout, inferred deletion, or another rollback target. After successful apply,
report restored/deleted paths and end.

## Step 4 — Execute Returned Packets

Request the next execution unit:

```bash
python3 .orderspec/framework/scripts/code_workflow.py next \
  --mode "$MODE" \
  --feature-dir "$FEATURE_DIR" \
  $SELECTED_PHASE_FLAG
```

For `LOCAL_PHASE`, `SELECTED_PHASE_FLAG` is the exact preflight value as
`--selected-phase <value>`. Obey `action`:

- `EXECUTE_TASK`: execute the sole packet locally or in one worker.
- `EXECUTE_TASK_GROUP`: dispatch one worker per returned packet concurrently;
  wait for all. This action is emitted only for adjacent, unchecked, same-phase
  `[P]` tasks with distinct paths. If any non-file dependency or shared state is
  uncertain, execute returned packets sequentially.
- `PHASE_COMPLETE`: run terminal validation with `PHASE_COMPLETE`.
- `COMPLETE`: run terminal validation with `COMPLETE`.
- `STOP`: leave the task unchecked and route the reported defect.

Apply loaded `sub-agent-execution.md` exactly. Both local and delegated
execution receive only the returned packet, including exact `task_context` and
`contract_context`. Do not open full `spec.md`, scan the repository, add read
paths, expand write paths, or infer missing requirements.

Workers are literal bounded implementers. They cannot mutate the environment,
edit checkboxes, start workers, or advance tasks. The coordinator owns
environment recovery, result validation, verification, and progress updates.

### Result and Progress

Return exactly:

```json
{
  "task_id": "T###",
  "status": "SUCCESS|FAILED|BLOCKED|NEEDS_CONTEXT",
  "changed_files": ["repo/relative/path"],
  "verification": {"status": "PASS|FAIL|NOT_RUN", "evidence": "observable result"},
  "deviation": null
}
```

The coordinator compares task-start and task-end state, runs the packet's
declared verification when project governance permits it, then submits the
unaltered JSON:

```bash
python3 .orderspec/framework/scripts/task_progress.py mark \
  --tasks "$FEATURE_DIR/tasks.md" --result-file "$RESULT_FILE"
```

A rejected result is terminal for this run. Preserve it and the exact error.
Never alter `changed_files`, `deviation`, evidence, or task path and retry.

An unchecked task already fully satisfied before this task attempt may use
`ALREADY_COMPLETE` only after exact deliverable inspection and positive
verification with no current-run write:

```json
{
  "task_id": "T###",
  "status": "ALREADY_COMPLETE",
  "changed_files": [],
  "verification": {"status": "PASS", "evidence": "exact command/result"},
  "observed_state": "exact deliverable evidence",
  "deviation": null
}
```

Submit it once through `task_progress.py reconcile`. File presence alone is
insufficient.

After every accepted task, call `code_workflow.py next` again. `LOCAL_ALL` and
`DELEGATED` continue until `COMPLETE` or a named STOP/HALT condition occurs.
Task count, elapsed work, context size, token/tool budget, convenient batch size,
and resumability are not completion boundaries.

### Verification Rules

- Test-writing tasks must run permitted evidence and observe the result declared
  by plan Evidence Sequencing. A mismatch is routed to `/order.tasks` or
  `/order.plan`; never manufacture a red state.
- `VERIFY:` and `GATE:` packets are read-only and report `changed_files: []`.
- A task requiring verification cannot complete from source inspection or
  intent. Denied/unavailable required execution leaves it unchecked and routes
  the capability/topology defect reported by the packet and project contracts.
- Phase verification must pass before the next phase.
- The final Contract GATE must pass before any contraction task. On failure,
  HALT; never perform deletion or contraction.

### Environment Blockers

Apply loaded `environment-block.md`. Stop before task writes, show the shortest
decisive error, exact bounded recovery action, side effect, scope, and fallback.
Obtain approval for each mutating action. Rerun the declared readiness check and
resume the same task only after success. Approval never amends an artifact.

### Deviations and Routing

Classify by owner:

- required path/mechanism exists in plan but task packet omits it: `/order.tasks`;
- required physical mapping is absent or wrong: `/order.plan`, then regenerate tasks;
- required external behavior is absent or contradictory: `/order.spec`;
- project capability/contract is absent or contradictory: `/order.bootstrap`.

Before every upstream route, persist one typed report:

```bash
python3 .orderspec/framework/scripts/workflow_feedback.py create \
  --feature-dir "$FEATURE_DIR" --input-file "$FEEDBACK_INPUT_FILE"
```

Use the exact observed evidence. Do not claim to invoke the owner command.

## Step 5 — Terminal Validation

For normal completion or phase completion:

```bash
python3 .orderspec/framework/scripts/code_workflow.py finish \
  --mode "$MODE" --feature-dir "$FEATURE_DIR" --outcome "$OUTCOME"
```

For an evidenced stop, persist required feedback first when routed upstream,
then use `--outcome HALTED`.

Obey `action`:

- `CONTINUE`: return to Step 4 at `first_unchecked`; no completion report.
- `STOP`: route the deterministic coverage/status defect.
- `COMPLETE`, `PHASE_COMPLETE`, or `HALTED`: report returned state.

The script owns full-work-order completeness, mechanism coverage, and active
feature status. Do not repeat or override them manually. A tasks gate report is
not consumed by `/order.code`; its artifact owner must repair and consume it.

## Completion Report

Keep chat output lean:

- mode; completed/total; phase boundary or exact halt evidence;
- forced/advisory upstream-gate state;
- delegated worker and concurrent groups, when used;
- verification/GATE outcomes;
- deviations, environment recovery, and feedback report paths;
- terminal coverage and active-feature result;
- next action: `/order.code-check` only after complete implementation, otherwise
  the exact routed owner command or `/order.code` resume.
