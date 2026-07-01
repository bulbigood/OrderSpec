---
orderspec:
  artifact: command_prompt
  command: order.tasks-check
  phase: check
description: Per-stage inspector gate validating tasks.md as a faithful, well-ordered projection of plan.md. The deterministic traceability tool (extract-trace, Variant C) already proves coverage/cap/subset-binding/no-documented/no-delegated at /order.tasks time; this gate NEVER re-judges those facts. It spends its LLM context only on what no script can decide: faithfulness to plan (no invented decisions), E-M-C ordering, test-first discipline, and SC buildability. A pure inspector: it auto-fixes only mechanical/structural-per-methodology defects (ordering, GATE/verification insertion, tags, numbering) and routes everything content/coverage to /order.tasks (or /order.plan / /order.spec for upstream defects). It ALWAYS writes a report file so that "no file" unambiguously means "the gate did not run".
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Role In The Pipeline

This is a **per-stage gate** for one document: `tasks.md`. It runs after `/order.tasks` and answers a single question:

> **Is tasks.md a faithful, well-ordered projection of the decisions already made in plan.md — at this moment of generation?**

It sits at the bottom of the authoring cascade: its upstream artifacts are `plan.md` (the decision source, assumed gated by `plan-check`) and `spec.md` (the ID vocabulary, assumed gated by `spec-check`).

**What is already proven before this gate runs.** `/order.tasks` runs the deterministic traceability tool (`extract-trace`, Variant C) and CANNOT write `tasks.md` unless it returns `rc=0`. That tool is the arbiter of every *traceability fact*:

- every `direct` mechanism is referenced by ≥1 task;
- every declared ref is a `direct` mechanism whose `primary_files` **contains that task's path** (subset-binding — ID-parking is structurally impossible);
- no `documented` ID and no `delegated` AC appears as a ref;
- the ≤3-ref atomicity cap holds, with no duplicate refs.

**This gate therefore does NOT re-derive, re-count, or re-judge coverage, cap, subset-binding, or ID-legality.** Those are settled facts the moment `tasks.md` exists. Spending LLM tokens to second-guess them is both wasteful and dangerous (it invites a false verdict). The gate's entire value is the layer the tool cannot see:

- **T1 — faithfulness**: does any task invent a decision absent from spec/plan?
- **T3 — E-M-C ordering**: Expand additive-only; Contract opens with a GATE.
- **T4 — test-first**: tests precede impl within a story; a verification task closes it.
- **T5 — SC buildability**: success criteria implying buildable work are reflected by tasks.
- **T7 — upstream reroute**: when the root defect lives in plan/spec, route up, never compensate.

It is **local**: spec for the ID vocabulary, plan as the decision source, tasks as the subject. It does **not** read the repository and does **not** reason about time — those belong to `/order.analyze`.

**Division of responsibility (read this first):**

- **Authoring task content is owned by `/order.tasks`.** To add a task, fill a coverage gap, or change what a task does, the user invokes `/order.tasks "<what they want>"`. That command owns task creation, ref-attribution, and the `extract-trace` write-gate.
- **This gate is a pure inspector.** It may perform only **mechanical / structural meaning-preserving** auto-fixes defined by the E-M-C / test-first methodology (reordering, inserting a required GATE/verification task, fixing tags, numbering). Anything that creates or changes the *content* of a task is surfaced as a **Routing block**, never written here.

Two content channels only:

1. **Auto-Fixed** — mechanical/structural defects corrected in place.
2. **Routing Required** — content findings it cannot touch, each with a ready-to-run `/order.tasks` (or `/order.plan` / `/order.spec`) invocation.

Plus one **persistence behaviour**: the gate **always** writes its report (see §6), every run, every verdict. A missing report file therefore unambiguously means the gate did not run.

Boundaries:

