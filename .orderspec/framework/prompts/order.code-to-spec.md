---
orderspec:
  artifact: command_prompt
  command: order.code-to-spec
  phase: specify
description: Reverse-engineer a feature specification from existing code. Requires a capable model. Produces a spec.md fully compatible with the OrderSpec pipeline.
---

## Role

`/order.code-to-spec` reverse-engineers existing code into a feature-level WHAT-contract (`spec.md`).

Unlike `/order.spec` which authors specifications from user requirements, this command scans the existing codebase to extract observable behaviour, interfaces, data models, and validation rules.

`spec.md` produced by this command is structurally identical to one produced by `/order.spec`. Downstream commands (`/order.plan`, `/order.tasks`, `/order.code`) treat it the same way.

## Model Requirement

**This command requires a capable model.**

Code-to-spec extraction involves:

- understanding implicit business logic across multiple files;
- distinguishing WHAT from HOW in imperative code;
- identifying invariants that are enforced but not declared;
- normalising technology-specific patterns into logical contracts;
- reconstructing user journeys from scattered interface usage.

A weak model will produce specifications contaminated with implementation details, miss implicit invariants, and conflate framework conventions with feature contracts.

Use `/order.spec` for forward specification from requirements. Use `/order.code-to-spec` only when reverse-engineering existing systems.

## User Input

```text
$ARGUMENTS
```

The text after `/order.code-to-spec` describes what feature or module to extract. It may contain:

- a feature name or description;
- a directory path or file glob;
- a subsystem name;
- a combination of the above.

If `$ARGUMENTS` is empty, STOP: `No feature description or code path provided`.

## Command Context Bootstrap

Before starting command-specific logic:

1. Resolve command context:

   ```bash
   python3 .orderspec/framework/scripts/command_context.py resolve order.code-to-spec --json
   ```

2. If `ok` is `false` or `missing_required` is non-empty, STOP and report the missing required context.
3. Read every file returned in `to_read`, in returned order.
4. Interpret each file according to its `usage` field:
   - `apply`: apply as procedural command/framework/template rules.
   - `constrain`: enforce as project constraints only.
   - `parse`: parse as structured config or runtime state.
   - `inspect`: inspect as command input/output artifact.
   - `reference`: use only as reference or evidence.
5. Do not manually load additional framework rules, protocols, configuration files, project contracts, templates, or runtime state before the main command logic unless they are returned by `command_context.py`.

Project contracts returned with `usage: "constrain"` constrain this command, but do not override framework rules.

If required project contracts are missing, STOP and tell the user:

> Project contracts not found or incomplete. Run `/order.bootstrap` first to create or repair `constitution.md`, `stack.md`, `architecture.md`, and `conventions.md`.

## Pre-Execution Checks

No operator-defined pre-execution extension phases are supported in the current OrderSpec core.

Complete Command Context Bootstrap before mode detection.

## Script Availability Checks

Before any mutation, verify these framework scripts exist when their step is needed:

| Script | Required for |
|---|---|
| `.orderspec/framework/scripts/feature_spec.py` | create mode feature directory allocation |
| `.orderspec/framework/scripts/active_feature.py` | active feature state reads/writes |
| `.orderspec/framework/scripts/traceability.py` | spec ID projection and mechanical validation |

If a required script is missing, STOP and report the missing script. Do not manually replace script-owned mechanics.

## Scanning Authority

Unlike `/order.spec`, this command has **expanded read authority**.

During scanning and extraction phases, this command MAY:

- read the full project file tree;
- read any source file in the project;
- read configuration files, test files, and documentation;
- read existing `spec.md` files for other features;
- read `package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`, or equivalent dependency manifests;
- read framework configuration files (routing, middleware, database schema).

All reads are for extraction purposes only. No file is mutated except:

- the target `spec.md`;
- traceability artifacts (`spec-ids.tsv`);
- active feature state (`.orderspec/state/active-feature.json`);
- self gate report consumption marker (if applicable).

