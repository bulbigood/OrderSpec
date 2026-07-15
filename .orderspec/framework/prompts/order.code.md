---
orderspec:
  artifact: command_prompt
  command: order.code
  phase: implement
description: Execute tasks.md phase by phase in sequential task order, respecting [P] parallel hints, story checkpoints, and the irreversible Contract GATE.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Role of This Artifact

`order.code` **executes** — it makes no design decisions. All decisions live in `spec.md` (WHAT) and `plan.md` (HOW); `tasks.md` defines ORDER.

- **Tasks are self-contained**: each task carries its file path, spec IDs, and a ≤15-word paraphrase. Execute from the task line; open `spec.md` ONLY if a paraphrase is insufficient to act — never preload it.
- **Sequential by default, `[P]` is a hint**: tasks execute top-to-bottom in ID order. `[P]` means a task is file-disjoint from adjacent `[P]` tasks, so they MAY run concurrently. Sequential execution is always correct on its own.
- **Resumable**: tasks marked `[X]` are done — skip them, never redo or "improve". A re-run continues from the first unchecked task. Never remove `[X]` markers.
- **No silent deviations**: if a task cannot be executed as written (missing path, contradiction with `plan.md`, broken dependency), apply the Deviation Rule below — do not improvise.

## Global Execution Rules

1. **Script Authority:** Framework scripts are deterministic. You MUST NOT second-guess, silently override, or manually repair successful script output. If a script exits non-zero or returns invalid JSON, read the error and fix your input data.
2. **Shell Variable Persistence:** Tool shell sessions may not preserve variables. You MUST rehydrate variables at the start of every new shell block:
   ```bash
   eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
   ```
3. **Scope Lock:** You execute `tasks.md`. Do not invent new requirements, endpoints, fields, or permissions. If execution strictly requires a new externally visible behavior not present in `spec.md`, STOP and report `CODE_BLOCKED: contract decision required`.

---

## Execution Flow

Follow these steps in exact order. Do not skip steps.

### Step 1: Command Context Resolution

Resolve and load all required context files.

```bash
python3 .orderspec/framework/scripts/command_context.py resolve order.code --json
```

1. If `ok` is `false` or `missing_required` is non-empty, STOP and report the missing context.
2. Read every file returned in `to_read`, in returned order.
3. Interpret each file according to its `usage` field (`apply`, `constrain`, `parse`, `inspect`, `reference`).

If required project contracts (`constitution.md`, `stack.md`, `architecture.md`, `conventions.md`) are missing, STOP and tell the user to run `/order.bootstrap` first.

### Step 2: Path Resolution

Resolve active feature paths.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
```

If this fails because no active feature directory can be resolved, STOP:

```text
CODE_STOPPED: no active feature
  1. Create/select a feature with /order.spec
  2. Then run /order.plan
  3. Then run /order.tasks
  4. Then run /order.code
```

### Step 3: Mode Detection

Determine mode before writing any file. State the mode in chat.

1. **Resume** — `tasks.md` exists, some tasks `[X]`, `$ARGUMENTS` empty or `--resume`. Continue from first unchecked task.
2. **Force-Implement** — `tasks.md` exists, `$ARGUMENTS` contains `--force`. Bypass upstream gate halt; record override in completion report.
3. **Refresh-blocked** — `tasks.md` does not exist → STOP (upstream gate handles this in Step 4).

### Step 4: Upstream Gate Guard

Run the deterministic guard. `$FORCE_FLAG` is `--force` iff `$ARGUMENTS` contains `--force`; otherwise empty.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

FORCE_FLAG=""
case "$ARGUMENTS" in
  *"--force"*) FORCE_FLAG="--force" ;;
esac

python3 .orderspec/framework/scripts/upstream_gate.py \
  --report        "$FEATURE_DIR/tasks-report.md" \
  --artifact      "$FEATURE_DIR/tasks.md" \
  --upstream-name "tasks.md" \
  --this          "/order.code" \
  --build         "/order.tasks" \
  --fix           "/order.tasks" \
  --recheck       "/order.tasks-check" \
  $FORCE_FLAG
```

Act on exit code / `status`:

- **exit 2, `status: stop`** → STOP. Write NO code. Print the STOP message and end.
- **exit 1, `status: halt`** → STOP. Write NO code. Print the HALT message and end.
- **exit 64, `status: error`** → STOP. Report `CODE_STOPPED: upstream gate invocation error (empty shell variables — re-run setup.py paths)`.
- **exit 0, `status: forced`** → Proceed, but record in the Completion Report: `⚠ Implemented over non-PASS tasks gate (verdict: {verdict}) via --force`.
- **exit 0, `status: advisory`** → Emit `reason` as one-line ⚠ warning in chat; proceed.
- **exit 0, `status: ok`** → Proceed silently.

