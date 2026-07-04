# OrderSpec

**Spec-driven development for relatively weak LLMs — built for engineers, hardened for teams.**

> **Adaptation status:** OrderSpec supports multiple AI agents simultaneously:
>
> - ✅ [Kilo Code](https://kilo.ai/) (`.kilo/` new format + `.kilocode/` legacy)
> - ✅ [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (`.claude/` + `CLAUDE.md`)
>
> There is **no installer yet**. Setup is manual: copy the OrderSpec `.orderspec/` directory into your project.

## Requirements

- **Python 3** — framework scripts are written in Python
- **Shell access** — to run framework utilities
- **At least one supported AI agent**

No package manager, no `uv`, no installer, no framework daemon required.

## Quick Start

First, copy .orderspec/ to the root of your project.
Then sync OrderSpec with your AI agent and start your first feature:

```bash
# Sync OrderSpec with installed AI agents
python3 .orderspec/framework/scripts/agents_sync.py sync

# Run bootstrap
/order.bootstrap

# Run the feature pipeline
/order.spec "describe the feature you want"
/order.plan
/order.tasks
/order.code
```

## The pipeline

```text
/order.bootstrap
      ↓
/order.spec  →  /order.plan  →  /order.tasks  →  /order.code
   WHAT           WHERE/HOW        ORDER            IMPLEMENT
```

OrderSpec splits each feature into three documents with distinct roles:

| Document | Role | Stability |
|----------|------|-----------|
| `spec.md` | **WHAT** + logical contract | **Stable. The source of truth.** |
| `plan.md` | **WHERE / HOW** — mapping onto physical code | **Regenerated** to match the current repository state |
| `tasks.md` | **ORDER** — execution sequence | **Disposable. A one-shot work order** |

The key insight: **`plan.md` depends on the state of the repository; `spec.md` does not.**

Each phase can be followed by an optional verification gate (`/order.spec-check`, `/order.plan-check`, etc.) that checks the previous artifact before you proceed.

## Why OrderSpec exists

Most spec-driven tooling assumes a strong model that can hold a whole feature in its head, reason about contracts, and write correct code in one pass.

In practice, many teams run cheaper or smaller models — and those models drift, hallucinate scope, skip acceptance criteria, confuse instructions with data, and silently desync documents from code.

OrderSpec is designed for exactly that environment.

Every design choice answers the same question:

> **How does this behave when the model is not very smart?**

The answer: **Mechanical work goes to deterministic scripts. Judgment is narrow and routed. Gates detect and delegate — they never improvise.**

## Comparison with spec-kit and OpenSpec

The three frameworks share a pipeline shape but believe different things about the world.

> **spec-kit** believes the spec is scaffolding for a capable model. The document exists to get the model productive; the model is trusted to fill the gaps and write the code.

> **OpenSpec** believes the spec is a proposal to be reviewed. The center of gravity is the change proposal and its review loop — alignment between humans on what to build before building it.

> **OrderSpec** believes the spec is a contract that a weak model must not be allowed to break. The document is the source of truth; the model is a fallible executor.

| | spec-kit | OpenSpec | OrderSpec |
|---|---|---|---|
| Core belief | spec = scaffolding for a smart model | spec = proposal to review | spec = contract a weak model must not break |
| Optimized for | capable models | human alignment | relatively weak models |
| Document roles | spec / plan / tasks | proposal / spec / tasks | spec contract / repo-mapped plan / disposable tasks |
| Gate behavior | generation-centric | review-centric | pure inspectors: detect + route |
| Mechanical work | often in-model | often in-model | deterministic scripts |

In one line: **spec-kit and OpenSpec assume the model is smart; OrderSpec assumes it is not, and pushes every judgment call to either a script or a human-owned command.**

## How gates behave

> **Gates detect and route. Owners fix.**

A gate is a constrained inspector. It does not silently rewrite a spec to resolve ambiguity. It does not pick a winner in a merge conflict. It does not improvise scope. It emits findings and routes fixes to the command that owns the artifact.

This is what makes OrderSpec safe under a weak model: the model is never trusted to silently "improve" your contract.

## Brownfield projects

If you are applying OrderSpec to an existing codebase (a brownfield project), you don't need to write specs for everything manually. You can use the reverse-engineering command to extract specifications directly from your existing code.

Use `/order.code-to-spec` to scan existing modules and generate a compliant `spec.md`:

```bash
# Scan an existing directory or module and generate a spec
/order.code-to-spec "path/to/existing/module"
```

**How it works:**
- The command scans the specified code area, extracting interfaces, entities, and observable behaviors.
- It translates technical implementation details (frameworks, libraries) into logical WHAT-contracts, routing new technologies to `/order.bootstrap` for registration.
- It generates a standard `spec.md` that seamlessly fits into the downstream pipeline (`/order.plan`, `/order.tasks`).

**Note:** Code extraction requires understanding implicit business logic. It is recommended to use a more capable model for `/order.code-to-spec` than for standard forward-engineering commands.

## Documentation

- [Getting Started](docs/getting-started.md) — setup, bootstrap phases, pipeline walkthrough
- [Architecture](docs/architecture.md) — three-document model, pipeline details, gates, governance, command context, repository layout
- [Multi-Agent Support](docs/multi-agent.md) — adapter pattern, external rules, adding new agents
- [Philosophy](docs/philosophy.md) — why OrderSpec exists, design principles, comparison with spec-kit and OpenSpec
- [Reference](docs/reference.md) — customization, useful checks, roadmap, limitations

## Design principles

- **Weak-model-first.** Tuned for modest models, not only frontier models.
- **Deterministic scripts own mechanical work.** AI agent = semantic glue between deterministic logic parts.
- **Gates detect and route; owners fix.** A gate is an inspector, not an author.
- **Default-deny capabilities.** Commands and gates only do what project governance permits.
- **Agent-agnostic core.** Framework core is independent of any specific AI agent; agent-specific logic lives in adapters.
