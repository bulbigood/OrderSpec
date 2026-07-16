---
orderspec:
  artifact: protocol
  authority: framework
---

# OrderSpec Sub-Agent Execution Protocol

## Purpose

This protocol defines the boundary between `/order.code` coordinator and one
task worker. It is framework procedure for the coordinator. The worker receives
the rendered task packet; it does not read this file, `command-context.json`,
`orderspec-rules.md`, project contracts, `spec.md`, `plan.md`, or the whole
repository unless the coordinator explicitly includes an exact path in the
packet.

## Coordinator contract

Coordinator MUST prepare one packet per task. Packet fields:

```yaml
task_id: T###
phase: phase name
task_line: exact tasks.md line
objective: one imperative sentence
read_paths:
  - exact repo-relative file path
write_paths:
  - exact repo-relative task path
context:
  - short excerpt or fact prepared by coordinator
verification:
  command: exact command, or null
  expected: observable success condition
stop_conditions:
  - missing required context
  - task contradicts supplied context
  - required change outside write_paths
```

Rules:

- `read_paths` MUST be an explicit finite list. No directories, globs, or
  repository-wide searches.
- `write_paths` MUST contain exactly the task `path` field. A task requiring
  another file is a task decomposition or plan defect, not worker discretion.
- Coordinator MUST read OrderSpec Markdown artifacts and project contracts
  itself, then pass only the minimum relevant excerpts in `context`.
- By default, worker MUST NOT open any `.md` file. A Markdown target may be
  included only when the task path itself is that Markdown file.
- Coordinator MUST NOT pass `plan.md`, `spec.md`, contracts, or framework rules
  as worker paths. Their relevant facts belong in `context`.
- `verification.command` is allowed only when the command is declared by the
  task/plan and permitted by project governance.
- Network access, package installation, git mutation, new sub-agents, and
  unrelated commands are forbidden.

## Worker contract

Worker is a literal executor, not a planner or reviewer.

- Read only `read_paths` and inline `context`.
- Modify only `write_paths`.
- Follow `objective` and `task_line` literally.
- Do not infer missing requirements or choose architecture.
- Do not broaden scope, create stubs, fix unrelated defects, or edit task
  checkboxes.
- Do not start another worker.
- Do not expose chain-of-thought or perform an open-ended reasoning report.
- If any stop condition occurs, stop without guessing and return `BLOCKED` or
  `NEEDS_CONTEXT`.
- Return one result object. Do not claim success without observable evidence.

## Worker result

Worker result MUST have this shape:

```json
{
  "task_id": "T###",
  "status": "SUCCESS|FAILED|BLOCKED|NEEDS_CONTEXT",
  "changed_files": ["repo/relative/path"],
  "verification": {
    "status": "PASS|FAIL|NOT_RUN",
    "evidence": "short observable result"
  },
  "deviation": null
}
```

`SUCCESS` requires:

- matching `task_id`;
- every changed file is in `write_paths`;
- verification is `PASS` when task declares verification;
- no `deviation` requiring a design decision.

`FAILED`, `BLOCKED`, or `NEEDS_CONTEXT` leaves task unchecked. Worker output
never changes `[X]` markers.

## Coordinator completion sequence

For each task, coordinator MUST:

1. Build packet from the exact task line and explicitly read context.
2. Dispatch packet in `DELEGATED`, or execute the same packet locally in
   `LOCAL_PHASE`/`LOCAL_ALL`.
3. Parse the result and inspect the allowed diff only.
4. Run declared verification and capture its observable result.
5. Call the deterministic task-state script to mark that exact task `[X]`.
6. Continue only after the marker script succeeds.

On worker failure, invalid result, unexpected changed path, or marker failure:
stop before the next task. Preserve the task unchecked and report the exact
task ID and stopping reason.