- task faithfulness to plan, E-M-C ordering, test-first discipline, SC buildability → **this gate** (detect only).
- coverage, ≤3-cap, subset-binding, documented/delegated legality, ID integrity, numbering, raw `[P]` file-disjointness → **the traceability tool**, already enforced at `/order.tasks`.
- authoring/filling task content, ref-attribution, deciding how an SC is realized → `/order.tasks`.
- plan↔spec completeness, plan role-purity, mechanism adequacy, stack → `plan-check` / `/order.plan`.
- spec self-consistency, glossary, AC form, testability → `spec-check` / `/order.spec`.
- repository state, `[NEW]`/`[MOD]` path existence, temporal drift, whole-system constitution sweep, cross-artifact contradictions → `/order.analyze`.

## The Non-Negotiable Invariant (read before anything else)

**The deterministic traceability tool is ground truth on every traceability fact, and you may never overrule it.**

The traceability outputs (`.orderspec/traceability.tsv` / `traceability.md`, produced by `extract-trace`/`render`) are facts produced by literal parsing under the Variant C contract — not judgements. Coverage, the ≤3-cap, subset-binding, and documented/delegated legality were all enforced as a hard write-gate (`rc=3` = file untouched) before `tasks.md` could exist.

Therefore:

- You MUST treat every `direct` mechanism present in `traceability.tsv` as **covered**, full stop. A mechanism that reached the trace file is covered by definition.
- You MUST NOT raise, even internally, a finding of the form "ID X is uncovered / has no task / needs a task / is only name-dropped / is covered in spirit but not really". If `tasks.md` exists, the tool already proved coverage. Catching yourself reasoning "the tasking missed X" is itself the violation.
- You MUST NOT re-judge ref-attribution. The tool already rejected any ref whose `primary_files` does not contain the task's path; you cannot find a "mis-attributed ref" it let through — by construction there are none.
- You MUST NOT re-check the ≤3-cap or hunt for "kitchen-sink" tasks on coverage grounds — the cap is enforced. (You MAY still flag a task that *operationally* bundles unrelated work as a **granularity/ordering** concern under T2, but never as a coverage or cap-violation finding.)

**If you genuinely believe the tool's contract is wrong** (e.g. a mechanism you think should be `direct` was classified `documented` upstream, so it carries no task): that is an **upstream defect in the plan's Mechanism table**, not a tasks defect. Record it as a **T7 Route to `/order.plan`** — never as a tasks coverage gap, and never by arguing the trace file is incomplete. The trace file is correct *with respect to the mechanisms it was given*; if the mechanisms are wrong, fix them at the plan.

There is no "tag-autofix" channel and no coverage-reconciliation step in this gate anymore — coverage is not a thing this gate decides, so there is nothing to reconcile.

## When to Run

Conditional. Recommended after every `/order.tasks` run, especially when:

- tasks.md was generated or heavily edited by a **weaker model**.
- plan.md was edited shortly before tasking, so the *ordering/faithfulness* projection may be stale (note: coverage staleness is impossible — `extract-trace` re-ran at write time).
- The feature is large or safety-relevant and a mis-ordered task list would be expensive once `/order.code` executes it.

Can be wired as `hooks.after_tasks` for weaker-model workflows.

## Pre-Execution Checks

Run the **`before_tasks_check`** phase per `.orderspec/memory/hooks-protocol.md`.

## Goal

Act as an **independent inspector with fresh context** over `tasks.md`. You did not write it. Determine whether tasks.md is a **faithful, well-ordered projection of plan.md** — accepting coverage/cap/attribution as already-proven facts:

- **No new decisions**: tasks only sequence decisions already in spec/plan; no task invents a file, mechanism, library, schema field, or endpoint not derivable upstream.
- **E-M-C ordering**: Expand → Migrate/Implement → Contract; Expand is additive-only; Contract begins with a GATE.
- **Test-first discipline**: within a story, test tasks precede implementation; a verification task closes the phase.
- **SC buildability**: success criteria implying buildable work are reflected by tasks.
- **Task format**: each task is actionable, correctly tagged, file-scoped.

Fix only mechanical / structural meaning-preserving defects. Route everything that creates or changes task content to `/order.tasks` (or `/order.plan` / `/order.spec` when the root is upstream).

## Out of Scope (do NOT do here)

