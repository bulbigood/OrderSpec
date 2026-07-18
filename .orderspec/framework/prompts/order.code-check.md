---
orderspec:
  artifact: command_prompt
  command: order.code-check
  phase: check
description: Terminal pure-inspection gate driven by a deterministic whole-contract obligation ledger.
---

## User Input

```text
$ARGUMENTS
```

Use input only for unambiguous feature selection or `--base <ref>`. It never
grants capabilities or changes the contract.

## Contract

`/order.code-check` is a pure inspector. It answers one question per agreed
runtime obligation:

> What reachable implementation and evidence exist, and is this obligation
> satisfied, violated, unproven, or not checked?

Authority:

1. `spec.md`: normative behavior;
2. `plan.md` and `.state/mechanisms.tsv`: physical mapping;
3. `tasks.md`: advisory execution/evidence topology;
4. source and tests: evidence, never requirements.

The gate never repairs inspected artifacts or chooses among conflicting ones.
Implementation repair belongs to `/order.code`; artifact validity to its
`*-check`. When artifacts disagree, route the root defect to the owner of the
first invalid upstream artifact; never name a command that is not registered.

Direct writes are forbidden except resolved `code-report.md`. Deterministic
gate scripts may refresh that report, write the machine ledger, and apply the
validated active-feature status. Never hand-edit generated state.

## Step 1 — Resolve Context and Feature

Resolve context and the read-only target together:

```bash
python3 .orderspec/framework/scripts/command_context.py resolve order.code-check \
  --arguments "$ARGUMENTS" --json
```

Stop on failed/missing required context. Read all `to_read` items in returned
order and apply `usage` and `authority` literally.

Use only the returned `target.feature_directory`, `target.feature_id`, and
`target.base_ref`. If no safe target resolves, stop in chat; never create a
root-level report or change active selection.

Initialize the canonical report:

```bash
TARGET_VARS="$(python3 .orderspec/framework/scripts/gate_target.py \
  --command order.code-check --arguments "$ARGUMENTS" --shell-vars)" || exit $?
eval "$TARGET_VARS"
python3 .orderspec/framework/scripts/setup.py code-check \
  --feature-dir "$FEATURE_DIR_REL" --json --refresh-template
```

Use only returned paths and existence flags.

- Missing `spec.md`: write terminal `BLOCK`, route `/order.spec`, finalize, stop.
- Missing/archived `plan.md`: continue spec-only; record an assurance limit and
  skip mapping checks.
- Missing `tasks.md`: continue without task-derived evidence; tasks are advisory.

## Step 2 — Establish Stable Target

Read existing upstream reports as signals; never rerun their gates.

- Missing report or `CONSUMED_STALE`: assurance note, not defect or PASS proof.
- Stale PASS: reduced assurance; inspect independently when obligations remain
  unambiguous.
- Active BLOCK/ROUTING or artifact contradiction: target `UNSTABLE`; emit one
  routed root-cause finding, set `terminal_precondition: true`, stop semantic
  inspection of that target, write/finalize `BLOCK`.

Never select a winner among disagreeing artifacts. Scope remains the complete
contract. `--base` only prioritizes changed paths; record
`whole-contract, delta-prioritized vs <base>`. Use read-only Git commands only.

## Step 3 — Build the Obligation Ledger

Create the machine-owned whole-contract ledger:

```bash
python3 .orderspec/framework/scripts/code_obligations.py write-ledger \
  --feature-dir "$FEATURE_DIR" \
  --output "$FEATURE_DIR/.state/code-obligations.json" --json
```

The ledger deterministically enumerates normative `REQ`, `NFR`, `SC`, `INV`,
`EDGE`, `IF`, and `AC` records, priority context, declared mechanisms, task
evidence, and candidate paths. Its ID set defines completeness. Generated
linkage proves declared mapping only, never runtime behavior.

## Step 4 — Evidence Mode and Assurance

Resolve from constitution and declared topology whether tests are expected and
whether each exact test/build command may run. Capability silence means denial.
Lint/style and dependency freshness are out of scope.

Evidence mode:

- `FULL`: relevant permitted tests and build executed;
- `TEST_ONLY`: tests executed; build denied/unavailable;
- `STATIC_TESTS`: relevant tests inspected, execution denied/unavailable;
- `STATIC_CODE`: direct code tracing; no declared test topology.

Assurance:

- `EXECUTED`: all contract-required permitted executable evidence ran;
- `STATIC_STRONG`: complete static trace with relevant source/test evidence;
- `STATIC_LIMITED`: mapping, evidence, scope, or environment materially limits proof.

Record test and build commands separately with exit status and shortest decisive
result. Missing, skipped, empty, trivially true, wrong-topology, or weak expected
tests are `UNPROVEN`. Never mutate code/tests to obtain green evidence.

Establish and record this evidence before recording any obligation result. The
ledger may be created first to enumerate scope, but no packet receives a final
result until all permitted shared test/build evidence has completed.

## Step 5 — Evaluate Obligation Packets

Inspect every ledger ID exactly once after Step 4. Resolve one bounded packet at
a time:

```bash
python3 .orderspec/framework/scripts/code_obligations.py packet \
  --feature-dir "$FEATURE_DIR" --obligation "$OBLIGATION_ID" --json
```

