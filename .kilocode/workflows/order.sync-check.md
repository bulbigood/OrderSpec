---
description: Cross-artifact synchronization gate. NOT a pipeline stage and NOT a per-document validator — an event-triggered inspector run when something has shifted one artifact relative to the others outside the normal owner→gate flow: a merge/rebase/PR-conflict, a long-lived branch, a hand-edit, or a skipped per-stage check. Detects temporal drift, cross-version ID collisions after a merge, repo-staleness of plan's physical mapping, cross-artifact contradictions, and whole-system constitution alignment. Mechanical traceability via validate-traceability.sh, plus git diff against the merge-base when a merge is in progress. Inspects ARTIFACTS + repo, never the implementation delta — code-vs-contract is /order.code-check. Auto-fixes only cross-artifact terminology drift and stale ID-references; routes every source-of-truth / drift / collision / contradiction / constitution finding to the owning artifact's command. Never authors content, never deletes or regenerates artifacts, never merges or resolves a conflict — any reconciliation is routed to the owner, never performed by the gate.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## What This Gate Is (and Is Not)

`sync-check` is **not a stage** in the `/order.spec → /order.plan → /order.tasks → /order.code` flow, and it is **not** a per-document validator. Per-document validity is owned by the stage gates:
- `/order.spec-check` → spec.md is a valid, self-consistent, testable WHAT-contract.
- `/order.plan-check` → plan.md is correctly derived from spec + repo *at plan time*.
- `/order.tasks-check` → tasks.md is correctly derived from plan.
- `/order.code-check` → the written code faithfully implements spec + plan (the implementation delta).

`sync-check` owns the **orthogonal, irreducible** layer that no single-document, single-moment check can capture: **are the artifacts still synchronized with each other and with the repo right now**, after some event has moved one relative to the others. It is **event-triggered**, not stage-triggered.

The events that desynchronize artifacts:
1. **Merge / rebase / PR-conflict** — two histories diverged; after slicing them together, spec/plan/tasks/repo may contradict *across versions* (the primary, canonical case).
2. **Long-lived branch** — `main` moved ahead (renames, deletions, sibling features, new constitution principles) while the feature was being built.
3. **Hand-edit** — an artifact was edited directly, bypassing its owner command, so downstream references may have silently drifted.
4. **Skipped stage gate** — a `*-check` did not run, so a class of per-document defect may have reached the assembly.

What it inspects: **the artifacts (spec/plan/tasks), the constitution, and the repository snapshot** — plus, when a merge is in progress, the **git diff against the merge-base**. What it does **NOT** inspect: the **implementation delta** (does the written code do what the contract says). Code-vs-contract is `/order.code-check`'s job — see *Division With code-check*.

**Division of responsibility:** like every OrderSpec gate, `sync-check` is a **pure inspector**. It performs only **mechanical / meaning-preserving** auto-fixes (cross-artifact terminology normalization to the glossary; a stale ID-reference corrected to an *unchanged* upstream ID). Everything else — and that is the norm here, because drift, collisions, and contradictions are inherently *"which side is the source of truth?"* questions — is surfaced as a **Routing block** naming the owning command (`/order.spec`, `/order.plan`, or `/order.tasks`). The gate **never** authors content, **never** deletes or regenerates an artifact, and — critically for the merge case — **never merges, resolves a conflict, or picks a winning version**: reconciliation is a recommendation routed to the owner, never an action the gate performs.

## Division With code-check (the merge has two axes)

A merge/PR conflict desynchronizes along **two independent axes**, handled by two different gates:

| Axis | What diverged | Gate | When |
|------|---------------|------|------|
| **Artifacts** | spec/plan/tasks/repo-snapshot disagree across versions | **`sync-check`** (this gate) | conflict still open, or code **not yet** merged |
| **Code** | the merged code no longer implements the current contract | **`/order.code-check`** | conflict resolved by hand, code **already** merged |

- **Conflict still open, or you resolved artifacts but haven't touched code** → run **`sync-check`** first: it diffs against the merge-base, finds cross-version artifact divergence, and routes reconciliation to owners *before* any code is rebuilt. Safest point — code is untouched.
- **PR was resolved manually and the code is already integrated** → `sync-check` can still confirm the *artifacts* are consistent, but it cannot tell whether the hand-merged **code** matches them. For that, run **`/order.code-check`**. If `sync-check` detects that code-affecting paths were touched in the merge, it emits a routing pointer to `code-check` rather than pretending to verify the code itself.

