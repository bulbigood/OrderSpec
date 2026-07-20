# Continuous execution policy

OrderSpec separates continuous execution into three responsibilities:

1. commands detect defects, completed stages, runtime failures, and questions;
2. a runtime adapter converts the terminal result into a typed automation event;
3. the deterministic supervisor applies operator policy and persists the run.

The model does not decide whether an event may proceed unattended. That decision
belongs to `.orderspec/config/automation.json` and
`framework/scripts/automation_policy.py`.

## Optional by default

Automation ships with `enabled: false`. Set it to `true` only after reviewing
the ordered rules. A disabled policy classifies every event as `PAUSE`; normal
interactive OrderSpec commands continue to work unchanged.

Validate the edited policy:

```bash
python3 .orderspec/framework/scripts/automation_policy.py validate
```

## Events and decisions

Runtime adapters submit one schema-valid event after a command boundary:

For `order.code`, a command boundary exists only after `code_workflow.py finish`
accepts the outcome. The script rejects `open_attempt_boundary` while the
canonical attempt slot is active or accepted but not durably marked and cleaned.
Adapters must execute the sole returned `attempt-recover` command and obey its
state-specific action; they must not construct a recovery list, emit a supervisor
event, or produce a user-visible completion report from that internal state.
`RECONCILE_PREEXISTING` is also internal: it means a retry positively verified
write paths already preserved by a closed prior attempt, or positively verified
work inherited from a completed predecessor owning the same paths. The adapter
executes the returned reconciliation commands in order and continues with
`code_workflow.py next`; it does not emit a runtime failure event.

| Kind | Meaning | Possible automated outcome |
|---|---|---|
| `ADVANCE` | the current stage completed | run the framework-declared next stage |
| `ROUTE` | an evidenced defect belongs to another command | run a legal artifact owner |
| `OPERATOR_INPUT` | the command needs a decision or exact approval | never auto-answer |
| `RUNTIME` | execution infrastructure failed | bounded retry, pause, or stop |
| `COMPLETE` | the declared terminal gate has a canonical PASS report | finish the run |

The classifier returns `AUTO_ROUTE`, `RETRY`, `PAUSE`, `STOP`, or terminal
`COMPLETE`. Rules are evaluated in file order; the first match wins. When no
rule matches, the kind-specific default applies.

The shipped policy automatically routes evidenced, non-destructive upstream
defects from artifact authors as well as gates and implementation commands.
For example, `order.tasks → order.plan` continues without an operator boundary;
the deterministic owner table still rejects illegal source/target pairs.

Event reasons are kind-specific rather than arbitrary labels. `ADVANCE` uses
`STAGE_COMPLETE`; routes use `ARTIFACT_DEFECT`, `UPSTREAM_DEFECT`, or the
code-to-tasks `IMPLEMENTATION_REPAIR`; runtime
failures use `TRANSIENT_FAILURE` or `FRAMEWORK_ERROR`; terminal completion uses
`WORKFLOW_COMPLETE`. Routes require non-empty evidence.

The supervisor, not the event producer, owns lifecycle legality. It checks every
command against the framework registry, every `ADVANCE` against the canonical
pipeline, and every `ROUTE` against the source command's legal artifact owners.
An `order.*`-shaped unknown command is invalid.

Example routed defect:

```json
{
  "version": 1,
  "id": "EVT-001",
  "kind": "ROUTE",
  "reason": "UPSTREAM_DEFECT",
  "source": "order.code-check",
  "target": "order.plan",
  "severity": "HIGH",
  "destructive": false,
  "summary": "The physical mapping omits a required boundary.",
  "evidence": "code-report.md finding C1-deadbeef"
}
```

Classify it from a file or stdin:

```bash
python3 .orderspec/framework/scripts/automation_policy.py classify \
  --event-file event.json
```

## Operator interrupts

`OPERATOR_INPUT` is distinct from routing. Runtime adapters never hand-author
it. The canonical constructor binds it to the current run command, validates
the reason, requires stable choice tokens plus a human-readable label and
consequence for each token, and persists one bounded question:

```bash
python3 .orderspec/framework/scripts/workflow_supervisor.py ask \
  --run-file <run-file> --source order.code \
  --reason MUTATION_APPROVAL --interaction-id INT-001 \
  --question "Start the local database?" \
  --choice approve "Start database" "Start the configured local database; this mutates the local environment." \
  --choice deny "Do not start database" "Leave the local environment unchanged and stop this execution path." \
  --exact-action "docker compose up -d database" --destructive
```

