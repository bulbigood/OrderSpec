# Reference

## Customization

OrderSpec is meant to bend to your project, but customization is deliberately constrained.

Supported today:

- optional verification gates;
- project governance through `constitution.md`;
- project stack/architecture/conventions through `.orderspec/contracts/`;
- tooling policy through `.orderspec/config/tooling.json`;
- deterministic framework scripts;
- multi-agent adapter pattern for adding AI agent support;
- external rules integration policy in constitution.

Not supported yet:

- operator-defined lifecycle extension execution;
- arbitrary prompt hooks;
- custom procedural instructions loaded from project config.

This restriction is intentional. Operator-managed configuration is data, not procedural prompt authority.

## Useful direct checks

These are framework-level checks, useful during development or debugging.

```bash
# Command context resolver
python3 .orderspec/framework/scripts/command_context.py validate --json
python3 .orderspec/framework/scripts/command_context.py resolve order.bootstrap --json

# Bootstrap contracts
python3 .orderspec/framework/scripts/bootstrap_contracts.py inspect --json
python3 .orderspec/framework/scripts/bootstrap_contracts.py validate --json

# Multi-agent sync
python3 .orderspec/framework/scripts/agents_sync.py detect --json
python3 .orderspec/framework/scripts/agents_sync.py sync --agents kilocode claude_code --json
python3 .orderspec/framework/scripts/agents_sync.py read-rules --agents kilocode claude_code --json
python3 .orderspec/framework/scripts/agents_sync.py state
```

Framework tests:

```bash
python3 -m py_compile .orderspec/framework/scripts/command_context.py
python3 -m py_compile .orderspec/framework/scripts/bootstrap_contracts.py
python3 -m py_compile .orderspec/framework/scripts/agents_sync.py
python3 .orderspec/framework/scripts/test/test-command-context.py
python3 .orderspec/framework/scripts/test/test-bootstrap-contracts.py
python3 .orderspec/framework/scripts/test/test-agents-sync.py
```

## Master test runner

The `run_all_tests.py` script recursively discovers and runs all test files in `.orderspec/framework/scripts/test/`. It aggregates results, handles timeouts (120s per test), and exits non-zero if any test failed.

```bash
python3 .orderspec/framework/scripts/run_all_tests.py
```

The script automatically discovers test files matching patterns: `test-*.py`, `test_*.py`, `*_test.py`. Output shows progress per test file with pass/fail status and elapsed time.

Use this to verify framework scripts after making changes to adapters, bootstrap logic, or command context resolution.

## Status and roadmap

Future work:

- 🔜 Adapters for more agents (OpenCode, Cursor, Windsurf, ...).
- 🔜 Better cross-platform support.
- 🔜 MDA-like spec structure in addition to existing feature-specs.
- 🔜 System-level spec graph: cross-spec validation and traceability.
- 🔜 Explicit interface contracts between subsystems — to keep code changes localized and their blast radius predictable.
- 🔜 Machine-readable specs: YAML "islands" with schema validation and auto-generated views, to detect and reduce spec drift.
- 🔜 BDD/Gherkin tests.

## Current limitations

- Setup is manual (no installer yet).
- Python 3 is required for current framework scripts.
- Project contract files live under `.orderspec/contracts/`; names there may still overlap with other frameworks if paths are made configurable in the future.
- Operator-defined procedural extensions are not supported yet.
- Some project facts cannot be inferred safely during bootstrap and are marked unresolved instead of guessed.
- Not all AI agents are supported yet — only Kilo Code and Claude Code.
- Claude Code skills registration uses a symlink, which may not work on all platforms (Windows without developer mode).

This is intentional: OrderSpec prefers an explicit unresolved marker over a hallucinated contract.