- **Re-judging any traceability fact** — coverage, the ≤3-cap, subset-binding/ref-attribution, documented/delegated legality. All settled by `extract-trace` at write time (see the Non-Negotiable Invariant).
- **Authoring or filling task content** — adding a task, changing what a task does, deciding how an SC is realized. `/order.tasks`'s job; the gate only routes.
- Requirement quality / spec self-consistency / glossary / AC form → `spec-check` / `/order.spec`.
- plan↔spec completeness, plan role-purity, mechanism adequacy, a wrong/mis-classified plan Mechanism → `plan-check` / `/order.plan`. If the root defect is upstream, do NOT patch tasks around it — Route it (`T7`).
- Repository state, `[NEW]`/`[MOD]` path existence, temporal drift, whole-system constitution sweep, cross-artifact contradictions → `/order.analyze`.

## Operating Constraints

- **INSPECTOR + MECHANIC**: you MAY modify `tasks.md` ONLY for mechanical / structural meaning-preserving auto-fixes. You MUST NOT author task content and MUST NOT edit plan.md or spec.md.
- **Auto-fix vs Route boundary** (kept deliberately tight):
  - **Auto-fix** ONLY when ALL hold: (a) the correction is mechanical or structural-per-methodology (E-M-C / test-first rules, not content choice), (b) exactly one valid form exists, (c) it does NOT change scope or what a task *does*, (d) it is obvious/reversible. Examples: task numbering, test/impl ordering swap, inserting a required per-phase verification task, inserting a required Contract GATE, moving a destructive step after the GATE when placement is unambiguous, fixing a `[US#]` tag resolvable from context, removing a `[P]` whose description depends on an adjacent `[P]`, terminology-to-glossary. Apply in place, record in **Auto-Fixed**.
  - **Route** for **everything else** — a task that invents a decision, a vague task whose target is not unambiguous in plan, an SC needing a new realizing task, a cross-story dependency breaking independent testability. Emit a **Routing block**.
  - **When in doubt, Route — never Auto-fix.** Creating or changing what a task *does* is never deterministic.
- **Auto-fix touches TASK LINES only, never derived sections.** Do NOT edit, rebalance, or regenerate the Files-Touched table, any summary section, or — emphatically — the tool-owned `traceability.md`/`.tsv`. Those are projections owned by `/order.tasks` and the tool. A disagreement between a task line and a derived table is a **Route**, not a rewrite.
- **You never touch refs.** Adding, removing, or changing the spec-ID list on a task line is ref-attribution — that is `/order.tasks`'s job and is re-validated by `extract-trace`. The gate does not edit field 3 of any task. (This is the single biggest change from older versions: there is no "tag-autofix".)
- **The report file is separate from the tasks.** Writing `tasks-report.md` (see §6) is a gate artifact, written every run regardless of verdict; it never counts as authoring task content.
- **No Ask-and-apply**: the gate never asks the user a question whose answer it then writes into tasks.md. Content decisions are made through `/order.tasks`.
- **Constitution authority**: a direct task-vs-`.orderspec/memory/constitution.md` conflict you happen to encounter is CRITICAL → Route. The full sweep is `/order.analyze`'s job.

## Routing Block Format

When a content finding cannot be auto-fixed, emit exactly this; **batch all routing blocks together** at the end:

```text
### Routing Required: {short title}

**Finding**: {what is wrong or missing}
**Location**: {task IDs / section}
**Why owner, not gate**: {creates/changes task content — must go through the artifact's author}
**Impact if unresolved**: {what breaks downstream — /order.code executes a mis-ordered or unfaithful list}
**Suggested direction**: {1–2 candidate resolutions; advisory only}
**Run**: `/order.tasks "{ready-to-run refinement request}"`  (or `/order.plan "..."` / `/order.spec "..."` if the root is upstream)
```

The `Run` line is a copy-pasteable instruction to the owner. It is a recommendation, not an action the gate performs.

## Execution Steps

### 1. Initialize

Run `.orderspec/framework/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks`
once from repo root; parse FEATURE_DIR and AVAILABLE_DOCS. Derive these
**feature-relative** paths (under FEATURE_DIR):
  SPEC   = `FEATURE_DIR/spec.md`
  PLAN   = `FEATURE_DIR/plan.md`
  TASKS  = `FEATURE_DIR/tasks.md`
  TRACE  = `FEATURE_DIR/.orderspec/traceability.tsv`
  REPORT = `FEATURE_DIR/tasks-report.md`