## Core Contract Boundaries

### Feature namespace

Every feature has a stable feature namespace:

```text
FEAT-NNN-slug
```

Examples:

```text
FEAT-001-user-auth
FEAT-002-task-audit
FEAT-003-billing-invoices
```

Inside one `spec.md`, local IDs are used:

```text
REQ-001
IF-001
AC-001
```

Cross-feature references MUST use fully namespaced IDs:

```text
FEAT-001-user-auth:REQ-003
FEAT-002-task-audit:IF-001
```

### Status separation

| Location | Field | Allowed meaning |
|---|---|---|
| `spec.md` frontmatter | `orderspec.status` | artifact review lifecycle: `draft`, `review`, `approved` |
| `.orderspec/state/active-feature.json` | `status` | runtime pipeline state: `specified`, `planned`, `tasks`, `implementing`, etc. |

After successful `/order.code-to-spec`, active feature state status is `specified`.

## Mode Detection

Determine mode before writing any managed file.

Read-only operations allowed during mode detection:

- command context resolution;
- reading files returned by resolver;
- reading `$ARGUMENTS`;
- running `active_feature.py get --json`;
- running `active_feature.py validate --json`;
- running `active_feature.py list --json`;
- reading an existing `spec.md` only after the target feature is resolved;
- checking whether target files exist;
- **reading project files for scanning purposes** (this is the key difference from `/order.spec`).

### Modes

1. **Create** — no active non-template `spec.md`, or user passed `--new`.
2. **Refine** — active non-template `spec.md` exists and the user wants to re-scan code to update it.

Explicit flags override auto-detection:

| Flag | Mode |
|---|---|
| `--new` | create |

There is no Decompose mode in this command. If the scanned scope is oversized, recommend running `/order.spec --split` on the resulting specification instead.

State the detected mode in one line before proceeding.

### Active feature read-only resolution

Read current state:

```bash
python3 .orderspec/framework/scripts/active_feature.py get --json
```

Validate current state:

```bash
python3 .orderspec/framework/scripts/active_feature.py validate --json
```

If validation fails, STOP and report the script JSON.

If `$ARGUMENTS` contains an explicit feature reference for an existing feature, resolve it with:

```bash
python3 .orderspec/framework/scripts/active_feature.py select <feature-ref> --last-command order.code-to-spec --json
```

### Refine vs create heuristics

Use refine when:

- the active feature is valid and has a non-template `spec.md`;
- the user says "re-scan", "update from code", "sync with code", or similar.

Use create when:

- `--new` is present;
- no active feature exists;
- the active feature has no non-template `spec.md`;
- the request clearly describes a separate code area not covered by the active spec.

If ambiguous, ask one blocking question:

```markdown
## Question 1: Refine or new feature?

**Context**: There is an active spec, but your request does not clearly say whether to update it from code or start a separate reverse-engineering pass.
**What we need to decide**: Should this request refine the active spec from code or create a new spec from a different code area?
**My recommendation**: Option A if the request refers to the same code area; Option B if it refers to a different module.

| Option | Answer | Implications |
|--------|--------|--------------|
| A | Refine active spec | Existing `spec.md` is edited surgically; IDs remain append-only |
| B | Create new feature | A new `FEAT-NNN-slug` namespace and feature directory are allocated |
| Custom | Provide your own | Specify target feature or boundary |

**Reply** with `A`, `B`, or Custom.
```

## Self Gate Report Intake

If a target feature directory exists, check for a self gate report:

```text
<feature-directory>/spec-report.md
```

If absent, proceed with `$ARGUMENTS`.

If present:

- Read it.
- If verdict is PASS, proceed.
- If state is `CONSUMED_STALE`, ignore it as an active verdict and proceed; `/order.spec-check` is required for new PASS evidence.
- If verdict is BLOCK or ROUTING REQUIRED:
  1. Treat findings routed to `/order.code-to-spec` as authoritative defects to resolve.
  2. Do not silently compensate for findings owned by other commands.
  3. List upstream/downstream-owned findings in the completion report.
  4. Treat `$ARGUMENTS` as additional guidance, not a replacement for the report.

