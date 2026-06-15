---
description: Per-stage passive-active gate validating spec.md for coverage and internal integrity. The root of the cascade — no repo, no plan, no time. A pure inspector for content: it detects defects, missing high-impact topics, and oversized scope, but NEVER authors contract content; it auto-fixes only strictly mechanical / meaning-preserving defects and routes everything contractual (including decomposition) to /order.spec. It ALWAYS writes a report file (every run, every verdict) so that "no file" unambiguously means "the gate did not run". LLM context spent on coverage-taxonomy sweep, testability, consistency, glossary discipline, AC form, journey coverage, and scope sizing.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Role In The Pipeline

This is a **per-stage gate** for one document: `spec.md`. It runs after `/order.spec` and answers a single question:

> **Is spec.md a complete, internally consistent, testable contract — independent of how it will be built?**

It is the **root of the cascade**: there is no upstream artifact. A defect here originates either in the spec text or in the user's intent.

**Division of responsibility (read this first):**

- **Authoring contract content is owned by `/order.spec`**, not by this gate. If the user wants to add, change, or fill in spec content, they invoke `/order.spec "<what they want>"`. That command owns the elicitation taxonomy, ID-routing, and write discipline.
- **This gate is a pure inspector.** It verifies the contract and may perform only **mechanical / meaning-preserving** auto-fixes (glossary spelling, numbering, broken internal references, format). Anything that would **change requirement meaning, scope, thresholds, or fill a missing topic** is NOT done here — it is surfaced as a **Routing block** telling the user exactly which `/order.spec` call will resolve it.

So the gate has two content channels only:

1. **Auto-Fixed** — mechanical defects it silently corrected in place.
2. **Routing Required** — contractual findings it cannot touch, each with a ready-to-run `/order.spec` invocation.

Plus one **persistence behaviour**: the gate **always** writes its report to a file (see §6), on every run and every verdict. A missing report file therefore unambiguously means the gate did not run.

It is the **narrowest** gate in context: it reads only `spec.md` and the constitution (the latter only for direct goal-vs-principle conflicts). It does **not** read the repository, **not** read plan.md, and **not** reason about time or implementation. `/order.spec` no longer produces a self-grading checklist, so there is no author checklist to cross-check.

Boundaries:

- spec self-consistency, glossary, AC form, testability, no-physical-detail purity, **detection of missing high-impact topics, and detection of oversized scope** → **this gate** (detect only).
- authoring/filling spec content, elicitation, ID-routing, **and decomposition (`--split`)** → `/order.spec`.
- plan↔spec completeness, mechanism adequacy, stack → `plan-check`.
- tasks ordering / coverage-by-task → `tasks-check`.
- repo state, drift, whole-system constitution sweep, cross-artifact contradictions → `/order.analyze`.
- mechanical ID inventory, dangling internal references, numbering → the script.

## The Two Non-Negotiable Invariants (read before anything else)

These two rules override every other consideration in this gate. They exist because the last failure mode was the gate using its own semantic judgement to overrule the deterministic script and emit a false PASS. That must never happen.

1. **The mechanical script is ground truth; you may never overrule it.** Every entry in the script's `findings[]` array is a *deterministic fact* produced by grep/awk over literal text — not a judgement. You MUST import each spec-internal finding at its stated severity. You MAY choose its disposition (Auto-fix vs Route) and add context. You MUST NOT downgrade, suppress, or call a mechanical finding a "false positive" on semantic grounds. "The requirement is covered in spirit / via an AC" does NOT cancel an M1 finding — M1 checks whether the literal ID appears in a UJ `Covers` field, a *traceability fact* orthogonal to whether behaviour is tested. If you genuinely believe the script's PATTERN is wrong, that is a bug in the SCRIPT (report it as **S0-002**, MEDIUM); it is NEVER grounds to overrule the result and pass.

2. **The script exit code is a hard floor on the verdict.** Read it FIRST, before forming any opinion:
   - exit **1** → ≥1 mechanical CRITICAL/HIGH exists → the verdict **cannot be ✅ PASS**. Floor is 🔀 ROUTING REQUIRED (⛔ BLOCK if any is MVP-affecting).
   - exit **3** → clean but partial scope (downstream artifacts absent) → does NOT by itself force non-PASS.
   - exit **0** → clean, full scope.
   - exit **2** → required `spec.md` missing → abort.
   You may make the verdict MORE severe than the floor (semantic findings can push exit-0 to ROUTING); you may NEVER make it less. If you are about to write PASS while the script returned 1, you have made an error — stop and reconcile.

