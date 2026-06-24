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

python3 .orderspec/scripts/upstream_gate.py \
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
SELF_REPORT="$FEATURE_DIR/checklists/plan-report.md"
test -e "$SELF_REPORT" && echo "SELF_REPORT_PRESENT" || echo "SELF_REPORT_ABSENT"
```

- **SELF_REPORT_ABSENT** → no prior gate run for this artifact. Proceed normally; treat `$ARGUMENTS` as the only refinement signal.
- **SELF_REPORT_PRESENT** → read `$SELF_REPORT` and parse its header verdict (`✅ PASS` | `⛔ BLOCK` | `🔀 ROUTING REQUIRED`):
  - **verdict ✅ PASS** → the previous artifact was clean. Ignore the report as a fix-source; proceed with `$ARGUMENTS` only.
  - **verdict ⛔ BLOCK or 🔀 ROUTING REQUIRED** → this is the authoritative list of defects YOU must resolve. You MUST:
    1. Read the **Routing Required** section and the **Findings** table.
    2. Address **every** finding whose `Run` line targets `/order.plan` — these are owned by this command. Each becomes a concrete change in plan.md.
    3. Findings whose `Run` line targets a DIFFERENT command (e.g. an upstream `/order.spec`) are NOT yours: do NOT silently compensate for them. If any unresolved upstream finding blocks a fix you must make, STOP and report `PLAN_BLOCKED: upstream finding must be resolved first`, listing the finding IDs and their owning command.
    4. Treat `$ARGUMENTS` as ADDITIONAL guidance layered on top of the report — never as a replacement for it. If `$ARGUMENTS` is a vague directive such as "fix the errors" / "исправь ошибки", the report findings ARE the definition of "the errors": action them by ID.

  Record in the Completion Report which report-finding IDs you addressed, so a follow-up `/order.plan-check` can confirm closure.

## Mechanisms Are Machine State, Not Document Prose

The mechanism decisions for this feature do **not** live as a table inside `plan.md`.
They live in `mechanisms.tsv` under the feature's machine state, written **only** by
`traceability.py put-mechanisms`. This is a hard rule:

- **You MUST NOT author, hand-edit, or hand-read a mechanism table in `plan.md`.**
  `plan.md` holds prose, structure decisions, and the component diagram — never the
  machine-read mechanism matrix.
- **The only writer of `mechanisms.tsv` is `put-mechanisms`.** You emit TSV data
  rows on stdin; the script prepends the contract header, lints every row, and either
  writes the whole file atomically or rejects it and leaves the file untouched.
- **`mechanisms.tsv` is the single source of truth** for each ID's mechanism, primary file, and coverage. Downstream (`/order.tasks`) reads it via the script — never from `plan.md`.

### `mechanisms.tsv` row contract (what you emit on stdin)

One **data row per spec ID** (no header — the script writes it). Tab-separated, exactly
five columns:

```
spec_id <TAB> coverage_kind <TAB> mechanism <TAB> primary_files <TAB> test_type
```

- **`spec_id`** — one ID, e.g. `AC-003`. Exactly one row per ID; a duplicate ID is
  rejected by lint. If two IDs share one mechanism, emit **two rows** (same mechanism
  text, one ID each) — never a comma-separated list in the cell.
- **`mechanism`** — short concrete decision (e.g. `optimistic lock on version column`).
  Non-empty.
- **`primary_files`** — exactly **one** repo-relative primary file (forward-slash, **no spaces**), the point where this mechanism lives/is verified. Not a list. The full set of touched files is the path-manifest's job, not this matrix.
- **`test_type` × `coverage_kind`** — the coverage classification, lint-enforced:

  | `coverage_kind` | meaning | required `test_type` |
  |---|---|---|
  | `direct` | an executable test exercises this ID | `unit` **or** `integration` |
  | `documented` | asserted in docs/spec, **no executable task** will exercise it | `documented` |
  | `delegated:<spec_id>` | coverage is provided by another ID's mechanism | (test_type of the delegating row) |

  Hard invariants (lint rejects violations; fix the row, not the file):
  - `direct` ⇒ `test_type ∈ {unit, integration}` (a direct mechanism without an
    executable test is meaningless).
  - `documented` ⇔ `test_type = documented` (one implies the other, both directions).
  - `delegated:<ID>` ⇒ `<ID>` is a syntactically valid spec_id and **not the row's own
    id** (no self-loop). Real delegation cycles are caught later by the check gate.

- **Coverage classes that MUST appear**: every `REQ`, `AC`, `EDGE`, `INV`, `NFR` that
  the feature realizes needs a row. `SC` and `CON` are registered in `spec-ids.tsv` but
  do **not** require a mechanism row.

## Outline

1. **Setup**: Run `python3 .orderspec/scripts/setup.py plan --json` from repo root; parse FEATURE_SPEC, IMPL_PLAN, SPECS_DIR, BRANCH. For single quotes in args use `'I'\''m Groot'` or double quotes. Resolve the feature name for the scripts:

   ```bash
   FEATURE=$(basename "$FEATURE_DIR")   # the scripts take the feature NAME, not a path
   ```

