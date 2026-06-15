---
description: Map the spec's logical architecture onto the current codebase — physical structure, verified stack, and constitution gates.
handoffs:
  - label: Create Tasks
    agent: order.tasks
    prompt: Break the plan into tasks
    send: true
  - label: Create Checklist
    agent: order.checklist
    prompt: Create a checklist for the following domain...
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Role of This Artifact

`plan.md` answers **WHERE and HOW**: it maps the stable contract in `spec.md` onto the **current physical state of the repository**. Properties:

- **Regenerable**: derived from spec.md + actual codebase. If the repo changes, re-run this command; never edit spec.md to fit the code.
- **Non-duplicating**: reference spec IDs (`REQ-`, `NFR-`, `CON-`, `INV-`) — do NOT copy their text, do NOT restate the Executive Summary, do NOT re-draw spec diagrams. The only diagram here is the internal Component Diagram (physical decomposition of spec containers).
- **Concrete**: exact files, folders, versions, and verified facts from the repo — no aspirational placeholders.

## Contract Drift Guard

`spec.md` is the stable contract. During planning, you MUST NOT introduce new externally visible behavior unless it is explicitly present in `spec.md`.

Forbidden additions unless already specified:

- new API endpoints, request/response shapes, status codes, fields, enums, permissions, roles, RBAC rules, authorization semantics, retention policies, TTLs, background jobs, feature flags, environment variables, or user-visible semantics;
- new non-functional targets or scale numbers not stated in `spec.md`;
- alternative error semantics that differ from acceptance criteria or clarifications.

Allowed additions:

- internal implementation mechanisms needed to satisfy existing `REQ-`, `NFR-`, `CON-`, `INV-`, `EDGE-`, or `AC-` IDs;
- physical file/module mapping;
- test file mapping;
- verified dependency/version facts from the repository.

If a necessary implementation decision would change the contract, STOP and report:
`PLAN_BLOCKED: contract decision required`, followed by the conflicting Spec IDs and the proposed decision.

## Pre-Execution Checks

Run the **`before_plan`** phase per `.orderspec/memory/hooks-protocol.md`.

## Upstream Gate Guard

The plan must not be built without an approved contract. First resolve the
feature directory, then run the deterministic guard (it makes no judgement —
it only checks that `spec.md` exists and read its gate verdict):

```bash
FEATURE_DIR="$(jq -r '.feature_directory' .orderspec/feature.json)"

.orderspec/scripts/bash/check-upstream-gate.sh \
  --report        "$FEATURE_DIR/checklists/spec-report.md" \
  --artifact      "$FEATURE_DIR/spec.md" \
  --upstream-name "spec.md" \
  --this          "/order.plan" \
  --build         "/order.spec" \
  --fix           "/order.spec" \
  --recheck       "/order.spec-check" \
  $FORCE_FLAG
```

`$FORCE_FLAG` is `--force` iff the user input explicitly contains `--force` (or an
unambiguous "build anyway despite ROUTING/BLOCK"); otherwise empty.

Act on the result by exit code / `status`:

- **exit 2, `status: stop`** → **STOP. Produce NO plan.** There is no `spec.md` to
  build from. `--force` does NOT override this. Print the STOP message and end.
- **exit 1, `status: halt`** → **STOP. Produce NO plan.** The contract has
  unresolved gate findings. Print the HALT message and end. Do not run Setup, do
  not read the repository.
- **exit 0, `status: forced`** → emit a prominent warning AND stamp this line at
  the very top of `plan.md`:
  `> ⚠ Built over non-PASS spec gate (verdict: {verdict}) via --force` — then proceed.
- **exit 0, `status: advisory`** → emit the `reason` as a one-line ⚠ warning, then
  proceed (gate is optional, or spec changed after PASS — not a hard stop).
- **exit 0, `status: ok`** → contract approved; proceed silently.

**STOP message (exit 2 — missing artifact):**

```text
PLAN_STOPPED: no spec to plan from
There is no spec.md in this feature ({FEATURE_DIR}).
A plan maps an existing contract onto the codebase — it cannot be built first.
  1. Create the contract:  /order.spec "<your feature description>"
  2. (recommended) Verify it: /order.spec-check
  3. Then run /order.plan
--force does NOT bypass this — there is genuinely nothing to plan.
```

**HALT message (exit 1 — gate not passed):**

