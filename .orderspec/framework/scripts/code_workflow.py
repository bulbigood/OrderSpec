#!/usr/bin/env python3
"""Deterministic state machine boundary for /order.code.

The script owns mechanical preflight, task selection, packet construction, and
terminal completeness checks. The agent still owns bounded semantic execution.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from common import get_feature_paths, get_repo_root  # noqa: E402
from task_context import load_and_validate  # noqa: E402
from task_contract_context import resolve as resolve_contract, validate as validate_contracts  # noqa: E402
from task_progress import parse_tasks  # noqa: E402


FULL_MODES = {"LOCAL_ALL", "DELEGATED"}
MODES = {*FULL_MODES, "LOCAL_PHASE", "RESET"}


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def run_json(command: list[str], cwd: Path) -> tuple[int, dict[str, Any]]:
    process = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError:
        payload = {
            "ok": False,
            "error": "invalid_script_output",
            "command": command,
            "stdout": process.stdout.strip(),
            "stderr": process.stderr.strip(),
        }
    return process.returncode, payload


def safe_feature_dir(value: str, repo_root: Path) -> Path:
    path = Path(value).expanduser().resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError("feature directory must be inside repository root") from exc
    return path


def resolve_paths() -> tuple[Path, dict[str, str]]:
    paths = get_feature_paths(persist_active_feature=False)
    return Path(paths["REPO_ROOT"]).resolve(), paths


def stop(error: str, message: str, *, route: str | None = None) -> tuple[int, dict[str, Any]]:
    payload: dict[str, Any] = {
        "ok": False,
        "action": "STOP",
        "error": error,
        "message": message,
    }
    if route:
        payload["route"] = route
    return 2, payload


def preflight(mode: str, force: bool) -> tuple[int, dict[str, Any]]:
    if mode not in MODES:
        return stop("invalid_mode", f"unsupported execution mode: {mode}")
    try:
        repo_root, paths = resolve_paths()
    except RuntimeError as exc:
        return stop("no_active_feature", str(exc), route="/order.spec")

    feature_dir = Path(paths["FEATURE_DIR"])
    plan = Path(paths["IMPL_PLAN"])
    tasks = Path(paths["TASKS"])
    if not feature_dir.is_dir():
        return stop("missing_feature_directory", str(feature_dir), route="/order.spec")
    if not plan.is_file():
        return stop("missing_plan", str(plan), route="/order.plan")
    if not tasks.is_file():
        return stop("missing_tasks", str(tasks), route="/order.tasks")

    if mode == "RESET":
        return 0, {
            "ok": True,
            "action": "RESET_PREVIEW",
            "mode": mode,
            "feature_dir": str(feature_dir),
            "command": [
                sys.executable,
                str(SCRIPT_DIR / "work_order.py"),
                "rollback",
                "--feature-dir",
                str(feature_dir),
            ],
        }

    gate_command = [
        sys.executable,
        str(SCRIPT_DIR / "upstream_gate.py"),
        "--report",
        str(feature_dir / "tasks-report.md"),
        "--artifact",
        str(tasks),
        "--upstream-name",
        "tasks.md",
        "--this",
        "/order.code",
        "--build",
        "/order.tasks",
        "--fix",
        "/order.tasks",
        "--recheck",
        "/order.tasks-check",
    ]
    if force:
        gate_command.append("--force")
    gate_rc, gate = run_json(gate_command, repo_root)
    if gate_rc != 0:
        return gate_rc, {
            "ok": False,
            "action": "STOP",
            "error": "upstream_gate",
            "gate": gate,
        }

    records, task_errors = parse_tasks(tasks)
    if task_errors:
        return stop("invalid_tasks", "; ".join(task_errors), route="/order.tasks")

    _, _, context_errors, missing = load_and_validate(feature_dir, repo_root)
    if context_errors:
        rc, payload = stop("invalid_task_context", "; ".join(context_errors), route="/order.tasks")
        payload["missing_required"] = missing
        return rc, payload

    contract_rc, contract_validation = validate_contracts(feature_dir, repo_root)
    if contract_rc != 0:
        return contract_rc, {
            "ok": False,
            "action": "STOP",
            "error": "invalid_task_contract_context",
            "route": "/order.tasks or /order.spec",
            "validation": contract_validation,
        }

    unchecked = [record for record in records if record["status"] == " "]
    phases = list(dict.fromkeys(record["phase"] for record in records))
    selected_phase = unchecked[0]["phase"] if unchecked and mode == "LOCAL_PHASE" else None
    return 0, {
        "ok": True,
        "action": "COMPLETE" if not unchecked else "READY",
        "mode": mode,
        "force": force,
        "feature_dir": str(feature_dir),
        "feature_id": Path(feature_dir).name,
        "tasks_file": str(tasks),
        "total": len(records),
        "completed": len(records) - len(unchecked),
        "first_unchecked": unchecked[0]["task_id"] if unchecked else None,
        "phase_count": len(phases),
        "selected_phase": selected_phase,
        "gate": gate,
    }


def packet_for(
    record: dict[str, Any],
    feature_dir: Path,
    repo_root: Path,
    contexts: dict[str, dict[str, Any]],
) -> tuple[int, dict[str, Any]]:
    context = contexts[record["task_id"]]
    contract_rc, contract = resolve_contract(feature_dir, record["task_id"], repo_root)
    if contract_rc != 0:
        return contract_rc, contract
    return 0, {
        "task_id": record["task_id"],
        "phase": record["phase"],
        "task_line": record["line"],
        "objective": record["line"].split(" | ")[-1].strip(),
        "task_context": {
            "to_read": [
                {
                    "path": path,
                    "usage": "inspect",
                    "authority": "feature",
                    "required": True,
                }
                for path in context["read"]
            ],
            "write_paths": [record["path"]],
            "target_state": context["target_state"],
        },
        "contract_context": contract,
        "verification_required": record["requires_verification"],
        "read_only": record["is_verification_only"],
        "stop_conditions": [
            "missing required context",
            "task contradicts supplied context",
            "required change outside task_context.write_paths",
        ],
    }


def next_packets(mode: str, feature_dir_value: str, selected_phase: str | None) -> tuple[int, dict[str, Any]]:
    if mode not in FULL_MODES | {"LOCAL_PHASE"}:
        return stop("invalid_mode", f"next does not support mode: {mode}")
    repo_root = get_repo_root().resolve()
    try:
        feature_dir = safe_feature_dir(feature_dir_value, repo_root)
    except ValueError as exc:
        return stop("invalid_feature_dir", str(exc))

    records, contexts, errors, missing = load_and_validate(feature_dir, repo_root)
    if errors:
        rc, payload = stop("invalid_task_context", "; ".join(errors), route="/order.tasks")
        payload["missing_required"] = missing
        return rc, payload

    unchecked = [record for record in records if record["status"] == " "]
    if mode == "LOCAL_PHASE":
        if not selected_phase:
            return stop("missing_selected_phase", "LOCAL_PHASE requires --selected-phase")
        unchecked = [record for record in unchecked if record["phase"] == selected_phase]
        if not unchecked:
            return 0, {"ok": True, "action": "PHASE_COMPLETE", "phase": selected_phase}
    if not unchecked:
        return 0, {"ok": True, "action": "COMPLETE"}

    first = unchecked[0]
    candidates = [first]
    if mode == "DELEGATED" and first["is_parallel"]:
        first_index = records.index(first)
        seen_paths = {first["path"]}
        for record in records[first_index + 1 :]:
            if (
                record["status"] != " "
                or record["phase"] != first["phase"]
                or not record["is_parallel"]
                or record["path"] in seen_paths
            ):
                break
            candidates.append(record)
            seen_paths.add(record["path"])

    packets = []
    for record in candidates:
        rc, packet = packet_for(record, feature_dir, repo_root, contexts)
        if rc != 0:
            return rc, {
                "ok": False,
                "action": "STOP",
                "error": "packet_resolution_failed",
                "task_id": record["task_id"],
                "details": packet,
            }
        packets.append(packet)

    return 0, {
        "ok": True,
        "action": "EXECUTE_TASK_GROUP" if len(packets) > 1 else "EXECUTE_TASK",
        "packets": packets,
    }


def finish(mode: str, feature_dir_value: str, outcome: str) -> tuple[int, dict[str, Any]]:
    if mode not in FULL_MODES | {"LOCAL_PHASE"}:
        return stop("invalid_mode", f"finish does not support mode: {mode}")
    if outcome not in {"COMPLETE", "PHASE_COMPLETE", "HALTED"}:
        return stop("invalid_outcome", f"unsupported outcome: {outcome}")
    if mode in FULL_MODES and outcome == "PHASE_COMPLETE":
        return stop("invalid_outcome", f"{mode} cannot finish at a phase boundary")

    repo_root = get_repo_root().resolve()
    try:
        feature_dir = safe_feature_dir(feature_dir_value, repo_root)
    except ValueError as exc:
        return stop("invalid_feature_dir", str(exc))
    tasks = feature_dir / "tasks.md"
    records, errors = parse_tasks(tasks)
    if errors:
        return stop("invalid_tasks", "; ".join(errors), route="/order.tasks")
    unchecked = [record["task_id"] for record in records if record["status"] == " "]
    if mode in FULL_MODES and outcome == "COMPLETE" and unchecked:
        return 1, {
            "ok": False,
            "action": "CONTINUE",
            "error": "tasks_incomplete",
            "first_unchecked": unchecked[0],
            "unchecked": len(unchecked),
        }
    feature_name = feature_dir.name
    feature_id = feature_name if feature_name.startswith("FEAT-") else f"FEAT-{feature_name}"
    feature_rel = str(feature_dir.relative_to(repo_root)).replace("\\", "/")

    def update_status(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        status_rc, status = run_json(
            [
                sys.executable,
                str(SCRIPT_DIR / "active_feature.py"),
                "set",
                "--feature-id",
                feature_id,
                "--feature-directory",
                feature_rel,
                "--status",
                "implementing",
                "--last-command",
                "order.code",
                "--json",
            ],
            repo_root,
        )
        payload["active_feature"] = status
        if status_rc != 0:
            payload.update({"ok": False, "action": "STOP", "error": "status_update_failed"})
            return status_rc, payload
        return 0, payload

    if outcome == "HALTED":
        return update_status({
            "ok": True,
            "action": "HALTED",
            "completed": len(records) - len(unchecked),
            "total": len(records),
            "first_unchecked": unchecked[0] if unchecked else None,
        })

    trace_rc, trace = run_json(
        [
            sys.executable,
            str(SCRIPT_DIR / "traceability.py"),
            "-C",
            str(repo_root),
            "--feature-dir",
            str(feature_dir),
            "check-mechanisms",
        ],
        repo_root,
    )
    if trace_rc != 0:
        payload = {
            "ok": False,
            "action": "STOP",
            "error": "mechanism_coverage",
            "route": "/order.tasks or /order.spec",
            "details": trace,
        }
        status_rc, payload = update_status(payload)
        return trace_rc if status_rc == 0 else status_rc, payload
    return update_status({
        "ok": True,
        "action": outcome,
        "completed": len(records) - len(unchecked),
        "total": len(records),
        "coverage": trace,
    })


def main() -> int:
    parser = argparse.ArgumentParser(prog="code_workflow.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight_parser = subparsers.add_parser("preflight")
    preflight_parser.add_argument("--mode", required=True, choices=sorted(MODES))
    preflight_parser.add_argument("--force", action="store_true")

    next_parser = subparsers.add_parser("next")
    next_parser.add_argument("--mode", required=True, choices=sorted(FULL_MODES | {"LOCAL_PHASE"}))
    next_parser.add_argument("--feature-dir", required=True)
    next_parser.add_argument("--selected-phase")

    finish_parser = subparsers.add_parser("finish")
    finish_parser.add_argument("--mode", required=True, choices=sorted(FULL_MODES | {"LOCAL_PHASE"}))
    finish_parser.add_argument("--feature-dir", required=True)
    finish_parser.add_argument("--outcome", required=True, choices=["COMPLETE", "PHASE_COMPLETE", "HALTED"])

    args = parser.parse_args()
    if args.command == "preflight":
        rc, payload = preflight(args.mode, args.force)
    elif args.command == "next":
        rc, payload = next_packets(args.mode, args.feature_dir, args.selected_phase)
    else:
        rc, payload = finish(args.mode, args.feature_dir, args.outcome)
    emit(payload)
    return rc


if __name__ == "__main__":
    sys.exit(main())