## When to Run

Conditional. Recommended after every `/order.spec` run (including refinement runs), especially when:

- spec.md was generated or heavily edited by a **weaker model**.
- The feature is large or safety-relevant and a malformed/under-specified contract would be expensive downstream.
- The spec carries unresolved `[NEEDS CLARIFICATION]` markers or open `Q-NNN` items.
- You want a clean, fully-covered root before `/order.plan` consumes it.

Can be wired as an automatic post-spec hook (`hooks.after_spec`) for weaker-model workflows.

## Pre-Execution Checks

Run the **`before_spec_check`** phase per `.orderspec/memory/hooks-protocol.md`.

## Goal

Act as an **independent inspector with fresh context** over `spec.md`. You did not write it. Determine whether spec.md is a **sound, complete contract**:

- **Coverage**: no high-impact topic is missing; explicit `[NEEDS CLARIFICATION]` markers and open `Q-NNN` are flagged for resolution.
- **Testability**: every REQ is verifiable; every AC is in checkable form (Given/When/Then), with measurable thresholds where behavior is quantitative.
- **Consistency**: no REQ contradicts another REQ, an INV, or a CON; no absolute-quantifier INV is contradicted by a weakening NFR or ASM.
- **Glossary discipline**: terms defined once, used consistently; no synonym drift.
- **Journey completeness**: each user-journey step (§14/§15) is backed by requirements; named EDGE cases have defined behavior.
- **Purity**: spec states *what/why*, not *how* — no paths, libraries, schemas, signatures.
- **Scope clarity**: in/out-of-scope explicit; SC are outcomes, not tasks.
- **Scope sizing**: the contract is cohesive enough to live as one spec; an oversized contract (many independent domains/actors) is flagged for guided decomposition — detect only, never split here.

Fix only strictly mechanical / meaning-preserving defects. Route everything contractual to `/order.spec`.

## Out of Scope (do NOT do here)

- **Authoring or filling spec content** — adding REQ/NFR/CON/INV/EDGE/AC, defining terms, setting thresholds, resolving `[NEEDS CLARIFICATION]` by writing an answer. All of this is `/order.spec`'s job; the gate only routes to it.
- **Performing the decomposition** — splitting an oversized spec into sub-specs is a content/authoring action owned by `/order.spec --split`; the gate only detects oversized scope and routes.
- **Overruling the mechanical script** — see the Two Non-Negotiable Invariants above.
- How the spec will be implemented — mechanisms, stack, paths → `plan-check` / `/order.plan`.
- Topics that are genuinely planning-time decisions (which library, which deployment, code structure) → tag the finding **"defer-to-plan"** (do NOT route to spec; it carries forward as a known planning decision).
- Whether tasks cover the spec → `tasks-check`.
- Repository state, drift, whole-system constitution sweep, cross-artifact contradictions → `/order.analyze`.
- Mechanical ID counting, internal dangling-reference detection, numbering → the script.

## Operating Constraints

- **INSPECTOR + MECHANIC**: you MAY modify `spec.md` ONLY for mechanical / meaning-preserving auto-fixes. You MUST NOT author, fill, or alter the meaning of any contract content.
- **Auto-fix vs Route boundary** (the single permission to write spec content, kept deliberately tight):
  - **Auto-fix** ONLY when ALL hold: (a) the defect is mechanical or strictly meaning-preserving, (b) exactly one valid correction exists, (c) it does NOT change the meaning, threshold, or scope of any requirement, and (d) it is obvious/reversible. Examples: a term not matching the glossary's defined spelling, a broken internal ID cross-reference, duplicate phrasing of the same requirement, AC reformatted into Given/When/Then **without** altering its conditions/thresholds, section/ID numbering. Apply in place, record in **Auto-Fixed**.
  - **Route** for **everything else** — anything touching requirement meaning, threshold, scope, term definition, EDGE behavior, or a missing topic. Emit a **Routing block** naming the defect and the exact `/order.spec` call that will resolve it. The gate does NOT write the resolution and does NOT wait to apply one.
  - **When in doubt, Route — never Auto-fix.** The write permission is the narrow exception, not the norm.
