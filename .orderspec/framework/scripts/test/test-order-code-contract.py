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
        "artifacts": ["plan", "tasks"],
    },
    "order.code requires active feature plan and tasks",
)
expect(
    resources["protocol.sub_agent_execution"]["usage"] == "apply"
    and resources["protocol.sub_agent_execution"]["authority"] == "framework",
    "sub-agent protocol has framework apply authority",
)

code_prompt = (FRAMEWORK / "prompts" / "order.code.md").read_text(encoding="utf-8")
expect("LOCAL_PHASE" in code_prompt and "LOCAL_ALL" in code_prompt, "order.code documents local fallback modes")
expect("task_progress.py mark" in code_prompt, "order.code delegates marker writes to deterministic script")
expect("`**Verification**` line" in code_prompt, "order.code uses phase Verification prose")
expect("task_contract_context.py" in code_prompt, "order.code resolves task contract context")

protocol = (FRAMEWORK / "protocols" / "sub-agent-execution.md").read_text(encoding="utf-8")
expect("task_context" in protocol and "to_read" in protocol, "protocol consumes resolver task context")
expect("MUST be copied verbatim" in protocol, "protocol forbids coordinator whitelist edits")
expect("contract_context" in protocol and "task_contract_context.py" in protocol, "protocol carries exact contract context")
expect("NEEDS_CONTEXT" in protocol and "changed_files" in protocol, "protocol defines bounded worker result")

rules = (FRAMEWORK / "orderspec-rules.md").read_text(encoding="utf-8")
expect("task_progress.py" in rules, "framework rules define marker ownership")
expect("task-context" in rules and "task_context.py" in rules, "framework rules define task context authority")

print("All order-code contract tests passed")
