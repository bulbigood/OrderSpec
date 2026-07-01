# OrderSpec

**Spec-driven development for relatively weak LLMs — built for engineers, hardened for teams.**

> **Adaptation status:** OrderSpec supports multiple AI agents simultaneously:
>
> - ✅ [Kilo Code](https://kilo.ai/) (`.kilo/` new format + `.kilocode/` legacy)
> - ✅ [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (`.claude/` + `CLAUDE.md`)
>
> There is **no installer yet**. Setup is manual: copy the OrderSpec `.orderspec/` directory into your project.

## 🚀 Quick Start

After copying the `.orderspec/` directory into your project, run this command in your terminal:

```bash
python3 .orderspec/scripts/agents_sync.py sync
```

The script will automatically detect installed AI agents and prompt you to select which ones to integrate. It will copy the OrderSpec prompts and register the skills directory for the selected agents.

Once the sync is complete, you can launch the bootstrap command inside your AI agent:

```text
/order.bootstrap
```

> **Note:** You can also sync specific agents directly by passing their IDs:
> `python3 .orderspec/scripts/agents_sync.py sync --agents kilocode claude_code`

---

OrderSpec is a spec-driven workflow that turns a feature idea into a verifiable implementation through explicit phases:

```text
bootstrap → specify → plan → tasks → implement
```

The core feature pipeline remains:

```text
/order.spec  →  /order.plan  →  /order.tasks  →  /order.code
   WHAT           WHERE/HOW        ORDER            IMPLEMENT
```

OrderSpec is a re-architecture of the [spec-kit](https://github.com/github/spec-kit) pipeline, redesigned around one core constraint:

> It must run reliably on relatively weak LLM models.

---

## Why OrderSpec exists

Most spec-driven tooling assumes a strong model that can hold a whole feature in its head, reason about contracts, and write correct code in one pass.

In practice, many teams run cheaper or smaller models — and those models drift, hallucinate scope, skip acceptance criteria, confuse instructions with data, and silently desync documents from code.

OrderSpec is designed for exactly that environment.

Every design choice answers the same question:

> **How does this behave when the model is not very smart?**

The answer is consistent:

> **Mechanical work goes to deterministic scripts. Judgment is narrow and routed. Gates detect and delegate — they never improvise.**

---

## Multi-agent support

OrderSpec is not tied to a specific AI agent. It uses a deterministic **adapter pattern** to support multiple agents simultaneously.

### Supported agents

| Agent | Detection | Prompts delivered to | Skills registration | Rules read from |
|---|---|---|---|---|
| **Kilo Code** | `.kilo/` dir or `kilo.jsonc` (new); `.kilocode/` dir (legacy) | `.kilo/commands/` (new); `.kilocode/workflows/` (legacy) — copied, no symlinks | `skills.paths` array in `kilo.jsonc` | `AGENTS.md`, files from `instructions` array in `kilo.jsonc`, `.kilocode/rules/*.md` (legacy) |
| **Claude Code** | `.claude/` dir or `CLAUDE.md` at root | `.claude/commands/` — copied | Symlink: `.claude/skills` → `.orderspec/skills` | `CLAUDE.md`, `.claude/CLAUDE.md` |

### How it works

1. **Detection**: each adapter's `detect()` method checks the project for signs of its agent.
2. **Prompt sync**: OrderSpec prompts live in `.orderspec/framework/prompts/` as a single source of truth. Each adapter copies them to the agent's commands directory. SHA-256 hashing avoids unnecessary copies.
3. **Skills registration**: instead of copying skills, each adapter registers `.orderspec/skills/` in the agent's config — one source of truth.
4. **External rules**: each adapter reads agent-specific rule files (AGENTS.md, CLAUDE.md, etc.) for optional integration into `conventions.md` during bootstrap.

### Adapter architecture

```text
.orderspec/framework/adapters/
├── base.py          # AgentAdapter interface (detect, sync_skills_dir, sync_prompts, read_rules)
├── registry.py      # Adapter registry
├── kilocode.py      # Kilo Code adapter
├── claude_code.py   # Claude Code adapter
└── jsonc_utils.py   # JSONC read/write utilities for kilo.jsonc
```

### Agent state

Multi-agent configuration and sync state lives in:

```text
.orderspec/state/agents.json
```

This file is generated and maintained by `.orderspec/scripts/agents_sync.py`. It records which agents are enabled, their detection info, and sync state (last sync timestamp, copied/skipped prompts).

### Adding a new agent adapter

1. Create a new file in `.orderspec/framework/adapters/` implementing the `AgentAdapter` interface from `base.py`.
2. Register it in `registry.py`.
3. The adapter must implement four methods: `detect`, `sync_skills_dir`, `sync_prompts`, `read_rules`.

The framework core remains agent-agnostic. All agent-specific logic lives in adapters.

---

## Bootstrap: project contracts first

Before writing feature specs, run:

```text
/order.bootstrap
```

Bootstrap creates or amends the project-level contracts that all later commands use:

| File | Role |
|---|---|
| `.orderspec/contracts/constitution.md` | Project governance and capability grants. Defines what gates may do as evidence. Also defines external rules integration policy. |
| `.orderspec/contracts/stack.md` | Project technology stack, with stable `STACK-NNN` IDs. |
| `.orderspec/contracts/architecture.md` | Project architecture and dependency rules, with stable `ARCH-NNN` IDs. |
| `.orderspec/contracts/conventions.md` | Project implementation conventions, with stable `CONV-NNN` IDs. |

These files live under `.orderspec/contracts/`. No OrderSpec artifact is written to the repository root.

OrderSpec uses them as constraints during planning, tasking, implementation, and verification.

### Bootstrap phases

```text
1. Command Context Resolution (via command_context.py)
2. Mode Detection (Init / Amend / Targeted Amend)
3. Deterministic Bootstrap Script (bootstrap_contracts.py)
4. Gate Capabilities Question
5. Agents Discovery & Sync Phase         ← multi-agent
6. Tooling Discovery Phase
7. External Rules Integration Phase      ← multi-agent
8. Report
```

**Agents Discovery & Sync Phase** detects installed AI agents, asks the operator which to enable, and synchronizes prompts and skills configuration.

**External Rules Integration Phase** reads rule files from enabled agents (AGENTS.md, CLAUDE.md, etc.) and offers to integrate uncovered statements into `conventions.md`.

### External rules integration policy

The policy is defined in `constitution.md`:

| Policy | Behavior |
|---|---|
| `constrain_on_bootstrap` (default) | Rule files are read only during `/order.bootstrap`. Content is offered for integration into `conventions.md`. After bootstrap, OrderSpec commands work only with their own contracts. |
| `constrain_always` | Rule files are loaded as constrain source for every command. May conflict with OrderSpec contracts. Use with caution. |
| `ignore` | Rule files are not read by OrderSpec at all. |

The principle is: **external rules are detected and routed, never silently applied.**

---

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

---

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

---

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

---

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
- **external rules integration policy** (new).

The default policy is restrictive:

> **Anything not explicitly granted is denied. Silence is never permission.**

Authoring commands may use read-only documentation lookup when allowed by project governance and `.orderspec/config/tooling.json`.

Gate commands follow `constitution.md` literally.

---

## Tooling and documentation evidence

OrderSpec can record tooling/documentation policy and runtime detection state.

| File | Type | Meaning |
|---|---|---|
| `.orderspec/config/tooling.json` | Configuration | Project/operator policy for documentation lookup and skill usage. |
| `.orderspec/state/tooling-detection.json` | Runtime state | Generated detection result for currently available tools such as Context7 or find-skills. |
| `.orderspec/state/agents.json` | Runtime state | Multi-agent configuration: enabled agents, sync state, last sync timestamp. |

These files live in different directories on purpose:

- `.orderspec/config/` contains durable configuration and policy.
- `.orderspec/state/` contains generated runtime state that may depend on the current environment.

---

## Command context loading

OrderSpec commands do not manually maintain long preload lists in prompts.

At command start, each command resolves its context through the framework resolver:

```bash
python3 .orderspec/scripts/command_context.py resolve <order.command> --json
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

---

## Repository layout

A typical OrderSpec-enabled project contains:

```text
.
└── .orderspec/
    ├── README.md                      ← this file
    ├── framework/
    │   ├── orderspec-rules.md
    │   ├── command-context.json
    │   ├── protocols/
    │   ├── schemas/
    │   │   ├── agents-state.schema.json   ← multi-agent state schema
    │   │   └── ...
    │   ├── templates/
    │   ├── prompts/                       ← single source of truth for all prompts
    │   └── adapters/                      ← multi-agent adapters
    │       ├── base.py
    │       ├── registry.py
    │       ├── kilocode.py
    │       ├── claude_code.py
    │       └── jsonc_utils.py
    ├── scripts/
    │   ├── command_context.py
    │   ├── bootstrap_contracts.py
    │   ├── agents_sync.py                 ← multi-agent orchestrator
    │   └── test/
    │       ├── test-command-context.py
    │       ├── test-bootstrap-contracts.py
    │       └── test-agents-sync.py        ← multi-agent tests
    ├── contracts/                         ← project contracts (generated/maintained by /order.bootstrap)
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
    │   ├── agents.json                   ← multi-agent state
    │   ├── tooling-detection.json
    │   └── active-feature.json
    └── skills/                           ← project skills (single source of truth)
```

### Why everything lives under `.orderspec/`

OrderSpec keeps **all** generated artifacts and project contracts inside `.orderspec/`. Nothing is written to the repository root. This keeps the project tree clean, makes OrderSpec-owned content easy to gitignore or review as a unit, and prevents overlap with other frameworks or existing project files.

Project contracts (`constitution.md`, `stack.md`, `architecture.md`, `conventions.md`) live under `.orderspec/contracts/`. Feature artifacts live under `.orderspec/features/<feature>/`.

### Why framework files live under `.orderspec/`

| Directory | Meaning |
|---|---|
| `.orderspec/framework/` | Framework-owned rules, schemas, templates, protocols, adapters, and resolver manifest. |
| `.orderspec/scripts/` | Deterministic framework utilities and tests. |
| `.orderspec/contracts/` | Project contracts generated and maintained by `/order.bootstrap`. |
| `.orderspec/features/` | Generated feature artifacts (`spec.md`, `plan.md`, `tasks.md`). |
| `.orderspec/config/` | Operator/project configuration. |
| `.orderspec/state/` | Generated runtime state. |
| `.orderspec/skills/` | Project skills — single source of truth, registered in each agent's config. |

---

## Multi-framework coexistence

OrderSpec keeps all of its generated content (project contracts, feature artifacts, state, reports) under `.orderspec/`, so it does not clutter the repository root or collide with other frameworks' files.

The intended model is:

- if a project contract is missing, `/order.bootstrap` creates it under `.orderspec/contracts/`;
- if a contract already exists and is OrderSpec-owned, `/order.bootstrap` amends it;
- OrderSpec does not write outside `.orderspec/`, so similarly named non-OrderSpec files at the repository root are left untouched;
- future versions may support configurable contract paths.

---

## Customization

OrderSpec is meant to bend to your project, but customization is deliberately constrained.

Supported today:

- optional verification gates;
- project governance through `constitution.md`;
- project stack/architecture/conventions through `.orderspec/contracts/`;
- tooling policy through `.orderspec/config/tooling.json`;
- deterministic framework scripts;
- **multi-agent adapter pattern** for adding AI agent support;
- **external rules integration policy** in constitution.

Not supported yet:

- operator-defined lifecycle extension execution;
- arbitrary prompt hooks;
- custom procedural instructions loaded from project config.

This restriction is intentional. Operator-managed configuration is data, not procedural prompt authority.

---

## Environment requirements

OrderSpec is intentionally lightweight. It requires:

- `python3`;
- shell access capable of running the framework scripts;
- at least one supported AI agent installed (Kilo Code and/or Claude Code).

There is currently:

- no package manager requirement;
- no `uv` requirement;
- no installer;
- no framework daemon.

Setup is manual: copy `.orderspec/` into your project.

---

## Philosophy: OrderSpec vs spec-kit vs OpenSpec

The three frameworks share a pipeline shape but believe different things about the world.

> **spec-kit** believes the spec is scaffolding for a capable model.
>
> The document exists to get the model productive; the model is trusted to fill the gaps and write the code. It is optimized for generation speed with a strong agent.

> **OpenSpec** believes the spec is a proposal to be reviewed.
>
> The center of gravity is the change proposal and its review loop — alignment between humans on what to build before building it.

> **OrderSpec** believes the spec is a contract that a weak model must not be allowed to break.
>
> The document is the source of truth; the model is a fallible executor. Every phase is guarded, every judgment is narrow and cited, and every fix is routed to a named owner instead of being silently improvised.

In one line:

> **spec-kit and OpenSpec assume the model is smart; OrderSpec assumes it is not, and pushes every judgment call to either a script or a human-owned command.**

### Side by side

| | spec-kit | OpenSpec | OrderSpec |
|---|---|---|---|
| Core belief | spec = scaffolding for a smart model | spec = proposal to review | spec = contract a weak model must not break |
| Primary audience | general | general | software engineers |
| Optimized for | capable models | human alignment | relatively weak models |
| Project governance | framework memory / templates | proposal process | `.orderspec/contracts/` + constitution |
| Document roles | spec / plan / tasks | proposal / spec / tasks | spec contract / repo-mapped plan / disposable tasks |
| Gate behavior | generation-centric | review-centric | pure inspectors: detect + route |
| Merge safety | limited | process-dependent | dedicated `sync-check` |
| Code verification | agent-dependent | process-dependent | terminal `code-check` |
| Mechanical work | often in-model | often in-model | deterministic scripts |
| Multi-agent | not primary | not primary | adapter pattern, multiple agents simultaneously |
| Environment | installer / CLI-oriented | Node-oriented | Python scripts, agent-agnostic, no installer yet |
| Weak-model strategy | not primary | not primary | primary design constraint |

---

## Design principles

The principles that shape OrderSpec:

- **Weak-model-first.** The workflow is tuned to run reliably on modest models, not only frontier models.
- **Deterministic scripts own mechanical work.** Resolution, validation, bootstrap generation, agent sync, and state management should not depend on model memory.
- **Gates detect and route; owners fix.** A gate is an inspector, not an author.
- **Quality first.** Generated documents and code are the product. Everything else bends to keep them correct.
- **Token-efficient, but correctness wins.** Lean prompts are valuable, but not at the cost of ambiguity or broken contracts.
- **Engineer-facing.** Documents assume technical literacy and use precise terminology.
- **Readable to humans and models alike.** Stable IDs, tables, explicit sections, and narrow responsibilities.
- **Phase-separated.** Work is split across bootstrap, spec, plan, tasks, and code so no single step is overloaded.
- **Project- and stack-agnostic.** The framework is not tied to a language, runtime, or package manager.
- **Agent-agnostic core.** Framework core is independent of any specific AI agent; agent-specific logic lives in adapters.
- **Default-deny capabilities.** Commands and gates only do what project governance permits.
- **Framework internals stay internal.** Runtime agents use resolver output, not internal manifests, to decide what to read.
- **One source of truth for prompts.** Prompts live in `.orderspec/framework/prompts/` and are delivered to agents by adapters.

---

## Quick start

> Manual setup. Supports Kilo Code and Claude Code.

1. Copy the OrderSpec `.orderspec/` directory into your project.

2. **Initial sync (required once):** Run this in your terminal to copy prompts to the agent's command directory:

   ```bash
   # For Kilo Code:
   python3 .orderspec/scripts/agents_sync.py sync --agents kilocode

   # For Claude Code:
   python3 .orderspec/scripts/agents_sync.py sync --agents claude_code

   # For both:
   python3 .orderspec/scripts/agents_sync.py sync --agents kilocode claude_code
   ```

3. Run bootstrap:

   ```text
   /order.bootstrap
   ```

   This creates or amends:

   ```text
   .orderspec/contracts/constitution.md
   .orderspec/contracts/stack.md
   .orderspec/contracts/architecture.md
   .orderspec/contracts/conventions.md
   .orderspec/config/tooling.json
   .orderspec/state/tooling-detection.json
   .orderspec/state/agents.json
   ```

   Bootstrap will also:
   - detect installed AI agents
   - ask which agents to enable
   - sync prompts to all enabled agents
   - register `.orderspec/skills/` in each agent's config
   - read external rule files (AGENTS.md, CLAUDE.md) and offer integration

3. Run the feature pipeline:

   ```text
   /order.spec "describe the feature you want"
   /order.plan
   /order.tasks
   /order.code
   ```

4. Run gates when you want verification:

   ```text
   /order.spec-check
   /order.plan-check
   /order.tasks-check
   /order.code-check
   /order.sync-check
   ```

5. Re-run bootstrap when project-level contracts need to evolve:

   ```text
   /order.bootstrap
   ```

---

## Useful direct checks

These are framework-level checks, useful during development or debugging:

```bash
# Command context resolver
python3 .orderspec/scripts/command_context.py validate --json
python3 .orderspec/scripts/command_context.py resolve order.bootstrap --json

# Bootstrap contracts
python3 .orderspec/scripts/bootstrap_contracts.py inspect --json
python3 .orderspec/scripts/bootstrap_contracts.py validate --json

# Multi-agent sync
python3 .orderspec/scripts/agents_sync.py detect --json
python3 .orderspec/scripts/agents_sync.py sync --agents kilocode claude_code --json
python3 .orderspec/scripts/agents_sync.py read-rules --agents kilocode claude_code --json
python3 .orderspec/scripts/agents_sync.py state
```

Framework tests:

```bash
python3 -m py_compile .orderspec/scripts/command_context.py
python3 -m py_compile .orderspec/scripts/bootstrap_contracts.py
python3 -m py_compile .orderspec/scripts/agents_sync.py
python3 .orderspec/scripts/test/test-command-context.py
python3 .orderspec/scripts/test/test-bootstrap-contracts.py
python3 .orderspec/scripts/test/test-agents-sync.py
```

---

## Status and roadmap

Current status:

- ✅ Multi-agent support: Kilo Code + Claude Code.
- ✅ Adapter pattern for adding new agents.
- ✅ Manual setup.
- ✅ `/order.bootstrap` with agents discovery & sync phase.
- ✅ Project contracts: `.orderspec/contracts/constitution.md`, `stack.md`, `architecture.md`, `conventions.md`.
- ✅ Constitution includes external rules integration policy.
- ✅ Command context resolver.
- ✅ Deterministic bootstrap scripts.
- ✅ Tooling configuration and runtime detection state.
- ✅ Core feature pipeline: `/order.spec`, `/order.plan`, `/order.tasks`, `/order.code`.
- ✅ Optional verification gates.
- ✅ Active feature state support.
- ✅ Agent sync orchestrator (`agents_sync.py`).
- ✅ Multi-agent regression tests.

Future work:

- 🔜 Installer.
- 🔜 Adapters for more agents (OpenCode, Cursor, Windsurf, ...).
- 🔜 `/order.sync-agents` command for re-syncing without full bootstrap.
- 🔜 Stronger semantic validation for generated contracts.
- 🔜 Optional namespaced contract layout or configurable contract paths.
- 🔜 Better cross-platform script parity verification.
- 🔜 Lifecycle extension system, if it can be made deterministic and constitution-gated.

---

## Current limitations

- Setup is manual (no installer yet).
- Python 3 is required for current framework scripts.
- Project contract files live under `.orderspec/contracts/`; names there may still overlap with other frameworks if paths are made configurable in the future.
- Operator-defined procedural extensions are not supported yet.
- Some project facts cannot be inferred safely during bootstrap and are marked unresolved instead of guessed.
- Not all AI agents are supported yet — only Kilo Code and Claude Code.
- Claude Code skills registration uses a symlink, which may not work on all platforms (Windows without developer mode).

This is intentional: OrderSpec prefers an explicit unresolved marker over a hallucinated contract.