**STOP message (exit 2):**

```text
CODE_STOPPED: no tasks to implement
There is no tasks.md in this feature ($FEATURE_DIR).
Implementation executes an existing task list — the tasks must exist first.
  1. Create the tasks:  /order.tasks
  2. (recommended) Verify them: /order.tasks-check
  3. Then run /order.code
--force does NOT bypass this — there is genuinely nothing to implement.
```

**HALT message (exit 1):**

```text
CODE_BLOCKED: tasks gate not passed
Tasks gate verdict: {verdict} (from tasks-report.md, dated {date})
The task list has unresolved findings. Resolve them first:
  1. Action each Routing block in tasks-report.md via /order.tasks "..."
  2. Re-run /order.tasks-check until the verdict is ✅ PASS
  3. Then re-run /order.code
To implement anyway (NOT recommended), re-run with --force.
```

### Step 5: Tooling Validation

If the current command loads `tooling-protocol.md` (check `to_read` from Step 1), verify library skills deterministically:

```bash
python3 .orderspec/framework/scripts/validate_tooling.py -C "$PWD" --json
```

Interpret the JSON `summary`:

| Field | Required Action |
|-------|-----------------|
| `summary.installed_and_verified` (non-empty) | Use these skills as evidence source |
| `summary.installed_but_missing` (non-empty) | Follow `tooling-protocol.md` rule 6: MUST NOT silently continue; ask user to install or proceed without library-specific claims |
| `summary.discovered_only` (non-empty) | Ask user before installing per `tooling-protocol.md` rule 4 |
| `summary.pending` (non-empty) | Treat as unavailable; do not use as evidence |

For each `STACK-NNN` referenced in the feature spec that requires library-specific implementation:
1. Look up the technology in `.orderspec/contracts/stack.md`.
2. Search `tooling.json` `skills.bindings` for a binding where `match.stack_id` equals that `STACK-NNN`.
3. If a binding exists, use `validate_tooling.py` output to check `installed_and_verified`.
4. If no binding exists for a `STACK-NNN` requiring library-specific work, follow rule 6: do not silently proceed.

For each `docs_sources` source with `policy: "required_if_available"`:
1. Check if current command is in the source's `commands` array.
2. If yes and source is available as runtime tool, consult it before making library-specific claims.
3. If unavailable, apply `fallback_when_unavailable` (default: block library-specific claims).

Do NOT hardcode tool names in procedural logic — use only source names and policies from `tooling.json`. Record evidence in the Completion Report under `## Library Documentation Evidence`.

### Step 6: Self Gate Report Intake

Check for a prior `/order.tasks-check` report.

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
SELF_REPORT="$FEATURE_DIR/tasks-report.md"
test -e "$SELF_REPORT" && echo "SELF_REPORT_PRESENT" || echo "SELF_REPORT_ABSENT"
```

- **ABSENT** → Proceed.
- **PRESENT (✅ PASS)** → Ignore report; proceed with `$ARGUMENTS`.
- **PRESENT (⛔ BLOCK / 🔀 ROUTING)** → This is your fix-list IF findings target `/order.code`. But `/order.code` executes a frozen `tasks.md`; findings targeting `/order.tasks` or upstream MUST NOT be patched here. If any finding targets `/order.code` execution behavior (e.g. "task Tnnn path missing"), STOP and route back to `/order.tasks`. Otherwise proceed — `tasks.md` was already gated in Step 4.

### Step 7: Load Execution Context

Read the following from `$FEATURE_DIR`:

1. **REQUIRED**: `tasks.md` — phases, task lines (`T### [P?] [US?] | path | refs? | gloss`), checkpoints, GATE.
2. **REQUIRED**: `plan.md` — tech stack, file structure (pathmanifest), build/test commands.
3. **ON DEMAND ONLY**: `spec.md` — open a specific section only when a task's spec-ID paraphrase is insufficient to act. Do not preload.

Do NOT look for a hand-built Traceability Matrix or Files Touched table in `tasks.md` — those are derived artifacts; `order.tasks` does not author them. For file-disjointness verification (Step 9), use `plan.md` pathmanifest and task `path` fields directly.

