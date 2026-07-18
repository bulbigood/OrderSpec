---
orderspec:
  artifact: command_prompt
  command: order.code-check
  phase: check
description: Terminal OrderSpec gate for executable code. Verifies code against the stable spec contract and the current plan mapping, respects constitution-denied execution, detects real implementation and evidence gaps, writes code-report.md on every run, and routes every defect to its owner.
---

## User Input

```text
$ARGUMENTS
```

Consider non-empty user input before selecting feature, scope, or capabilities.

## Role

`/order.code-check` is the terminal implementation gate. It answers one question:

> Does executable code implement the agreed OrderSpec contract completely and without extra observable behavior?

The verification target is:

- `spec.md`: stable WHAT contract and logical behavior;
- `plan.md`: current repository mapping and mechanism decisions, when available;
- `.state/*.tsv`: deterministic traceability and mechanism data, when available;
- `tasks.md`: advisory implementation intent and test topology, when available;
- source code and tests: implementation evidence.

OrderSpec lifecycle matters:

- `spec.md` is source of truth and is not regenerated from code;
- `plan.md` is repository-dependent but remains the frozen baseline for its
  derived work order; it is not regenerated merely because implementation
  applied `[NEW]`/`[DEL]` transitions;
- `tasks.md` is disposable execution order and may be absent after implementation;
- `[NEW]` means “expected to be created”, not “must remain absent”. An existing `[NEW]` file after `/order.code` is normally success, not a plan defect;
- `.state/*.tsv` is generated evidence. Do not hand-edit or rebuild it in this gate.

This gate inspects code semantics. Artifact-to-artifact drift belongs to `/order.sync-check`. Internal spec, plan, or task validity belongs to the corresponding `*-check` command.

## Non-Negotiable Rules

1. Pure inspector for implementation artifacts. Never edit `spec.md`, `plan.md`, `tasks.md`, `.state/*.tsv`, source code, or tests.
2. Report writing is the only feature-artifact write: always overwrite `$FEATURE_DIR/code-report.md`, including `PASS`, `BLOCK`, and `ROUTING_REQUIRED`.
3. Active-feature status may be updated only through `active_feature.py`: `verified` after `PASS`, `blocked` after `BLOCK` or `ROUTING_REQUIRED`.
4. Every finding is `Route` to the command that owns the defective artifact.
5. Default assumption is code defect. Route to `/order.spec` or `/order.plan` only when the contract or mapping is the real root. Route artifact disagreement to `/order.sync-check`.
6. Never overrule objective evidence. A failing permitted test, build failure, missing implementation, or violated invariant remains a finding at its evidence-driven severity.
7. Capability silence means denial. Never run tests, builds, compilers, linters, network calls, MCP calls, or package commands unless the constitution explicitly grants that exact capability.
8. Do not use `.orderspec/memory/*`; current project contracts live under `.orderspec/contracts/` and are loaded by command-context resolution.

## Boundary With Other Commands

| Question | Owner |
|---|---|
| Is `spec.md` complete, consistent, and testable? | `/order.spec-check` |
| Does `plan.md` faithfully map the spec onto this repository? | `/order.plan-check` |
| Is `tasks.md` faithful and correctly ordered? | `/order.tasks-check` |
| Do spec, plan, tasks, state, and repository snapshot agree? | `/order.sync-check` |
| Does executable code satisfy the agreed contract? | `/order.code-check` |
| How is a routed code defect fixed? | `/order.code` |

Run `/order.sync-check` first after merge, rebase, conflict resolution, hand-edited artifacts, or a long-lived branch. If this gate detects an artifact contradiction, stop semantic verification against the unstable target and route to `/order.sync-check`.

## Step 1: Command Context Resolution

Run once, before repository inspection or feature selection:

```bash
python3 .orderspec/framework/scripts/command_context.py resolve order.code-check --json
```

If `ok` is `false` or `missing_required` is non-empty, stop and report the resolver error. Read every existing item in `to_read`, in returned order, and interpret its `usage` and `authority` literally. Do not maintain a manual replacement list of framework rules or contracts.