```text
PLAN_BLOCKED: spec gate not passed
Spec gate verdict: {verdict} (from checklists/spec-report.md, dated {date})
The contract has unresolved findings. Resolve them first:
  1. Action each Routing block in spec-report.md via /order.spec "..."
  2. Re-run /order.spec-check until the verdict is ✅ PASS
  3. Then re-run /order.plan
To build the plan anyway (NOT recommended), re-run with --force.
```

## Self Gate Report Intake

Before regenerating `plan.md`, check whether a gate report from a previous run
exists at `checklists/plan-report.md`. If present, it is the cited input for any
refinement request — it carries the Routing blocks you must action. (The report is
written by the optional `/order.plan-check` gate; this command does not require
that gate to exist — it only reads the file if it is there.)

```bash
SELF_REPORT="$FEATURE_DIR/{REPORT}"
test -e "$SELF_REPORT" && echo "SELF_REPORT_PRESENT" || echo "SELF_REPORT_ABSENT"
```

- **SELF_REPORT_ABSENT** → no prior gate run for this artifact. Proceed normally; treat `$ARGUMENTS` as the only refinement signal.
- **SELF_REPORT_PRESENT** → read `$SELF_REPORT` and parse its header verdic (`✅ PASS` | `⛔ BLOCK` | `🔀 ROUTING REQUIRED`):
  - **verdict ✅ PASS** → the previous artifact was clean. Ignore the report as a fix-source; proceed with `$ARGUMENTS` only.
  - **verdict ⛔ BLOCK or 🔀 ROUTING REQUIRED** → this is the authoritative list of defects YOU must resolve. You MUST:
    1. Read the **Routing Required** section and the **Findings** table.
    2. Address **every** finding whose `Run` line targets `{THIS_CMD}` — these are owned by this command. Each becomes a concrete change in {ARTIFACT}.
    3. Findings whose `Run` line targets a DIFFERENT command (e.g. an upstream `/order.spec`) are NOT yours: do NOT silently compensate for them. If any unresolved upstream finding blocks a fix you must make, STOP and report `{BLOCKED_TOKEN}: upstream finding must be resolved first`, listing the finding IDs and their owning command.
    4. Treat `$ARGUMENTS` as ADDITIONAL guidance layered on top of the report — never as a replacement for it. If `$ARGUMENTS` is a vague directive such as "fix the errors" / "исправь ошибки", the report findings ARE the definition of "the errors": action them by ID.

  Record in the Completion Report which report-finding IDs you addressed, so a follow-up `{CHECK_CMD}` can confirm closure.

## Outline

1. **Setup**: Run `.orderspec/scripts/bash/setup-plan.sh --json` from repo root; parse FEATURE_SPEC, IMPL_PLAN, SPECS_DIR, BRANCH. For single quotes in args use `'I'\''m Groot'` or double quotes.

2. **Load context**: Read FEATURE_SPEC (the SDD) and `.orderspec/memory/constitution.md`. Load the IMPL_PLAN template (already copied).

