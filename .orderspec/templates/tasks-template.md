# Tasks: [FEATURE NAME]

**Input**: `/specs/[###-feature-name]/spec.md` (SDD), `/specs/[###-feature-name]/plan.md`

**Execution Strategy (Expand-Migrate-Contract)**:

1. **Expand**: Add new schemas, models, and contract stubs without breaking existing flows.
2. **Migrate & Implement**: Build behavior increments grouped by User Stories. Complete and verify P1 (MVP) first.
3. **Contract**: Remove deprecated code, drop obsolete schema/routes, remove feature flags, finalize.

**Format**: `` - [ ] T### [P?] [US?] Description referencing `exact/file/path` (Spec IDs: ≤15-word paraphrase) ``

- Every file path in a task line MUST be wrapped in backtick inline-code, as shown in the Format example above. The traceability validator (path-vs-manifest and parallel-conflict checks) extracts paths only from backtick-delimited spans; a path written as plain prose is not extracted, so its existence is never verified. When unsure, wrap it.
- The P marker is OPTIONAL: present only when the task is file-disjoint and independent of adjacent marked tasks. Sequential top-to-bottom order is always correct on its own; the marker is a hint that adjacent marked tasks MAY run concurrently. There are no "waves".
- The US marker maps 1:1 to UJ-NNN in spec (US1 to UJ-001); present on story-phase tasks only.
- Do NOT put backtick inline-code around anything other than real file paths in task lines. Spec IDs, commands, field names and markers stay as plain text — otherwise the validator may mistake them for paths.

<!--
  IMPORTANT: Tasks below are SAMPLE placeholders. The /order.tasks command
  MUST replace them with real tasks derived from spec.md (UJ/AC/REQ/EDGE/INV IDs)
  and exact file paths from plan.md. Renumber T001..TNNN sequentially.
  DO NOT keep sample tasks in the generated file.

  PATH RULE: every file path in a generated task line MUST be wrapped in
  backtick inline-code (see the Format example). The validator extracts paths
  ONLY from backtick spans. Conversely, do NOT wrap spec IDs, shell commands,
  field names, or markers in backticks inside task lines — the validator would
  then read them as bogus paths.

  Do NOT copy these explanatory notes into the generated tasks.md.
-->

---

## Execution Order

Phase 1 (Setup & Expand) → Phase 2 (US1 / MVP) → **STOP & VALIDATE** → Phase 3+ (US2..) → **GATE** → Final Phase (Contract).

- Phases are hard sequential barriers; within a phase, execute tasks top-to-bottom.
- Test tasks within a story phase are written first and MUST fail before their implementation tasks.

---

## Phase 1: Setup & Expand (Safe, Non-Breaking Additions)

**Purpose**: Prepare models, validation, config, and interface boundaries without breaking existing flows.

- [ ] T001 [P] Create core entity model in `src/models/[entity].ext` (REQ-NNN: paraphrase)
- [ ] T002 Add validation schemas in `src/validations/[entity].ext` (REQ-NNN: paraphrase)
- [ ] T003 Register new model and validation in their respective barrel/index files (single task — all barrel edits here)

---

## Phase 2: Migrate & Implement — User Story 1 (Priority: P1) 🎯 MVP

**Goal**: [Brief description from Spec § Acceptance Criteria]
**Verification**: Run [test command from plan.md]; assert AC-NNN.. pass and INV-NNN.. hold.

### Tests (Write First, Verify Failure)

- [ ] T004 [US1] Integration/contract test in `tests/[file].ext` (AC-001: paraphrase; AC-002: paraphrase)

### Implementation

- [ ] T005 [US1] Implement service logic in `src/services/[entity].ext` (REQ-NNN: mechanism paraphrase)
- [ ] T006 [US1] Implement controller handlers in `src/controllers/[entity].ext` (non-2xx: e.g. 404 only if never existed)
- [ ] T007 [US1] Define routes with auth + validate middleware in `src/routes/[entity].ext` (REQ-NNN: paraphrase)
- [ ] T008 [US1] Handle EDGE-NNN relevant to US1 in `src/services/[entity].ext` (EDGE-NNN: paraphrase)
- [ ] T009 [US1] Run verification: [test command] — assert AC-001/002 pass, INV-NNN holds, no regressions (AC-001, AC-002, INV-NNN)

