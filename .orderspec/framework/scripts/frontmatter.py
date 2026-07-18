#!/usr/bin/env python3
"""frontmatter.py — YAML frontmatter validation for all OrderSpec artifact types.

Portable: Python 3 standard library only. No external dependencies.

Single source of truth for frontmatter structure, required fields,
and validation logic. All artifact types (spec, command_prompt,
gate_report, project_contract, framework_rules, protocol) are validated here.
"""

import json
import re
import sys
from pathlib import Path


# ── constants ─────────────────────────────────────────────────────────────────

SPEC_REQUIRED_METADATA_FIELDS = ["artifact", "feature_id", "slug", "status"]
SPEC_REQUIRED_NESTED_FIELDS = [
    "refs.framework_rules",
    "refs.constitution",
    "refs.stack",
    "refs.architecture",
    "refs.conventions",
    "generator.command",
    "generator.model",
]
SPEC_STATUS_VALUES = {"draft", "review", "approved"}
FEATURE_ID_RE = re.compile(r"^FEAT-[0-9]{3}-[a-z0-9]+(?:-[a-z0-9]+)*$")

COMMAND_PROMPT_REQUIRED_FIELDS = ["artifact", "command", "phase", "description", "handoffs"]
COMMAND_PROMPT_PHASE_VALUES = {"bootstrap", "specify", "plan", "tasks", "implement", "check"}
COMMAND_PROMPT_HANDOFFS_ITEM_FIELDS = {"label", "agent", "prompt"}

GATE_REPORT_REQUIRED_FIELDS = [
    "artifact", "command", "model", "generated_at",
    "verdict", "feature_id", "feature_directory",
]
GATE_REPORT_VERDICT_VALUES = {"PASS", "BLOCK", "ROUTING_REQUIRED"}
CODE_REPORT_ASSURANCE_VALUES = {"EXECUTED", "STATIC_STRONG", "STATIC_LIMITED"}

PROJECT_CONTRACT_REQUIRED_FIELDS = ["artifact", "kind"]
PROJECT_CONTRACT_KIND_VALUES = {"constitution", "stack", "architecture", "conventions"}

FRAMEWORK_RULES_REQUIRED_FIELDS = ["artifact", "authority", "customization"]

PROTOCOL_REQUIRED_FIELDS = ["artifact"]


# ── YAML parsing helpers ──────────────────────────────────────────────────────

def _strip_quotes(value):
    """Remove surrounding single or double quotes from a scalar value."""
    if len(value) >= 2:
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value[1:-1]
    return value


def _parse_yaml_scalar(value):
    """Parse a minimal YAML scalar.

    This intentionally supports only the subset needed by OrderSpec frontmatter:
    strings, booleans, null, and simple inline arrays.
    """
    value = value.strip()

    if value == "":
        return ""

    lowered = value.lower()

    if lowered in {"null", "~"}:
        return None

    if lowered == "true":
        return True

    if lowered == "false":
        return False

    if value.startswith("[") and value.endswith("]"):
        body = value[1:-1].strip()
        if not body:
            return []
        return [_strip_quotes(part.strip()) for part in body.split(",")]

    return _strip_quotes(value)


def extract_yaml_frontmatter(text):
    """Extract YAML frontmatter from text starting with --- ... ---.

    This is a small deterministic parser for the OrderSpec frontmatter subset.
    It supports nested mappings such as:

        orderspec:
          artifact: spec
          refs:
            framework_rules: ".orderspec/framework/orderspec-rules.md"

    It is not a full YAML parser and intentionally avoids external dependencies.
    """
    if not text.startswith("---"):
        return {}

    lines = text.splitlines()
    end_idx = None

    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}

    yaml_lines = lines[1:end_idx]
    root = {}
    stack = [(-1, root)]

    for raw_line in yaml_lines:
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue

        stripped = raw_line.strip()
        if stripped.startswith("- "):
            continue

        if ":" not in raw_line:
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        key, _, value = raw_line.strip().partition(":")
        key = key.strip()
        value = value.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()

        if not stack:
            stack = [(-1, root)]

        parent = stack[-1][1]

        if value == "":
            node = {}
            parent[key] = node
            stack.append((indent, node))
        else:
            parent[key] = _parse_yaml_scalar(value)

    return root


def normalize_frontmatter_scalar(value):
    if not isinstance(value, str):
        return value

    text = value.strip()

    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]

    return text


