---
description: Per-stage passive-active gate validating spec.md for coverage and internal integrity. The root of the cascade — no repo, no plan, no time. A pure inspector for content: it detects defects, missing high-impact topics, and oversized scope, but NEVER authors contract content; it auto-fixes only strictly mechanical / meaning-preserving defects and routes everything contractual (including decomposition) to /order.spec. LLM context spent on coverage-taxonomy sweep, testability, consistency, glossary discipline, AC form, journey coverage, and scope sizing.
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

So the gate has two output channels only:
1. **Auto-Fixed** — mechanical defects it silently corrected in place.
2. **Routing Required** — contractual findings it cannot touch, each with a ready-to-run `/order.spec` invocation.

It is the **narrowest** gate in context: it reads only `spec.md`, the `requirements.md` checklist if present (read-only), and the constitution (only for direct goal-vs-principle conflicts). It does **not** read the repository, **not** read plan.md, and **not** reason about time or implementation.

Boundaries:
- spec self-consistency, glossary, AC form, testability, no-physical-detail purity, **detection of missing high-impact topics, and detection of oversized scope** → **this gate** (detect only).
- authoring/filling spec content, elicitation, ID-routing, **and decomposition (`--split`)** → `/order.spec`.
- plan↔spec completeness, mechanism adequacy, stack → `plan-check`.
- tasks ordering / coverage-by-task → `tasks-check`.
- repo state, drift, whole-system constitution sweep, cross-artifact contradictions → `/order.analyze`.
- mechanical ID inventory, dangling internal references, numbering → the script.

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

Act as an **independent inspector with fresh context** over `spec.md`. You did not write it — ignore any self-reported checklist inside it. Determine whether spec.md is a **sound, complete contract**:

- **Coverage**: no high-impact topic is missing; explicit `[NEEDS CLARIFICATION]` markers and open `Q-NNN` are flagged for resolution.
- **Testability**: every REQ is verifiable; every AC is in checkable form (Given/When/Then), with measurable thresholds where behavior is quantitative.
- **Consistency**: no REQ contradicts another REQ, an INV, or a CON.
- **Glossary discipline**: terms defined once, used consistently; no synonym drift.
- **Journey completeness**: each user-journey step (§14/§15) is backed by requirements; named EDGE cases have defined behavior.
- **Purity**: spec states *what/why*, not *how* — no paths, libraries, schemas, signatures.
- **Scope clarity**: in/out-of-scope explicit; SC are outcomes, not tasks.
- **Scope sizing**: the contract is cohesive enough to live as one spec; an oversized contract (many independent domains/actors) is flagged for guided decomposition — detect only, never split here.

Fix only strictly mechanical / meaning-preserving defects. Route everything contractual to `/order.spec`.

## Out of Scope (do NOT do here)

- **Authoring or filling spec content** — adding REQ/NFR/CON/INV/EDGE/AC, defining terms, setting thresholds, resolving `[NEEDS CLARIFICATION]` by writing an answer. All of this is `/order.spec`'s job; the gate only routes to it.
- **Performing the decomposition** — splitting an oversized spec into sub-specs is a content/authoring action owned by `/order.spec --split`; the gate only detects oversized scope and routes.
- How the spec will be implemented — mechanisms, stack, paths → `plan-check` / `/order.plan`.
- Topics that are genuinely planning-time decisions (which library, which deployment, code structure) → tag the finding **"defer-to-plan"** (do NOT route to spec; it carries forward as a known planning decision).
- Whether tasks cover the spec → `tasks-check`.
- Repository state, drift, whole-system constitution sweep, cross-artifact contradictions → `/order.analyze`.
- Mechanical ID counting, internal dangling-reference detection, numbering → the script.

## Operating Constraints