`sync-check` never reads or judges source code semantics. It reasons about artifacts + paths + git history of artifacts. Code semantics belong to `code-check`.

## When to Run

Conditional and **event-driven** — run it when at least one holds (ordered by how strongly it implies desync):

- A **merge / rebase / PR-conflict** touched any of spec/plan/tasks, or touched repo paths referenced by plan's `[MOD]`/`[NEW]`. *(Run after resolving git conflicts, before re-running `/order.code`.)*
- You are **integrating a long-lived branch** and `main` has moved ahead.
- Any artifact was **hand-edited** after generation, bypassing its owner command.
- A relevant `*-check` was **skipped** for any stage.
- You took over a **branch authored by someone/something else** and want a fresh-context, whole-system consistency verdict.

On a clean, single-session, end-to-end run where every `*-check` passed and nothing diverged afterward, this gate is usually green — skipping it is acceptable. It earns its cost precisely when artifacts moved **outside** the normal flow.

## Pre-Execution Checks

**Check for extension hooks (before analysis)**:
- If `.specify/extensions.yml` exists, read entries under `hooks.before_sync_check`. If missing or unparsable YAML, skip silently.
- Filter out hooks with `enabled: false` (absent `enabled` = enabled).
- Do **not** evaluate hook `condition` expressions: hooks with no/empty `condition` are executable; hooks with a non-empty `condition` are skipped (left to HookExecutor).
- For each executable hook, output by `optional` flag:
  - **Optional hook** (`optional: true`):
    ```
    ## Extension Hooks

    **Optional Pre-Hook**: {extension}
    Command: `/{command}`
    Description: {description}

    Prompt: {prompt}
    To execute: `/{command}`
    ```
  - **Mandatory hook** (`optional: false`):
    ```
    ## Extension Hooks

    **Automatic Pre-Hook**: {extension}
    Executing: `/{command}`
    EXECUTE_COMMAND: {command}

    Wait for the result of the hook command before proceeding to the Goal.
    ```

## Goal

Act as an **independent synchronization inspector with fresh context**. You did not write these artifacts and you do not re-judge each in isolation — that is the `*-check` prompts' job. Your job is the **assembly**: are spec, plan, tasks, the repository, and the constitution mutually consistent **right now**, after whatever event triggered this run? Determine this, fix only mechanical cross-artifact defects, route the rest:

- **Integrity of the cross-artifact chain** REQ → UJ → AC → Task (mechanical, via script).
- **Merge / divergence reconciliation** — when a merge is in progress, cross-version ID collisions and clauses surviving from a superseded version (via git diff against the merge-base).
- **Temporal drift** between stages.
- **Repo-staleness** of plan's physical mapping (especially paths a sibling branch may have renamed/deleted).
- **Cross-artifact contradictions** and **terminology coherence**.
- **Whole-system constitution alignment**.

## Delegated (out of scope unless degraded)

Owned by other prompts. Do NOT enumerate findings for them in normal operation. If a `*-check` was demonstrably skipped, see the Degradation Rule.

- Requirement quality / ambiguity / vague adjectives, spec self-consistency, glossary, AC form, spec purity → `/order.spec` + `/order.spec-check`.
- plan↔spec completeness, mechanism adequacy, plan role-purity, plan not duplicating spec, stack consistency → `/order.plan` + `/order.plan-check`.
- tasks E-M-C ordering, coverage self-validation, SC→task reflection, test-first, task format/numbering → `/order.tasks` + `/order.tasks-check`.
- **code-vs-contract** — does the written/merged code implement spec + plan → `/order.code` + `/order.code-check`. `sync-check` never judges code semantics.

## Operating Constraints

