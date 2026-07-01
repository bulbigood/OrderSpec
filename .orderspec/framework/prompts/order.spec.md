---
orderspec:
  artifact: command_prompt
  command: order.spec
  prompt_version: "0.3.0"
  phase: specify
description: Create or update the feature specification — the stable WHAT-contract with logical architecture. Owns spec.md contract content.
handoffs:
  - label: Build Technical Plan
    agent: order.plan
    prompt: Create a plan for this specification.
---

## Role

`/order.spec` creates or refines `spec.md`: the stable feature-level WHAT-contract.

`spec.md` defines:

- observable behaviour;
- logical architecture;
- requirements;
- interface contracts;
- information model;
- invariants;
- edge cases;
- user journeys;
- acceptance criteria;
- assumptions and decisions.

`spec.md` does **not** define:

- physical code structure;
- implementation tasks;
- file paths;
- class names;
- framework/library-specific implementation details;
- task ordering.

Those belong to downstream artifacts owned by other commands.

`/order.spec` is the sole owner of feature contract content. Gates may detect and route defects, but meaning, scope, requirements, acceptance criteria, interface behaviour, and invariants are authored here.

## User Input

```text
$ARGUMENTS
```

Consider the user input before proceeding if non-empty. The text after `/order.spec` is the request. Do not ask the user to repeat it unless it is empty and create mode cannot proceed.

## Command Context Bootstrap

Before starting command-specific logic:

1. Resolve command context:

   ```bash
   python3 .orderspec/scripts/command_context.py resolve order.spec --json
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
| `.orderspec/scripts/feature_spec.py` | create mode feature directory allocation |
| `.orderspec/scripts/active_feature.py` | active feature state reads/writes |
| `.orderspec/scripts/traceability.py` | spec ID projection and mechanical validation |

If a required script is missing, STOP and report the missing script. Do not manually replace script-owned mechanics.

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

`feature_id` is the stable cross-spec namespace. `slug` is the short human-readable kebab-case name. Feature directory names are filesystem allocation details.

### Status separation

Do not confuse lifecycle states:

| Location | Field | Allowed meaning |
|---|---|---|
| `spec.md` frontmatter | `orderspec.status` | artifact review lifecycle: `draft`, `review`, `approved` |
| `.orderspec/state/active-feature.json` | `status` | runtime pipeline state: `specified`, `planned`, `tasks`, `implementing`, etc. |

After successful `/order.spec`, active feature state status is `specified`.

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
- checking whether target files exist.

Do not create directories, copy templates, write `spec.md`, update active feature state, or run traceability writers during mode detection.

### Modes

1. **Create** — no active non-template `spec.md`, or user passed `--new`.
2. **Refine** — active non-template `spec.md` exists and the request changes, adds, removes, narrows, broadens, or clarifies its contract.
3. **Decompose** — user passed `--split`, or the requested scope is oversized.

Explicit flags override auto-detection:

| Flag | Mode |
|---|---|
| `--new` | create |
| `--split` | decompose |

State the detected mode in one line before proceeding.

### Active feature read-only resolution

Read current state:

```bash
python3 .orderspec/scripts/active_feature.py get --json
```

Validate current state:

```bash
python3 .orderspec/scripts/active_feature.py validate --json
```

If validation fails, STOP and report the script JSON. Do not hand-repair `.orderspec/state/active-feature.json`.

If `$ARGUMENTS` contains an explicit feature reference for an existing feature, resolve it with:

```bash
python3 .orderspec/scripts/active_feature.py select <feature-ref> --last-command order.spec --json
```

Use `select` only when the command is committed to operating on that existing feature. Never silently choose among ambiguous matches.

### Refine vs create heuristics

Use refine when:

- the active feature is valid and has a non-template `spec.md`;
- the request references existing local IDs such as `REQ-007`, `IF-002`, `AC-004`;
- the request says change, add, clarify, remove, split, weaken, strengthen, or update the active spec.

Use create when:

- `--new` is present;
- no active feature exists;
- the active feature has no non-template `spec.md`;
- the request clearly describes a separate deliverable with its own scope and acceptance criteria.

If ambiguous, ask one blocking question:

```markdown
## Question 1: Refine or new feature?

