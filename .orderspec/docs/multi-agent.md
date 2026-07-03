# Multi-Agent Support

OrderSpec is not tied to a specific AI agent. It uses a deterministic **adapter pattern** to support multiple agents simultaneously.

## Supported agents

| Agent | Detection | Prompts delivered to | Skills registration | Rules read from |
|---|---|---|---|---|
| **Kilo Code** | `.kilo/` dir or `kilo.jsonc` (new); `.kilocode/` dir (legacy) | `.kilo/commands/` (new); `.kilocode/workflows/` (legacy) — copied, no symlinks | `skills.paths` array in `kilo.jsonc` | `AGENTS.md`, files from `instructions` array in `kilo.jsonc`, `.kilocode/rules/*.md` (legacy) |
| **Claude Code** | `.claude/` dir or `CLAUDE.md` at root | `.claude/commands/` — copied | Symlink: `.claude/skills` → `.orderspec/skills` | `CLAUDE.md`, `.claude/CLAUDE.md` |

## How it works

1. **Detection**: each adapter's `detect()` method checks the project for signs of its agent.
2. **Prompt sync**: OrderSpec prompts live in `.orderspec/framework/prompts/` as a single source of truth. Each adapter copies them to the agent's commands directory. SHA-256 hashing avoids unnecessary copies.
3. **Skills registration**: instead of copying skills, each adapter registers `.orderspec/skills/` in the agent's config — one source of truth.
4. **External rules**: each adapter reads agent-specific rule files (AGENTS.md, CLAUDE.md, etc.) for optional integration into `conventions.md` during bootstrap.

## Adapter architecture

```text
.orderspec/framework/adapters/
├── base.py          # AgentAdapter interface (detect, sync_skills_dir, sync_prompts, read_rules)
├── registry.py      # Adapter registry
├── kilocode.py      # Kilo Code adapter
├── claude_code.py   # Claude Code adapter
└── jsonc_utils.py   # JSONC read/write utilities for kilo.jsonc
```

## Agent state

Multi-agent configuration and sync state lives in:

```text
.orderspec/state/agents.json
```

This file is generated and maintained by `.orderspec/framework/scripts/agents_sync.py`. It records which agents are enabled, their detection info, and sync state (last sync timestamp, copied/skipped prompts).

## Adding a new agent adapter

1. Create a new file in `.orderspec/framework/adapters/` implementing the `AgentAdapter` interface from `base.py`.
2. Register it in `registry.py`.
3. The adapter must implement four methods: `detect`, `sync_skills_dir`, `sync_prompts`, `read_rules`.

The framework core remains agent-agnostic. All agent-specific logic lives in adapters.

## External rules integration policy

The policy is defined in `constitution.md`:

| Policy | Behavior |
|---|---|
| `constrain_on_bootstrap` (default) | Rule files are read only during `/order.bootstrap`. Content is offered for integration into `conventions.md`. After bootstrap, OrderSpec commands work only with their own contracts. |
| `constrain_always` | Rule files are loaded as constrain source for every command. May conflict with OrderSpec contracts. Use with caution. |
| `ignore` | Rule files are not read by OrderSpec at all. |

The principle is: **external rules are detected and routed, never silently applied.**
