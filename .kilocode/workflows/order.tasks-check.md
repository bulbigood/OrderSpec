---
description: Per-stage inspector gate validating tasks.md as a faithful, well-ordered, complete-coverage projection of the plan.md decisions. A pure inspector: it detects coverage gaps, ordering/test-first violations, invented decisions, and SC-buildability gaps, but NEVER authors task content; it auto-fixes only mechanical / structural-per-methodology defects (ordering, GATE/verification insertion, tags, numbering) and routes everything content/coverage to /order.tasks (or /order.plan / /order.spec for upstream defects). It ALWAYS writes a report file (every run, every verdict) so that "no file" unambiguously means "the gate did not run". Mechanical coverage/format/[P] checks via validate-traceability.sh; LLM context spent on task-intent semantics, E-M-C ordering, test-first discipline, and SC buildability.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Role In The Pipeline

This is a **per-stage gate** for one document: `tasks.md`. It runs after `/order.tasks` and answers a single question:

> **Is tasks.md a correct, faithful, well-ordered, complete-coverage ordering of decisions already made in plan.md — at this moment of generation?**

It sits **at the bottom of the authoring cascade**: its upstream artifacts are `plan.md` (the decision source, assumed already gated by `plan-check`) and `spec.md` (the ID vocabulary, assumed already gated by `spec-check`). A defect here originates either in the task text, or — when routed — in the plan/spec it was derived from.

It is **local** by design: narrow context (spec for the ID vocabulary, plan as the decision source, tasks as the subject). It does **not** read the repository and does **not** reason about time — those cross-stage/temporal concerns are owned by `/order.analyze`.

**Division of responsibility (read this first):**

- **Authoring task content is owned by `/order.tasks`**, not by this gate. If the user wants to add a task, fill a true coverage gap, or change what a task does, they invoke `/order.tasks "<what they want>"`. That command owns task creation, ID-routing, and write discipline.
- **This gate is a pure inspector.** It verifies the projection and may perform only **mechanical / structural meaning-preserving** auto-fixes — these are defined by the E-M-C / test-first methodology, not by content choice (reordering, inserting a required GATE/verification task, fixing tags, numbering). Anything that would **create or change the content of a task, or fill a true coverage gap**, is NOT done here — it is surfaced as a **Routing block** telling the user exactly which command will resolve it.

So the gate has two content channels only:

1. **Auto-Fixed** — mechanical/structural defects it silently corrected in place.
2. **Routing Required** — content/coverage findings it cannot touch, each with a ready-to-run `/order.tasks` (or `/order.plan` / `/order.spec`) invocation.

Plus one **persistence behaviour**: the gate **always** writes its report to a file (see §6), on every run and every verdict. A missing report file therefore unambiguously means the gate did not run.

It reads `spec.md` (ID vocabulary), `plan.md` (decision source), `tasks.md` (the subject), and the constitution (only for a direct task-vs-principle conflict it happens to encounter). It does **not** read the repository, **not** reason about temporal drift, and **not** re-judge spec/plan validity. `/order.tasks` no longer produces a self-grading checklist, so there is no author checklist to cross-check.

Boundaries:

- task faithfulness to plan, semantic coverage, E-M-C ordering, test-first discipline, SC buildability, task format → **this gate** (detect only).
- authoring/filling task content, task creation, ID-routing, deciding how an SC is realized → `/order.tasks`.
- plan↔spec completeness, plan role-purity, mechanism adequacy, stack → `plan-check` / `/order.plan`.
- spec self-consistency, glossary, AC form, testability → `spec-check` / `/order.spec`.
- repository state, `[NEW]`/`[MOD]` path existence, temporal drift, whole-system constitution sweep, cross-artifact contradictions → `/order.analyze`.
- mechanical coverage counts, ID integrity, numbering, raw `[P]` file-disjointness → the script.

## The Two Non-Negotiable Invariants (read before anything else)

These two rules override every other consideration in this gate. They exist because the worst failure mode is the gate using its own semantic judgement to overrule the deterministic script and emit a false PASS. That must never happen.

1. **The mechanical script is ground truth; you may never overrule it.** Every entry in the script's `findings[]` array is a *deterministic fact* produced by grep/awk over literal text — not a judgement.
You MUST import each tasks-relevant finding at its stated severity.
You MAY choose its disposition (Auto-fix vs Route), MAY escalate severity with justification (an uncovered AC of the MVP/P1 story → CRITICAL), and MAY add context.
You MUST NOT downgrade, suppress, or dismiss a mechanical finding on semantic grounds — and this prohibition is term-agnostic: calling an M2 coverage finding a **"false positive", a "false negative", "covered in spirit", "covered by an adjacent task", or "the script's pattern just didn't match"** is the SAME forbidden move and is equally banned. If a spec ID is in the script's uncovered set, its Coverage Matrix status is `UNCOVERED (script)` — full stop.
You may ADD a T0-002 note that you suspect the script's pattern, but the finding still stands at its severity and the status stays `UNCOVERED (script)`.
You may NEVER flip it to `covered` by argument.
"The behaviour is covered by an adjacent task / in spirit" does NOT cancel an M2 coverage finding — M2 checks whether the literal spec ID is referenced by a task, a *traceability fact* orthogonal to whether the work conceptually exists. If you genuinely believe the script's PATTERN is wrong, that is a bug in the SCRIPT (report it as **T0-002**, MEDIUM); it is NEVER grounds to overrule the result and pass.
**This prohibition binds your REASONING, not only the written report.** You may not conclude — even internally, even in a sentence you never write to the file — that an uncovered ID is "really covered", a "false negative", "actually fine", or "covered by T###". Catching yourself thinking "the script missed this, it's a false negative" IS the violation, even if the Matrix row stays correct. The ONLY permitted framing is: *"the script marks X uncovered — a traceability fact; a task may implement the behaviour, so the correct remedy is either a T2a tag-autofix (which legally turns the status into `covered (tag auto-fixed)`) or a Route. Until a tag is actually added, the status stays `UNCOVERED (script)`."* If you believe the work genuinely exists in a task, do NOT argue the point — **take the legal action: apply the T2a tag-autofix.** That is the sanctioned channel for "I think this is really covered"; an argument in prose is not.
**Corollary — a tag-autofix is a coverage assertion, and it binds you symmetrically.** The instant you apply a T2a tag-autofix to ID X, you have formally asserted "a task produces X's behaviour", and X is now **covered** — with the *identical force* of the script marking X "covered". From that moment, the prohibition above runs in the OTHER direction too: just as you may never argue a script-covered ID is "really uncovered", you may never argue (or record as a finding) that an ID YOU just tag-autofixed is "still uncovered" / "has no task" / "needs a task". Your own autofix is a `covered` source you must trust exactly as much as the script's verdict. Treating your autofix as mere cosmetics on the line — while still routing the same ID as a coverage gap — is a self-contradiction and is forbidden (the reconciliation step in §5 enforces this mechanically).