2. **Load context**: Read FEATURE_SPEC (the SDD) and `.orderspec/memory/constitution.md`. Load the IMPL_PLAN template (already copied). The registered spec IDs are available from machine state — read them with the FULL script path:

   ```bash
   python3 .orderspec/scripts/traceability.py get "$FEATURE" spec-ids
   ```

   rather than re-parsing `spec.md` by hand. **Fallback**: if this prints
   `no spec-ids.tsv … run extract/put first`, then `/order.spec` did not project
   the IDs (or state was reset). Recover it yourself, then re-run the `get`:

   ```bash
   python3 .orderspec/scripts/traceability.py init "$FEATURE" # idempotent
   python3 .orderspec/scripts/traceability.py extract-spec-ids "$FEATURE"
   ```

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
   - **Implementation mechanisms**: inspect enough analogous code to choose concrete mechanisms for relevant `AC-`, `INV-`, `EDGE-`, and `NFR-` items. These choices become the `mechanisms.tsv` rows (see *Mechanisms Are Machine State*).

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
     - one internal component diagram showing physical decomposition.

   The **mechanism decisions themselves are NOT written into `plan.md`** — they are emitted to `mechanisms.tsv` via `put-mechanisms` (Outline step 4). `plan.md` may describe the mechanism *approach* in prose where it aids the reader, but the machine-read matrix lives only in the TSV.

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

     - Structure & Path Decisions: target folders, naming evidence, architectural mapping (which spec container/component → which folder/module), Component Diagram showing internal design of spec containers.
     - Do NOT generate `data-model.md`, `contracts/`, or `quickstart.md` — the data model and API contracts live in `spec.md`; reference their section headings or Spec IDs instead of duplicating them.

   - **Emit the mechanism matrix to machine state** (this replaces the old in-document mechanism table):
     - Scan spec ACs/INVs/EDGEs/NFRs/REQs for every behaviour requiring a concrete mechanism (atomicity, concurrency, idempotency, cascading, validation, persistence shape, …). For each relevant ID, decide its mechanism, its single primary file, and its coverage classification per the *row contract* above.
     - For every spec Clarification that constrains a STORED shape or persisted value (not just behavior), include a row capturing the concrete persistence decision (e.g. mechanism = "store full post-action entity snapshot, not a diff").
     - A behaviour that is genuinely documented-only (asserted in spec, but no task will exercise it) gets `coverage_kind = documented`, `test_type = documented`. This is a deliberate contract with the downstream gate, which will refuse to attach an executable task to a documented-only ID. Do NOT mark something documented if you expect a task to implement it.
     - Then write the matrix transactionally — emit one TSV data row per ID on stdin and pipe to `put-mechanisms`:

       ```bash
       FEATURE=$(basename "$FEATURE_DIR")
       printf '%s\n' \
         "AC-003	direct	optimistic lock on version column	src/services/task.service.js	unit" \
         "AC-004	delegated:AC-003	delegated to AC-003 lock path	src/services/task.service.js	unit" \
         "INV-002	direct	DB check constraint amount >= 0	src/models/task.model.js	integration" \
         "NFR-001	documented	documented latency budget, no executable assertion	docs/perf.md	documented" \
| python3 .orderspec/scripts/traceability.py put-mechanisms "$FEATURE"
       ```

       (Columns are tab-separated. The lines above use literal tabs between cells.)
     - **If `put-mechanisms` exits non-zero, the matrix is rejected and `mechanisms.tsv` is untouched.** The stderr names the offending row(s) and reason (duplicate `spec_id`, path with a space, bad `coverage_kind`/`test_type` pairing, self-delegation, too few columns). **Fix the emitted rows and re-run — never hand-write the file to work around lint.**

   - **Re-evaluate Constitution Check** after Phase 1 layout.

5. **Agent context update**: update the plan reference between `<!-- ORDERSPEC START -->` and `<!-- ORDERSPEC END -->` markers in `.kilocode/rules/orderspec-rules.md` to point to IMPL_PLAN.

## Key Rules

- Absolute paths for filesystem operations; project-relative paths inside documents.
- ERROR on gate failures or unresolved NEEDS CLARIFICATION.
- If the plan reveals a contradiction in spec.md, STOP and report — do not silently "fix" the contract.
- Every path in the manifest must be real (`[MOD]`) or genuinely absent (`[NEW]`); `test -e` is the arbiter.
- The mechanism matrix is written ONLY by `put-mechanisms`; `mechanisms.tsv` is never hand-edited and never mirrored as a table in `plan.md`.

## Post-Execution Checks

Run the **`after_plan`** phase per `.orderspec/memory/hooks-protocol.md`.