**Context**: There is an active spec, but your request does not clearly say whether to update it or start a separate feature.
**What we need to decide**: Should this request refine the active spec or create a new spec?
**My recommendation**: Option A if this is part of the current feature; Option B if it should ship independently.

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
<feature-directory>/checklists/spec-report.md
```

If absent, proceed with `$ARGUMENTS`.

If present:

- Read it.
- If verdict is PASS, proceed.
- If verdict is BLOCK or ROUTING REQUIRED:
  1. Treat findings routed to `/order.spec` as authoritative defects to resolve.
  2. Do not silently compensate for findings owned by other commands.
  3. List upstream/downstream-owned findings in the completion report.
  4. Treat `$ARGUMENTS` as additional guidance, not a replacement for the report.

If a BLOCK/ROUTING REQUIRED report was used to modify `spec.md`, then after successful write, ID projection, and validation, replace the old report with a `CONSUMED_STALE` marker that states:

- the previous report was consumed by `/order.spec`;
- it is no longer an active verdict;
- this is not PASS;
- `/order.spec-check` is required for a fresh verdict.

Do not add a changelog row merely for report consumption. Changelog records actual contract changes only.

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

Downstream commands read project contract documents to resolve the meaning of IDs.

### Missing project contract ID

If the feature requires a technology, architecture rule, or convention that is not present in project contracts:

1. Do not invent `STACK-NNN`, `ARCH-NNN`, or `CONV-NNN`.
2. Do not silently amend project contracts.
3. Ask for explicit confirmation to route a targeted `/order.bootstrap` amend.
4. If confirmed, invoke bootstrap as the owning command/subagent with a narrow request.
5. Use only the returned ID.
6. If not confirmed, STOP and tell the user to run `/order.bootstrap`.

Targeted bootstrap amend is allowed only with explicit user confirmation during this run.

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

Incorrect tombstone:

```markdown
REQ-014 removed — superseded by ...
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

## Clarification Protocol

`/order.spec` is not fully autonomous on consequential decisions.

When the request leaves a genuine fork that materially changes scope, architecture, security, privacy, authorization, acceptance, interface behaviour, invariant guarantees, data retention, or failure semantics, STOP and ask the user.

Ask at most 3 questions per round, prioritized:

1. scope;
2. security/privacy/authorization;
3. data consistency/failure semantics;
4. acceptance/testability;
5. UX;
6. technical defaults.

### Fork awareness areas

Ask if unresolved, relevant to the feature, and there are at least two defensible options with no safe default:

- authorization and tenant/ownership scope;
- audit/write consistency;
- multi-entity write semantics: atomic, best-effort, compensating;
- soft-delete visibility;
- snapshot/diff semantics;
- idempotency;
- concurrent update resolution;
- retention/cleanup;
- externally observable status codes or failure modes;
- security/privacy-sensitive data exposure;
- acceptance thresholds that cannot be inferred from user input or project governance.

### When not to ask

Low-impact naming, formatting, and obvious conventional defaults may be recorded as `ASM-NNN` only if they do not alter IF/INV semantics or externally observable behaviour.

### Question format

```markdown
## Question [N]: [Topic]

**Context**: [Quote relevant request/spec text or conflicting IDs]
**What we need to decide**: [Specific question]
**My recommendation**: Option [X] — [one-line reason]

| Option | Answer | Implications |
|--------|--------|--------------|
| A | [Answer] | [Consequence] |
| B | [Answer] | [Consequence] |
| Custom | Provide your own | [How] |

**Reply** with a choice per question, e.g. `Q1: B`, or write `yes` to accept my recommendation for every open question.
```

Wait for the reply. On `yes`, apply every recommendation. Then:

- replace any blocking `[NEEDS CLARIFICATION]` marker;
- record the result as `DEC-NNN` if it affects IF or INV;
- otherwise record it as `ASM-NNN`;
- reflect it in the normative section;
- re-run relevant validation.

## Create Mode

Create mode writes a new feature spec.

### Create mode no-write rule

Do not create directories, write `spec.md`, update active feature state, or initialize traceability until:

1. command context has been resolved and read;
2. mode has been detected;
3. the user request has been parsed;
4. scope sizing has completed;
5. decomposition has been ruled out or the user selected one module;
6. blocking clarification questions have been answered.

### Create flow

1. Parse the request.
   - If the request is empty, STOP: `No feature description provided`.
2. Generate a short slug from the feature description.
   - Slug is lowercase kebab-case, 2–4 words when practical.
   - Example: `user-auth`, `task-audit`, `invoice-export`.