2. **The script exit code is a hard floor on the verdict.** Read it FIRST, before forming any opinion:
   - exit **1** → ≥1 mechanical CRITICAL/HIGH exists → the verdict **cannot be ✅ PASS**. Floor is 🔀 ROUTING REQUIRED (⛔ BLOCK if any is MVP-affecting).
   - exit **3** → clean but partial scope (an upstream artifact this gate doesn't own was absent) → does NOT by itself force non-PASS.
   - exit **0** → clean, full scope.
   - exit **2** → a required artifact (`spec.md` / `plan.md` / `tasks.md`) missing → abort.
   You may make the verdict MORE severe than the floor (semantic findings can push exit-0 to ROUTING); you may NEVER make it less. If you are about to write PASS while the script returned 1, you have made an error — stop and reconcile.

## When to Run

Conditional. Recommended after every `/order.tasks` run (including refinement runs), especially when:

- tasks.md was generated or heavily edited by a **weaker model**.
- plan.md was edited shortly before tasking, so the projection may be stale against the decisions.
- The feature is large or safety-relevant and a mis-ordered/under-covered task list would be expensive once `/order.code` starts executing it.
- You want a clean, fully-covered task list before `/order.code` consumes it.

Can be wired as an automatic post-tasks hook (`hooks.after_tasks`) for weaker-model workflows.

## Pre-Execution Checks

Run the **`before_tasks_check`** phase per `.orderspec/memory/hooks-protocol.md`.

## Goal

Act as an **independent inspector with fresh context** over `tasks.md`. You did not write it. Determine whether tasks.md is a **faithful, well-ordered, complete-coverage projection of plan.md**:

- **No new decisions**: tasks only sequence decisions already in spec/plan; no task invents a file, mechanism, library, schema field, or endpoint not derivable upstream.
- **Coverage**: every spec ID that needs a task has one (mechanical via script; semantic gaps via LLM).
- **E-M-C ordering**: Expand → Migrate/Implement → Contract discipline holds; Expand is additive-only; Contract begins with a GATE.
- **Test-first discipline**: within a story, test tasks precede implementation; a verification task closes the phase.
- **SC buildability**: success criteria requiring buildable work are reflected in tasks.
- **Task format**: each task is actionable, correctly tagged, file-scoped.

Fix only mechanical / structural meaning-preserving defects. Route everything that creates or changes task content to `/order.tasks` (or `/order.plan` / `/order.spec` when the root is upstream).

## Out of Scope (do NOT do here)

- **Authoring or filling task content** — adding a task, filling a true coverage gap, deciding how an SC is realized, changing what a task does. All of this is `/order.tasks`'s job; the gate only routes to it.
- **Overruling the mechanical script** — see the Two Non-Negotiable Invariants above.
- Requirement quality / spec self-consistency / glossary / AC form → `spec-check` / `/order.spec`.
- plan↔spec completeness, plan role-purity, mechanism adequacy, plan duplication of spec → `plan-check` / `/order.plan`. If the root defect lives **upstream** (a wrong plan Mechanism, a spec ambiguity), do NOT patch tasks around it — Route it (`T7`) to `/order.plan` or `/order.spec`; tasks cannot compensate for an upstream gap.
- Repository state, `[NEW]`/`[MOD]` path existence, temporal drift, whole-system constitution sweep, cross-artifact contradictions → `/order.analyze`.
- Mechanical ID counting, dangling-ID detection, numbering, raw `[P]` file-disjointness → the script.

## Operating Constraints

- **INSPECTOR + MECHANIC**: you MAY modify `tasks.md` ONLY for mechanical / structural meaning-preserving auto-fixes. You MUST NOT author task content or fill a true coverage gap, and you MUST NOT edit plan.md or spec.md.
- **Auto-fix vs Route boundary** (the single permission to write task content, kept deliberately tight):
  - **Auto-fix** ONLY when ALL hold: (a) the correction is mechanical or structural-per-methodology (E-M-C / test-first rules, not content choice), (b) exactly one valid form exists, (c) it does NOT change contract/scope or what a task *does*, and (d) it is obvious/reversible. Examples: ID-reference typo, task numbering, test/impl ordering swap, inserting a required per-phase verification task, inserting a required Contract GATE, moving a destructive step after the GATE when placement is unambiguous, fixing a `[US#]` tag resolvable from context, removing a `[P]` whose description depends on an adjacent `[P]`, terminology-to-glossary. Apply in place, record in **Auto-Fixed**.
  - **Route** for **everything else** — a task that invents a decision, a true coverage gap with no home task, a vague task whose target is not unambiguous in plan, an SC needing a new realizing task, a cross-story dependency breaking independent testability. Emit a **Routing block** naming the defect and the exact command that will resolve it. The gate does NOT write the resolution and does NOT wait to apply one.
  - **When in doubt, Route — never Auto-fix.** Creating or changing what a task *does* is never deterministic; it is always a Route. The write permission is the narrow exception, not the norm.
- **Auto-fix touches TASK LINES only, never derived sections.** A tag-autofix edits the spec-ID list ON THE TASK'S OWN LINE and nothing else. You MUST NOT edit, "rebalance", regenerate, or "sync" the Traceability Matrix, the Files-Touched table, or any other derived/summary section of `tasks.md` — those are projections owned by `/order.tasks`. If a task line and the Traceability Matrix disagree, that disagreement is a finding to **Route** (or a consequence `/order.tasks` will reconcile on its next authoring run), NOT something the gate rewrites. Rewriting a derived table is content authoring and is out of scope even when the correction looks "obvious" or "mechanical". A single tag-autofix therefore changes exactly ONE line (the task's), never a matrix row, and never the same spec ID across several task lines to make a table balance.
- **A tag-autofix you applied = covered; never route it as a gap.** Once you tag-autofix ID X onto a task this run, X's status is `covered (tag auto-fixed)` and X is NOT eligible for any "uncovered"/coverage-gap finding (no T2b Route, no "needs a task", no Note claiming absence). Recording both "added X tag (task produces X)" in Auto-Fixed AND "X uncovered, needs a task" in Findings is a self-contradiction — the uncovered finding is the bug. The §5 reconciliation step (Step 1c) walks every autofixed ID and deletes any such contradictory finding before the verdict is computed.
- **The report file is separate from the tasks.** Writing `tasks-report.md` (see §6) is a gate artifact, not a tasks edit; it never counts as authoring task content. It is written on every run regardless of verdict.
- **No Ask-and-apply, no Decision-blocks-that-mutate**: the gate never asks the user a question whose answer it then writes into tasks.md. Content decisions are made by the user *through* `/order.tasks`. The gate's job ends at producing precise Routing blocks (and persisting them to the report file).
- **Constitution authority**: a direct task-vs-`.orderspec/memory/constitution.md` MUST conflict you happen to encounter is CRITICAL → Route. The full whole-system constitution sweep remains `/order.analyze`'s job.
- **No duplication of mechanical work**: trust the script's coverage/format/`[P]`/numbering findings; do not re-count, do not re-derive, do not second-guess.
- **Local stance**: do not reach into the repository or reason about time — that is `/order.analyze`. If a concern needs either, it is out of scope for this gate.