- **INSPECTOR + MECHANIC**: you MAY modify artifacts ONLY for mechanical / meaning-preserving auto-fixes (see boundary). You MUST NOT author content, resolve a source-of-truth question by writing one side's version, merge two versions, or delete/regenerate any artifact.
- **Auto-fix vs Route boundary**:
  - **Auto-fix** ONLY when the resolution is deterministic and does NOT change contract or scope — for this gate, almost exclusively: **cross-artifact terminology drift** normalized to spec's glossary, or a downstream artifact's stale ID-reference corrected to match an **unchanged** upstream ID (a pure rename with one unambiguous target). Apply in place, record in **Auto-Fixed**.
  - **Route** for everything else — and that is the norm: drift, cross-version collisions, contradictions, repo-staleness, constitution conflicts are all "which side governs?" judgments. Emit a **Routing block** naming the owning command. Examples: spec and plan disagree on scope (→ spec or plan, depending on the chosen source of truth); a merge brought in two different `REQ-018`s (→ spec to renumber/consolidate); a task targets a mechanism removed from plan (→ plan or tasks); a `[MOD]` path a sibling branch renamed (→ plan); a stack choice now conflicts with a CON (→ plan or spec); the assembled system violates a constitution MUST (→ the offending artifact's owner).
  - **When in doubt, Route — never Auto-fix.** Source-of-truth resolution is never deterministic.
- **No destruction, no merging, no cascade execution**: the gate NEVER deletes, regenerates, or merges artifacts, and NEVER resolves a git conflict by choosing a side. A cascade ("root is in spec → plan and tasks need regenerating") and a merge reconciliation ("new spec from main wins → realign plan") are both presented as a **Routing block** recommending the ordered sequence of owner commands (e.g., "Run `/order.spec "..."`, then re-run `/order.plan` and `/order.tasks`"). The architect executes them; the gate does not. This is structural, not a policy the gate could bypass.
- **Constitution authority**: conflicts with `.specify/memory/constitution.md` are CRITICAL → Route. The principle is never diluted; HOW to comply is the owner's decision.
- **No duplication of mechanical work**: trust the script's findings; do not re-count IDs or re-verify paths by hand unless the script is unavailable.
- **No duplication of per-stage work**: trust a passed `*-check`; do not re-run its analysis unless the Degradation Rule applies.
- **No code-semantics work**: never read source files to judge whether they implement the contract — that is `code-check`. You may only check whether *paths* exist (repo-staleness), not what the code inside them does.

## Routing Block Format

When a finding cannot be auto-fixed, emit exactly this; **batch all routing blocks** at the end:

```
### Routing Required: {short title}

**Finding**: {the cross-artifact conflict / drift / staleness / cross-version collision}
**Location**: {artifacts / IDs / paths / branch sides involved}
**Why owner, not gate**: {source-of-truth judgment, contract/scope change, merge reconciliation, or cascade — must go through the artifact's author}
**Impact if unresolved**: {what breaks at /order.code time or at integration}
**Suggested direction**: {1–2 candidate resolutions, incl. which side/artifact is the likely source of truth; advisory only}
**Run**: `/order.{spec|plan|tasks} "{ready-to-run request}"`  (for a cascade/reconciliation, list the ordered sequence of commands; for code drift, point to `/order.code-check`)
```

The `Run` line is a recommendation to the owner, not an action the gate performs.

## Execution Steps

### 1. Initialize

Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` once from repo root; parse FEATURE_DIR and AVAILABLE_DOCS. Derive: SPEC = `FEATURE_DIR/spec.md`, PLAN = `FEATURE_DIR/plan.md`, TASKS = `FEATURE_DIR/tasks.md`. Abort with instructions if any required file is missing. For single quotes in args use `'I'\''m Groot'` or double quotes.

**Detect git state** (drives whether the merge-reconciliation pass runs):
- A merge/rebase is in progress if `.git/MERGE_HEAD` (or `REBASE_HEAD`) exists, OR `git diff --name-only --diff-filter=U` lists any unmerged paths, OR `$ARGUMENTS` says a merge/PR conflict was just resolved.
- If so, record `MERGE_MODE = true` and resolve `MERGE_BASE` via `git merge-base HEAD MERGE_HEAD` (fall back to the user-named base in `$ARGUMENTS`). Note which of spec/plan/tasks and which plan-referenced paths appear in `git diff --name-only $MERGE_BASE...`.
- Otherwise `MERGE_MODE = false`; skip pass S8.
- If git is unavailable, set `MERGE_MODE = false` and note it once; S8 is skipped (the static passes still run).

### 2. Mechanical Validation (script)

Run:

```bash
.specify/scripts/bash/validate-traceability.sh --json "$FEATURE_DIR"
```

- Parse `summary`, `inventory`, `coverage`, `findings` (IDs `M1`–`M14`). Import all script findings as-is (keep IDs/severities).
- You MAY escalate severity with justification (an uncovered AC of the MVP story → CRITICAL).
- The script covers the mechanical core (M1–M5 chain, M8/M10 path & repo-staleness, M11 timestamp drift, M12 [P]-disjointness). Do not re-perform by hand.
- **Fallback**: if the script is missing/fails, emit HIGH `S0-001` ("mechanical validator unavailable — degraded mode") and a compact manual pass over only: dangling IDs, AC/EDGE/INV → task coverage, task numbering, `[MOD]`/`[NEW]` path existence. Keep it brief.

### 3. Semantic Detection Passes (LLM — cross-stage only, DETECT ONLY)

Load the three artifacts and the constitution. Build minimal internal models — do not dump raw artifacts. Limit to 30 findings total (including M-findings); on overflow drop LOW first, aggregate into one line — never drop a CRITICAL. Stable IDs per pass (S1-001…). Classify each as **Auto-fix** or **Route** (cross-stage findings are predominantly Route).

#### S1. Temporal Drift

- S1a: If the script flagged M11 (timestamp drift), judge whether **real semantic** drift exists. Timestamps only, no divergence → downgrade M11 to LOW (no action). Real divergence (plan no longer reflects spec's current scope/terminology) → **Route**: source-of-truth question — owner is `/order.spec` (if downstream must align to spec) or `/order.plan`/`/order.tasks` (if a deliberate later decision must be promoted into spec).
- S1b: Do tasks reference plan decisions (mechanisms, paths, names) that **still exist** in the current plan? A pure rename with one unambiguous current target → **Auto-fix** (update the reference). A task pointing at a removed mechanism → **Route** (→ plan to restore, or tasks to rewrite).
- S1c: Does spec's current scope (REQ/AC set, §2 Out-of-Scope) still match what plan/tasks assume? Requirements added to spec after downstream froze, or scope removed from spec but still implemented downstream → **Route** (align downstream via `/order.plan`/`/order.tasks`, or promote the downstream decision into spec via `/order.spec`).

#### S2. Repo-Staleness (plan's physical mapping vs reality now)

- S2a: Spot-check 2–3 of plan's Technical Context claims against the actual repo (framework versions in the manifest, key module locations). Divergence → **Route** (→ `/order.plan` to update to current repo; or note the repo regressed).
- S2b: Use the script's M8/M10 for path existence and `[NEW]`/`[MOD]` correctness. Add judgment only where the script cannot: a `[MOD]` file exists but plan assumes a function/export now absent. Sample at most 2 high-risk claims. A vanished target → **Route** (→ `/order.plan`). **You check path/symbol existence only — never what the code does.** In `MERGE_MODE`, prioritize paths the diff shows a sibling branch renamed/deleted.

#### S3. Cross-Artifact Contradictions

- S3a: Contradictions **between** documents only (intra-document conflicts belong to the relevant `*-check`): REQ vs CON, plan-stack vs CON, plan vs constitution, tasks' implied behavior vs spec's contract. Any such → **Route** (name the source-of-truth owner).
- S3b: Near-duplicate or conflicting REQs that survived into plan/tasks and would cause divergent implementation → **Route** (→ `/order.spec` to consolidate).

#### S4. Whole-System Constitution Alignment (independent final re-check)

- S4a: Any artifact element conflicting with a MUST principle, viewed across the whole system → CRITICAL, **Route** to the offending artifact's owner. Defense-in-depth: re-verify the assembled system even if per-stage gates checked constitution per document — the cost of a miss is maximal. In `MERGE_MODE`, pay special attention to constitution principles that the diff shows were **added/changed by the incoming branch** — the feature was designed before they existed.
- S4b: A constitution-mandated gate/section absent from the system as a whole → **Route** (→ the owner that should carry it).

#### S5. Cross-Artifact Terminology Coherence

- S5a: A concept named differently across spec/plan/tasks; canonical term is spec §3 Glossary. Clear canonical + unambiguous synonyms → **Auto-fix** (normalize downstream to canonical). Unclear whether two terms denote the same concept → **Route**.

#### S8. Merge / Divergence Reconciliation (only when `MERGE_MODE = true`)

The artifacts are the result of slicing two diverged histories together. Using the `git diff` against `MERGE_BASE`, detect *cross-version* defects no single-version check can see. **Every S8 finding is Route** — choosing which side governs is a source-of-truth decision owned by the artifact's author; the gate never picks a winner or merges.

- S8a: **Cross-version ID collisions.** The same stable ID (e.g., `REQ-018`) now denotes *different things* on the two sides, or both sides independently appended the same next-free number to different statements. → **Route** (→ `/order.spec` to renumber one side per ID Discipline and reconcile references). CRITICAL if it affects MVP scope, else HIGH.
- S8b: **Superseded clauses surviving the merge.** A REQ/AC/INV that the incoming branch deliberately removed or replaced is still present (or vice versa) — the merge kept a stale version. → **Route** to the owning artifact; state which side appears authoritative as advisory.
- S8c: **Downstream orphaned by an upstream merge.** The incoming branch changed spec/plan in a way that strands the local plan/tasks (a mechanism's spec basis changed; a `[MOD]` path the sibling renamed). → **Route** as an ordered reconciliation sequence (likely `/order.plan` then `/order.tasks`).
- S8d: **Code already integrated.** If the diff shows code-affecting paths (plan's `[MOD]`/`[NEW]` or general source) were changed by the merge and the conflict has been committed, the *artifacts* may be consistent yet the *merged code* may not implement them. → emit one Routing pointer: "merged code touched {paths} — run `/order.code-check` to verify code-vs-contract." This gate does NOT verify the code itself.

#### Degradation Rule (when a `*-check` was skipped)

`*-check` prompts are optional. If you have positive reason a stage's `*-check` did NOT run (user said so in `$ARGUMENTS`, or the script surfaces a class of defect a `*-check` would normally have caught), then for that stage ONLY:
- Emit one MEDIUM finding `S6-00n` as a **Routing block**: "`/order.{stage}-check` appears not to have run — run it for full per-document validation." Optionally note the single most load-bearing property you spot-checked (e.g., for tasks: each P1 AC maps to a task; for plan: the 2–3 highest-priority REQ have a Mechanism) — but only **detect and route**; do NOT author content or re-derive the full per-stage analysis.
- No signal that a `*-check` was skipped → assume it ran; do nothing here.

#### Rerouting Rule (not a pass)

If you incidentally notice requirement-quality issues (ambiguity, vague adjectives without NFR metrics): do NOT enumerate them. Emit one Routing block `S7-001` (MEDIUM): "Requirement-quality issues at {locations} — Run `/order.spec "..."` then re-run `/order.spec-check`."

### 4. Severity Assignment

- **CRITICAL**: constitution MUST violation; AC/REQ with zero coverage blocking baseline functionality; dangling ID breaking traceability of MVP scope; tasks built on a plan decision that no longer exists and blocks MVP; **cross-version ID collision affecting MVP scope (S8a)**.
- **HIGH**: stale plan vs repo (`[MOD]` missing / `[NEW]` already present); cross-artifact contradiction affecting behavior; semantic drift changing MVP scope; **superseded MVP clause surviving a merge (S8b); cross-version collision off the MVP path**.
- **MEDIUM**: cross-artifact terminology drift; uncovered EDGE/INV of non-MVP stories; degradation (`S6-*`); rerouting (`S7-*`); timestamp drift with minor semantic divergence; **a `code-check` pointer (S8d)**.
- **LOW**: cosmetic cross-doc wording; minor redundancy; timestamp-only drift with no semantic divergence.

**MVP-scope**: stories whose UJ priority is P1 in spec §15. A HIGH on a P1 story blocks; the same class on P2+ does not auto-block.

### 5. Produce Gate Report

```markdown
## Sync Gate Report (cross-artifact synchronization)

**Verdict**: ✅ PASS | ⛔ BLOCK | 🔀 ROUTING REQUIRED
**Trigger**: {merge-in-progress | long-lived branch | hand-edit | skipped gate | manual} · Git: {MERGE_MODE on (base {sha}) | off}

### Auto-Fixed (mechanical / meaning-preserving only)
| ID | Artifact | What was changed | Why meaning-preserving |
|----|----------|------------------|------------------------|
(empty if none)

### Routing Required (owned by /order.spec / .plan / .tasks — gate did NOT modify, merge, or regenerate content)
(render each as the Routing block format; batched; cascades & merge reconciliations listed as an ordered command sequence)

### Findings
| ID | Source | Severity | Disposition | Location(s) | Summary |
|----|--------|----------|-------------|-------------|---------|
| M10-001 | script | HIGH | Route | plan.md | [MOD] src/x.js absent from repo |
| S8a-001 | semantic | CRITICAL | Route | spec.md (both sides) | REQ-018 denotes two different requirements after merge |
| S5a-002 | semantic | MEDIUM | Auto-fixed | tasks.md | "session token" normalized to glossary "access token" |

### Coverage Matrix
(from script `coverage` array — render: Spec ID | Task IDs | Status)

### Metrics
- Inventory: REQ / AC / EDGE / INV / UJ / tasks (from script)
- Findings by severity: C/H/M/L counts (script + semantic)
- Auto-fixed: N · Routing required: M
- Merge reconciliation: {n S8 findings | n/a — not in merge mode}
- Per-stage checks: note any stage where a `*-check` appears skipped (from S6-* findings)
- Code verification: {pointer to /order.code-check emitted | not needed}
```

**Verdict rule**: 🔀 ROUTING REQUIRED if any Routing block exists. Independently, ⛔ BLOCK if any CRITICAL remains, or any HIGH affects MVP-scope (P1) stories — a routed CRITICAL/HIGH still BLOCKS until the owner resolves it (BLOCK and ROUTING can co-display: "⛔ BLOCK — routing required"). Otherwise ✅ PASS. If zero issues: success report with coverage statistics. Rerunning an unchanged, consistent system must produce consistent IDs and counts.

### 6. Next Actions

The gate's responsibilities end at detection, mechanical repair, and routing:
- **Mechanical** (terminology / stale-ID rename) → already auto-fixed; no user action.
- **Drift / contradiction / repo-staleness / constitution** → see the Routing block; the user resolves it via the named owner command. The gate did not write a side of the conflict.
- **Merge reconciliation (S8)** → routed as an ordered owner sequence; the architect chooses the source of truth and runs the commands. The gate never merged or picked a side.
- **Cascade** (root in spec → realign plan+tasks) → presented as an ordered Routing sequence (`/order.spec "..."` → `/order.plan` → `/order.tasks`); the architect executes it. The gate never deletes or regenerates anything.
- **Merged code may be stale (S8d)** → run `/order.code-check`; this gate does not verify code-vs-contract.

Route remediation to the cheapest artifact consistent with the likely source of truth. Recommended loop: run the routed commands, then **re-run `/order.sync-check`** to confirm the artifacts are synchronized; if code was touched, follow with **`/order.code-check`**. Idempotent: a synchronized system yields ✅ PASS.

### 7. Post-Execution Hooks

- If `.specify/extensions.yml` is missing, unparsable, or has no `hooks.after_sync_check` entries, skip silently.
- Filter out `enabled: false` hooks (absent = enabled). Do **not** evaluate `condition`: no/empty condition = executable; non-empty condition = skip (left to HookExecutor).
- For each executable hook:
  - **Mandatory** (`optional: false`):
    ```
    ## Extension Hooks

    **Automatic Hook**: {extension}
    Executing: `/{command}`
    EXECUTE_COMMAND: {command}
    ```
  - **Optional** (`optional: true`):
    ```
    ## Extension Hooks

    **Optional Hook**: {extension}
    Command: `/{command}`
    Description: {description}

    Prompt: {prompt}
    To execute: `/{command}`
    ```

## Operating Principles

- **Pure inspector for content**: the gate detects and routes; it NEVER authors content, resolves a source-of-truth question by writing one side, merges two versions, or deletes/regenerates artifacts.
- **No destruction, no merging, structurally**: cascade rollback and merge reconciliation are routed sequences of owner commands, never actions the gate takes. The safeguard is in the architecture, not a rule the gate could bypass.
- **One narrow write permission**: auto-fix applies ONLY to cross-artifact terminology drift and unambiguous stale-ID renames. When in doubt, Route.
- **Route, don't ask-and-apply**: source-of-truth and merge decisions become Routing blocks naming the owner command — never a question whose answer the gate would write.
- **Artifacts + repo, not code**: inspect spec/plan/tasks/constitution/paths and git history of artifacts. Code semantics belong to `/order.code-check`; never read source to judge behavior.
- **Event-triggered, not a stage**: this gate exists for desync events (merge, long branch, hand-edit, skipped gate), not as a mandatory step in the linear flow.
- **System reviewer stance**: check the *assembly*, not each part. Trust passed `*-check` and the script; re-do their work only in the narrow Degradation fallback (detect+route).
- **Fresh context**: ignore self-reported checklists; verify cross-stage facts independently.
- Mechanics belong to the script; per-document validity belongs to `*-check`; code-vs-contract belongs to `code-check`; **only cross-artifact synchronization belongs to your LLM tokens**.
- **NEVER hallucinate missing sections** — report absences accurately.
- Minimal high-signal tokens: cite specific instances, cap at 30 findings, summarize overflow.
- Constitution violations are always CRITICAL — routed, BLOCK.
- Under-parallelization is never a defect; absence of `[P]` needs no remediation.

## Context

$ARGUMENTS