3. **Codebase reconnaissance** (mandatory — `plan.md` must reflect repository reality):

   Perform a focused repository scan before filling the plan. Use the smallest file set sufficient to map `spec.md` onto the current codebase.

   ### Reconnaissance Read Budget

   **Hard cap**: read at most 1 dependency manifest + 1 entrypoint/route-registration file + 1 exemplar per touched implementation layer + the shared utilities/middlewares/plugins explicitly named by `spec.md` constraints. If the total exceeds ~12 files, you are over-reading. In `Verified Against`, list ONLY files whose content actually changed a planning decision.

   Default maximum: read no more than:
   - dependency manifest(s): `package.json`, `pyproject.toml`, `go.mod`, `build.gradle`, `Cargo.toml`, etc.;
   - application entrypoint or route registration file(s);
   - one existing exemplar per touched implementation layer, when available:
     - model/entity/schema layer;
     - validation/request schema layer;
     - route/API registration layer;
     - controller/handler layer;
     - service/business logic layer;
     - repository/data access layer, if the project uses one;
   - shared utilities, middlewares, plugins, or framework helpers explicitly named by `spec.md` constraints;
   - test setup/configuration and one analogous test file per relevant test type.

   Do not recursively inspect whole directories unless first-pass evidence is insufficient. If additional files are needed, read only the specific files required and record them in `Verified Against` with a short reason.

   Prefer representative exemplars over exhaustive reading.

   ### What to Verify

   - **Stack and commands**: actual language/runtime versions, framework/library versions, package manager, test/lint/build scripts.
   - **Source layout**: existing top-level structure, module boundaries, layer names, route mounting style, config organization, migration/tooling conventions if relevant.
   - **Touched files vs. gaps**: assign `[NEW]`/`[MOD]` by PHYSICAL EXISTENCE, never by logical role. The tag answers one question only: *is this file on disk right now?*
     - The fact that a file *logically should be modified* (e.g. "permissions belong in `roles.js`", "the model must be exported from the barrel `index.js`") does NOT make it `[MOD]`. Verify the file is actually present before tagging `[MOD]`.
     - Registration/barrel/index files are a common trap: they may or may not exist. Check each one with `test -e` — do not assume the framework's usual layout.
     - This is enforced mechanically by `validate-traceability` (M10): `[MOD]` ⇒ path exists; `[NEW]` ⇒ path does not exist. A violation is a blocking HIGH finding. `test -e` decides this, not your reasoning.
   - **Spec constraints**: verify every `CON-NNN` against repository evidence; flag conflicts explicitly.
   - **Testing conventions**: test folder layout, naming pattern, fixtures/helpers, integration vs. unit test style, command used to run tests.
   - **Implementation mechanisms**: inspect enough analogous code to choose concrete mechanisms for relevant `AC-`, `INV-`, `EDGE-`, and `NFR-` items.

   ### Naming Convention Verification

   Record naming conventions from actual files in each affected target folder.

   Requirements:
   - Cite at least 2 observed filenames per affected layer when available.
   - Record case style and suffix pattern, e.g. `kebab-case`, `camelCase`, `PascalCase`, `*.service.js`, `*.controller.ts`.
   - Do not claim a convention as verified unless there is direct repository evidence.
   - Every `[NEW]` path MUST follow the verified or explicitly justified convention.

   For multi-word new filenames (e.g. `auditLog` / `audit-log`), choose the case style by applying the FIRST matching rule below, and record which rule fired:
   1. Same-layer multi-word filename precedent.
   2. Cross-layer multi-word filename precedent.
   3. Repo config-filename casing (e.g. config files with multiple words).
   4. Ecosystem default (camelCase for JS/TS source files).

   When no same-layer precedent exists (rule 1 fails), explicitly write:
   `No same-layer multi-word precedent found; rule fired: <N>; chosen convention: ...`.

   The rationale MUST NOT cite a single-word filename, a schema field name, a variable name, or a function name as evidence. Use only the rule that actually fired. This fixed order keeps filenames stable across plan regenerations.

   ### Required Output in `plan.md`

   The plan MUST include:
   - `Technical Context & Stack Verification` with verified versions, dependencies, commands, constraints honored, NFR IDs, and `Verified Against`.
   - `Physical Project Structure` — a flat **path manifest**, NOT a tree (see Outline step 4 for the exact format).
   - `Structure & Path Decisions` with:
     - target folders.
     - file naming convention evidence.
     - architectural mapping from spec containers/components to physical files.
     - mechanism decisions for relevant `REQ-`, `AC-`, `INV-`, `EDGE-`, and `NFR-` IDs. The Mechanism Decisions table is the SINGLE machine-read source of truth for each ID's Test Type — it is consumed by `validate-traceability` to enforce T2a(d) at task time. It MUST therefore obey a strict format:
       - It is preceded by the `<!-- MECHANISM-TABLE: ... -->` marker (see template) so the validator can locate it unambiguously.
       - Columns appear in EXACTLY this order: `Spec ID(s) | Mechanism | Primary Files | Test Type`.
       - The `Spec ID(s)` cell contains ONLY comma-separated spec IDs (e.g. `AC-003, AC-004`) — no prose, no parentheses, no other text.
       - The `Test Type` cell is EXACTLY one of `unit`, `integration`, or `—`. Nothing else (no "unit/integration", no test file names, no assertions).
     - `Test Type` `—` means **documented-only**: there is NO executable task for this ID. The downstream gate will REFUSE to tag-autofix a `—` ID onto any task (T2a(d)). Choosing `—` is therefore a deliberate statement that this behaviour is asserted in docs, not exercised by a task — do NOT use `—` for anything you expect a task to implement.
       - Every relevant spec ID MUST appear in exactly one row's `Spec ID(s)` cell. An ID you omit is treated by the validator as documented-only.
     - Group Spec IDs that share one mechanism into a single row with comma-separated IDs. Emit one row per distinct mechanism, NOT one row per requirement.
     - For every spec Clarification that constrains a STORED shape or persisted value (not just behavior), emit a Mechanism Decisions row capturing the concrete persistence decision (e.g. "store full post-action entity snapshot, not a diff").
     - one internal component diagram showing physical decomposition.

   If repository evidence contradicts `spec.md`, STOP and report the contradiction. Do not silently adapt the contract to the codebase.