## Routing Block Format

When a content/coverage finding cannot be auto-fixed, emit exactly this; **batch all routing blocks together** at the end, do not interleave one-by-one:

```text
### Routing Required: {short title}

**Finding**: {what is wrong or missing}
**Location**: {task IDs / section / "Uncovered: {spec ID}"}
**Why owner, not gate**: {creates/changes task content or coverage — must go through the artifact's author}
**Impact if unresolved**: {what breaks downstream — /order.code executes an incomplete or mis-ordered list}
**Suggested direction**: {1–2 candidate resolutions the author may consider; advisory only}
**Run**: `/order.tasks "{ready-to-run refinement request capturing the finding}"`  (or `/order.plan "..."` / `/order.spec "..."` if the root is upstream)
```

The `Run` line is a concrete, copy-pasteable instruction to the artifact's owner. It is a recommendation, not an action the gate performs.

## Execution Steps

### 1. Initialize

Run `.orderspec/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` once from repo root; parse FEATURE_DIR and AVAILABLE_DOCS. Derive: SPEC = `FEATURE_DIR/spec.md`, PLAN = `FEATURE_DIR/plan.md`, TASKS = `FEATURE_DIR/tasks.md`, REPORT = `FEATURE_DIR/checklists/tasks-report.md`. If EXISTS, load `.orderspec/memory/constitution.md` for governance constraints. Abort with instructions (re-run `/order.tasks`, or `/order.plan` / `/order.spec` if the missing file is upstream) if any required file is missing. For single quotes in args use `'I'\''m Groot'` or double quotes.

### 2. Mechanical Validation (script — GROUND TRUTH)

Run, scoping the script to this gate's stage:

