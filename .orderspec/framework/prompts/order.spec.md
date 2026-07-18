---
orderspec:
  artifact: command_prompt
  command: order.spec
  phase: specify
description: Create or refine spec.md, the stable feature WHAT-contract.
---

## Role

`/order.spec` owns feature contract content in `spec.md`. It defines observable
behaviour, logical boundaries, requirements, interfaces, information, invariants,
edge cases, journeys, acceptance criteria, and resolved contract decisions.

It MUST NOT prescribe repository files, classes, packages, frameworks, physical
components, implementation mechanisms, tasks, or task order. Interface addresses
such as an HTTP path or event name are contract data, not repository paths.

Gates inspect and route; they never repair `spec.md`. Plans choose repository-specific
WHERE/HOW. Tasks sequence that plan.

## User Input

```text
$ARGUMENTS
```

The arguments are the request. Supported control flags are `--new` and `--split`.
Reject unsupported flags and the combination `--new --split` before mutation.
`--new` always selects Create. `--split` always selects Decompose. Routed reports
and feedback may constrain that mode but never override an explicit flag.

## 1. Resolve Command Context

Before repository inspection or mutation, run:

```bash
python3 .orderspec/framework/scripts/command_context.py resolve order.spec \
  --arguments "$ARGUMENTS" --json
```

Stop when `ok` is false or `missing_required` is non-empty. Read every `to_read`
entry once, in returned order, and apply its declared `usage` and `authority`.
Do not build a second preload list or inspect framework internals.

Use only returned `input.controls` and `input.semantic_input`; do not parse raw
input again.

If project contracts are missing or incomplete, tell the user to run
`/order.bootstrap`; this command does not amend those contracts.

## 2. Resolve the Target Without Writing

Mode selection and all clarification happen before managed-file writes.

Read and validate active feature state:

```bash
python3 .orderspec/framework/scripts/active_feature.py get --json
python3 .orderspec/framework/scripts/active_feature.py validate --json
```

If validation fails, stop with the script result. Do not repair runtime state.

Use only validated active state as existing target. If semantic input names a
different existing feature, do not resolve or switch it here; route the user to
`/order.feature --select <feature-ref>` and stop without mutation.

## Self Gate Report Intake

For the resolved existing target, read `spec.md` and, if present,
`spec-report.md`. Treat report state `CONSUMED_STALE` as inactive. A `BLOCK` or
`ROUTING_REQUIRED` finding routed to `/order.spec` is authoritative Refine input;
other findings remain owned by their routed commands. `input.semantic_input` adds guidance
but does not replace open routed findings.

With `--new`, do not treat the active feature as target and do not load its
self-report or feedback. With `--split`, parent intake may constrain the split,
but mode remains Decompose.

Also load persistent feedback for that target:

```bash
python3 .orderspec/framework/scripts/workflow_feedback.py list \
  --feature-dir "<feature-directory>" --target order.spec
```

Open feedback targeting `order.spec` is authoritative Refine input. Consume it
only after the revised spec passes mechanical validation.

### Mode selection

For empty `input.semantic_input` without an explicit mode flag, resolve the
state-based default before selecting a mode:

```bash
python3 .orderspec/framework/scripts/default_mode.py resolve \
  --command order.spec --feature-dir "<resolved-feature-directory>" \
  --semantic-input "<input.semantic_input>"
```

Omit `--feature-dir` when active-feature resolution found no existing target.

Obey `action`. `RUN/REFINE` selects Refine, including an existing active spec
with no feedback: audit it against current inputs, make only objectively
evidenced corrections, and otherwise report it already aligned. `ASK` means no
active specification exists and a feature description cannot be inferred; ask
one blocking scope question. Never stop merely because semantic input is empty.

Select the mode only after Self Gate Report Intake above:

- **Create**: `--new`; otherwise no active feature, no substantive active `spec.md`, or a
  clearly separate independently releasable contract.
- **Decompose**: `--split`; otherwise an incohesive request containing independently
  releasable contracts.
- **Refine**: without an explicit mode flag, the request, routed report, or open feedback changes the resolved
  existing contract. When a self-gate finding targets `/order.spec`, select **Refine** even when `input.semantic_input` is empty.

If an active spec exists but non-empty input could reasonably mean either Refine
or Create, ask one blocking question. Empty input targets the active spec and is
not ambiguous.

State the selected mode in one line. Do not create directories, write artifacts,
or update state before this point and all blocking questions are resolved.

## 3. Clarify Only Consequential Forks

