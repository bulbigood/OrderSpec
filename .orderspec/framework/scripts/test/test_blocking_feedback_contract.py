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
rules = (FRAMEWORK / "orderspec-rules.md").read_text(encoding="utf-8")
normalized_protocol = " ".join(protocol.split())
normalized_rules = " ".join(rules.split())
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
expect(
    "Before every final response" in normalized_rules
    and "A `RUNNING` run is never a user-visible stop" in normalized_rules
    and "operator_action.recommended_commands" in normalized_rules
    and "operator_action.recommended_command" in normalized_rules
    and "operator_action.recommended_replies" in normalized_rules
    and "choices[].consequence" in normalized_rules
    and "user's configured language" in normalized_rules
    and "Only tokens and exact commands are verbatim machine data" in normalized_rules
    and "copy every entry verbatim and in order" in normalized_rules,
    "every command receives the complete ordered operator-action terminal contract",
)
expect(
    "Never hand-author a supervisor event when a canonical adapter exists" in normalized_rules
    and "`ask` for `OPERATOR_INPUT`" in normalized_rules
    and "CALLER_EVENT_INVALID" in normalized_rules
    and "FRAMEWORK_ADAPTER_FAILURE" in normalized_rules,
    "canonical adapters own operator events and distinguish caller errors from framework failures",
)
expect(
    "--source order.<completed-command>" in normalized_rules
    and "Never chain or batch supervisor transitions" in normalized_rules
    and "STALE_ADVANCE_REJECTED" in normalized_rules,
    "every command binds one supervisor advance to the stage that actually completed",
)
expect(
    "terminal:false" in normalized_rules
    and "continuation_required:true" in normalized_rules
    and "Every supervisor mutation that leaves the run `RUNNING`" in normalized_rules
    and "`final_response` object with `permitted:false`" in normalized_rules
    and "It MUST NOT return an `operator_action`" in normalized_rules
    and "Never self-declare a host interruption" in normalized_rules,
    "RUNNING payloads forbid agent-authored handoff while recovery remains diagnosable",
)

for command in ("order.bootstrap", "order.spec", "order.plan", "order.tasks"):
    prompt = (FRAMEWORK / "prompts" / f"{command}.md").read_text(encoding="utf-8")
    expect("feedback.open" in prompt, f"{command} consumes resolver feedback intake")

print("All blocking-feedback contract tests passed")