If a BLOCK/ROUTING REQUIRED report was used to modify `spec.md`, then after successful write, ID projection, and validation, replace it through the deterministic marker command:

```bash
python3 .orderspec/framework/scripts/traceability.py mark-consumed \
  --report "<feature-directory>/spec-report.md" \
  --consumer /order.code-to-spec \
  --recheck /order.spec-check
```

## Project Contracts and §6

Project contracts are loaded through Command Context Bootstrap with `usage: "constrain"`:

- `constitution.md`
- `stack.md`
- `architecture.md`
- `conventions.md`

Build an internal index of all valid project contract IDs:

- `STACK-NNN`
- `ARCH-NNN`
- `CONV-NNN`

`spec.md` §6 may reference these IDs only with short neutral labels.

Allowed:

```markdown
- `STACK-001` — runtime constraint
- `STACK-003` — persistence constraint
- `ARCH-001` — architecture constraint
- `CONV-001` — error-handling convention
```

Forbidden in `spec.md`:

- technology names;
- library names;
- versions;
- file paths;
- class names;
- plugin names;
- query syntax;
- copied project contract prose.

### Missing project contract ID

During code scanning, the model will encounter technologies, libraries, and framework-specific patterns not yet registered in project contracts.

For each technology not present in project contracts:

1. Do not invent `GOV-NNN`, `STACK-NNN`, `ARCH-NNN`, or `CONV-NNN`.
2. Do not silently amend project contracts.
3. Collect all discovered technologies into a batch.
4. Present the batch to the user:

   ```markdown
   ## Discovered Technologies

   The following technologies were found in the scanned code but are not 
   registered in project contracts:

   | Technology | Role | Evidence |
   |------------|------|----------|
   | stripe | external payment provider | `import stripe` in `payments/service.py` |
   | redis | caching layer | `redis.connect()` in `cache/client.py` |

   To write a clean specification, these need `STACK-NNN` IDs in `stack.md`.

   Confirm to route a targeted `/order.bootstrap` amend for these entries?
   ```

5. On confirmation, invoke `/order.bootstrap` with a narrow amend request for each technology.
6. Use only the returned IDs in §6.
7. If not confirmed, STOP and tell the user to run `/order.bootstrap` manually.

Targeted bootstrap amend is allowed only with explicit user confirmation during this run.

## Scanning Process

### Phase 1: Discovery

1. Read the project file tree. Respect `.gitignore` if present. Skip `node_modules`, `.git`, `__pycache__`, `dist`, `build`, `.orderspec` (except existing specs for reference).
2. From `$ARGUMENTS`, identify the target code area:
   - If a directory path is given, start there.
   - If a feature name is given, search for relevant files by name patterns, route definitions, module names.
   - If ambiguous, identify candidate files and present them to the user for confirmation.
3. Read identified source files.
4. Read related test files, if they exist.
5. Read related documentation (README sections, API docs, inline comments).

### Phase 2: Extraction

Build an internal model of:

- **External interfaces**: HTTP endpoints, CLI commands, event consumers, job handlers.
- **Internal interfaces**: service-to-service calls, module public APIs.
- **Data entities**: database models, DTOs, domain objects, their fields and types.
- **Status codes and error responses**: from route handlers, middleware, exception handlers.
- **Validation rules**: input validation, schema validation, business rule guards.
- **State transitions**: enum values, status fields, transition logic.
- **External dependencies**: imported libraries, external service calls, message queue publishers.
- **Authentication and authorization**: middleware, guards, role checks, ownership checks.
- **Error handling patterns**: try/catch blocks, error response shapes, retry logic.

### Phase 3: Translation

Translate the internal model into OrderSpec logical contract:

