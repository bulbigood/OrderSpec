# OrderSpec

**Spec-driven development for relatively weak LLMs — built for engineers, hardened for teams.**

> ⚠️ **Adaptation status:** OrderSpec is currently adapted for **[Kilo Code](https://kilocode.ai/)** only.
>
> There is **no installer yet**. Setup is manual: copy the OrderSpec prompts, framework files, and scripts into your project.
>
> Support for other agents and a proper installer are future work.

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

## Bootstrap: project contracts first

Before writing feature specs, run:

```text
/order.bootstrap
```

Bootstrap creates or amends the project-level contracts that all later commands use:

| File | Role |
|---|---|
| `constitution.md` | Project governance and capability grants. Defines what gates may do as evidence. |
| `stack.md` | Project technology stack, with stable `STACK-NNN` IDs. |
| `architecture.md` | Project architecture and dependency rules, with stable `ARCH-NNN` IDs. |
| `conventions.md` | Project implementation conventions, with stable `CONV-NNN` IDs. |

These files intentionally live at the repository root.

They are not hidden framework internals. They are first-class project documents, useful to humans, reviewers, and other tools even outside OrderSpec.

OrderSpec uses them as constraints during planning, tasking, implementation, and verification.

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

This is what makes OrderSpec safe under a weak model: the model is never trusted to silently “improve” your contract.

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
- whether mechanical auto-fixes are allowed.

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

These files live in different directories on purpose:

- `.orderspec/config/` contains durable configuration and policy.
- `.orderspec/state/` contains generated runtime state that may depend on the current environment.

For example:

```text
.orderspec/config/tooling.json
```

says what the project wants:

```json
{
  "docs": {
    "context7": {
      "policy": "required_if_available"
    }
  }
}
```

while:

```text
.orderspec/state/tooling-detection.json
```

records what was detected in the current runtime:

```json
{
  "version": 1,
  "context7_status": "available",
  "find_skills_status": "available"
}
```

If availability cannot be determined, commands should record `unknown`, not guess.

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
├── constitution.md
├── stack.md
├── architecture.md
├── conventions.md
├── specs/
│   └── <feature>/
│       ├── spec.md
│       ├── plan.md
│       └── tasks.md
└── .orderspec/
    ├── framework/
    │   ├── orderspec-rules.md
    │   ├── command-context.json
    │   ├── protocols/
    │   ├── schemas/
    │   └── templates/
    ├── scripts/
    ├── config/
    │   └── tooling.json
    └── state/
        ├── tooling-detection.json
        └── active-feature.json
```

### Why project contracts live at the root

The root files:

```text
constitution.md
stack.md
architecture.md
conventions.md
```

are project contracts, not framework internals.

They are meant to be visible, reviewable, and useful outside OrderSpec.

This mirrors the treatment of feature specs: feature artifacts live under `specs/`, not inside `.orderspec/`.

### Why framework files live under `.orderspec/`

`.orderspec/` contains OrderSpec machinery:

| Directory | Meaning |
|---|---|
| `.orderspec/framework/` | Framework-owned rules, schemas, templates, protocols, and resolver manifest. |
| `.orderspec/scripts/` | Deterministic framework utilities. |
| `.orderspec/config/` | Operator/project configuration. |
| `.orderspec/state/` | Generated runtime state. |

---

## Multi-framework coexistence

OrderSpec intentionally makes project contracts visible at the repository root.

This is useful, but it can overlap with other frameworks or existing project files — especially `constitution.md`.

The intended model is:

- if a project contract is missing, `/order.bootstrap` creates it;
- if a contract already exists and is OrderSpec-owned, `/order.bootstrap` amends it;
- if a similarly named non-OrderSpec file already exists, the command should not blindly overwrite it;
- future versions may support namespaced or configurable contract paths.

This is a tradeoff:

| Layout | Benefit | Cost |
|---|---|---|
| Root contracts | Human-visible, project-native, useful outside OrderSpec | Possible filename collisions |
| `.orderspec/contracts/` | Namespaced, fewer collisions | Less visible, looks framework-internal |

OrderSpec currently chooses root contracts as the default because they are project source-of-truth documents, not hidden framework memory.

---

## Customization

OrderSpec is meant to bend to your project, but customization is deliberately constrained.

Supported today:

- optional verification gates;
- project governance through `constitution.md`;
- project stack/architecture/conventions through root contracts;
- tooling policy through `.orderspec/config/tooling.json`;
- deterministic framework scripts.

Not supported yet:

- operator-defined lifecycle extension execution;
- arbitrary prompt hooks;
- custom procedural instructions loaded from project config.

This restriction is intentional. Operator-managed configuration is data, not procedural prompt authority.

If lifecycle extensions are introduced later, they should be implemented through deterministic scripts with explicit configuration, allowlisted commands, JSON output, and constitution-gated capability checks.

---

## Environment requirements

OrderSpec is intentionally lightweight, but the current implementation does require:

- Kilo Code;
- `python3`;
- shell access capable of running the framework scripts.

There is currently:

- no package manager requirement;
- no `uv` requirement;
- no installer;
- no framework daemon.

Setup is manual.

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
| Project governance | framework memory / templates | proposal process | root project contracts + constitution |
| Document roles | spec / plan / tasks | proposal / spec / tasks | spec contract / repo-mapped plan / disposable tasks |
| Gate behavior | generation-centric | review-centric | pure inspectors: detect + route |
| Merge safety | limited | process-dependent | dedicated `sync-check` |
| Code verification | agent-dependent | process-dependent | terminal `code-check` |
| Mechanical work | often in-model | often in-model | deterministic scripts |
| Environment | installer / CLI-oriented | Node-oriented | Kilo Code + Python scripts, no installer yet |
| Weak-model strategy | not primary | not primary | primary design constraint |

---

## Design principles

The principles that shape OrderSpec:

- **Weak-model-first.** The workflow is tuned to run reliably on modest models, not only frontier models.
- **Deterministic scripts own mechanical work.** Resolution, validation, bootstrap generation, and state management should not depend on model memory.
- **Gates detect and route; owners fix.** A gate is an inspector, not an author.
- **Quality first.** Generated documents and code are the product. Everything else bends to keep them correct.
- **Token-efficient, but correctness wins.** Lean prompts are valuable, but not at the cost of ambiguity or broken contracts.
- **Engineer-facing.** Documents assume technical literacy and use precise terminology.
- **Readable to humans and models alike.** Stable IDs, tables, explicit sections, and narrow responsibilities.
- **Phase-separated.** Work is split across bootstrap, spec, plan, tasks, and code so no single step is overloaded.
- **Project- and stack-agnostic.** The framework is not tied to a language, runtime, or package manager.
- **Default-deny capabilities.** Commands and gates only do what project governance permits.
- **Framework internals stay internal.** Runtime agents use resolver output, not internal manifests, to decide what to read.

---

## Quick start

> Manual setup. Kilo Code only for now.

1. Copy the OrderSpec prompts and `.orderspec/` directory into your project.

2. Run bootstrap:

   ```text
   /order.bootstrap
   ```

   This creates or amends:

   ```text
   constitution.md
   stack.md
   architecture.md
   conventions.md
   .orderspec/config/tooling.json
   .orderspec/state/tooling-detection.json
   ```

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
python3 .orderspec/scripts/command_context.py validate --json
python3 .orderspec/scripts/command_context.py resolve order.bootstrap --json
python3 .orderspec/scripts/bootstrap_contracts.py inspect --json
python3 .orderspec/scripts/bootstrap_contracts.py validate --json
```

Framework tests:

```bash
python3 -m py_compile .orderspec/scripts/command_context.py
python3 -m py_compile .orderspec/scripts/bootstrap_contracts.py
python3 .orderspec/scripts/test/test-command-context.py
```

---

## Status and roadmap

Current status:

- ✅ Kilo Code adaptation.
- ✅ Manual setup.
- ✅ `/order.bootstrap`.
- ✅ Project contracts: `constitution.md`, `stack.md`, `architecture.md`, `conventions.md`.
- ✅ Command context resolver.
- ✅ Deterministic bootstrap scripts.
- ✅ Tooling configuration and runtime detection state.
- ✅ Core feature pipeline: `/order.spec`, `/order.plan`, `/order.tasks`, `/order.code`.
- ✅ Optional verification gates.
- ✅ Active feature state support.

Future work:

- 🔜 Installer.
- 🔜 Adapters for agents beyond Kilo Code.
- 🔜 Stronger semantic validation for generated contracts.
- 🔜 Optional namespaced contract layout or configurable contract paths.
- 🔜 Better cross-platform script parity verification.
- 🔜 Lifecycle extension system, if it can be made deterministic and constitution-gated.

---

## Current limitations

- OrderSpec is currently Kilo Code-only.
- Setup is manual.
- Python 3 is required for current framework scripts.
- Root project contract names may overlap with other frameworks or existing project files.
- Operator-defined procedural extensions are not supported yet.
- Some project facts cannot be inferred safely during bootstrap and are marked unresolved instead of guessed.

This is intentional: OrderSpec prefers an explicit unresolved marker over a hallucinated contract.