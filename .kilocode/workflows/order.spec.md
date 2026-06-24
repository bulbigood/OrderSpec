---
description: Create or update the feature specification (SDD) — the stable WHAT-contract with logical architecture. Authors and refines spec.md content; the sole owner of contract content in the pipeline. Detects oversized scope and offers guided decomposition.
handoffs:
  - label: Build Technical Plan
    agent: order.plan
    prompt: Create a plan for the spec. I am building with...
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Role of This Artifact

`spec.md` is the **Software Design Document (SDD)**: the stable source of truth defining **WHAT** the system must do and its **logical architecture** (contracts, data model, behaviour). It is written for an Architect Software Engineer and must be:

- **Repo-independent**: valid regardless of codebase state. No file paths, folder layouts, class names, or library versions — except §6 Constraints (externally imposed tech as `CON-NNN`).
- **Logically complete**: diagrams, ERD, API contracts, and invariants live HERE (not in plan.md).
- **Traceable**: every statement carries a stable ID (REQ/NFR/CON/SC/INV/EDGE/UJ/AC/Q/ASM) that downstream commands reference instead of copying text.

Allowed: logical data model, interface contracts, externally imposed tech constraints (as `CON-NNN`).
Forbidden: physical code structure, implementation steps, task ordering — those belong to `plan.md` / `tasks.md`.

**This command is the sole owner of contract content.** The `*-check` gates may detect defects and auto-fix only mechanical issues, but any change to requirement meaning, scope, thresholds, or any added/removed topic is authored HERE. This command operates in three modes (auto-detected): **create**, **refine**, and **decompose**.

**This command authors content; it does NOT write a self-grading checklist file.** Validation here is *constructive* (rules that shape generation) and *interactive* (it asks the user about genuine high-impact forks). Independent post-hoc review belongs to `/order.spec-check`.

## Pre-Execution Checks

Run the **`before_spec`** phase per `.orderspec/memory/hooks-protocol.md`.

## Mode Detection (run first, before any file operation)

The text after `/order.spec` **is** the request. Do not ask the user to repeat it unless empty.

Determine the operating mode **before touching the filesystem**:

1. **Resolve the target feature.** If the user passed `SPECIFY_FEATURE_DIRECTORY`, use it. Else, if `.orderspec/feature.json` resolves to a directory containing a non-template `spec.md`, treat that as the active feature. Else there is no active spec.
2. **Explicit flags override detection**: `--split` forces **decompose**; `--new` forces **create** even if an active spec exists.
3. **Auto-detect** when no flag is given:
   - **No active `spec.md`** (or it is still the untouched template) → **create**.
   - **Active `spec.md` exists** and the request is a change/addition/clarification → **refine**. **Never overwrite an existing contract with a fresh template.**
   - **Active `spec.md` exists** and the request describes a clearly separate feature → **create** a new feature directory.
4. **Ambiguity signals** (use to decide refine vs new-feature):
   - Request references IDs from existing spec (REQ-007, UJ-002) → **refine**.
   - Request introduces a new entity or actor not in existing spec → **create**.
   - Request neither references IDs nor introduces new → **ask the user once** (blocking question, Clarification Protocol format).
5. **State the detected mode in one line** before proceeding.

## Self Gate Report Intake

Before regenerating `spec.md`, check if a gate report exists at `checklists/spec-report.md`.

```bash
SELF_REPORT="$FEATURE_DIR/{REPORT}"
test -e "$SELF_REPORT" && echo "SELF_REPORT_PRESENT" || echo "SELF_REPORT_ABSENT"
```

- **ABSENT or verdict ✅ PASS** → proceed with `$ARGUMENTS` only.
- **verdict ⛔ BLOCK or 🔀 ROUTING REQUIRED** → this is the authoritative list of defects to resolve:
  1. Read the Routing Required section and Findings table.
  2. Address **every** finding whose `Run` line targets `/order.spec`.
  3. Findings targeting a different command are upstream-blocked — list them in the Completion Report, do NOT silently compensate.
  4. `$ARGUMENTS` is additional guidance layered on top of the report — never a replacement.

## ID Discipline (applies to every mode that writes)

