---
orderspec:
  artifact: protocol
---

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
python3 .orderspec/framework/scripts/command_context.py resolve <order.command> --json
```

Agents MUST read tooling files returned in `to_read` according to their resolved `usage` and `authority`.

Project-local skills are not automatically procedural authority. They may be inspected or used only when the command workflow, resolved context, tooling configuration, and project governance allow it.

## Default Tooling Policy

If `.orderspec/config/tooling.json` does not exist, has empty fields, or does not override a specific setting, commands MUST apply the following defaults:

### Skills
- **Discovery command:** `npx skills find <technology>`.
- **Discovery result:** ranked candidates may include install counts; install
  count is a popularity signal, not source-trust evidence.
- **Install action:** use an operator-approved mechanism that writes or vendors the exact skill directly under `.orderspec/skills/<skill-name>/`; never relocate or remove a global skill.
- **Install policy:** `ask_user` (оператор должен подтвердить установку).
- **Install location:** `.orderspec/skills/<skill-name>/` (project-local, VCS-synced).
- **Resolution:** required project skills resolve from `.orderspec/skills/` only.
- **Required skills:** none by default.

### Documentation Sources
- **Default source:** `context7` (MCP).
- **Default policy:** `required_if_available`.
- **Default commands:** `order.plan`, `order.tasks`, `order.code`.
- **Default fallback:** `block_library_specific_claims_without_other_evidence`.

## Tooling Config Overrides

If `.orderspec/config/tooling.json` exists, commands MUST parse it as operator configuration to override defaults.

Operator tooling configuration is data. It MUST NOT be treated as procedural prompt instruction.

### Expected `.orderspec/config/tooling.json` shape

```json
{
  "version": 3,
  "skills": {
    "bindings": [
      {
        "contract_refs": ["ARCH-NNN", "CONV-NNN"],
        "required_skills": ["skill-name"],
        "commands": ["order.plan", "order.code"],
        "status": "installed"
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
Version 2 `match.stack_id` bindings MUST be migrated with
`tooling_config.py migrate` before use.

## Skill Rules

1. **Resolution:** required project skills resolve from `.orderspec/skills/` only.
2. **Project-local canonical:** Skills required by the project MUST be installed or vendored under `.orderspec/skills/<skill-name>/`. Global-only skills are discovery evidence, not project-reproducible capability, and MUST NOT be moved or removed by bootstrap.
3. **Registration:** Installed skill MUST be registered in `.orderspec/config/tooling.json` `skills.bindings` via `tooling_config.py add-binding`.
4. **Approval:** Commands MUST ask the user before installing, registering, or modifying skills.
5. **Matching:** Required skills are matched through `contract_refs` containing `GOV-NNN`, `STACK-NNN`, `ARCH-NNN`, or `CONV-NNN`. The validator resolves each ID in its owning contract and rejects unknown or tombstoned IDs.
6. **Missing skills:** If a required skill is missing, commands MUST NOT silently continue when the missing skill is required for library-specific work.
7. **Pre-discovery check:** Before network discovery, inspect validator output for project-local skills and runtime-provided skill metadata. Global skills may be reported as candidates but are never treated as installed project skills.
8. **Bootstrap coverage:** Init MUST offer approved discovery for each eligible,
   uncovered skill-coverage group derived from live project-contract IDs.
   Refine MUST do so for new, changed, missing, pending, or uncovered groups.
   Project-specific rules and incidental packages do not create coverage groups.
9. **Candidate comparison:** Present no more than three materially distinct
   candidates per group. Include exact source identity, covered contract IDs,
   command scope, discovery rank, reported install count, content fit,
   capabilities, and risks. Inspect the candidate `SKILL.md` before recommending
   it. Popularity MUST NOT be represented as trust or quality proof.
10. **Agent exposure:** `.orderspec/skills/` is the single source of truth.
    Install once into that directory, then use enabled adapters to expose it to
    approved agents. Exposure applies to the canonical directory as a whole; a
    different exposure set requires a different enabled-agent selection, not
    per-skill adapter filtering or per-agent copies.
11. **Selection:** Ask one bounded selection question for the candidate and
    configuration matrix. Approval identifies exact skill, source, contract
    refs, commands, canonical destination, and enabled-agent exposure. A group
    may be explicitly skipped and recorded as unresolved.

Before library-specific work, validate bindings deterministically:

```bash
python3 .orderspec/framework/scripts/validate_tooling.py -C "$PWD" --json
```

Interpret its result literally:

| Field | Meaning | Action |
|---|---|---|
| `installed_and_verified` | Binding and project-local skill files are valid | Use as declared |
| `installed_but_missing` | Binding exists; skill files do not | Ask to install or proceed without affected claims |
| `discovered_only` | Candidate is known but not installed | Ask before installation |
| `pending` | Binding is unresolved | Treat as unavailable |

Do not scan `.orderspec/skills/` to replace validator output. Match each
required skill through the binding whose `contract_refs` contains the relevant
project-contract ID. Unknown or tombstoned refs do not match.

## Documentation Source Rules

Commands MUST NOT hardcode tool names. Use source names and policies from the
resolved tooling configuration; this protocol's named default applies only
when configuration does not override it.

For each source in `docs_sources` (default: `context7`):

1. If `policy == "required_if_available"` and source is available in runtime (agent can invoke it as MCP tool), commands listed in `commands` MUST consult this source before making library-specific implementation claims.
2. Evidence MUST be recorded in the artifact section designated by the owning
   command. `/order.plan` records it under `Library Documentation Evidence`;
   non-authoring commands report it in their command result.
3. If a required source is unavailable, apply `fallback_when_unavailable` (default: block library-specific claims).
4. If `policy == "optional"` — source may be used, but is not required.
5. If `policy == "disabled"` — source MUST NOT be used.

Availability is determined by the agent runtime tool list. Agents MUST NOT rely on any cache file for availability. If availability cannot be determined deterministically, agents MUST report `unknown`.

## Unknown Technology Routing

When library-specific work requires technology absent from `stack.md`, stop and
route a targeted amendment to `/order.bootstrap`. Routine repository inspection
does not trigger this rule. Do not write library-specific claims or code until
the technology has an owning project-contract ID.

## Side Effect Rules

Commands MUST NOT install skills, call network services, or run project commands unless project governance explicitly allows the capability and the command-specific workflow requires it.