**Checkpoint**: User Story 1 (MVP) is fully functional, backwards-compatible, and independently testable.

---

## Phase 3: Migrate & Implement — User Story 2 (Priority: P2)

**Goal**: [Brief description from Spec § Acceptance Criteria]
**Verification**: Run [test command]; assert AC-NNN.. pass with no regressions on US1.

### Tests

- [ ] T010 [US2] Integration test in `tests/[file].ext` (AC-003: paraphrase)

### Implementation

- [ ] T011 [US2] Extend service logic in `src/services/[entity].ext` (REQ-NNN: paraphrase)
- [ ] T012 [US2] Wire endpoint + handle EDGE-NNN in `src/routes/[entity].ext` (EDGE-NNN: paraphrase)
- [ ] T013 [US2] Run verification: [test command] — assert AC-003 passes, no US1 regressions (AC-003)

**Checkpoint**: User Stories 1 and 2 both functional and backwards-compatible.

---

[Add more story phases as needed, one per remaining UJ in priority order, same shape.]

---

## Final Phase: Contract (Gate, Cleanup, Hardening)

**Purpose**: Verify everything, then perform irreversible cleanup. **Greenfield rule**: if nothing pre-exists to deprecate, this phase only removes scaffolding/flags and polishes — do NOT invent legacy code to delete.

- [ ] T0XX GATE: Run [test command from plan.md] — verify all AC-* pass, INV-* hold, NFR-* targets met. STOP on any failure (contraction is irreversible).
- [ ] T0XX Remove feature flags / scaffolding; delete deprecated code/routes; drop obsolete columns/tables (only if a legacy mechanism is being replaced)
- [ ] T0XX Run linters and formatters (commands from plan.md); fix violations
- [ ] T0XX Update technical docs / inline docstrings to match final state

---

## Traceability Matrix

> Coverage source of truth. Every AC/EDGE/INV maps to >=1 task. Verification tasks reference IDs only (paraphrases live in the implementation tasks above — do not repeat them here).
> Each ID listed against a task here MUST also appear in that task's line above. The matrix is a roll-up of the task lines, not an independent claim — keep them consistent.

| Spec ID | Type | Task(s) |
|---------|------|---------|
| REQ-001 | REQ  | T001 |
| AC-001  | AC   | T004, T009 |
| AC-002  | AC   | T004, T009 |
| EDGE-001 | EDGE | T008 |
| INV-001 | INV  | T005, T009 |

---

## Files Touched

> Detects same-file conflicts: any file listed against >=2 tasks means those tasks are NOT eligible for the same P group. Paths here are wrapped in backticks for consistency with task lines (the validator reads paths from task lines, not this table).

| File | Task(s) |
|------|---------|
| `src/models/[entity].ext` | T001 |
| `src/validations/[entity].ext` | T002 |
| `src/services/[entity].ext` | T005, T008, T011 |
| `src/controllers/[entity].ext` | T006 |
| `src/routes/[entity].ext` | T007, T012 |
| `tests/[file].ext` | T004, T010 |

---

## Notes

- The P marker means file-disjoint and independent of adjacent marked tasks; safe to run concurrently OR sequentially. Absence of the marker = run sequentially. No "waves".
- The US marker traces a task to its user story.
- Wrap only real file paths in backticks; never wrap spec IDs, commands, field names, or markers (the validator would read them as bogus paths). See the Format note for why.
- Each task is self-contained: exact path + spec IDs + ≤15-word paraphrase, so the implementer need not re-open spec.md.
- Keep the Traceability Matrix consistent with the task lines: every ID in the matrix must appear in the referenced task's line, and vice versa.
- Tests within a story fail before their implementation.
- Commit after each task or logical group. Stop at any checkpoint to validate a story independently.
- Avoid: vague tasks, same-file P conflicts, cross-story dependencies that break independence, retrofitting a mechanism into already-written code, splitting many unrelated REQ/AC into one oversized task just to satisfy coverage.