Semantic decisions, scope clarification, mutations, tool installation,
governance changes, candidate selection, work-order reset, credentials, and
permissions cannot produce `AUTO_ROUTE` or `RETRY`. The classifier overrides an
unsafe matching rule with `PAUSE`. Destructive events receive the same
protection. Configuration controls pause versus stop; it is not an approval.

## Persistent runs

Atomically create or recover a feature-scoped run-state:

```bash
python3 .orderspec/framework/scripts/workflow_supervisor.py acquire \
  --feature-dir .orderspec/features/<feature> \
  --command order.code-check \
  --terminal-command order.code-check
```

`STARTED_RUN` creates a lease; `RESUME_RUN` returns the newest unfinished lease
for the same root command and terminal gate only when it was created after the
latest terminal run. Older RUNNING leases are superseded by a later `STOPPED`
or `COMPLETE` boundary. This makes a host-interrupted turn resumable without a
synthetic runtime event or duplicate run. Concurrent
acquires serialize on the run store and return one lease. `OPERATOR_BOUNDARY`
never auto-resumes `PAUSED` or `WAITING_OPERATOR` state.

Destructive maintenance controls are outside continuous execution. In
particular, explicit `order.code --reset` authorizes and applies its bounded
rollback without `acquire` or a second confirmation; otherwise the supervisor's
normal `--resume` continuation would erase the operator's reset intent and
leave a maintenance-only RUNNING lease.

The command returns a `run_file`. `evaluate` remains the low-level path for
typed events without a canonical constructor:

```bash
python3 .orderspec/framework/scripts/workflow_supervisor.py evaluate \
  --run-file <run-file> --event-file <event.json>
```

For normal stage completion, adapters use the canonical constructor instead of
manually assembling an `ADVANCE` event:

```bash
python3 .orderspec/framework/scripts/workflow_supervisor.py advance \
  --run-file <run-file> --source order.<completed-command> \
  --summary "<completed stage evidence>"
```

The explicit source binds the event to the command that produced the completion
evidence; the supervisor rejects a stale or repeated call after state has moved
to another command. It derives `target` from the canonical pipeline. Adapters
submit one transition at a time and execute its returned `next_action` before
constructing another event; they never batch transitions across command
boundaries. An `order.code` ADVANCE is additionally rejected while any task is
unchecked. On acquire, a persisted legacy `order.code -> order.code-check`
transition with unchecked tasks is deterministically reconciled back to
`order.code --resume`.

For a persisted cross-owner feedback item, adapters likewise use the canonical
route constructor instead of translating feedback fields into an event:

```bash
python3 .orderspec/framework/scripts/workflow_supervisor.py route-feedback \
  --run-file <run-file> --feedback-file <FB-NNN.json>
```

The command validates the feedback store and open status, derives the ROUTE
event, applies policy, and returns either an exact `next_action` for
`AUTO_ROUTE` or an exact `operator_action` for `PAUSE`/`STOP`.

`ADVANCE`, persisted `ROUTE`, and `OPERATOR_INPUT` therefore use `advance`,
`route-feedback`, and `ask` respectively. A direct invalid event returns
`CALLER_EVENT_INVALID`, `state_mutated:false`, the allowed enum values,
`continuation_required:true`, and `final_response.permitted:false`. It is a
caller transport error, not a framework stop. A schema failure produced by a
canonical constructor is reported separately as `FRAMEWORK_ADAPTER_FAILURE`.

Every event response is self-describing. `RUNNING` always returns
`terminal:false`, `continuation_required:true`, the exact next command, and
`final_response.permitted:false`. It intentionally omits `operator_action` so a
healthy continuation cannot be presented as a host interruption. Terminal
decisions return `terminal:true` and `continuation_required:false`. Command-internal setup,
mechanical validation, and unfinished report output never substitute for this
supervisor boundary payload.

Before any user-visible final response, adapters inspect the retained run.
`RUNNING` requires immediate execution of `next_action`; a terminal operator
report copies every ordered `operator_action.recommended_commands` entry when
present, otherwise its singular `recommended_command`.

A real host interruption produces no agent-authored final response. A later
diagnostic may request the exact recovery command with
`workflow_supervisor.py status --operator-recovery`; normal execution and the
mandatory pre-final status check must not use that flag.

