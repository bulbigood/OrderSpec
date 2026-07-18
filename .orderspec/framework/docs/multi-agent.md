# Multi-Agent Support

OrderSpec is not tied to a specific AI agent. It uses a deterministic **adapter pattern** to support multiple agents simultaneously.

## Supported agents

| Agent | Detection | Prompts delivered to | Skills registration | Rules read from |
|---|---|---|---|---|
| **Kilo Code** | `.kilo/` dir or `kilo.jsonc` (new); `.kilocode/` dir (legacy) | `.kilo/commands/` (new); `.kilocode/workflows/` (legacy) — copied, no symlinks | `skills.paths` array in `kilo.jsonc` | `AGENTS.md`, files from `instructions` array in `kilo.jsonc`, `.kilocode/rules/*.md` (legacy) |
| **Claude Code** | `.claude/` dir or `CLAUDE.md` at root | `.claude/commands/` — copied | Symlink: `.claude/skills` → `.orderspec/skills` | `CLAUDE.md`, `.claude/CLAUDE.md` |
| **Codex** | `.codex/`, `.agents/skills/`, `AGENTS.md`, or `.codex-plugin/plugin.json` | `.agents/skills/<order-command>/SKILL.md` — rendered from prompts | Symlink: `.agents/skills` → `.orderspec/skills`; existing real directory is preserved | `AGENTS.override.md` or `AGENTS.md` |

## How it works

1. **Detection**: each adapter's `detect()` method checks the project for signs of its agent.
2. **Prompt sync**: OrderSpec prompts live in `.orderspec/framework/prompts/` as a single source of truth. Each adapter delivers them to the agent's command surface. SHA-256 hashing avoids unnecessary copies; Codex renders each prompt as a `SKILL.md`.
3. **Skills registration**: instead of copying project skills, each adapter registers `.orderspec/skills/` in the agent's config or native discovery path — one source of truth.
4. **Worker inspection**: before delegation, the command asks the current runtime adapter to validate its selected worker. Sync never creates one silently.
5. **External rules**: each adapter reads agent-specific rule files (AGENTS.md, CLAUDE.md, etc.) for optional integration into `conventions.md` during bootstrap.

## Adapter architecture

```text
.orderspec/framework/adapters/
├── base.py          # AgentAdapter interface plus worker policy/inspection/configuration
├── registry.py      # Adapter registry
├── kilocode.py      # Kilo Code adapter
├── claude_code.py   # Claude Code adapter
├── codex.py         # Codex adapter
└── jsonc_utils.py   # JSONC read/write utilities for kilo.jsonc
```

## Agent state

Multi-agent configuration and sync state lives in:

```text
.orderspec/state/agents.json
```

This file is generated and maintained by `.orderspec/framework/scripts/agents_sync.py`. It records which agents are enabled, their detection info, and sync state (last sync timestamp, copied/skipped prompts).

## Worker selection and configuration

Prompt synchronization is separate from sub-agent dispatch. `/order.code`
checks the current runtime's actual dispatch capability, then selects delegated
execution, phase-local execution, or an explicit all-local fallback.
`/order.code --all --local` and `--no-subagents` keep work in the current agent
session and skip worker inspection.

Inspect a selected worker before dispatch:

```bash
python3 .orderspec/framework/scripts/agents_sync.py subagents inspect \
  --agent codex --name worker --json
```

Create a missing worker through the adapter's default policy, or configure one
explicitly:

```bash
python3 .orderspec/framework/scripts/agents_sync.py subagents ensure \
  --agent codex --name worker --json

python3 .orderspec/framework/scripts/agents_sync.py subagents configure \
  --agent codex \
  --name worker \
  --reasoning high \
  --scope project \
  --model <model-id> \
  --json
```

For Codex, the built-in `worker` inherits the parent session's model and
reasoning settings. A project-scoped custom definition is written to
`.codex/agents/worker.toml` and takes precedence. Omit `--model` when inherited
model selection is desired. Global worker configuration is available only
when explicitly selected with `--scope global`.

Worker selection follows
`.orderspec/framework/protocols/sub-agent-rules.md`.

### Task boundary

Worker execution follows:

```text
coordinator reads context
      ↓
task packet with explicit read/write paths
      ↓
worker executes one task
      ↓
structured result + allowed diff check
      ↓
task_progress.py marks one [X]
```

The packet and result contract lives in
`.orderspec/framework/protocols/sub-agent-execution.md`. The worker receives
one rendered packet with finite read/write paths and exact contract excerpts,
not the protocol file or the whole OrderSpec context.

## Adding a new agent adapter

1. Create a new file in `.orderspec/framework/adapters/` implementing the `AgentAdapter` interface from `base.py`.
2. Register it in `registry.py`.
3. The adapter must implement four core methods: `detect`, `sync_skills_dir`, `sync_prompts`, `read_rules`.
4. If the agent has named worker configuration, implement `subagent_policy`,
   `inspect_subagents`, and `configure_subagent`; otherwise report runtime-only
   worker management through the base implementation.

The framework core remains agent-agnostic. All agent-specific logic lives in adapters.

## External rules integration policy

The policy is defined in `constitution.md`:

| Policy | Behavior |
|---|---|
| `constrain_on_bootstrap` (default) | Rule files are read only during `/order.bootstrap`. Content is offered for integration into `conventions.md`. After bootstrap, OrderSpec commands work only with their own contracts. |
| `constrain_always` | Rule files are loaded as constrain source for every command. May conflict with OrderSpec contracts. Use with caution. |
| `ignore` | Rule files are not read by OrderSpec at all. |

The principle is: **external rules are detected and routed, never silently applied.**