3. Perform scope sizing before any write.
4. If oversized, switch to Decompose Mode.
5. Allocate the feature directory using the deterministic script:

   ```bash
   python3 .orderspec/scripts/feature_spec.py create --slug "<slug-or-title>" --json
   ```

   The script returns:
   - `feature_id`, e.g. `FEAT-001-user-auth`;
   - `slug`, e.g. `user-auth`;
   - `feature_directory`, e.g. `specs/001-user-auth`;
   - `spec_file`, e.g. `specs/001-user-auth/spec.md`.

   If the script exits non-zero, STOP and report the script JSON.

6. Load the resolved spec template from command context.
7. **Pre-Write Validation Checklist**: Before drafting content, verify these invariants to ensure mechanical validation passes on the first try:
   - Every `REQ-NNN` MUST be listed in the `Covers` field of at least one `UJ-NNN`.
   - Every `INV-NNN` containing absolute words (`MUST`, `exactly`, `always`, `never`) MUST have a corresponding row in the `Contradiction Grid` (§10).
   - Every HTTP status code mentioned in an `AC-NNN` (e.g., "returns 200") MUST explicitly appear in the `Success` or `Failure` field of the corresponding `IF-NNN` record in §9.
   - Only use `STACK-NNN`, `ARCH-NNN`, `CONV-NNN` IDs that exist in the loaded project contracts.
8. Author the full `spec.md` content.
9. Write `spec.md` in one complete mutation. Do not leave placeholder partial specs.
9. Run traceability projection and validation.
10. Update active feature state with `active_feature.py set`.

### Scope sizing gate

If any two of these heuristics fire, treat the request as oversized and switch to Decompose Mode:

- roughly more than 25–30 plausible REQs;
- more than 3 independent functional domains;
- more than 3 distinct primary actor sets;
- more than 2 viable P1 MVP slices that are not one end-to-end thread;
- multiple independently releasable modules with separate contracts.

## Refine Mode

Refine mode surgically edits an existing `spec.md`.

Rules:

1. Load the existing `spec.md`.
2. Do not copy the template over it.
3. Preserve `orderspec.feature_id` and `orderspec.slug`.
4. Preserve stable IDs.
5. Classify edits:
   - Add → assign next-free ID in the correct prefix.
   - Change → edit in place under same ID and reconcile dependents.
   - Remove → tombstone with strict anchor.
   - Resolve Q → promote to DEC if it affects IF/INV; otherwise ASM.
6. Update YAML frontmatter only if artifact lifecycle status changes.
7. Update affected diagrams, IF records, INV, EDGE, UJ, AC, DEC, ASM, and coverage links.
8. Maintain the contradiction grid for touched INV/NFR/ASM/REQ pairs.
9. Append a changelog row in `## 16. Changelog`.

### Changelog row format

| Date | Type | Change | IDs affected | Contract impact | Reason |
|------|------|--------|--------------|-----------------|--------|

Type must be one of:

```text
Added, Changed, Removed, Strengthened, Weakened, Moved, Split, Merged, Clarified, Renamed
```

Use only the changelog types listed above.

### Contract Change Summary

For Refine Mode, prepare a concise semantic change summary for the completion report.

This summary is derived from the edits made in this run, not from git history and not from a separate diff script.

Include:

- classification: clarification, behaviour change, interface change, invariant change, NFR change, security/privacy change, scope change, or coverage-only change;
- added IDs;
- changed IDs;
- tombstoned IDs;
- strengthened contract points;
- weakened contract points;
- affected IF/INV/AC records;
- downstream stale artifacts;
- whether user approval or clarification was required.

Do not store this summary in `spec.md`. The persistent history remains `## 16. Changelog`.

## Decompose Mode

Triggered by `--split`, oversized create/refine scope, or a clearly too-broad request.

Decompose mode writes at most one new spec, and only after the user chooses the target module.

### Decompose flow

1. Do not create or overwrite any spec yet.
2. Produce a decomposition plan to chat:
   - natural module boundaries;
   - proposed `FEAT-NNN-slug`-style names without allocating numbers yet;
   - 1–2 line scope;
   - actors;
   - dependencies;
   - recommended first module.
3. Provide ready-to-run prompts:

   ```text
   /order.spec --new "<focused description of this module, with boundaries and dependencies>"
   ```