An operator interrupt changes the state to `WAITING_OPERATOR`. Its
`operator_action` contains structured `choices`, `recommended_replies`, and one
exact `answer_commands` entry per mutually exclusive reply. The runtime adapter
renders the question, labels, and consequences in the user's configured
language while preserving reply tokens and commands verbatim. The operator
replies with exactly one stable token; the runtime adapter invokes only the
corresponding command:

```bash
python3 .orderspec/framework/scripts/workflow_supervisor.py answer \
  --run-file <run-file> --interaction-id INT-001 --answer approve
```

The answer returns a healthy non-terminal payload with `resume_input`, an exact
`next_action`, and `final_response.permitted:false`. It sets
`session_mode=resume` for `same_session`; normal cross-command
transitions use `context.between_commands`, which defaults to `fresh`. Run files
live under feature `.state/runs/`, or project `.orderspec/state/runs/` before a
feature exists. Run IDs use exclusive random filenames, so concurrent starts
cannot overwrite each other. Run files are ignored local state but survive
process restarts.

A policy or loop-limit `PAUSE` is an enforced barrier: `evaluate` accepts events
only in `RUNNING`. Its `operator_action.recommended_commands` is a complete
recovery sequence: the first command explicitly accepts the pending transition,
and the second resumes the root runtime adapter. After reviewing the cause, the
operator explicitly resumes, for example:

```bash
python3 .orderspec/framework/scripts/workflow_supervisor.py resume \
  --run-file <run-file> --reason "reviewed loop-limit evidence"
```

For a paused legal `ROUTE` or `ADVANCE`, `resume` atomically applies that pending
transition, returns the exact owner/next command, and leaves the run `RUNNING`.
It never returns to the source command and silently loses the approved route.

`COMPLETE` is accepted only from the `terminal_command` declared at start. Its
`evidence` must reference that gate's canonical feature report
(`spec-report.md`, `plan-report.md`, `tasks-report.md`, or `code-report.md`),
whose command metadata and `verdict: PASS` are checked mechanically. A prose
claim of completion is insufficient.

## Loop protection

The policy independently limits total automatic transitions, routed
transitions, repetitions of the same semantic defect/runtime event, and
per-rule occurrences of that same event. A `ROUTE` fingerprint includes its
normalized summary and evidence, so unrelated defects between the same command
pair do not collide. Repeated `ADVANCE` transitions are not same-event cycles;
the routed defect that caused a return through the pipeline owns cycle identity.
Crossing a limit produces `PAUSE`, never an unbounded retry.

On acquire, a `PAUSED` legal transition is reclassified from its persisted
evidence against the current policy. This repairs both a newly automated route
after a policy update and a legacy route that collided under the old structural
fingerprint. The supervisor records `PAUSED_TRANSITION_RECLASSIFIED` or
`LEGACY_EVENT_FINGERPRINT_COLLISION` and continues at the target without
operator intervention. Limits are recomputed without the rejected occurrence,
so a genuinely repeated semantic defect remains paused.
`FRAMEWORK_ERROR` always produces `STOP`; it is not routed to an artifact owner.

`IMPLEMENTATION_REPAIR` means the frozen contract is still valid but a code
gate exposed incomplete implementation. `/order.tasks` handles it additively:
completed task lines remain immutable and bounded pending correction tasks are
inserted before the failed `@verify` task.

Before any user-visible final response, an automated command calls
`workflow_supervisor.py guard-final --run-file <run>`. A RUNNING lease returns
`CONTINUE_REQUIRED` and a concrete next command with non-zero status; only a
terminal lease returns `FINAL_RESPONSE_PERMITTED`. Host-level enforcement
remains the adapter's responsibility, while this framework boundary fails
closed whenever it is invoked.

## Runtime adapter boundary

The supervisor core is runtime-neutral and does not parse prose transcripts.
An agent adapter is responsible for starting a fresh or resumed agent session,
enforcing the automation-event output schema, and submitting the validated
event. Schema validity is the transport contract; the supervisor additionally
checks state-dependent transition, ownership, pause, and terminal-evidence
invariants. This keeps Codex, Claude Code, and Kilo invocation details outside
the workflow policy.

The synchronized Codex `order-code` skill provides this adapter loop for runs
started with `order.code`: while automation is enabled, its coordinator retains
the supervisor run, executes allowed owner/gate transitions, and resumes
`order.code` without ending the agent turn. Other entry commands and runtimes
still require their own runtime adapter.