| Code concept | spec.md artifact |
|---|---|
| HTTP endpoint | `IF-NNN` with logical Operation name |
| CLI command | `IF-NNN` with Kind: `cli` |
| Event consumer | `IF-NNN` with Kind: `consumer` |
| Request/response schema | `### Structure:` in §8 |
| Database model | `### Entity:` in §8 |
| Enum values | `### Value Set:` in §8 |
| Input validation | `REQ-NNN` (testable, observable) |
| Status codes | `IF-NNN` Success/Failure fields |
| Error responses | `IF-NNN` Failure field |
| State transitions | `EDGE-NNN` or `INV-NNN` (if provable) |
| External library | `STACK-NNN` reference (via bootstrap) |
| Architecture pattern | `ARCH-NNN` reference (via bootstrap) |
| Convention | `CONV-NNN` reference (via bootstrap) |
| Auth middleware | `IF-NNN` Actor field + `REQ-NNN` for authorization |
| User workflow reconstructed from interface usage | `UJ-NNN` |
| Interface behaviour testable scenario | `AC-NNN` |

### Phase 4: Scope Sizing

If any two of these fire, the scanned scope is oversized:

- more than 25–30 plausible REQs extracted;
- more than 3 independent functional domains in the scanned code;
- more than 3 distinct primary actor sets;
- multiple independently releasable modules with separate contracts.

If oversized:

1. Complete the scan but note the sizing finding.
2. In the completion report, recommend running `/order.spec --split` on the resulting specification to decompose it.
3. Do not block completion — the user may still want the full spec.

## Invariant Handling

Reverse-engineered specifications may have fewer invariants than forward-authored ones, because:

- implicit invariants are hard to extract reliably from imperative code;
- race conditions and concurrency guarantees are often undocumented;
- some invariants exist only as test assertions, not as code contracts;
- some invariants are enforced by the framework, not the application code.

### Rules

- Extract `INV-NNN` only when the invariant is **explicitly enforced** in code via:
  - database constraint (unique, not null, foreign key);
  - validation guard with explicit error response;
  - type system enforcement;
  - state machine with explicit transition table.
- If no reliable invariants are found, add to §10:

  ```markdown
  ### Contradiction Grid

  | Pair | Source | Tension | Verdict |
  |------|--------|---------|---------|
  | — | brownfield: no reliably extractable invariants from code | — | n/a |
  ```

- Do NOT invent invariants that "look right" — only document what the code actually enforces.
- If an invariant is suspected but not provable from code, record it as `ASM-NNN` with tag `[inferred]`:

  ```markdown
  - **ASM-003**: [inferred] Payment amounts are likely positive-only
    - **Evidence**: No negative amount found in test fixtures, but no explicit guard in code
  ```

- If some invariants are extracted, include them normally and populate the contradiction grid for those entries only.

## ID Discipline

Applies to every mode that writes `spec.md`.

Every feature-spec ID definition MUST be on a strict anchor line:

```markdown
- **PREFIX-NNN**: Statement text.
```

Allowed prefixes:

```text
REQ, NFR, SC, INV, EDGE, UJ, AC, Q, ASM, DEC, IF
```

Rules:

- Each ID is defined exactly once.
- Mentions elsewhere are references, not definitions.
- Stable IDs are append-only.
- Additions use the next free number within the prefix.
- Never renumber, reuse, or shift existing IDs.
- Editing in place keeps the same ID.
- Removing an item requires a tombstone that remains a strict anchor definition.

Correct tombstone:

```markdown
- **REQ-014**: [removed — superseded by `FEAT-002-task-audit:REQ-003`; retained as tombstone]
```

After every edit, reconcile:

- `Covers:` references;
- AC inline `[Covers: ...]`;
- `EDGE-NNN → covered by AC-NNN`;
- IF table `Covers`;
- cross-feature references;
- diagrams;
- payload/schema references;
- contradiction grid rows.

## Spec Content Requirements

Follow the resolved spec template and these rules.

### YAML frontmatter

