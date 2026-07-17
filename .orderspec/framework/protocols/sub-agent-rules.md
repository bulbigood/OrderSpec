---
orderspec:
  artifact: protocol
  authority: framework
---

# OrderSpec Sub-Agent Rules

## Purpose

These rules apply to every OrderSpec command, skill, or future prompt that may
delegate work. `sub-agent-execution.md` defines the task packet and result
boundary. This file defines worker selection, readiness checks, and
configuration ownership.

Delegation is a runtime capability. Prompt synchronization, skill
registration, and the presence of `.orderspec/state/agents.json` do not prove
that the current runtime can spawn or wait for a worker.

## Worker request

Every delegating command MUST resolve one worker request before its first
dispatch. A request contains:

```yaml
caller: command or skill identifier
role: stable semantic role, for example implementation-worker
preferred_name: optional runtime-specific worker name
reasoning_effort: optional requested reasoning level
scope: project | global
```

The request is command-owned. Tasks, specs, and plans must not contain
agent-specific syntax merely to select a worker.

`/order.code` uses this default request only when its user input permits
delegation. Explicit instructions to avoid sub-agents, use one agent, or keep
all work in one agent session select the command's local mode and skip worker
resolution entirely. `medium` is the default for a newly configured worker;
an existing valid worker reports and keeps its own configured level.

```yaml
caller: order.code
role: implementation-worker
preferred_name: worker
reasoning_effort: medium
scope: project
```

The `worker` name is a preference, not a guarantee. A command MUST use the
current runtime's adapter to decide whether that name exists and is valid.

## Selection algorithm

1. Resolve explicit user execution constraints. If delegation is prohibited,
   use the command's documented local mode. Do not inspect, configure,
   dispatch, or wait for a worker.
2. Resolve actual runtime dispatch capability. Do not infer it from adapter
   detection or `agents.json`.
3. Identify the current runtime agent and select its registered adapter. Do
   not guess an agent from the list of enabled agents when multiple agents are
   present.
4. Resolve the request's preferred name. If no name is supplied, use the
   adapter's documented default or its built-in execution worker.
5. Ask the adapter to inspect that name. The adapter owns discovery rules,
   valid fields, built-in names, and configuration paths.
6. Use the worker only when the adapter reports `configured: true` and
   `valid: true`. Built-in workers are valid only when the adapter explicitly
   reports them.
7. If the worker is missing or invalid, do not dispatch. Ask the operator to
   choose a worker name and reasoning effort, then invoke the adapter's
   explicit configuration operation. Never silently invent a name, model, or
   reasoning level.
8. Re-run inspection after configuration. Continue only after the requested
   worker is reported ready.
9. Use the resolved worker for every dispatch in the current command. A later
   command may resolve a different role or worker.

If dispatch is unavailable, use the command's documented local fallback. Do
not configure a worker merely because local execution was selected.

## Configuration scope

Project scope is the default. It makes the worker role, instructions, and
reasoning choice reproducible for this repository and reviewable alongside
other project configuration.

Global scope is personal configuration and affects unrelated repositories. It
MUST be selected explicitly by the operator. An adapter MUST NOT write global
configuration as an implicit fallback.

Configuration belongs to the agent adapter. The framework core MUST NOT parse
or write Codex TOML, Claude configuration, Kilo configuration, or any future
agent format.

## Adapter contract

An adapter that supports named workers exposes:

- `subagent_policy()` — discovery, scopes, built-ins, required fields, and
  supported reasoning values;
- `inspect_subagents(project_root, requested_name, scope)` — read-only
  readiness and validation report;
- `configure_subagent(...)` — explicit, user-authorized native configuration
  write.

An adapter without a named-worker configuration surface reports runtime-only
  management. It must not pretend that prompt or skill sync created a worker.

The deterministic entry point is:

```bash
python3 .orderspec/framework/scripts/agents_sync.py subagents inspect \
  --agent <runtime-agent> --name <worker-name> --json
```

To configure after operator choice:

```bash
python3 .orderspec/framework/scripts/agents_sync.py subagents configure \
  --agent <runtime-agent> --name <worker-name> \
  --reasoning <level> --scope project --json
```

Interactive callers may use `subagents ensure`; non-interactive callers must
provide the name and reasoning explicitly and must stop with a user-input
request when either is missing.

## Future callers

The same request and selection algorithm applies to `/order.plan`, gates,
skills, hooks, and other future callers. Only `caller`, `role`, preferred
worker, and reasoning need to change. Agent-specific deployment and lifecycle
rules remain in adapters; shared safety and worker-boundary rules remain here.
