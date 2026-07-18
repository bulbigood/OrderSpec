#!/usr/bin/env python3
"""Static regression checks for /order.code orchestration wiring."""

import json
from pathlib import Path


FRAMEWORK = Path(__file__).resolve().parents[2]
ORDERSPEC = FRAMEWORK.parent


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


manifest = json.loads((FRAMEWORK / "command-context.json").read_text(encoding="utf-8"))
resources = manifest["resources"]
code_required = manifest["commands"]["order.code"]["required"]

expect("protocol.sub_agent_execution" in resources, "sub-agent protocol is a manifest resource")
expect(
    any(item.get("ref") == "protocol.sub_agent_execution" for item in code_required),
    "order.code requires sub-agent protocol",
)
expect(
    any(item.get("ref") == "schema.task_context" for item in code_required),
    "order.code requires task context schema",
)
expect(
    manifest["commands"]["order.code"]["feature_context"] == {
        "mode": "required",
        "artifacts": ["tasks", "plan"],
    },
    "order.code loads active tasks before plan",
)
expect(
    resources["protocol.sub_agent_execution"]["usage"] == "apply"
    and resources["protocol.sub_agent_execution"]["authority"] == "framework",
    "sub-agent protocol has framework apply authority",
)

code_prompt = (FRAMEWORK / "prompts" / "order.code.md").read_text(encoding="utf-8")
normalized_code_prompt = " ".join(code_prompt.split())
expect("LOCAL_PHASE" in code_prompt and "LOCAL_ALL" in code_prompt, "order.code documents local fallback modes")
expect(
    "`--local` / `--no-subagents`" in code_prompt
    and "User prohibition of delegation" in code_prompt,
    "order.code gives explicit user local execution priority over dispatch capability",
)
expect(
    "keep all work in one agent session" in normalized_code_prompt
    and "Do not inspect dispatch capability or resolve a worker" in normalized_code_prompt,
    "order.code maps a single-agent-session constraint to local execution",
)
expect("task_progress.py mark" in code_prompt, "order.code delegates marker writes to deterministic script")
expect(
    "task_progress.py reconcile" in code_prompt and "ALREADY_COMPLETE" in code_prompt,
    "order.code reconciles previously completed unchecked work from evidence",
)
expect(
    "work_order.py rollback" in code_prompt and "Step 3.25: RESET Work Order" in code_prompt,
    "order.code reset uses a bounded work-order baseline",
)
expect(
    "workflow_feedback.py create" in code_prompt and "Persistent Routing Report" in code_prompt,
    "order.code persists every upstream route",
)
expect(
    "task_progress.py assert-complete" in normalized_code_prompt
    and "return to Step 9" in normalized_code_prompt,
    "order.code deterministically rejects voluntary partial completion",
)
expect(
    "No Voluntary Partial Completion" in code_prompt
    and "Task count, elapsed work, context size, token/tool budget" in normalized_code_prompt,
    "order.code forbids workload-based LOCAL_ALL chunking",
)
expect(
    "PHASE_COMPLETE" in code_prompt
    and "state is **HALTED** with that evidence" in normalized_code_prompt,
    "order.code distinguishes phase completion from evidenced halt",
)
expect(
    "Marker rejection is terminal" in code_prompt
    and "NEVER alter or retry" in code_prompt,
    "order.code forbids marker-result laundering and retries",
)
expect(
    "If it passes immediately, STOP" in normalized_code_prompt,
    "order.code stops on green-first test tasks",
)
expect("`VERIFY:` tasks" in code_prompt, "order.code defines read-only command gates")
expect("`**Verification**` line" in code_prompt, "order.code uses phase Verification prose")
expect("task_contract_context.py" in code_prompt, "order.code resolves task contract context")
expect(
    "MUST NOT open, search, or preload full" in normalized_code_prompt,
    "order.code forbids bypassing resolved spec excerpts",
)
expect(
    "Frozen Baseline and Pathmanifest Semantics" in code_prompt
    and "Do not run `check-plan`" in code_prompt,
    "order.code preserves plan baseline during resume",
)
expect(
    "Task decomposition defect" in code_prompt
    and "Plan mapping defect" in code_prompt,
    "order.code routes task and plan defects separately",
)
expect("`contract_refs`" in code_prompt, "order.code forwards support-path contract refs")

tasks_prompt = (FRAMEWORK / "prompts" / "order.tasks.md").read_text(encoding="utf-8")
tasks_template = (FRAMEWORK / "templates" / "tasks-template.md").read_text(encoding="utf-8")
task_context_schema = json.loads(
    (FRAMEWORK / "schemas" / "task-context.schema.json").read_text(encoding="utf-8")
)
expect(
    "task_refine.py begin" in tasks_prompt
    and "task_refine.py validate" in tasks_prompt
    and "Refine only" in tasks_prompt,
    "order.tasks Refine protects existing progress without template regeneration",
)
expect(
    "work_order.py capture" in tasks_prompt,
    "order.tasks captures a reset baseline for each new work order",
)
expect(
    "mandatory for behavior-bearing support tasks" in tasks_prompt,
    "order.tasks supplies exact contract context to support paths",
)
expect(
    "Every test-writing task's own gloss MUST state the expected red result" in tasks_prompt
    and "expect failure before implementation:" in tasks_template,
    "order.tasks makes red-first expectation task-local in prompt and template",
)
expect(
    "command-only lint/typecheck task MUST begin with `VERIFY:`" in tasks_prompt
    and "forbid autofix/writes" in tasks_template,
    "order.tasks makes final command verification explicitly read-only",
)
expect(
    "then `render`" not in tasks_prompt
    and "`render` produces" not in tasks_prompt,
    "order.tasks does not invoke removed traceability render command",
)
expect(
    "contract_refs"
    in task_context_schema["properties"]["tasks"]["additionalProperties"]["properties"],
    "task context schema permits support-path contract refs",
)

protocol = (FRAMEWORK / "protocols" / "sub-agent-execution.md").read_text(encoding="utf-8")
expect("task_context" in protocol and "to_read" in protocol, "protocol consumes resolver task context")
expect("MUST be copied verbatim" in protocol, "protocol forbids coordinator whitelist edits")
expect("contract_context" in protocol and "task_contract_context.py" in protocol, "protocol carries exact contract context")
expect("NEEDS_CONTEXT" in protocol and "changed_files" in protocol, "protocol defines bounded worker result")

subagent_rules = (FRAMEWORK / "protocols" / "sub-agent-rules.md").read_text(encoding="utf-8")
expect(
    "If delegation is prohibited" in subagent_rules
    and "Do not inspect, configure" in subagent_rules,
    "sub-agent rules skip worker resolution when user prohibits delegation",
)

rules = (FRAMEWORK / "orderspec-rules.md").read_text(encoding="utf-8")
expect("task_progress.py" in rules, "framework rules define marker ownership")
expect(
    "task_progress.py assert-complete" in rules
    and "not a voluntary resume boundary" in rules,
    "framework rules require deterministic full-execution completion",
)
expect("task-context" in rules and "task_context.py" in rules, "framework rules define task context authority")
expect("Plan/work-order baseline rules" in rules, "framework rules freeze work-order baseline")

print("All order-code contract tests passed")