`spec.md` MUST start with YAML frontmatter. The template (`spec-template.md`) is the single source of truth for frontmatter structure. Substitute placeholders as follows:

| Placeholder | Value |
|---|---|
| `__FEATURE_SLUG__` | slug from `feature_spec.py` output |
| `__FEATURE_ID__` | feature_id from `feature_spec.py` output |
| `__MODEL_NAME__` | identifier of the AI model currently running this command |

Allowed `orderspec.status`: `draft`, `review`, `approved`.

### Requirements

`REQ-NNN` statements:

- must be testable;
- must use MUST or MUST NOT;
- must describe observable WHAT;
- must not include implementation strategy.

Forbidden in REQ:

- retry strategy;
- transaction mechanism;
- polling;
- last-writer-wins;
- framework/library names;
- file paths;
- class names;
- database/query syntax.

### Non-functional requirements

Do not invent quantitative thresholds.

If a threshold is not found in code or configuration:

- omit the NFR; or
- write a qualitative SHOULD; or
- record as `ASM-NNN` with tag `[inferred]`.

### Architecture & Behaviour

Use logical roles only:

Allowed examples:

- Actor;
- Authentication;
- Authorization;
- Validation;
- Application Service;
- Persistence;
- External System.

Forbidden examples:

- library names;
- framework names;
- class names;
- folder names;
- ORM/plugin names.

Mermaid safety:

- flowchart node labels use quoted form: `A["label"]`;
- sequence diagrams declare participants at top with `participant X`.

### Information model

Use logical entities, structures, and value sets.

No physical implementation details.

Parseable anchors:

```markdown
### Entity: Name
### Structure: Name
### Value Set: Name
```

Entity/structure fields use tables.

### Interface contracts

Every externally observable boundary gets an `IF-NNN` strict anchor and a structured Field/Value table.

Required fields:

| Field | Required |
|---|---|
| Kind | yes |
| Operation | yes |
| Actor | yes |
| Success | yes |
| Failure | yes |
| Covers | yes |

Recommended fields:

| Field | Required |
|---|---|
| Address | recommended |
| Input | recommended |

Authorization rules:

- For create interfaces, authorization is about assignment (e.g., `userId` is set from authenticated user, not from request body).
- For read/mutate interfaces, authorization is about ownership (resource belongs to authenticated user).

Pagination rules:

If a list interface mentions pagination, it MUST either:

- define a Pagination Envelope in §9 Shared Structures; or
- reference a `CONV-NNN` that defines pagination.

### Edge cases

`EDGE-NNN` covers boundary conditions, failures, races, unusual inputs, and state conflicts.

If an edge is fully covered by an AC:

```markdown
- **EDGE-001**: Duplicate request → covered by AC-004
```

For reverse-engineered specs, prioritise edges that are:

- explicitly handled in code (try/catch, guard clauses);
- covered by test cases;
- mentioned in error response schemas.

### User journeys and acceptance criteria

`UJ-NNN` is an independently implementable and testable slice.

Rules:

- order UJs by priority;
- P1 journeys form the smallest coherent MVP; declare dependencies when more
  than one P1 journey is required;
- every UJ has Covers, priority rationale, independent test, and Done when;
- every AC has inline `[Covers: ...]`;
- every REQ is covered by at least one UJ/AC;
- every IF is covered by at least one AC unless explicitly documented as non-user-testable with a reason.

For reverse-engineered specs, UJs are reconstructed from:

- interface call sequences in tests;
- documented workflows;
- inferred user goals from interface operations.

### Decisions vs assumptions

Use `DEC-NNN` when the extracted code reveals a decision that affects:

- IF response;
- IF status code;
- IF failure mode;
- INV wording;
- INV guarantee.

Use `ASM-NNN` for:

- defaults that do not affect IF or INV wording;
- inferred behaviour not provable from code;
- framework conventions assumed but not visible in application code.

Tags:

```text
[default]
[narrowing REQ-NNN]
[deferred]
[inferred]
```

### Open questions

