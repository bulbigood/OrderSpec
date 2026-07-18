---
orderspec:
  artifact: command_prompt
  command: order.code
  phase: implement
description: Execute a frozen work order through deterministic state transitions and bounded semantic worker envelopes.
---

## User Input

```text
$ARGUMENTS
```

Apply non-empty input when selecting execution controls. User prohibition of delegation always wins.

## Contract

`/order.code` implements an existing work order. It makes no contract,
architecture, mapping, or task-decomposition decisions. Local coding choices
are allowed only inside the resolved task envelope and project constraints.

- `spec.md` owns WHAT; `plan.md` owns WHERE/HOW; `tasks.md` owns ORDER.
- `code_workflow.py` owns mechanical preflight, task selection, envelope
  construction, attempt snapshots, completeness, coverage, and status transitions.
- The executor performs one bounded semantic task and returns evidence.
- A change outside `task_context.write_paths` is a deviation, including a
  missing import or mechanical repair in another path.
- Framework script output is authoritative. On non-zero or malformed output,
  follow its reported action or route the input defect to its owner. Never
  repair an unowned input or rewrite a rejected result.
- Applied `[NEW]` and `[DEL]` transitions are expected work-order state. Never run plan-authoring current-state checks from this command.

### Turn termination contract

For `LOCAL_ALL` and `DELEGATED`, do not end the turn while the latest framework
payload has `continuation_required: true` or `terminal: false`. `READY`,
`EXECUTE_TASK`, `EXECUTE_TASK_GROUP`, `DISPATCH`, `READY_TO_VERIFY_AND_MARK`,
`ATTEMPT_CLEANED`, `CONTINUE`, and pre-validation `COMPLETE` are internal states,
not user-visible stopping points. Execute `next_action` immediately. A progress
update such as "ready at T008" is never a final response.

End only after a framework payload has `terminal: true`: `STOP`, `HALTED`,
`RESET_PREVIEW` awaiting approval, or the result of terminal validation
(`COMPLETE`/`PHASE_COMPLETE`). The words `continue`, `resume`, and the default
`LOCAL_ALL` request mean continue through all internal states to one of these
terminal outcomes.

## Step 1 — Resolve Context

Run first:

```bash
python3 .orderspec/framework/scripts/command_context.py resolve order.code \
  --arguments "$ARGUMENTS" --json
```

If `ok` is false or `missing_required` is non-empty, stop. Read every `to_read`
item in order and interpret its `usage` and `authority` literally. Reuse loaded
feature artifacts; do not reopen them.

Use only returned `input.controls` and `input.semantic_input`; do not parse raw
input again.

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

## Step 4 — Execute Returned Envelopes

Request the next execution unit:

```bash
python3 .orderspec/framework/scripts/code_workflow.py next \
  --mode "$MODE" \
  --feature-dir "$FEATURE_DIR" \
  $SELECTED_PHASE_FLAG
```

For `LOCAL_PHASE`, `SELECTED_PHASE_FLAG` is the exact preflight value as
`--selected-phase <value>`. Obey `action`:

- `EXECUTE_TASK`: execute the sole `worker_envelope` locally or in one worker.
- `EXECUTE_TASK_GROUP`: dispatch one worker per returned envelope concurrently;
  wait for all. This action is emitted only for adjacent, unchecked, same-phase
  `[P]` tasks with distinct paths. If any non-file dependency or shared state is
  uncertain, execute returned envelopes sequentially.
- `PHASE_COMPLETE`: run terminal validation with `PHASE_COMPLETE`.
- `COMPLETE`: run terminal validation with `COMPLETE`.
- `STOP`: leave the task unchecked and route the reported defect.

Before any task write, start the exact returned execution unit:

```bash
python3 .orderspec/framework/scripts/code_workflow.py attempt-begin \
  --mode "$MODE" --feature-dir "$FEATURE_DIR" \
  $SELECTED_PHASE_FLAG --task-id <T###> [--task-id <T###>]
```

Task IDs MUST be in returned order. Obey only the `worker_envelopes` returned
by `attempt-begin`; dispatch or execute each complete envelope verbatim without
summarizing, augmenting, or translating it. The envelope is self-contained and
schema-versioned. Do not send the worker this command prompt, framework
protocol files, full feature artifacts, or coordinator commentary.

Both local and delegated execution receive the same envelope, including exact
`task_context` and `contract_context`. Do not open full `spec.md`, scan the
repository, add read paths, expand write paths, or infer missing requirements.

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

Write the worker result object, or ordered result array for a group, to the exact
`results_file` returned by `attempt-begin`. Then run:

```bash
python3 .orderspec/framework/scripts/code_workflow.py attempt-finish \
  --feature-dir "$FEATURE_DIR" --attempt-id "$ATTEMPT_ID" \
  --results-file "$RESULT_FILE"
```

The attempt script compares repository state against its task-start snapshot,
rejects undeclared writes and false `changed_files`, and returns
`READY_TO_VERIFY_AND_MARK` only for successful workers. Rejection is terminal.
After acceptance, run the envelope's declared verification when project
governance permits it, then submit each original, unaltered result JSON:

```bash
python3 .orderspec/framework/scripts/task_progress.py mark \
  --tasks "$FEATURE_DIR/tasks.md" --result-file "$RESULT_FILE"
```

After every result in the accepted execution unit is marked `[X]`, remove its
successful transient snapshot and result pair:

```bash
python3 .orderspec/framework/scripts/code_workflow.py attempt-cleanup \
  --feature-dir "$FEATURE_DIR" --attempt-id "$ATTEMPT_ID"
```

Cleanup is permitted only after every task owned by the attempt is marked. A
failed, blocked, rejected, interrupted, or otherwise unmarked attempt remains
in `.state/code-attempts/` as local diagnostic evidence and is not committed.

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
- `VERIFY:` and `GATE:` envelopes are read-only and report `changed_files: []`.
- A task requiring verification cannot complete from source inspection or
  intent. Denied/unavailable required execution leaves it unchecked and routes
  the capability/topology defect reported by the envelope and project contracts.
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

- required path/mechanism exists in plan but task envelope omits it: `/order.tasks`;
- required physical mapping is absent or wrong: `/order.plan`, then regenerate tasks;
- required external behavior is absent or contradictory: `/order.spec`;
- project capability/contract is absent or contradictory: `/order.bootstrap`.

Before every upstream route, persist one typed report:

```bash
python3 .orderspec/framework/scripts/workflow_feedback.py create \
  --feature-dir "$FEATURE_DIR" --input-file - <<'JSON'
{"source":"order.code","target":"order.<owner>","category":"<category>","summary":"<summary>","evidence":"<evidence>","location":"<location>","requested_change":"<bounded change>"}
JSON
```

Use the exact observed evidence. Do not claim to invoke the owner command.

Close the active attempt with its original worker result before creating this
feedback report. A `FAILED`, `BLOCKED`, or `NEEDS_CONTEXT` result is expected to
make `attempt-finish` return a terminal worker failure; only after that return
may the coordinator create feedback. Never create feedback input or report files
during the attempt snapshot. Pass input through standard input as shown.
Framework bookkeeping must not become an unexpected task write.

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

Treat `terminal` and `continuation_required` as authoritative. Never turn an
internal payload into a completion report, even when the next task is ready and
no attempt has started yet.

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