- **The report file is separate from the spec.** Writing `spec-report.md` (see §6) is a gate artifact, not a spec edit; it never counts as authoring contract content. It is written on every run regardless of verdict.
- **No Ask-and-apply, no Decision-blocks-that-mutate**: the gate never asks the user a question whose answer it then writes into the spec. Content decisions are made by the user *through* `/order.spec`. The gate's job ends at producing precise Routing blocks (and persisting them to the report file).
- **Constitution authority**: a spec *goal* directly conflicting with a `.orderspec/memory/constitution.md` MUST principle is CRITICAL → Route (the principle is fixed; reconciling the goal is a content change owned by spec). The full whole-system constitution sweep remains `/order.analyze`'s job.
- **No duplication of mechanical work**: trust the script's inventory/dangling/numbering findings; do not re-count, do not re-derive, do not second-guess.
- **Root stance**: never read repo, plan, or reason about time; if a concern needs any of those, it is out of scope for this gate.

## Routing Block Format

When a contractual finding cannot be auto-fixed, emit exactly this; **batch all routing blocks together** at the end, do not interleave one-by-one:

```text
### Routing Required: {short title}

**Finding**: {what is wrong or missing}
**Location**: {spec ID / §section / "Missing: {taxonomy category}"}
**Why owner, not gate**: {changes meaning/threshold/scope OR fills a missing topic — must go through the spec's author}
**Impact if unresolved**: {what breaks downstream — plan/tasks inherit the ambiguity or gap}
**Suggested direction**: {1–2 candidate resolutions the author may consider; advisory only}
**Run**: `/order.spec "{ready-to-run refinement request capturing the finding}"`
```

The `Run` line is a concrete, copy-pasteable instruction to the artifact's owner. It is a recommendation, not an action the gate performs.

## Execution Steps

### 1. Initialize

Run `.orderspec/scripts/bash/check-prerequisites.sh --json --paths-only` once from repo root; parse FEATURE_DIR and FEATURE_SPEC. Derive: SPEC = FEATURE_SPEC; REPORT = `FEATURE_DIR/checklists/spec-report.md`. plan.md and tasks.md may be absent and are NOT read by this gate. If EXISTS, load `.orderspec/memory/constitution.md` for governance constraints. Abort with instructions (re-run `/order.spec`) if SPEC is missing. For single quotes in args use `'I'\''m Groot'` or double quotes.

### 2. Mechanical Validation (script — GROUND TRUTH)

Run, scoping the script to this gate's stage so absent downstream artifacts are NOT treated as failure:

```bash
.orderspec/scripts/bash/validate-traceability.sh --json --stage spec "$FEATURE_DIR"
```

> **Where to read the exit code:** the script embeds it in the JSON as
> `summary.exit_code` (and also returns it as the process exit status). Read
> `summary.exit_code` — it is always present in the output you were given, even
> if the shell's `$?` was not forwarded to you. Do NOT infer the exit code by
> eyeballing `findings[]`, and NEVER open the script's source to "verify" the
> code — the JSON is authoritative. If `summary.high > 0` or
> `summary.critical > 0`, `exit_code` will be 1; trust the field, do not
> second-guess it.

**Read the exit code FIRST and apply it as the verdict floor** (see Invariant 2):

- **0** — clean, full spec-stage scope. Normal.
- **3** — clean, but some checks were skipped because `plan.md`/`tasks.md` are absent. **This is the EXPECTED state at the root of the cascade and is NOT degraded mode.** The `skipped` array lists what was deferred (M2/M3/M8/M14 etc., all downstream concerns this gate does not own). Proceed normally; do NOT emit S0-001; this does NOT make spec-stage scope "partial".
- **1** — ≥1 CRITICAL/HIGH mechanical finding present. **Verdict floor is now non-PASS.** Import the spec-internal findings (M1, M5 plan/tasks side as applicable, M6, M7, M14) at their stated severities; choose a disposition (most are Auto-fix; M1 Covers-gaps are Route — adding an ID to a `Covers` field is contractual).
- **2** — `spec.md` itself is missing → abort, instruct the user to run `/order.spec`.

Import **only spec-internal** findings (ID inventory, internal dangling refs, numbering/format within spec). Ignore any plan/tasks/repo/timestamp findings — not this gate's concern.

**You may NOT overrule any imported finding (Invariant 1).** A mechanical finding is a deterministic fact, never a "false positive" you can dismiss. If you believe the script's pattern itself is faulty, record it as **S0-002 (MEDIUM)** and STILL import the finding — do not suppress it.