4. **Fill the plan template**:
   - **Summary**: technical approach only (2-4 sentences).
   - **Technical Context & Stack Verification**: verified facts from step 3. Mark genuinely unresolvable items as "NEEDS CLARIFICATION". List CON-IDs honored and NFR-IDs critical during coding (IDs only).
   - **Constitution Check**: evaluate gates from the constitution.

   Granularity rule:
     - Emit ONE row per top-level constitution principle (e.g. I, II, III, IV), NOT one row per sub-clause.
     - Merge sub-clauses with the same status into a short list inside the `Evidence` cell.
     - Split a sub-clause into its own row ONLY if its status differs from the principle's majority status.

   Gate status rules:
     - `PASS` = verifiable against existing repository state right now. Use only when the relevant code/config already exists or the feature does not change that area.
     - `DESIGN-OK` = planned implementation complies, but the relevant files/code do not exist yet or enforcement happens during implementation.
     - `FAIL` = current plan violates a constitution gate; justify in Complexity Tracking or STOP if unjustified.

   Never mark `PASS` for properties of planned `[NEW]` files. For new controllers, services, validations, routes, models, tests, indexes, or response behavior, use `DESIGN-OK` unless already implemented.

   - **Phase 0 — Research (conditional)**: only if NEEDS CLARIFICATION items or unverified technology choices remain. For each, research and record in `research.md`: Decision / Rationale / Alternatives considered. Skip the file entirely if nothing to resolve. All NEEDS CLARIFICATION must be resolved before Phase 1.
   - **Phase 1 — Physical Structure**:
     - Feature Artifacts Layout (per template).
     - **Physical Project Structure** — emit a flat, machine-readable **path manifest** in a fenced block tagged `pathmanifest`. This block is the contract the validator checks; there is NO tree diagram. Rules:
       - One FILE per line. NEVER list directories — they are implied by file paths.
       - Format per line: `<repo-relative-path>` then whitespace then exactly one tag `[NEW]` or `[MOD]`. No untagged lines.
       - `[NEW]` = the file does NOT exist on disk now; `[MOD]` = it DOES exist now. This is a physical fact verified by `test -e`, not a role inference.
       - Paths are repo-relative, forward-slash, no leading `./`.
       - Each new service/business-logic file MUST have a corresponding planned unit-test file present in the manifest, unless explicitly justified in Structure & Path Decisions.

       Example:

       ```pathmanifest
       src/models/task.model.js          [NEW]
       src/models/index.js               [MOD]
       src/services/task.service.js      [NEW]
       tests/unit/models/task.model.test.js   [NEW]
       ```

     - Structure & Path Decisions: target folders, naming evidence, architectural mapping (which spec container/component → which folder/module), Mechanism Decisions, Component Diagram showing internal design of spec containers.
     - Do NOT generate `data-model.md`, `contracts/`, or `quickstart.md` — the data model and API contracts live in `spec.md`; reference their section headings or Spec IDs instead of duplicating them.
     - Scan spec ACs/INVs/EDGEs for cases requiring a concrete mechanism (atomicity, concurrency, idempotency, cascading). For each, record a one-line decision in Mechanism Decisions with its `Test Type`. If a behaviour is genuinely documented-only (asserted in spec, but no task will exercise it), set its `Test Type` to `—` deliberately — this is a contract with the downstream gate, which will block any attempt to tag-autofix that ID onto a task. The plan owns HOW; do not defer mechanism choices to implement.
   - **Re-evaluate Constitution Check** after Phase 1 layout.

5. **Agent context update**: update the plan reference between `<!-- ORDERSPEC START -->` and `<!-- ORDERSPEC END -->` markers in `.kilocode/rules/orderspec-rules.md` to point to IMPL_PLAN.

## Key Rules

