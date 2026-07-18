#!/usr/bin/env python3
"""Static contract checks for shared blocking-feedback routing and intake."""

import json
from pathlib import Path


FRAMEWORK = Path(__file__).resolve().parents[2]


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


manifest = json.loads((FRAMEWORK / "command-context.json").read_text(encoding="utf-8"))
defaults = manifest["defaults"]["required"]
expect(
    any(item.get("ref") == "protocol.blocking_feedback" for item in defaults),
    "every command receives the shared blocking-feedback protocol",
)

protocol = (FRAMEWORK / "protocols" / "blocking-feedback.md").read_text(encoding="utf-8")
normalized_protocol = " ".join(protocol.split())
expect(
    "Never create an informal report" in normalized_protocol
    and "call a check recursively" in normalized_protocol,
    "block persistence does not counterfeit or recursively invoke gate reports",
)
expect(
    "command_context.py resolve" in protocol and "feedback.open" in protocol,
    "owner intake is supplied by command context",
)
expect(
    "Close an active attempt before creating feedback" in normalized_protocol,
    "code attempts close before cross-stage feedback writes",
)

for command in ("order.bootstrap", "order.spec", "order.plan", "order.tasks"):
    prompt = (FRAMEWORK / "prompts" / f"{command}.md").read_text(encoding="utf-8")
    expect("feedback.open" in prompt, f"{command} consumes resolver feedback intake")

print("All blocking-feedback contract tests passed")
