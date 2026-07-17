---
orderspec:
  artifact: protocol
  authority: framework
---

# OrderSpec Sub-Agent Execution Protocol

## Purpose

This protocol defines the boundary between `/order.code` coordinator and one
task worker. It is framework procedure for the coordinator. The worker receives
the rendered task packet and resolver output. Files absent from that output are
unavailable to the worker.

## Coordinator contract

Coordinator MUST prepare one packet per task. Packet fields:

```yaml
task_id: T###
phase: phase name
task_line: exact tasks.md line
objective: one imperative sentence
task_context:
  resolver: python3 .orderspec/framework/scripts/task_context.py resolve --feature-dir "$FEATURE_DIR" --task-id "$TASK_ID" --json
  to_read: exact resolver output, copied verbatim
  write_paths: exact resolver output, copied verbatim
contract_context:
  resolver: python3 .orderspec/framework/scripts/task_contract_context.py resolve --feature-dir "$FEATURE_DIR" --task-id "$TASK_ID" --json
  output: exact resolver output, copied verbatim
context:
  - short excerpt or fact prepared by coordinator
verification:
  command: exact command, or null
  expected: observable success condition
stop_conditions:
  - missing required context
  - task contradicts supplied context
  - required change outside task_context.write_paths
```

Rules:

- `task_context.to_read` MUST be copied verbatim from `task_context.py` output.
  Coordinator MUST NOT add, remove, reorder, or manually recreate entries.
- `task_context.write_paths` MUST be copied verbatim from resolver output. A
  task requiring another write path is a task decomposition or plan defect, not
  worker discretion.
- `contract_context` MUST be copied verbatim from
  `task_contract_context.py`. It is the authoritative mapping from task refs to
  exact `spec.md` excerpts, mechanism rows, and current phase Goal/Verification.
- Coordinator MUST prepare only the minimum relevant inline excerpts in
  `context`; excerpts are not permission to open additional files.
- Worker MUST receive literal file paths only. Directories, globs, and
  repository-wide searches are invalid.
- `verification.command` is allowed only when the command is declared by the
  task/plan and permitted by project governance.
- Environment recovery belongs to the coordinator. A worker that encounters
  an unavailable runtime prerequisite MUST return `BLOCKED`; it MUST NOT ask
  for approval or mutate the environment.
- Network access, package installation, git mutation, new sub-agents, and
  unrelated commands are forbidden.

## Worker contract

Worker is a literal executor, not a planner, reviewer, or reasoner.

- Read only `task_context.to_read`, `contract_context`, and inline `context`.
- Treat `contract_context.spec_excerpts` as the exact contract for every
  referenced spec ID. Do not invent missing requirements or replace excerpts
  with memory or paraphrase.
- Modify only `task_context.write_paths`.
- Follow `objective` and `task_line` literally.
- Do not infer missing requirements or choose architecture.
- Do not broaden scope, create stubs, fix unrelated defects, or edit task
  checkboxes.
- Do not start another worker.
- Do not produce chain-of-thought or an open-ended reasoning report. Return
  only the protocol result object.
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
- every changed file is in `task_context.write_paths`;
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
