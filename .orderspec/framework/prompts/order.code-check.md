---
orderspec:
  artifact: command_prompt
  command: order.code-check
  phase: check
description: Terminal OrderSpec implementation gate. Traces stable contract obligations to executable paths and evidence, separates impact from proof strength, writes and validates code-report.md, and routes defects without modifying implementation artifacts.
---

## User Input

```text
$ARGUMENTS
```

Use non-empty input only to select an unambiguous feature or an explicit
`--base <ref>`. It does not grant execution capabilities or alter the contract.

## Role and Claim Boundary

`/order.code-check` is a pure inspector. It answers:

> For each agreed runtime obligation, what implementation and evidence exist,
> and is the obligation satisfied, violated, unproven, or not checked?

The gate does not claim that static inspection proves program correctness.
Verdict, assurance, and obligation result are independent:

- `verdict` controls workflow advancement;
- `assurance` states evidence strength;
- obligation `result` states what was observed.

Authority order:

1. `spec.md` — normative behavior;
2. `plan.md` and `.state/mechanisms.tsv` — repository mapping, when present;
3. `tasks.md` — advisory execution/evidence topology, when present;
4. source and tests — implementation evidence, never a source of requirements.

Internal artifact validity belongs to its `*-check`. Artifact disagreement
belongs to `/order.sync-check`. Implementation repair belongs to `/order.code`.

## Non-Negotiable Rules

1. Never edit spec, plan, tasks, generated state, source, tests, or configuration.
2. The only feature-artifact write is the resolved `code-report.md`.
3. Write a report for every computed verdict when a safe feature path exists.
   A resolver/path failure without a safe target is a chat-only STOP, not a verdict.
4. Route every `VIOLATED` or material `UNPROVEN` finding to the artifact owner.
   Reduced-assurance notes may be `Advisory` and do not require routing.
5. Severity measures runtime/contract impact, not test status, evidence source,
   inspection difficulty, or whether inspection can continue.
6. Capability silence means denial. Run tests/builds only when the resolved
   constitution grants that exact capability. Lint and style review are out of scope.
7. Framework scripts named by this prompt are deterministic gate mechanics and
   must be used exactly. Never hand-edit active-feature state.
8. Core checks are stack-neutral. Discover mutation, serialization, concurrency,
   and registration surfaces from resolved stack/architecture/convention contracts
   and repository evidence. Never assume a framework-specific API list.

## Step 1 — Resolve Command Context

Run before repository inspection or feature setup:

```bash
python3 .orderspec/framework/scripts/command_context.py resolve order.code-check --json
```

If `ok` is false or `missing_required` is non-empty, STOP. Read every existing
`to_read` item in returned order and apply its `usage` and `authority` literally.
Do not substitute a manual preload list.

## Step 2 — Resolve Feature and Canonical Report

If input names a feature, select only an unambiguous match from:

```bash
python3 .orderspec/framework/scripts/active_feature.py list --json
```

Do not mutate active selection. Otherwise validate the active feature:

```bash
python3 .orderspec/framework/scripts/active_feature.py get --json
python3 .orderspec/framework/scripts/active_feature.py validate --json
```

If no safe feature directory resolves, STOP in chat with
`CODE_STOPPED: no active feature`; do not create a root-level report.

Initialize paths and overwrite the report from its framework-owned template:

```bash
python3 .orderspec/framework/scripts/setup.py code-check --json --refresh-template
```

Use only the returned `CODE_REPORT`, `REPORT_TEMPLATE`, paths, and existence
flags. The setup script intentionally creates the report template even when
`spec.md` is missing so the missing contract can be recorded as a terminal
precondition.

- Missing `spec.md`: write `BLOCK`, set `terminal_precondition: true`, route to
  `/order.spec`, validate the report, set status `blocked`, and stop.
- Missing/archived `plan.md`: continue in spec-only mode. Record an assurance
  limit, not a finding. Skip mapping checks.
- Missing `tasks.md`: continue without task findings. Tasks are advisory.

## Step 3 — Establish Target Stability and Scope

Read existing upstream reports as signals; do not rerun upstream gates.

- Missing upstream report is an assurance note, not a defect.
- `CONSUMED_STALE` is inactive advisory history: it is neither a finding nor
  current PASS evidence. Continue from current artifacts and available evidence.