- **INSPECTOR + MECHANIC**: you MAY modify `spec.md` ONLY for mechanical / meaning-preserving auto-fixes. You MUST NOT author, fill, or alter the meaning of any contract content.
- **Auto-fix vs Route boundary** (the single permission to write, kept deliberately tight):
  - **Auto-fix** ONLY when ALL hold: (a) the defect is mechanical or strictly meaning-preserving, (b) exactly one valid correction exists, (c) it does NOT change the meaning, threshold, or scope of any requirement, and (d) it is obvious/reversible. Examples: a term not matching the glossary's defined spelling, a broken internal ID cross-reference, duplicate phrasing of the same requirement, AC reformatted into Given/When/Then **without** altering its conditions/thresholds, section/ID numbering. Apply in place, record in **Auto-Fixed**.
  - **Route** for **everything else** — anything touching requirement meaning, threshold, scope, term definition, EDGE behavior, or a missing topic. Emit a **Routing block** naming the defect and the exact `/order.spec` call that will resolve it. The gate does NOT write the resolution and does NOT wait to apply one.
  - **When in doubt, Route — never Auto-fix.** The write permission is the narrow exception, not the norm.
- **No Ask-and-apply, no Decision-blocks-that-mutate**: the gate never asks the user a question whose answer it then writes into the spec. Content decisions are made by the user *through* `/order.spec`. The gate's job ends at producing precise Routing blocks.
- **Constitution authority**: a spec *goal* directly conflicting with a `.orderspec/memory/constitution.md` MUST principle is CRITICAL → Route (the principle is fixed; reconciling the goal is a content change owned by spec). The full whole-system constitution sweep remains `/order.analyze`'s job.
- **No duplication of mechanical work**: trust the script's inventory/dangling/numbering findings; do not re-count.
- **Root stance**: never read repo, plan, or reason about time; if a concern needs any of those, it is out of scope for this gate.

## Routing Block Format

When a contractual finding cannot be auto-fixed, emit exactly this; **batch all routing blocks together** at the end, do not interleave one-by-one:

```
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

Run `.orderspec/scripts/bash/check-prerequisites.sh --json --paths-only` once from repo root; parse FEATURE_DIR and FEATURE_SPEC. Derive: SPEC = FEATURE_SPEC. Locate `FEATURE_DIR/checklists/requirements.md` if present (read-only). plan.md and tasks.md may be absent and are NOT read by this gate. If EXISTS, load `.orderspec/memory/constitution.md` for governance constraints. Abort with instructions (re-run `/order.spec`) if SPEC is missing. For single quotes in args use `'I'\''m Groot'` or double quotes.

### 2. Mechanical Validation (script)

Run:

```bash
.orderspec/scripts/bash/validate-traceability.sh --json "$FEATURE_DIR"
```

- Parse the JSON: `summary`, `inventory`, `findings` (IDs prefixed `M1`–`M14`).
- Import **only the spec-internal** script findings (ID inventory presence, internal dangling cross-references, ID numbering/format within spec). Keep their IDs and severities. Ignore script findings about plan/tasks/repo/timestamps — not this gate's concern.
- Most spec-internal mechanical findings (numbering, broken internal ref) are **Auto-fix**.
- **Fallback**: if the script is missing or fails, emit a HIGH finding `S0-001` ("mechanical validator unavailable — degraded mode") and manually spot-check only: ID blocks (REQ/AC/EDGE/INV/NFR/CON/SC/ASM) are present and uniquely numbered; internal references resolve. Keep it brief.

### 3. Detection Passes (LLM — coverage + integrity, DETECT ONLY)

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
| Invariants | §13 | INV deterministic, always-true consistency rules |
| Edge cases | §14 | Negative flows, concurrency conflicts, limits/throttling covered as EDGE |
| Acceptance | §15 | Every AC testable G/W/T; Covers complete; each UJ independently testable; P1 = viable MVP |
| Terminology | §3 | Canonical terms defined; no synonym drift |
| Open items | §16–§17 | No stale TODO/placeholders; risky ASM defaults confirmed |