and this **repo-root** path (NOT under FEATURE_DIR):
  CONSTITUTION = `.orderspec/memory/constitution.md`  ← project-level, repo root
If CONSTITUTION exists, load it for governance constraints. Abort ... if any
required feature file is missing.

### 2. Read the Traceability Facts (tool output — GROUND TRUTH, do not re-derive)

The coverage layer was already enforced by `extract-trace` as a write-gate at `/order.tasks` time. Your job here is to **read** its result, not reproduce it.

- If `TRACE` exists and is non-empty: load it. Every `direct` mechanism in it is **covered** — this is the Coverage Matrix, verbatim. You will render it in §6 but you will NOT recompute, second-guess, or flag any of it.
- If `TRACE` is **missing, empty, or unparseable** while `tasks.md` exists: this is the ONLY mechanical anomaly this gate cares about. It means tasking finished without a valid trace write — a genuine tooling/process failure. Emit HIGH **T0-001** ("traceability trace absent — coverage layer unverified for this run") and recommend re-running `/order.tasks` (which re-runs `extract-trace`). Do NOT attempt to reconstruct coverage by hand or by grepping refs — that is exactly the work the tool owns.

There is no exit-code floor to apply and no findings array to import: coverage is not re-litigated here. The verdict is driven entirely by the semantic passes in §3 (plus T0-001 if the trace is genuinely absent).

> **Why so little here?** In older versions this step ran a grep-based validator and imported a `findings[]` array the gate had to police against its own judgement. Variant C moved that enforcement *into* `/order.tasks` as a hard write-gate, so by the time `tasks.md` exists, those facts are already true. Re-checking them would only create opportunities to wrongly overrule the tool.

### 3. Detection Passes (LLM — task intent, DETECT ONLY)

**These semantic passes are MANDATORY on every run.** They are the entire point of this gate — the layer the tool cannot see. The full Findings table and Coverage Matrix MUST appear in the output on every run, including PASS.

Load spec, plan, tasks. Build minimal internal models — do not dump raw artifacts into output. Limit to 25 findings total; on overflow, drop LOW first and aggregate into one summary line — never drop a CRITICAL. Use stable IDs prefixed by pass (T1-001, T3-001…). For each finding, classify disposition as **Auto-fix**, **Route**, or **defer-upstream** (T7). Detection only — the gate never authors task content.

Process `T1` first (faithfulness logically precedes ordering).

#### T1. No New Decisions (faithfulness to plan)

- T1a: Any task introducing a design decision **absent from spec and plan** (file, mechanism, library, schema field, endpoint not derivable upstream) → **Route** (legitimize via `/order.plan`, or strip via `/order.tasks`). The gate never silently keeps or deletes an invented decision.
- T1b: Any task referencing a plan Mechanism / file / path **not in the current plan**: an obvious typo for an existing item → **Auto-fix** (correct the reference) — *but only the prose/path, never the ref-ID list*; something genuinely absent → **Route**.

> Note: subset-binding already guarantees every *ref* points at a real plan mechanism on a matching path. T1b therefore concerns prose mentions and path references in the description, not field-3 refs.

#### T2. Operational Granularity (NOT a coverage or cap check)

The ≤3-ref cap is tool-enforced; you never re-check it. T2 catches only the *operational* shape the tool is blind to:

- T2a: A task whose description bundles **unrelated** work that shares no coherent behavior or flow (a genuine grab-bag), such that `/order.code` cannot execute it as one discrete step → **Route** to split. Severity **MEDIUM** (it reduces granularity but, since coverage is already proven, does not make MVP undeliverable). Do NOT raise this merely because a task lists several refs — that is legal and capped. Raise it only when the *work itself* is incohesive.
- T2b: A TEST task legitimately exercises one coherent multi-AC user flow (e.g. create→list→soft-delete→verify-exclusion) — this is NOT a defect. Flag only a test task bundling genuinely unrelated scenarios, at **LOW/MEDIUM**, never HIGH.

#### T3. E-M-C Ordering