def looks_like_unresolved_placeholder(value):
    if value is None:
        return True

    s = str(value).strip()

    if not s:
        return True

    return (
        s.startswith("__")
        or s.endswith("__")
        or s.startswith("[")
        or s.endswith("]")
        or s.startswith("{")
        or "TODO" in s.upper()
        or "TKTK" in s.upper()
    )


def _get_nested(d, dotted_key):
    """Get a value from a nested dict using a dotted key like 'refs.framework_rules'."""
    parts = dotted_key.split(".")
    current = d
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


# ── validators ────────────────────────────────────────────────────────────────

def validate_spec_frontmatter(spec_text):
    """Validate spec.md YAML frontmatter.

    Checks all required fields from frontmatter.yml:
    - Top-level: artifact, feature_id, slug, status
    - Nested: refs.framework_rules, refs.constitution, refs.stack,
      refs.architecture, refs.conventions, generator.command, generator.model

    Returns list of (field, message) errors.
    """
    errors = []

    fm = extract_yaml_frontmatter(spec_text)

    if not fm:
        errors.append(("__frontmatter", "No YAML frontmatter block found"))
        return errors

    orderspec = fm.get("orderspec", {})
    if not isinstance(orderspec, dict):
        errors.append(("orderspec", "orderspec block is not a mapping"))
        return errors

    for field in SPEC_REQUIRED_METADATA_FIELDS:
        value = orderspec.get(field)
        if looks_like_unresolved_placeholder(value):
            errors.append((field, f"Required metadata field 'orderspec.{field}' is missing, empty, or unresolved"))

    for field in SPEC_REQUIRED_NESTED_FIELDS:
        value = _get_nested(orderspec, field)
        if looks_like_unresolved_placeholder(value):
            errors.append(("orderspec." + field, f"Required field 'orderspec.{field}' is missing, empty, or unresolved"))

    artifact = orderspec.get("artifact")
    if artifact and not looks_like_unresolved_placeholder(artifact) and artifact != "spec":
        errors.append(("artifact", f"orderspec.artifact must be 'spec', got '{artifact}'"))

    feature_id = orderspec.get("feature_id")
    feature_id_value = normalize_frontmatter_scalar(feature_id)
    if (
        feature_id_value is not None
        and not looks_like_unresolved_placeholder(feature_id_value)
        and (not isinstance(feature_id_value, str) or not FEATURE_ID_RE.match(feature_id_value))
    ):
        errors.append((
            "feature_id",
            "orderspec.feature_id must match FEAT-NNN-slug, e.g. FEAT-001-user-auth",
        ))

    status = orderspec.get("status")
    if status and not looks_like_unresolved_placeholder(status) and status not in SPEC_STATUS_VALUES:
        errors.append((
            "status",
            f"orderspec.status must be one of {sorted(SPEC_STATUS_VALUES)}, got '{status}'",
        ))

    return errors


def validate_command_prompt_frontmatter(text):
    """Validate command_prompt YAML frontmatter.

    Required top-level: description, handoffs.
    Required under orderspec: artifact, command, phase.
    Returns list of (field, message) errors.
    """
    errors = []
    fm = extract_yaml_frontmatter(text)
    if not fm:
        errors.append(("__frontmatter", "No YAML frontmatter block found"))
        return errors

    orderspec = fm.get("orderspec", {})
    if not isinstance(orderspec, dict):
        errors.append(("orderspec", "orderspec block is not a mapping"))
        return errors

    for field in ["artifact", "command", "phase"]:
        value = orderspec.get(field)
        if looks_like_unresolved_placeholder(value):
            errors.append(("orderspec." + field, f"Required field 'orderspec.{field}' is missing, empty, or unresolved"))

    artifact = orderspec.get("artifact")
    if artifact and not looks_like_unresolved_placeholder(artifact) and artifact != "command_prompt":
        errors.append(("orderspec.artifact", f"orderspec.artifact must be 'command_prompt', got '{artifact}'"))

    phase = orderspec.get("phase")
    if phase and not looks_like_unresolved_placeholder(phase) and phase not in COMMAND_PROMPT_PHASE_VALUES:
        errors.append(("orderspec.phase", f"orderspec.phase must be one of {sorted(COMMAND_PROMPT_PHASE_VALUES)}, got '{phase}'"))

    for field in ["description"]:
        value = fm.get(field)
        if looks_like_unresolved_placeholder(value):
            errors.append((field, f"Required field '{field}' is missing, empty, or unresolved"))

    handoffs = fm.get("handoffs")
    if isinstance(handoffs, list):
        for i, item in enumerate(handoffs):
            if not isinstance(item, dict):
                errors.append(("handoffs", f"handoffs[{i}] must be a mapping"))
                continue
            for req in COMMAND_PROMPT_HANDOFFS_ITEM_FIELDS:
                if looks_like_unresolved_placeholder(item.get(req)):
                    errors.append(("handoffs", f"handoffs[{i}].{req} is missing, empty, or unresolved"))

    return errors