**Genuine degraded mode (S0-001) is narrow.** Emit HIGH **S0-001** ("mechanical validator unavailable — degraded mode") ONLY if the script is missing, crashes, or returns unparseable output (a real tooling failure). **Exit code 3 is NOT degraded mode.** In a true degraded case, manually spot-check only: ID blocks present and uniquely numbered; internal references resolve. Keep it brief. S0-001 is surfaced in the report but does NOT by itself drive the contract verdict (see §5).

### 3. Detection Passes (LLM — coverage + integrity, DETECT ONLY)

**These semantic passes are MANDATORY on every run and run INDEPENDENTLY of the mechanical result.** A clean (or seemingly clean) script result NEVER lets you skip them — the script covers only ~14 literal-text facts; the semantic contract (status-code coherence, undefined roles, missing auth ACs, what/why purity, journey backing) is yours alone to assess and is the primary value of this gate. The full Findings table, Coverage Taxonomy, Contradiction Grid, and Journey Coverage Matrix MUST appear in the output on every run, including PASS.

Load the spec. Build a minimal internal model — do not dump the raw artifact into output. Limit to 30 findings total (including imported M-findings); on overflow, drop LOW first and aggregate into one summary line — never drop a CRITICAL. Use stable IDs prefixed by pass (C0-001, C1-001...). For each finding, classify disposition as **Auto-fix**, **Route**, or **defer-to-plan**. Remember: detection only — the gate never writes contract content in these passes.

Process passes in order; **`C0` first**, because "what is missing entirely" logically precedes "what is written wrong".

#### C0. Coverage Taxonomy Sweep (detect missing high-impact topics)

First flag **explicit incompleteness markers (P0)** — always, before anything else:

- Every inline `[NEEDS CLARIFICATION: ...]` marker → Route.
- Every unresolved `Q-NNN` in §16 Open Questions → Route.
- Any risky `ASM-NNN` default in §17 whose wrongness would change behavior → Route (confirm or revise via spec).

Then walk this **section-mapped taxonomy**; mark each row Clear / Partial / Missing against the current spec:

| Category | Spec § | What to check |
|----------|--------|---------------|
| Scope & success | §2 | Objectives concrete; Out-of-Scope explicit; each SC measurable & tech-agnostic |
| Functional requirements | §4 | Each REQ a testable MUST/MUST NOT; actor/object/outcome present |
| Quality attributes | §5 | Vague adjectives ("fast","secure","robust") quantified as NFR metrics |
| External constraints | §6 | Mandated tech/platform/compliance captured as CON |
| Architecture & behaviour | §7–§10 | External systems & failure modes present; error paths covered, not just happy path |
| Data & contracts | §11–§12 | Entities, identity/uniqueness, relationships, lifecycle sufficient; contracts unambiguous |
| Invariants | §13 | INV deterministic, always-true consistency rules; contradiction grid present when applicable |
| Edge cases | §14 | Negative flows, concurrency conflicts, limits/throttling covered as EDGE |
| Acceptance | §15 | Every AC testable G/W/T; Covers complete; each UJ independently testable; P1 = viable MVP |
| Terminology | §3 | Canonical terms defined; no synonym drift |
| Open items | §16–§17 | No stale TODO/placeholders; risky ASM defaults confirmed |

For each **Partial/Missing** category, decide via the **Impact × Uncertainty** heuristic:

- **Route** to `/order.spec` ONLY if the gap would materially change requirements, data model, invariants, acceptance tests, UX behavior, operational readiness, or compliance — AND is not better deferred to planning. ASMs that define externally observable API semantics (idempotency of mutations, status codes for state conflicts, pagination presence/absence) are high-impact regardless of the map.
- **Feasibility-vs-infrastructure gaps**: when a REQ/NFR/INV demands a property whose feasibility depends on infrastructure not guaranteed by any CON (e.g. an NFR requiring **atomic / transactional** multi-entity writes, which need DB transactions / a replica set), emit a **defer-to-plan** finding naming the dependency explicitly: the plan MUST confirm the environment supports it, else the requirement must be re-negotiated. Trigger this on words like *atomic, transactional, exactly-once, strongly-consistent* applied across multiple entities.
- A gap better resolved at planning time → MEDIUM finding tagged **"defer-to-plan"**; do NOT route to spec.
- A low-impact gap → LOW finding, no routing.

A Missing high-impact category is **never filled by the gate** — that would author contract content. Aggregate a cluster of related gaps into one Routing block where natural; respect the 30-finding cap. Glossary/terminology gaps surfaced here feed `C3`.

