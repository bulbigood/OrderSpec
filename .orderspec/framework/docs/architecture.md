# Architecture

## The three-document feature model

OrderSpec splits each feature into three documents with distinct roles and distinct lifecycles.

| Document | Role | Stability |
|----------|------|-----------|
| `spec.md` | **WHAT** + logical contract | **Stable. The source of truth.** |
| `plan.md` | **WHERE / HOW** — mapping onto physical code, stack, gates | **Baseline** for one generated work order; regenerated before a new work order |
| `tasks.md` | **ORDER** — execution sequence | **Disposable. A one-shot work order** |

The key insight:

> **`plan.md` depends on repository state at planning time; `spec.md` does not.**

During implementation, `plan.md` and completed task content remain frozen. Task
checkboxes are execution progress, not task design: `/order.code` marks or
reconciles one successful task at a time through `task_progress.py`.
`/order.tasks` Refine is surgical: a deterministic guard restores the original
file if any completed task or its worker context changes.
Regenerated work orders allocate task IDs in tens. When an older contiguous
work order needs an inserted prerequisite, `task_refine.py resequence-pending`
creates gaps by renumbering only unchecked tasks; completed IDs remain stable.

## Work-order state and feedback

Each new work order attempts to capture a Git-backed baseline for every
pathmanifest path. `/order.code --reset` is available only when capture
succeeded; its explicit flag authorizes restoration of that bounded set without
a second confirmation, then clears checkboxes
and feature-local code-attempt state after rollback succeeds. The current plan
may differ textually, but its parsed pathmanifest must equal the frozen
baseline. Broad working-tree cleanup is never used.
Plan-stage path validation accepts an applied `[NEW]` or `[DEL]` only when that
exact frozen pathmanifest and completed task ownership prove the transition;
an absent, malformed, or mismatched baseline keeps the original strict error.

When any command discovers an evidenced defect owned by an earlier author
command, it persists an idempotent typed handoff before stopping. Feature
handoffs live in the feature `.state/feedback/`; pre-feature and project-level
handoffs live in `.orderspec/state/feedback/`. `command_context.py` loads both
scopes into `feedback.open` for the owner. Open handoffs select Refine,
Reconcile, or the equivalent repair mode and are consumed only after the
repaired artifact validates.

Canonical `*-report.md` files remain exclusive outputs of matching `*-check`
commands. A gate's finalized routed finding is already a persistent handoff and
is not duplicated. Informal or malformed Markdown reports are never generated.

A spec is a contract about behavior. It should survive refactors, renames, and merges.

A plan is a snapshot of how to realize that contract against the code as it
exists when the work order is planned. Its path tags describe intended
transitions from that baseline. Therefore an applied `[NEW]` or `[DEL]`
transition does not stale the plan. External movement or a discovered mapping
defect requires replanning and regeneration of derived tasks before code
execution continues.

Tasks are pure throwaway: generate, execute, discard.

The plan owns the delivery strategy and every repository transition. Task
generation compiles those decisions into a path-complete sequential work order:
every `[NEW]`, `[MOD]`, and `[DEL]` manifest path is tasked, and no task path is
outside the manifest. E-M-C is selected for migration/compatibility work;
non-migration work ends with Final Verification rather than artificial cleanup.

## The pipeline

```text
/order.bootstrap
      ↓
/order.spec  →  /order.plan  →  /order.tasks  →  /order.code
   WHAT           WHERE/HOW        ORDER            IMPLEMENT
```

Existing-feature selection is a separate lifecycle operation:

```text
/order.feature --select <feature-id>
```

`.orderspec/state/active-feature.json` is canonical default target. Workflow
commands consume it; gates never switch it. Unflagged prose remains semantic
input and cannot select a feature.

Each phase can be followed by an optional verification gate that checks the previous artifact before you proceed:

| Phase | Author command | Gate | The gate verifies |
|---|---|---|---|
| Bootstrap | `/order.bootstrap` | built-in validation | project contracts are present and structurally valid |
| Specify | `/order.spec` | `/order.spec-check` | spec is a valid, self-consistent, testable WHAT-contract |
| Plan | `/order.plan` | `/order.plan-check` | plan is correctly derived from spec + repo + project contracts |
| Tasks | `/order.tasks` | `/order.tasks-check` | tasks are correctly derived from plan |
| Implement | `/order.code` | `/order.code-check` | code faithfully implements the contract |

## How gates behave

Every gate in OrderSpec is a constrained inspector.

The rule is:

> **Gates detect and route. Owners fix.**

