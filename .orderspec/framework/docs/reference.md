# Reference

This document indexes supported extension points, diagnostic commands, tests,
known limitations, and planned directions. Normal project setup belongs in
[Getting Started](getting-started.md).

## Customization boundary

Supported:

- optional verification gates;
- governance through `.orderspec/contracts/constitution.md`;
- stack, architecture, and conventions through `.orderspec/contracts/`;
- documentation and skill policy through `.orderspec/config/tooling.json`;
- project skills under `.orderspec/skills/`;
- agent adapters under `.orderspec/framework/adapters/`;
- external-rules integration policy in the constitution.
- optional automatic routing policy through `.orderspec/config/automation.json`.

Not supported:

- operator-defined lifecycle extension execution;
- arbitrary prompt hooks;
- custom procedural instructions loaded from project configuration.

Project-managed configuration is data and constraints, not procedural prompt
authority. Framework procedure remains in framework-owned rules and prompts.

## Direct diagnostics

These commands are intended for framework development, auditing, and targeted
debugging. Add `--help` to a command or subcommand for its complete interface.

```bash
# Command context
python3 .orderspec/framework/scripts/command_context.py validate --json
python3 .orderspec/framework/scripts/command_context.py resolve order.bootstrap --json

# Bootstrap contracts
python3 .orderspec/framework/scripts/bootstrap_contracts.py inspect --json
python3 .orderspec/framework/scripts/bootstrap_contracts.py audit --json
python3 .orderspec/framework/scripts/bootstrap_contracts.py validate --json
python3 .orderspec/framework/scripts/bootstrap_contracts.py complete --json

# Work-order state and upstream feedback
python3 .orderspec/framework/scripts/task_progress.py validate --tasks <feature>/tasks.md
python3 .orderspec/framework/scripts/work_order.py rollback --feature-dir <feature>
python3 .orderspec/framework/scripts/workflow_feedback.py list \
  --feature-dir <feature> --target order.tasks
python3 .orderspec/framework/scripts/workflow_feedback.py list \
  --scope project --project-root . --target order.bootstrap

# Agent detection, synchronization, and state
python3 .orderspec/framework/scripts/agents_sync.py detect --json
python3 .orderspec/framework/scripts/agents_sync.py sync \
  --agents kilocode claude_code codex --json
python3 .orderspec/framework/scripts/agents_sync.py read-rules \
  --agents kilocode claude_code codex --json
python3 .orderspec/framework/scripts/agents_sync.py state --json

# Continuous execution policy and persistent run state
python3 .orderspec/framework/scripts/automation_policy.py validate
python3 .orderspec/framework/scripts/automation_policy.py classify \
  --event-file <event.json>
python3 .orderspec/framework/scripts/workflow_supervisor.py start \
  --feature-dir <feature> --command order.code
python3 .orderspec/framework/scripts/workflow_supervisor.py status \
  --run-file <run-file>
```

`work_order.py rollback` previews by default; pass `--apply` only after
reviewing the bounded rollback.

## Regression tests

The master runner recursively discovers `test-*.py`, `test_*.py`, and
`*_test.py` under `.orderspec/framework/scripts/test/`, applies a per-test
timeout, reports progress, and exits non-zero on failure:

```bash
python3 .orderspec/framework/scripts/run_all_tests.py
```

Run an individual test file directly only when isolating a failure.

## Current limitations

- Skill discovery and installation are operator-approved bootstrap steps;
  unattended installation is not supported.
- Python 3 is required by the framework scripts.
- Contract paths under `.orderspec/contracts/` are fixed.
- Operator-defined procedural extensions and arbitrary prompt hooks are not
  supported.
- Facts that bootstrap cannot infer safely remain explicitly unresolved.
- Adapters currently cover Kilo Code, Claude Code, and Codex only.
- Claude Code skill registration uses a symlink, which can require developer
  mode on Windows.
- The continuous supervisor core is runtime-neutral; agent-specific unattended
  invocation drivers must submit schema-valid terminal events.

Unresolved markers are intentional: an explicit unknown is safer than an
invented project contract.

## Roadmap

- adapters for additional agents;
- Codex, Claude Code, and Kilo continuous-execution runtime drivers;
- improved cross-platform behavior;
- MDA-like structures alongside feature specifications;
- a system-level specification graph with cross-spec validation;
- explicit subsystem interface contracts;
- additional machine-readable specification structures and generated views;
- BDD/Gherkin test integration.
