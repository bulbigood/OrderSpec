#!/usr/bin/env python3
"""command_context.py — deterministic OrderSpec command context resolver.

This script resolves the preloaded context for an OrderSpec command from the
framework-owned command context manifest.

Strict format:
- manifest version must be 2
- command context entries must be objects
- string entries are not supported
- legacy "optional" is not supported
- required/read_if_exists are the only context list keys
- entries may be concrete file entries, { "ref": "resource.id" }, or { "group": "group.id" }
- resources define concrete files once
- groups define reusable ordered lists of refs/groups
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path
from typing import Any


MANIFEST_REL = ".orderspec/framework/command-context.json"

ALLOWED_USAGE = {
    "apply",
    "constrain",
    "parse",
    "inspect",
    "reference",
}

ALLOWED_AUTHORITY = {
    "framework",
    "project",
    "operator_config",
    "runtime",
    "feature",
    "external",
}

ALLOWED_FEATURE_CONTEXT_MODES = {
    "none",
    "if_active",
    "required",
}

ALLOWED_FEATURE_ARTIFACTS = {
    "spec",
    "plan",
    "tasks",
}

FEATURE_ARTIFACT_FILES = {
    "spec": "spec.md",
    "plan": "plan.md",
    "tasks": "tasks.md",
}


def posix(path: Path | str) -> str:
    return str(path).replace(os.sep, "/")


def json_print(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def manifest_path(root: Path) -> Path:
    return root / MANIFEST_REL


def is_safe_relative_path(value: str) -> bool:
    if not isinstance(value, str) or not value:
        return False

    p = Path(value)

    if p.is_absolute():
        return False

    if value.startswith("~"):
        return False

    parts = p.parts

    if any(part == ".." for part in parts):
        return False

    if any(part == "" for part in parts):
        return False

    return True


def has_glob(value: str) -> bool:
    return any(ch in value for ch in ["*", "?", "["])


def load_manifest(root: Path) -> tuple[dict[str, Any] | None, list[str]]:
    path = manifest_path(root)

    if not path.exists():
        return None, [f"manifest not found: {MANIFEST_REL}"]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"invalid manifest JSON: {exc}"]

    if not isinstance(data, dict):
        return None, ["manifest must be a JSON object"]

    return data, []


def validate_concrete_entry(
    raw: Any,
    source: str,
    required: bool,
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []

    if isinstance(raw, str):
        return None, [f"{source}: entry must be an object; string entries are not supported"]

    if not isinstance(raw, dict):
        return None, [f"{source}: entry must be an object"]

    if "ref" in raw or "group" in raw:
        return None, [f"{source}: ref/group entries must be expanded before concrete validation"]

    path_value = raw.get("path")
    if not isinstance(path_value, str) or not path_value:
        errors.append(f"{source}: entry.path must be a non-empty string")
    elif not is_safe_relative_path(path_value):
        errors.append(f"{source}: entry.path must be a safe relative path")

    kind = raw.get("kind")
    if not isinstance(kind, str) or not kind:
        errors.append(f"{source}: entry.kind must be a non-empty string")

    usage = raw.get("usage")
    if usage not in ALLOWED_USAGE:
        errors.append(f"{source}: entry.usage must be one of {sorted(ALLOWED_USAGE)}")

    authority = raw.get("authority")
    if authority not in ALLOWED_AUTHORITY:
        errors.append(f"{source}: entry.authority must be one of {sorted(ALLOWED_AUTHORITY)}")

    reason = raw.get("reason")
    if not isinstance(reason, str) or not reason:
        errors.append(f"{source}: entry.reason must be a non-empty string")

    expand = raw.get("expand", True)
    if not isinstance(expand, bool):
        errors.append(f"{source}: entry.expand must be a boolean")

    allowed_keys = {
        "path",
        "kind",
        "usage",
        "authority",
        "reason",
        "expand",
    }

    extra = sorted(set(raw.keys()) - allowed_keys)
    if extra:
        errors.append(f"{source}: unsupported entry keys: {extra}")

    if errors:
        return None, errors

    return {
        "path": path_value,
        "kind": kind,
        "usage": usage,
        "authority": authority,
        "required": required,
        "reason": reason,
        "source": source,
        "expand": expand,
    }, []


def validate_resource_entry(
    raw: Any,
    source: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    entry, errors = validate_concrete_entry(raw, source, required=False)

    if entry is None:
        return None, errors

    return {
        "path": entry["path"],
        "kind": entry["kind"],
        "usage": entry["usage"],
        "authority": entry["authority"],
        "reason": entry["reason"],
        "expand": entry["expand"],
    }, []


def validate_feature_context(raw: Any, source: str) -> list[str]:
    errors: list[str] = []

    if raw is None:
        return errors

    if not isinstance(raw, dict):
        return [f"{source}.feature_context must be an object"]

    allowed_keys = {"mode", "artifacts"}
    extra = sorted(set(raw.keys()) - allowed_keys)
    if extra:
        errors.append(f"{source}.feature_context has unsupported keys: {extra}")

    mode = raw.get("mode")
    if mode not in ALLOWED_FEATURE_CONTEXT_MODES:
        errors.append(
            f"{source}.feature_context.mode must be one of {sorted(ALLOWED_FEATURE_CONTEXT_MODES)}"
        )

    artifacts = raw.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append(f"{source}.feature_context.artifacts must be a list")
    else:
        seen: set[str] = set()
        for i, item in enumerate(artifacts):
            if item not in ALLOWED_FEATURE_ARTIFACTS:
                errors.append(
                    f"{source}.feature_context.artifacts[{i}] must be one of {sorted(ALLOWED_FEATURE_ARTIFACTS)}"
                )
            elif item in seen:
                errors.append(
                    f"{source}.feature_context.artifacts[{i}] duplicates {item}"
                )
            seen.add(item)

    return errors


def expand_manifest_entry(
    raw: Any,
    source: str,
    required: bool,
    resources: dict[str, dict[str, Any]],
    groups: dict[str, list[Any]],
    group_stack: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []

    if isinstance(raw, str):
        return [], [f"{source}: entry must be an object; string entries are not supported"]

    if not isinstance(raw, dict):
        return [], [f"{source}: entry must be an object"]

    has_ref = "ref" in raw
    has_group = "group" in raw
    has_path = "path" in raw

    selector_count = sum([has_ref, has_group, has_path])

    if selector_count == 0:
        entry, entry_errors = validate_concrete_entry(raw, source, required)
        return ([entry] if entry else []), entry_errors

    if selector_count > 1:
        return [], [f"{source}: entry must use exactly one of path, ref, or group"]

    if has_ref:
        extra = sorted(set(raw.keys()) - {"ref"})
        if extra:
            return [], [f"{source}: ref entry has unsupported keys: {extra}"]

        ref = raw.get("ref")
        if not isinstance(ref, str) or not ref:
            return [], [f"{source}: entry.ref must be a non-empty string"]

        if ref not in resources:
            return [], [f"{source}: unknown resource ref: {ref}"]

        resource = resources[ref]
        return [
            {
                "path": resource["path"],
                "kind": resource["kind"],
                "usage": resource["usage"],
                "authority": resource["authority"],
                "required": required,
                "reason": resource["reason"],
                "source": f"{source} -> ref:{ref}",
                "expand": resource.get("expand", True),
            }
        ], []

    if has_group:
        extra = sorted(set(raw.keys()) - {"group"})
        if extra:
            return [], [f"{source}: group entry has unsupported keys: {extra}"]

        group_name = raw.get("group")
        if not isinstance(group_name, str) or not group_name:
            return [], [f"{source}: entry.group must be a non-empty string"]

        if group_name not in groups:
            return [], [f"{source}: unknown group: {group_name}"]

        if group_name in group_stack:
            cycle = " -> ".join(group_stack + [group_name])
            return [], [f"{source}: group cycle detected: {cycle}"]

        result: list[dict[str, Any]] = []
        values = groups[group_name]

        if not isinstance(values, list):
            return [], [f"groups.{group_name} must be a list"]

        for index, item in enumerate(values):
            expanded, item_errors = expand_manifest_entry(
                item,
                f"{source} -> group:{group_name}[{index}]",
                required,
                resources,
                groups,
                group_stack + [group_name],
            )
            errors.extend(item_errors)
            result.extend(expanded)

        return result, errors

    entry, entry_errors = validate_concrete_entry(raw, source, required)
    return ([entry] if entry else []), entry_errors


def expand_context_list(
    values: Any,
    source: str,
    required: bool,
    resources: dict[str, dict[str, Any]],
    groups: dict[str, list[Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []

    if values is None:
        values = []

    if not isinstance(values, list):
        return [], [f"{source} must be a list"]

    result: list[dict[str, Any]] = []

    for index, item in enumerate(values):
        expanded, item_errors = expand_manifest_entry(
            item,
            f"{source}[{index}]",
            required,
            resources,
            groups,
            [],
        )
        errors.extend(item_errors)
        result.extend(expanded)

    return result, errors


def validate_context_group(
    raw: Any,
    source: str,
    resources: dict[str, dict[str, Any]],
    groups: dict[str, list[Any]],
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []

    if raw is None:
        raw = {}

    if not isinstance(raw, dict):
        return None, [f"{source} must be an object"]

    allowed_keys = {
        "required",
        "read_if_exists",
        "feature_context",
    }

    if "optional" in raw:
        errors.append(f"{source}.optional is not supported; use read_if_exists")

    extra = sorted(set(raw.keys()) - allowed_keys - {"optional"})
    if extra:
        errors.append(f"{source} has unsupported keys: {extra}")

    normalized: dict[str, Any] = {}

    required_entries, required_errors = expand_context_list(
        raw.get("required", []),
        f"{source}.required",
        True,
        resources,
        groups,
    )
    errors.extend(required_errors)
    normalized["required"] = required_entries

    if "read_if_exists" in raw:
        read_entries, read_errors = expand_context_list(
            raw.get("read_if_exists", []),
            f"{source}.read_if_exists",
            False,
            resources,
            groups,
        )
        errors.extend(read_errors)
        normalized["read_if_exists"] = read_entries
    else:
        normalized["read_if_exists"] = []

    if "feature_context" in raw:
        errors.extend(validate_feature_context(raw.get("feature_context"), source))
        normalized["feature_context"] = raw.get("feature_context")

    return normalized, errors


def validate_manifest_shape(manifest: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []

    allowed_keys = {
        "version",
        "resources",
        "groups",
        "defaults",
        "commands",
    }

    extra = sorted(set(manifest.keys()) - allowed_keys)
    if extra:
        errors.append(f"manifest has unsupported keys: {extra}")

    if manifest.get("version") != 2:
        errors.append("version must be 2")

    resources_raw = manifest.get("resources", {})
    if resources_raw is None:
        resources_raw = {}

    if not isinstance(resources_raw, dict):
        errors.append("resources must be an object")
        resources_raw = {}

    resources: dict[str, dict[str, Any]] = {}

    for resource_name, resource_raw in resources_raw.items():
        if not isinstance(resource_name, str) or not resource_name:
            errors.append("resource names must be non-empty strings")
            continue

        resource, resource_errors = validate_resource_entry(
            resource_raw,
            f"resources.{resource_name}",
        )
        errors.extend(resource_errors)

        if resource is not None:
            resources[resource_name] = resource

    groups_raw = manifest.get("groups", {})
    if groups_raw is None:
        groups_raw = {}

    if not isinstance(groups_raw, dict):
        errors.append("groups must be an object")
        groups_raw = {}

    groups: dict[str, list[Any]] = {}

    for group_name, group_raw in groups_raw.items():
        if not isinstance(group_name, str) or not group_name:
            errors.append("group names must be non-empty strings")
            continue

        if not isinstance(group_raw, list):
            errors.append(f"groups.{group_name} must be a list")
            continue

        groups[group_name] = group_raw

    commands_raw = manifest.get("commands")
    if not isinstance(commands_raw, dict):
        errors.append("commands must be an object")
        commands_raw = {}

    if errors:
        return None, errors

    # Validate every group, including unused groups, for unknown refs/groups and cycles.
    for group_name, group_values in groups.items():
        for index, item in enumerate(group_values):
            _, group_errors = expand_manifest_entry(
                item,
                f"groups.{group_name}[{index}]",
                required=False,
                resources=resources,
                groups=groups,
                group_stack=[group_name],
            )
            errors.extend(group_errors)

    defaults, default_errors = validate_context_group(
        manifest.get("defaults", {}),
        "defaults",
        resources,
        groups,
    )
    errors.extend(default_errors)

    commands: dict[str, Any] = {}

    for command_name, group_raw in commands_raw.items():
        if not isinstance(command_name, str) or not command_name:
            errors.append("command names must be non-empty strings")
            continue

        group, group_errors = validate_context_group(
            group_raw,
            f"commands.{command_name}",
            resources,
            groups,
        )
        errors.extend(group_errors)

        if group is not None:
            commands[command_name] = group

    if errors:
        return None, errors

    return {
        "version": 2,
        "resources": resources,
        "groups": groups,
        "defaults": defaults or {},
        "commands": commands,
    }, []


def materialize(
    entry: dict[str, Any],
    item_path: str,
    exists: bool,
    expanded_from: str | None,
) -> dict[str, Any]:
    return {
        "path": item_path,
        "kind": entry["kind"],
        "usage": entry["usage"],
        "authority": entry["authority"],
        "required": entry["required"],
        "reason": entry["reason"],
        "source": entry["source"],
        "exists": exists,
        "expanded_from": expanded_from,
    }


def resolve_active_feature_directory(root: Path) -> Path | None:
    """Resolve active feature directory without mutating runtime state.

    Command context resolution runs before command-specific path setup. It uses
    the same two read-only sources as `setup.py paths`: explicit environment
    override first, then active-feature state.
    """
    raw_value = os.environ.get("SPECIFY_FEATURE_DIRECTORY")

    if not raw_value:
        state_path = root / ".orderspec" / "state" / "active-feature.json"
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}
        if isinstance(state, dict):
            raw_value = state.get("feature_directory")

    if not isinstance(raw_value, str) or not raw_value:
        return None

    candidate = Path(raw_value)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()

    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(
            "active feature directory must be inside repository root"
        ) from exc

    return candidate


def resolve_feature_context(
    root: Path,
    feature_context: dict[str, Any] | None,
    command: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Materialize active feature artifacts declared by command context.

    `required` means artifacts are required when an active feature exists. A
    command with no active feature still reaches its normal path-resolution
    step, which owns the user-facing `no active feature` stop message.
    """
    if not feature_context or feature_context.get("mode") == "none":
        return [], [], {"mode": "none", "artifacts": [], "active": False}

    mode = feature_context["mode"]
    artifacts = feature_context["artifacts"]
    feature_dir = resolve_active_feature_directory(root)
    summary: dict[str, Any] = {
        "mode": mode,
        "artifacts": artifacts,
        "active": feature_dir is not None,
    }

    if feature_dir is None:
        return [], [], summary

    try:
        feature_rel = feature_dir.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("active feature directory is outside repository root") from exc

    summary["feature_directory"] = posix(feature_rel)
    required = mode == "required"
    resolved: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    for index, artifact in enumerate(artifacts):
        filename = FEATURE_ARTIFACT_FILES[artifact]
        path_value = posix(feature_rel / filename)
        entry = {
            "path": path_value,
            "kind": "feature_artifact",
            "usage": "inspect",
            "authority": "feature",
            "required": required,
            "reason": f"{command} active feature {artifact}.md",
            "source": f"commands.{command}.feature_context.artifacts[{index}]",
            "exists": (root / path_value).is_file(),
            "expanded_from": None,
        }
        if entry["exists"]:
            resolved.append(entry)
        elif required:
            missing.append(entry)

    return resolved, missing, summary