- **Every ID is *defined* on a line in the strict anchor form** `- **PREFIX-NNN**: …` (dash-bullet, bold, exactly 3 digits, at line start). This is the contract the extractor reads. **Mentions** of an ID elsewhere (`Covers:`, prose, diagrams) are references, not definitions. Each ID is defined exactly once.
- **Stable IDs are append-only.** When adding, assign the **next free number** within its prefix. **Never renumber, reuse, or shift existing IDs.**
- **Editing in place** keeps the same ID; the meaning change propagates.
- **Removing** a statement: do not delete silently. Move it to §2 Out-of-Scope with a tombstone ("REQ-014 removed — <reason>").
- **Reference reconciliation** (mandatory after any edit): every `Covers:`, every `EDGE-NNN → covered by AC-NNN`, and every diagram/contract code must still resolve.

## Clarification Protocol

`/order.spec` is **not fully autonomous on consequential decisions**. When the request leaves a genuine fork that materially changes scope, architecture, security, or acceptance — **STOP and ask the user**.

### Fork Awareness Areas

Think about these areas while writing the spec. If any is unresolved AND has ≥2 defensible options AND no reasonable default — ask:

- **Audit/Write Consistency**: Is audit logging strict (mutation fails if audit fails) or best-effort (mutation succeeds, audit is lost)? **MUST be asked.**
- **Visibility of Soft-Deleted Entities**: Do read endpoints (e.g., history/audit) work for soft-deleted entities?
- **Authorization & Scope**: Who can perform each mutating operation? Is the system multi-tenant? Are there ownership rules for entities?
- **Multi-entity write semantics**: atomic / best-effort / compensating? (e.g., task + audit log write)
- **Snapshot/diff semantics**: full state or changed fields for audit/snapshot?
- **Pagination strategy**: shared plugin or custom for new collections?
- **Idempotency**: what happens on repeated mutating calls?
- **Concurrent update resolution**: last-writer-wins / optimistic locking?
- **Retention/cleanup**: unlimited or TTL for cumulative data (audit logs, history)?

### When NOT to ask

Low-impact field defaults, naming, obvious conventional choices → record as `ASM-NNN` silently.

### Question format (max 3 per round, numbered Q1–Q3, prioritised scope > security/privacy > UX > technical)

```markdown
## Question [N]: [Topic]

**Context**: [Quote the relevant spec section / the conflicting IDs]
**What we need to decide**: [Specific question]
**My recommendation**: Option [X] — [one-line why]

| Option | Answer | Implications |
|--------|--------|--------------|
| A      | [Answer] | [Consequence] |
| B      | [Answer] | [Consequence] |
| Custom | Provide your own | [How] |

**Reply** with a choice per question (e.g., "Q1: B, Q2: Custom — …"), **or just write `yes`** to accept my recommendation for every open question.
```

Wait for the reply. On `yes`, apply the recommended option for each question. Then: replace any `[NEEDS CLARIFICATION]` marker, record the decision in §13/§14, reflect it in the normative section (REQ / §9 contract / INV as appropriate), and re-run Self-Validation on the touched items.

## Outline (CREATE mode)

1. **Generate a short name** (2-4 words, action-noun, kebab-case): e.g., "user-auth", "oauth2-api-integration".

2. **Branch creation** (optional, via hook): if a `before_spec` hook ran, note `BRANCH_NAME`/`FEATURE_NUM` from its JSON output. If the user provided `GIT_BRANCH_NAME` explicitly, pass it through to the hook unchanged.

3. **Create the spec feature directory**:
   - If `SPECIFY_FEATURE_DIRECTORY` is set, use it. Otherwise auto-generate under `specs/`:
     - Read `.orderspec/init-options.json`: `feature_numbering` (preferred) or `branch_numbering` (deprecated).
     - `"timestamp"` → prefix `YYYYMMDD-HHMMSS`; `"sequential"` or absent → prefix `NNN` (next available 3-digit number).
     - Directory: `specs/<prefix>-<short-name>`.
   - `mkdir -p SPECIFY_FEATURE_DIRECTORY`; resolve the active `spec-template` via the preset/template resolution stack; copy it to `SPECIFY_FEATURE_DIRECTORY/spec.md`; set `SPEC_FILE`.
   - **Refuse to overwrite**: if `SPEC_FILE` already exists with non-template content, STOP and re-route to *Refine Mode*.
   - Persist to `.orderspec/feature.json`:

     ```json
     { "feature_directory": "specs/003-user-auth" }
     ```

