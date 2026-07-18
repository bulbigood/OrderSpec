# Tasks: [FEATURE NAME]

**Input**: `/specs/[###-feature-name]/spec.md` (SDD), `/specs/[###-feature-name]/plan.md`

**Execution Strategy (derived from plan.md)**:

1. Migration work order: **Expand → Migrate → Contract** when the plan declares compatibility or cleanup transitions.
2. Non-migration work order: **Setup → User Stories → Final Verification** with no invented cleanup phase.

**Format (STRICT — pipe-delimited, machine-parsed)**: `- [ ] T### [P?] [US?] | path | refs? | gloss`

- `extract-trace` splits each task line on ` | ` (space-pipe-space). Every task has exactly four fields and three separators. Field 2 is the file path; field 3 is the spec IDs.
- **Path field is a RAW plan.md path — NO backticks, NO markdown.** The tool matches the literal path; backticks make it not match and silently drop coverage.
- **refs is optional in meaning, but its field is mandatory.** An infrastructure task (barrel/index registration, route wiring, test fixtures, GATE/verification) uses `... | path |  | gloss`. NEVER invent a ref to give a task a home.
- **A declared ref MUST be a DIRECT mechanism whose `primary_files` CONTAINS this task's path.** The tool REJECTS (rc=3) any ref attached to a path that does not realize/exercise it (filler / mis-attribution / ID-parking). `documented` IDs and `delegated` (AC) IDs MUST NOT appear as refs (rc=3) — task a delegate's `<ID>` instead.
- **refs** when present: comma-separated, NO SPACES (`REQ-001,AC-002`), at most **3** per line, no duplicates.
- **gloss** = ≤15-word paraphrase of the asserted criteria. Free text (never grepped). Name asserted AC/INV here on verification/GATE tasks (not in refs).
- The `[P]` marker is absent by default. Add it only when plan evidence establishes that adjacent marked tasks are both file-disjoint and dependency-independent. Sequential top-to-bottom order is always correct on its own.
- The `[USn]` marker maps 1:1 to UJ-NNN in spec (US1 ↔ UJ-001); present on story-phase tasks only, omitted in Setup/Expand and Contract.

<!--
  LAYOUT CONTRACT: Keep this section exactly here: after the Format rules and
  immediately before the first horizontal rule / Execution Order section.
  Replace only the JSON inside the single task-context fence. Do not move or
  duplicate this heading or fence.
-->
## Task Context (Machine-Readable)

`/order.tasks` MUST replace only the JSON payload in this fence with exactly one
entry for every task. Keep this heading and fence at this fixed location. It is
the single source of truth for task read context. `/order.code` MUST NOT
invent or edit per-task file lists; it resolves this block through
`task_context.py` before each task.

```task-context
{
  "version": 1,
  "tasks": {}
}
```

Each `read` item is one existing repo-relative file that the task worker must
inspect before editing. `target_state` is `new`, `mod`, or `del`, copied from
the task path's `[NEW]`/`[MOD]`/`[DEL]` status in `plan.md`. Include a `mod` or
`del` write target and only the exact source/config/test files required by that
task. New write targets are not readable until created. Paths must be literal
files, not directories or globs. The resolver validates existence, path safety,
task coverage, and output order. Optional `contract_refs` carries exact spec IDs
needed by support paths without claiming traceability ownership on the task
line.

<!--
  IMPORTANT: Tasks below are SAMPLE placeholders. The /order.tasks command MUST
  replace them with real tasks derived from spec.md (UJ/AC/REQ/EDGE/INV IDs) and
  exact file paths from plan.md. Renumber T001..TNNN sequentially. DO NOT keep
  sample tasks in the generated file.

  FORMAT RULE: every task line is pipe-delimited — `T### [markers] | path | refs? | gloss`.
  The path is a RAW plan.md path with NO backticks. refs is OPTIONAL — infra tasks (barrel/wiring/fixture/GATE) carry EMPTY refs. A declared ref MUST be a direct
  mechanism whose primary_files contains that task's path (else rc=3). Never invent a ref to home a task. Coverage is proven by `traceability.py extract-trace`, NOT by any hand-written table.
  Every test-writing task's OWN gloss MUST say it is expected to fail before
  implementation; the section heading is not enough. Every command-only lint
  or typecheck task MUST start with VERIFY:, forbid autofix/writes, and stop on
  failure.

  DO NOT author a Traceability Matrix or a Files Touched table in the generated
  tasks.md. Coverage is derived by extract-trace into .state/traceability.tsv.
  A hand-built matrix is exactly the drift this system removes. If this template
  ever grows such a section, delete it.

  Do NOT copy these explanatory notes into the generated tasks.md.
-->

---

## Execution Order