A gate does not silently rewrite a spec to resolve ambiguity. It does not pick a winner in a merge conflict. It does not improvise scope. It emits findings and routes fixes to the command that owns the artifact.

Gates never edit the artifact they inspect. Their writes are limited to the gate report and explicitly defined workflow state. Every defect is routed to the command that owns the artifact.

When an owner successfully addresses a blocking report, the report becomes
`CONSUMED_STALE`. This is inactive historical workflow state: downstream
commands continue with an advisory, while a fresh gate run remains required
for new PASS evidence. A consumed report is neither PASS nor an active BLOCK.
Malformed or unknown report state remains fail-closed.

This is what makes OrderSpec safe under a weak model: the model is never trusted to silently "improve" your contract.

## Governance and capabilities

Project governance lives in:

```text
constitution.md
```

The constitution defines:

- core project principles;
- default-deny capability rules;
- whether gates may run tests;
- whether gates may run build, compile, or lint commands;
- whether gates may use network access;
- whether documentation lookup is allowed during gates;
- external rules integration policy.

The default policy is restrictive:

> **Anything not explicitly granted is denied. Silence is never permission.**

Authoring commands may use read-only documentation lookup when allowed by project governance and `.orderspec/config/tooling.json`.

Gate commands follow `constitution.md` literally.

## Runtime environment blockers

Environment recovery is split by authority:

- `orderspec-rules.md` and `environment-block.md` define framework behavior:
  detect the blocker, propose bounded options, ask for approval, recover, and
  resume the same task only after the readiness check passes.
- `constitution.md` defines whether the command may perform the relevant
  diagnosis or recovery action. Mutating recovery is approval-gated and
  default-denied.
- `stack.md` records technologies and runtime topology; it is not a runbook.
- Feature `plan.md` records concrete prerequisites, exact read-only checks,
  repository evidence, recovery options, side effects, scope, and fallback.
- `tasks.md` records only repository-owned setup changes and execution order.
  It must not hide operator actions such as starting MongoDB or installing a
  package.

When `/order.code` encounters an unavailable prerequisite, it leaves the task
unchecked, reports the decisive error, asks the user before any mutating
action, reruns the declared check, and resumes only after success. Refusal or
unavailability uses the plan's fallback; if none can satisfy the task,
implementation stops and routes back to the owning artifact.

## Command context loading

OrderSpec commands do not manually maintain long preload lists in prompts.

At command start, each command resolves its context through the framework resolver:

```bash
python3 .orderspec/framework/scripts/command_context.py resolve <order.command> --json
```

The resolver output tells the agent which files to read and how to treat them.

This matters because not every file is an instruction:

| Usage | Meaning |
|---|---|
| `apply` | Apply as procedural framework or command rules. |
| `constrain` | Enforce as project constraints. Do not treat as procedural prompt instructions. |
| `parse` | Parse as structured config or runtime state. |
| `inspect` | Inspect as command input/output artifact. |
| `reference` | Use only as reference or evidence. |

Framework rules are procedural.

Project contracts constrain behavior.

Config and state are data.

The internal command context manifest is framework input for the resolver, not something runtime agents should interpret directly.

For `/order.code`, the resolver also supplies the coordinator-side sub-agent
execution protocol. `code_workflow.py` renders a self-contained worker envelope
with finite read/write paths, exact contract excerpts, default-deny capabilities,
and the result schema. The coordinator passes it verbatim. Workers do not scan
the repository or interpret OrderSpec Markdown contracts. Attempt snapshots
deterministically reject undeclared writes and inaccurate `changed_files`.
Information Model blocks have stable context-only `ENT`, `STR`, and `VAL` IDs;
tasks select them through `contract_refs` without claiming behavioural
traceability. See [Bounded Contract Context](contract-context.md).

`code_workflow.py` is the implementation state-machine boundary: it performs
preflight, chooses the next legal task unit, constructs packets through the
task resolvers, and validates terminal completeness. `/order.code-check` uses
`code_obligations.py` to generate a complete machine ledger and record one
schema-validated semantic result per obligation before report finalization.
Attempt state v3 uses one canonical `current.json` slot and stores the exact
envelope. Exclusive creation prevents concurrent snapshots. Repeated
`attempt-begin` resumes the same attempt, accepted attempts block new snapshots
until marking and cleanup, closed failures move atomically to history, and
supervisor ROUTE/ADVANCE events are rejected across an open code boundary.

## Continuous execution policy

