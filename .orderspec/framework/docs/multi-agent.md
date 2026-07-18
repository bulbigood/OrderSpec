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
2. **Prompt sync**: OrderSpec prompts live in `.orderspec/framework/prompts/` as a single source of truth. Each adapter injects its runtime-specific worker rules and delivers the result to the agent's command surface. SHA-256 hashing avoids unnecessary copies; Codex renders each prompt as a `SKILL.md`.
3. **Skills registration**: instead of copying project skills, each adapter registers `.orderspec/skills/` in the agent's config or native discovery path — one source of truth.
4. **Worker provisioning and inspection**: bootstrap proposes current weak/medium/strong model bindings, asks for operator confirmation, and writes native config through the current adapter. Before delegation, the command asks that adapter to validate the selected role. Sync never creates workers silently.
5. **External rules**: each adapter reads agent-specific rule files for optional, operator-approved integration into the owning governance, stack, architecture, or conventions contract during bootstrap.

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

Prompt synchronization injects adapter-owned sub-agent rules but remains
separate from dispatch. `/order.code`
checks the current runtime's actual dispatch capability, then selects delegated
execution, phase-local execution, or an explicit all-local fallback.
`/order.code --all --local` and `--no-subagents` keep work in the current agent
session and skip worker inspection.

Inspect a selected worker before dispatch:

```bash
python3 .orderspec/framework/scripts/agents_sync.py subagents inspect \
  --agent codex --name orderspec.worker.weak --json
```

Create a missing worker through the adapter's default policy, or configure one
explicitly:

```bash
python3 .orderspec/framework/scripts/agents_sync.py subagents ensure \
  --agent codex --name orderspec.worker.weak --json

python3 .orderspec/framework/scripts/agents_sync.py subagents configure \
  --agent codex \
  --name orderspec.worker.weak \
  --reasoning low \
  --scope project \
  --model <model-id> \
  --json
```

Bootstrap closes the Codex agents phase only after
`subagents validate-orderspec` returns a configuration-readiness receipt. This
receipt validates the exact model, explicit reasoning field, and canonical
worker instructions in project TOML. Actual model/effort availability remains
runtime-owned and is checked by dispatch; TOML inspection does not claim it.

For Codex, bootstrap currently requires only `orderspec.worker.weak`, because it
is the only role consumed by `/order.code`. The AI proposes its exact current
model and `model_reasoning_effort`, prioritizing reliable bounded-envelope
execution before cost, and the operator approves the mapping. Reserved
medium/strong roles are not provisioned until a deterministic framework
consumer uses them. OrderSpec never falls back to the built-in `worker` or
inherits the coordinator model. Global configuration is available only when
explicitly selected with `--scope global`.

Worker selection follows the rules injected by the active adapter during
`agents_sync.py sync`.

### Task boundary

Worker execution follows:

```text
coordinator reads context
      ↓
self-contained worker envelope with explicit read/write paths
      ↓
worker executes one task
      ↓
structured result + deterministic attempt snapshot comparison
      ↓
task_progress.py marks one [X]
```

The coordinator contract lives in
`.orderspec/framework/protocols/sub-agent-execution.md`. `code_workflow.py`
renders the canonical worker-only rules, finite paths, exact contract excerpts,
default-deny capabilities, and result schema into one envelope. Local and
delegated executors receive that envelope verbatim, not framework protocol files
or the whole OrderSpec context.

## Adding a new agent adapter

1. Create a new file in `.orderspec/framework/adapters/` implementing the `AgentAdapter` interface from `base.py`.
2. Register it in `registry.py`.
3. The adapter must implement four core methods: `detect`, `sync_skills_dir`, `sync_prompts`, `read_rules`.
4. Implement `subagent_rules` for the runtime-specific instructions injected
   into delegating/bootstrap commands.
5. If the agent has named worker configuration, implement `subagent_policy`,
   `inspect_subagents`, and `configure_subagent`; otherwise report runtime-only
   worker management through the base implementation.

The framework core remains agent-agnostic. All agent-specific logic lives in adapters.

## External rules integration policy

The policy is defined in `constitution.md`:

| Policy | Behavior |
|---|---|
| `constrain_on_bootstrap` (default) | Rule files are read only during `/order.bootstrap`. Content is classified and offered for integration into its owning project contract. After bootstrap, OrderSpec commands work only with their own contracts. |
| `ignore` | Rule files are not read by OrderSpec at all. |

The principle is: **external rules are detected and routed, never silently applied.**