#### C1. Testability

- C1a: Each REQ is **verifiable** — a tester could devise a pass/fail check. Unobservable/unmeasurable → **Route** (spec must add the observable criterion/threshold).
- C1b: Quantitative behavior ("fast","shortly") has a **measurable threshold**. Vague adjective without a number → **Route** (spec must set the contract value — the gate never picks a number).
- C1c: Each AC is in **checkable form** (G/W/T). Pure reformatting preserving conditions → **Auto-fix**; if it would require inventing a missing condition/threshold → **Route**.

#### C2. Consistency

- C2a: No two REQs contradict; no REQ contradicts an INV or CON. Genuine contradiction → **Route** (spec must decide which governs; the gate never silently deletes one).
- C2b: AC do not contradict their parent REQ. An AC asserting forbidden behavior → **Route**.
- C2c: **Absolute-vs-weakening contradiction grid.** For each INV with an absolute quantifier (exactly / always / every / never / must produce), enumerate every **NFR and every ASM** carrying a weakening qualifier (best-effort / may fail / non-blocking / eventually / excludes / optional). You MUST scan BOTH sources — NFRs and ASMs — not NFRs alone; a weakening ASM is the most common place a contradiction hides. Emit one verdict line per pair: `INV-NNN × {NFR|ASM}-NNN → compatible | CONFLICT`. Any CONFLICT → **Route** (the spec must decide which governs; the gate never rewrites the INV). If the spec already contains a §13 grid, re-derive it independently and flag any pair the author **omitted** (especially missing ASM pairings) as a finding. This grid is mandatory gate output whenever ≥1 absolute INV and ≥1 weakening NFR/ASM coexist.
- C2d: **Narrowing-ASM vs REQ check.** For each ASM that narrows a REQ's field set / scope / behavior, verify the narrowed form satisfies the REQ for every action the REQ covers. If the narrowing defeats the REQ for any case → **Route** (the ASM is a laundered scope cut; fixing it is contractual).
- C2e: **Status-code coherence (§12 is normative).** Every HTTP status code named in §14 EDGE, §15 AC, or a sequence diagram MUST be declared for that endpoint in §12. A code appearing in EDGE/AC/diagram but absent from the §12 contract (e.g. EDGE introduces 500 while §12 lists only 4xx) → **Route** (the contract must add the code or the EDGE must align). The gate never picks which side is right — that is contractual.

#### C3. Glossary Discipline

- C3a: Terms used as defined concepts appear in §3 Glossary. Undefined-but-used term → **Route** (defining a term is contractual).
- C3b: Synonym drift — same concept, varying terms. Where one is canonical and variants are unambiguous synonyms → **Auto-fix** (normalize to canonical; one-time `(formerly "X")` allowed). Where it is unclear two terms mean the same → **Route**.

#### C4. Journey Completeness

- C4a: Each user-journey step (§14/§15) is backed by ≥1 REQ/AC. Unbacked step → **Route** (spec must add the backing requirement).
- C4b: Each named EDGE case has **defined expected behavior**. Listed without resolution → **Route** (spec must define the behavior).
- C4c: Each INV and CON is unambiguous enough to honor downstream. Vague invariant → **Route**.

#### C5. Purity (what/why, not how)

- C5a: spec contains no **physical/implementation detail** — paths, library/framework names, schema definitions, API signatures, deployment specifics. Leaked detail → **Route** with two candidate directions in *Suggested direction*: (i) remove it (belongs in plan), or (ii) it is a genuine mandated constraint → restate as a `CON-NNN`. The gate does not auto-strip — that judgment (remove vs promote to CON) is contractual.

#### C6. Scope Clarity

- C6a: In-scope / out-of-scope explicit and non-overlapping. Scope ambiguity → **Route**.
- C6b: Each SC is an **outcome**, not a task ("users complete checkout in <3 steps", not "add a checkout button"). SC-as-task → **Route** (spec must rephrase to the intended outcome).

#### C7. Direct Constitution Conflicts (narrow)

- C7a: Flag only a **direct** spec-goal-vs-constitution conflict you encounter. Any conflict is CRITICAL → **Route** (the principle is fixed; reconciling the goal is a content change owned by spec). Do NOT perform the full constitution sweep — that is `/order.analyze`.

#### C8. Scope Sizing (detect oversized contract — route to decomposition)