`Q-NNN` is allowed for non-blocking unresolved references or intentionally deferred issues.

For reverse-engineered specs, use `Q-NNN` when:

- code behaviour is ambiguous and cannot be resolved by reading tests;
- a code path exists but its trigger condition is unclear;
- an interface is defined but no implementation found.

## Clarification Protocol

`/order.code-to-spec` is not fully autonomous on consequential decisions.

When the code reveals a genuine fork that materially changes scope, architecture, security, privacy, authorization, acceptance, interface behaviour, invariant guarantees, data retention, or failure semantics, STOP and ask the user.

Ask at most 3 questions per round, prioritized:

1. scope;
2. security/privacy/authorization;
3. data consistency/failure semantics;
4. acceptance/testability;
5. UX;
6. technical defaults.

Use the same question format as `/order.spec`.

## Create Mode

### Create flow

1. Parse `$ARGUMENTS` to identify the target code area.
2. Perform full scanning process (Phase 1–3).
3. Perform scope sizing.
4. Generate a short slug from the feature description.
   - Slug is lowercase kebab-case, 2–4 words when practical.
5. Allocate the feature directory:

   ```bash
   python3 .orderspec/framework/scripts/feature_spec.py create --slug "<slug>" --json
   ```

6. Load the resolved spec template from command context.
7. Perform technology discovery and routing (see "Project Contracts and §6").
8. Author the full `spec.md` content.
9. Write `spec.md` in one complete mutation.
10. Run traceability projection and validation.
11. Update active feature state with `active_feature.py set`.

## Refine Mode

Refine mode re-scans code and surgically edits an existing `spec.md` to align it with the current codebase.

Rules:

1. Load the existing `spec.md`.
2. Do not copy the template over it.
3. Preserve `orderspec.feature_id` and `orderspec.slug`.
4. Preserve stable IDs.
5. Re-scan the relevant code area.
6. Classify edits:
   - Add → assign next-free ID in the correct prefix.
   - Change → edit in place under same ID and reconcile dependents.
   - Remove → tombstone with strict anchor.
   - Resolve Q → promote to DEC if it affects IF/INV; otherwise ASM.
7. Update YAML frontmatter only if artifact lifecycle status changes.
8. Update affected diagrams, IF records, INV, EDGE, UJ, AC, DEC, ASM, and coverage links.
9. Maintain the contradiction grid for touched INV/NFR/ASM/REQ pairs.
10. Append a changelog row in `## 16. Changelog`.

### Changelog row format

| Date | Type | Change | IDs affected | Contract impact | Reason |
|------|------|--------|--------------|-----------------|--------|

Type must be one of:

```text
Added, Changed, Removed, Strengthened, Weakened, Moved, Split, Merged, Clarified, Renamed
```

## Mechanical Validation

After writing or refining `spec.md`, run these commands in order:

```bash
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" init
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" extract-spec-ids
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" validate --stage spec --json
```

Rules:

- `init` is idempotent.
- `extract-spec-ids` is the only writer of `spec-ids.tsv`.
- Never hand-write or hand-read `spec-ids.tsv`.
- If any script exits non-zero, STOP the mutation flow and report/fix according to ownership.
- If validation findings are owned by this command and self-fixable without changing meaning, fix and rerun.
- Maximum 3 self-fix iterations.
- If still failing, report residual findings and recommend `/order.spec-check`.

### Active feature state update

After successful write, ID extraction, and mechanical validation, update active feature state:

```bash
python3 .orderspec/framework/scripts/active_feature.py set \
  --feature-id "$FEATURE_ID" \
  --feature-directory "$FEATURE_DIR" \
  --status specified \
  --last-command order.code-to-spec \
  --json
```

## Semantic Self-Validation

Before completion, reason through these checks:

