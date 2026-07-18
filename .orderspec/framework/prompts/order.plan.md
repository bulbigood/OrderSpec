---
orderspec:
  artifact: command_prompt
  command: order.plan
  phase: plan
description: Map the spec's logical architecture onto the current repository state — physical structure, verified stack, path manifest, and mechanism machine state.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding if not empty.

## Role of This Artifact

`plan.md` answers **WHERE and HOW**: it maps the stable contract in `spec.md`
onto the physical repository state observed at planning time. That state is the
baseline for one derived `tasks.md` work order.

Properties:
- **Regenerable before a work order**: derived from `spec.md` + actual
  repository state. Once `tasks.md` is generated, implementation applying
  `[NEW]`/`[DEL]` transitions does not stale or relabel the plan.
- **Non-duplicating**: reference stable Spec IDs (`REQ-`, `IF-`, `AC-`, `INV-`, `EDGE-`, `NFR-`, `CON-`) instead of copying contract text.
- **Concrete**: exact repo-relative files, verified stack facts, and physical implementation mapping.
- **Mechanism-aware**: implementation mechanism decisions are written to machine state (`.state/mechanisms.tsv`) via scripts, not mirrored as Markdown tables in `plan.md`.

`spec.md` remains the source of truth for **WHAT**. `plan.md` is a planning
baseline for **WHERE/HOW**, not a live inventory rewritten after each task.

---

## Global Execution Rules

1.  **Script Authority:** Framework scripts are deterministic. You MUST NOT second-guess, silently override, or manually repair successful script output. If a script fails, read the error and fix your input data.
2.  **Shell Variable Persistence:** Tool shell sessions may not preserve variables. You MUST rehydrate variables at the start of every new shell block by running:
    ```bash
    eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
    ```
    Do not assume variables like `$FEATURE_DIR` persist between separate shell calls.
3.  **Scope Lock:** You are mapping `spec.md` to code. Do not invent new requirements, endpoints, fields, or permissions. If implementation strictly requires a new externally visible behavior not present in `spec.md`, STOP and report `PLAN_BLOCKED: contract decision required`.

---

## Execution Flow

Follow these steps in exact order. Do not skip steps.

### Step 1: Command Context Resolution

Resolve and load all required context files.

```bash
python3 .orderspec/framework/scripts/command_context.py resolve order.plan --json
```

1.  If `ok` is `false` or `missing_required` is non-empty, STOP and report the missing context.
2.  Read every file returned in `to_read`, in returned order.
3.  Interpret each file according to its `usage` field (`apply`, `constrain`, `parse`, `inspect`, `reference`).

If required project contracts (`constitution.md`, `stack.md`, `architecture.md`, `conventions.md`) are missing, STOP and tell the user to run `/order.bootstrap` first.

### Step 2: Path Resolution

Resolve active feature paths.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
```

If this fails because no active feature directory can be resolved, STOP:
```text
PLAN_STOPPED: no active feature
  1. Create/select a feature with /order.spec
  2. Then run /order.plan
```

### Step 3: Mode Detection

Before selecting a mode, inspect the self-gate report. This check is read-only
and MUST happen before any `plan.md`-existence stop.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
SELF_REPORT="$FEATURE_DIR/plan-report.md"
test -e "$SELF_REPORT" && echo "SELF_REPORT_PRESENT" || echo "SELF_REPORT_ABSENT"
```

If `SELF_REPORT_PRESENT`, read it before mode selection.

Inspect persistent downstream feedback before mode selection:

```bash
python3 .orderspec/framework/scripts/workflow_feedback.py list \
  --feature-dir "$FEATURE_DIR" --target order.plan
```

Determine mode before writing any file. State the mode in chat.

1.  **Regenerate** — active `spec.md` exists, and `plan.md` needs to be recreated.
2.  **Refine** — active `plan.md` exists and either `$ARGUMENTS` requests specific changes, the prior `plan-report.md` has a `⛔ BLOCK` or `🔀 ROUTING` finding targeting `/order.plan`, or open workflow feedback targets `order.plan`. A blocking self-gate or open feedback selects Refine even when `$ARGUMENTS` is empty.
3.  **Refresh** — `plan.md` already exists and `$ARGUMENTS` is empty → STOP:

A blocking self-gate selects Refine even when `$ARGUMENTS` is empty. Open
workflow feedback has the same effect.

```text
PLAN_STOPPED: plan.md already exists
  - To verify the current plan: /order.plan-check
  - To regenerate from scratch: /order.plan --force
  - To apply specific changes: /order.plan "describe the change"
```

If `tasks.md` exists, inspect task markers before selecting Regenerate or
Refine. Any `[X]` marker means implementation has started and the plan is a
locked work-order baseline. Do not regenerate it merely because planned
`[NEW]` paths now exist or `[DEL]` paths are gone. With only `--force` and no
specific mapping defect, STOP:

```text
PLAN_STOPPED: implementation baseline is active
  Applied pathmanifest transitions are not plan drift.
  Continue with /order.code --resume, or describe the actual mapping defect.
```

Even a specific mapping defect MUST NOT change `plan.md` while any task is
`[X]`: changing the plan would invalidate the safe rollback baseline. STOP and
require `/order.code --reset` first. After reset, refine the plan, then run
`/order.plan-check`, `/order.tasks --force`, and `/order.tasks-check`. Never absorb
partial implementation into `[NEW]` to `[MOD]` relabeling.

### Step 4: Upstream Gate Guard

Check the upstream spec gate.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

FORCE_FLAG=""
case "$ARGUMENTS" in
  *"--force"*) FORCE_FLAG="--force" ;;
esac

python3 .orderspec/framework/scripts/upstream_gate.py \
  --report        "$FEATURE_DIR/spec-report.md" \
  --artifact      "$FEATURE_DIR/spec.md" \
  --upstream-name "spec.md" \
  --this          "/order.plan" \
  --build         "/order.spec" \
  --fix           "/order.spec" \
  --recheck       "/order.spec-check" \
  $FORCE_FLAG