Ask one question per round when two defensible answers materially
change scope, security/privacy/authorization, interface behaviour, invariants,
retention, consistency/failure semantics, or acceptance. Give a recommended
answer and the observable consequence of each option, then wait. Resolve that
fork before selecting another semantic question.

Do not ask about formatting, naming, or a safe low-impact default. Record such a
default as `ASM-NNN` only when it does not change externally observable behaviour
or IF/INV meaning. Never invent a quantitative threshold.

Blocking questions MUST be resolved before writing. `Q-NNN` is reserved for a
non-blocking unresolved reference or explicitly deferred issue that cannot alter
scope, REQ, NFR, IF, INV, security/privacy, acceptance, or testability.

## 4. Execute the Selected Mode

### Create

An empty feature description is a blocking error.

1. Check cohesion before writing. Size alone is advisory; decompose only when
   the request contains independently releasable contracts.
2. Derive a concise kebab-case slug and allocate the directory:

   ```bash
   python3 .orderspec/framework/scripts/feature_spec.py create \
     --slug "<slug-or-title>" --json
   ```

3. Use only the returned `feature_id`, `slug`, `feature_directory`, and
   `spec_file`. On failure, stop with the script result.
4. Read the canonical `.orderspec/framework/templates/spec-template.md` selected
   by this owning command step, fill it completely, and write the returned
   `spec_file`. Do not leave template tokens or example content.

### Refine

Edit the resolved `spec.md` surgically:

- preserve `orderspec.feature_id`, `orderspec.slug`, and all stable IDs;
- add with the next free ID, edit changed meaning in place, and tombstone removed
  definitions; never renumber or reuse an ID;
- reconcile every affected reference, diagram, model field, interface, invariant,
  edge, journey, criterion, decision, assumption, and contradiction-grid row;
- append one concise row to `## 16. Changelog` using an allowed type from the
  canonical template;
- change frontmatter status only when the artifact review lifecycle changed;
  allowed values are `draft`, `review`, and `approved`.

Do not overwrite an existing spec with the template. Do not derive change history
from Git; summarize only edits made in this run.

### Decompose

Do not write before the user chooses a module. Present cohesive module boundaries,
scope, actors, dependencies, a recommended first module, and one ready-to-run
`/order.spec --new "..."` request per module. Do not allocate feature numbers in
the proposal.

After selection, create at most one module through Create. When splitting an
existing spec, also refine the parent: tombstone moved IDs and point them to the
new namespaced contract. Track both the new module and parent as mutated targets;
neither may bypass validation. Report the remaining module requests.

## 5. Contract Authoring Rules

The canonical spec template controls section structure and frontmatter. These
rules control meaning.

### Stable IDs and references

Definitions use exactly one strict anchor:

```markdown
- **PREFIX-NNN**: Statement.
```

Use only prefixes defined by the resolved identifier resource. Additions use the
next free number. Removed definitions remain anchors, for example:

```markdown
- **REQ-014**: [removed — superseded by `FEAT-002-task-audit:REQ-003`; retained as tombstone]
```

Local references use local IDs. Cross-feature references use the full stable
namespace, for example `FEAT-001-user-auth:IF-003`. Reconcile UJ `Covers`, AC
inline `[Covers: ...]`, IF `Covers`, edge coverage, diagrams, schemas, and the
contradiction grid after every edit.

### Role purity and project constraints

Describe observable WHAT and logical roles. Do not include technology names,
versions, repository paths, code symbols, database/query syntax, or copied
project-contract prose.

`§6` may contain only existing `GOV-NNN`, `STACK-NNN`, `ARCH-NNN`, and
`CONV-NNN` references with neutral labels. Build the valid-ID index from resolved
project contracts. Never invent an ID or amend a contract. If a missing project
constraint is necessary, stop and route a narrow `/order.bootstrap` request.

### Requirements and NFRs

- Each `REQ-NNN` is one observable, testable MUST/MUST NOT statement.
- Specify observable consistency and failure guarantees when they are part of
  WHAT; do not prescribe the transaction, retry, polling, or persistence
  mechanism that implements them.
- A quantitative NFR is allowed only when supplied by the user or a loaded
  project contract, and records `Source: user-request` or the exact contract ID.
- Otherwise use a meaningful qualitative SHOULD, omit the NFR, or ask when the
  decision is consequential. Every NFR needs an observable oracle.

### Information and interfaces

Use logical entities, structures, fields, and value sets; omit the information
model when none applies. Every observable boundary has one `IF-NNN` record in
the template's structured form.

