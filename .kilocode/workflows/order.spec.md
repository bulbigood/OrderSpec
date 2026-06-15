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

- **Repo-independent**: valid regardless of codebase state. No file paths, folder layouts, class names, or library versions.
- **Logically complete**: diagrams, ERD, API contracts, and invariants live HERE (not in plan.md).
- **Traceable**: every statement carries a stable ID (REQ/NFR/CON/SC/INV/EDGE/UJ/AC/Q/ASM) that downstream commands reference instead of copying text.

Allowed: logical data model, interface contracts, externally imposed tech constraints (as `CON-NNN`, e.g., "Must use PostgreSQL").
Forbidden: physical code structure, implementation steps, task ordering — those belong to `plan.md` / `tasks.md`.

**This command is the sole owner of contract content.** The `*-check` gates may detect defects and auto-fix only mechanical issues, but any change to requirement meaning, scope, thresholds, or any added/removed topic is authored HERE — invoked by the user (often via a gate's Routing block). This command therefore operates in three modes (auto-detected in the Outline): **create**, **refine**, and **decompose**.

**This command authors content; it does NOT write a self-grading checklist file.** Validation here is *constructive* (rules that shape generation) and *interactive* (it asks the user about genuine high-impact forks). Independent post-hoc review and any report file are owned by `/order.spec-check`, never produced here.

## Pre-Execution Checks

Run the **`before_spec`** phase per `.orderspec/memory/hooks-protocol.md`.

## Mode Detection (run first, before any file operation)

The text after `/order.spec` **is** the request. Do not ask the user to repeat it unless empty.

Determine the operating mode **before touching the filesystem**:

1. **Resolve the target feature.** If the user passed `SPECIFY_FEATURE_DIRECTORY`, use it. Else, if `.orderspec/feature.json` resolves to a directory containing a non-template `spec.md`, treat that as the active feature. Else there is no active spec.
2. **Explicit flags override detection**: `--split` (or a request whose intent is clearly "break this spec up") forces **decompose** on the active spec; `--new` forces **create** even if an active spec exists (a genuinely separate feature).
3. **Auto-detect** when no flag is given:
   - **No active `spec.md`** (or it is still the untouched template) → **create**.
   - **Active `spec.md` exists** and the request is a change/addition/clarification ("add…", "change…", "the AC for REQ-007 should…", or a gate's Routing request) → **refine**. **Never overwrite an existing contract with a fresh template.**
   - **Active `spec.md` exists** and the request describes a clearly separate feature → **create** a new feature directory (do not refine the unrelated spec).
4. **State the detected mode in one line before proceeding** (e.g., "Mode: refine — applying changes to `specs/003-user-auth/spec.md`"). If detection is genuinely ambiguous (request could be refine or new-feature), ask the user once which they mean — this is a blocking question; it follows the *Clarification Protocol* format below.

## Self Gate Report Intake

Before regenerating `spec.md`, check whether a gate report from a previous run
exists at `checklists/spec-report.md`. If present, it is the cited input for any
refinement request — it carries the Routing blocks you must action. (The report is
written by the optional `/order.spec-check` gate; this command does not require
that gate to exist — it only reads the file if it is there.)

```bash
SELF_REPORT="$FEATURE_DIR/{REPORT}"
test -e "$SELF_REPORT" && echo "SELF_REPORT_PRESENT" || echo "SELF_REPORT_ABSENT"
```

- **SELF_REPORT_ABSENT** → no prior gate run for this artifact. Proceed normally; treat `$ARGUMENTS` as the only refinement signal.
- **SELF_REPORT_PRESENT** → read `$SELF_REPORT` and parse its header verdic (`✅ PASS` | `⛔ BLOCK` | `🔀 ROUTING REQUIRED`):
  - **verdict ✅ PASS** → the previous artifact was clean. Ignore the report as a fix-source; proceed with `$ARGUMENTS` only.
  - **verdict ⛔ BLOCK or 🔀 ROUTING REQUIRED** → this is the authoritative list of defects YOU must resolve. You MUST:
    1. Read the **Routing Required** section and the **Findings** table.
    2. Address **every** finding whose `Run` line targets `{THIS_CMD}` — these are owned by this command. Each becomes a concrete change in {ARTIFACT}.
    3. Findings whose `Run` line targets a DIFFERENT command (e.g. an upstream `/order.spec`) are NOT yours: do NOT silently compensate for them. If any unresolved upstream finding blocks a fix you must make, STOP and report `{BLOCKED_TOKEN}: upstream finding must be resolved first`, listing the finding IDs and their owning command.
    4. Treat `$ARGUMENTS` as ADDITIONAL guidance layered on top of the report — never as a replacement for it. If `$ARGUMENTS` is a vague directive such as "fix the errors" / "исправь ошибки", the report findings ARE the definition of "the errors": action them by ID.

  Record in the Completion Report which report-finding IDs you addressed, so a follow-up `{CHECK_CMD}` can confirm closure.

## ID Discipline (applies to every mode that writes)

- **Stable IDs are append-only.** When adding a statement, assign the **next free number** within its prefix (scan existing IDs first). **Never renumber, reuse, or shift existing IDs** — downstream artifacts reference them by number.
- **Editing in place** keeps the same ID; the meaning change is what propagates.
- **Removing** a statement: do not delete the ID silently. If scope is genuinely cut, move it to §2 Out-of-Scope with a one-line tombstone ("REQ-014 removed — <reason>") so dangling downstream references are explained, not mysterious.
- **Reference reconciliation (mandatory after any edit)**: every `Covers:`, every `EDGE-NNN → covered by AC-NNN`, every diagram/contract code, and every `ASM→normative` link must still resolve. Fix references in the spec; if a change invalidates a downstream artifact's reference, that is reported (see *Downstream Impact*), not silently patched here.

## Clarification Protocol (shared by all modes — interactive resolution of high-impact forks)

`/order.spec` is **not fully autonomous on consequential decisions**. When the request leaves a genuine fork that materially changes scope, architecture, data model, invariants, externally observable behaviour, security, or acceptance — and there is no single obviously-correct default — **STOP and ask the user** rather than silently choosing and burying the choice in an `ASM`.

**When to ask (trigger conditions — any one fires):**

- A §13 contradiction-grid pair resolves to **CONFLICT** and the fix is not obvious (e.g., weakening an INV vs strengthening an NFR both change the contract meaningfully).
- A significant **architecture or behaviour** decision has ≥2 defensible options (e.g., atomic vs best-effort vs compensating write semantics for a multi-entity operation; synchronous vs queued processing; pagination present vs absent on a collection endpoint).
- A choice **significantly impacts scope / security-privacy / UX**, multiple interpretations genuinely diverge, and no reasonable default exists.
- Mode detection is genuinely ambiguous (refine vs new-feature).

**When NOT to ask (resolve via informed default + ASM instead):**

- Low-impact field defaults, naming, optional descriptive fields, obvious conventional choices. These become `ASM-NNN` silently — do not interrupt the user for these.

**Question format (numbered options + `yes` shortcut):**

Present all open questions together, **maximum 3**, numbered Q1–Q3, prioritised scope > security/privacy > UX > technical. For each, render:

```markdown
## Question [N]: [Topic]

**Context**: [Quote the relevant spec section / the conflicting IDs]
**What we need to decide**: [Specific question]
**My recommendation**: Option [X] — [one-line why]

| Option | Answer | Implications |
|--------|--------|--------------|
| A      | [Answer] | [Consequence] |
| B      | [Answer] | [Consequence] |
| C      | [Answer] | [Consequence] |
| Custom | Provide your own | [How] |

**Reply** with a choice per question (e.g., "Q1: B, Q2: Custom — …"), **or just write `yes`** to accept my recommendation for every open question.
```

Ensure tables render correctly (spaces around cell content, ≥3 dashes in separators). **Wait** for the reply. On `yes`, apply the recommended option for each question. Then apply each answer: replace any `[NEEDS CLARIFICATION]` marker, record the decision in §16/§17, reflect it in the normative section (REQ / §12 contract / INV as appropriate), and re-run *Self-Validation* on the touched items. This is the only place the command blocks for input.

## Outline (CREATE mode)

1. **Generate a short name** (2-4 words, action-noun, kebab-case, preserve acronyms): e.g., "user-auth", "oauth2-api-integration", "fix-payment-timeout".

2. **Branch creation** (optional, via hook): if a `before_spec` hook ran, note `BRANCH_NAME`/`FEATURE_NUM` from its JSON output. Branch name does **not** dictate the spec directory name. If the user provided `GIT_BRANCH_NAME` explicitly, pass it through to the hook unchanged.

3. **Create the spec feature directory**:
   - If the user explicitly provided `SPECIFY_FEATURE_DIRECTORY`, use it as-is. Otherwise auto-generate under `specs/`:
     - Read `.orderspec/init-options.json`: `feature_numbering` (preferred) or `branch_numbering` (deprecated).
     - `"timestamp"` → prefix `YYYYMMDD-HHMMSS`; `"sequential"` or absent → prefix `NNN` (next available 3-digit number in `specs/`).
     - Directory: `specs/<prefix>-<short-name>` (e.g., `specs/003-user-auth`).
     - If `branch_numbering` was used, warn once: "⚠️ `branch_numbering` in init-options.json is deprecated. Rename to `feature_numbering`."
   - `mkdir -p SPECIFY_FEATURE_DIRECTORY`; resolve the active `spec-template` via the preset/template resolution stack; copy it to `SPECIFY_FEATURE_DIRECTORY/spec.md`; set `SPEC_FILE`.
   - **Refuse to overwrite**: if `SPEC_FILE` already exists with non-template content, STOP and re-route to *Refine Mode* — never clobber a contract in create mode.
   - Persist to `.orderspec/feature.json` (actual resolved path, not the literal variable name):

     ```json
     { "feature_directory": "specs/003-user-auth" }
     ```

   - One feature per invocation. Spec directory and git branch names are independent.

4. Load the resolved `spec-template` to understand required sections.

5. **IF EXISTS**: Load `.orderspec/memory/constitution.md` for governance constraints.

6. **Scope sizing gate (run before filling sections).** Estimate the contract's breadth from the parsed request: count distinct functional domains, independent actor/role sets, and rough REQ/UJ/entity volume. If it **exceeds the decomposition threshold** (heuristic below), do NOT author a giant spec — switch to *Decompose Mode*.
   - **Threshold heuristic** (any two firing → oversized): ≳ 25–30 plausible REQ; ≳ 3 independent functional domains that could ship/test separately; ≳ 3 distinct primary actor sets with non-overlapping journeys; > 2 viable P1-MVP slices that aren't a single end-to-end thread.
   - This is a heuristic, not a hard stop on size alone — a dense but cohesive single domain stays one spec.

7. **Execution flow** (fills the SDD template section by section):
   1. Parse the description. If empty: ERROR "No feature description provided".
   2. Extract: actors, actions, data, constraints, external systems.
   3. **§1 Executive Summary**: concise system/feature overview (≤ 5-10 paragraphs).
   4. **§2 Goal & Scope**: objectives, explicit out-of-scope items, and `SC-NNN` success criteria — measurable, technology-agnostic, verifiable without implementation knowledge (e.g., "Users complete checkout in under 3 minutes", NOT "API responds in 200ms").
   5. **§3 Glossary**: domain terms only; omit obvious ones.
   6. **§4 Functional Requirements**: `REQ-NNN`, one testable MUST/MUST NOT statement each.
   7. **§5 NFR / §6 Constraints**: `NFR-NNN` (performance, security, observability), `CON-NNN` (externally imposed: mandated tech, platforms, compliance).
   8. **§7-10 Architecture & Behaviour**: System Context diagram (always); Container diagram, sequence diagrams (happy path + key error paths), state machine — only where applicable. **Omit non-applicable sections entirely; never emit placeholder diagrams.** Diagrams are logical (roles/responsibilities), not physical (no file/class names). Mermaid safety: ALL node labels MUST use the quoted form `X["label"]` without exception. After generating each diagram block, scan every node definition; any `[...]` not in `["..."]` form is an error — fix before writing. In sequenceDiagram, declare every participant used in any branch (including alt/else) at the top via participant X lines.
   9. **§11-12 Data & Contracts**: ERD for key entities + relationships; logical API/event contracts. Verbose schemas go inside `<details>` blocks. Omit sections if no data/external interface. §12 contracts are the single normative source for status codes and response shapes. SC, AC, EDGE and sequence diagrams MUST use codes identical to §12 and MUST NOT redefine semantics (e.g., do not call an idempotent 200 no-op a "failure"). On conflict, fix the non-§12 occurrence. Define repeated structures (pagination envelope, error body `{code, message}`) ONCE in a shared `<details>` block at the top of §12; per-endpoint entries reference them ("→ standard pagination envelope") instead of repeating full JSON. Include full examples only for responses with non-obvious shape.
   10. **§13 Invariants**: `INV-NNN` — conditions that must hold true at all times, deterministic form. Not requirements, not behaviours. Before finalizing, cross-check every INV against all REQ, NFR, **and ASM** touching the same subject. If an INV conflicts with a quality target (e.g., "exactly one record MUST exist before the operation completes" vs "write is best-effort/non-blocking"), resolve the conflict in the spec — if the fix is non-obvious or high-impact, route it to the *Clarification Protocol*; never write both sides of a contradiction. For any operation that writes to more than one entity (e.g., primary record + audit/event record), the spec MUST state failure semantics explicitly: atomic / best-effort / compensating. If undecidable, raise it via the *Clarification Protocol*.

       **Mandatory contradiction grid (write it, do not assert it).** Before finalizing §13, for EACH INV containing an absolute quantifier (exactly / always / every / never / must produce), enumerate every **NFR and every ASM** containing a weakening qualifier (best-effort / may fail / non-blocking / eventually / excludes / optional). You MUST scan BOTH sources — NFRs and ASMs — not NFRs alone; a weakening ASM is the most common place a contradiction hides. For each such pair output one line:

       ```text
       INV-NNN × {NFR|ASM}-NNN → compatible | CONFLICT — one-line reason
       ```

       Render the full grid as a table inside §13 of the spec (it is contract content, not a self-report). Any **CONFLICT** MUST be resolved before writing — weaken the INV (e.g. "MUST attempt to produce") or strengthen the NFR/ASM; if the resolution is non-obvious or high-impact, route it to the *Clarification Protocol*. If no INV has an absolute quantifier, or nothing weakens one, state "No absolute INV × weakening NFR/ASM pairs" — do not omit the grid silently.
   11. **§14 Edge Cases**: `EDGE-NNN` — boundary conditions, failures, races. If an EDGE case is fully expressed by an AC, do not duplicate the wording: write `EDGE-NNN: <one-line name> → covered by AC-NNN`. Before writing `EDGE-NNN → covered by AC-NNN`, verify the AC's Given/When/Then actually describes this scenario. If no AC matches, either add an AC to the relevant UJ or keep the full EDGE text inline. A behaviour expressed only in an ASM or a state diagram is NOT covered. Each behaviour's full text lives in exactly one place.
   12. **§15 User Journeys & Acceptance Criteria**: each `UJ-NNN` is an independently implementable & testable slice, ordered P1..Pn (P1 = MVP). At most 2 UJs may be P1: P1 = the minimal end-to-end slice delivering value. Guard rails, defensive behaviour, and secondary flows are P2+. If more than 2 UJs rank P1, re-rank before writing. Each UJ has `Covers: REQ-/NFR-IDs`, priority rationale, independent test description, and `AC-NNN` in Given/When/Then form. Every AC must trace to a REQ via Covers.
   13. **§16-17 Open Questions & Assumptions**: ambiguity handling rules:
       - Prefer informed defaults for **low-impact** ambiguity; record each as `ASM-NNN`. If a default changes externally observable behaviour (e.g., "endpoint X has no pagination"), it MUST also appear in the normative section (REQ or §12 contract); the ASM only references it. ASM alone never carries behaviour.
       - **High-impact forks are NOT silently defaulted into an ASM.** If a choice meets a *Clarification Protocol* trigger, ask the user (numbered options + `yes` shortcut) instead of inventing an ASM. An ASM is for decisions a competent reviewer would not contest; a Question is for the rest.
       - **Narrowing ASMs must be revalidated against the REQ they touch.** If an ASM narrows the field set, scope, or behavior of a REQ (e.g. "snapshot excludes fields X, Y"), name that REQ explicitly and verify the narrowed form still satisfies the REQ's intent for EVERY action/case the REQ covers. If the narrowing defeats the REQ for any case (e.g. an audit snapshot that excludes the very fields a given action changes), the ASM is wrong — fix the ASM to be case/action-aware, do not record the narrowing.
       - Use `[NEEDS CLARIFICATION: question]` inline + paired `Q-NNN` only when the choice significantly impacts scope/security/UX, multiple interpretations diverge, and no reasonable default exists — and surface it through the *Clarification Protocol*.
       - **Maximum 3 clarification questions total.** Priority: scope > security/privacy > UX > technical details.

8. Write the specification to `SPEC_FILE`, preserving template section order and headings. Replace all placeholders; remove non-applicable optional sections entirely.

9. **Self-Validation** — run the shared *Self-Validation* block below (no file is written).

## Refine Mode (modify an existing contract)

Triggered when an active `spec.md` exists and the request is a change/addition/clarification (including a gate Routing request). The contract is **edited surgically**, never regenerated.

1. **Load** the existing `SPEC_FILE` and (IF EXISTS) the constitution. Build a light internal index of current IDs per prefix. Do **not** copy the template over the file.
2. **Classify the request** into one or more concrete edits:
   - *Add* a topic/requirement/edge/AC → assign next-free IDs (per *ID Discipline*), place in the correct section, wire `Covers:`/`→ covered by` links.
   - *Change* an existing statement → edit in place under the same ID; propagate the meaning change to every dependent AC/EDGE/INV/diagram/contract code (Mirror).
   - *Resolve* a `[NEEDS CLARIFICATION]` / open `Q-NNN` → if the request supplies the answer, apply it, move the item to a decision in §16/§17 with the chosen value, and reflect it in the normative section. If the answer is missing or the choice is high-impact with no default, run the *Clarification Protocol* rather than guessing.
   - *Remove/narrow scope* → only on explicit request; tombstone in §2 Out-of-Scope per *ID Discipline*. Never silently delete.
3. **Coverage sweep on the touched area.** After applying edits, re-walk only the affected sections to ensure no topic is half-covered (a new REQ with no AC, an AC with no `Covers`, an EDGE pointing at a non-matching AC). Close gaps within the same edit.
4. **Reference reconciliation** (mandatory) per *ID Discipline*: confirm every internal reference still resolves.
5. **Grid maintenance**: if the edit touched an INV with an absolute quantifier, or added/changed any NFR or ASM with a weakening qualifier, **regenerate the affected rows of the §13 contradiction grid** (NFR and ASM sources both). Resolve any new CONFLICT in-spec or via the *Clarification Protocol*.
6. **Re-size check**: if the refinement has pushed the contract past the decomposition threshold (§6 heuristic), surface a one-line note recommending `/order.spec --split` — do not auto-split mid-refine.
7. **Changelog**: append a dated one-line entry to a `## Changelog` section at the end of the spec (create it if absent): what changed, which IDs added/edited/tombstoned. This is the human-visible audit trail.
8. **Self-Validation**: run the shared block; re-validate only the touched items plus traceability/uniqueness globally.
9. **Downstream Impact**: see the dedicated section — refinement almost always means `plan.md`/`tasks.md` may now be stale.

## Decompose Mode (oversized scope — Option Г)

Triggered by `--split`, by the create-mode sizing gate firing, or when a request is clearly too broad for one cohesive contract. **This mode writes at most one new spec, and only after the user picks the target.** It never bulk-generates many specs (too heavy / low-quality for weaker models) and never auto-assigns priority silently.

1. **Do NOT create or overwrite any spec yet.** First, produce a **decomposition plan** as output (not a file):
   - Identify the natural module boundaries (by functional domain / actor set / independently shippable slice).
   - For each proposed sub-spec give: a short kebab name, a 1–2 line scope, its key actors, and its **dependencies** on the other modules (which is core vs which build on it).
   - Render as a table plus a small dependency note.
2. **Provide a ready-to-run prompt for every module** (Option В safety net): for each proposed sub-spec, emit a copy-paste line:

   ```text
   /order.spec --new "<focused description of this module, with its boundary and the IDs/contracts it depends on from sibling specs>"
   ```

   so the user can create the rest in later passes (one spec per pass — light for the model) without re-deriving the decomposition.
3. **Ask the user to choose ONE module to build now** (Option Г). Recommend a default with a one-line rationale — normally the **core/most-depended-upon** module, so siblings can reference its IDs; or the most autonomous slice if the user wants the fastest standalone value. Offer the modules as a numbered choice + Custom (this choice uses the *Clarification Protocol* shape). Wait for the choice.
4. **Build exactly the chosen module** as a single focused spec:
   - If decomposing a brand-new oversized request → run **CREATE mode** scoped to that one module (own feature directory).
   - If decomposing an existing oversized `spec.md` via `--split` → run **CREATE mode** for the extracted module in a **new** feature directory, then **REFINE** the parent spec to narrow its scope: tombstone the moved REQ/UJ/etc. in §2 Out-of-Scope with "→ extracted to specs/<new>" and reconcile references. Parent and child are now two clean contracts.
5. **Report** what was created, the chosen module, and the ready-to-run prompts for the remaining modules so the user can continue at their own pace.

## Self-Validation (inline reasoning — shared by all writing modes; NO file is written)

Run these checks **as reasoning before/after writing the spec**, fixing the spec in place. **Do not create a checklist file** — this is the author's own correctness pass, not an independent review (independent review and any report file belong to `/order.spec-check`). Where a check surfaces a high-impact fork, route it to the *Clarification Protocol* rather than guessing.

a. **Contract quality (silent self-checks, no output file):**

   - Repo-independent outside §6. Before concluding this, scan the entire spec (excluding §6) for path-like tokens: `src/`, `./`, file extensions (`.js`, `.py`, `.ts`, …), and class/function identifiers from the user input. If the user input supplied physical paths, rewrite them at logical level (e.g., "the project's existing objectId validator") and note inline that physical mapping is deferred to `plan.md`.
   - Logical architecture present where applicable (context diagram, ERD, contracts); no placeholder/empty diagrams; non-applicable sections removed; all mandatory sections completed.

b. **Requirement completeness:**

   - No unresolved `[NEEDS CLARIFICATION]` remains (each is either resolved via the *Clarification Protocol* or paired with a `Q-NNN`).
   - Every REQ is testable and unambiguous (MUST/MUST NOT). SC are measurable and tech-agnostic. INV are deterministic consistency rules, not behaviours. EDGE cases identified; scope explicitly bounded. Low-impact assumptions recorded as `ASM-NNN`.
   - **Contradiction grid is present in §13**, built over **both NFR and ASM** weakening sources against every absolute-quantifier INV, every pair verdicted compatible/CONFLICT with a reason, and **zero unresolved CONFLICT** remain.
   - **Every narrowing ASM** names the REQ it narrows and is verified case/action-aware against that REQ's intent.

c. **Traceability & readiness:**

   - Every AC traces to ≥1 REQ via `Covers`. Every REQ is covered by ≥1 UJ/AC. Every `covered by AC-NNN` points to an AC whose text matches the EDGE scenario. Each UJ is independently implementable and testable; ≤2 UJs are P1 and together form a viable MVP. IDs are unique and sequential per prefix; no pre-existing IDs renumbered.

d. **Handle results:**

   - **All pass** → proceed to post-execution hooks.
   - **Self-fixable defects** (the fix is obvious and meaning-preserving-or-clearly-correct) → fix the spec, re-check (max 3 iterations).
   - **High-impact fork or unresolved CONFLICT with no obvious fix** → STOP and run the *Clarification Protocol* (numbered options + `yes`); apply the answer; re-check the touched items.
   - **Still failing after 3 iterations** → note the residual gap in the *Completion Report* to the user and recommend running `/order.spec-check`.

## Downstream Impact (refine & decompose only)

After modifying an **existing** contract (refine, or the parent-narrowing half of `--split`), the spec may no longer match its downstream artifacts:

- If `plan.md` exists for this feature, warn: "spec.md changed — `plan.md` may be stale. Run `/order.plan` (or `/order.plan-check`) to re-align."
- If `tasks.md` exists, add: "tasks.md may also be stale — re-derive via `/order.tasks` after the plan is aligned."
- For a cross-cutting change, recommend a final `/order.analyze` pass before `/order.code`.

This command does **not** modify `plan.md` or `tasks.md` — propagation is the user's call through the owning commands, exactly as the gates route it.

## Post-Execution Checks

Run the **`after_spec`** phase per `.orderspec/memory/hooks-protocol.md`.

## Completion Report

Report, scaled to the mode (to chat — no checklist file is produced here):

- **create**: `SPECIFY_FEATURE_DIRECTORY`, `SPEC_FILE`, self-validation summary (pass / fixed / residual), ID counts (REQ/UJ/AC/INV/EDGE), contradiction-grid result (pairs checked, conflicts resolved), readiness for `/order.plan`. Recommend `/order.spec-check` for weaker-model or high-importance work.
- **refine**: `SPEC_FILE`, the Changelog line (IDs added/edited/tombstoned), self-validation re-check result, grid-maintenance note (if §13 touched), and the **Downstream Impact** warnings.
- **decompose**: the decomposition table, which module was built (path), and the ready-to-run prompts for the remaining modules.

**NOTE:** Branch creation is handled by the `before_spec` hook; spec directory/file creation is handled by this command in create/decompose modes. Refine mode edits the existing file in place and never copies the template over it.

## Done When

- [ ] **Prior gate report consumed (if present)**: if `{REPORT}` existed with a ⛔/🔀 verdict, every finding owned by `{THIS_CMD}` was addressed and listed in the Completion Report; upstream-owned findings were routed/STOPped, not silently patched. If the report was ✅ PASS or absent, this item is N/A.
- [ ] Mode was detected and stated; no existing contract was overwritten by a template
- [ ] Content written/edited with stable, append-only IDs and all internal references reconciled
- [ ] §13 contradiction grid present over **NFR and ASM** sources; zero unresolved CONFLICT
- [ ] High-impact forks were surfaced via the *Clarification Protocol* (numbered options + `yes`), not silently defaulted
- [ ] Self-Validation reasoning completed; **no self-grading checklist file was written**
- [ ] (refine/decompose) Downstream Impact reported; (decompose) remaining-module prompts provided
- [ ] Extension hooks dispatched or skipped per rules above
- [ ] Completion reported per mode