The contract should be **cohesive enough to plan and build as one unit**. A spec spanning many independent domains is expensive to plan, hard for a weaker model to keep consistent, and tends to hide cross-domain contradictions. Detect oversize; **never split here** — decomposition authors new artifacts and is owned by `/order.spec --split`.

- C8a: Estimate breadth from the current spec: distinct functional domains, independent primary actor sets with non-overlapping journeys, REQ volume, and the number of viable P1-MVP threads.
  - **Oversized heuristic** (any two firing): ≳ 25–30 REQ; ≳ 3 independent functional domains that could ship/test separately; ≳ 3 distinct primary actor sets with non-overlapping journeys; > 2 UJs that each look like a standalone P1-MVP rather than one end-to-end thread.
  - **Oversized** → **Route** to `/order.spec --split`. In *Suggested direction*, list the natural module boundaries you observed (advisory only — the gate proposes seams, the author decides and decomposes). Severity MEDIUM (HIGH only if the breadth already produced a cross-domain contradiction you flagged under C2).
  - **Cohesive-but-dense** (one domain, many REQ, single MVP thread) → NOT a finding. Density alone is never oversized; do not route. At most a LOW note.
- This pass fires at most **one** Routing block (the split recommendation); do not emit per-domain routes — decomposition is a single authoring decision.

### 4. Severity Assignment

- **CRITICAL**: a P1-journey step (§14/§15) has no backing requirement; two requirements directly contradict on MVP behavior; an absolute-quantifier INV is in genuine CONFLICT with a weakening NFR/ASM on MVP behavior; a spec goal violates a constitution MUST; an unresolved P0 marker blocking MVP correctness.
- **HIGH**: an untestable/unmeasurable MVP requirement; a P1 EDGE with no defined behavior; an AC contradicting its REQ; a Missing high-impact taxonomy category affecting MVP; an absolute INV × weakening ASM/NFR pair the author omitted from the §13 grid that turns out to be a CONFLICT; **every imported mechanical HIGH (e.g. M1 Covers-gap) — these keep the script's severity, never downgraded.**
- **MEDIUM**: undefined glossary term; non-MVP EDGE undefined; leaked physical detail (purity); SC phrased as a task; synonym drift requiring routing; **defer-to-plan** gaps; **oversized scope recommending decomposition (C8)**; an omitted grid pair that resolves compatible (grid incompleteness without a live conflict); **S0-002 (suspected script-pattern bug — note only, the finding is still imported)**.
- **LOW**: cosmetic glossary/numbering (usually auto-fixed); meaning-preserving AC reformatting; verbose phrasing; low-impact coverage gaps.

**MVP-scope definition**: "MVP-scope" = requirements/steps tied to the P1 (highest) priority in the user journey (§14/§15). A HIGH finding on MVP-scope blocks; the same class on non-MVP does not auto-block.

### 5. Determine Verdict

**Step 1 — apply the exit-code floor (Invariant 2):** if the script returned exit 1, the verdict is already non-PASS; you may only decide between 🔀 ROUTING REQUIRED and ⛔ BLOCK. If exit 0 or 3, the floor is open and the verdict is decided by the C-pass findings below.

**Step 2 — apply semantic findings (can only raise severity, never lower the floor):**

- 🔀 **ROUTING REQUIRED** if any Routing block exists (mechanical or semantic) — the spec needs an author pass via `/order.spec` before it is clean.
- ⛔ **BLOCK** if any CRITICAL remains, or any HIGH affects MVP-scope. A routed CRITICAL/HIGH still BLOCKS the pipeline until the owner resolves it (BLOCK and ROUTING co-display: "⛔ BLOCK — routing required").
- ✅ **PASS** only if there are zero Routing blocks AND zero unresolved CRITICAL/HIGH AND the script did NOT return exit 1. Auto-fixes applied and LOW notes are compatible with PASS.

Rerunning a clean spec.md must produce consistent IDs, counts, and verdict.

> **What "HIGH affects MVP-scope" means for BLOCK (be precise):** a HIGH blocks
> ONLY if the defect makes the P1/MVP behaviour itself incorrect, untestable, or
> unbuildable — e.g. an untestable MVP requirement, a P1 EDGE with no defined
> behaviour, an AC contradicting its REQ on MVP behaviour. A finding that touches
> an MVP requirement but does NOT break its correctness is NOT MVP-blocking.
> In particular: an **M1 Covers-gap is a traceability defect, never MVP-blocking
> on its own** — the behaviour is typically already backed by a journey step +
> AC (check the Journey Matrix); only the `Covers` list omits the ID. Route it
> (HIGH), but it yields 🔀 ROUTING REQUIRED, not ⛔ BLOCK, unless some OTHER
> CRITICAL/MVP-breaking finding coexists. Rule of thumb: BLOCK needs a defect
> that breaks MVP correctness; ROUTING needs a defect that needs the author but
> doesn't break MVP. When the only HIGHs are traceability/Covers gaps and there
> is no CRITICAL → verdict is 🔀 ROUTING REQUIRED.