```

Interpret the JSON `status` field and exit code:

-   **exit 2 (stop)** or **exit 1 (halt)** → STOP. Do not produce a plan.
-   **exit 64 (error)** → STOP. Report: `PLAN_STOPPED: upstream gate invocation error (empty shell variables — re-run setup.py paths)`. Do not produce a plan.
-   **exit 0 (forced)** → Proceed, but insert this warning at the top of `plan.md`:
    `> ⚠ Built over non-PASS spec gate (verdict: {verdict}) via --force`
-   **exit 0 (advisory)** → Proceed, but warn the user in chat: "Upstream spec gate report is stale or absent. It is recommended to re-run `/order.spec-check` before relying on this plan."
-   **exit 0 (ok)** → Proceed.

### Step 5: Self Gate Report Intake

Use self-gate result read in Step 3. Do not perform a second check.

-   **ABSENT** → Proceed.
-   **PRESENT (✅ PASS)** → Ignore report; proceed with `$ARGUMENTS`.
-   **PRESENT (⛔ BLOCK / 🔀 ROUTING)** → This is your fix-list. Address every finding targeting `/order.plan`. Route findings for other commands. Treat `$ARGUMENTS` as additional guidance, not a replacement.

Treat every open `order.plan` workflow feedback item loaded in Step 3 as an
additional mandatory fix-list item. Do not consume it yet.

### Step 6: Tooling Validation

Verify tooling and skills deterministically.

```bash
python3 .orderspec/framework/scripts/validate_tooling.py -C "$PWD" --json
```

Store the JSON output. Use it to determine skill availability. Do not manually inspect `.orderspec/skills/`.

**You MUST use the results from Step 6 in Step 8 (Focused Reconnaissance).**
For each `STACK-NNN` referenced in `spec.md` §6:
1.  Look up the technology name in `stack.md` using the `STACK-NNN` ID.
2.  If `validate_tooling.py` reports `installed_and_verified` for a matching skill — consult that skill's documentation as primary evidence source before recon.
3.  If `validate_tooling.py` reports `installed_but_missing` — follow `orderspec-rules.md` (Documentation Evidence and Tooling Policy): MUST NOT silently continue with library-specific claims; ask the operator to install the skill or proceed without library-specific claims.
4.  If no binding exists for a `STACK-NNN` — no skill is required for that technology; proceed normally.

### Step 7: Setup Plan Artifact

Initialize the plan file from the template.

```bash
python3 .orderspec/framework/scripts/setup.py plan --json --refresh-template > /dev/null
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
```

### Step 8: Focused Reconnaissance

**Before scanning the repository, you MUST consult available skills and MCP documentation sources:**

1.  **Skills:** For each `STACK-NNN` from `spec.md` §6 where `validate_tooling.py` reported `installed_and_verified`, read the skill files under `.orderspec/skills/<skill-name>/` and use them as the primary reference for that technology's conventions, patterns, and API usage.
2.  **MCP Documentation Sources:** If a documentation source (default: `context7`) is available in your runtime tool list and its `policy` is `required_if_available` for `order.plan`, you MUST consult it before making any library-specific implementation claims about technologies referenced in `spec.md` §6.
3.  **Evidence Recording:** Record all consulted sources in the `Library Documentation Evidence` section of `plan.md` (Step 9.7).

Only after consulting skills and docs sources, perform a focused repository scan to map `spec.md` onto the codebase.

**Read Budget:** Hard cap of ~20 files. Prefer exemplars over exhaustive scans.
**Verify:**
-   Language/runtime/framework versions.
-   Test/lint/build commands.
-   Source layout and module boundaries.
-   Implementation mechanisms for Spec IDs.
-   Existing project abstractions relevant to the feature (for example shared plugins, middleware, base models, transaction helpers, locks, serializers, and pagination helpers).
-   Runtime and deployment capabilities required by candidate mechanisms (for example database topology, process count, external services, queues, and distributed coordination).
-   Environment readiness for every material prerequisite: exact read-only check, expected result, repository evidence, bounded recovery option, approval/side-effect boundary, and safe fallback. Do not defer an obvious prerequisite to `/order.code`.
-   Cross-boundary completeness for every planned behavior: persistence/schema,
    service, controller/serializer, route, export/wiring, and test boundaries
    that must cooperate. A later task MUST NOT discover that an earlier model,
    schema, DTO, or route lacks fields or operations already required by
    `spec.md`.

For each material mechanism, distinguish three evidence classes:

1. **Library/API evidence** proves only that an API or feature exists and how it behaves.
2. **Repository runtime evidence** proves that the required capability is configured or supplied by manifests, deployment files, runtime configuration, or the test harness.
3. **Operational scope evidence** proves the boundary within which the mechanism is correct: `process`, `host`, `cluster`, `external service`, or `not applicable`.

Do not treat library support as runtime readiness. For example, documentation that an ODM exposes transactions does not prove that the repository deploys a transaction-capable database topology. A process-local lock does not satisfy a cluster-wide concurrency invariant unless the repository proves single-process deployment or the spec limits the invariant to one process.

Prefer an existing project abstraction when it satisfies the contract. If the plan introduces a parallel mechanism, record the observed abstraction and the concrete mismatch that prevents reuse.

If repository evidence contradicts `spec.md`, STOP and report `PLAN_BLOCKED: repository contradicts spec`.

### Step 9: Write `plan.md`

Rewrite `$IMPL_PLAN` (which was initialized from `plan-template.md` in Step 7).

**Instructions per Section:**

**Before filling sections:** Replace `[DATE]` in the template header with today's date in `YYYY-MM-DD` format (use the current date from system context).

1.  **Summary:** 2–4 sentences of technical approach only. Do not restate `spec.md` Executive Summary.
2.  **Technical Context & Stack Verification:** Fill the table with verified facts only.
    *   **Verified Against**: List the specific files you read during reconnaissance that influenced your decisions.
    *   If a fact cannot be verified, write "No [item] found in inspected manifests". Do not write vague text.
3.  **Mechanism Evidence & Runtime Closure:** Fill one row for each material mechanism whose correctness depends on an existing project abstraction, runtime/deployment capability, external service, or concurrency scope.
    *   Group Spec IDs only when they share the same mechanism and evidence.
    *   Record the existing project mechanism and either reuse it or state the concrete mismatch that prevents reuse.
    *   Record every runtime prerequisite and cite repository evidence. Library/API documentation alone is insufficient runtime evidence.
    *   List every config, deployment, manifest, and test-harness path needed to establish the prerequisite. Every listed path that will change MUST also appear in the `pathmanifest`.
    *   State operational scope as `process`, `host`, `cluster`, `external service`, or `not applicable`.
    *   If no material mechanism needs closure, retain the table and write one `None` row with a short repository-evidence statement.
    *   If a required prerequisite cannot be verified, select a repository-supported alternative or STOP and report `PLAN_BLOCKED: runtime prerequisite unverified: <mechanism>: <prerequisite>`. Do not mark the feature `planned` with an unresolved prerequisite.
4.  **Environment Readiness:** Fill the template's `Environment Readiness` table for every material runtime prerequisite. Include applicable task/spec IDs, an exact read-only check, expected result, repository evidence, bounded recovery options, required approval, side effect/scope, and safe fallback. If no prerequisite exists, write one `None` row with repository evidence. If a required prerequisite has no verified check and no safe fallback, STOP with `PLAN_BLOCKED: runtime prerequisite unverified`.
5.  **Constitution Check:** Fill the table.
    *   **Status**: Use `PASS`, `DESIGN-OK`, or `FAIL`.
    *   Never mark `PASS` for planned `[NEW]` files.
6.  **Physical Project Structure:** Emit the `pathmanifest` block (see Step 10). Preserve the fenced-block syntax and canonical template comments that document machine-readable output. Remove copied self-check lists or non-canonical authoring residue.
7.  **Structure & Path Decisions:**
    *   **File Naming Convention Evidence**: Fill the table. For the `Rule Fired` column, apply these rules in order for multi-word new filenames:
        1.  Same-layer multi-word filename precedent.
        2.  Cross-layer multi-word filename precedent.
        3.  Repo config-filename casing.
        4.  Ecosystem default.
        If rule 1 fails, explicitly write: "No same-layer precedent; rule fired: N; chosen convention: ...".
    *   **Architectural Mapping**: Map logical roles / Spec IDs to physical files.
        For every behavior-bearing `[NEW]`/`[MOD]` path, record its complete
        bounded obligation and relevant Spec IDs, including supporting paths
        that are not the single `primary_files` owner in `mechanisms.tsv`.
        Trace each required data field and interface value through persistence,
        mutation, serialization, routing, and tests. Generic labels such as
        "task schema" or "audit support" are insufficient when the spec names
        exact fields or snapshots.
    *   **Interface Fidelity**: For every `IF-NNN`, preserve the exact method, externally visible path, mounted route prefix, input semantics, response shape and nullability, pagination/filter behavior, and failure statuses. Map each behavior to the physical boundary that directly realizes it. Do not add endpoints absent from `spec.md`.
    *   **Internal Component Diagram**: Draw physical/internal decomposition using quoted Mermaid labels.
8.  **Mechanism Matrix:** Preserve this section's structure and explanatory text; do not add a Markdown mechanism table. Replace `<FEATURE_DIR>` and `<feature>` placeholders with the resolved repo-relative feature path. Mechanism rows remain machine state, not plan prose.
9.  **Library Documentation Evidence:** For each library-specific implementation claim made in this plan (e.g., specific API usage, non-obvious configuration, framework-specific patterns), cite the evidence source (skill name, documentation source name, or user-provided reference). If no library-specific claims were made, write exactly: "No library-specific claims."

    Note: Referencing `STACK-NNN` IDs from `spec.md` §6 is not itself a library-specific claim — those IDs map to `stack.md` entries. A library-specific claim is a concrete implementation detail (e.g., "use Mongoose middleware hooks", "configure Joi abortEarly option") that goes beyond simply naming the technology.
10. **Complexity Tracking:** Fill the table ONLY if Constitution Check has `FAIL` rows or justified deviations.

**Prohibitions:**
-   Do not duplicate §8 Information Model or §9 Interface Contracts from `spec.md`.
-   Do not include `TODO`, `???`, or placeholder paths.

### Step 10: Emit Pathmanifest

In the `Physical Project Structure` section of `plan.md`, emit a flat `pathmanifest` fenced block.

**Rules:**
-   One file per line.
-   Paths are repo-relative, forward-slash, no leading `./`.
-   Mark files **`[MOD]`** if you saw them during reconnaissance.
-   Mark files **`[NEW]`** if you are planning to create them.
-   Mark files **`[DEL]`** if you are planning to delete them.
-   Include every config, deployment, manifest, or test-harness file that must change to establish a runtime prerequisite selected in Mechanism Evidence & Runtime Closure.
-   Do not list directories.

```pathmanifest
src/example/existing.py      [MOD]
src/example/new_file.py      [NEW]
src/example/old_file.py      [DEL]
tests/example/test_new.py    [NEW]
```

### Step 11: Emit Mechanism Matrix

Before emitting rows, verify two bindings:

1. primary_files is the boundary that directly realizes the mechanism, not a
   nearby coordinator. For example, audit-log immutability belongs to the
   write boundary that blocks updates/deletes, not merely to an audit-create
   service. It is a single traceability owner, not an exhaustive dependency
   list. Supporting boundaries still require exact obligations and Spec IDs in
   Architectural Mapping and the pathmanifest.
2. test_type matches the evidence topology: unit mechanisms require a unit
   test path in the manifest; integration mechanisms require an integration
   test path. If the repository has no suitable path, add it to the plan
   manifest. Task-writing evidence is owned and checked by `/order.tasks` and
   `/order.tasks-check`; do not inspect or modify `tasks.md` in this command.
3. For `delegated:<ID>` rows, the target mechanism must semantically cover the
   source ID. Do not delegate an edge or acceptance criterion to a generic
   endpoint that does not explicitly verify it.
4. For `ASM-NNN` rows, emit a mechanism only when the assumption materially
   narrows implementation. Do not emit a mechanism for a `[default]`
   assumption that merely restates normal behavior.

Write mechanism decisions to machine state. You MUST NOT author a mechanism table in `plan.md`.

**1. Get Spec IDs:**
```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" get spec-ids
```
*(If this fails, try to recover by running:)*
```bash
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" init
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" extract-spec-ids
```
*(If recovery also fails — STOP and report:)*
```text
PLAN_STOPPED: spec-ids extraction failed
  The spec.md may be missing or malformed.
  Run /order.spec to create or fix the feature contract.