The resolver is the only canonical preload source. It currently supplies framework rules, identifiers, and project contracts. Do not read `command-context.json` directly.

## Step 2: Feature Resolution

Resolve a feature only after Step 1.

1. If `$ARGUMENTS` names a feature, use `active_feature.py list --json` and select only an unambiguous match. Do not mutate active state to select it.
2. Otherwise use the active feature from `.orderspec/state/active-feature.json`:

   ```bash
   python3 .orderspec/framework/scripts/active_feature.py get --json
   python3 .orderspec/framework/scripts/active_feature.py validate --json
   ```

3. If no feature is resolved, stop with `CODE_STOPPED: no active feature` and report `/order.spec` as the human/orchestrator next command.
4. Resolve paths from active state or:

   ```bash
   eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
   ```

5. `spec.md` is required. If absent, write `BLOCK` to `code-report.md` when `$FEATURE_DIR` is known, route to `/order.spec`, and stop.
6. `plan.md` is preferred but may be archived. If absent, continue in spec-only mode and record one reduced-scope note; skip plan-fidelity checks.
7. `tasks.md` is advisory. If absent, do not invent task findings; use spec and mechanism data.

The report path is always:

```text
$FEATURE_DIR/code-report.md
```

If feature resolution itself fails, no safe report path exists; report the stop in chat and do not create a root-level report.

## Step 3: Upstream and Scope Signals

Do not re-run `spec-check`, `plan-check`, `tasks-check`, or `sync-check` inside this gate. Read existing reports only as signals.

- Existing upstream `BLOCK` or `ROUTING_REQUIRED` report is a routing finding to its owner. Do not claim code verification is clean.
- Existing upstream `CONSUMED_STALE` report is inactive advisory state, not a finding and not PASS evidence. Continue inspection; name the relevant `*-check` when fresh evidence is needed.
- Missing upstream report is an advisory note; it does not become a code defect.
- A report older than its artifact is stale evidence. Record a routing finding to the relevant `*-check`; never use stale `PASS` as current proof.
- If spec and plan disagree on behavior, emit one `/order.sync-check` routing block and verify only obligations that remain unambiguous.
- If `$ARGUMENTS` contains `--base <ref>`, use delta scope and read-only `git diff --name-only <base>...HEAD`.
- If `.git/MERGE_HEAD` exists, resolve merge-base and use delta scope.
- Otherwise use whole-feature scope. Do not guess a base ref from “latest commit”.
- In delta scope, prioritize obligations touched by changed paths, but still report observed pre-existing CRITICAL defects.

## Step 4: Constitution-Gated Evidence Mode

Read capability grants from the resolved constitution. Do not infer permission from `package.json`, a task gloss, or user wording.

Resolve separately:

- `TEST_EXEC_OK`: explicit permission to run the relevant test command;
- `BUILD_OK`: explicit permission to run the relevant build or compile command;
- `LINT_OK`: irrelevant here; linting is out of scope even if allowed;
- `TESTS_EXPECTED`: not an execution permission. Set it from declared feature topology: test tasks, test paths in `plan.md`, or non-`documented` `test_type` in `mechanisms.tsv`. If no test topology is declared, absence of tests is not a finding.

Use one mode in the report:

| Mode | Meaning |
|---|---|
| `FULL` | tests and build explicitly allowed and executed;
| `TEST-ONLY` | tests explicitly allowed, build denied or unavailable;
| `STATIC+TESTS` | tests are expected, but execution/build is denied; read tests as evidence only;
| `STATIC-ONLY` | no test topology is declared; verify code directly.

This project currently denies test execution and build/compile evidence. Expected tests may still be inspected; they must not be executed.

If execution is permitted, discover commands from the repository manifest and plan. Capture command, exit status, pass/fail counts, failing test names, and the shortest decisive assertion. Never patch a test or source file to obtain green output.

## Step 5: Build the Obligation Set

Use `spec.md` as the normative source. In delta mode focus first on touched obligations. Never drop:

- every P1 acceptance criterion;
- every invariant;
- every interface contract in §9, including status codes, response shapes, error behavior, and declared input semantics;
- runtime-observable NFRs and success criteria;
- relevant edge cases.