4. Ask the user to choose one module to build now.
5. After the user chooses:
   - run Create Mode scoped to that one module;
   - if splitting an existing parent spec, refine the parent by tombstoning moved IDs and referencing the new feature namespace.
6. Report created module and remaining prompts.

## Spec Content Requirements

When authoring or refining `spec.md`, follow the resolved template and these rules.

### YAML frontmatter

`spec.md` MUST start with YAML frontmatter:

```yaml
---
orderspec:
  artifact: spec
  slug: "<slug>"
  feature_id: "FEAT-NNN-slug"
  status: draft
  refs:
    framework_rules: ".orderspec/framework/orderspec-rules.md"
    constitution: "constitution.md"
    stack: "stack.md"
    architecture: "architecture.md"
    conventions: "conventions.md"
  generator:
    command: order.spec
    prompt_version: "<prompt version>"
    model: "<current AI model name>"
    model_tier: "<model tier>"
---
```

> **Note on metadata**: `prompt_version` MUST be the exact version from the `order.spec.md` frontmatter. `model` MUST be the identifier of the AI model currently running this command (e.g., `kilo/moe-medium`, `claude-3.5-sonnet`).

Allowed `orderspec.status`:

```text
draft, review, approved
```

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

If a threshold is not supplied by user input, constitution, or project contracts:

- omit the NFR; or
- write a qualitative SHOULD; or
- ask through Clarification Protocol if critical.

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

`§9 Interface Contracts` is the single normative source for status codes and response shapes.

Repeated structures are defined only when used. Do not emit a Pagination Envelope unless this feature actually has list interfaces that require pagination by user/project contract.

### Invariants

`INV-NNN` are absolute conditions that must hold at all times.

Do not put operational exceptions in invariants. Use REQ/DEC/ASM for exceptions.

If multiple fields encode the same logical state, add an invariant defining their relationship.

### Contradiction grid

`§10` MUST include a contradiction grid.

Include rows for:

- INV × NFR where INV is absolute and NFR weakens or qualifies behaviour;
- INV × ASM where ASM weakens or qualifies behaviour;
- REQ × ASM where ASM narrows a REQ.

If no pairs exist, state:

```text
No absolute INV × weakening NFR/ASM pairs.
```

Any conflict must be resolved before completion or routed through Clarification Protocol.

### Edge cases

`EDGE-NNN` covers boundary conditions, failures, races, unusual inputs, and state conflicts.

If an edge is fully covered by an AC:

```markdown
- **EDGE-001**: Duplicate request → covered by AC-004
```

Verify the AC actually covers it.

### User journeys and acceptance criteria

`UJ-NNN` is an independently implementable and testable slice.

Rules:

- order UJs by priority;
- at most 2 UJs may be P1;
- every UJ has Covers, priority rationale, independent test, and Done when;
- every AC has inline `[Covers: ...]`;
- every REQ is covered by at least one UJ/AC;
- every IF is covered by at least one AC unless it is explicitly documented as non-user-testable with a reason.

### Decisions vs assumptions

Use `DEC-NNN` when the resolved decision affects:

- IF response;
- IF status code;
- IF failure mode;
- INV wording;
- INV guarantee.

Each DEC must include:

```markdown
- **DEC-001**: Decision statement.
  - **Affects**: `IF-001` (...), `INV-001` (...)
  - **Rationale**: ...
```

Use `ASM-NNN` only for defaults that do not affect IF or INV wording.

Tags:

```text
[default]
[narrowing REQ-NNN]
[deferred]
```

If in doubt, promote to DEC.

### Open questions

Blocking questions must be resolved before `spec.md` is ready for `/order.plan`.

`Q-NNN` is allowed only for non-blocking unresolved references or intentionally deferred issues that do not affect:

- scope;
- security/privacy;
- acceptance;
- IF;
- INV;
- REQ;
- NFR;
- testability.

## Mechanical Validation

After writing or refining `spec.md`, run these commands in order:

```bash
python3 .orderspec/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" init
python3 .orderspec/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" extract-spec-ids
python3 .orderspec/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" validate --stage spec --json
```

> **Note on symlinks**: The `-C "$PWD"` flag is critical if your `.orderspec` directory is symlinked from another repository. It forces the script to use the current working directory as the project root instead of resolving the symlink to the framework source.


Rules:

