---
orderspec:
  artifact: framework_rules
  authority: framework
  customization: forbidden
---

# OrderSpec Identifiers Glossary

This document defines the stable identifier prefixes used in `spec.md` and `plan.md`.
Agents MUST use these prefixes when creating artifacts. Scripts validate their presence and format via `traceability.yml`.

## Feature Spec Identifiers (used in `spec.md`)

| Prefix | Full Name | Description |
|--------|-----------|-------------|
| `REQ` | Requirement | Core functional requirement. Describes observable WHAT the system must do. Must be testable. |
| `NFR` | Non-Functional Requirement | Quality attributes (performance, security, reliability, etc.). |
| `SC` | Scenario | Specific sequence of events or user interaction flow. |
| `INV` | Invariant | Absolute conditions that MUST hold at all times (e.g., state rules, data constraints). |
| `EDGE` | Edge Case | Boundary conditions, failures, races, unusual inputs, and state conflicts. |
| `UJ` | User Journey | An independently implementable and testable slice of user flow. Ordered by priority. |
| `AC` | Acceptance Criteria | Testable conditions (Given/When/Then) that must be met to consider a requirement done. |
| `Q` | Question | Open question requiring resolution before or during implementation. Blocking questions must be resolved before `plan.md`. |
| `ASM` | Assumption | A hypothesis taken as true without full evidence, or a default that does not affect IF or INV wording. |
| `DEC` | Decision | A recorded architectural or implementation choice that affects IF response, status code, or INV wording. |
| `IF` | Interface | Externally observable boundary or API contract (endpoint, operation, payload). |

## Information Model Context Identifiers (used in `spec.md`)

These IDs address normative Information Model blocks for bounded worker context.
They are valid in task-context `contract_refs`, but they are not behavioural
traceability coverage and never require mechanism rows.

| Prefix | Full Name | Heading form | Description |
|--------|-----------|--------------|-------------|
| `ENT` | Entity | `### Entity ENT-NNN: Name` | Logical entity and its field contract. |
| `STR` | Structure | `### Structure STR-NNN: Name` | Logical nested, request, response, or snapshot structure. |
| `VAL` | Value Set | `### Value Set VAL-NNN: Name` | Closed logical value set and value meanings. |

Information Model IDs are append-only. Refinement preserves an existing ID when
its logical subject retains identity; removed subjects retain a tombstone note
instead of reusing their number. `ENT`, `STR`, and `VAL` references MUST NOT
appear in task-line coverage fields.

## Project Contract Identifiers

| Prefix | Full Name | Description |
|--------|-----------|-------------|
| `GOV` | Governance | Project-wide hard governance rule defined in `constitution.md`. |
| `STACK` | Stack | A specific technology, library, runtime, or tool. |
| `ARCH` | Architecture | Architectural pattern, component, or structural constraint. |
| `CONV` | Convention | Coding standard, naming rule, methodology, or development practice. |
