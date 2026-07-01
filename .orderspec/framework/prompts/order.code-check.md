---
orderspec:
  artifact: command_prompt
  command: order.code-check
  phase: check
description: Terminal verification gate — the only gate that inspects executable CODE rather than a Markdown artifact, and the only one with NO write permission of any kind (zero auto-fix; everything is Route). Verifies that the written/merged code faithfully implements the contract (spec AC/INV/§12 + plan mechanisms). Test execution, compilation, and builds are CONSTITUTION-GATED capabilities: the gate runs them ONLY when the constitution explicitly permits, and degrades to static inspection otherwise (silence means deny; it never violates governance to gather evidence). Where permitted, tests are the primary oracle; otherwise it spot-checks code against obligations directly. Operates whole-tree or on a git delta (PR / merged branch). It ALWAYS writes a report file (every run, every verdict) so that "no file" unambiguously means "the gate did not run". Routes code defects to /order.code, contract-root defects to /order.spec/.plan, and cross-artifact desync to /order.sync-check. Linting/style is out of scope — wire it as an after_code_check hook.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## What This Gate Is (and Is Not)

`code-check` is the **terminal** gate of OrderSpec and the **only one that inspects executable code**. The four upstream gates inspect Markdown artifacts; this one answers the final, different question:

> **Does the written code actually do what the contract says it must — no less, and nothing un-contracted?**

The contract is **spec + plan**, and the code is the **suspect**. When code and contract disagree, the default assumption is that the *code* is wrong (route to `/order.code`) — unless the disagreement reveals that the *contract itself* is underspecified or contradictory, in which case the root is upstream (route to `/order.spec` / `/order.plan`).

What it inspects: **source code, test code, and test results**, against spec (AC / INV / §12 contracts / SC) and plan (mechanisms / `[NEW]`/`[MOD]` files). What it does **NOT** inspect: whether the *artifacts agree with each other* — that is `/order.sync-check`. If `code-check` finds the artifacts themselves are inconsistent, it routes to `sync-check` rather than guessing which one the code should have followed.

**This gate has NO write permission over code.** Unlike the text gates, it performs **zero auto-fixes**: a code edit is almost never both unambiguous *and* reversible *and* meaning-preserving, so the "mechanical auto-fix" exception that text gates rely on does not exist for code. Every finding is **Route**. The only thing this gate executes is the **test suite / build, read-only** (and only when the constitution permits), to gather objective evidence — it never modifies a single line of source.

## The Two Non-Negotiable Invariants (adapted for the code gate — read before anything else)

This gate has no mechanical traceability script to defer to, so the invariants are adapted to its two grounds of truth — **objective evidence** and **governance** — but the spirit is identical to the text gates: never let LLM judgement manufacture a false PASS.

1. **Objective evidence is ground truth; you may never overrule it.** A failing test, a build break, or a missing implementation that you observed is a *fact*, not an opinion. You MUST import it at its evidence-driven severity. You MAY route it and add context; you MUST NOT call a red test a "false positive", reason that the code is "correct in spirit despite the failure", or silence/skip/rewrite a test to make the suite green. If you believe a test itself is wrong (asserts something the contract does not require), that is a **finding routed to `/order.code`** (fix the test) — it is NEVER grounds to ignore the failure and pass. You never run anything that mutates code, and you never re-run selectively to suppress a failure.

2. **Governance is a hard floor on the evidence method, and evidence is a hard floor on the verdict.** Two layers:
   - **Capability floor (fail-safe):** test execution, compilation, and builds run ONLY when the constitution explicitly permits — **silence means deny**. You may NEVER execute what the project did not sanction to "get a better signal". `$ARGUMENTS` may further restrict but never expand a granted capability.
   - **Verdict floor:** if you hold objective evidence of a CRITICAL/MVP defect (a red P1 test, a build break, a violable INV, a constitution-MUST breach), the verdict **cannot be ✅ PASS** — floor is 🔀 ROUTING REQUIRED, ⛔ BLOCK if MVP-affecting. Reduced confidence from a denied capability (STATIC modes) may only make you *more* cautious, never let you PASS over a defect you did observe. If you are about to write PASS while a failing test or build break stands, stop and reconcile.

## Division With sync-check (the two axes, restated from this side)

