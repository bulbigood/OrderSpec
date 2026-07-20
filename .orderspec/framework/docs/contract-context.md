# Bounded Contract Context

## Information Model identity

Behavioural IDs (`REQ`, `INV`, `IF`, and related prefixes) describe observable
obligations. Information Model blocks describe the exact logical shapes needed
to implement those obligations. They use a separate context-only identity:

```markdown
### Entity ENT-001: Task
### Structure STR-001: Mutation Snapshot
### Value Set VAL-001: Task Status
```

`ENT`, `STR`, and `VAL` IDs are append-only. They are legal in task-context
`contract_refs`, but illegal in a task line's coverage field and never require a
mechanism row. This prevents schema tasks from claiming behavioural coverage
while still giving their worker exact, bounded field and value tables.

`task_contract_context.py` resolves each reference to one exact block. A model
block ends at the next level-two/level-three heading. A behavioural block ends
at the next behavioural anchor or level-two heading, preventing the final ID in
a section from accidentally absorbing later sections.

## Authoring and gates

`/order.spec` and `/order.code-to-spec` assign kind-specific IDs. `/order.tasks`
adds the smallest complete model reference set to each schema-bearing task.
`/order.tasks-check` treats behavioural refs without required field/value blocks
as insufficient context.

Mechanical spec validation emits blocking `M41` findings for missing, malformed,
duplicate, or kind-mismatched Information Model IDs. Contract resolution also
rejects those defects, so advisory upstream gates cannot allow an unaddressable
Information Model into `/order.code`.

## Migration from framework 0.6

Existing headings migrate without changing their logical content:

```markdown
### Entity: Task          -> ### Entity ENT-001: Task
### Structure: Snapshot  -> ### Structure STR-001: Snapshot
### Value Set: Status    -> ### Value Set VAL-001: Status
```

Allocate numbers independently per prefix, preserve them on later refinement,
then regenerate/refine `tasks.md` so model/schema tasks reference every required
entity, nested structure, and value set. Run `/order.spec-check`, `/order.plan`,
`/order.plan-check`, `/order.tasks`, and `/order.tasks-check` before resuming
implementation.

## Attempt boundary

Attempt state v3 stores the exact rendered worker envelope in one canonical
`current.json` slot. Exclusive creation makes parallel active snapshots
unrepresentable. Repeating `attempt-begin` for the same execution unit returns
`RESUME_ATTEMPT` with the same attempt ID, envelope, and result path.

An active attempt must pass through `attempt-finish`. A successful attempt must
then be verified, marked, and cleaned. `code_workflow.py finish` and
`workflow_supervisor.py evaluate` reject a command boundary while either state
is unfinished. Terminal worker failures move atomically to diagnostic history
and no longer participate in boundary discovery. `attempt-recover` therefore
returns exactly one legal action for the canonical slot.