```

**2. Prepare Rows:**
For each required Spec ID (`REQ`, `IF`, `AC`, `EDGE`, `INV`, `NFR`; conditional `ASM`), construct a row using **only** these templates.

**Do NOT** emit rows for `UJ`, `DEC`, or `SC` IDs. They are not testable mechanisms and will be rejected by `put-mechanisms`.

-   **TEMPLATE 1 (Testable logic):** `SPEC_ID<TAB>direct<TAB>mechanism<TAB>file<TAB>unit`
-   **TEMPLATE 2 (Testable via API):** `SPEC_ID<TAB>direct<TAB>mechanism<TAB>file<TAB>integration`
-   **TEMPLATE 3 (Covered by other test):** `SPEC_ID<TAB>delegated:ID<TAB>mechanism<TAB>file<TAB>unit`
-   **TEMPLATE 4 (Design only):** `SPEC_ID<TAB>documented<TAB>mechanism<TAB>plan.md<TAB>documented`

**3. Write Rows:**
```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

printf 'REQ-001\tdirect\tvalidate credentials\tsrc/services/auth.js\tunit\nIF-001\tdirect\tHTTP route\tsrc/routes/auth.js\tintegration\n' \\n
  | python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" put-mechanisms

**CRITICAL:** Fields MUST be separated by literal TAB characters (`\\t` in printf), NOT spaces. The `mechanisms.tsv` file is tab-separated. Using spaces will cause `put-mechanisms` to fail or produce corrupt data.
```
If `put-mechanisms` exits non-zero, read stderr, fix rows, and re-run. Do not hand-edit `mechanisms.tsv`.

**4. Lint & Check:**
```bash
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" lint
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" check-mechanisms
```
Both must pass.

### Step 12: Validate Plan

Run mechanical self-checks.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" check-plan
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" validate --stage plan --json
```