Optional continuous execution remains outside artifact authorship. Commands
produce typed boundary events; the deterministic supervisor applies
`.orderspec/config/automation.json` and persists a feature- or project-scoped
run checkpoint. Framework-owned command, advance, and owner-route tables decide
whether an event is legal; an agent-provided target is not authoritative by
itself. Canonical `ADVANCE` also requires the explicit completed-command source,
so a repeated call cannot advance the next stage; `order.code` cannot advance
while tasks remain unchecked. Acquire repairs a persisted legacy premature code
gate back to `order.code --resume`. `ADVANCE` and `ROUTE` may continue
automatically. Questions and exact approvals become `OPERATOR_INPUT` interrupts
and can only pause or stop; operator configuration never fabricates an answer.
The canonical `ask` adapter constructs these interrupts and emits stable reply
tokens plus exact answer commands, so runtime models never guess event enums or
interaction fields. Invalid direct events are non-mutating caller errors; only
invalid output from a canonical adapter is a framework failure.
The shipped policy covers legal non-destructive upstream routes emitted by
artifact authors, so a derived author can route a missing upstream decision to
its owner without an accidental default pause. A real policy/limit pause stores
the pending transition; explicit supervisor resume applies it and returns the
owner command plus the root adapter recovery command.

Normal cross-command transitions start a fresh agent context and reconstruct
authoritative input through the command context resolver. An interrupted
command may resume its own session after the operator answers. Route,
transition, semantic-event, and per-rule-per-event limits stop non-progress
cycles without aggregating unrelated defects that share a source and target. See
[Continuous Execution](continuous-execution.md).

Active-plan reconciliation uses a deterministic impact packet.
`plan_reconcile.py` distinguishes no delta, pending-only changes, completed-work
overlap, and reset-required cases. Pending-only changes preserve completed work
automatically; only evidenced completed overlap creates a semantic operator
interrupt. The packet separates plan-owned `changed_spec_ids` from
`evidence_dependency_spec_ids`, so an acceptance test may cite completed
production behavior without falsely invalidating its completed task. Selecting
reset first produces a bounded rollback preview and never applies it without a
separate mutation approval.

## Repository layout

```text
.
└── .orderspec/
    ├── README.md
    ├── contracts/                         ← project contracts (maintained by /order.bootstrap)
    │   ├── constitution.md
    │   ├── stack.md
    │   ├── architecture.md
    │   └── conventions.md
    ├── features/                          ← generated feature artifacts
    │   └── <feature>/
    │       ├── spec.md
    │       ├── plan.md
    │       ├── tasks.md
    │       └── .state/                    ← mechanisms, work-order baseline, feedback
    │           └── code-attempts/         ← ignored transient snapshots/results
    ├── config/
    │   └── tooling.json
    ├── state/
    │   ├── agents.json
    │   ├── bootstrap.json
    │   ├── tooling-detection.json
    │   └── active-feature.json
    ├── skills/                            ← project skills (single source of truth)
    └── framework/
        ├── docs/                          ← framework documentation
        ├── orderspec-rules.md
        ├── command-context.json
        ├── protocols/
        ├── schemas/
        │   ├── active-feature-state.schema.json
        │   ├── agents-state.schema.json
        │   └── ...
        ├── templates/
        ├── prompts/                       ← single source of truth for all prompts
        ├── adapters/                      ← multi-agent adapters
        │   ├── base.py
        │   ├── registry.py
        │   ├── kilocode.py
        │   ├── claude_code.py
        │   └── jsonc_utils.py
        └── scripts/                       ← deterministic utilities and tests
            ├── command_context.py
            ├── bootstrap_contracts.py
            ├── bootstrap_workflow.py
            ├── agents_sync.py
            ├── run_all_tests.py
            └── test/
```

## Tooling and documentation evidence

| File | Type | Meaning |
|---|---|---|
| `.orderspec/config/tooling.json` | Configuration | Project/operator policy for documentation lookup and skills bound to `GOV`, `STACK`, `ARCH`, or `CONV` contract IDs. |
| `.orderspec/state/tooling-detection.json` | Runtime state | Generated detection result for currently available tools such as Context7 or find-skills. |
| `.orderspec/state/agents.json` | Runtime state | Multi-agent configuration: enabled agents, sync state, last sync timestamp. |
| `.orderspec/state/bootstrap.json` | Runtime state | Initialization flag, last successful framework version, and Refine comparison fingerprints. |

These files live in different directories on purpose:

- `.orderspec/config/` contains durable configuration and policy.
- `.orderspec/state/` contains generated runtime state that may depend on the current environment.

Feature `.state/code-attempts/` is local transient runtime evidence. An active
attempt needs its snapshot and result files through `attempt-finish`; successful
pairs are deleted only after all owned tasks are marked `[X]`. Failed or rejected
pairs remain ignored local evidence until diagnosis and may then be removed.