- Stale `PASS` is not proof. If affected obligations remain independently
  unambiguous, inspect them and record reduced assurance; otherwise route the
  unstable target to the relevant check.
- Existing `BLOCK`/`ROUTING_REQUIRED` or an observed artifact contradiction
  makes `target stability: UNSTABLE`. Emit one root-cause finding, set
  `terminal_precondition: true`, stop semantic judgment against that target,
  write and validate `BLOCK`, and route to the owning check or `/order.sync-check`.
- Never select a winner among disagreeing artifacts.

Scope is always the complete contract obligation set. `--base <ref>` or an
active merge may prioritize changed paths, but the report must say
`whole-contract, delta-prioritized vs <base>`; delta inspection is not permission
to omit P1, invariants, or interfaces. Use only read-only Git commands.

## Step 4 — Resolve Evidence Mode and Assurance

Resolve independently from the constitution and declared topology:

- whether tests are expected;
- whether the exact test command may execute;
- whether the exact build/compile command may execute.

Evidence modes:

| Mode | Meaning |
|---|---|
| `FULL` | relevant tests and build permitted and executed |
| `TEST_ONLY` | relevant tests executed; build denied or unavailable |
| `STATIC_TESTS` | tests inspected but execution denied or unavailable |
| `STATIC_CODE` | direct code tracing; no declared test topology |

Assurance:

| Assurance | Meaning |
|---|---|
| `EXECUTED` | all contract-required permitted executable evidence was run |
| `STATIC_STRONG` | complete static trace with relevant test/source evidence, but no execution |
| `STATIC_LIMITED` | evidence, mapping, scope, or environment materially limits proof |

Denied capability is an assurance limit, never an invented defect. An expected
test that is missing, skipped, empty, trivially true, or too weak to establish
its obligation is `UNPROVEN`. When execution is allowed, record test and build
commands separately with exit status and the shortest decisive result. Never
modify code or tests to obtain green evidence.

## Step 5 — Build the Obligation Ledger

Derive the finite obligation set from `spec.md`. Include at minimum:

- every P1 acceptance criterion;
- every invariant;
- every interface method/path/auth/input/status/shape/error obligation;
- runtime-observable NFR and success criterion;
- applicable edge cases and negative permissions.

Use `.state/spec-ids.tsv` and `.state/mechanisms.tsv` for identifiers and declared
mapping when present. Generated traceability proves declared linkage only; it
does not prove executable behavior.

For every obligation trace:

```text
obligation → implementation path → evidence → observed result
```

Use exactly these results:

- `SATISFIED`: available evidence agrees with the obligation;
- `VIOLATED`: concrete implementation/executed evidence contradicts it;
- `UNPROVEN`: required implementation or material evidence is absent/weak;
- `NOT_CHECKED`: target instability or a named inspection limit prevented judgment.

Only `VIOLATED`, `UNPROVEN`, and `NOT_CHECKED` belong in Coverage Exceptions.
Do not render the full satisfied matrix in Markdown.

## Step 6 — Semantic Inspection Passes

Run every applicable pass. Attribute behavior only when a reachable path,
feature mapping, or relevant diff connects it to the feature.

### C0 — Gate and evidence integrity

- Required contract/path unavailable: terminal precondition, not automatically
  CRITICAL.
- Permitted test/build failure is objective evidence, but severity comes from
  the exposed contract impact.
- Tool/script crash or malformed output is a framework concern and cannot be
  silently replaced by manual mechanics.

### C1 — Obligation, evidence, implementation

- Locate a reachable implementation for each obligation.
- A documented mechanism, TODO, stub, fixture-only branch, unreachable code, or
  path-only match is not executable proof.
- Match declared unit/integration/system topology without silently substituting
  another evidence type. Route wrong topology to `/order.plan`; omitted faithful
  implementation/evidence to `/order.code` or `/order.tasks` according to ownership.
- Exact response contracts require evidence that detects missing and extra fields;
  subset assertions alone do not prove exactness.

### C2 — Interfaces and serialization

Trace the complete reachable boundary: registration, authentication,
authorization, validation, handler, serialization, middleware/interceptors, and
error mapping. Compare input semantics, status, names, presence, nullability,
types, pagination, IDs, timestamps, and exact shapes where contracted.

### C3 — Invariants, writes, concurrency, and failure semantics