def expand_entry(
    root: Path,
    entry: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    path_value = entry["path"]
    expand = entry.get("expand", True)

    if not expand:
        exists = (root / path_value).is_file()
        item = materialize(
            entry,
            path_value,
            exists=exists,
            expanded_from=None,
        )

        if exists:
            return [item], []

        return [], [item]

    if has_glob(path_value):
        matches = sorted(glob.glob(str(root / path_value), recursive=True))
        resolved: list[dict[str, Any]] = []

        for match in matches:
            p = Path(match)

            if not p.is_file():
                continue

            try:
                rel = p.relative_to(root)
            except ValueError:
                continue

            resolved.append(
                materialize(
                    entry,
                    posix(rel),
                    exists=True,
                    expanded_from=path_value,
                )
            )

        if resolved:
            return resolved, []

        missing = materialize(
            entry,
            path_value,
            exists=False,
            expanded_from=None,
        )

        return [], [missing]

    exists = (root / path_value).is_file()
    item = materialize(
        entry,
        path_value,
        exists=exists,
        expanded_from=None,
    )

    if exists:
        return [item], []

    return [], [item]


def resolve_with_normalized_manifest(
    root: Path,
    normalized_manifest: dict[str, Any],
    command: str,
) -> dict[str, Any]:
    commands = normalized_manifest.get("commands", {})

    result: dict[str, Any] = {
        "ok": True,
        "command": command,
        "manifest": MANIFEST_REL,
        "to_read": [],
        "missing_required": [],
        "skipped_if_missing": [],
        "validation_errors": [],
    }

    if command not in commands:
        result["ok"] = False
        result["validation_errors"].append(f"unknown command: {command}")
        return result

    all_entries: list[dict[str, Any]] = []

    defaults = normalized_manifest.get("defaults", {})
    command_group = commands.get(command, {})

    all_entries.extend(defaults.get("required", []))
    all_entries.extend(defaults.get("read_if_exists", []))
    all_entries.extend(command_group.get("required", []))
    all_entries.extend(command_group.get("read_if_exists", []))

    feature_context = command_group.get("feature_context")
    if feature_context is None:
        feature_context = defaults.get("feature_context")

    try:
        feature_entries, feature_missing, feature_summary = resolve_feature_context(
            root,
            feature_context,
            command,
        )
    except ValueError as exc:
        result["ok"] = False
        result["validation_errors"].append(str(exc))
        return result

    result["feature_context"] = feature_summary

    seen_to_read: set[str] = set()
    seen_missing: set[str] = set()
    seen_skipped: set[str] = set()

    for entry in all_entries:
        resolved, absent = expand_entry(root, entry)

        for item in resolved:
            path_value = item["path"]
            if path_value in seen_to_read:
                continue
            seen_to_read.add(path_value)
            result["to_read"].append(item)

        for item in absent:
            path_value = item["path"]

            if item["required"]:
                if path_value in seen_missing:
                    continue
                seen_missing.add(path_value)
                result["missing_required"].append(item)
            else:
                if path_value in seen_skipped:
                    continue
                seen_skipped.add(path_value)
                result["skipped_if_missing"].append(item)

    for item in feature_entries:
        path_value = item["path"]
        if path_value in seen_to_read:
            continue
        seen_to_read.add(path_value)
        result["to_read"].append(item)

    for item in feature_missing:
        path_value = item["path"]
        if path_value in seen_missing:
            continue
        seen_missing.add(path_value)
        result["missing_required"].append(item)

    if result["missing_required"]:
        result["ok"] = False

    return result


def resolve_command(root: Path, command: str) -> dict[str, Any]:
    manifest, load_errors = load_manifest(root)

    if load_errors:
        return {
            "ok": False,
            "command": command,
            "manifest": MANIFEST_REL,
            "to_read": [],
            "missing_required": [],
            "skipped_if_missing": [],
            "validation_errors": load_errors,
        }

    assert manifest is not None

    normalized, validation_errors = validate_manifest_shape(manifest)

    if validation_errors:
        return {
            "ok": False,
            "command": command,
            "manifest": MANIFEST_REL,
            "to_read": [],
            "missing_required": [],
            "skipped_if_missing": [],
            "validation_errors": validation_errors,
        }

    assert normalized is not None

    return resolve_with_normalized_manifest(root, normalized, command)


def list_commands(root: Path) -> dict[str, Any]:
    manifest, load_errors = load_manifest(root)

    if load_errors:
        return {
            "ok": False,
            "manifest": MANIFEST_REL,
            "commands": [],
            "validation_errors": load_errors,
        }

    assert manifest is not None

    normalized, validation_errors = validate_manifest_shape(manifest)

    if validation_errors:
        return {
            "ok": False,
            "manifest": MANIFEST_REL,
            "commands": [],
            "validation_errors": validation_errors,
        }

    assert normalized is not None

    return {
        "ok": True,
        "manifest": MANIFEST_REL,
        "commands": sorted(normalized.get("commands", {}).keys()),
        "validation_errors": [],
    }


def validate_all(root: Path) -> dict[str, Any]:
    manifest, load_errors = load_manifest(root)

    if load_errors:
        return {
            "ok": False,
            "manifest": MANIFEST_REL,
            "validation_errors": load_errors,
        }

    assert manifest is not None

    normalized, validation_errors = validate_manifest_shape(manifest)

    if validation_errors:
        return {
            "ok": False,
            "manifest": MANIFEST_REL,
            "validation_errors": validation_errors,
        }

    assert normalized is not None

    errors: list[str] = []

    for command in sorted(normalized.get("commands", {}).keys()):
        resolved = resolve_with_normalized_manifest(root, normalized, command)

        if not resolved.get("ok"):
            errors.append(f"{command}: invalid context")

    return {
        "ok": not errors,
        "manifest": MANIFEST_REL,
        "validation_errors": errors,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve OrderSpec command context."
    )

    parser.add_argument(
        "-C",
        "--directory",
        default=".",
        help="repository root directory",
    )

    sub = parser.add_subparsers(
        dest="action",
        required=True,
    )

    p_resolve = sub.add_parser("resolve")
    p_resolve.add_argument("command")
    p_resolve.add_argument("--json", action="store_true")

    p_list = sub.add_parser("list")
    p_list.add_argument("--json", action="store_true")

    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--json", action="store_true")

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    root = Path(args.directory).resolve()

    if args.action == "resolve":
        data = resolve_command(root, args.command)
    elif args.action == "list":
        data = list_commands(root)
    elif args.action == "validate":
        data = validate_all(root)
    else:
        parser.error(f"unknown action: {args.action}")
        return 2

    json_print(data)

    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