A merge / PR / long branch desynchronizes along two axes:

| Axis | Question | Gate |
|------|----------|------|
| **Artifacts ↔ artifacts** | do spec/plan/tasks/repo-snapshot agree? | `/order.sync-check` |
| **Code ↔ contract** | does the code implement the (agreed) contract? | **`code-check`** (this gate) |

Run `sync-check` **first** when artifacts may have diverged (it works on untouched code, the safest point). Run `code-check` **after** the artifacts are confirmed consistent — typically when a PR was resolved by hand and the merged code must be verified. If `code-check` discovers the artifacts are *not* consistent, it stops judging the code against an unstable target and routes to `sync-check`.

## When to Run

After `/order.code` has produced or changed code, and especially:
- A **PR / merge was resolved by hand** and the integrated code must be checked against the current contract (the canonical case; `sync-check` typically pointed you here).
- Code was written or heavily edited by a **weaker model**.
- The feature is **safety-/correctness-sensitive** and a silent code-vs-contract gap is expensive.
- Before merging a branch to `main`, as the final correctness gate.

Can be wired as a `hooks.after_code` step for weaker-model workflows. On a small, fully test-covered change where the suite is green and every AC has a passing test, it is usually a fast ✅ PASS.

## Pre-Execution Checks

Run the **`before_code_check`** phase per `.orderspec/memory/hooks-protocol.md`.

## Goal

Act as an **independent code reviewer with fresh context**, verifying the implementation against the contract. You did not write the code. Determine whether the code **faithfully and completely implements spec + plan**, using the cheapest sufficient evidence the constitution permits:

- **Test reality** — does the suite build and pass; do tests exist for the contract's AC/INV (where tests are expected)?
- **AC → test → code traceability** — every contract obligation is backed by evidence (a passing test where tests are expected, or a located real implementation otherwise), not a stub.
- **No un-contracted behavior** — the code does not silently add behavior absent from any REQ/AC/§12.
- **Plan fidelity** — code lives in the planned `[NEW]`/`[MOD]` locations and uses the planned mechanisms; no smuggled-in alternative approach.
- **Contract-root detection** — where code looks "wrong" because the AC/§12 is ambiguous or contradictory, name the *contract* as the root, not the code.

Detect and route. Never edit code.

## Out of Scope (do NOT do here)

- **Editing code** — fixing the defect is `/order.code`'s job; this gate only reports it. There is no auto-fix channel of any kind.
- **Overruling objective evidence or violating the capability floor** — see the Two Non-Negotiable Invariants above.
- **Re-judging artifact internal validity** — spec self-consistency → `/order.spec-check`; plan derivation → `/order.plan-check`; tasks order → `/order.tasks-check`.
- **Artifact-vs-artifact consistency** (drift, merge collisions, repo-staleness of plan) → `/order.sync-check`.
- **Style / lint / formatting** — not a contract concern and not this gate's job. Wire a linter as an `after_code_check` hook (`optional: true`) instead. Flag style ONLY if a constitution MUST mandates a specific rule and the code provably violates it (→ Route).
- **Performance micro-optimization** — unless an NFR sets a measurable threshold the code provably misses.
- **Internal design quality, naming, architecture** — beyond what a contract obligation or constitution MUST requires.

## Operating Constraints

- **PURE INSPECTOR — read + (permitted) execute, never write**: you MAY read source/tests and **run the test suite / build read-only when the constitution permits**; you MUST NOT modify, create, delete, or refactor any code or test file. There is no auto-fix channel.
- **Everything is Route.** Each finding names the owning command:
  - code fails to implement / partially implements / contradicts an obligation, or adds un-contracted behavior → **`/order.code`**.
  - the obligation itself is ambiguous, untestable, or self-contradictory (the code can't be "right" because the contract isn't) → **`/order.spec`** (AC/REQ/§12 root) or **`/order.plan`** (mechanism root).
  - the artifacts disagree with each other, so the verification target is unstable → **`/order.sync-check`**.