For every invariant, discover all reachable mutation and deletion surfaces from
the actual stack and repository. Verify enforcement at the correct boundary,
including bulk/direct paths, owner derivation, visibility filters, audit effects,
immutability, partial failure, retries, and concurrency where contracted.

If the contract leaves required atomicity/compensation/partial-failure semantics
undecided, the root finding belongs to `/order.spec`; do not impose a preferred
technology mechanism.

### C4 — Mapping and lifecycle fidelity

Skip when plan is absent. `[NEW]` means expected to exist after implementation.
Verify `[NEW]`, `[MOD]`, and direct mechanisms by symbol and behavior, not path
alone. Attribute unplanned feature behavior carefully. Route an incorrect mapping
to `/order.plan`; route code that ignored a sound mapping to `/order.code`.

### C5 — Uncontracted behavior and governance

Identify reachable new endpoints, state transitions, side effects, persistence,
response fields, permissions, or query semantics without contract basis. Route
removal to `/order.code`, or intended missing behavior to `/order.spec`. A direct
constitution `MUST` violation is CRITICAL. Do not expand into general architecture,
style, dependency freshness, lint, or whole-system review.

## Step 7 — Finding Identity, Severity, and Verdict

Finding severity measures impact only:

- `CRITICAL`: security, data loss/corruption, reachable invariant violation,
  dangerous atomicity failure, or constitution `MUST` violation;
- `HIGH`: missing/contradicted P1/MVP behavior, required interface mismatch,
  release-blocking implementation/build path, or material P1 evidence gap;
- `MEDIUM`: non-P1 behavioral/evidence/mapping defect with material impact;
- `LOW`: minor evidence weakness or contract-adjacent residue without runtime impact.

A failing build or P1 test is HIGH by default; escalate only when the revealed
impact satisfies the CRITICAL definition.

Use a deterministic finding ID. For each finding run:

```bash
python3 .orderspec/framework/scripts/validate_code_report.py finding-id \
  --pass C1 --owner order.code --obligation AC-001 --location path/to/file:symbol
```

The ID is a stable hash of pass, owner, obligation, and normalized location.
Do not assign or renumber IDs manually. Keep at most 30 detailed findings;
aggregate only LOW findings that share owner, obligation, and remediation.

Disposition:

- `Route`: owner action required;
- `Advisory`: assurance/environment note without an artifact defect;
- `Accepted`: only when an explicit resolved contract accepts the condition.

Deterministic verdict:

- `BLOCK`: terminal precondition or routed CRITICAL/HIGH;
- `ROUTING_REQUIRED`: no BLOCK condition, but routed MEDIUM/LOW;
- `PASS`: no routed findings. Advisory notes may remain.

## Step 8 — Fill and Validate the Canonical Report

Fill `CODE_REPORT` in place using `REPORT_TEMPLATE`. Do not add, remove, rename,
or duplicate sections/frontmatter fields. Routing entries reference finding IDs
and contain one copy-pasteable owner command; do not duplicate full evidence
already present in Findings. Escape Markdown table pipes inside evidence.

Use `terminal_precondition: true|false` as a YAML boolean, not a quoted string.
Fill every placeholder. Empty sections/tables use `(none)` rows.

Validate after writing and apply the status derived from the validated verdict:

```bash
python3 .orderspec/framework/scripts/validate_code_report.py finalize "$CODE_REPORT" --json
```

`finalize` performs no status write unless validation succeeds. It maps `PASS`
to `verified` and both non-PASS verdicts to `blocked` through `active_feature.py`.
If it fails, correct only `code-report.md` and rerun it. Never hand-compute a
different verdict or write status separately.

## Step 9 — Complete

Completion chat states verdict, assurance, scope, report path, result/severity
counts, separate test/build state, and next routed commands. A `PASS` with static
assurance means no routed defect was observed under the recorded limits; it does
not claim that tests or build ran.

## Done When

- [ ] context and feature paths resolved without mutating selection;
- [ ] canonical template refreshed through `setup.py code-check`;
- [ ] target stability and whole-contract scope recorded;
- [ ] finite obligations traced to implementation and evidence;
- [ ] stack-specific surfaces discovered from resolved contracts/repository;
- [ ] impact, result, disposition, and assurance kept independent;
- [ ] exception-only coverage and separate execution evidence rendered;
- [ ] report finalizer validated the verdict and applied its derived status;
- [ ] implementation and upstream artifacts remained unchanged.