- T3a: Phase 1 (Expand) tasks are **additive only** (read descriptions, not just labels). A destructive step in Expand → **Auto-fix** (move to the correct phase) when unambiguous; else **Route**.
- T3b: Story phases follow UJ priority order from spec §14 (P1 before P2). Out-of-order with a single correct ordering → **Auto-fix** (reorder).
- T3c: The Contract phase begins with a GATE task; **no destructive task** precedes that GATE. Missing GATE → **Auto-fix** (insert it). A destructive task ahead of it → **Auto-fix** (move after GATE) if placement is unambiguous; else **Route**.

#### T4. Test-First Discipline

- T4a: Within each story phase, test tasks **precede** implementation (classify by description). A clear test-after-impl pair → **Auto-fix** (swap order).
- T4b: Each **story** phase (one tagged to a `[US#]`) is closed by a verification task asserting that story's ACs. Missing → **Auto-fix** (append one).
**Scope clarification:** the non-story Expand/Setup phase (Phase 1) is NOT required to carry a verification task — its additive schema/fixture work is self-verified by any unit test it contains and asserts no story AC. Absence of a verification task in Phase 1 is explicitly NOT a finding. Apply T4b ONLY to `[US#]`-tagged story phases.
- T4c: Test tasks state the expectation to **fail first** (red). Missing red-state note → **Auto-fix** (add it) where the test's intent is clear.

#### T5. SC Buildability

- T5a: Each Success Criterion (spec §2) implying **buildable work** (load tests, security tooling, performance assertions) is reflected by ≥1 task; post-launch / business KPIs exempt. A buildable SC with no task → **Route** (the realizing task is content owned by `/order.tasks`). The gate never picks how the SC is realized.

#### T6. Task Format

- T6a: Each task is **actionable and self-contained**: exact file path + short paraphrase (refs optional — infra/verification tasks legitimately carry none). A vague task ("handle errors") → **Auto-fix** by enriching the gloss from plan when the target is unambiguous; else **Route**. NEVER add/alter refs.
- T6b: `[US#]` tags trace each implementation task to a story; `[P]` semantics respected at description level. Missing `[US#]` resolvable from context → **Auto-fix**. A `[P]` whose description depends on an adjacent `[P]`'s output → **Auto-fix** (remove the offending `[P]`). NOTE: **absence of `[P]` is NEVER a finding** — sequential is always valid; never add `[P]`.
- T6c: Cross-story dependency breaking independent-testability (a P1 task depending on a P2 task) → **Route** (re-sequencing stories touches the delivery contract).

#### T7. Upstream Reroute (route upward, never compensate)

- T7a: Where tasks cannot be made faithful because the **root defect lives upstream** — a wrong/inadequate/mis-classified plan Mechanism (e.g. a behavior the plan marked `documented` that you believe needs executable work, so it correctly carries no task), or a spec ambiguity → **Route** to `/order.plan` or `/order.spec` describing the suspected root. Do NOT patch tasks around it; do NOT edit upstream artifacts; do NOT argue the trace file is incomplete (it is correct w.r.t. the mechanisms it was given). Note in *Impact if unresolved* that tasks stay blocked until the root is fixed. Severity inherits MVP-scope (CRITICAL if it blocks a P1 story).

### 4. Severity Assignment

- **CRITICAL**: a task invents a decision that changes MVP scope; a destructive task precedes the Contract GATE with ambiguous placement; an upstream defect (T7) blocking a P1 story.
- **HIGH**: tests ordered after implementation within a P1 story; a P1 story phase with no verification task; a task references a non-existent plan mechanism on the MVP path; an SC requiring buildable work with no task; **T0-001 (traceability trace absent) — the coverage layer is unverified for this run.**
- **MEDIUM**: an operational grab-bag task (T2a); a vague/non-self-contained task; an upstream reroute (T7) on a non-MVP story; a cross-story dependency on a non-MVP story.
- **LOW**: cosmetic format issues; minor paraphrase verbosity; a fat-but-coherent test task.

**MVP-scope definition**: "MVP-scope" = stories whose UJ priority is P1 in spec §14. A HIGH finding on a P1 story blocks; the same class on P2+ does not auto-block.

### 5. Determine Verdict