- **Tests are the primary oracle where permitted, not your reading.** Prefer a failing/missing test as evidence over prose reasoning about code. Spend LLM tokens on semantic spot-checks ONLY where tests are absent/forbidden or demonstrably weak, and only for high-impact obligations (INV, §12 contracts, MVP-AC).
- **Suspect-the-code default, with contract-root escape**: when code ≠ contract, route to `/order.code` UNLESS the contract is the root, then route upstream. Never resolve the ambiguity yourself.
- **The report file is separate from the code.** Writing `code-report.md` (see §6) is a gate artifact, not a code edit; it is written on every run regardless of verdict and never counts as touching the codebase.
- **No Ask-and-apply**: the gate never asks the user a question whose answer it would then act on by editing code. Its job ends at producing precise Routing blocks (and persisting them to the report file).
- **Constitution authority**: code violating a `.orderspec/memory/constitution.md` MUST is CRITICAL → Route.
- **Degraded plan**: if `plan.md` is absent/archived, verify against spec only, emit one MEDIUM note that plan-fidelity checks (E4) were skipped, and proceed — do not abort.

## Routing Block Format

When a finding is detected, emit exactly this; **batch all routing blocks together** at the end, do not interleave one-by-one:

```text
### Routing Required: {short title}

**Finding**: {what the code does vs what the contract requires}
**Location**: {file:line / symbol / test name} ↔ {spec AC/INV/§12 ID or plan mechanism}
**Evidence**: {failing test name + assertion | "no test covers AC-NNN" | quoted code vs quoted contract}
**Why owner, not gate**: {a code edit is never an unambiguous mechanical fix — or the root is an underspecified contract}
**Impact if unresolved**: {what breaks at runtime / which AC is unmet / which INV can be violated}
**Suggested direction**: {1–2 advisory fixes; for contract-root, which clause needs tightening}
**Run**: `/order.{code|spec|plan|sync-check} "{ready-to-run request}"`
```

The `Run` line is a concrete, copy-pasteable instruction to the owner, never an action the gate performs.

## Execution Steps

### 1. Initialize

Run `.orderspec/scripts/bash/check-prerequisites.sh --json --paths-only` once from repo root; parse FEATURE_DIR, FEATURE_SPEC, IMPL_PLAN, TASKS. Derive SPEC = FEATURE_SPEC, PLAN = IMPL_PLAN, TASKS = TASKS, and REPORT = `FEATURE_DIR/code-report.md`. `--paths-only` performs NO file validation — this gate decides presence itself, because plan/tasks are disposable and may be archived post-implementation. SPEC is required: `test -f "$FEATURE_SPEC"` — abort with instructions to re-run `/order.spec` if missing. **PLAN may be archived/absent**: `test -f "$IMPL_PLAN"` — if absent, set `PLAN_AVAILABLE = false` (degraded — skip E4 plan-fidelity, note it). TASKS is advisory here (tells you which AC/INV were meant to be implemented). If EXISTS, load `.orderspec/memory/constitution.md`. For single quotes in args use `'I'\''m Groot'` or double quotes.

**Determine scope mode** (whole-tree vs delta):
- If `$ARGUMENTS` names a base ref, or a merge just landed (`.git/MERGE_HEAD` recently present, or PR context), set `DELTA_MODE = true` and resolve `BASE` (e.g., `git merge-base HEAD <base>`); the change set is `git diff --name-only BASE...HEAD`. Focus verification on obligations touched by the changed files (but still report any pre-existing CRITICAL you encounter).
- Otherwise `DELTA_MODE = false` — verify the whole feature's implementation against the full contract.
- If git is unavailable, fall back to whole-tree.

### 2. Resolve Execution Capabilities (constitution-gated — fail-safe, the capability floor)

Test execution, compilation, and builds are **capabilities the constitution may grant or withhold**. The gate gathers evidence by executing things ONLY with explicit permission — **silence means deny** (fail-safe: never run what the project did not sanction; see Invariant 2). Read `.orderspec/memory/constitution.md` (if absent, all execution is denied — pure static mode) and resolve three independent flags:

| Capability | Granted when the constitution explicitly permits… | Effect when denied/unmentioned |
|------------|---------------------------------------------------|--------------------------------|
| `TESTS_EXPECTED` | tests are a required/allowed deliverable | absence of a test is **not** a finding; presence of a test may itself be a violation → Route |
| `TEST_EXEC_OK` | running the test suite | do not run the suite; rely on static analysis (+ any test output the user supplied in `$ARGUMENTS`) |
| `BUILD_OK` | compiling/building the project | do not compile; detect build breaks statically only (weaker, note the limitation) |