- No file paths, library names, class names, plugin names, framework-specific query syntax, or technology versions appear in `spec.md`.
- IF `Failure` field must not contain template residue.
- §6 references only valid `GOV-NNN`, `STACK-NNN`, `ARCH-NNN`, `CONV-NNN` IDs with neutral labels.
- Every REQ has acceptance coverage.
- Every AC has inline `[Covers: ...]`.
- IF `Covers` references defined IDs.
- IF success/failure outcomes match related ACs.
- Authorization is specified for mutating interfaces and cross-owner reads.
- Contradiction grid is present (may be empty with brownfield marker).
- DEC/ASM separation is correct.
- Tombstoned IDs remain strict anchors.
- Cross-feature refs use `FEAT-NNN-slug:LOCAL-NNN`.
- No placeholder values remain in frontmatter or normative sections.

## Downstream Impact

For refine mode only:

- If `plan.md` exists, warn:

  > `spec.md` changed — `plan.md` may be stale. Run `/order.plan` later to re-align.

- If `tasks.md` exists, warn:

  > `tasks.md` may also be stale. Re-derive via `/order.tasks` after the plan is aligned.

This command does not modify `plan.md` or `tasks.md`.

## Completion Report

Report to chat. Do not create a checklist file.

### Create report

Include:

- mode;
- `feature_id`;
- `slug`;
- `feature_directory`;
- `spec_file`;
- command context status;
- project contracts loaded;
- files scanned (count, not full list);
- technologies discovered and routed to bootstrap;
- traceability init result;
- ID extraction result;
- mechanical validation result;
- active feature update result;
- ID counts by prefix;
- §6 project constraint IDs referenced;
- contradiction-grid result (populated or brownfield marker);
- invariant extraction summary (how many INV, how many deferred to ASM as `[inferred]`);
- coverage gaps (interfaces with no AC, REQs with no UJ) if any;
- bootstrap routing, if any;
- scope sizing finding (if oversized);
- readiness for `/order.plan`;
- manual/orchestrator recommendation to run `/order.spec-check`;
- recommendation to manually review extracted specs for missed invariants.

### Refine report

Include:

- mode;
- `spec_file`;
- changelog row;
- files re-scanned (count);
- technologies discovered and routed to bootstrap (if any);
- changed IDs;
- traceability result;
- mechanical validation result;
- active feature update result;
- invariant extraction summary;
- downstream impact warnings;
- bootstrap routing, if any;
- manual/orchestrator recommendation to run `/order.spec-check`.

## Done When

- [ ] Command context resolved via `command_context.py`
- [ ] Every `to_read` file was read and interpreted by `usage`
- [ ] Mode detected and stated
- [ ] Full code scan completed for the target area
- [ ] Technology discovery completed (all external deps cross-referenced with project contracts)
- [ ] Missing project contract needs were routed to `/order.bootstrap` only with explicit confirmation
- [ ] Create mode allocated feature directory via `feature_spec.py`
- [ ] Existing non-template spec was never overwritten by a template
- [ ] Feature namespace uses `FEAT-NNN-slug`
- [ ] `spec.md` frontmatter contains `orderspec.artifact`, `feature_id`, `slug`, and valid `status`
- [ ] Project contracts constrained generation
- [ ] §6 contains only valid project contract IDs with neutral labels
- [ ] No technology names, library names, class names, file paths, or framework syntax in normative sections
- [ ] Stable IDs use strict anchor lines
- [ ] Removed IDs are tombstoned as strict anchors
- [ ] Cross-feature refs use `FEAT-NNN-slug:LOCAL-NNN`
- [ ] IF/REQ/UJ/AC coverage links reconciled
- [ ] DEC and ASM separated correctly
- [ ] Contradiction grid present (populated or brownfield marker)
- [ ] Invariants extracted only where explicitly enforced in code
- [ ] `traceability.py init` succeeded
- [ ] `traceability.py extract-spec-ids` succeeded
- [ ] `traceability.py validate --stage spec --json` succeeded or residual findings were reported
- [ ] Active feature state updated via `active_feature.py set`
- [ ] Refine downstream impact reported
- [ ] Completion report emitted to chat