Coverage is not a verdict input here — it was settled by the tool. The verdict is driven by the semantic passes (plus T0-001 if the trace is genuinely absent).

- 🔀 **ROUTING REQUIRED** if any Routing block exists — tasks.md needs an author pass via `/order.tasks` (or `/order.plan` / `/order.spec`) before it is clean.
- ⛔ **BLOCK** if any CRITICAL remains, or any HIGH affects MVP-scope. A routed CRITICAL/HIGH still BLOCKS until the owner resolves it (co-display: "⛔ BLOCK — routing required").
- ✅ **PASS** only if there are zero Routing blocks AND zero unresolved CRITICAL/HIGH. Auto-fixes applied and LOW notes are compatible with PASS.

Rerunning a clean tasks.md must produce consistent IDs, counts, and verdict.

> **What "HIGH affects MVP-scope" means for BLOCK (be precise):** a HIGH blocks ONLY if the defect makes the P1/MVP work mis-ordered to the point of being unbuildable, or unfaithful — e.g. tests ordered after impl in a P1 story, a P1 story with no verification task, a P1 task referencing a non-existent mechanism, a P1-scope invented decision. A finding that touches an MVP story but does NOT break its ordering/faithfulness is NOT MVP-blocking → 🔀 ROUTING REQUIRED, not ⛔ BLOCK. BLOCK needs a defect that breaks MVP delivery; ROUTING needs a defect that needs the author but doesn't break MVP.

> **T0-001 is the one infrastructure signal that matters now.** If the trace is genuinely absent (tooling failure), surface it as a HIGH degraded banner and recommend re-running `/order.tasks`. It indicates coverage was not verified *this run* — distinct from a real task defect, but worth blocking on because the whole coverage guarantee is missing. If the trace is present, no infrastructure signal exists and the verdict is purely the T-pass result.

### 6. Produce Gate Report — ALWAYS WRITTEN (chat + file, every run)

**Persistence rule (simple and absolute):**

- **Always** write the report to `REPORT` — every run, every verdict (✅ PASS, ⛔ BLOCK, 🔀 ROUTING REQUIRED) — overwrite, never append, stamp the header with date and verdict.
- A PASS report is a *positive record* that the gate ran and tasks.md is clean. The only state in which `REPORT` does not exist is **the gate never ran**.
- The header stamp, the verdict line, and the Metrics line MUST agree.

Report body:

```markdown
<!-- tasks-report.md — generated by /order.tasks-check · {DATE} · verdict: {VERDICT} · overwritten each run -->

## Tasks Gate Report (tasks.md ← plan.md)

**Verdict**: ✅ PASS | ⛔ BLOCK | 🔀 ROUTING REQUIRED

{If T0-001 present: one-line "⚠ DEGRADED — traceability trace absent (T0-001); the coverage layer was NOT verified this run. Re-run /order.tasks." banner here. Omit entirely otherwise.}

### Auto-Fixed (applied automatically — mechanical / structural meaning-preserving only)
| ID | What was changed in tasks.md | Why meaning-preserving |
|----|------------------------------|------------------------|
(empty if none. Record ONLY changes actually written this run — one row per task LINE edited. A "no change needed" row is forbidden: if nothing was written, the row does not exist. NEVER a row that adds/alters refs — the gate does not touch field 3.)

### Routing Required (owned by /order.tasks / .plan / .spec — gate did NOT author content)
(render each as the Routing block format; batched. "None" if PASS.)

### Findings
| ID | Source | Severity | Disposition | Task / Location | Summary |
|----|--------|----------|-------------|-----------------|---------|
| T4a-001 | semantic | HIGH | Auto-fixed | T013/T014 | Impl preceded its test in US2 — order swapped |
| T1a-002 | semantic | CRITICAL | Route | T021 | Task invents an endpoint absent from plan |
(on PASS, this table may legitimately be empty or carry only LOW notes — render it anyway. There is NO coverage-gap finding type in this gate — coverage is the tool's settled fact.)

### Coverage Matrix (verbatim from the tool — NOT re-judged)
| Spec ID | Task IDs | Status |
|---------|----------|--------|
(render from `traceability.tsv`/`render` output on every run, including PASS. Status is `covered` for every direct mechanism in the trace — that is the only value that appears, because by construction the trace contains only covered mechanisms. documented/delegated IDs are shown with a "—" / "documented" task column exactly as the tool renders them. NEVER invent an "UNCOVERED" row — if the trace exists, nothing is uncovered; if the trace is absent, emit T0-001 and render this table as "unavailable — trace absent" instead of guessing.)

### Metrics
- Inventory (from plan Mechanism table / trace): REQ / AC / EDGE / INV / SC / tasks — verbatim.
- Findings by severity: C/H/M/L counts (semantic + T0-001 if present)
- Auto-fixed: N · Routing required: M · upstream reroutes (T7): K
- Traceability trace: {present — coverage proven by extract-trace | ABSENT — T0-001, coverage unverified this run}
- Report file: always written to tasks-report.md
```

