# Coding Agent Context Extension

This bundled extension manages the **coding agent context/instruction file** (e.g. `CLAUDE.md`, `.github/copilot-instructions.md`, `AGENTS.md`, `GEMINI.md`, …) for the active integration.

It owns the lifecycle of the managed section delimited by the configurable start/end markers (defaults: `<!-- ORDERSPEC START -->` / `<!-- ORDERSPEC END -->`).

## Why an extension?

Not every OrderSpec user wants OrderSpec to write into the coding agent's context file. Extracting this behavior into a dedicated extension lets users:

- **Opt out** entirely with `orderspec extension disable agent-context` — OrderSpec will then never create or modify the agent context file.
- **Customize the markers** by editing `.orderspec/extensions/agent-context/agent-context-config.yml` — both the Python layer and the bundled scripts honor the same `context_markers` value.
- **Refresh on demand** with `/order.agent-context.update`, or automatically through the hooks declared in `extension.yml` (`after_spec`, `after_plan`).

## Commands

| Command | Description |
|---------|-------------|
| `order.agent-context.update` | Refresh the managed section in the agent context file with the current plan path. |

## Configuration

All configuration flows through the extension's own config file at
`.orderspec/extensions/agent-context/agent-context-config.yml`:

```yaml
# Path to the coding agent context file managed by this extension
context_file: CLAUDE.md

# Delimiters for the managed OrderSpec section
context_markers:
  start: "<!-- ORDERSPEC START -->"
  end: "<!-- ORDERSPEC END -->"
```

- `context_file` — the project-relative path to the coding agent context file, written by `orderspec init` and `orderspec integration install`.
- `context_markers.start` / `.end` — the delimiters around the managed section. Edit these to use custom markers.

## Requirements

The bundled update scripts require **Python 3** with **PyYAML** for YAML/upsert processing (PowerShell can also use `ConvertFrom-Yaml` when available).

PyYAML ships with the `spec` CLI and is normally available via the same `python3` interpreter. If a hook reports *"PyYAML is required … not available in the current Python environment"*, it means the system `python3` differs from the one used to install OrderSpec. To resolve, run:

```bash
pip install pyyaml
# or target the specific interpreter OrderSpec uses:
/path/to/order-python -m pip install pyyaml
```

## Disable

```bash
orderspec extension disable agent-context
```

When disabled, OrderSpec skips context file creation, updates, and removal (the gates are inside `upsert_context_section()` and `remove_context_section()`).
