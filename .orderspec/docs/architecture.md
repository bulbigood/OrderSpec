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

Each new work order attempts to capture a Git-backed baseline for every
pathmanifest path. `/order.code --reset` is available only when capture
succeeded; it previews and restores that bounded set, then clears checkboxes
after rollback succeeds. Broad working-tree cleanup is never used.

When code execution discovers an upstream defect, it persists a typed feedback
report in the feature `.state/feedback/`. The owning author command loads it on
the next run and consumes it only after the repaired artifact validates.

A spec is a contract about behavior. It should survive refactors, renames, and merges.

A plan is a snapshot of how to realize that contract against the code as it
exists when the work order is planned. Its path tags describe intended
transitions from that baseline. Therefore an applied `[NEW]` or `[DEL]`
transition does not stale the plan. External movement or a discovered mapping
defect requires replanning and regeneration of derived tasks before code
execution continues.

Tasks are pure throwaway: generate, execute, discard.

## The pipeline

```text
/order.bootstrap
      ↓
/order.spec  →  /order.plan  →  /order.tasks  →  /order.code
   WHAT           WHERE/HOW        ORDER            IMPLEMENT
```

Each phase can be followed by an optional verification gate that checks the previous artifact before you proceed:

| Phase | Author command | Gate | The gate verifies |
|---|---|---|---|
| Bootstrap | `/order.bootstrap` | built-in validation | project contracts are present and structurally valid |
| Specify | `/order.spec` | `/order.spec-check` | spec is a valid, self-consistent, testable WHAT-contract |
| Plan | `/order.plan` | `/order.plan-check` | plan is correctly derived from spec + repo + project contracts |
| Tasks | `/order.tasks` | `/order.tasks-check` | tasks are correctly derived from plan |
| Implement | `/order.code` | `/order.code-check` | code faithfully implements the contract |

There is also one event-triggered gate outside the linear flow:

| Gate | When you run it | What it does |
|---|---|---|
| `/order.sync-check` | after a merge, rebase, long branch, or hand-edit | detects drift, cross-version ID collisions, and stale relationships between artifacts, then routes reconciliation to the owning command |

`sync-check` checks **artifact ↔ artifact** consistency.

`code-check` checks **code ↔ contract** consistency.

Together they cover the two axes along which a project can drift.

## How gates behave

Every gate in OrderSpec is a constrained inspector.

The rule is:

> **Gates detect and route. Owners fix.**

A gate does not silently rewrite a spec to resolve ambiguity. It does not pick a winner in a merge conflict. It does not improvise scope. It emits findings and routes fixes to the command that owns the artifact.

Gates never edit the artifact they inspect. Their writes are limited to the gate report and explicitly defined workflow state. Every defect is routed to the command that owns the artifact.

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

For `/order.code`, the resolver also supplies the sub-agent execution protocol.
The coordinator reads feature artifacts and passes workers only explicit task
packets with finite read/write paths. Workers do not scan the repository or
interpret OrderSpec Markdown contracts.

## Repository layout

```text
.
└── .orderspec/
    ├── README.md
    ├── docs/                              ← documentation
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
    ├── config/
    │   └── tooling.json
    ├── state/
    │   ├── agents.json
    │   ├── bootstrap.json
    │   ├── tooling-detection.json
    │   └── active-feature.json
    ├── skills/                            ← project skills (single source of truth)
    └── framework/
        ├── orderspec-rules.md
        ├── command-context.json
        ├── protocols/
        ├── schemas/
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
            ├── agents_sync.py
            ├── run_all_tests.py
            └── test/
```

## Tooling and documentation evidence

| File | Type | Meaning |
|---|---|---|
| `.orderspec/config/tooling.json` | Configuration | Project/operator policy for documentation lookup and skill usage. |
| `.orderspec/state/tooling-detection.json` | Runtime state | Generated detection result for currently available tools such as Context7 or find-skills. |
| `.orderspec/state/agents.json` | Runtime state | Multi-agent configuration: enabled agents, sync state, last sync timestamp. |
| `.orderspec/state/bootstrap.json` | Runtime state | Initialization flag, last successful framework version, and Refine comparison fingerprints. |

These files live in different directories on purpose:

- `.orderspec/config/` contains durable configuration and policy.
- `.orderspec/state/` contains generated runtime state that may depend on the current environment.
