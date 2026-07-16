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
    resources["protocol.sub_agent_execution"]["usage"] == "apply"
    and resources["protocol.sub_agent_execution"]["authority"] == "framework",
    "sub-agent protocol has framework apply authority",
)

code_prompt = (FRAMEWORK / "prompts" / "order.code.md").read_text(encoding="utf-8")
expect("LOCAL_PHASE" in code_prompt and "LOCAL_ALL" in code_prompt, "order.code documents local fallback modes")
expect("task_progress.py mark" in code_prompt, "order.code delegates marker writes to deterministic script")
expect("`**Verification**` line" in code_prompt, "order.code uses phase Verification prose")

protocol = (FRAMEWORK / "protocols" / "sub-agent-execution.md").read_text(encoding="utf-8")
expect("read_paths" in protocol and "write_paths" in protocol, "protocol defines read/write allowlists")
expect("NEEDS_CONTEXT" in protocol and "changed_files" in protocol, "protocol defines bounded worker result")

rules = (FRAMEWORK / "orderspec-rules.md").read_text(encoding="utf-8")
expect("task_progress.py" in rules, "framework rules define marker ownership")

print("All order-code contract tests passed")