For each **Partial/Missing** category, decide via the **Impact × Uncertainty** heuristic:
- **Route** to `/order.spec` ONLY if the gap would materially change requirements, data model, invariants, acceptance tests, UX behavior, operational readiness, or compliance — AND is not better deferred to planning. ASMs that define externally observable API semantics (idempotency of mutations, status codes for state conflicts, pagination presence/absence) are high-impact regardless of the map.
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

### 4. Checklist Cross-Check (read-only)

If `FEATURE_DIR/checklists/requirements.md` exists (else skip silently):
- Read all checkbox lines (`- [ ]` / `- [x]` / `- [X]`, tolerant of leading whitespace, outside code fences).
- Re-evaluate each item against the current spec. **Do NOT modify the file** — toggling checkboxes follows content changes, and content is owned by `/order.spec`.
- Where your evaluation disagrees with the recorded marker, record it as a finding (LOW unless it reveals an MVP gap): "checklist item '{text}' is marked {checked|unchecked} but the spec now {fails|passes} it." Report before/after-your-evaluation counts in Metrics. If a disagreement reflects a real content gap, fold it into the relevant Routing block rather than emitting a duplicate.

### 5. Severity Assignment

- **CRITICAL**: a P1-journey step (§14/§15) has no backing requirement; two requirements directly contradict on MVP behavior; a spec goal violates a constitution MUST; an unresolved P0 marker blocking MVP correctness.
- **HIGH**: an untestable/unmeasurable MVP requirement; a P1 EDGE with no defined behavior; an AC contradicting its REQ; a Missing high-impact taxonomy category affecting MVP.
- **MEDIUM**: undefined glossary term; non-MVP EDGE undefined; leaked physical detail (purity); SC phrased as a task; synonym drift requiring routing; **defer-to-plan** gaps; **oversized scope recommending decomposition (C8)**.
- **LOW**: cosmetic glossary/numbering (usually auto-fixed); meaning-preserving AC reformatting; verbose phrasing; low-impact coverage gaps; checklist marker disagreements with no MVP impact.

**MVP-scope definition**: "MVP-scope" = requirements/steps tied to the P1 (highest) priority in the user journey (§14/§15). A HIGH finding on MVP-scope blocks; the same class on non-MVP does not auto-block.

### 6. Produce Gate Report

Markdown output. Merge mechanical (M*) and semantic (C*) findings:

```markdown
## Spec Gate Report (spec.md — coverage + internal integrity)

**Verdict**: ✅ PASS | ⛔ BLOCK | 🔀 ROUTING REQUIRED

### Auto-Fixed (applied automatically — mechanical / meaning-preserving only)
| ID | What was changed in spec.md | Why meaning-preserving |
|----|-----------------------------|------------------------|
(empty if none)

### Routing Required (owned by /order.spec — gate did NOT modify content)
(render each as the Routing block format; batched)

### Findings
| ID | Source | Severity | Disposition | Location | Summary |
|----|--------|----------|-------------|----------|---------|
| C0-001 | semantic | HIGH | Route | Missing: Non-functional/security | No NFR for auth rate-limiting |
| C4a-002 | semantic | CRITICAL | Route | §15 UJ1 step 3 | Journey step has no backing requirement |
| C3b-003 | semantic | MEDIUM | Auto-fixed | REQ-005, REQ-011 | "member"/"user" normalized to glossary "user" |

### Coverage Taxonomy (C0)
| Category | §  | Status | Disposition |
|----------|----|--------|-------------|
(render each taxonomy row: Clear / Partial / Missing → Route / defer-to-plan / LOW / —)

### Journey Coverage Matrix
(render: Journey step (§14/§15) | Backing REQ/AC | Status)

### Metrics
- Scope sizing: {cohesive | oversized → split recommended} (from C8)
- Inventory: REQ / AC / EDGE / INV / NFR / CON / SC / ASM (from script)
- Findings by severity: C/H/M/L counts (script + semantic)
- Auto-fixed: N · Routing required: M · defer-to-plan: K
- P0 markers: {n} [NEEDS CLARIFICATION] · {n} open Q-NNN (all routed)
- Checklist cross-check: {agree}/{total} agree with spec; {n} disagreements (if requirements.md present)
```