Use `.state/spec-ids.tsv` and `.state/mechanisms.tsv` for IDs, `coverage_kind`, `primary_files`, and `test_type` when present. Do not hand-build a competing traceability matrix and do not treat `traceability.py` coverage as proof that code implements a mechanism.

## Step 6: Mandatory Detection Passes

Run all applicable passes on every gate run. Use stable IDs `C0-NNN`, `C1-NNN`, and so on. Keep at most 30 findings; aggregate LOW overflow without dropping CRITICAL findings. Every finding has a location, obligation ID, evidence, severity, owner, and ready-to-run route.

### C0 — Gate, lifecycle, and evidence integrity

- Missing command context, active feature, or required spec: `BLOCK` and stop.
- Upstream non-PASS report: route to its owner; do not treat code-check as a substitute.
- Stale upstream report: route to the relevant `*-check`; stale `PASS` is not current evidence.
- Missing `code-report.md` before this run is normal. Missing after this run is a gate failure.
- A denied execution capability is a reduced-confidence banner, not an invented defect.
- A permitted red build is `CRITICAL`. A permitted failing P1 test or invariant test is `CRITICAL`; other permitted failing tests are at least `HIGH`.

### C1 — Obligation to test/evidence to code

For every obligation, trace:

```text
obligation -> declared evidence -> executable code path
```

- `TESTS_EXPECTED`: missing test evidence is a finding, severity by obligation priority.
- No test topology: locate a real implementation directly; do not penalize absent tests.
- Test exists but is skipped, empty, trivially true, or asserts only a fixture setup: route.
- `toMatchObject` or subset assertions cannot prove an exact §9 response shape. Route the weak test evidence for exact-field assertions when the shape is contractual.
- A `documented` mechanism is not executable evidence. A `direct` mechanism needs a real symbol/path implementation.
- `TODO`, `NotImplemented`, hardcoded fixture behavior, or unreachable code is not implementation evidence.
- For a mechanism with `test_type=unit`, locate unit-test evidence. For `integration`, locate endpoint or flow evidence. If the topology itself is wrong, route to `/order.plan` or `/order.tasks`, not silently reinterpret it.

### C2 — Interface contract and serialization fidelity

For every implemented endpoint or event, compare implementation with spec §9 and the relevant ACs:

- method, path, authentication, validation, and owner scope;
- success and failure status codes;
- response field presence, names, nullability, types, and exact error body where specified;
- pagination request semantics and response envelope;
- ID conversion and timestamps;
- serializers, `toJSON` transforms, plugins, middleware, and controller response helpers that can remove or rename fields.

Inspect the complete response path, not only the controller. A model plugin that strips a contract-required field is a code defect even when the controller sends the model object.

### C3 — Invariants, writes, and failure semantics

For immutable or append-only records, inspect every supported write surface:
updateOne, updateMany, replaceOne, findOneAndReplace, findOneAndUpdate,
findByIdAndUpdate, deleteOne, deleteMany, findOneAndDelete,
findByIdAndDelete, findOneAndRemove, findByIdAndRemove, document remove,
bulkWrite, and direct model writes where applicable. Schema immutable flags
alone are not proof that every query write path is blocked.

For every `INV`, identify every write path that could violate it and verify enforcement at the right boundary:

- owner is set from auth context and cannot be client-controlled or changed;
- soft-deleted records are excluded from every standard list/detail query;
- each mutation creates exactly one audit record;
- audit records cannot be modified or deleted through every supported write API;
- soft-deleted records reject every prohibited mutation;
- multi-document mutation and audit writes honor the failure semantics declared by the contract.

If an invariant requires atomicity, compensation, or a defined partial-failure result but spec/§13 does not decide which, route to `/order.spec` as a contract-root finding. Do not demand a transaction from code against an unresolved contract.

Check all relevant Mongoose write methods, not only `save` and `findOneAndUpdate`: `updateOne`, `updateMany`, `replaceOne`, `deleteOne`, `deleteMany`, `findOneAndDelete`, `findByIdAndDelete`, and direct model writes where applicable. Schema `immutable` flags alone are not proof that every query write path is blocked.

