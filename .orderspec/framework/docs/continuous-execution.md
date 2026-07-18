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

Event reasons are kind-specific rather than arbitrary labels. `ADVANCE` uses
`STAGE_COMPLETE`; routes use `ARTIFACT_DEFECT` or `UPSTREAM_DEFECT`; runtime
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

`OPERATOR_INPUT` is distinct from routing. It contains a stable interaction ID,
one bounded question, a `choice` or free-form `text` response contract, and the
required resume strategy:

```json
{
  "version": 1,
  "id": "EVT-002",
  "kind": "OPERATOR_INPUT",
  "reason": "MUTATION_APPROVAL",
  "source": "order.code",
  "interaction": {
    "id": "INT-001",
    "kind": "MUTATION_APPROVAL",
    "question": "Start the local database?",
    "response_type": "choice",
    "options": ["approve", "deny"],
    "exact_action": "docker compose up -d database",
    "resume_strategy": "same_session"
  }
}
```

Semantic decisions, scope clarification, mutations, tool installation,
governance changes, candidate selection, work-order reset, credentials, and
permissions cannot produce `AUTO_ROUTE` or `RETRY`. The classifier overrides an
unsafe matching rule with `PAUSE`. Destructive events receive the same
protection. Configuration controls pause versus stop; it is not an approval.

## Persistent runs

Start a feature-scoped run-state:

```bash
python3 .orderspec/framework/scripts/workflow_supervisor.py start \
  --feature-dir .orderspec/features/<feature> \
  --command order.code-check \
  --terminal-command order.code-check
```

The command returns a `run_file`. Runtime adapters submit events through:

```bash
python3 .orderspec/framework/scripts/workflow_supervisor.py evaluate \
  --run-file <run-file> --event-file <event.json>
```

An operator interrupt changes the state to `WAITING_OPERATOR`. Resume it with
one of the declared options:

```bash
python3 .orderspec/framework/scripts/workflow_supervisor.py answer \
  --run-file <run-file> --interaction-id INT-001 --answer approve
```

The answer sets `session_mode=resume` for `same_session`; normal cross-command
transitions use `context.between_commands`, which defaults to `fresh`. Run files
live under feature `.state/runs/`, or project `.orderspec/state/runs/` before a
feature exists. Run IDs use exclusive random filenames, so concurrent starts
cannot overwrite each other. Run files are ignored local state but survive
process restarts.

A policy or loop-limit `PAUSE` is an enforced barrier: `evaluate` accepts events
only in `RUNNING`. After reviewing the cause, the operator explicitly resumes:

```bash
python3 .orderspec/framework/scripts/workflow_supervisor.py resume \
  --run-file <run-file> --reason "reviewed loop-limit evidence"
```

`COMPLETE` is accepted only from the `terminal_command` declared at start. Its
`evidence` must reference that gate's canonical feature report
(`spec-report.md`, `plan-report.md`, `tasks-report.md`, or `code-report.md`),
whose command metadata and `verdict: PASS` are checked mechanically. A prose
claim of completion is insufficient.

## Loop protection

The policy independently limits total automatic transitions, routed
transitions, repetitions of the same typed event, and occurrences of individual
rules. Crossing a limit produces `PAUSE`, never an unbounded retry.
`FRAMEWORK_ERROR` always produces `STOP`; it is not routed to an artifact owner.

## Runtime adapter boundary

The supervisor core is runtime-neutral and does not parse prose transcripts.
An agent adapter is responsible for starting a fresh or resumed agent session,
enforcing the automation-event output schema, and submitting the validated
event. Schema validity is the transport contract; the supervisor additionally
checks state-dependent transition, ownership, pause, and terminal-evidence
invariants. This keeps Codex, Claude Code, and Kilo invocation details outside
the workflow policy.