Read only packet evidence paths plus already resolved project contracts and the
Step 4 execution evidence. If reachable behavior requires another path, record
it as evidence and inspect it; do not modify anything.

Return one schema result and record it through `code_obligations.py record`:

```json
{
  "obligation": "AC-001",
  "result": "SATISFIED|VIOLATED|UNPROVEN|NOT_CHECKED",
  "evidence": ["path:symbol — observation"],
  "implementation_paths": ["path"],
  "finding": null
}
```

`SATISFIED` means all available static and executed evidence agrees;
`VIOLATED` means reachable behavior contradicts the contract; `UNPROVEN` means
implementation or material evidence is weak/missing; `NOT_CHECKED` means a named
instability prevented judgment. Record each result once, continue until
`complete: true`, and render only non-satisfied obligations in Coverage
Exceptions. Every `VIOLATED`, material `UNPROVEN`, and `NOT_CHECKED` requires a
routed finding; a report with `NOT_CHECKED` cannot PASS.

Write each result to a temporary file and submit it unchanged:

```bash
python3 .orderspec/framework/scripts/code_obligations.py record \
  --ledger "$FEATURE_DIR/.state/code-obligations.json" \
  --result-file "$RESULT_FILE" --json
```

## Step 6 — Semantic Inspection

For every packet, inspect only applicable surfaces connected by reachable code,
declared mapping, or relevant diff:

### C0 — Integrity

Unavailable required target is a terminal precondition, not automatically
CRITICAL. Script crash/malformed output is a framework concern; never replace it
with manual mechanics.

### C1 — Obligation and evidence

Locate reachable implementation and faithful evidence. TODO, stub, fixture-only
branch, unreachable code, documentation, or path match is not executable proof.
Exact response contracts require evidence detecting missing and extra fields.
Wrong evidence topology routes `/order.plan`; omitted faithful code/evidence
routes `/order.code` or `/order.tasks` by ownership.

### C2 — Interfaces

Trace registration, authentication, authorization, validation, handler,
serialization, middleware/interceptors, and error mapping. Compare method/path,
input semantics, status, names, presence, nullability, types, IDs, timestamps,
pagination, exact shapes, and failures only where contracted.

### C3 — Invariants and writes

Discover reachable mutation/deletion surfaces from actual stack and repository.
Check enforcement boundary, bulk/direct paths, owner derivation, visibility,
audit effects, immutability, partial failure, retry, and concurrency where
contracted. Undecided externally visible failure semantics route `/order.spec`;
never impose a preferred mechanism.

### C4 — Mapping

Skip without plan. Verify `[NEW]`, `[MOD]`, `[DEL]`, and mechanisms by symbol and
behavior, not path alone. Wrong mapping routes `/order.plan`; code ignoring sound
mapping routes `/order.code`.

### C5 — Uncontracted behavior and governance

Find reachable new endpoints, state transitions, side effects, persistence,
fields, permissions, or query semantics without contract basis. Remove through
`/order.code`, or define intended behavior through `/order.spec`. Direct
constitution `MUST` violation is CRITICAL. Avoid general style/architecture review.

## Step 7 — Findings and Verdict

Severity measures runtime/contract impact only:

- `CRITICAL`: security, data loss/corruption, reachable invariant violation,
  dangerous atomicity failure, constitution `MUST` violation;
- `HIGH`: missing/contradicted P1 behavior, interface mismatch,
  release-blocking path, material P1 evidence gap;
- `MEDIUM`: material non-P1 behavioral/evidence/mapping defect;
- `LOW`: minor evidence weakness or contract-adjacent residue.

Generate every ID through `validate_code_report.py finding-id`. Do not assign or
renumber IDs manually. Never cap material findings. LOW findings may be
aggregated only when owner, obligations, evidence, and remediation are preserved
losslessly.

Disposition:

- `Route`: owner action required;
- `Advisory`: assurance/environment note without artifact defect;
- `Accepted`: only an explicit resolved contract may accept the condition;
  never use it for `NOT_CHECKED`.

Verdict:

- `BLOCK`: terminal precondition, any routed CRITICAL/HIGH, or any `NOT_CHECKED`;
- `ROUTING_REQUIRED`: routed MEDIUM/LOW without BLOCK condition;
- `PASS`: every ledger obligation assessed, no routed finding, no `NOT_CHECKED`.

## Step 8 — Write and Finalize

Fill `CODE_REPORT` using the refreshed template without changing its structure.
Every routing entry references one finding ID and one copy-pasteable owner
command. Escape table pipes. Fill every placeholder; use `(none)` rows for empty
tables.

```bash
python3 .orderspec/framework/scripts/validate_code_report.py finalize \
  "$CODE_REPORT" --ledger "$FEATURE_DIR/.state/code-obligations.json" --json
```

The finalizer validates ledger completeness, result/finding consistency,
deterministic verdict, report structure, and derived active-feature status. On
failure, correct only `code-report.md`; never hand-edit status or ledger.

Completion chat: verdict, assurance, whole-contract scope, ledger/report paths,
result/severity counts, separate test/build state, and routed commands. Static
PASS means no routed defect under recorded limits; it never claims execution.
