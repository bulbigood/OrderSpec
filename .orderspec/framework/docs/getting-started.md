# Getting Started

This guide covers project installation and normal feature workflows. For
artifact semantics and internal behavior, read [Architecture](architecture.md).

## Requirements

- Python 3
- shell access capable of running framework scripts
- Kilo Code, Claude Code, and/or Codex

No package manager, `uv`, installer, or framework daemon is required.

## Install and synchronize

1. Copy the complete `.orderspec/` directory into the project root.

2. Synchronize OrderSpec commands and project skills with detected agents:

   ```bash
   # Interactive detection and selection
   python3 .orderspec/framework/scripts/agents_sync.py sync

   # Or select adapters explicitly
   python3 .orderspec/framework/scripts/agents_sync.py sync \
     --agents kilocode claude_code codex
   ```

   Use one or more adapter IDs after `--agents`. Re-run synchronization after
   framework prompts change or an agent is added. See
   [Multi-Agent Support](multi-agent.md) for delivery paths and worker setup.

3. Bootstrap project-level contracts:

   ```text
   /order.bootstrap
   ```

   In Codex, invoke synced commands as repository skills, for example
   `$order-bootstrap`.

Bootstrap creates or refines:

```text
.orderspec/contracts/constitution.md
.orderspec/contracts/stack.md
.orderspec/contracts/architecture.md
.orderspec/contracts/conventions.md
.orderspec/config/automation.json
.orderspec/config/tooling.json
.orderspec/state/tooling-detection.json
.orderspec/state/agents.json
.orderspec/state/active-feature.json
```

It also detects agents and tooling, synchronizes enabled agents, derives
reusable skill needs from the project contracts, and—after approval for the
exact search queries—compares popular discovery candidates. Bootstrap asks
which candidate/configuration to install, vendors approved skills once under
`.orderspec/skills/`, exposes that canonical directory through approved agent
adapters, and offers to integrate external agent rules according to the
constitution.

Continuous execution is optional and disabled by default. Review and enable
`.orderspec/config/automation.json` when an external runtime adapter or the
synchronized Codex `order-code` coordinator will drive commands. See
[Continuous Execution](continuous-execution.md) for routing rules, operator
interrupts, and persistent run-state commands.

## Create and implement a feature

Run the authoring pipeline in order:

```text
/order.spec "describe the feature you want"
/order.plan
/order.tasks
/order.code
```

In Codex, use `$order-spec`, `$order-plan`, `$order-tasks`, and `$order-code`.
Each command resolves the active feature and its required inputs through
command context.

Switch between existing features explicitly; other commands never infer a
selection from prose:

```text
/order.feature --select FEAT-002-billing
```

Run `/order.feature` without controls to inspect current selection and list
available features.

Run verification gates at the boundary where feedback is most useful:

```text
/order.spec-check
/order.plan-check
/order.tasks-check
/order.code-check
```

`/order.code-check` is the terminal verification gate. Until it passes, the
feature remains implementing rather than verified as implemented. Gates are
inspectors: they write reports and route defects to the owning author command.

## Existing code (brownfield)

Use the reverse-engineering command to derive a compliant logical contract
from an existing code area:

```text
/order.code-to-spec "path/to/existing/module"
```

In Codex, use `$order-code-to-spec`. The command extracts observable behavior,
interfaces, and entities while keeping implementation details in project
contracts or the later plan. Because implicit business logic requires broader
judgment, use a capable model and review the resulting specification before
continuing with `/order.plan`.

## Bootstrap lifecycle

The initial bootstrap creates a deterministic baseline. Later runs default to
Refine: they audit project contracts against current framework rules,
repository evidence, and project skill bindings. The successful baseline is
stored in `.orderspec/state/bootstrap.json`.

Run `/order.bootstrap` again when the stack, architectural boundaries,
conventions, governance, enabled agents, or project skills change. Do not edit
framework-owned files to record project-specific decisions; those belong in
`.orderspec/contracts/`, `.orderspec/config/`, or `.orderspec/skills/`.

## Recovery and reset

During implementation, completed tasks and the plan baseline are protected.
When a safe Git-backed work-order baseline exists, `/order.code --reset`
previews and restores only planned paths, then clears task progress after the
rollback succeeds. If execution finds an upstream contract, plan, or task
defect, it persists feedback for the owning command instead of silently
rewriting the artifact. See [Architecture](architecture.md#work-order-state-and-feedback).
