---
orderspec:
  artifact: command_prompt
  command: order.plan
  phase: plan
description: Map the spec's logical architecture onto the current repository state — physical structure, verified stack, path manifest, and mechanism machine state.
handoffs:
  - label: Create Tasks
    agent: order.tasks
    prompt: Break the plan into tasks
    send: true
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding if not empty.

## Role of This Artifact

`plan.md` answers **WHERE and HOW**: it maps the stable contract in `spec.md` onto the **current physical state of the repository**.

Properties:
- **Regenerable**: derived from `spec.md` + actual repository state. If the repo changes, re-run this command.
- **Non-duplicating**: reference stable Spec IDs (`REQ-`, `IF-`, `AC-`, `INV-`, `EDGE-`, `NFR-`, `CON-`) instead of copying contract text.
- **Concrete**: exact repo-relative files, verified stack facts, and physical implementation mapping.
- **Mechanism-aware**: implementation mechanism decisions are written to machine state (`.state/mechanisms.tsv`) via scripts, not mirrored as Markdown tables in `plan.md`.

`spec.md` remains the source of truth for **WHAT**. `plan.md` is a repo snapshot for **WHERE/HOW**.

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

Determine mode before writing any file. State the mode in chat.

1.  **Regenerate** — active `spec.md` exists, and `plan.md` needs to be recreated.
2.  **Refine** — active `plan.md` exists, and `$ARGUMENTS` requests specific changes.

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
  --artifact      "$FEATURE_SPEC" \
  --upstream-name "spec.md" \
  --this          "/order.plan" \
  --build         "/order.spec" \
  --fix           "/order.spec" \
  --recheck       "/order.spec-check" \
  $FORCE_FLAG
```

-   **exit 2 (stop)** or **exit 1 (halt)** → STOP. Do not produce a plan.
-   **exit 0 (forced)** → Proceed, but insert this warning at the top of `plan.md`:
    `> ⚠ Built over non-PASS spec gate (verdict: {verdict}) via --force`
-   **exit 0 (advisory/ok)** → Proceed.

### Step 5: Self Gate Report Intake

Check for a prior `/order.plan-check` report.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
SELF_REPORT="$FEATURE_DIR/plan-report.md"
test -e "$SELF_REPORT" && echo "SELF_REPORT_PRESENT" || echo "SELF_REPORT_ABSENT"
```

-   **ABSENT** → Proceed.
-   **PRESENT (✅ PASS)** → Ignore report; proceed with `$ARGUMENTS`.
-   **PRESENT (⛔ BLOCK / 🔀 ROUTING)** → This is your fix-list. Address every finding targeting `/order.plan`. Route findings for other commands. Treat `$ARGUMENTS` as additional guidance, not a replacement.

### Step 6: Tooling Validation

Verify tooling and skills deterministically.

```bash
python3 .orderspec/framework/scripts/validate_tooling.py -C "$PWD" --json
```

Store the JSON output. Use it to determine skill availability. Do not manually inspect `.orderspec/skills/`.

### Step 7: Setup Plan Artifact

Initialize the plan file from the template.

```bash
python3 .orderspec/framework/scripts/setup.py plan --json --refresh-template > /dev/null
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
```

### Step 8: Focused Reconnaissance

Perform a focused repository scan to map `spec.md` onto the codebase.

**Read Budget:** Hard cap of ~20 files. Prefer exemplars over exhaustive scans.
**Verify:**
-   Language/runtime/framework versions.
-   Test/lint/build commands.
-   Source layout and module boundaries.
-   Implementation mechanisms for Spec IDs.

If repository evidence contradicts `spec.md`, STOP and report `PLAN_BLOCKED: repository contradicts spec`.

### Step 9: Write `plan.md`

Rewrite `$IMPL_PLAN` (which was initialized from `plan-template.md` in Step 7).

**Instructions per Section:**

1.  **Summary:** 2–4 sentences of technical approach only. Do not restate `spec.md` Executive Summary.
2.  **Technical Context & Stack Verification:** Fill the table with verified facts only.
    *   **Verified Against**: List the specific files you read during reconnaissance that influenced your decisions.
    *   If a fact cannot be verified, write "No [item] found in inspected manifests". Do not write vague text.