### C4 — Plan, mechanism, and lifecycle fidelity

Skip this pass only when `plan.md` is archived or absent.

- `[NEW]` path absent after implementation is a missing implementation finding; `[NEW]` path present is expected success.
- `[MOD]` path must exist and contain the planned change.
- Feature behavior in an unplanned file is a mapping finding, unless the plan explicitly delegates a shared serializer, middleware, or barrel change.
- Compare direct mechanism `primary_files` and mechanism description with actual symbols/exports. A path-only match is insufficient.
- Do not flag an existing `[NEW]` file as stale M10. Check presence, symbol, behavior, and relevant diff instead.
- A plan saying model static methods while behavior lives only in a service is a plan/code deviation. Route to `/order.plan` if mapping is wrong; route to `/order.code` if code ignored a sound plan.
- `test_type=unit` with only an integration test path is a test-topology mismatch. Route to `/order.plan` when mechanism classification is wrong, or `/order.tasks` when the plan is correct but task execution omitted the test.

### C5 — Uncontracted behavior and constitution compliance

- New endpoint, state transition, side effect, persistence write, response field, permission, or query behavior without a REQ/IF/AC/§9 basis is a finding. Route to `/order.code` to remove it, or `/order.spec` if it is intended behavior missing from the contract.
- A direct code violation of a constitution MUST is `CRITICAL` and routes to `/order.code`.
- Do not perform a whole-system architecture or style review. Check only obligations, declared mechanisms, and constitution rules touched by the implementation.

## Contract-Root and Desynchronization Rules

Before routing to `/order.code`, test whether the contract is the real problem.

Route to `/order.spec` when the code cannot satisfy an obligation unambiguously because of:

- pagination mentioned without envelope, limits, ordering, or a response contract;
- exact-one audit invariant without atomicity or partial-failure semantics;
- changed-fields requirement conflicting with a full-snapshot decision;
- mandatory concurrency behavior simultaneously deferred;
- contradictory status, shape, or mutation semantics.

Route to `/order.plan` when spec is stable but physical mapping or mechanism topology is wrong.

Route to `/order.sync-check` when spec, plan, tasks, generated state, or repository snapshot disagree. Do not select a winner and do not continue judging code against a moving target.

## Severity and Verdict

Use framework verdict strings exactly: `PASS`, `BLOCK`, `ROUTING_REQUIRED`. Do not use emoji variants in machine-readable reports.

- `CRITICAL`: permitted build break; P1 test failure; violated or unenforced invariant with a reachable write path; constitution MUST violation; data-corruption risk.
- `HIGH`: P1 obligation missing, contradicted, or weakly evidenced; §9 status/shape mismatch; missing required implementation path; test topology failure blocking P1; upstream non-PASS.
- `MEDIUM`: non-P1 evidence gap; plan unavailable; stale upstream report; non-MVP uncontracted behavior; mechanism deviation that still satisfies behavior.
- `LOW`: minor evidence weakness or cosmetic contract-adjacent note with no runtime impact.

Verdict rules:

- `BLOCK` if any unresolved CRITICAL exists or any HIGH affects P1/MVP scope.
- `ROUTING_REQUIRED` if any routing block remains but no BLOCK condition applies.
- `PASS` only when no routing blocks remain and no unresolved CRITICAL/HIGH exists.
- Static-mode reduced confidence never creates BLOCK and never permits PASS over an observed defect.

## Step 7: Write `code-report.md` Always

Write the report after every run, overwriting the previous file. Use the framework gate-report frontmatter schema, not the old custom emoji format:

```yaml
---
orderspec:
  artifact: gate_report
  command: "order.code-check"
  model: "{model}"
  generated_at: "{ISO-8601}"
  verdict: "{VERDICT}"
  feature_id: "{FEATURE_ID}"
  feature_directory: "{FEATURE_DIR_REL}"
---
```

Use this body structure:

```markdown
<!-- code-report.md — generated by order.code-check · {DATE} · verdict: {VERDICT} · overwritten each run -->

## Code Check (implementation — code ↔ contract)

**Verdict**: {VERDICT}
**Scope**: whole-feature | delta vs {base}
**Mode**: FULL | TEST-ONLY | STATIC+TESTS | STATIC-ONLY
**Plan**: available | archived — C4 skipped
**Suite**: green N/N | red F failing | not run (constitution) | none

{STATIC mode banner, when applicable}

### Routing Required
{all routing blocks, grouped by /order.code, /order.spec, /order.plan, /order.tasks, /order.sync-check}

### Findings
| ID | Source | Severity | Disposition | Owner | Location ↔ Obligation | Evidence |
|---|---|---|---|---|---|---|

### Obligation Coverage Matrix
| Obligation | Priority | Test/evidence | Result | Implementation | Status |
|---|---|---|---|---|---|

### Metrics
- Capabilities: tests expected/none · execution allowed/denied · build allowed/denied
- Obligations verified: N (AC N · INV N · §9 N · NFR/SC N)
- Evidence coverage: N/N
- Findings by severity: CRITICAL=N · HIGH=N · MEDIUM=N · LOW=N
- Routing by owner: code N · spec N · plan N · tasks N · sync-check N
- Active feature status: verified | blocked | unchanged (stop before status update)
- Report file: {FEATURE_DIR}/code-report.md
```

Each routing block must be precise and copy-pasteable:

```markdown
### Routing Required: {short title}

**Finding**: {code behavior vs contract or evidence gap}
**Location**: {file:line/symbol/test} ↔ {REQ/AC/INV/IF/NFR/SC or mechanism ID}
**Evidence**: {short quoted code, test assertion, report signal, or missing path}
**Why owner, not gate**: {owner owns code, contract meaning, mapping, task order, or artifact reconciliation}
**Impact if unresolved**: {runtime failure or blocked proof}
**Suggested direction**: {advisory only; never silently apply}
**Run**: `/order.{owner} "{ready-to-run request}"`
```

Render findings and the full obligation matrix even on `PASS`. Empty sections must say `(none)`, never disappear. Do not dump full test logs.

## Step 8: Active Feature Status and Completion

After writing the report, update runtime status through the framework script:

```bash
eval "$(python3 .orderspec/framework/scripts/setup.py paths --shell-vars)"
python3 .orderspec/framework/scripts/active_feature.py set \
  --feature-id "$FEATURE_ID" \
  --feature-directory "$FEATURE_DIR_REL" \
  --status verified \
  --last-command order.code-check \
  --json
```

Use `verified` only for `PASS`. For `BLOCK` or `ROUTING_REQUIRED`, use `blocked`. If the command stopped before a verdict, leave status unchanged and state why.

Completion response must state:

- verdict and scope/mode;
- report path;
- counts by severity and owner;
- suite/build state (`not run (constitution)` when denied);
- next routed command(s).

Final feature completion requires `PASS` plus `code-report.md`. `/order.code` marking all tasks `[X]` is not proof of verification.

## Done When

- [ ] command context resolved and every `to_read` item read;
- [ ] feature resolved without mutating selection;
- [ ] spec presence checked; plan/tasks lifecycle handled correctly;
- [ ] constitution capabilities resolved literally;
- [ ] whole-feature or explicit delta scope recorded;
- [ ] obligations traced to evidence and real code;
- [ ] response serialization and all relevant write paths inspected;
- [ ] plan lifecycle does not treat existing `[NEW]` files as stale;
- [ ] artifact contradictions routed to `/order.sync-check`;
- [ ] every finding routed to its owner;
- [ ] standard `code-report.md` written on every verdict;
- [ ] active-feature status updated only through `active_feature.py` after verdict;
- [ ] completion response names report and next action.

## Operating Principles

- Code-check verifies code against an agreed contract; it does not repair upstream artifacts.
- Deterministic scripts own IDs, paths, report schema, and runtime state.
- Semantic judgment is limited to code behavior, evidence strength, mechanism fidelity, serialization, invariant enforcement, and contract-root routing.
- Static verification is valid when constitution denies execution, but its reduced confidence must be visible.
- A PASS is a positive verification record, never a claim that tests ran when governance denied them.
