#!/usr/bin/env python3
"""Create, validate, and atomically update operator-owned automation.json."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from automation_policy import validate_config


CONFIG_PATH = Path(".orderspec/config/automation.json")
TEMPLATE_PATH = Path(".orderspec/framework/templates/automation-config.json")


def emit(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def project_root(value: str) -> Path:
    root = Path(value).resolve()
    if not (root / ".orderspec").is_dir():
        raise ValueError("project root must contain .orderspec")
    return root


def read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def validated(value: Any, label: str) -> dict[str, Any]:
    config, errors = validate_config(value)
    if config is None:
        raise ValueError(f"invalid {label}: {'; '.join(errors)}")
    return config


def digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def load_current(root: Path) -> tuple[Path, dict[str, Any]]:
    path = root / CONFIG_PATH
    if not path.is_file():
        raise ValueError(f"automation config not found: {path}; run init")
    return path, validated(read_object(path), str(path))


def cmd_init(args: argparse.Namespace) -> int:
    root = project_root(args.project_root)
    path = root / CONFIG_PATH
    if path.exists():
        config = validated(read_object(path), str(path))
        emit({"ok": True, "action": "unchanged", "config": str(path), "enabled": config["enabled"], "sha256": digest(config)})
        return 0
    template_path = root / TEMPLATE_PATH
    template = validated(read_object(template_path), str(template_path))
    if template["enabled"] is not False:
        raise ValueError("automation template must default to enabled=false")
    atomic_write(path, template)
    emit({"ok": True, "action": "created", "config": str(path), "enabled": False, "sha256": digest(template)})
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    root = project_root(args.project_root)
    path, config = load_current(root)
    emit({"ok": True, "config": str(path), "enabled": config["enabled"], "rule_count": len(config["rules"]), "sha256": digest(config)})
    return 0


def cmd_set_enabled(args: argparse.Namespace) -> int:
    root = project_root(args.project_root)
    path, config = load_current(root)
    expected = args.expected_current_sha256
    current_digest = digest(config)
    if expected and expected != current_digest:
        raise ValueError("automation config changed since inspection")
    enabled = args.value == "true"
    action = "unchanged" if config["enabled"] is enabled else "updated"
    config["enabled"] = enabled
    validated(config, "updated automation config")
    if action == "updated":
        atomic_write(path, config)
    emit({"ok": True, "action": action, "config": str(path), "enabled": enabled, "sha256": digest(config)})
    return 0


def cmd_write(args: argparse.Namespace) -> int:
    root = project_root(args.project_root)
    path, current = load_current(root)
    expected = args.expected_current_sha256
    current_digest = digest(current)
    if expected and expected != current_digest:
        raise ValueError("automation config changed since inspection")
    raw = sys.stdin.read() if args.input_file == "-" else Path(args.input_file).read_text(encoding="utf-8")
    try:
        candidate = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid candidate JSON: {exc}") from exc
    candidate = validated(candidate, "automation config candidate")
    action = "unchanged" if candidate == current else "updated"
    if action == "updated":
        atomic_write(path, candidate)
    emit({"ok": True, "action": action, "config": str(path), "enabled": candidate["enabled"], "rule_count": len(candidate["rules"]), "sha256": digest(candidate)})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage .orderspec/config/automation.json")
    parser.add_argument("-C", "--project-root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.set_defaults(func=cmd_init)
    validate = sub.add_parser("validate")
    validate.set_defaults(func=cmd_validate)
    enabled = sub.add_parser("set-enabled")
    enabled.add_argument("--value", choices=["true", "false"], required=True)
    enabled.add_argument("--expected-current-sha256")
    enabled.set_defaults(func=cmd_set_enabled)
    write = sub.add_parser("write")
    write.add_argument("--input-file", required=True, help="complete candidate JSON file or - for stdin")
    write.add_argument("--expected-current-sha256")
    write.set_defaults(func=cmd_write)
    args = parser.parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
