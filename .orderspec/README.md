# OrderSpec

**Spec-driven development for relatively weak LLMs — built for engineers,
hardened for teams.**

OrderSpec treats a feature specification as a contract and moves mechanical
resolution, validation, state management, and synchronization into
deterministic scripts. The AI agent performs narrow semantic work inside
explicit boundaries.

Supported agent adapters:

- [Kilo Code](https://kilo.ai/) (`.kilo/` and legacy `.kilocode/`)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (`.claude/` and `CLAUDE.md`)
- [Codex](https://openai.com/codex/) (repository skills in `.agents/skills/`)

## Documentation

Framework documentation is bundled under [`.orderspec/framework/docs/`](framework/docs/).
It is framework-owned, read-only material, not generated project state.

| Document | Read it when you need to understand… |
|---|---|
| [Getting Started](framework/docs/getting-started.md) | installation, agent sync, bootstrap, the feature workflow, gates, or brownfield extraction |
| [Architecture](framework/docs/architecture.md) | artifact ownership and lifecycles, gates, governance, command context, feedback, rollback, or repository layout |
| [Multi-Agent Support](framework/docs/multi-agent.md) | adapters, prompt/skill delivery, worker selection and configuration, or adding an agent |
| [Continuous Execution](framework/docs/continuous-execution.md) | optional automatic routing, operator interrupts, context isolation, run checkpoints, or loop limits |
| [Philosophy](framework/docs/philosophy.md) | design principles, weak-model-first reasoning, or comparison with spec-kit and OpenSpec |
| [Reference](framework/docs/reference.md) | supported customization, direct script commands, tests, limitations, or roadmap |

**For AI agents:** this README is only an entry point. Before changing the
framework or executing a non-trivial OrderSpec workflow, read the document(s)
whose purpose matches the task. Framework behavior is defined by
`framework/orderspec-rules.md` and command context, not by this overview.

## Core model

```text
/order.bootstrap
      ↓
/order.spec  →  /order.plan  →  /order.tasks  →  /order.code
   WHAT           WHERE/HOW        ORDER            IMPLEMENT
```

Each feature uses three artifacts with separate owners and lifecycles:

| Document | Role | Lifecycle |
|---|---|---|
| `spec.md` | logical **WHAT** contract | stable source of truth |
| `plan.md` | physical **WHERE/HOW** mapping | baseline for one work order |
| `tasks.md` | execution **ORDER** | disposable work order |

The plan is derived from the specification, project contracts, and repository
state. Tasks are derived from the plan. Code is executed from bounded task
packets. Optional `*-check` gates inspect artifacts and route defects to the
command that owns them; gates do not repair inspected artifacts.

## Requirements

- Python 3
- shell access
- at least one supported AI agent

No package manager, installer, or framework daemon is required.

## Quick start

Copy `.orderspec/` to the project root, then run:

```bash
# Detect agents interactively and synchronize commands and skills
python3 .orderspec/framework/scripts/agents_sync.py sync
```

```text
/order.bootstrap
/order.spec "describe the feature you want"
/order.feature --select FEAT-001-example
/order.plan
/order.tasks
/order.code
/order.code-check
```

In Codex, synced commands are repository skills such as `$order-bootstrap` and
`$order-spec`. For complete setup, verification gates, brownfield usage, and
agent-specific commands, read [Getting Started](framework/docs/getting-started.md).

## Essential principles

- Specs are the stable source of truth; plans and tasks are derived.
- Deterministic scripts own mechanical work.
- Deterministic state machines select one bounded semantic question at a time.
- Gates detect and route; artifact owners fix.
- Capabilities are default-deny and governed by project contracts.
- Every requirement traces forward, and every implementation file traces back.
- Agent-specific behavior stays in adapters; the framework core is agent-agnostic.

See [Philosophy](framework/docs/philosophy.md) for the complete rationale and
[Architecture](framework/docs/architecture.md) for the operational model.

## License

[MIT](LICENSE)