For each applicable IF, make actor/authorization, inputs, optionality,
nullability, success shape, failure outcomes, and malformed-input behaviour
explicit. A paginated interface defines or references bounds, ordering, envelope,
and empty-page semantics. `§9` is the normative source for interface status codes
and response shapes; ACs must agree with it.

For an operation that writes multiple logical records, specify the observable
atomic, partial, best-effort, or compensating guarantee and failure result. This
states contract behaviour, not an implementation mechanism.

### Invariants, edges, journeys, and acceptance

- Invariants are absolute within an explicit scope. Qualifiers and operational
  exceptions belong in REQ/DEC/ASM, not hidden in INV wording.
- Maintain the template's contradiction grid for every absolute INV and every
  applicable INV×NFR, INV×ASM, or narrowing REQ×ASM pair. Resolve conflicts.
- Every edge is covered by a real AC or explicitly deferred with a reason.
- P1 journeys form the smallest coherent MVP. Every UJ states priority, coverage,
  independent test, and observable completion.
- Every REQ is covered by a UJ and AC. Every AC has inline `[Covers: ...]`.
- Every IF is covered by an AC. HTTP success and failure codes agree across IFs
  and ACs.

### Decisions and assumptions

Record a resolved WHAT-decision as `DEC-NNN` when it changes IF or INV meaning;
include `Affects` and rationale. Use `ASM-NNN` only for a low-impact default that
does not change IF/INV meaning. Reflect every decision in the normative section;
DEC/ASM text is not a substitute for the contract.

## 6. Validate and Finalize

Build an ordered list of every spec mutated in this run. Create and Refine have
one target. Decompose has the new module plus the parent when the parent changed.
For each target, use only its resolved or created literal `feature_id` and
`feature_directory`; do not rely on shell variables surviving another step.

After all writes, run these commands in order for **each** mutated target, setting
`FEATURE_ID` and `FEATURE_DIR` from that target's metadata:

```bash
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" \
  --feature-dir "$FEATURE_DIR" init
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" \
  --feature-dir "$FEATURE_DIR" extract-spec-ids
python3 .orderspec/framework/scripts/traceability.py -C "$PWD" \
  --feature-dir "$FEATURE_DIR" validate --stage spec --json
```

`extract-spec-ids` is the only writer of `spec-ids.tsv`; never hand-edit or use
that file as semantic source. Record each target's result separately. On script
failure, follow its disposition. Fix an `/order.spec` finding only when the
correction is unambiguous and does not choose new contract meaning; otherwise
stop and report it. Stop retrying unchanged evidence. Do not update active state
until every mutated target passes.

Before completion, verify no known placeholder, blocking question, contradiction,
role impurity, untraced requirement, interface gap, or unscoped absolute guarantee
remains. Independent severity assignment belongs to `/order.spec-check`.

After every target passes, Create activates its new target. Decompose activates
the newly created selected module; parent validation does not make parent
active:

```bash
python3 .orderspec/framework/scripts/active_feature.py set \
  --feature-id "$FEATURE_ID" \
  --feature-directory "$FEATURE_DIR" \
  --status specified \
  --last-command order.spec --json
```

Refine must not change selection. Update status only when expected feature is
still active:

```bash
python3 .orderspec/framework/scripts/active_feature.py status \
  --feature-id "$FEATURE_ID" \
  --status specified \
  --last-command order.spec --json
```

For each routed self-report actually addressed, mark that target's report
consumed only now:

```bash
python3 .orderspec/framework/scripts/traceability.py mark-consumed \
  --report "$FEATURE_DIR/spec-report.md" \
  --consumer /order.spec \
  --recheck /order.spec-check
```

Consume each addressed feedback item against its owning target only now:

```bash
python3 .orderspec/framework/scripts/workflow_feedback.py consume \
  --feature-dir "$FEATURE_DIR" --id "FB-NNN" --consumer order.spec
```

If marking or consumption fails, report it; do not claim that evidence was
consumed.

## Completion Response

Report mode, every mutated feature ID/path, concise semantic changes and affected
IDs, per-target validation, active-state result, and unresolved routed findings.
For Refine/Decompose, classify downstream impact instead of blanket-invalidating
artifacts. Contract-only IDs, acceptance detail, or schema detail that do not
change WHERE/HOW route directly to argument-free `/order.tasks` for surgical
refinement of unchecked work. Only a physical mapping, mechanism, topology, or
delivery-strategy change routes to `/order.plan`. Do not modify downstream
artifacts here. Recommend `/order.spec-check` when independent assurance is
required.