> **Infrastructure signals never drive the contract verdict.** S0-001 (validator
> unavailable) and exit-code-3 "partial scope" are *tooling/coverage* signals,
> not contract defects. They are NEVER counted as a HIGH-affecting-MVP for BLOCK
> purposes. If the only non-LOW finding is S0-001, the verdict is decided purely
> by the C-pass findings (✅ PASS if none). Surface S0-001 (when genuinely
> present) as a one-line degraded-mode banner in the report so the user knows
> coverage was reduced — that is all it does. **Note the distinction from
> Invariant 2: exit 1 (real findings) IS a floor; exit 3 (absent downstream) is
> not.**

### 6. Produce Gate Report — ALWAYS WRITTEN (chat + file, every run)

**Persistence rule (simple and absolute):**

- **Always** write the report to `REPORT` — every run, every verdict (✅ PASS, ⛔ BLOCK, 🔀 ROUTING REQUIRED) — overwrite, never append, stamp the header with date and verdict.
- A PASS report is a *positive record* that the gate ran and the spec is clean; it is NOT noise. The only state in which `REPORT` does not exist is **the gate never ran** — that is the whole point.
- The header stamp, the verdict line, and the Metrics line MUST agree. Never write one verdict in the header and another in the metrics.

Report body (merge mechanical `M*` and semantic `C*` findings):

```markdown
<!-- spec-report.md — generated by /order.spec-check · {DATE} · verdict: {VERDICT} · overwritten each run -->

## Spec Gate Report (spec.md — coverage + internal integrity)

**Verdict**: ✅ PASS | ⛔ BLOCK | 🔀 ROUTING REQUIRED

{If S0-001 present: one-line "⚠ DEGRADED — mechanical validator did not run (S0-001); the M1–M14 layer was skipped and findings below are LLM-only." banner here. Omit entirely otherwise.}

### Auto-Fixed (applied automatically — mechanical / meaning-preserving only)
| ID | What was changed in spec.md | Why meaning-preserving |
|----|-----------------------------|------------------------|
(empty if none)

### Routing Required (owned by /order.spec — gate did NOT modify content)
(render each as the Routing block format; batched. "None" if PASS.)

### Findings
| ID | Source | Severity | Disposition | Location | Summary |
|----|--------|----------|-------------|----------|---------|
| M1-001 | mechanical | HIGH | Route | spec.md | REQ-003 not in any UJ 'Covers' — traceability gap |
| C0-001 | semantic | HIGH | Route | Missing: Non-functional/security | No NFR for auth rate-limiting |
| C4a-002 | semantic | CRITICAL | Route | §15 UJ1 step 3 | Journey step has no backing requirement |
| C3b-004 | semantic | MEDIUM | Auto-fixed | REQ-005, REQ-011 | "member"/"user" normalized to glossary "user" |
(on PASS, this table may legitimately be empty or carry only LOW notes — render it anyway)

### Coverage Taxonomy (C0)
| Category | §  | Status | Disposition |
|----------|----|--------|-------------|
(render every taxonomy row: Clear / Partial / Missing → Route / defer-to-plan / LOW / — — on every run, including PASS)

### Contradiction Grid (C2c / C2d)
| Pair | Verdict | Reason |
|------|---------|--------|
| INV-004 × NFR-003 | compatible | INV governs intent; NFR governs failure handling |
| INV-004 × ASM-011 | CONFLICT | ASM makes audit best-effort; INV demands exactly one — author omitted this pair |
(render every absolute-INV × weakening-NFR/ASM pair, scanning BOTH NFR and ASM sources; '—' if none qualify)

### Journey Coverage Matrix
(render: Journey step (§14/§15) | Backing REQ/AC | Status — on every run, including PASS)

### Metrics
- Scope sizing: {cohesive | oversized → split recommended} (from C8)
- Inventory (from script): REQ / AC / EDGE / INV / UJ — these come from the script's `inventory` object, use verbatim.
- Inventory (LLM-counted from spec text): NFR / CON / SC / ASM — the script does NOT count these; count them yourself from the spec and they MUST agree with what your C2c grid scanned. If you report ASM=N here, your Contradiction Grid MUST reflect those N ASMs (or explicitly state each is non-weakening).
- Findings by severity: C/H/M/L counts (script + semantic)
- Auto-fixed: N · Routing required: M · defer-to-plan: K
- P0 markers: {n} [NEEDS CLARIFICATION] · {n} open Q-NNN (all routed)
- Grid: {p} pairs checked (NFR+ASM) · {c} conflicts · {o} author-omitted pairs detected
- Script exit code: {0 | 1 | 3} · verdict floor applied: {none | non-PASS}
- Mechanical scope: {full, no findings (exit 0) | full, findings present (exit 1) | full, downstream deferred (exit 3 — expected at spec root) | DEGRADED — validator did not run (S0-001), M1–M14 skipped}
- Report file: always written to checklists/spec-report.md
```