## Completion Report

Report: branch, IMPL_PLAN path, whether `research.md` was generated, constitution gate status, count of NEW vs MODIFIED files, the mechanism-matrix result (`put-mechanisms` exited zero; N rows in `mechanisms.tsv`, of which direct / documented / delegated), and readiness for `/order.tasks`.

## Done When

This self-check is for the generator only. Do NOT copy it into `plan.md`. The artifact ends at Complexity Tracking.

Before reporting completion, run this blocking self-check. If any item fails, fix `plan.md` (or the emitted mechanism rows) and repeat. If it cannot be fixed without changing `spec.md`, STOP and report `PLAN_BLOCKED`.

- [ ] **Mechanism matrix written to machine state (blocking)**: the mechanism decisions were emitted to `mechanisms.tsv` via `traceability.py put-mechanisms` and the command **exited zero**. The file was NOT hand-written, and NO mechanism table was authored inside `plan.md`. Confirm the written matrix lints clean:

  ```bash
  FEATURE=$(basename "$FEATURE_DIR")
  python3 .orderspec/scripts/traceability.py lint "$FEATURE"
  ```

  Lint must exit zero. Every `REQ`/`AC`/`EDGE`/`INV`/`NFR` the feature realizes has exactly one row; every row obeys the `coverage_kind` × `test_type` invariants; no duplicate `spec_id`; every `primary_files` cell is a single space-free repo-relative path; every `delegated:<ID>` targets a valid, non-self spec_id.

- [ ] **Manifest verified against the filesystem (mechanical, blocking)**

  Run the deterministic check on the generated plan:

  ```bash
  FEATURE=$(basename "$FEATURE_DIR")
  python3 .orderspec/scripts/traceability.py check-plan "$FEATURE"
  python3 .orderspec/scripts/traceability.py validate --stage plan "$FEATURE"
  ```

  Read `summary.exit_code` and the findings:

  - **M10** = a tag contradicts the disk (`[MOD]` on a missing path, or `[NEW]` on an existing one). This is a physical fact, NOT a judgement call. You may NOT dismiss it as a "false positive" — `test -e` is the arbiter. Fix the tag (or the path) and re-run. The `check-plan` command isolates this check so it runs even faster.
  - **M9** = a manifest line carries a path but lacks a `[NEW]`/`[MOD]` tag, OR the `pathmanifest` block is missing/lists a directory. Fix and re-run.
  - **M5** = a spec ID cited somewhere in `plan.md` prose is NOT defined in `spec.md` (dangling / hallucinated reference). This is a hard BLOCK: you invented or mistyped an ID, or left fictional IDs behind from an older template. Find every cited ID in `plan.md` (Architectural Mapping, Summary, diagrams, any leftover table) and either correct it to a real `spec.md` ID or delete the citation. Re-run until **M5** is gone.
  - Any `MECHANISM-TABLE` / mechanism-format finding (legacy M15) is **obsolete** — the mechanism matrix no longer lives in `plan.md`. Do not just ignore the finding: it means a legacy mechanism table is still in `plan.md` — DELETE that table, then re-run. The authoritative mechanism check is `traceability.py lint` above.
  - Completion is forbidden while any **M5 / M9 / M10** finding remains.

- [ ] **Upstream gate respected**: the guard returned `ok`/`advisory`/`forced` (not `halt`); on `forced`, a `--force` warning was stamped at the top of the artifact.

- [ ] **Prior gate report consumed (if present)**: if `checklists/plan-report.md` existed with a ⛔/🔀 verdict, every finding owned by `/order.plan` was addressed and listed in the Completion Report; upstream-owned findings were routed/STOPped, not silently patched. If the report was ✅ PASS or absent, this item is N/A.

- [ ] **No contract drift**: `plan.md` adds no externally visible behavior absent from `spec.md` (no new endpoints, status codes, response shapes, fields, enums, permissions, roles, RBAC, retention/TTL, jobs, flags, env vars, or NFR targets unless specified).

- [ ] **Repo mapping is complete**: Technical context, test/build commands, constitution gates, the `pathmanifest`, naming evidence, architectural mapping, and component diagram are all filled. Registration/barrel/`index.*`/route-mount files that the feature touches appear in the manifest, each tagged by verified existence (M10 clear confirms this).

- [ ] **Tests are mapped**: every new service/business-logic file has a planned unit test in the manifest (unless justified); every `spec.md` endpoint has planned integration coverage; every relevant ID has a `mechanisms.tsv` row whose `coverage_kind`/`test_type` reflects how it will be tested. Concrete test files and assertions are left to `/order.tasks`.

- [ ] **Ready for `/order.tasks`**: `/order.tasks` should not need to invent missing architecture decisions. Completion report includes branch, `plan.md` path, whether `research.md` was generated, constitution status, count of `[NEW]` vs `[MOD]` files, the mechanism-matrix summary, and readiness.
