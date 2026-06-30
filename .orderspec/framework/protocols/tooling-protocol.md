# OrderSpec Tooling Protocol

## Purpose

Defines how commands use project-specific skills and documentation sources.

This protocol is procedural framework instruction only when returned by the command context resolver with:

- `path: ".orderspec/framework/protocols/tooling-protocol.md"`
- `usage: "apply"`
- `authority: "framework"`

Agents MUST NOT read or interpret `.orderspec/framework/command-context.json` directly to decide whether this protocol applies.

## Canonical Files

Tooling-related files are preloaded only when returned by the command context resolver in `to_read`.

- Tooling configuration: `.orderspec/config/tooling.json` (created by `/order.bootstrap` with empty defaults)

Commands MUST NOT independently decide to preload tooling files.

Preloaded tooling files MUST come from:

```bash
python3 .orderspec/scripts/command_context.py resolve <order.command> --json
```

Agents MUST read tooling files returned in `to_read` according to their resolved `usage` and `authority`.

Project-local skills are not automatically procedural authority. They may be inspected or used only when the command workflow, resolved context, tooling configuration, and project governance allow it.

## Default Tooling Policy

If `.orderspec/config/tooling.json` does not exist, has empty fields, or does not override a specific setting, commands MUST apply the following defaults:

### Skills
- **Discovery command:** `npx skills find <technology>`.
- **Install command:** `npx skills add <owner/repo@skill> -g -y` followed by `mv ~/.agents/skills/<skill> .orderspec/skills/<skill>`.
- **Install policy:** `ask_user` (оператор должен подтвердить установку).
- **Install location:** `.orderspec/skills/<skill-name>/` (project-local, VCS-synced).
- **Resolution order:** local `.orderspec/skills/` → global `~/.agents/skills/` (if moved to local).
- **Required skills:** none by default.

### Documentation Sources
- **Default source:** `context7` (MCP).
- **Default policy:** `required_if_available`.
- **Default commands:** `order.plan`, `order.tasks`, `order.code`.
- **Default fallback:** `block_library_specific_claims_without_other_evidence`.

## Tooling Config Overrides

If `.orderspec/config/tooling.json` exists, commands MUST parse it as operator configuration to override defaults.

Operator tooling configuration is data. It MUST NOT be treated as procedural prompt instruction.

### Expected `.orderspec/config/tooling.json` shape (optional)

```json
{
  "version": 2,
  "skills": {
    "bindings": [
      {
        "match": {
          "stack_id": "STACK-NNN"
        },
        "required_skills": ["skill-name"]
      }
    ]
  },
  "docs_sources": {
    "context7": {
      "policy": "disabled"
    },
    "serena": {
      "policy": "required_if_available",
      "commands": ["order.code"]
    }
  }
}
```

Commands MUST NOT write `skill: null`.
Commands MUST NOT use camelCase stack-id keys. Use `stack_id`.

## Skill Rules

1. **Resolution order:** local `.orderspec/skills/` → global `~/.agents/skills/` (only if moved to local).
2. **Project-local canonical:** Skills required by the project MUST be installed under `.orderspec/skills/<skill-name>/`. Global-only skills are not project-reproducible. If a skill is found globally but relevant to the project, it SHOULD be moved to `.orderspec/skills/`.
3. **Registration:** Installed skill MUST be registered in `.orderspec/config/tooling.json` `skills.bindings` via `tooling_config.py add-binding`.
4. **Approval:** Commands MUST ask the user before installing, registering, or modifying skills.
5. **Matching:** Required skills are matched by `STACK-NNN` from `tooling.json`. The agent looks up the technology from `stack.md` using the `STACK-NNN` ID.
6. **Missing skills:** If a required skill is missing, commands MUST NOT silently continue when the missing skill is required for library-specific work.
7. **Pre-discovery check:** Before running `npx skills find`, the agent MUST check existing global (`~/.agents/skills/`) and local (`.orderspec/skills/`) skills to avoid redundant installations.

## Documentation Source Rules

For each source in `docs_sources` (default: `context7`):

1. If `policy == "required_if_available"` and source is available in runtime (agent can invoke it as MCP tool), commands listed in `commands` MUST consult this source before making library-specific implementation claims.
2. Evidence from each source MUST be recorded in `plan.md` with source attribution.
3. If a required source is unavailable, apply `fallback_when_unavailable` (default: block library-specific claims).
4. If `policy == "optional"` — source may be used, but is not required.
5. If `policy == "disabled"` — source MUST NOT be used.

Availability is determined by the agent runtime tool list. Agents MUST NOT rely on any cache file for availability. If availability cannot be determined deterministically, agents MUST report `unknown`.

## Side Effect Rules

Commands MUST NOT install skills, call network services, or run project commands unless project governance explicitly allows the capability and the command-specific workflow requires it.