Blocking findings (`severity: HIGH` or `CRITICAL`) must be fixed. Fix the data in `plan.md` or `mechanisms.tsv` and re-run validation. Do not maintain a separate list of checks; trust the script output.

### Step 13: Update Active Feature State

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

python3 .orderspec/framework/scripts/active_feature.py set \
  --feature-id "$FEATURE_ID" \
  --feature-directory "$FEATURE_DIR_REL" \
  --status planned \
  --last-command order.plan \
  --json
```

### Step 14: Consumed Report Marker

If a BLOCK/ROUTING `plan-report.md` was used in Step 5, mark it consumed.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
python3 .orderspec/framework/scripts/traceability.py mark-consumed --report "$FEATURE_DIR/plan-report.md"
```

After successful plan validation, consume each addressed workflow feedback item:

```bash
python3 .orderspec/framework/scripts/workflow_feedback.py consume \
  --feature-dir "$FEATURE_DIR" --id "FB-NNN" --consumer order.plan
```

---

## Completion Report

Report to chat:
-   `FEATURE_DIR`
-   Constitution status summary
-   `[NEW]` / `[MOD]` / `[DEL]` file counts
-   Mechanism matrix result (row counts from `summarize-mechanisms --json`)
-   Validation result (`validate --stage plan`)
-   **Manual/orchestrator next step:** Run `/order.plan-check` to verify the plan before starting `/order.tasks`
-   Readiness for `/order.tasks` (after plan-check passes)