```bash
.orderspec/scripts/bash/validate-traceability.sh --json --stage tasks "$FEATURE_DIR"
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

- **0** — clean, full tasks-stage scope. Normal.
- **3** — clean, but some checks were skipped because an upstream artifact this gate doesn't own was absent. **This is NOT degraded mode.** The `skipped` array lists what was deferred (all concerns this gate does not own). Proceed normally; do NOT emit T0-001; this does NOT make tasks-stage scope "partial".
- **1** — ≥1 CRITICAL/HIGH mechanical finding present. **Verdict floor is now non-PASS.** Import the tasks-relevant findings (coverage gaps M2, task numbering, `[P]` disjointness, dangling task IDs) at their stated severities; choose a disposition (numbering/`[P]` issues are typically Auto-fix; a true coverage gap M2 is Route — authoring the missing task is contractual).
- **2** — a required artifact (`spec.md` / `plan.md` / `tasks.md`) itself is missing → abort, instruct the user to run the appropriate `/order.*`.

Import **only tasks-relevant** findings (coverage gaps, task numbering, `[P]` disjointness, dangling task IDs). Ignore any plan/spec-internal, repo, or timestamp findings — not this gate's concern.

**You may NOT overrule any imported finding (Invariant 1).** A mechanical finding is a deterministic fact, never a "false positive" you can dismiss. You MAY escalate its severity with justification; you may NOT downgrade it. If you believe the script's pattern itself is faulty, record it as **T0-002 (MEDIUM)** and STILL import the finding — do not suppress it.

**Genuine degraded mode (T0-001) is narrow.** Emit HIGH **T0-001** ("mechanical validator unavailable — degraded mode") ONLY if the script is missing, crashes, or returns unparseable output (a real tooling failure). **Exit code 3 is NOT degraded mode.** In a true degraded case, manually spot-check only: each P1 AC maps to ≥1 task; task IDs sequential/unique; no two `[P]` on the same path. Keep it brief. T0-001 is surfaced in the report but does NOT by itself drive the verdict (see §5).

### 3. Detection Passes (LLM — task intent, DETECT ONLY)

**These semantic passes are MANDATORY on every run and run INDEPENDENTLY of the mechanical result.** A clean (or seemingly clean) script result NEVER lets you skip them — the script covers only literal coverage/format/`[P]` facts; the semantic projection (faithfulness to plan, real-vs-name-drop coverage, E-M-C ordering, test-first discipline, SC buildability) is yours alone to assess and is the primary value of this gate. The full Findings table and Coverage Matrix MUST appear in the output on every run, including PASS.

Load spec, plan, tasks. Build minimal internal models — do not dump the raw artifacts into output. Limit to 25 findings total (including imported M-findings); on overflow, drop LOW first and aggregate into one summary line — never drop a CRITICAL. Use stable IDs prefixed by pass (T1-001, T2-001…). For each finding, classify disposition as **Auto-fix**, **Route**, or **defer-upstream** (upstream root → Route to plan/spec). Remember: detection only — the gate never authors task content in these passes.

Process passes in order; **`T1` first** (no new decisions), then `T2` (coverage), because "is this list faithful and complete" logically precedes "is it well-ordered".

#### T1. No New Decisions (faithfulness to plan)

- T1a: Any task introducing a design decision **absent from spec and plan** (file, mechanism, library, schema field, endpoint not derivable upstream) → **Route** (legitimize it via `/order.plan`, or strip it via `/order.tasks`). The gate never silently keeps or deletes an invented decision.
- T1b: Any task referencing a plan Mechanism / file / path **not in the current plan**: an obvious typo for an existing mechanism → **Auto-fix** (correct the reference); something genuinely absent → **Route**.

#### T2. Coverage Semantics (gaps the script cannot see)

- **T2a**: For each spec ID the script marks "covered", does the task actually address it or just name-drop the ID? — A tag-autofix is permitted ONLY when a SINGLE, SPECIFIC IMPLEMENTATION task directly and literally produces the behaviour of that ID, and merely omitted the tag. ALL of these must hold, or it is a Route, not an autofix:
  - **(a)** the target is an implementation task that PRODUCES the behaviour — NEVER a verification/GATE/test-run task (those assert, they do not implement; tagging them fabricates traceability);
  - **(b)** the coverage is DIRECT, not "indirect"/"via AC-XXX"/"in spirit" — if your justification contains the word "indirect", "via", or "the AC covers it", STOP: that is a Route (or, for documented-only behaviour with a "—" test type in the plan Mechanism table, leave UNCOVERED and Route with a note);
  - **(c)** you add the tag to exactly ONE task, the one that does the work — do NOT scatter the same ID across multiple tasks to "make the matrix balance";
  - **(d)** the plan's Mechanism table assigns an executable task to that ID (test type is NOT "—"). If the plan marks the behaviour as documented-only ("—"), there is no implementing task to tag → leave UNCOVERED (script) and Route.
If any of (a)–(d) fails → Route (true coverage/traceability gap; authoring/retagging is /order.tasks). When unsure whether a task "really implements" an ID → Route, never autofix.
**Once you DO apply a tag-autofix to an ID, that ID is now `covered` (Invariant 1 corollary): you may NOT later raise an "uncovered"/"needs a task" finding for it. See §5 Step 1c — it deletes any such contradictory finding.**

- **T2b: EDGE / INV needing executable behavior is backed by a task (pure-documentation invariants exempt).** Missing coverage → **Route** (the work doesn't exist; authoring it is `/order.tasks`). **Eligibility:** you may raise a T2b coverage gap ONLY for an ID that is *script-uncovered AND not tag-autofixed by you this run AND* has no implementing task. An ID the script marked covered, or one you just tag-autofixed, is NOT a T2b candidate — routing it would contradict its `covered` status.
- **T2c: Task atomicity (mirror of the /order.tasks ≤3-spec-ID cap).** Detect tasks that name many behaviors but do not schedule them atomically. Apply the three sub-rules below in order:
  - **T2c-i — the defect.** An IMPLEMENTATION task whose paraphrase enumerates more than ~3 spec IDs driving *distinct* behaviors (e.g. "implement REQ-003..REQ-009, INV-001..INV-006" in one task) is a **kitchen-sink defect** — even though the script may mark every ID "covered" because they all appear in that one line. This is exactly the shape that tempts a false "covered" verdict: the work is named but not atomically scheduled, so `/order.code` cannot execute or verify it discretely. → **Route** to `/order.tasks` to split the task into one per coherent behavior. Severity: **HIGH** if the bloated task is on the P1/MVP path (it makes MVP delivery unverifiable), else **MEDIUM**.
  - **T2c-ii — classify by what the task DOES, not by ID count.** VERIFICATION/GATE tasks are exempt from the cap, but the exemption is earned by behavior, not phrasing: a task is *verification* ONLY if it merely ASSERTS existing behaviour via a test-run/gate command (e.g. "Run `yarn test`, assert AC-001..AC-008 pass"). A task that PRODUCES code/schema/routes is *implementation* and is subject to the ≤3 cap even if it lists few IDs. Do NOT grant the exemption to a code-producing task just because it is worded to sound like a check.
  - **T2c-iii — TEST tasks are not implementation tasks.** A TEST task (writes test cases; lives in a "Tests (Write First...)" section) is NOT an implementation task for the ≤3 cap and is NOT auto-blocked merely by enumerating several ACs: a single integration test legitimately exercises ONE coherent user-flow spanning multiple ACs (e.g. create→list→soft-delete→verify-exclusion is one scenario covering AC-001/002/004/005). Apply T2c to a test task ONLY if it bundles UNRELATED scenarios that share no flow (a genuine grab-bag), and then at **MEDIUM, never HIGH** — a fat test reduces granularity but does NOT make MVP unbuildable the way a fat production task does. The **HIGH** cap is reserved for IMPLEMENTATION (code/schema/route-producing) tasks on the P1 path.

#### T3. E-M-C Ordering

- T3a: Phase 1 (Expand) tasks are **additive only** (read descriptions, not just labels). A destructive step in Expand → **Auto-fix** (move to the correct phase) when unambiguous; else **Route**.
- T3b: Story phases follow UJ priority order from spec §14 (P1 before P2). Out-of-order with a single correct ordering → **Auto-fix** (reorder).
- T3c: The Contract phase begins with a GATE task; **no destructive task** precedes that GATE. Missing GATE → **Auto-fix** (insert it). A destructive task ahead of it → **Auto-fix** (move after GATE) if placement is unambiguous; else **Route**.

#### T4. Test-First Discipline

- T4a: Within each story phase, test tasks **precede** implementation (classify by description). A clear test-after-impl pair → **Auto-fix** (swap order).
- T4b: Each story phase is **closed by a verification task** asserting the story's ACs. Missing → **Auto-fix** (append one referencing that story's AC IDs).
- T4c: Test tasks state the expectation to **fail first** (red). Missing red-state note → **Auto-fix** (add it) where the test's intent is clear.

#### T5. SC Buildability

- T5a: Each Success Criterion (spec §2) implying **buildable work** (load tests, security tooling, performance assertions) is reflected by ≥1 task; post-launch / business KPIs exempt. A buildable SC with no task → **Route** (the realizing task is content owned by `/order.tasks`). The gate never picks how the SC is realized.

#### T6. Task Format

- T6a: Each task is **actionable and self-contained**: exact file path + spec IDs + short paraphrase. A vague task ("handle errors") → **Auto-fix** by enriching from plan when the target is unambiguous in plan; else **Route**.
- T6b: `[US#]` tags trace each implementation task to a story; `[P]` semantics respected at description level. Missing `[US#]` resolvable from context → **Auto-fix**. A `[P]` whose description depends on an adjacent `[P]`'s output → **Auto-fix** (remove the offending `[P]`). NOTE: **absence of `[P]` is NEVER a finding** — sequential is always valid; never add `[P]`.
- T6c: Cross-story dependency breaking independent-testability (a P1 task depending on a P2 task) → **Route** (re-sequencing stories touches the delivery contract).

#### T7. Upstream Reroute (route upward, never compensate)

- T7a: Where tasks cannot be made faithful or complete because the **root defect lives upstream** (a wrong/inadequate plan Mechanism, a spec ambiguity, a requirement-quality issue) → **Route** to `/order.plan` or `/order.spec` describing the suspected root. Do NOT patch tasks to paper over it; do NOT edit upstream artifacts from here; do NOT silently invent the missing decision. Note in *Impact if unresolved* that tasks stay blocked until the root is fixed. Severity inherits the affected obligation's MVP-scope (CRITICAL if it blocks a P1 story).

### 4. Severity Assignment

- **CRITICAL**: a P1/MVP AC has no task (true coverage gap); a destructive task precedes the Contract GATE and placement is ambiguous; a task invents a decision that changes MVP scope; an upstream defect (T7) blocking a P1 story.
- **HIGH**: tests ordered after implementation within a P1 story; a P1 story phase with no verification task; a task references a non-existent plan mechanism on the MVP path; an SC requiring buildable work with no task; **a kitchen-sink implementation task (>3 driving spec IDs) on the P1/MVP path (T2c)**; **every imported mechanical HIGH (e.g. an M2 coverage gap on a P1 AC) — these keep the script's severity, never downgraded.**
- **MEDIUM**: non-MVP EDGE/INV uncovered; a vague/non-self-contained task; an upstream reroute (`T7-*`) on a non-MVP story; a cross-story dependency on a non-MVP story; **T0-002 (suspected script-pattern bug — note only, the finding is still imported)**.
- **LOW**: cosmetic format issues; minor paraphrase verbosity; redundant ID listing; **a desire for finer-grained per-ID test assertions when the ID is already covered by a broad integration test or range-asserting GATE (never HIGH, never a Route, never a BLOCK driver)**.

**MVP-scope definition**: "MVP-scope" = stories whose UJ priority is P1 in spec §14. A HIGH finding on a P1 story blocks; the same class on P2+ does not auto-block.

### 5. Determine Verdict

**Step 1 — apply the exit-code floor (Invariant 2):** if the script returned exit 1, the verdict is already non-PASS; you may only decide between 🔀 ROUTING REQUIRED and ⛔ BLOCK. If exit 0 or 3, the floor is open and the verdict is decided by the T-pass findings below.

**Step 1b — mandatory reconciliation (do this before writing anything):** the exit code reflects the **severity of `findings[]`**, NOT the completeness of `coverage[]`. These are TWO INDEPENDENT axes and you must not conflate them:

- **Coverage axis (`coverage[]`)** — every ID with `"status":"uncovered"` in the script's `coverage[]` array is rendered `UNCOVERED (script)` in the Coverage Matrix, **regardless of the exit code**. The script MAY legitimately return exit 0 while `coverage[]` still contains `uncovered` IDs — this happens when those IDs did not escalate into a CRITICAL/HIGH `findings[]` entry. That is a CONSISTENT state, not a contradiction. An `uncovered` ID stays `UNCOVERED (script)`, drives a Route (or a justified severity escalation), but does NOT by itself force exit 1. Do NOT "reconcile" it by flipping the status to `covered`.
- **Severity axis (`findings[]`)** — reconcile the exit code against `findings[]` ONLY: if you record (or import) any finding whose severity is CRITICAL or HIGH, then `summary.exit_code` MUST be 1. If you are about to write `exit code: 0` next to a CRITICAL/HIGH finding, you have misread the field — STOP, re-read `summary.exit_code`, and reconcile. Never edit the exit code to fit a desired verdict.

The two checks are orthogonal: a clean `exit 0` with several `UNCOVERED (script)` rows is valid and may still be a ✅ PASS (if those uncovered IDs are semantically resolved to Notes / tag-autofixes and none escalated to C/H). A `UNCOVERED (script)` row is therefore NOT evidence the exit code is wrong.

**Step 1c — MANDATORY auto-fix / coverage reconciliation (run after ALL tag-autofixes are applied, before Findings are finalized and before the verdict is computed).** This step exists because the single most common gate error is contradicting yourself: tag-autofixing an ID (asserting a task produces it) and then ALSO routing that same ID as "uncovered / needs a task". A tag-autofix is NOT cosmetic — per the Invariant 1 corollary, applying it makes the ID `covered` with the identical force of the script's own `covered` verdict. The SOURCE of `covered` (script vs. your autofix) makes NO difference; treat them the same.

Execute literally:

1. Build the **covered set** = every ID the script marked `covered` ∪ every ID you tag-autofixed this run (now `covered (tag auto-fixed)`).
2. Walk EVERY finding. **DELETE** any finding that asserts "uncovered" / "no task covers/tests this" / "needs a task" / a T2b coverage gap **whose target ID is in the covered set.** Such a finding is a double-count; the uncovered finding is the bug, not the coverage. Removing it is mandatory, not optional.
3. You already apply this deletion correctly for script-covered IDs (you would drop an uncovered finding on an ID the script reports covered). Apply the EXACT same deletion to IDs YOU made covered via autofix — do NOT exempt your own autofixes from the reconciliation you apply to the script's verdict.
4. **"Covered" never requires a dedicated one-ID test.** A single integration test, or a GATE asserting a range ("assert AC-001..AC-008 pass"), covers every ID in that range (consistent with T2c-iii). Wanting finer-grained per-AC assertions is at most a LOW Note — NEVER a HIGH, NEVER a Route, NEVER a BLOCK driver.
5. After the walk, a **genuine** coverage gap (the only kind that may remain as a Route) is an ID that is ALL of: script-uncovered **AND** not tag-autofixed by you **AND** has no implementing task **AND** no test/GATE asserting it. Everything else has been reconciled away.

Cross-check before proceeding: no ID may appear simultaneously as `covered` / `covered (tag auto-fixed)` in the Coverage Matrix AND inside any Route/uncovered finding. If one does, you have not finished Step 1c — go back and delete the contradictory finding.

**Step 2 — apply semantic findings (can only raise severity, never lower the floor):**

- 🔀 **ROUTING REQUIRED** if any Routing block exists (mechanical or semantic) — tasks.md needs an author pass via `/order.tasks` (or `/order.plan` / `/order.spec`) before it is clean.
- ⛔ **BLOCK** if any CRITICAL remains, or any HIGH affects MVP-scope. A routed CRITICAL/HIGH still BLOCKS the pipeline until the owner resolves it (BLOCK and ROUTING co-display: "⛔ BLOCK — routing required").
- ✅ **PASS** only if there are zero Routing blocks AND zero unresolved CRITICAL/HIGH AND the script did NOT return exit 1. Auto-fixes applied and LOW notes are compatible with PASS.

**Step 2a — BLOCK floor self-audit (run immediately before stamping a BLOCK).** A BLOCK may rest on a HIGH/CRITICAL coverage-gap finding ONLY if that ID *survived Step 1c* — i.e. it is script-uncovered AND not tag-autofixed by you. If every HIGH/CRITICAL driving the BLOCK targets an ID you tag-autofixed (now `covered (tag auto-fixed)`) or one the script marked covered, the BLOCK is **spurious**: those findings should have been deleted in Step 1c. Drop them and recompute the verdict. Corroborating signal: a `summary.exit_code` of 0 with `summary.critical = 0` and `summary.high = 0` is strong evidence that no real blocking finding exists — do NOT out-vote the script with a self-authored finding you have already contradicted. (Genuine non-autofixed, script-uncovered P1 gaps still BLOCK — this audit removes only the self-contradictory ones.)

Rerunning a clean tasks.md must produce consistent IDs, counts, and verdict.

> **What "HIGH affects MVP-scope" means for BLOCK (be precise):** a HIGH blocks
> ONLY if the defect makes the P1/MVP work itself uncovered, mis-ordered to the
> point of being unbuildable, or unfaithful — e.g. a true P1 coverage gap, tests
> ordered after impl in a P1 story, a P1 story with no verification task, a P1
> task referencing a non-existent mechanism. A finding that touches an MVP story
> but does NOT break its coverage/ordering/faithfulness is NOT MVP-blocking.
> When the only HIGHs are non-MVP or cosmetic-but-routed and there is no
> CRITICAL → verdict is 🔀 ROUTING REQUIRED, not ⛔ BLOCK. Rule of thumb: BLOCK
> needs a defect that breaks MVP delivery; ROUTING needs a defect that needs the
> author but doesn't break MVP. A "P1 coverage gap" that you yourself closed with
> a tag-autofix this run is NOT a gap — it was reconciled away in Step 1c and must
> not resurface as a BLOCK driver.

> **Infrastructure signals never drive the verdict.** T0-001 (validator
> unavailable) and exit-code-3 "partial scope" are *tooling/coverage* signals,
> not task defects. They are NEVER counted as a HIGH-affecting-MVP for BLOCK
> purposes. If the only non-LOW finding is T0-001, the verdict is decided purely
> by the T-pass findings (✅ PASS if none). Surface T0-001 (when genuinely
> present) as a one-line degraded-mode banner in the report so the user knows
> coverage was reduced — that is all it does. **Note the distinction from
> Invariant 2: exit 1 (real findings) IS a floor; exit 3 (absent upstream) is
> not.**

### 6. Produce Gate Report — ALWAYS WRITTEN (chat + file, every run)

**Persistence rule (simple and absolute):**

- **Always** write the report to `REPORT` — every run, every verdict (✅ PASS, ⛔ BLOCK, 🔀 ROUTING REQUIRED) — overwrite, never append, stamp the header with date and verdict.
- A PASS report is a *positive record* that the gate ran and tasks.md is clean; it is NOT noise. The only state in which `REPORT` does not exist is **the gate never ran** — that is the whole point.
- The header stamp, the verdict line, and the Metrics line MUST agree. Never write one verdict in the header and another in the metrics.

Report body (merge mechanical `M*` and semantic `T*` findings):

```markdown
<!-- tasks-report.md — generated by /order.tasks-check · {DATE} · verdict: {VERDICT} · overwritten each run -->

## Tasks Gate Report (tasks.md ← plan.md)

**Verdict**: ✅ PASS | ⛔ BLOCK | 🔀 ROUTING REQUIRED

{If T0-001 present: one-line "⚠ DEGRADED — mechanical validator did not run (T0-001); the coverage/format/[P] layer was skipped and findings below are LLM-only." banner here. Omit entirely otherwise.}

### Auto-Fixed (applied automatically — mechanical / structural meaning-preserving only)
| ID | What was changed in tasks.md | Why meaning-preserving |
|----|------------------------------|------------------------|
(empty if none. Record ONLY changes actually written to tasks.md this run — one row per task LINE edited. A "no change needed" / "tag already present" / "already exists" row is forbidden: if nothing was written, the row does not exist.)

### Routing Required (owned by /order.tasks / .plan / .spec — gate did NOT author content)
(render each as the Routing block format; batched. "None" if PASS.)

### Findings
| ID | Source | Severity | Disposition | Task / Location | Summary |
|----|--------|----------|-------------|-----------------|---------|
| M2-001 | mechanical | CRITICAL | Route | tasks.md | AC-003 (P1) not referenced by any task |
| T4a-002 | semantic | HIGH | Auto-fixed | T013/T014 | Impl preceded its test in US2 — order swapped |
| T1a-003 | semantic | CRITICAL | Route | T021 | Task invents an endpoint absent from plan |
(on PASS, this table may legitimately be empty or carry only LOW notes — render it anyway. No row here may target an ID that the Coverage Matrix shows as covered / covered (tag auto-fixed) with an "uncovered"/"needs a task" summary — Step 1c deletes those.)

### Coverage Matrix
| Spec ID | Task IDs | Status |
|---------|----------|--------|
(render from the script `coverage` array on every run, including PASS. The **Status** column is a CLOSED vocabulary — use exactly one of: `covered` · `UNCOVERED (script)` · `covered (tag auto-fixed)`. No free-text status, no parenthetical justifications, NEVER `covered (script false negative)` or any variant that overturns the script. An uncovered ID stays `UNCOVERED (script)` and drives a Route. `covered (tag auto-fixed)` is permitted ONLY when a T2a tag-autofix was actually applied to tasks.md this run — never as a way to argue an uncovered ID is "really fine". Any ID marked `covered` or `covered (tag auto-fixed)` here MUST NOT appear in any uncovered/coverage-gap Finding above — Step 1c enforces this.)

### Metrics
- Inventory (from script): REQ / AC / EDGE / INV / SC / tasks — these come from the script's `inventory` object, use verbatim.
- Findings by severity: C/H/M/L counts (script + semantic)
- Auto-fixed: N · Routing required: M · upstream reroutes (T7): K
- Script exit code: {0 | 1 | 3} (copied verbatim from `summary.exit_code` — NEVER altered to fit a desired verdict) · verdict floor applied: {none | non-PASS} · exit/findings reconciled: {yes} · autofix/coverage reconciled (Step 1c): {yes}
- Mechanical scope: {full, no C/H findings (exit 0) | full, C/H findings present (exit 1) | full, upstream deferred (exit 3) | DEGRADED — validator did not run (T0-001), coverage/format/[P] skipped}
- Report file: always written to checklists/tasks-report.md
```

After rendering, state in one line the `REPORT` path where the file was written (always).

### 7. Next Actions

The gate's responsibilities end at detection, mechanical/structural repair, routing, and writing the report file. For each finding:

- **Mechanical / structural meaning-preserving** → already auto-fixed (see Auto-Fixed); no user action.
- **Content / coverage** → see the Routing block; the user resolves it by running the suggested `/order.tasks "..."`. The gate did not and will not author this content.
- **Upstream root cause (`T7`)** → see the Routing block; the user resolves it via `/order.plan "..."` or `/order.spec "..."`. Tasks never compensate for an upstream gap.
- **T0-001 (degraded)** → the validator failed to run; fix the tooling and re-run so the mechanical layer is restored. **T0-002** → suspected script-pattern bug; report to the maintainer, but the imported finding still stands.

Recommended loop: run the routed commands (batch the requests if convenient), then **re-run `/order.tasks-check`** to confirm tasks.md is now clean. The gate is idempotent: a faithful, fully-covered tasks.md yields ✅ PASS and writes a clean PASS report.

Downstream note: once tasks.md is clean it is ready for `/order.code`. Repo state, drift-over-time, or whole-system concerns → `/order.analyze`, not acted on here.

## Post-Execution Checks

Run the **`after_tasks_check`** phase per `.orderspec/memory/hooks-protocol.md`.

## Operating Principles

- **The script is ground truth (Invariant 1)**: mechanical findings are deterministic facts, imported at their severity, never overruled, never called "false positives" / "false negatives" — not in the report and not in your reasoning. You may escalate severity with justification but never downgrade. A suspected bad pattern is T0-002 — the finding still stands. If you think an uncovered ID is really implemented, the legal move is a T2a tag-autofix, never an argument.
- **A tag-autofix is a coverage assertion that binds you symmetrically (Invariant 1 corollary, Step 1c)**: the moment you tag-autofix an ID it is `covered` with the same force as a script-covered ID; you may NEVER then route it as "uncovered / needs a task". Treating your own autofix as cosmetics while still flagging the ID as a gap is a self-contradiction — Step 1c deletes such findings and Step 2a prevents them from driving a spurious BLOCK.
- **"Covered" never requires a per-ID test**: one integration test or a range-asserting GATE covers every ID in its range; wanting finer granularity is a LOW Note at most, never a Route or BLOCK driver.
- **Coverage status and exit code are independent axes (Step 1b)**: `coverage[]` drives the Matrix; `findings[]` severity drives the exit code. `exit 0` with `UNCOVERED (script)` rows is a valid, consistent state — reconcile the exit code against C/H findings only, never against coverage completeness.
- **Exit code is the verdict floor (Invariant 2)**: exit 1 → cannot PASS. Semantic findings raise severity, never lower it.
- **Always write the report**: every run, every verdict, including PASS. "No file" means "the gate did not run" — never "tasks.md is clean".
- **Semantic passes are mandatory and independent**: a clean script result never lets you skip T1–T7. The full Findings table and Coverage Matrix appear on every run.
- **Pure inspector for content**: the gate detects, repairs structure, and routes; it NEVER authors a task or fills a true coverage gap.
- **Structural auto-fix is methodology-driven, not content**: reordering, GATE/verification insertion, and tag fixes follow fixed E-M-C / test-first rules — meaning-preserving. Creating or changing what a task *does* is always a Route.
- **Auto-fix touches task lines only**: never edit the Traceability Matrix, Files-Touched, or any derived section; never scatter one ID across multiple task lines to balance a table. A disagreement between a task line and a derived table is a Route, not a rewrite.
- **One narrow write permission on the tasks**: auto-fix applies ONLY to mechanical / structural meaning-preserving defects with a single obvious correction. When in doubt, Route — never Auto-fix.
- **Route, don't ask-and-apply**: content/coverage findings become Routing blocks with a ready-to-run `/order.tasks "..."` (or `/order.plan "..."` / `/order.spec "..."`).
- **Local-stage stance**: validate tasks.md against plan.md (and spec for the ID vocabulary) only; never reach into the repo or reason about time — that is `/order.analyze`.
- **Trust a passed upstream `*-check`, route an upstream defect upward**: an upstream root cause is routed to its owner (T7), never patched around in tasks.
- **Detect coverage gaps, but never fill them**: a true coverage gap is the core finding type here — reported as a Route, never authored.
- **NEVER hallucinate missing sections** — report absences accurately.
- Mechanics belong to the script; **only task-intent meaning belongs to your LLM tokens**.
- Minimal high-signal tokens: cite specific task IDs, cap at 25 findings, aggregate overflow.
- A P1/MVP coverage gap is always at least HIGH; a destructive task before the GATE with ambiguous placement is always CRITICAL — both routed/auto-fixed per disposition, both can BLOCK.
- Under-parallelization is never a defect; absence of `[P]` needs no remediation.

## Context

$ARGUMENTS
