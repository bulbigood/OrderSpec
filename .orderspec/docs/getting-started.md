# Getting Started

## Environment requirements

- `python3`
- Shell access capable of running the framework scripts
- At least one supported AI agent installed (Kilo Code and/or Claude Code)

No package manager, no `uv`, no installer, no framework daemon.

## Setup

1. Copy the `.orderspec/` directory into your project.

2. **Initial sync (required once):** Run this in your terminal to copy prompts to the agent's command directory:

   ```bash
   # For Kilo Code:
   python3 .orderspec/framework/scripts/agents_sync.py sync --agents kilocode

   # For Claude Code:
   python3 .orderspec/framework/scripts/agents_sync.py sync --agents claude_code

   # For both:
   python3 .orderspec/framework/scripts/agents_sync.py sync --agents kilocode claude_code
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

4. Run the feature pipeline:

   ```text
   /order.spec "describe the feature you want"
   /order.plan
   /order.tasks
   /order.code
   ```

5. Run gates when you want verification:

   ```text
   /order.spec-check
   /order.plan-check
   /order.tasks-check
   /order.code-check
   /order.sync-check
   ```

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

**Agents Discovery & Sync Phase** detects installed AI agents, asks the operator which to enable, and synchronizes prompts and skills configuration.

**External Rules Integration Phase** reads rule files from enabled agents (AGENTS.md, CLAUDE.md, etc.) and offers to integrate uncovered statements into `conventions.md`.