After rendering, state in one line the `REPORT` path where the file was written (always).

### 7. Next Actions

The gate's responsibilities end at detection, mechanical repair, routing, and writing the report file. For each finding:

- **Mechanical / meaning-preserving** → already auto-fixed (see Auto-Fixed); no user action.
- **Contractual (meaning / threshold / scope / missing topic)** → see the Routing block; the user resolves it by running the suggested `/order.spec "..."`. The gate did not and will not write this content.
- **defer-to-plan** → noted, not routed to spec; it carries forward as a known planning decision for `/order.plan`.
- **Oversized scope (C8)** → see the Routing block; the user decomposes via `/order.spec --split`. The gate never splits.
- **S0-001 (degraded)** → the validator failed to run; fix the tooling and re-run so the mechanical layer is restored. **S0-002** → suspected script-pattern bug; report to the maintainer, but the imported finding still stands.

Recommended loop: run the routed `/order.spec` calls (batch the requests if convenient), then **re-run `/order.spec-check`** to confirm the contract is now clean. The gate is idempotent: a spec with no contractual findings yields ✅ PASS and writes a clean PASS report.

Downstream note: if plan/tasks already exist and a routed spec change lands, they may need `/order.plan` / `/order.tasks` regeneration — but that is observed by `plan-check` / `tasks-check` / `/order.analyze`, not acted on here.

## Post-Execution Checks

Run the **`after_spec_check`** phase per `.orderspec/memory/hooks-protocol.md`.

## Operating Principles

- **The script is ground truth (Invariant 1)**: mechanical findings are deterministic facts, imported at their severity, never overruled, never called "false positives". A suspected bad pattern is S0-002 — the finding still stands.
- **Exit code is the verdict floor (Invariant 2)**: exit 1 → cannot PASS. Semantic findings raise severity, never lower it.
- **Always write the report**: every run, every verdict, including PASS. "No file" means "the gate did not run" — never "the spec is clean".
- **Semantic passes are mandatory and independent**: a clean script result never lets you skip C0–C8. The full Findings table, Taxonomy, Grid, and Journey Matrix appear on every run.
- **Detect oversize, never decompose**: C8 flags a contract too broad and routes to `/order.spec --split`; density alone is never a defect.
- **Pure inspector for content**: the gate detects and routes; it NEVER authors, fills, or alters contract meaning.
- **One narrow write permission on the spec**: auto-fix applies ONLY to mechanical / strictly meaning-preserving defects with a single obvious correction. When in doubt, Route — never Auto-fix.
- **Route, don't ask-and-apply**: contractual findings become Routing blocks with a ready-to-run `/order.spec "..."`.
- **Scan BOTH NFR and ASM for weakening qualifiers**: the contradiction grid (C2c) is incomplete unless every absolute INV is paired against both sources.
- **Detect missing topics, but never fill them**: the C0 taxonomy sweep finds gaps and routes them.
- **Root stance**: the only "upstream" is the user (through spec). Planning-time gaps are tagged "defer-to-plan". Never read repo, plan, or reason about time.
- **NEVER hallucinate missing sections** — report absences accurately.
- Mechanics belong to the script; **only contract coverage + integrity detection belong to your LLM tokens**.
- Minimal high-signal tokens: cite specific spec IDs, cap at 30 findings, aggregate overflow.
- An unbacked P1-journey step is always CRITICAL; a spec goal violating a constitution MUST is always CRITICAL — both routed, both BLOCK.

## Context

$ARGUMENTS
