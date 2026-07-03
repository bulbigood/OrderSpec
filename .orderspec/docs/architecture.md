# Architecture

## The three-document feature model

OrderSpec splits each feature into three documents with distinct roles and distinct lifecycles.

| Document | Role | Stability |
|----------|------|-----------|
| `spec.md` | **WHAT** + logical contract | **Stable. The source of truth.** |
| `plan.md` | **WHERE / HOW** — mapping onto physical code, stack, gates | **Regenerated** to match the current repository state |
| `tasks.md` | **ORDER** — execution sequence | **Disposable. A one-shot work order** |

The key insight:

> **`plan.md` depends on the state of the repository; `spec.md` does not.**

A spec is a contract about behavior. It should survive refactors, renames, and merges.

A plan is a snapshot of how to realize that contract against the code as it exists right now, so it is regenerated whenever the codebase moves underneath it.

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

Allowed gate writes are intentionally narrow:

- mechanical glossary normalization;
- unambiguous stale-ID reference fixes;
- other explicitly allowed, meaning-preserving corrections.

Anything that touches meaning, behavior, scope, architecture, implementation strategy, or code is routed.

`code-check` is stricter: it does not edit code. It reads, optionally gathers evidence permitted by the constitution, and reports.

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
- whether mechanical auto-fixes are allowed;
- external rules integration policy.

The default policy is restrictive:

> **Anything not explicitly granted is denied. Silence is never permission.**

Authoring commands may use read-only documentation lookup when allowed by project governance and `.orderspec/config/tooling.json`.

Gate commands follow `constitution.md` literally.

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
    │       └── tasks.md
    ├── config/
    │   └── tooling.json
    ├── state/
    │   ├── agents.json
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

These files live in different directories on purpose:

- `.orderspec/config/` contains durable configuration and policy.
- `.orderspec/state/` contains generated runtime state that may depend on the current environment.