def validate_gate_report_frontmatter(text):
    """Validate gate_report YAML frontmatter.

    Required under orderspec: artifact, command, model, generated_at,
    verdict, feature_id, feature_directory.
    Returns list of (field, message) errors.
    """
    errors = []
    fm = extract_yaml_frontmatter(text)
    if not fm:
        errors.append(("__frontmatter", "No YAML frontmatter block found"))
        return errors

    orderspec = fm.get("orderspec", {})
    if not isinstance(orderspec, dict):
        errors.append(("orderspec", "orderspec block is not a mapping"))
        return errors

    for field in GATE_REPORT_REQUIRED_FIELDS:
        value = orderspec.get(field)
        if looks_like_unresolved_placeholder(value):
            errors.append(("orderspec." + field, f"Required field 'orderspec.{field}' is missing, empty, or unresolved"))

    artifact = orderspec.get("artifact")
    if artifact and not looks_like_unresolved_placeholder(artifact) and artifact != "gate_report":
        errors.append(("orderspec.artifact", f"orderspec.artifact must be 'gate_report', got '{artifact}'"))

    verdict = orderspec.get("verdict")
    if verdict and not looks_like_unresolved_placeholder(verdict) and verdict not in GATE_REPORT_VERDICT_VALUES:
        errors.append(("orderspec.verdict", f"orderspec.verdict must be one of {sorted(GATE_REPORT_VERDICT_VALUES)}, got '{verdict}'"))

    if orderspec.get("command") == "order.code-check":
        assurance = orderspec.get("assurance")
        if looks_like_unresolved_placeholder(assurance):
            errors.append(("orderspec.assurance", "Required code report field 'orderspec.assurance' is missing, empty, or unresolved"))
        elif assurance not in CODE_REPORT_ASSURANCE_VALUES:
            errors.append(("orderspec.assurance", f"orderspec.assurance must be one of {sorted(CODE_REPORT_ASSURANCE_VALUES)}, got '{assurance}'"))

        terminal_precondition = orderspec.get("terminal_precondition")
        if not isinstance(terminal_precondition, bool):
            errors.append(("orderspec.terminal_precondition", "Required code report field 'orderspec.terminal_precondition' must be true or false"))

    return errors


def validate_project_contract_frontmatter(text, expected_kind=None):
    """Validate project_contract YAML frontmatter.

    Required under orderspec: artifact, kind.
    Returns list of (field, message) errors.
    """
    errors = []
    fm = extract_yaml_frontmatter(text)
    if not fm:
        errors.append(("__frontmatter", "No YAML frontmatter block found"))
        return errors

    orderspec = fm.get("orderspec", {})
    if not isinstance(orderspec, dict):
        errors.append(("orderspec", "orderspec block is not a mapping"))
        return errors

    for field in PROJECT_CONTRACT_REQUIRED_FIELDS:
        value = orderspec.get(field)
        if looks_like_unresolved_placeholder(value):
            errors.append(("orderspec." + field, f"Required field 'orderspec.{field}' is missing, empty, or unresolved"))

    artifact = orderspec.get("artifact")
    if artifact and not looks_like_unresolved_placeholder(artifact) and artifact != "project_contract":
        errors.append(("orderspec.artifact", f"orderspec.artifact must be 'project_contract', got '{artifact}'"))

    kind = orderspec.get("kind")
    if kind and not looks_like_unresolved_placeholder(kind) and kind not in PROJECT_CONTRACT_KIND_VALUES:
        errors.append(("orderspec.kind", f"orderspec.kind must be one of {sorted(PROJECT_CONTRACT_KIND_VALUES)}, got '{kind}'"))

    if expected_kind and kind and kind != expected_kind:
        errors.append(("orderspec.kind", f"orderspec.kind must be '{expected_kind}', got '{kind}'"))

    return errors