## Done When

- [ ] Command context resolved via `command_context.py`
- [ ] Every `to_read` file was read and interpreted by `usage`
- [ ] Mode detected and stated
- [ ] Feature paths resolved; `eval` used for shell vars
- [ ] Upstream gate respected: exit 64 reported as STOP; advisory distinguished from ok
- [ ] `plan.md` regenerated from current template
- [ ] Prior `plan-report.md` consumed if present
- [ ] Open `order.plan` workflow feedback loaded; addressed items consumed only after validation
- [ ] Scope Lock enforced: no invented requirements
- [ ] Files listed in `Verified Against`
- [ ] Existing project mechanisms reviewed; every parallel mechanism has a concrete non-reuse justification
- [ ] Every behavior-bearing path has an exact bounded obligation and relevant Spec IDs; persistence-to-interface dependencies are complete before tasking
- [ ] Existing tasks with `[X]` were not absorbed by relabeling applied `[NEW]`/`[DEL]` transitions
- [ ] Mechanism Evidence & Runtime Closure completed; runtime prerequisites have repository evidence and explicit operational scope
- [ ] Every path needed to establish a selected runtime prerequisite appears in the pathmanifest
- [ ] `pathmanifest` uses `[MOD]` for seen files, `[NEW]` for created, `[DEL]` for deleted
- [ ] Mechanism rows emitted via `put-mechanisms` using templates; Mechanism Matrix section retains its structure, has no Markdown mechanism table, and contains no unresolved placeholders
- [ ] `traceability.py lint` and `check-mechanisms` pass
- [ ] `validate --stage plan` has no blocking findings
- [ ] Active feature status updated to `planned`
- [ ] Skills and MCP documentation sources consulted before reconnaissance
- [ ] `[DATE]` replaced with today's date in `plan.md` header
- [ ] Completion Report provided, including manual/orchestrator recommendation to run `/order.plan-check`