- `init` is idempotent.
- `extract-spec-ids` is the only writer of `spec-ids.tsv`.
- Never hand-write or hand-read `spec-ids.tsv`.
- If any script exits non-zero, STOP the mutation flow and report/fix according to ownership.
- If validation findings are owned by `/order.spec` and self-fixable without changing meaning, fix and rerun.
- Maximum 3 self-fix iterations.
- If still failing, report residual findings and recommend `/order.spec-check`.

### Active feature state update

After successful write, ID extraction, and mechanical validation, update active feature state:

```bash
python3 .orderspec/scripts/active_feature.py set \
  --feature-id "$FEATURE_ID" \
  --feature-directory "$FEATURE_DIR" \
  --status specified \
  --last-command order.spec \
  --json
```

Do not hand-write `.orderspec/state/active-feature.json`.

## Semantic Self-Validation

Before completion, reason through these checks. Do not write a checklist file.

### Required semantic checks

- No file paths, library names, class names, plugin names, framework-specific query syntax, or technology versions appear in `spec.md`.
- §6 references only valid `STACK-NNN`, `ARCH-NNN`, `CONV-NNN` IDs with neutral labels.
- No unresolved blocking clarification remains.
- Every REQ has acceptance coverage.
- Every AC has inline `[Covers: ...]`.
- IF `Covers` references defined IDs.
- IF success/failure outcomes match related ACs.
- Authorization is specified for mutating interfaces and cross-tenant reads.
- Atomic/best-effort/compensating semantics are specified for multi-entity writes.
- Contradiction grid is present and has no unresolved conflict.
- DEC/ASM separation is correct.
- Tombstoned IDs remain strict anchors.
- Cross-feature refs use `FEAT-NNN-slug:LOCAL-NNN`.
- No placeholder values remain in frontmatter or normative sections.

## Downstream Impact

For refine and decompose mode only:

- If `plan.md` exists, warn:

  > `spec.md` changed — `plan.md` may be stale. Run `/order.plan` later to re-align.

- If `tasks.md` exists, warn:

  > `tasks.md` may also be stale. Re-derive via `/order.tasks` after the plan is aligned.

This command does not modify `plan.md` or `tasks.md`.

## Post-Execution Checks

No operator-defined post-execution extension phases are supported in the current OrderSpec core.

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
- traceability init result;
- ID extraction result;
- mechanical validation result;
- active feature update result;
- ID counts by prefix;
- §6 project constraint IDs referenced;
- contradiction-grid result;
- bootstrap routing, if any;
- readiness for `/order.plan`;
- recommendation to run `/order.spec-check` for high-importance work.

### Refine report

Include:

- mode;
- `spec_file`;
- changelog row;
- Contract Change Summary;
- changed IDs;
- traceability result;
- mechanical validation result;
- active feature update result;
- downstream impact warnings;
- bootstrap routing, if any;
- recommendation to run `/order.spec-check`.

### Decompose report

Include:

- decomposition table;
- selected module;
- created feature path if created;
- remaining ready-to-run prompts;
- parent spec refinement summary if a parent was narrowed.

## Done When

- [ ] Command context resolved via `command_context.py`
- [ ] Every `to_read` file was read and interpreted by `usage`
- [ ] Mode detected and stated
- [ ] No hooks or operator-defined extension phases executed
- [ ] Create mode allocated feature directory via `feature_spec.py`
- [ ] Existing non-template spec was never overwritten by a template
- [ ] Feature namespace uses `FEAT-NNN-slug`
- [ ] `spec.md` frontmatter contains `orderspec.artifact`, `feature_id`, `slug`, and valid `status`
- [ ] Project contracts constrained generation
- [ ] §6 contains only valid project contract IDs with neutral labels
- [ ] Missing project contract needs were routed to `/order.bootstrap` only with explicit confirmation
- [ ] Stable IDs use strict anchor lines
- [ ] Removed IDs are tombstoned as strict anchors
- [ ] Cross-feature refs use `FEAT-NNN-slug:LOCAL-NNN`
- [ ] IF/REQ/UJ/AC coverage links reconciled
- [ ] DEC and ASM separated correctly
- [ ] Contradiction grid present and conflict-free
- [ ] Blocking clarifications resolved
- [ ] `traceability.py init` succeeded
- [ ] `traceability.py extract-spec-ids` succeeded
- [ ] `traceability.py validate --stage spec --json` succeeded or residual findings were reported
- [ ] Active feature state updated via `active_feature.py set`
- [ ] Refine/decompose downstream impact reported
- [ ] Completion report emitted to chat