3.  **Constitution Check:** Fill the table.
    *   **Status**: Use `PASS`, `DESIGN-OK`, or `FAIL`.
    *   Never mark `PASS` for planned `[NEW]` files.
4.  **Physical Project Structure:** Emit the `pathmanifest` block (see Step 10). Do not modify the surrounding instructional comments in the template.
5.  **Structure & Path Decisions:**
    *   **File Naming Convention Evidence**: Fill the table. For the `Rule Fired` column, apply these rules in order for multi-word new filenames:
        1.  Same-layer multi-word filename precedent.
        2.  Cross-layer multi-word filename precedent.
        3.  Repo config-filename casing.
        4.  Ecosystem default.
        If rule 1 fails, explicitly write: "No same-layer precedent; rule fired: N; chosen convention: ...".
    *   **Architectural Mapping**: Map logical roles / Spec IDs to physical files.
    *   **Internal Component Diagram**: Draw physical/internal decomposition using quoted Mermaid labels.
6.  **Mechanism Matrix:** **Leave this section exactly as is in the template.** Do not add or remove text. The explanatory text is already present.
7.  **Library Documentation Evidence:** Cite skill/docs source for library-specific claims, or write "No library-specific claims."
8.  **Complexity Tracking:** Fill the table ONLY if Constitution Check has `FAIL` rows or justified deviations.

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
-   Do not list directories.

```pathmanifest
src/example/existing.py      [MOD]
src/example/new_file.py      [NEW]
src/example/old_file.py      [DEL]
tests/example/test_new.py    [NEW]
```

### Step 11: Emit Mechanism Matrix

Write mechanism decisions to machine state. You MUST NOT author a mechanism table in `plan.md`.

**1. Get Spec IDs:**
```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" get spec-ids
```
*(If this fails, run `init` then `extract-spec-ids` as per script error instructions).*

**2. Prepare Rows:**
For each required Spec ID (`REQ`, `IF`, `AC`, `EDGE`, `INV`, `NFR`; conditional `ASM`), construct a row using **only** these templates:

-   **TEMPLATE 1 (Testable logic):** `SPEC_ID<TAB>direct<TAB>mechanism<TAB>file<TAB>unit`
-   **TEMPLATE 2 (Testable via API):** `SPEC_ID<TAB>direct<TAB>mechanism<TAB>file<TAB>integration`
-   **TEMPLATE 3 (Covered by other test):** `SPEC_ID<TAB>delegated:ID<TAB>mechanism<TAB>file<TAB>unit`
-   **TEMPLATE 4 (Design only):** `SPEC_ID<TAB>documented<TAB>mechanism<TAB>plan.md<TAB>documented`

**3. Write Rows:**
```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

printf '%s\n' \
  "REQ-001  direct  validate credentials  src/services/auth.js  unit" \
  "IF-001 direct  HTTP route  src/routes/auth.js  integration" \
  | python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" put-mechanisms
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
  --feature-directory "$FEATURE_DIR" \
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

---

## Completion Report

Report to chat:
-   Branch
-   `FEATURE_DIR`
-   Constitution status summary
-   `[NEW]` / `[MOD]` / `[DEL]` file counts
-   Mechanism matrix result (row counts from `summarize-mechanisms --json`)
-   Validation result (`validate --stage plan`)
-   Readiness for `/order.tasks`

## Done When

-   [ ] Command context resolved via `command_context.py`
-   [ ] Every `to_read` file was read and interpreted by `usage`
-   [ ] Mode detected and stated
-   [ ] Feature paths resolved; `eval` used for shell vars
-   [ ] Upstream gate respected
-   [ ] `plan.md` regenerated from current template
-   [ ] Prior `plan-report.md` consumed if present
-   [ ] Scope Lock enforced: no invented requirements
-   [ ] Files listed in `Verified Against`
-   [ ] `pathmanifest` uses `[MOD]` for seen files, `[NEW]` for created
-   [ ] Mechanism rows emitted via `put-mechanisms` using Templates; **Mechanism Matrix section in plan.md left as template default**
-   [ ] `traceability.py lint` and `check-mechanisms` pass
-   [ ] `validate --stage plan` has no blocking findings
-   [ ] Active feature status updated to `planned`
-   [ ] Completion Report provided
