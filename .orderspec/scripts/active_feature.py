#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any


from common import SPECS_ROOT

STATE_PATH = Path(".orderspec/state/active-feature.json")
DEFAULT_SPECS_ROOT = SPECS_ROOT

VALID_STATUSES = {
    "unknown",
    "specified",
    "planned",
    "tasks",
    "implementing",
    "implemented",
    "verified",
    "done",
    "blocked",
}

FEATURE_ID_RE = re.compile(r"^FEAT-[0-9]{3}-[a-z0-9]+(?:-[a-z0-9]+)*$")


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def posix(path: Path) -> str:
    return path.as_posix()


def json_out(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def error(code: str, message: str, extra: dict[str, Any] | None = None) -> int:
    payload: dict[str, Any] = {
        "ok": False,
        "error": code,
        "message": message,
    }
    if extra:
        payload.update(extra)
    json_out(payload)
    return 1


def state_file(root: Path) -> Path:
    return root / STATE_PATH


def ensure_state_dir(root: Path) -> None:
    state_file(root).parent.mkdir(parents=True, exist_ok=True)


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_rel(value: str) -> bool:
    p = Path(value)
    if p.is_absolute():
        return False
    return ".." not in p.parts


def read_feature_id_from_spec(spec_file: Path) -> str | None:
    if not spec_file.exists():
        return None

    text = spec_file.read_text(encoding="utf-8", errors="replace")

    # Minimal YAML-frontmatter friendly extraction.
    match = re.search(r"(?m)^\s*feature_id\s*:\s*[\"']?([^\"'\s]+)[\"']?\s*$", text)
    if match:
        return match.group(1).strip()

    match = re.search(r"(?m)^\s*feature_id\s*:\s*(.+?)\s*$", text)
    if match:
        return match.group(1).strip().strip("\"'")

    return None


def infer_feature_id(root: Path, feature_dir: Path) -> str:
    spec_id = read_feature_id_from_spec(root / feature_dir / "spec.md")
    if spec_id:
        return spec_id
    return feature_dir.name


def infer_files(root: Path, feature_dir: Path) -> dict[str, str | None]:
    spec = feature_dir / "spec.md"
    plan = feature_dir / "plan.md"
    tasks = feature_dir / "tasks.md"

    return {
        "spec_file": posix(spec) if (root / spec).exists() else None,
        "plan_file": posix(plan) if (root / plan).exists() else None,
        "tasks_file": posix(tasks) if (root / tasks).exists() else None,
    }


def infer_status(root: Path, feature_dir: Path) -> str:
    if (root / feature_dir / "tasks.md").exists():
        return "tasks"
    if (root / feature_dir / "plan.md").exists():
        return "planned"
    if (root / feature_dir / "spec.md").exists():
        return "specified"
    return "unknown"


def inactive_state() -> dict[str, Any]:
    return {
        "version": 1,
        "active": False,
        "feature_id": None,
        "feature_directory": None,
        "spec_file": None,
        "plan_file": None,
        "tasks_file": None,
        "status": "unknown",
        "last_command": None,
        "updated_at": now_iso(),
    }


def normalize_state(data: Any) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []

    if not isinstance(data, dict):
        return None, ["state must be a JSON object"]

    version = data.get("version", 1)
    if version != 1:
        errors.append("version must be 1")

    active = bool(data.get("active", False))

    if not active:
        normalized = inactive_state()
        normalized["updated_at"] = data.get("updated_at") or normalized["updated_at"]
        return normalized, errors

    feature_id = data.get("feature_id")
    feature_directory = data.get("feature_directory")

    if not isinstance(feature_id, str) or not feature_id.strip():
        errors.append("active state requires non-empty feature_id")
    elif not FEATURE_ID_RE.match(feature_id):
        errors.append("feature_id must match FEAT-NNN-slug, e.g. FEAT-001-user-auth")

    if not isinstance(feature_directory, str) or not feature_directory.strip():
        errors.append("active state requires non-empty feature_directory")
    elif not safe_rel(feature_directory):
        errors.append("feature_directory must be a safe relative path")

    status = data.get("status") or "unknown"
    if status not in VALID_STATUSES:
        errors.append(f"status must be one of: {', '.join(sorted(VALID_STATUSES))}")

    for key in ["spec_file", "plan_file", "tasks_file"]:
        value = data.get(key)
        if value is not None and (not isinstance(value, str) or not safe_rel(value)):
            errors.append(f"{key} must be null or a safe relative path")

    normalized = {
        "version": 1,
        "active": True,
        "feature_id": feature_id,
        "feature_directory": feature_directory,
        "spec_file": data.get("spec_file"),
        "plan_file": data.get("plan_file"),
        "tasks_file": data.get("tasks_file"),
        "status": status,
        "last_command": data.get("last_command"),
        "updated_at": data.get("updated_at") or now_iso(),
    }

    return normalized, errors


def load_state(root: Path) -> tuple[dict[str, Any], list[str], bool]:
    path = state_file(root)
    if not path.exists():
        return inactive_state(), [], False

    try:
        data = read_json(path)
    except Exception as exc:
        return inactive_state(), [f"invalid JSON: {exc}"], True

    normalized, errors = normalize_state(data)
    if normalized is None:
        return inactive_state(), errors, True

    return normalized, errors, True


def build_state(
    root: Path,
    feature_dir_value: str,
    feature_id: str | None,
    status: str | None,
    last_command: str | None,
    allow_missing: bool,
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []

    if not safe_rel(feature_dir_value):
        return None, ["feature_directory must be a safe relative path"]

    feature_dir = Path(feature_dir_value)
    abs_feature_dir = root / feature_dir

    if not abs_feature_dir.exists() and not allow_missing:
        return None, [f"feature_directory does not exist: {feature_dir_value}"]

    if abs_feature_dir.exists() and not abs_feature_dir.is_dir():
        return None, [f"feature_directory is not a directory: {feature_dir_value}"]

    inferred_files = infer_files(root, feature_dir)
    final_feature_id = feature_id or infer_feature_id(root, feature_dir)
    final_status = status or infer_status(root, feature_dir)

    if final_status not in VALID_STATUSES:
        errors.append(f"status must be one of: {', '.join(sorted(VALID_STATUSES))}")

    state = {
        "version": 1,
        "active": True,
        "feature_id": final_feature_id,
        "feature_directory": posix(feature_dir),
        "spec_file": inferred_files["spec_file"],
        "plan_file": inferred_files["plan_file"],
        "tasks_file": inferred_files["tasks_file"],
        "status": final_status,
        "last_command": last_command,
        "updated_at": now_iso(),
    }

    normalized, validation_errors = normalize_state(state)
    errors.extend(validation_errors)

    return normalized, errors


def discover_features(root: Path, specs_root: Path) -> list[dict[str, Any]]:
    abs_specs_root = root / specs_root
    features: list[dict[str, Any]] = []

    if not abs_specs_root.exists():
        return features

    for child in sorted(abs_specs_root.iterdir()):
        if not child.is_dir():
            continue

        rel_dir = child.relative_to(root)
        spec = child / "spec.md"

        # Treat directories with spec.md as real OrderSpec features.
        if not spec.exists():
            continue

        feature_id = read_feature_id_from_spec(spec) or child.name
        rel_feature_dir = Path(posix(rel_dir))

        files = infer_files(root, rel_feature_dir)
        features.append(
            {
                "feature_id": feature_id,
                "feature_directory": posix(rel_feature_dir),
                "spec_file": files["spec_file"],
                "plan_file": files["plan_file"],
                "tasks_file": files["tasks_file"],
                "status": infer_status(root, rel_feature_dir),
            }
        )

    return features


def find_feature(root: Path, specs_root: Path, ref: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    # Direct path match.
    if safe_rel(ref):
        p = root / ref
        if p.exists() and p.is_dir():
            rel_dir = p.relative_to(root)
            state, errors = build_state(
                root=root,
                feature_dir_value=posix(rel_dir),
                feature_id=None,
                status=None,
                last_command=None,
                allow_missing=False,
            )
            if errors or state is None:
                return None, []
            return state, [state]

    features = discover_features(root, specs_root)

    matches = []
    for feature in features:
        fid = feature["feature_id"]
        fdir = feature["feature_directory"]
        dirname = Path(fdir).name

        if ref in {fid, fdir, dirname}:
            matches.append(feature)
            continue

        # Friendly partial ID match: "003" matches "003-user-auth".
        if dirname.startswith(ref + "-"):
            matches.append(feature)

    if len(matches) == 1:
        match = matches[0]
        state, errors = build_state(
            root=root,
            feature_dir_value=match["feature_directory"],
            feature_id=match["feature_id"],
            status=match["status"],
            last_command=None,
            allow_missing=False,
        )
        if errors or state is None:
            return None, matches
        return state, matches

    return None, matches


def cmd_get(args: argparse.Namespace) -> int:
    root = Path(args.cwd).resolve()
    state, errors, exists = load_state(root)

    payload = {
        "ok": not errors,
        "state_file": posix(STATE_PATH),
        "exists": exists,
        "active": state.get("active", False),
        "state": state,
        "validation_errors": errors,
    }

    json_out(payload)
    return 0 if not errors else 1


def cmd_validate(args: argparse.Namespace) -> int:
    root = Path(args.cwd).resolve()
    state, errors, exists = load_state(root)

    if state.get("active"):
        feature_directory = state.get("feature_directory")
        if feature_directory and not (root / feature_directory).exists():
            errors.append(f"feature_directory does not exist: {feature_directory}")

        for key in ["spec_file", "plan_file", "tasks_file"]:
            value = state.get(key)
            if value is not None and not (root / value).exists():
                errors.append(f"{key} does not exist: {value}")

    json_out(
        {
            "ok": not errors,
            "state_file": posix(STATE_PATH),
            "exists": exists,
            "active": state.get("active", False),
            "state": state,
            "validation_errors": errors,
        }
    )
    return 0 if not errors else 1


def cmd_clear(args: argparse.Namespace) -> int:
    root = Path(args.cwd).resolve()

    if args.delete:
        path = state_file(root)
        if path.exists():
            path.unlink()
        json_out(
            {
                "ok": True,
                "action": "deleted",
                "state_file": posix(STATE_PATH),
                "active": False,
            }
        )
        return 0

    state = inactive_state()
    state["last_command"] = args.last_command
    ensure_state_dir(root)
    write_json_atomic(state_file(root), state)

    json_out(
        {
            "ok": True,
            "action": "cleared",
            "state_file": posix(STATE_PATH),
            "active": False,
            "state": state,
        }
    )
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    root = Path(args.cwd).resolve()

    state, errors = build_state(
        root=root,
        feature_dir_value=args.feature_directory,
        feature_id=args.feature_id,
        status=args.status,
        last_command=args.last_command,
        allow_missing=args.allow_missing,
    )

    if errors or state is None:
        return error(
            "invalid_active_feature",
            "could not set active feature",
            {"validation_errors": errors},
        )

    ensure_state_dir(root)
    write_json_atomic(state_file(root), state)

    json_out(
        {
            "ok": True,
            "action": "set",
            "state_file": posix(STATE_PATH),
            "active": True,
            "state": state,
        }
    )
    return 0



def cmd_resolve(args: argparse.Namespace) -> int:
    root = Path(args.cwd).resolve()
    specs_root = Path(args.specs_root)

    if not safe_rel(args.specs_root):
        return error("invalid_specs_root", "specs root must be a safe relative path")

    state, matches = find_feature(root, specs_root, args.feature_ref)

    if state is None and not matches:
        return error(
            "feature_not_found",
            f"feature not found: {args.feature_ref}",
            {"matches": []},
        )

    if state is None and len(matches) > 1:
        return error(
            "ambiguous_feature",
            f"feature reference is ambiguous: {args.feature_ref}",
            {"matches": matches},
        )

    if state is None:
        return error(
            "invalid_feature",
            f"could not resolve feature: {args.feature_ref}",
            {"matches": matches},
        )

    normalized, errors = normalize_state(state)
    if errors or normalized is None:
        return error(
            "invalid_active_feature",
            "resolved feature state is invalid",
            {"validation_errors": errors},
        )

    json_out(
        {
            "ok": True,
            "action": "resolved",
            "active": normalized.get("active", False),
            "state": normalized,
            "matches": matches,
            "state_written": False,
        }
    )
    return 0

def cmd_select(args: argparse.Namespace) -> int:
    root = Path(args.cwd).resolve()
    specs_root = Path(args.specs_root)

    if not safe_rel(args.specs_root):
        return error("invalid_specs_root", "specs root must be a safe relative path")

    state, matches = find_feature(root, specs_root, args.feature_ref)

    if state is None and not matches:
        return error(
            "feature_not_found",
            f"feature not found: {args.feature_ref}",
            {"matches": []},
        )

    if state is None and len(matches) > 1:
        return error(
            "ambiguous_feature",
            f"feature reference is ambiguous: {args.feature_ref}",
            {"matches": matches},
        )

    if state is None:
        return error(
            "invalid_feature",
            f"could not resolve feature: {args.feature_ref}",
            {"matches": matches},
        )

    state["last_command"] = args.last_command
    state["updated_at"] = now_iso()

    normalized, errors = normalize_state(state)
    if errors or normalized is None:
        return error(
            "invalid_active_feature",
            "resolved feature state is invalid",
            {"validation_errors": errors},
        )

    ensure_state_dir(root)
    write_json_atomic(state_file(root), normalized)

    json_out(
        {
            "ok": True,
            "action": "selected",
            "state_file": posix(STATE_PATH),
            "active": True,
            "state": normalized,
            "matches": matches,
        }
    )
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    root = Path(args.cwd).resolve()
    specs_root = Path(args.specs_root)

    if not safe_rel(args.specs_root):
        return error("invalid_specs_root", "specs root must be a safe relative path")

    features = discover_features(root, specs_root)

    json_out(
        {
            "ok": True,
            "specs_root": args.specs_root,
            "count": len(features),
            "features": features,
        }
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="OrderSpec active feature state manager")
    parser.add_argument("-C", "--cwd", default=".", help="project root")

    sub = parser.add_subparsers(dest="command", required=True)

    get_p = sub.add_parser("get", help="read active feature state")
    get_p.add_argument("--json", action="store_true")

    validate_p = sub.add_parser("validate", help="validate active feature state")
    validate_p.add_argument("--json", action="store_true")

    clear_p = sub.add_parser("clear", help="clear active feature state")
    clear_p.add_argument("--json", action="store_true")
    clear_p.add_argument("--delete", action="store_true", help="delete the state file instead of writing active:false")
    clear_p.add_argument("--last-command")

    set_p = sub.add_parser("set", help="set active feature explicitly")
    set_p.add_argument("--json", action="store_true")
    set_p.add_argument("--feature-id")
    set_p.add_argument("--feature-directory", required=True)
    set_p.add_argument("--status", choices=sorted(VALID_STATUSES))
    set_p.add_argument("--last-command")
    set_p.add_argument("--allow-missing", action="store_true")

    resolve_p = sub.add_parser("resolve", help="resolve existing feature by ID, directory, or short prefix without writing state")
    resolve_p.add_argument("feature_ref")
    resolve_p.add_argument("--json", action="store_true")
    resolve_p.add_argument("--specs-root", default=posix(DEFAULT_SPECS_ROOT))

    select_p = sub.add_parser("select", help="select existing feature by ID, directory, or short prefix")
    select_p.add_argument("feature_ref")
    select_p.add_argument("--json", action="store_true")
    select_p.add_argument("--specs-root", default=posix(DEFAULT_SPECS_ROOT))
    select_p.add_argument("--last-command")

    list_p = sub.add_parser("list", help="list discovered features")
    list_p.add_argument("--json", action="store_true")
    list_p.add_argument("--specs-root", default=posix(DEFAULT_SPECS_ROOT))

    args = parser.parse_args()

    if args.command == "get":
        return cmd_get(args)
    if args.command == "validate":
        return cmd_validate(args)
    if args.command == "clear":
        return cmd_clear(args)
    if args.command == "set":
        return cmd_set(args)
    if args.command == "resolve":
        return cmd_resolve(args)
    if args.command == "select":
        return cmd_select(args)
    if args.command == "list":
        return cmd_list(args)

    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