def validate_framework_rules_frontmatter(text):
    """Validate framework_rules YAML frontmatter.

    Required under orderspec: artifact, authority, customization.
    Returns list of (field, message) errors.
    """
    errors = []
    fm = extract_yaml_frontmatter(text)
    if not fm:
        errors.append(("__frontmatter", "No YAML frontmatter block found"))
        return errors

    orderspec = fm.get("orderspec", {})
    if not isinstance(orderspec, dict):
        errors.append(("orderspec", "orderspec block is not a mapping"))
        return errors

    for field in FRAMEWORK_RULES_REQUIRED_FIELDS:
        value = orderspec.get(field)
        if looks_like_unresolved_placeholder(value):
            errors.append(("orderspec." + field, f"Required field 'orderspec.{field}' is missing, empty, or unresolved"))

    artifact = orderspec.get("artifact")
    if artifact and not looks_like_unresolved_placeholder(artifact) and artifact != "framework_rules":
        errors.append(("orderspec.artifact", f"orderspec.artifact must be 'framework_rules', got '{artifact}'"))

    authority = orderspec.get("authority")
    if authority and not looks_like_unresolved_placeholder(authority) and authority != "framework":
        errors.append(("orderspec.authority", f"orderspec.authority must be 'framework', got '{authority}'"))

    customization = orderspec.get("customization")
    if customization and not looks_like_unresolved_placeholder(customization) and customization != "forbidden":
        errors.append(("orderspec.customization", f"orderspec.customization must be 'forbidden', got '{customization}'"))

    return errors


def validate_protocol_frontmatter(text):
    """Validate protocol YAML frontmatter.

    Required under orderspec: artifact.
    Returns list of (field, message) errors.
    """
    errors = []
    fm = extract_yaml_frontmatter(text)
    if not fm:
        errors.append(("__frontmatter", "No YAML frontmatter block found"))
        return errors

    orderspec = fm.get("orderspec", {})
    if not isinstance(orderspec, dict):
        errors.append(("orderspec", "orderspec block is not a mapping"))
        return errors

    for field in PROTOCOL_REQUIRED_FIELDS:
        value = orderspec.get(field)
        if looks_like_unresolved_placeholder(value):
            errors.append(("orderspec." + field, f"Required field 'orderspec.{field}' is missing, empty, or unresolved"))

    artifact = orderspec.get("artifact")
    if artifact and not looks_like_unresolved_placeholder(artifact) and artifact != "protocol":
        errors.append(("orderspec.artifact", f"orderspec.artifact must be 'protocol', got '{artifact}'"))

    return errors


# ── dispatcher ────────────────────────────────────────────────────────────────

VALIDATORS = {
    "spec": validate_spec_frontmatter,
    "command_prompt": validate_command_prompt_frontmatter,
    "gate_report": validate_gate_report_frontmatter,
    "project_contract": validate_project_contract_frontmatter,
    "framework_rules": validate_framework_rules_frontmatter,
    "protocol": validate_protocol_frontmatter,
}


def validate_frontmatter(artifact_type, text):
    """Validate frontmatter for the given artifact type.

    Returns list of (field, message) errors.
    Raises ValueError for unknown artifact type.
    """
    validator = VALIDATORS.get(artifact_type)
    if not validator:
        raise ValueError(f"unknown artifact type: {artifact_type}. Valid: {sorted(VALIDATORS.keys())}")
    return validator(text)


# ── CLI entry point ───────────────────────────────────────────────────────────

def _die(msg, rc=2):
    print(msg, file=sys.stderr)
    sys.exit(rc)


def cmd_validate_frontmatter(args, remaining):
    """Standalone frontmatter validation for any artifact type."""
    artifact_type = getattr(args, "artifact_type", None) or (remaining[0] if remaining else None)
    file_path = getattr(args, "file", None) or (remaining[1] if len(remaining) > 1 else None)

    if not artifact_type or not file_path:
        _die("usage: frontmatter.py validate-frontmatter <artifact-type> <file>", 64)

    if not Path(file_path).is_file():
        _die(f"file not found: {file_path}", 2)

    text = Path(file_path).read_text(encoding="utf-8")

    try:
        errors = validate_frontmatter(artifact_type, text)
    except ValueError as e:
        _die(str(e), 64)

    if getattr(args, "json", False):
        output = {
            "ok": len(errors) == 0,
            "artifact_type": artifact_type,
            "file": file_path,
            "errors": [{"field": f, "message": m} for f, m in errors],
        }
        print(json.dumps(output, indent=2))
    else:
        for field, message in errors:
            print(f"{field}: {message}")

    sys.exit(0 if not errors else 1)
