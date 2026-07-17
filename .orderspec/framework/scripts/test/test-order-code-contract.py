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
task_context_schema = json.loads(
    (FRAMEWORK / "schemas" / "task-context.schema.json").read_text(encoding="utf-8")
)
expect(
    "mandatory for behavior-bearing support tasks" in tasks_prompt,
    "order.tasks supplies exact contract context to support paths",
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
expect("task-context" in rules and "task_context.py" in rules, "framework rules define task context authority")
expect("Plan/work-order baseline rules" in rules, "framework rules freeze work-order baseline")

print("All order-code contract tests passed")