### Step 8: Validate `tasks.md` Format

Before executing, validate structure. If invalid, STOP and suggest re-running `/order.tasks` (tasks.md is disposable — regenerate, don't hand-patch).

- Every task line matches: `- [ ] T### [P?] [US?] | path | refs? | gloss` (or `- [X] ...` for completed).
- Task IDs are monotonically non-decreasing (T001, T002, ...). Gaps ARE legal (T005, T010, T015). Duplicates are rejected. Out-of-order insertions signal a hand-patched file — flag but proceed in document order.
- Structure follows E-M-C: optional Setup/Expand phase first, one phase per user story in the middle, Contract phase LAST whose first task is the GATE. Extra non-story phases (e.g. dedicated unit-test phase) are allowed as long as they sit before the Contract GATE.
- `[P]` is OPTIONAL; absence everywhere is valid (purely sequential plan). Do NOT require any parallel markers.
- Verification/GATE tasks carry EMPTY refs (AC/INV IDs named in gloss, not in refs field).
- A Contract GATE task MUST exist and MUST be the first task of the Final Phase.

### Step 9: Execute Phase by Phase

Run phases strictly in order (hard sequential barriers). Within a phase, execute tasks top-to-bottom in ID order.

#### The Loop

1. Skip tasks already marked `[X]` (resume support — never redo).
2. Execute the current task (see Per-Task Rules).
3. After completing each task: mark it `[X]` in `tasks.md` immediately, before starting the next task.
4. Advance to the next unchecked task in ID order.

#### Parallelism (`[P]`) — opt-in, verified, never assumed

- **Default**: execute sequentially. `[P]` is only a hint that adjacent marked tasks MAY be safe to run concurrently.
- **Single-agent mode**: ignore `[P]` entirely — run everything sequentially in ID order. This is always correct.
- **Orchestrator mode** (sub-agents available) — before dispatching any group of adjacent `[P]` tasks concurrently, VERIFY file-disjointness:
  - For each candidate task, read its `path` field (field 2 of the task line).
  - Cross-check against `plan.md` pathmanifest to resolve any path aliases.
  - If any two candidate tasks share a resolved path, they are NOT parallel-safe — run them sequentially regardless of the `[P]` marker.
  - Only dispatch tasks concurrently when every pair in the group is file-disjoint. Wait for ALL to finish before continuing past the group.
  - When in doubt, fall back to sequential. Losing parallelism is harmless; a same-file race is not.

#### Per-Task Rules

- Touch only the file named in the task's `path` field. Need to change another file → that's a deviation (see Deviation Rule).
- Never create a file as an empty stub to "fill later" — implement the task's real behavior now. If a task itself says to create a stub, that is its complete deliverable.
- **Test tasks** (TDD): write the test, run it, **confirm it fails** before coding the corresponding implementation. If it passes immediately, flag it — the test may be vacuous.
- **Verification/GATE tasks**: run the project's test command from `plan.md` verbatim; report pass/fail per asserted AC/INV ID named in the gloss. GATE tasks carry EMPTY refs.
- **Infra tasks** (barrels, fixtures, route wiring): carry EMPTY refs by design — execute the wiring/registration, no coverage expected.

#### Checkpoint / STOP & VALIDATE (end of each story phase)

- Run the story's verification task; confirm the story works independently and earlier stories show no regressions.
- On failure: **STOP within this phase**. Fix forward only the tasks of the current story; do not start the next story until the checkpoint passes.

#### GATE before Contract (absolute barrier)

- The GATE task is the first task of the Final Phase. Run the full test command from `plan.md` verbatim; verify all AC pass, INV hold, NFR targets met.
- **On any failure: HALT. Never proceed to Contract** — contraction (deleting code, dropping columns, removing flags, removing scaffolding) is irreversible. Report what failed and stop.

#### Failure Handling Summary

| Level | On failure |
|---|---|
| Task (sequential) | Halt; report task ID, error, suspected cause |
| Task (in a concurrent `[P]` group) | Finish sibling tasks already dispatched; report failed ones; do not advance past the group |
| Checkpoint | Stay in current story phase; fix forward; re-verify |
| GATE | HALT everything; Contract phase is forbidden until GATE passes |

#### Deviation Rule

- **Minor mechanical fixes** (typo in a path with an obvious unique match, missing import) — apply, and log one line: `DEVIATION: Tnnn — what changed and why`.
- **Anything requiring a design decision** (new file not in `plan.md`, contract change, schema change) — do NOT decide. Stop and report: the fix belongs in spec/plan/tasks, not here.
- Collect all deviation lines for the Completion Report.

### Step 10: Post-Execution Coverage Check

After all tasks complete (or on halt), run a mechanical coverage check:

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

python3 .orderspec/framework/scripts/traceability.py -C "$PWD" --feature-dir "$FEATURE_DIR" check-mechanisms
```

- **exit 0** → mechanisms consistent; report success.
- **exit ≠ 0** → read stderr; report the defect. Do NOT silently patch `tasks.md` or `mechanisms.tsv` from `/order.code` — route back to `/order.tasks` if the defect is in task lines, or to `/order.spec` if a mechanism's `primary_files` is wrong.

Note: `extract-trace` validates task line coverage, not `[X]` execution state. Execution-state coverage is the job of `/order.code-check`. Do NOT run `extract-trace` here — it would re-project from task lines and ignore completion markers.

### Step 11: Update Active Feature State

On successful completion of all tasks (or on halt with partial progress), update the active feature status:

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"

python3 .orderspec/framework/scripts/active_feature.py set \
  --feature-id "$FEATURE_ID" \
  --feature-directory "$FEATURE_DIR_REL" \
  --status implementing \
  --last-command order.code \
  --json
```

- If all tasks `[X]` and GATE passed → status `implementing` (final transition to `implemented` is the job of `/order.code-check`).
- If halted early → status `implementing` (partial progress preserved for resume).

### Step 12: Mark Gate Report Consumed

If a BLOCK/ROUTING `tasks-report.md` was used as a fix-list in Step 6, mark it consumed:

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
python3 .orderspec/framework/scripts/traceability.py mark-consumed --report "$FEATURE_DIR/tasks-report.md"
```

---

## Progress Reporting (keep it lean)

- After each **phase**: one line — `Phase N: T010–T014 done (1 deviation)`.
- After a concurrent `[P]` group: one line naming the task IDs run together.
- After each **checkpoint/GATE**: verification result with AC/INV IDs pass/fail.
- No per-task narration beyond errors and deviations.

---

## Completion Report

Report to chat:

- **Tasks**: completed / total, per phase; confirm all completed tasks are marked `[X]` in tasks.md.
- **Coverage check**: `check-mechanisms` exit code (MUST be 0); one-line summary if defects found.
- **Verification**: checkpoint results per story; GATE result; final test command output summary (pass/fail counts).
- **Deviations log**: all `DEVIATION:` lines (or "none").
- **Library Documentation Evidence**: for each library-specific claim, cite the evidence source (skill name, docs source name, or user-provided reference). If a required source was unavailable, record that and the fallback applied.
- **If halted early**: exact stopping point (phase/task), reason, and the recommended next command (`/order.code` to resume, or `/order.tasks` / `/order.plan` if the failure is a design gap).
- **Active feature status**: updated to `implementing` (or not, with reason).
- **Gate report consumed**: if `tasks-report.md` was marked consumed in Step 12.
- **Recommended next step**: Run `/order.code-check` to verify the implementation before considering the feature done.

## Done When

- [ ] Command context resolved via `command_context.py`
- [ ] Every `to_read` file was read and interpreted by `usage`
- [ ] Mode detected and stated (Resume / Force-Implement)
- [ ] Feature paths resolved; `eval` used for shell vars
- [ ] Upstream gate respected: guard returned `ok`/`advisory`/`forced` (not `halt`/`stop`/`error`); on `forced`, a `--force` warning was recorded in the completion report; on `advisory`, user was warned in chat
- [ ] Tooling validated via `validate_tooling.py` (if `tooling-protocol.md` was loaded); missing required skills routed per rule 6, not silently continued
- [ ] Prior gate report consumed (if present and targeting `/order.code`): findings addressed or routed; `mark-consumed` run
- [ ] All tasks executed in phase + task-ID order and marked `[X]`, or a precise stopping point reported
- [ ] `[P]` groups run concurrently ONLY after path-disjoint verification via `plan.md` pathmanifest; otherwise sequential
- [ ] All story checkpoints passed; GATE passed before any Contract task ran
- [ ] `check-mechanisms` exited 0 (no coverage defects); defects routed to `/order.tasks` or `/order.spec`, not silently patched
- [ ] Deviations logged and reported; no silent design decisions made
- [ ] Active feature status updated to `implementing`
- [ ] Completion Report provided, including Library Documentation Evidence and recommendation to run `/order.code-check`