`$ARGUMENTS` may **further restrict** but never expand these (a user can say "don't run tests this time"; a user cannot override a constitution prohibition).

Set the **verification mode** from the flags and state it in the report header:

**Scope**: {whole-tree | delta vs {base}} · Mode: {FULL | STATIC+TESTS | STATIC-ONLY} · Plan: {available | archived — E4 skipped} · Suite: {green N/N | red F failing | not run (constitution) | none}

- **FULL** (`TEST_EXEC_OK` & `BUILD_OK`): run the suite + build; tests are the primary oracle (§3 onward as written).
- **STATIC+TESTS** (`TESTS_EXPECTED` but execution/build denied): read tests as a specification of intended behavior, but do NOT run them; the oracle is static trace of code ↔ obligation, cross-checked against what the tests assert.
- **STATIC-ONLY** (`TESTS_EXPECTED` false): the constitution does not want tests; the oracle is a direct static spot-check of code against each obligation. A test file existing here is a Route candidate (→ `/order.code` to remove, or `/order.spec` if the constitution is stale).

Execution is **read-only** in every mode (running tests/builds inspects, never modifies code) — and only occurs in FULL.

### 3. Establish the Oracle (mode-dependent)

**FULL mode only — run the suite read-only**: discover the test command (manifest scripts, CI config, convention) and execute it. Capture build/compile success, pass/fail counts, failing test names + assertions, and which contract IDs tests reference.
- Suite does not build → CRITICAL `E0-001` (→ `/order.code`); keep the rest brief, focused on the break.
- `TESTS_EXPECTED` but no runnable suite exists → HIGH `E0-002` ("no executable tests where the constitution expects them" → `/order.code` to add, or `/order.tasks` if the test task was never specified).
- Never modify a test to make it pass; a failing test is evidence (Invariant 1).

**STATIC+TESTS mode** — do NOT execute. Read test files as a declared behavior spec: each test names an obligation and an expected outcome. Verify statically that the code's behavior matches what the test asserts. If `$ARGUMENTS` includes externally-run test output (e.g., CI logs), use it as evidence but do not run anything yourself.

**STATIC-ONLY mode** — there is no test oracle by design. Skip E0; the oracle for §5 is direct static reading of the implementation against each obligation. Note in the header that verification confidence is reduced (no executable evidence).

### 4. Build the Obligation Set

From spec (in DELTA_MODE, prioritize those touched by the change set): collect the contract obligations to verify — every **AC** (Given/When/Then), every **INV**, every **§12 contract** (status codes, response shapes, idempotency semantics), and **SC** that maps to runtime-observable behavior. Note their priority (P1 = MVP from §15). This is the checklist the code must satisfy. Cap detailed verification at the highest-impact obligations if the set is large; never drop a P1/INV/§12 item.

### 5. Detection Passes (DETECT ONLY — Route everything)

**These passes are MANDATORY on every run.** Limit to 30 findings total; on overflow drop LOW first, aggregate into one summary line, never drop a CRITICAL. Stable IDs per pass (E1-001…). The full Findings table and Obligation Coverage Matrix MUST appear in the output on every run, including PASS.

#### E1. Obligation → (Test) → Code Traceability (the core pass)

The chain's middle link (a test) is required **only when `TESTS_EXPECTED` is true**. In STATIC-ONLY mode, verify obligation → code directly (skip the test link; absence of a test is not a finding).

For each obligation in the set:
- **E1a — backed by evidence?**
  - `TESTS_EXPECTED` true: no test exercises this AC/INV/§12 → **Route** (severity by priority).
  - STATIC-ONLY: no need for a test; instead, if you **cannot locate any code** implementing this obligation → **Route** (→ `/order.code`).