After rendering, state in one line the `REPORT` path where the file was written (always).

### 7. Next Actions

The gate's responsibilities end at detection, mechanical/structural repair, routing, and writing the report. For each finding:

- **Mechanical / structural meaning-preserving** → already auto-fixed; no user action.
- **Content** → see the Routing block; resolve via `/order.tasks "..."`. The gate did not and will not author this content.
- **Upstream root cause (T7)** → see the Routing block; resolve via `/order.plan "..."` or `/order.spec "..."`. Tasks never compensate for an upstream gap.
- **T0-001 (degraded)** → the traceability trace is absent; re-run `/order.tasks` so `extract-trace` regenerates it and the coverage guarantee is restored.

Recommended loop: run the routed commands, then **re-run `/order.tasks-check`** to confirm tasks.md is clean. The gate is idempotent: a faithful, well-ordered tasks.md with a present trace yields ✅ PASS and writes a clean PASS report.

Downstream note: once tasks.md is clean it is ready for `/order.code`. Repo state, drift-over-time, or whole-system concerns → `/order.analyze`.

## Post-Execution Checks

Run the **`after_tasks_check`** phase per `.orderspec/memory/hooks-protocol.md`.

## Operating Principles

- **The traceability tool is ground truth on coverage (the Non-Negotiable Invariant)**: coverage, the ≤3-cap, subset-binding, and documented/delegated legality were enforced as a hard write-gate at `/order.tasks` time. The gate reads the trace; it NEVER re-derives, re-counts, or overrules it, and there is no coverage-gap finding type here.
- **You never touch refs**: adding/removing/changing a task's spec-ID list is ref-attribution owned by `/order.tasks` and re-validated by `extract-trace`. There is no tag-autofix.
- **Semantic passes are the whole value**: T1 faithfulness, T3 E-M-C ordering, T4 test-first, T5 SC buildability, T7 upstream reroute — the layer no script can decide. Mandatory on every run; the Findings table and Coverage Matrix appear on every run.
- **A suspected coverage problem is an upstream defect, not a tasks gap**: if you think a behavior needs a task but has none, the plan mis-classified its mechanism — Route T7 to `/order.plan`, never argue the trace is incomplete.
- **Pure inspector for content**: the gate detects, repairs structure, and routes; it NEVER authors a task.
- **Structural auto-fix is methodology-driven, not content**: reordering, GATE/verification insertion, tag fixes follow fixed E-M-C / test-first rules. Creating or changing what a task *does* is always a Route.
- **Auto-fix touches task lines only**: never edit the tool-owned trace, the Files-Touched table, or any derived section; never touch field-3 refs.
- **When in doubt, Route — never Auto-fix.**
- **Route, don't ask-and-apply**: content findings become Routing blocks with a ready-to-run command.
- **Local-stage stance**: validate tasks.md against plan.md (and spec for the ID vocabulary) only; never reach into the repo or reason about time — that is `/order.analyze`.
- **Always write the report**: every run, every verdict, including PASS. "No file" means "the gate did not run".
- **NEVER hallucinate missing sections** — report absences accurately.
- Minimal high-signal tokens: cite specific task IDs, cap at 25 findings, aggregate overflow.
- Under-parallelization is never a defect; absence of `[P]` needs no remediation.

## Context

$ARGUMENTS