**Verdict rule**: 🔀 ROUTING REQUIRED if any Routing block exists (the spec needs an author pass via `/order.spec` before it is clean). Independently, ⛔ BLOCK if any CRITICAL remains, or any HIGH affects MVP-scope — a routed CRITICAL/HIGH still BLOCKS the pipeline until the owner resolves it (BLOCK and ROUTING can co-display: "⛔ BLOCK — routing required"). Otherwise ✅ PASS (auto-fixes applied, improvements noted). If zero issues and full coverage: success report with the taxonomy + journey matrices. Rerunning a clean spec.md must produce consistent IDs and counts.

### 7. Next Actions

The gate's responsibilities end at detection, mechanical repair, and routing. For each finding:
- **Mechanical / meaning-preserving** → already auto-fixed (see Auto-Fixed); no user action.
- **Contractual (meaning / threshold / scope / missing topic)** → see the Routing block; the user resolves it by running the suggested `/order.spec "..."`. The gate did not and will not write this content.
- **defer-to-plan** → noted, not routed to spec; it carries forward as a known planning decision for `/order.plan`.
- **Oversized scope (C8)** → see the Routing block; the user decomposes via `/order.spec --split`, which proposes module seams, builds one focused sub-spec on confirmation, and emits ready-to-run prompts for the rest. The gate never splits.

Recommended loop: run the routed `/order.spec` calls (batch the requests if convenient), then **re-run `/order.spec-check`** to confirm the contract is now clean. The gate is idempotent: a spec with no contractual findings yields ✅ PASS.

Downstream note: if plan/tasks already exist and a routed spec change lands, they may need `/order.plan` / `/order.tasks` regeneration — but that is observed by `plan-check` / `tasks-check` / `/order.analyze`, not acted on here.

## Post-Execution Checks

Run the **`after_spec_check`** phase per `.orderspec/memory/hooks-protocol.md`.

## Operating Principles

- **Detect oversize, never decompose**: C8 flags a contract too broad for one cohesive spec and routes to `/order.spec --split`; proposing seams is advisory, authoring sub-specs is the owner's job. Density alone is never a defect.
- **Pure inspector for content**: the gate detects and routes; it NEVER authors, fills, or alters contract meaning. Filling spec content is `/order.spec`'s job, invoked by the user.
- **One narrow write permission**: auto-fix applies ONLY to mechanical / strictly meaning-preserving defects with a single obvious correction. When in doubt, Route — never Auto-fix.
- **Route, don't ask-and-apply**: contractual findings become Routing blocks with a ready-to-run `/order.spec "..."` — the gate never asks a content question whose answer it would write.
- **Detect missing topics, but never fill them**: the C0 taxonomy sweep finds gaps and routes them; authoring the missing REQ/NFR/EDGE belongs to spec.
- **Root stance**: there is no upstream to reroute to — the only "upstream" is the user (through spec). Planning-time gaps are tagged "defer-to-plan", never routed to spec. Never read repo, plan, or reason about time.
- **Read-only on the checklist**: cross-check `requirements.md` against the spec and report disagreements; never toggle it (markers follow content, which spec owns).
- **NEVER hallucinate missing sections** — report absences accurately; a Missing high-impact category is a core finding type here.
- Mechanics belong to the script; **only contract coverage + integrity detection belong to your LLM tokens**.
- Minimal high-signal tokens: cite specific spec IDs, cap at 30 findings, aggregate overflow.
- An unbacked P1-journey step is always CRITICAL; a spec goal violating a constitution MUST is always CRITICAL — both routed, both BLOCK.

## Context

$ARGUMENTS
