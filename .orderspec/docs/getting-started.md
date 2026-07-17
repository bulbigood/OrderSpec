# Getting Started

## Environment requirements

- `python3`
- Shell access capable of running the framework scripts
- At least one supported AI agent installed (Kilo Code, Claude Code, and/or Codex)

No package manager, no `uv`, no installer, no framework daemon.

## Setup

1. Copy the `.orderspec/` directory into your project.

2. **Initial sync (required once):** Run this in your terminal to copy prompts to the agent's command directory:

   ```bash
   # For Kilo Code:
   python3 .orderspec/framework/scripts/agents_sync.py sync --agents kilocode

   # For Claude Code:
   python3 .orderspec/framework/scripts/agents_sync.py sync --agents claude_code

   # For Codex:
   python3 .orderspec/framework/scripts/agents_sync.py sync --agents codex

   # For both:
   python3 .orderspec/framework/scripts/agents_sync.py sync --agents kilocode claude_code

   # For all three:
   python3 .orderspec/framework/scripts/agents_sync.py sync --agents kilocode claude_code codex
   ```

3. Run bootstrap:

   ```text
   /order.bootstrap

   In Codex, invoke the synced skill as `$order-bootstrap`.
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

4. Run the feature pipeline:

   ```text
   /order.spec "describe the feature you want"
   /order.plan
   /order.tasks
   /order.code
   /order.code-check
   ```

   In Codex, use `$order-spec`, `$order-plan`, `$order-tasks`, `$order-code`, and `$order-code-check`.

5. Run per-stage gates when you want earlier verification:

   ```text
   /order.spec-check
   /order.plan-check
   /order.tasks-check
   /order.code-check
   /order.sync-check
   ```

   `/order.code-check` is the terminal verification gate and is required before a feature may be considered `implemented`. It may be deferred during iteration, but `/order.code` output remains `implementing` and unverified until this gate passes.

6. Re-run bootstrap when project-level contracts need to evolve:

   ```text
   /order.bootstrap
   ```

## Bootstrap phases

```text
1. Command Context Resolution (via command_context.py)
2. Mode Detection (Init / Amend / Targeted Amend)
3. Deterministic Bootstrap Script (bootstrap_contracts.py)
4. Gate Capabilities Question
5. Agents Discovery & Sync Phase
6. Tooling Discovery Phase
7. External Rules Integration Phase
8. Report
```

**Agents Discovery & Sync Phase** detects project markers, asks the operator which to enable, and synchronizes prompts and skills configuration. For Codex, it renders command prompts as repository skills in `.agents/skills/`.

**External Rules Integration Phase** reads rule files from enabled agents (AGENTS.md, CLAUDE.md, etc.) and offers to integrate uncovered statements into `conventions.md`.