4. Load the resolved `spec-template` to understand required sections.

5. **IF EXISTS**: Load `.orderspec/memory/constitution.md` for governance constraints.

6. **Scope sizing gate (run before filling sections).** Estimate the contract's breadth. If it **exceeds the decomposition threshold**, switch to *Decompose Mode*.
   - **Threshold heuristic** (any two firing → oversized): ≳ 25–30 plausible REQ; ≳ 3 independent functional domains; ≳ 3 distinct primary actor sets; > 2 viable P1-MVP slices that aren't a single end-to-end thread.

7. **Execution flow** (fills the SDD template section by section):
   1. Parse the description. If empty: ERROR "No feature description provided".
   2. Extract: actors, actions, data, constraints, external systems.
   3. **§1 Executive Summary**: concise system/feature overview (≤ 5-10 paragraphs).
   4. **§2 Goal & Scope**: objectives, explicit out-of-scope items, and `SC-NNN` success criteria — measurable, technology-agnostic, verifiable without implementation knowledge.
   5. **§3 Glossary**: domain terms only; omit obvious ones.
   6. **§4 Functional Requirements**: `REQ-NNN`, one testable MUST/MUST NOT statement each.
   7. **§5 NFR / §6 Constraints**: `NFR-NNN` (performance, security, observability), `CON-NNN` (externally imposed: mandated tech, platforms, compliance). If the user input supplied physical paths or library names, capture them HERE as `CON-NNN` — do not let them leak into diagrams or contracts.
   **NFR hallucination guard (CRITICAL)**: You MUST NOT invent quantitative thresholds (e.g., "200ms", "50ms", "99.9%") if they were not explicitly provided in the user input or constitution. If the user did not specify a number, either:
     (a) Omit the NFR entirely (preferred if the quality is not critical).
     (b) Record a neutral, pattern-based `ASM-NNN` (e.g., "uses existing pagination patterns").
     (c) If the quality is critical but the threshold is unknown, use the Clarification Protocol to ask the user.
   Downstream prompts cannot distinguish between user-requested SLAs and model-hallucinated SLAs; inventing numbers forces the pipeline to optimize for non-existent constraints.
   8. **§7 Architecture & Behaviour**: Choose the **minimal set** of Mermaid diagrams to fully describe the contract. Use **logical roles** (Authentication, Validation, Application Service, Persistence), **not** physical code names (Mongoose, Joi, Route Layer, catchAsync). At minimum, include one diagram showing actor-system interaction or data flow. Common choices: system context, sequence (happy + error paths), state machine, data flow. Omit non-applicable diagrams entirely — **never emit placeholder diagrams**. Mermaid safety: ALL node labels MUST use quoted form `X["label"]`. In sequenceDiagram, declare every participant at the top via `participant X` lines.
   9. **§8 Data Model (ERD)** + **§9 API Contracts**: ERD for key entities + relationships; logical API/event contracts. Verbose schemas go inside `<details>` blocks. §9 contracts are the single normative source for status codes and response shapes. Define repeated structures (pagination envelope, error body) ONCE in a shared `<details>` block; per-endpoint entries reference them. Include an **Authorization** subsection if the feature has mutating endpoints or cross-tenant reads — specify actor and permissions per endpoint, or note "deferred to Clarification Protocol" if unresolved.
   10. **§10 Invariants**: `INV-NNN` — conditions that must hold true at all times, deterministic form. Not requirements, not behaviours.

       **Redundant-field consistency**: If multiple fields encode the same state (e.g., `isDeleted` boolean + `deletedAt` timestamp), add an `INV-NNN` defining their relationship (e.g., "isDeleted=true iff deletedAt is non-null"). Without this, broken states (isDeleted=true, deletedAt=null) are not forbidden.

       **Contradiction Grid (required in §10).** For each INV with an absolute quantifier (exactly / always / never / must produce), check it against every NFR and every ASM with a weakening qualifier (best-effort / may fail / non-blocking / eventually / optional). For each pair, output one row:

       ```text
       INV-NNN × {NFR|ASM}-NNN → compatible | CONFLICT — one-line reason
       ```

       Additionally: for any ASM tagged with `[narrowing REQ-NNN]` (or any ASM that implicitly narrows a REQ's semantics), you MUST add a narrowing row to the grid. Do not claim "No REQ × ASM narrowing pairs" if such ASMs exist:

       ```text
       REQ-NNN × ASM-NNN → narrowing — compatible | contradiction — one-line reason
       ```

       Render the full grid as a table in §10. Any **CONFLICT** or **contradiction** MUST be resolved before writing — weaken the INV/REQ or strengthen the NFR/ASM; if non-obvious or high-impact, route to the *Clarification Protocol*. If no absolute-quantifier INV exists and nothing weakens one, state "No absolute INV × weakening NFR/ASM pairs" — do not omit the grid silently.

       For any operation that writes to more than one entity, the spec MUST state failure semantics explicitly: atomic / best-effort / compensating. If undecidable, raise it via the *Clarification Protocol*.
   11. **§11 Edge Cases**: `EDGE-NNN` — boundary conditions, failures, races. If an EDGE case is fully expressed by an AC, write `EDGE-NNN: <one-line name> → covered by AC-NNN` (verify the AC's Given/When/Then actually describes this scenario first).
   12. **§12 User Journeys & Acceptance Criteria**: each `UJ-NNN` is an independently implementable & testable slice, ordered P1..Pn (P1 = MVP). At most 2 UJs may be P1. Each UJ has `Covers: REQ-/NFR-IDs`, priority rationale, independent test description, `Done when` (observable outcome), and `AC-NNN` in Given/When/Then form. **Each AC must directly trace to the specific REQ whose behavior it tests** — not just to the UJ's Covers list. If an AC tests behavior not covered by any REQ, either add a REQ or remove the AC. Every REQ must be covered by ≥1 UJ/AC.
   13. **§13 Open Questions & §14 Assumptions**:
       - Prefer informed defaults for **low-impact** ambiguity; record as `ASM-NNN` with kind tag: `[default]`, `[narrowing REQ-NNN]`, or `[deferred]`. If a default changes externally observable behaviour, it MUST also appear in the normative section (REQ or §9 contract).
       - **High-impact forks are NOT silently defaulted.** Use `[NEEDS CLARIFICATION: question]` + paired `Q-NNN` and surface through the *Clarification Protocol*.
       - An ASM is for decisions a competent reviewer would not contest; a Question is for the rest.

8. Write the specification to `SPEC_FILE`, preserving template section order and headings. Replace all placeholders; remove non-applicable optional sections entirely.

   **ID-anchor reminder**: every stable ID must be *defined* on a line in the strict anchor form `- **PREFIX-NNN**: …`.

9. **Project IDs into machine state (mechanical — via script, never hand-written).** After the spec is written, run:

   ```bash
   FEATURE=$(basename "$SPECIFY_FEATURE_DIRECTORY")
   python3 .orderspec/scripts/traceability.py init "$FEATURE"
   python3 .orderspec/scripts/traceability.py extract-spec-ids "$FEATURE"
   ```

   - The script takes the **feature name** (directory basename), not a path.
   - `init` is idempotent. `extract-spec-ids` is the **only** writer of `spec-ids.tsv`. **Never** hand-write or hand-read it.
   - **If `extract-spec-ids` exits non-zero**, your spec violates the ID contract — fix the spec, not the table. Usual cause: duplicate ID or off-anchor definition.
   - **Warnings about disappeared IDs** mean an ID was removed — verify it was tombstoned in §2, not silently renumbered.

10. **Self-Validation** — run the block below (no file is written).

## Refine Mode (modify an existing contract)

Triggered when an active `spec.md` exists and the request is a change/addition/clarification. The contract is **edited surgically**, never regenerated.

1. **Load** the existing `SPEC_FILE` and (IF EXISTS) the constitution. Build a light internal index of current IDs per prefix. Do **not** copy the template over the file.
2. **Classify the request** into concrete edits:
   - *Add* → assign next-free IDs, place in correct section, wire `Covers:`/`→ covered by` links. New IDs defined on strict anchor lines.
   - *Change* → edit in place under the same ID; propagate to every dependent AC/EDGE/INV/diagram/contract.
   - *Resolve* a `[NEEDS CLARIFICATION]` / `Q-NNN` → apply the answer, move to §13/§14, reflect in normative section.
   - *Remove/narrow* → only on explicit request; tombstone in §2 per *ID Discipline*.
3. **Coverage sweep** on the touched area: no topic half-covered (new REQ with no AC, AC with no `Covers`, EDGE pointing at non-matching AC).
4. **Reference reconciliation**: confirm every internal reference still resolves.
5. **Grid maintenance**: if the edit touched an INV with absolute quantifier, or added/changed any NFR or ASM with weakening qualifier, **regenerate the affected rows of the §10 contradiction grid**. Resolve any new CONFLICT in-spec or via *Clarification Protocol*.
6. **Re-size check**: if refinement pushed past the decomposition threshold, surface a one-line note recommending `/order.spec --split`.
7. **Changelog**: append a dated one-line entry to `## 15. Changelog` at the end of the spec (create if absent): what changed, which IDs added/edited/tombstoned.
8. **Project IDs** (mechanical — via script):

   ```bash
   FEATURE=$(basename "$SPECIFY_FEATURE_DIRECTORY")
   python3 .orderspec/scripts/traceability.py init "$FEATURE"
   python3 .orderspec/scripts/traceability.py extract-spec-ids "$FEATURE"
   ```

9. **Self-Validation**: run the shared block; re-validate only touched items plus traceability/uniqueness globally.
10. **Downstream Impact**: see dedicated section below.

## Decompose Mode (oversized scope)

Triggered by `--split`, the create-mode sizing gate, or a clearly too-broad request. **This mode writes at most one new spec, and only after the user picks the target.**

1. **Do NOT create or overwrite any spec yet.** Produce a **decomposition plan** as output (not a file):
   - Identify natural module boundaries (by functional domain / actor set / independently shippable slice).
   - For each proposed sub-spec: short kebab name, 1–2 line scope, key actors, dependencies on other modules.
   - Render as a table plus a small dependency note.
2. **Provide a ready-to-run prompt for every module**: for each sub-spec, emit a copy-paste line:

   ```text
   /order.spec --new "<focused description of this module, with its boundary and the IDs/contracts it depends on from sibling specs>"
   ```

3. **Ask the user to choose ONE module to build now.** Recommend a default (normally the core/most-depended-upon module). Offer as numbered choice + Custom. Wait for the choice.
4. **Build exactly the chosen module** as a single focused spec:
   - Brand-new oversized request → run **CREATE mode** scoped to that one module (own feature directory).
   - Existing oversized `spec.md` via `--split` → run **CREATE mode** for the extracted module in a **new** feature directory, then **REFINE** the parent to narrow its scope: tombstone moved REQ/UJ/etc. in §2 with "→ extracted to specs/<new>" and reconcile references.
5. **Report**: what was created, the chosen module, and ready-to-run prompts for remaining modules.

## Self-Validation (no file written)

Run these checks as reasoning before completing. Do not create a checklist file — independent review belongs to `/order.spec-check`.

### Level 1 — Syntactic

- **Repo-independent outside §6**: scan spec (excluding §6) for `src/`, `./`, file extensions, and library/class names from user input (e.g., Mongoose, Joi, Passport). If found in §7-§12, rewrite using logical roles. Library names MUST ONLY appear in §6 Constraints.
- **Mermaid safety**: all node labels use quoted form `X["label"]`. In sequenceDiagram, all participants declared at top.
- **ID anchors**: every ID defined on a strict `- **PREFIX-NNN**: …` line. (Uniqueness enforced by `extract-spec-ids`.)
- **Contradiction grid present** in §10 with rows for INV×NFR and INV×ASM pairs (and REQ×ASM narrowing pairs if applicable).
- **No unresolved `[NEEDS CLARIFICATION]`** markers.
- **Every REQ covered by ≥1 UJ/AC.** Every AC traces to ≥1 REQ via Covers. ≤2 UJs are P1.

### Level 2 — Output Audit (re-read your spec after writing)

After writing, re-read these specific items and verify consistency:

1. **INV ↔ Grid consistency**: For each INV containing "exactly/always/never", quote the INV text and the paired NFR/ASM text from the spec. Verify the grid verdict matches the actual wording. If the grid says "Compatible" but the INV says "exactly one" and the NFR says "best-effort" — that is a **CONFLICT**. Fix the spec (weaken the INV or strengthen the NFR) or route to Clarification Protocol.
2. **Global Consistency for Weakened Invariants**: If you weakened an INV (e.g., MUST -> SHOULD) to resolve a conflict, you MUST verify that all corresponding REQ, SC, and AC also reflect this weakened semantics. If REQ says "MUST" but INV says "SHOULD", that is a **CONFLICT**. Fix the REQ/SC to match the weakened INV.
3. **REQ ↔ ASM consistency**: For each ASM that describes data structure or semantics (snapshot, diff, fields, scope), find the REQ it relates to. Quote both. If they contradict (e.g., REQ says "changed fields", ASM says "full state") — fix the ASM to be case/action-aware, or remove the narrowing.
4. **Authorization completeness**: For each mutating endpoint (POST/PATCH/DELETE) and each cross-tenant read endpoint, verify an actor or authorization rule is specified (REQ, INV, or ASM). If missing — add one or route to Clarification Protocol.
5. **AC ↔ REQ direct trace**: For each AC, verify it directly tests a specific REQ's behavior (not just listed in a UJ's Covers). If an AC tests behavior not covered by any REQ — add a REQ or remove the AC.
6. **AC ↔ Schema Alignment**: For each AC that checks a specific field in the response (e.g., "Then the response contains `updatedAt`"), verify that field is present in the corresponding §9 JSON response schema (or explicitly documented as stripped by a plugin).
7. **Diff semantics completeness**: If any REQ or ASM specifies a diff/changes model (e.g., "only changed fields"), verify that §9 or §14 defines the changes format for EVERY mutation action (create, update, soft-delete, restore). For `create`, specify whether all initial fields appear as changes from null. For `soft-delete`/`restore`, specify which fields appear in changes. If any action's diff format is undefined → add an ASM or §9 detail.

### Handle results

- **All pass** → proceed to post-execution hooks.
- **Self-fixable defects** (fix is obvious and meaning-preserving) → fix, re-check (max 3 iterations).
- **High-impact fork or unresolved CONFLICT** → STOP and run *Clarification Protocol*.
- **Still failing after 3 iterations** → note residual gap in Completion Report, recommend `/order.spec-check`.

## Downstream Impact (refine & decompose only)

After modifying an **existing** contract:

- If `plan.md` exists: warn "spec.md changed — `plan.md` may be stale. Run `/order.plan` (or `/order.plan-check`) to re-align."
- If `tasks.md` exists: add "tasks.md may also be stale — re-derive via `/order.tasks` after the plan is aligned."
- For cross-cutting changes, recommend a final `/order.analyze` pass before `/order.code`.

This command does **not** modify `plan.md` or `tasks.md`.

## Post-Execution Checks

Run the **`after_spec`** phase per `.orderspec/memory/hooks-protocol.md`.

## Completion Report

Report, scaled to the mode (to chat — no checklist file):

- **create**: `SPECIFY_FEATURE_DIRECTORY`, `SPEC_FILE`, self-validation summary (pass / fixed / residual), ID counts, contradiction-grid result, ID-projection result (`extract-spec-ids` exited zero; N IDs projected), readiness for `/order.plan`. Recommend `/order.spec-check` for weaker-model or high-importance work.
- **refine**: `SPEC_FILE`, the Changelog line, self-validation re-check result, grid-maintenance note, ID-projection result, and Downstream Impact warnings.
- **decompose**: the decomposition table, which module was built (path), and ready-to-run prompts for remaining modules.

## Done When

- [ ] Prior gate report consumed (if present): every finding owned by `/order.spec` was addressed; upstream-owned findings were routed/STOPped
- [ ] Mode detected and stated; no existing contract overwritten by a template
- [ ] Content written with stable, append-only IDs on strict anchor lines; all internal references reconciled
- [ ] §10 contradiction grid present (INV×NFR, INV×ASM, REQ×ASM narrowing); zero unresolved CONFLICT
- [ ] High-impact forks surfaced via Clarification Protocol (not silently defaulted)
- [ ] IDs projected into `spec-ids.tsv` via `traceability.py extract-spec-ids` (exited zero); table not hand-written
- [ ] Self-Validation completed (Level 1 syntactic + Level 2 Output Audit); no checklist file written
- [ ] (refine/decompose) Downstream Impact reported; (decompose) remaining-module prompts provided
- [ ] Extension hooks dispatched or skipped per rules
- [ ] Completion reported per mode
