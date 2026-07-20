#!/usr/bin/env python3
"""Deterministic policy classifier for continuous OrderSpec execution.

The classifier never answers an operator question. It maps a typed workflow
event to AUTO_ROUTE, RETRY, PAUSE, or STOP using operator-owned configuration,
then applies non-overridable safety and loop limits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from common import get_repo_root


CONFIG_PATH = Path(".orderspec/config/automation.json")
KINDS = {"ADVANCE", "ROUTE", "OPERATOR_INPUT", "RUNTIME", "COMPLETE"}
ACTIONS = {"auto_route", "retry", "pause", "stop"}
DECISIONS = {
    "auto_route": "AUTO_ROUTE",
    "retry": "RETRY",
    "pause": "PAUSE",
    "stop": "STOP",
    "complete": "COMPLETE",
}
DEFAULT_KEYS = {
    "ADVANCE": "advance",
    "ROUTE": "route",
    "OPERATOR_INPUT": "operator_input",
    "RUNTIME": "runtime_failure",
}
DEFAULT_ACTIONS = {
    "advance": {"auto_route", "pause", "stop"},
    "route": {"auto_route", "pause", "stop"},
    "operator_input": {"pause", "stop"},
    "runtime_failure": {"retry", "pause", "stop"},
}
MATCH_FIELDS = {"kind", "reason", "source", "target", "severity", "destructive"}
CONTEXT_BETWEEN = {"fresh", "resume", "compact"}
CONTEXT_AFTER_INPUT = {"resume", "fresh"}
COMMANDS = {
    "order.bootstrap",
    "order.feature",
    "order.spec",
    "order.code-to-spec",
    "order.spec-check",
    "order.plan",
    "order.plan-check",
    "order.tasks",
    "order.tasks-check",
    "order.code",
    "order.code-check",
}
ADVANCE_TARGETS = {
    "order.bootstrap": "order.feature",
    "order.feature": "order.spec",
    "order.spec": "order.spec-check",
    "order.code-to-spec": "order.spec-check",
    "order.spec-check": "order.plan",
    "order.plan": "order.plan-check",
    "order.plan-check": "order.tasks",
    "order.tasks": "order.tasks-check",
    "order.tasks-check": "order.code",
    "order.code": "order.code-check",
}
ROUTE_TARGETS = {
    "order.bootstrap": set(),
    "order.feature": {"order.bootstrap"},
    "order.spec": {"order.bootstrap", "order.feature"},
    "order.code-to-spec": {"order.bootstrap", "order.feature"},
    "order.spec-check": {"order.spec"},
    "order.plan": {"order.bootstrap", "order.spec"},
    "order.plan-check": {"order.plan", "order.spec"},
    "order.tasks": {"order.bootstrap", "order.plan", "order.spec"},
    "order.tasks-check": {"order.tasks", "order.plan", "order.spec"},
    "order.code": {"order.bootstrap", "order.code", "order.tasks", "order.plan", "order.spec"},
    "order.code-check": {"order.code", "order.tasks", "order.plan", "order.spec"},
}
TERMINAL_COMMANDS = {
    "order.spec-check",
    "order.plan-check",
    "order.tasks-check",
    "order.code-check",
}
HARD_OPERATOR_REASONS = {
    "SEMANTIC_DECISION",
    "SCOPE_CLARIFICATION",
    "MUTATION_APPROVAL",
    "TOOL_INSTALL_APPROVAL",
    "GOVERNANCE_APPROVAL",
    "CANDIDATE_SELECTION",
    "WORK_ORDER_RESET_REQUIRED",
    "CREDENTIALS_REQUIRED",
    "PERMISSION_REQUIRED",
}
REASONS_BY_KIND = {
    "ADVANCE": {"STAGE_COMPLETE"},
    "ROUTE": {"ARTIFACT_DEFECT", "UPSTREAM_DEFECT", "IMPLEMENTATION_REPAIR"},
    "OPERATOR_INPUT": HARD_OPERATOR_REASONS,
    "RUNTIME": {"TRANSIENT_FAILURE", "FRAMEWORK_ERROR"},
    "COMPLETE": {"WORKFLOW_COMPLETE"},
}


def emit(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _exact_keys(value: dict[str, Any], allowed: set[str], label: str, errors: list[str]) -> None:
    extra = sorted(set(value) - allowed)
    if extra:
        errors.append(f"{label} has unsupported keys: {extra}")


def _positive_int(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        errors.append(f"{label} must be a positive integer")


def validate_config(data: Any) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return None, ["automation config must be a JSON object"]
    _exact_keys(data, {"$schema", "version", "enabled", "context", "defaults", "rules", "limits"}, "config", errors)
    if data.get("version") != 1:
        errors.append("version must be 1")
    if not isinstance(data.get("enabled"), bool):
        errors.append("enabled must be a boolean")

    context = data.get("context")
    if not isinstance(context, dict):
        errors.append("context must be an object")
        context = {}
    else:
        _exact_keys(context, {"between_commands", "after_operator_input"}, "context", errors)
    if context.get("between_commands") not in CONTEXT_BETWEEN:
        errors.append("context.between_commands must be fresh, resume, or compact")
    if context.get("after_operator_input") not in CONTEXT_AFTER_INPUT:
        errors.append("context.after_operator_input must be resume or fresh")

    defaults = data.get("defaults")
    if not isinstance(defaults, dict):
        errors.append("defaults must be an object")
        defaults = {}
    else:
        _exact_keys(defaults, set(DEFAULT_ACTIONS), "defaults", errors)
    for key, allowed in DEFAULT_ACTIONS.items():
        action = defaults.get(key)
        if action not in allowed:
            errors.append(f"defaults.{key} must be one of: {', '.join(sorted(allowed))}")

    limits = data.get("limits")
    if not isinstance(limits, dict):
        errors.append("limits must be an object")
        limits = {}
    else:
        _exact_keys(limits, {"max_transitions", "max_routes", "max_same_event"}, "limits", errors)
    for key in ("max_transitions", "max_routes", "max_same_event"):
        _positive_int(limits.get(key), f"limits.{key}", errors)

    rules = data.get("rules")
    if not isinstance(rules, list):
        errors.append("rules must be an array")
        rules = []
    seen_ids: set[str] = set()
    for index, rule in enumerate(rules):
        label = f"rules[{index}]"
        if not isinstance(rule, dict):
            errors.append(f"{label} must be an object")
            continue
        _exact_keys(rule, {"id", "match", "action", "max_occurrences"}, label, errors)
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", rule_id):
            errors.append(f"{label}.id must be a lowercase kebab-case identifier")
        elif rule_id in seen_ids:
            errors.append(f"duplicate rule id: {rule_id}")
        else:
            seen_ids.add(rule_id)
        match = rule.get("match")
        if not isinstance(match, dict) or not match:
            errors.append(f"{label}.match must be a non-empty object")
        else:
            _exact_keys(match, MATCH_FIELDS, f"{label}.match", errors)
            for field, expected in match.items():
                values = expected if isinstance(expected, list) else [expected]
                if not values or any(not isinstance(item, (str, bool)) for item in values):
                    errors.append(f"{label}.match.{field} must be a string, boolean, or non-empty array of them")
                if field == "kind" and any(item not in KINDS for item in values):
                    errors.append(f"{label}.match.kind contains an unsupported kind")
                if field == "reason" and any(
                    item not in set().union(*REASONS_BY_KIND.values()) for item in values
                ):
                    errors.append(f"{label}.match.reason contains an unsupported reason")
                if field in {"source", "target"} and any(item not in COMMANDS for item in values):
                    errors.append(f"{label}.match.{field} contains an unsupported command")
                if field == "severity" and any(
                    item not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"} for item in values
                ):
                    errors.append(f"{label}.match.severity contains an unsupported severity")
                if field == "destructive" and any(not isinstance(item, bool) for item in values):
                    errors.append(f"{label}.match.destructive must contain booleans")
        if rule.get("action") not in ACTIONS:
            errors.append(f"{label}.action must be one of: {', '.join(sorted(ACTIONS))}")
        if "max_occurrences" in rule:
            _positive_int(rule.get("max_occurrences"), f"{label}.max_occurrences", errors)

    return (data if not errors else None), errors


def validate_event(data: Any) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return None, ["automation event must be a JSON object"]
    allowed = {
        "version", "id", "kind", "reason", "source", "target", "severity",
        "destructive", "summary", "evidence", "interaction",
    }
    _exact_keys(data, allowed, "event", errors)
    if data.get("version") != 1:
        errors.append("event.version must be 1")
    event_id = data.get("id")
    if not isinstance(event_id, str) or not event_id.strip():
        errors.append("event.id must be a non-empty string")
    kind = data.get("kind")
    if kind not in KINDS:
        errors.append(f"event.kind must be one of: {', '.join(sorted(KINDS))}")
    reason = data.get("reason")
    if not isinstance(reason, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", reason):
        errors.append("event.reason must be an uppercase identifier")
    elif kind in REASONS_BY_KIND and reason not in REASONS_BY_KIND[kind]:
        errors.append(f"event.reason {reason} is not valid for {kind}")
    source = data.get("source")
    if not isinstance(source, str) or source not in COMMANDS:
        errors.append("event.source must be a supported OrderSpec command")
    target = data.get("target")
    if kind in {"ADVANCE", "ROUTE"}:
        if not isinstance(target, str) or target not in COMMANDS:
            errors.append("ADVANCE and ROUTE events require a supported OrderSpec target")
    elif target is not None:
        errors.append("OPERATOR_INPUT, RUNTIME, and COMPLETE events require target=null or omitted")
    severity = data.get("severity")
    if severity is not None and severity not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        errors.append("event.severity must be LOW, MEDIUM, HIGH, CRITICAL, or null")
    destructive = data.get("destructive", False)
    if not isinstance(destructive, bool):
        errors.append("event.destructive must be a boolean")
    for field in ("summary", "evidence"):
        value = data.get(field, "")
        if not isinstance(value, str):
            errors.append(f"event.{field} must be a string")
    if kind in {"ROUTE", "COMPLETE"} and (
        not isinstance(data.get("evidence"), str) or not data.get("evidence", "").strip()
    ):
        errors.append(f"{kind} requires non-empty evidence")

    interaction = data.get("interaction")
    if kind == "OPERATOR_INPUT":
        if not isinstance(interaction, dict):
            errors.append("OPERATOR_INPUT requires interaction")
        else:
            _exact_keys(
                interaction,
                {
                    "id", "kind", "question", "response_type", "options", "choices",
                    "exact_action", "resume_strategy",
                },
                "event.interaction",
                errors,
            )
            if not isinstance(interaction.get("id"), str) or not interaction.get("id", "").strip():
                errors.append("interaction.id must be a non-empty string")
            if interaction.get("kind") != reason:
                errors.append("interaction.kind must equal event.reason")
            if not isinstance(interaction.get("question"), str) or not interaction.get("question", "").strip():
                errors.append("interaction.question must be a non-empty string")
            response_type = interaction.get("response_type", "choice")
            if response_type not in {"choice", "text"}:
                errors.append("interaction.response_type must be choice or text")
            options = interaction.get("options")
            if response_type == "choice":
                if not isinstance(options, list) or len(options) < 2 or any(not isinstance(item, str) or not item for item in options):
                    errors.append("choice interaction.options must contain at least two non-empty strings")
                choices = interaction.get("choices")
                if not isinstance(choices, list) or len(choices) < 2:
                    errors.append("choice interaction.choices must describe every option")
                else:
                    choice_values: list[str] = []
                    for index, choice in enumerate(choices):
                        label = f"interaction.choices[{index}]"
                        if not isinstance(choice, dict):
                            errors.append(f"{label} must be an object")
                            continue
                        _exact_keys(choice, {"value", "label", "consequence"}, label, errors)
                        for field in ("value", "label", "consequence"):
                            if not isinstance(choice.get(field), str) or not choice.get(field, "").strip():
                                errors.append(f"{label}.{field} must be a non-empty string")
                        if isinstance(choice.get("value"), str):
                            choice_values.append(choice["value"])
                    if isinstance(options, list) and choice_values != options:
                        errors.append("interaction.choices values must match interaction.options in order")
            else:
                if options not in (None, []):
                    errors.append("text interaction.options must be omitted or empty")
                if interaction.get("choices") not in (None, []):
                    errors.append("text interaction.choices must be omitted or empty")
            if interaction.get("resume_strategy", "same_session") not in {"same_session", "fresh_session"}:
                errors.append("interaction.resume_strategy must be same_session or fresh_session")
            exact_action = interaction.get("exact_action")
            if exact_action is not None and not isinstance(exact_action, str):
                errors.append("interaction.exact_action must be a string or null")
    elif interaction is not None:
        errors.append("interaction is allowed only for OPERATOR_INPUT")

    normalized = None
    if not errors:
        normalized = {
            "version": 1,
            "id": event_id,
            "kind": kind,
            "reason": reason,
            "source": source,
            "target": target,
            "severity": severity,
            "destructive": destructive,
            "summary": data.get("summary", ""),
            "evidence": data.get("evidence", ""),
            "interaction": interaction,
        }
        if interaction is not None:
            normalized["interaction"] = {
                **interaction,
                "response_type": interaction.get("response_type", "choice"),
                "resume_strategy": interaction.get("resume_strategy", "same_session"),
            }
    return normalized, errors


def event_fingerprint(event: dict[str, Any]) -> str:
    identity = {
        key: event.get(key)
        for key in ("kind", "reason", "source", "target", "severity", "destructive")
    }
    if event.get("kind") in {"ROUTE", "RUNTIME"}:
        identity["summary"] = " ".join(event.get("summary", "").split())
        identity["evidence"] = " ".join(event.get("evidence", "").split())
    elif event.get("kind") == "OPERATOR_INPUT":
        interaction = event.get("interaction") or {}
        identity["interaction"] = {
            "kind": interaction.get("kind"),
            "question": " ".join(interaction.get("question", "").split()),
        }
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20]


def _matches(match: dict[str, Any], event: dict[str, Any]) -> bool:
    for field, expected in match.items():
        values = expected if isinstance(expected, list) else [expected]
        if event.get(field) not in values:
            return False
    return True


def classify(
    config: dict[str, Any],
    event: dict[str, Any],
    counters: dict[str, int] | None = None,
) -> dict[str, Any]:
    counters = counters or {}
    fingerprint = event_fingerprint(event)
    matched_rule: dict[str, Any] | None = None
    requested_action: str
    basis: str

    if not config["enabled"]:
        requested_action = "pause"
        basis = "automation-disabled"
    elif event["kind"] == "COMPLETE":
        requested_action = "complete"
        basis = "terminal:complete"
    else:
        matched_rule = next((rule for rule in config["rules"] if _matches(rule["match"], event)), None)
        if matched_rule is not None:
            requested_action = matched_rule["action"]
            basis = matched_rule["id"]
        else:
            default_key = DEFAULT_KEYS[event["kind"]]
            requested_action = config["defaults"][default_key]
            basis = f"default:{default_key}"

    action = requested_action
    override: str | None = None
    occurrence_key = f"rule:{basis}:event:{fingerprint}"
    if matched_rule is not None and matched_rule.get("max_occurrences") is not None:
        if counters.get(occurrence_key, 0) >= matched_rule["max_occurrences"]:
            action = "pause"
            override = "rule occurrence limit reached"

    if event["kind"] == "OPERATOR_INPUT" or event["reason"] in HARD_OPERATOR_REASONS:
        if action not in {"pause", "stop"}:
            action = "pause"
            override = "operator input cannot be answered automatically"
    if action == "auto_route" and event["kind"] not in {"ADVANCE", "ROUTE"}:
        action = "pause"
        override = "AUTO_ROUTE is valid only for ADVANCE or ROUTE"
    if action == "retry" and event["kind"] != "RUNTIME":
        action = "pause"
        override = "RETRY is valid only for RUNTIME"
    if event["destructive"] and action not in {"pause", "stop"}:
        action = "pause"
        override = "destructive transition requires operator review"
    if event["kind"] == "RUNTIME" and event["reason"] == "FRAMEWORK_ERROR":
        action = "stop"
        override = "framework errors are not workflow routes"

    limits = config["limits"]
    if action in {"auto_route", "retry"}:
        if counters.get("transitions", 0) >= limits["max_transitions"]:
            action = "pause"
            override = "maximum transition count reached"
        elif event["kind"] == "ROUTE" and counters.get("routes", 0) >= limits["max_routes"]:
            action = "pause"
            override = "maximum route count reached"
        elif (
            event["kind"] in {"ROUTE", "RUNTIME"}
            and counters.get(f"event:{fingerprint}", 0) >= limits["max_same_event"]
        ):
            action = "pause"
            override = "same-event cycle limit reached"

    context_strategy = config["context"]["between_commands"]
    if action == "retry":
        context_strategy = "resume"
    if event["kind"] == "OPERATOR_INPUT":
        context_strategy = config["context"]["after_operator_input"]

    return {
        "ok": True,
        "decision": DECISIONS[action],
        "requested_action": requested_action,
        "basis": basis,
        "safety_override": override,
        "occurrence_key": occurrence_key,
        "event_fingerprint": fingerprint,
        "context_strategy": context_strategy,
        "target": event.get("target"),
    }


def default_config_path() -> Path:
    return get_repo_root().resolve() / CONFIG_PATH


def load_valid_config(path: Path) -> dict[str, Any]:
    data = read_object(path)
    normalized, errors = validate_config(data)
    if errors or normalized is None:
        raise ValueError("; ".join(errors))
    return normalized


def load_valid_event(path_value: str) -> dict[str, Any]:
    if path_value == "-":
        try:
            data = json.loads(sys.stdin.read())
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid event JSON from stdin: {exc}") from exc
    else:
        data = read_object(Path(path_value))
    normalized, errors = validate_event(data)
    if errors or normalized is None:
        raise ValueError("; ".join(errors))
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify OrderSpec automation events")
    parser.add_argument("-C", "--project-root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--config")
    classify_parser = sub.add_parser("classify")
    classify_parser.add_argument("--config")
    classify_parser.add_argument("--event-file", required=True, help="JSON file or - for stdin")
    classify_parser.add_argument("--counters", default="{}", help="JSON object with current counters")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    config_path = Path(args.config).resolve() if args.config else root / CONFIG_PATH
    try:
        config = load_valid_config(config_path)
        if args.command == "validate":
            emit({"ok": True, "config": str(config_path), "enabled": config["enabled"], "rule_count": len(config["rules"])})
            return 0
        event = load_valid_event(args.event_file)
        counters = json.loads(args.counters)
        if not isinstance(counters, dict) or any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in counters.values()
        ):
            raise ValueError("--counters must be a JSON object of non-negative integers")
        emit({**classify(config, event, counters), "event": event})
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
