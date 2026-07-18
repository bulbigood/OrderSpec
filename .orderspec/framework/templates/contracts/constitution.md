---
orderspec:
  artifact: project_contract
  kind: constitution
  scope: project
  owner_command: order.bootstrap
  id_prefix: GOV
---

# {project_name} Constitution

Highest-authority project governance below framework rules. Mission and values are context; only `GOV-NNN` rules and capability grants are normative.

## Project Intent (Non-Normative)

### Mission

{mission}

### Values

{values}

## Governance Rules

| ID | Rule | Rationale | Source |
|----|------|-----------|--------|
{governance_rows}

## Capability Grants

Unstated capabilities are denied.

### Test execution
{test}

### Build / compile / lint as evidence
{lint}

### Network access during a gate
{network}

### Skill discovery
DENIED unless current chat contains explicit approval for exact discovery action.

### Skill installation or registration
DENIED unless current chat contains explicit approval for exact skill name, source, and project-local destination.

### Documentation lookup during authoring
ALLOWED for read-only lookup required by resolved tooling policy. This does not allow package or skill installation, project command execution, arbitrary network access, or gate-time access.

### Environment diagnosis during authoring
ALLOWED for read-only readiness checks declared by current workflow.

### Environment recovery during authoring
ALLOWED only after explicit current-chat approval for exact bounded action and environment.

### Package installation, data reset, and production/shared-environment changes
DENIED.

### MCP documentation lookup during gates
DENIED unless explicitly allowed above.

## External Rules Integration

Policy: `{external_rules_policy}`

Allowed values: `constrain_on_bootstrap`, `ignore`.

## Governance

- Framework rules always win on conflict.
- Amendments are made only through `/order.bootstrap`.
- Changed project-contract IDs retain identity or become tombstones.

**Last Amended**: {date}