[Render the plan-derived order. End with Contract only for a migration work order; otherwise end with Final Verification.]

- Phases are hard sequential barriers; within a phase, execute tasks top-to-bottom.
- Test tasks within a story phase are written first and MUST fail before their implementation tasks.

---

## Phase 1: Setup & Expand (Safe, Non-Breaking Additions)

**Purpose**: Prepare models, validation, config, and interface boundaries without breaking existing flows.

- [ ] T001 [P] | src/models/[entity].ext | REQ-001 | core entity schema: fields and plugins
- [ ] T002 [P] | src/validations/[entity].ext | REQ-002 | Joi/validation schemas for create and update bodies
- [ ] T003 | src/models/index.js |  | register new model and validation in barrel/index (single task — all barrel edits here; empty refs — infra, no coverage)

---

## Phase 2: Migrate & Implement — User Story 1 (Priority: P1) 🎯 MVP

**Goal**: [Brief description from Spec § Acceptance Criteria]
**Verification**: Run [test command from plan.md]; assert AC-NNN.. pass and INV-NNN.. hold.

### Tests (Write First, Verify Failure)

- [ ] T004 [US1] | tests/[file].ext | AC-001,AC-002 | expect failure before implementation: test US1 happy-path endpoints

### Implementation

- [ ] T005 [US1] | src/services/[entity].ext | REQ-003 | service logic realizing the core mechanism
- [ ] T006 [US1] | src/controllers/[entity].ext | REQ-003,NFR-003 | controller handlers with catchAsync; 404 only if never existed
- [ ] T007 [US1] | src/routes/[entity].ext | REQ-003 | routes with auth and validate middleware
- [ ] T008 [US1] | src/services/[entity].ext | EDGE-001 | handle US1 edge case in service

**Checkpoint**: User Story 1 (MVP) is fully functional, backwards-compatible, and independently testable.

---

## Phase 3: Migrate & Implement — User Story 2 (Priority: P2)

**Goal**: [Brief description from Spec § Acceptance Criteria]
**Verification**: Run [test command]; assert AC-NNN.. pass with no regressions on US1.

### Tests (Write First, Verify Failure)

- [ ] T010 [US2] | tests/[file].ext | AC-003 | expect failure before implementation: test US2 behavior

### Implementation

- [ ] T011 [US2] | src/services/[entity].ext | REQ-004 | extend service logic for US2
- [ ] T012 [US2] | src/routes/[entity].ext | REQ-004,EDGE-002 | wire US2 endpoint and handle edge case

**Checkpoint**: User Stories 1 and 2 both functional and backwards-compatible.

---

[Add more story phases as needed, one per remaining UJ in priority order, same shape.]

---

## Final Phase: Contract or Final Verification

**Purpose**: Verify everything. Perform irreversible cleanup only when `plan.md` declares it; otherwise this is a read-only Final Verification phase.

- [ ] T0XX | [test file path from plan.md pathmanifest] |  | GATE: run [test command from plan.md] — verify all AC-* pass, INV-* hold, NFR-* met; STOP on failure (contraction is irreversible). Empty refs — verification asserts, does not realize. Path MUST be a real test file from pathmanifest (not a command) so M8 passes.
- [ ] T0XX | [cleanup path from plan.md] |  | remove only plan-declared deprecated mechanism after GATE
- [ ] T0XX | [relevant path from plan.md pathmanifest] |  | VERIFY: run [lint/typecheck command] without autofix; STOP on failure
- [ ] T0XX | [documentation path from plan.md] |  | update plan-declared technical documentation

---

## Notes

- Coverage is proven by the tool, never hand-built: `extract-trace` writes `.state/traceability.tsv`. Do NOT author a coverage matrix or a files-touched table here.
- `[P]` requires explicit plan evidence of file-disjointness and dependency independence. Absence means sequential execution.
- The `[USn]` marker traces a task to its user story.
- Each task is self-contained: raw path + spec IDs + ≤15-word gloss, so the implementer need not re-open spec.md.
- Every test task's own gloss states expected failure before implementation; earlier phases do not pre-implement tested behavior.
- `GATE:` and `VERIFY:` tasks are read-only and report `changed_files: []`.
- Stop at checkpoints to validate stories independently.
- A direct ref belongs on the task whose path equals its `primary_files` (the task that realizes/exercises it), never parked on a barrel/verify/GATE task. This is machine-enforced: extract-trace rejects (rc=3) a ref whose primary_files does not contain that task's path. Infra tasks carry EMPTY refs.
- Avoid: vague tasks, same-file `[P]` conflicts, cross-story dependencies that break independence, retrofitting a mechanism into already-written code, splitting many unrelated REQ/AC into one oversized task just to satisfy coverage.