- **E1b — does the evidence hold?** FULL: a test exists and **fails** → **Route** (→ `/order.code`), quote the assertion, CRITICAL if P1 AC/INV. STATIC+TESTS/STATIC-ONLY: the code statically contradicts the obligation's Then-clause → **Route**.
- **E1c — evidence is real, not vacuous?** FULL/STATIC+TESTS: the test actually asserts the Then-clause (not trivially-true, skipped, or asserting a stub's hardcoded value) → else **Route**.
- **E1d — implementation is real, not a stub?** The code path actually implements behavior (not `TODO`/`NotImplemented`/hardcoded fixture) → else **Route**. (Applies in all modes.)

#### E2. No Un-Contracted Behavior

- E2a: Code in the changed/feature files introduces externally-observable behavior (an endpoint, a state transition, a side effect) that **no REQ/AC/§12 describes** → **Route**. Either the behavior is unwanted (→ `/order.code` remove) or the contract is missing it (→ `/order.spec` to add — advisory, the gate states both directions, never picks). Un-contracted behavior is a contract risk even if tests pass.

#### E3. §12 Contract Fidelity

- E3a: For each implemented endpoint/event, the **status codes, response shapes, and error bodies** match spec §12 exactly (the single normative source). A 200 where §12 says 409, a missing field, a renamed error code → **Route** (→ `/order.code`; if §12 itself is wrong, `/order.spec`). Prefer a contract test as evidence; spot-read the handler only if untested.
- E3b: **Idempotency / failure semantics** declared in §12 or §13 (atomic / best-effort / compensating for multi-entity writes) are actually honored by the code path → else **Route**, CRITICAL if an INV is violable.

#### E4. Plan Fidelity (skipped if `PLAN_AVAILABLE = false`)

- E4a: Code changes live in the planned `[NEW]`/`[MOD]` locations; a planned `[NEW]` file is absent, or substantial feature code landed in files the plan never mentioned → **Route** (→ `/order.plan` to reconcile the map, or `/order.code` if the code went rogue).
- E4b: The code uses the **mechanism the plan specified** (e.g., plan said "validate via the existing X validator"; code rolled its own). A smuggled-in alternative mechanism → **Route** (→ `/order.code`, or `/order.plan` if the planned mechanism proved unworkable and the deviation is justified). The gate never picks which.

#### E5. Invariant Enforcement

- E5a: Each **INV** (deterministic always-true rule) is actually enforced where the code could violate it (e.g., "exactly one active record" enforced by a constraint/guard, not merely assumed). An INV with no enforcement point and no test → **Route**, HIGH+ (INV breaches corrupt data).

#### E6. Constitution Compliance (code level)

- E6a: Code violating a constitution MUST (mandated pattern, prohibited dependency, required security control) → CRITICAL, **Route** to the offending owner. Do NOT perform a full whole-system constitution sweep — that is `/order.analyze`; flag only a direct violation you encounter in the code under review.

#### Contract-Root Rule (applies across all passes)

Before routing a finding to `/order.code`, check: is the code "wrong" only because the obligation is **ambiguous, untestable, or self-contradictory**? If so, the root is the contract — route to `/order.spec` (AC/§12) or `/order.plan` (mechanism) instead, and say so. Do not ask the code to satisfy an unsatisfiable spec.

#### Artifact-Desync Rule (escape hatch)

If you observe that spec and plan **disagree with each other** about what the code should do (so there is no single stable target), stop verifying against the moving target: emit one Routing block (→ `/order.sync-check`) and verify only the obligations that are unambiguous across both. Do not pick which artifact the code should have followed.

### 6. Severity Assignment

- **CRITICAL**: suite does not build (E0-001); a failing test for a P1 AC or an INV; an INV with no enforcement and violable by existing code paths; §12 failure-semantics breach risking data corruption; constitution MUST violation in code.
- **HIGH**: a P1 AC unbacked by evidence (no test in test-expected modes, or no locatable implementing code in STATIC-ONLY); a passing-but-vacuous test for a P1/INV/§12 obligation; §12 status/shape mismatch on an MVP endpoint; planned `[NEW]` file absent; `TESTS_EXPECTED` but no runnable suite (E0-002).
- **MEDIUM**: missing test for a non-MVP AC; un-contracted behavior of low blast radius; plan-mechanism deviation that still meets the AC; plan-fidelity skipped (degraded, PLAN absent); a test file present while the constitution forbids tests (STATIC-ONLY) → Route to `/order.code`; **reduced-confidence verification because execution/build was constitution-denied (informational note, never an MVP-blocker)**.
- **LOW**: cosmetic divergence with no contract impact; minor un-contracted helper with no external effect; style-only-if-constitution-mandated near-misses.

**MVP-scope**: obligations tied to P1 user journeys (spec §15). A HIGH on MVP blocks; off-MVP does not auto-block.

### 7. Determine Verdict

**Step 1 — apply the evidence floor (Invariant 2):** if you hold objective evidence of a CRITICAL or MVP-affecting defect (build break, red P1 test, violable INV, constitution-MUST breach), the verdict is already non-PASS; you may only decide between 🔀 ROUTING REQUIRED and ⛔ BLOCK. Otherwise the floor is open.

**Step 2 — apply remaining findings (can only raise severity, never lower the floor):**

- 🔀 **ROUTING REQUIRED** if any Routing block exists (code, contract-root, or sync-check) — the code/contract needs an owner pass before it is clean.
- ⛔ **BLOCK** if any CRITICAL remains, or any HIGH affects MVP-scope. A routed CRITICAL/HIGH still BLOCKS the merge until the owner resolves it (BLOCK and ROUTING co-display: "⛔ BLOCK — routing required").
- ✅ **PASS** only if there are zero Routing blocks AND zero unresolved CRITICAL/HIGH AND you hold no observed evidence of a defect. LOW notes (and an informational reduced-confidence note) are compatible with PASS.

Re-running unchanged green code yields consistent IDs and a stable PASS.

> **Reduced confidence never manufactures a PASS, and never manufactures a BLOCK.** STATIC modes (execution/build denied by the constitution) lower your *confidence*, surfaced as one informational MEDIUM note — they are a coverage signal, not a contract defect, and are NEVER counted as a HIGH-affecting-MVP for BLOCK purposes. Equally, reduced confidence may NOT be used to PASS over a defect you *did* observe statically. The verdict is driven by the defects you found, at the confidence the permitted evidence allowed.

### 8. Produce Gate Report — ALWAYS WRITTEN (chat + file, every run)

**Persistence rule (simple and absolute):**

- **Always** write the report to `REPORT` — every run, every verdict (✅ PASS, ⛔ BLOCK, 🔀 ROUTING REQUIRED) — overwrite, never append, stamp the header with date, verdict, scope, mode, and suite state.
- A PASS report is a *positive record* that the gate ran and the code implements the contract; it is NOT noise. The only state in which `REPORT` does not exist is **the gate never ran** — that is the whole point, and it is especially important for the terminal merge gate, where "did this code get verified?" must be answerable from an artifact.
- The header stamp, the verdict line, and the Metrics line MUST agree. Never write one verdict in the header and another in the metrics.

```markdown
<!-- code-report.md — generated by /order.code-check · {DATE} · verdict: {VERDICT} · mode: {MODE} · overwritten each run -->

## Code Verification Gate Report (code ↔ contract)

**Verdict**: ✅ PASS | ⛔ BLOCK | 🔀 ROUTING REQUIRED
**Scope**: {whole-tree | delta vs {base}} · Mode: {FULL | STATIC+TESTS | STATIC-ONLY} · Plan: {available | archived — E4 skipped} · Suite: {green N/N | red F failing | not run (constitution) | none}

{If STATIC mode: one-line "⚠ REDUCED CONFIDENCE — execution/build denied by constitution; verification is static-only and findings below carry no runtime evidence." banner here. Omit in FULL mode.}

### Routing Required (gate did NOT modify code)
(render each as the Routing block format; batched, grouped by owner: /order.code · /order.spec · /order.plan · /order.sync-check. "None" if PASS.)

### Findings
| ID | Pass | Severity | Owner | Location ↔ Obligation | Evidence |
|----|------|----------|-------|----------------------|----------|
| E0-001 | test-reality | CRITICAL | /order.code | suite | build fails: {error} |
| E1b-002 | trace | CRITICAL | /order.code | auth.login ↔ AC-007 | test `rejects expired token` fails |
| E1a-003 | trace | HIGH | /order.code | — ↔ INV-002 | no test enforces single-active-session |
| E3a-004 | §12 | HIGH | /order.code | POST /sessions ↔ §12 | returns 200, contract says 409 |
(on PASS, this table may legitimately be empty or carry only LOW notes — render it anyway)

### Obligation Coverage Matrix
| Obligation (AC/INV/§12) | Priority | Test | Result | Impl | Status |
|-------------------------|----------|------|--------|------|--------|
(render every obligation on every run, including PASS — ✅ backed+passing+real / ⚠️ weak / ❌ missing-or-failing)

### Metrics
- Capabilities: tests {expected|forbidden} · exec {allowed|denied} · build {allowed|denied}
- Obligations verified: {n} (AC {a} · INV {i} · §12 {c})
- Suite: {pass}/{total} ({fail} failing) | not run (constitution) | none · coverage of obligations: {covered}/{total}
- Findings by severity: C/H/M/L
- Routing by owner: code {n} · spec {n} · plan {n} · sync-check {n}
- Mode: {whole-tree | delta} · verification: {FULL | STATIC+TESTS | STATIC-ONLY} · Plan fidelity: {checked | skipped (archived)}
- Evidence floor applied: {none | non-PASS}
- Report file: always written to code-report.md
```

After rendering, state in one line the `REPORT` path where the file was written (always).

### 9. Next Actions

The gate detects and routes; it never edited code, and it always wrote the report:
- **Code defect** → run the routed `/order.code "..."`, then re-run `/order.code-check`.
- **Contract-root** (ambiguous/contradictory obligation) → run `/order.spec`/`/order.plan` to tighten the contract, then re-run.
- **Artifact desync** → run `/order.sync-check` first; once artifacts agree, re-run `code-check` against the stable target.
- **Missing tests** → `/order.code` (or `/order.tasks` if the test task itself was never specified) — methodology is test-first; the test is part of the deliverable, where the constitution expects it.
- **Reduced confidence (STATIC modes)** → if stronger assurance is needed, the constitution must grant `TEST_EXEC_OK`/`BUILD_OK`; re-run in FULL mode to obtain runtime evidence.

Recommended loop: resolve routed findings via the named owner, re-run the suite, re-run `/order.code-check`. Idempotent: code that implements the contract with a green, AC-covering suite (or a clean static trace where execution is denied) yields ✅ PASS and writes a clean PASS report — ready to merge.

## Post-Execution Checks

Run the **`after_code_check`** phase per `.orderspec/memory/hooks-protocol.md`.

## Operating Principles

- **The only code-reading gate — and it still never writes code.** Zero auto-fix: code edits are never the unambiguous, reversible, meaning-preserving corrections that text gates' mechanical exception requires. Everything is Route.
- **Objective evidence is ground truth (Invariant 1)**: a red test or build break is a fact, imported at its severity, never called a "false positive", never silenced or rewritten to pass. A wrong test is a Route to `/order.code`, not grounds to ignore the failure.
- **Governance floors the method; evidence floors the verdict (Invariant 2)**: execution/build run ONLY when the constitution permits (silence = deny); an observed CRITICAL/MVP defect can never be a PASS.
- **Always write the report**: every run, every verdict, including PASS. "No file" means "the gate did not run" — never "the code is verified". For the terminal merge gate this is the record that the code was checked.
- **Mandatory output structures**: the Findings table and Obligation Coverage Matrix appear on every run, including PASS.
- **Tests are the oracle WHERE permitted.** In FULL mode prefer objective test evidence; in static modes the oracle is direct code↔obligation tracing. Test-first is a constitution-default, not an axiom: where tests are forbidden, their absence is correct and their presence is a finding.
- **Suspect the code, but find the real root.** Default route is `/order.code`; escape upstream to `/order.spec`/`/order.plan` when the contract is the actual problem, and to `/order.sync-check` when the artifacts disagree.
- **Read + (permitted) execute only.** Running the suite read-only is evidence-gathering, not modification. Never silence a failing test, never patch a stub.
- **Code ↔ contract, not artifact ↔ artifact.** That second axis is `sync-check`; this gate verifies the implementation against an assumed-consistent contract.
- **Degrade, don't abort.** No plan → spec-only with a note. No suite → static spot-check with a HIGH finding. Build break → focused CRITICAL. Capability denied → static mode with a reduced-confidence note.
- **NEVER hallucinate behavior** — base findings on quoted code, named tests, and cited obligation IDs.
- Minimal high-signal tokens: cite file:line, test name, and obligation ID; cap at 30 findings; aggregate overflow.
- Constitution violations and INV breaches are always CRITICAL — routed, BLOCK.

## Context

$ARGUMENTS