- Absolute paths for filesystem operations; project-relative paths inside documents.
- ERROR on gate failures or unresolved NEEDS CLARIFICATION.
- If the plan reveals a contradiction in spec.md, STOP and report — do not silently "fix" the contract.
- Every path in the manifest must be real (`[MOD]`) or genuinely absent (`[NEW]`); `test -e` is the arbiter.

## Post-Execution Checks

Run the **`after_plan`** phase per `.orderspec/memory/hooks-protocol.md`.

## Completion Report

Report: branch, IMPL_PLAN path, whether `research.md` was generated, constitution gate status, count of NEW vs MODIFIED files, and readiness for `/order.tasks`.

## Done When

This self-check is for the generator only. Do NOT copy it into `plan.md`. The artifact ends at Complexity Tracking.

Before reporting completion, run this blocking self-check. If any item fails, fix `plan.md` and repeat. If it cannot be fixed without changing `spec.md`, STOP and report `PLAN_BLOCKED`.

- [ ] **Mechanism table is machine-readable (blocking)**: the Mechanism Decisions table is preceded by the `<!-- MECHANISM-TABLE: ... -->` marker, uses the exact column order `Spec ID(s) | Mechanism | Primary Files | Test Type`, every `Spec ID(s)` cell is comma-separated IDs only, and every `Test Type` cell is exactly `unit`, `integration`, or `—`. Every relevant AC/INV/EDGE/NFR/REQ appears in exactly one row. The validator reads this table as the sole source of truth for T2a(d); a malformed cell silently mis-classifies an ID. (`validate-traceability --stage plan` raises M15 if the marker is missing or a Test Type cell is invalid.)

- [ ] **Manifest verified against the filesystem (mechanical, blocking)**

  Run the deterministic check on the generated plan:

  ```bash
  .orderspec/scripts/bash/validate-traceability.sh --json --stage plan "$FEATURE_DIR"
  ```

  Read `summary.exit_code` and the findings:

  - **M10** = a tag contradicts the disk (`[MOD]` on a missing path, or `[NEW]` on an existing one). This is a physical fact, NOT a judgement call. You may NOT dismiss it as a "false positive" — `test -e` is the arbiter. Fix the tag (or the path) and re-run.
  - **M9** = a manifest line carries a path but lacks a `[NEW]`/`[MOD]` tag, OR the `pathmanifest` block is missing/lists a directory. Fix and re-run.
  - **exit_code 1** = plan is physically inconsistent with the repo. Completion is forbidden until `exit_code` is `0` or `3` (`3` = clean, downstream artifacts absent — expected at plan stage).

  Completion is forbidden while any M9/M10 finding remains.

- [ ] **Upstream gate respected**: the guard returned `ok`/`advisory`/`forced` (not `halt`); on `forced`, a `--force` warning was stamped at the top of the artifact.

- [ ] **Prior gate report consumed (if present)**: if `{REPORT}` existed with a ⛔/🔀 verdict, every finding owned by `{THIS_CMD}` was addressed and listed in the Completion Report; upstream-owned findings were routed/STOPped, not silently patched. If the report was ✅ PASS or absent, this item is N/A.

- [ ] **No contract drift**: `plan.md` adds no externally visible behavior absent from `spec.md` (no new endpoints, status codes, response shapes, fields, enums, permissions, roles, RBAC, retention/TTL, jobs, flags, env vars, or NFR targets unless specified).

- [ ] **Repo mapping is complete**: Technical context, test/build commands, constitution gates, the `pathmanifest`, naming evidence, architectural mapping, mechanism decisions, and component diagram are all filled. Registration/barrel/`index.*`/route-mount files that the feature touches appear in the manifest, each tagged by verified existence (M10 clear confirms this).

- [ ] **Tests are mapped**: every new service/business-logic file has a planned unit test in the manifest (unless justified); every `spec.md` endpoint has planned integration coverage; every Mechanism Decisions row has a `Test Type`. Concrete test files and assertions are left to `/order.tasks`.

- [ ] **Mechanisms are consistent**: Mechanism Decisions include Spec ID(s), mechanism, primary files, and test type; IDs sharing one mechanism are grouped into a single row; no operation has two conflicting mechanisms.

- [ ] **Ready for `/order.tasks`**: `/order.tasks` should not need to invent missing architecture decisions. Completion report includes branch, `plan.md` path, whether `research.md` was generated, constitution status, count of `[NEW]` vs `[MOD]` files, and readiness.
