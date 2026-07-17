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

## Adding a new agent adapter

1. Create a new file in `.orderspec/framework/adapters/` implementing the `AgentAdapter` interface from `base.py`.
2. Register it in `registry.py`.
3. The adapter must implement four core methods: `detect`, `sync_skills_dir`, `sync_prompts`, `read_rules`.
4. If the agent has named worker configuration, implement `subagent_policy`,
   `inspect_subagents`, and `configure_subagent`; otherwise report runtime-only
   worker management through the base implementation.

The framework core remains agent-agnostic. All agent-specific logic lives in adapters.

### Worker selection and task boundary

Prompt synchronization is not sub-agent dispatch. The adapter interface records
agent detection and prompt/skill delivery; it does not claim that the current
runtime can create or wait for child agents. `/order.code` checks actual runtime
dispatch capability and selects `DELEGATED`, `LOCAL_PHASE`, or explicit
`LOCAL_ALL` fallback. `--local`, `--no-subagents`, or an explicit instruction
to keep work in one agent session selects local execution before capability
detection; no worker is inspected or configured. Worker selection follows
`.orderspec/framework/protocols/sub-agent-rules.md`.

Codex custom workers live in project-scoped `.codex/agents/*.toml` by default.
The adapter validates the TOML schema and `name` field, recognizes built-ins,
and writes a definition only after explicit operator choice. Global
`~/.codex/agents/` configuration is available only when explicitly selected.

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
the rendered packet, not the protocol file or the whole OrderSpec context.

## External rules integration policy

The policy is defined in `constitution.md`:

| Policy | Behavior |
|---|---|
| `constrain_on_bootstrap` (default) | Rule files are read only during `/order.bootstrap`. Content is offered for integration into `conventions.md`. After bootstrap, OrderSpec commands work only with their own contracts. |
| `constrain_always` | Rule files are loaded as constrain source for every command. May conflict with OrderSpec contracts. Use with caution. |
| `ignore` | Rule files are not read by OrderSpec at all. |

The principle is: **external rules are detected and routed, never silently applied.**
