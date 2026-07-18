#!/usr/bin/env python3
"""Deterministic state machine boundary for /order.code.

The script owns mechanical preflight, task selection, packet construction, and
terminal completeness checks. The agent still owns bounded semantic execution.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKER_PROTOCOL_PATH = SCRIPT_DIR.parent / "protocols" / "worker-execution.json"
ATTEMPT_STATE_DIR = ".state/code-attempts"
sys.path.insert(0, str(SCRIPT_DIR))

from common import get_feature_paths, get_repo_root  # noqa: E402
from task_context import READ_ONLY_TASK_TARGET, load_and_validate  # noqa: E402
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


def load_worker_protocol() -> tuple[dict[str, Any] | None, str | None]:
    try:
        protocol = json.loads(WORKER_PROTOCOL_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"cannot load canonical worker protocol: {exc}"
    required = {"protocol_version", "instructions", "capabilities", "result_schema"}
    if not isinstance(protocol, dict) or not required.issubset(protocol):
        return None, "canonical worker protocol is missing required fields"
    if protocol.get("protocol_version") != 1:
        return None, "unsupported canonical worker protocol version"
    if not isinstance(protocol.get("instructions"), list) or not protocol["instructions"]:
        return None, "canonical worker instructions must be a non-empty list"
    if any(not isinstance(item, str) or not item for item in protocol["instructions"]):
        return None, "canonical worker instructions must be non-empty strings"
    expected_capabilities = {
        "network", "package_installation", "git_mutation", "environment_mutation",
        "subagent_dispatch", "unrelated_commands",
    }
    capabilities = protocol.get("capabilities")
    if not isinstance(capabilities, dict) or set(capabilities) != expected_capabilities:
        return None, "canonical worker capabilities have invalid fields"
    if any(value is not False for value in capabilities.values()):
        return None, "canonical worker capabilities must be default-deny"
    result_schema = protocol.get("result_schema")
    if (
        not isinstance(result_schema, dict)
        or result_schema.get("type") != "object"
        or result_schema.get("additionalProperties") is not False
    ):
        return None, "canonical worker result schema is invalid"
    return protocol, None


def validate_worker_envelope(envelope: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(envelope, dict):
        return ["worker envelope must be an object"]
    expected = {"protocol_version", "instructions", "capabilities", "result_schema", "task"}
    if set(envelope) != expected:
        errors.append(f"worker envelope fields must be exactly {sorted(expected)}")
    task = envelope.get("task")
    task_fields = {
        "task_id", "phase", "task_line", "objective", "task_context",
        "contract_context", "inline_context", "verification", "read_only", "stop_conditions",
    }
    if not isinstance(task, dict) or set(task) != task_fields:
        errors.append(f"worker envelope task fields must be exactly {sorted(task_fields)}")
        return errors
    if not isinstance(task.get("task_id"), str) or not task["task_id"].startswith("T"):
        errors.append("worker envelope task_id is invalid")
    context = task.get("task_context")
    if not isinstance(context, dict) or set(context) != {"to_read", "write_paths", "target_state"}:
        errors.append("worker envelope task_context fields are invalid")
    verification = task.get("verification")
    if not isinstance(verification, dict) or set(verification) != {"required", "source", "expected"}:
        errors.append("worker envelope verification fields are invalid")
    elif verification.get("source") != "task_line":
        errors.append("worker envelope verification source must be task_line")
    if not isinstance(task.get("inline_context"), list):
        errors.append("worker envelope inline_context must be an array")
    return errors


def validate_worker_result(result: dict[str, Any], verification_required: bool) -> list[str]:
    errors: list[str] = []
    expected = {"task_id", "status", "changed_files", "verification", "deviation"}
    if set(result) != expected:
        errors.append(f"worker result fields must be exactly {sorted(expected)}")
    if result.get("status") not in {"SUCCESS", "FAILED", "BLOCKED", "NEEDS_CONTEXT"}:
        errors.append("worker result status is invalid")
    changed = result.get("changed_files")
    if (
        not isinstance(changed, list)
        or any(not isinstance(path, str) or not path for path in changed)
        or len(changed) != len(set(changed))
    ):
        errors.append("worker result changed_files must be unique non-empty strings")
    verification = result.get("verification")
    if not isinstance(verification, dict) or set(verification) != {"status", "evidence"}:
        errors.append("worker result verification fields are invalid")
    else:
        if verification.get("status") not in {"PASS", "FAIL", "NOT_RUN"}:
            errors.append("worker verification status is invalid")
        if not isinstance(verification.get("evidence"), str) or not verification["evidence"].strip():
            errors.append("worker verification evidence is empty")
        if result.get("status") == "SUCCESS" and verification_required and verification.get("status") != "PASS":
            errors.append("successful task requires PASS verification")
    deviation = result.get("deviation")
    if deviation is not None and not isinstance(deviation, str):
        errors.append("worker result deviation must be null or a string")
    if result.get("status") == "SUCCESS" and deviation is not None:
        errors.append("successful worker result must not contain a deviation")
    return errors


def safe_feature_dir(value: str, repo_root: Path) -> Path:
    path = Path(value).expanduser().resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError("feature directory must be inside repository root") from exc
    return path


def snapshot_repository(repo_root: Path) -> tuple[dict[str, dict[str, Any]], str | None]:
    snapshot: dict[str, dict[str, Any]] = {}
    try:
        for current, directories, files in os.walk(repo_root, topdown=True, followlinks=False):
            current_path = Path(current)
            directories[:] = sorted(
                name
                for name in directories
                if name != ".git"
            )
            for name in directories:
                path = current_path / name
                if path.is_symlink():
                    rel = path.relative_to(repo_root).as_posix()
                    snapshot[rel] = {"kind": "symlink", "digest": os.readlink(path)}
            for name in sorted(files):
                path = current_path / name
                rel = path.relative_to(repo_root).as_posix()
                if path.is_symlink():
                    snapshot[rel] = {"kind": "symlink", "digest": os.readlink(path)}
                    continue
                digest = hashlib.sha256()
                with path.open("rb") as handle:
                    while chunk := handle.read(1024 * 1024):
                        digest.update(chunk)
                snapshot[rel] = {"kind": "file", "digest": digest.hexdigest()}
    except (OSError, UnicodeError) as exc:
        return {}, f"cannot snapshot repository: {exc}"
    return snapshot, None


def changed_paths(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> list[str]:
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


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
    protocol, protocol_error = load_worker_protocol()
    if protocol_error:
        return 2, {"ok": False, "error": "invalid_worker_protocol", "message": protocol_error}
    task = {
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
            "write_paths": [] if record["path"] == READ_ONLY_TASK_TARGET else [record["path"]],
            "target_state": context["target_state"],
        },
        "contract_context": contract,
        "inline_context": [],
        "verification": {
            "required": record["requires_verification"],
            "source": "task_line",
            "expected": "PASS with short observable evidence when required; otherwise PASS or NOT_RUN",
        },
        "read_only": record["is_verification_only"],
        "stop_conditions": [
            "missing required context",
            "task contradicts supplied context",
            "required change outside task_context.write_paths",
        ],
    }
    assert protocol is not None
    envelope = copy.deepcopy(protocol)
    envelope["task"] = task
    envelope_errors = validate_worker_envelope(envelope)
    if envelope_errors:
        return 2, {
            "ok": False,
            "error": "invalid_worker_envelope",
            "validation_errors": envelope_errors,
        }
    return 0, envelope


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
        "worker_envelopes": packets,
    }


def attempt_begin(
    mode: str,
    feature_dir_value: str,
    task_ids: list[str],
    selected_phase: str | None,
) -> tuple[int, dict[str, Any]]:
    if not task_ids or len(task_ids) != len(set(task_ids)):
        return stop("invalid_attempt_tasks", "attempt requires unique task IDs")
    next_rc, next_payload = next_packets(mode, feature_dir_value, selected_phase)
    if next_rc != 0 or next_payload.get("action") not in {"EXECUTE_TASK", "EXECUTE_TASK_GROUP"}:
        return next_rc or 2, next_payload
    envelopes = next_payload["worker_envelopes"]
    expected_ids = [item["task"]["task_id"] for item in envelopes]
    if task_ids != expected_ids:
        return stop(
            "attempt_task_mismatch",
            f"attempt tasks {task_ids} do not match next execution unit {expected_ids}",
        )

    repo_root = get_repo_root().resolve()
    try:
        feature_dir = safe_feature_dir(feature_dir_value, repo_root)
    except ValueError as exc:
        return stop("invalid_feature_dir", str(exc))
    attempt_dir = feature_dir / ATTEMPT_STATE_DIR
    attempt_dir.mkdir(parents=True, exist_ok=True)
    baseline, snapshot_error = snapshot_repository(repo_root)
    if snapshot_error:
        return stop("attempt_snapshot_failed", snapshot_error)

    attempt_id = secrets.token_hex(16)
    state: dict[str, Any] = {
        "version": 1,
        "attempt_id": attempt_id,
        "mode": mode,
        "feature_dir": feature_dir.relative_to(repo_root).as_posix(),
        "task_ids": expected_ids,
        "write_paths": {
            envelope["task"]["task_id"]: envelope["task"]["task_context"]["write_paths"]
            for envelope in envelopes
        },
        "verification_required": {
            envelope["task"]["task_id"]: envelope["task"]["verification"]["required"]
            for envelope in envelopes
        },
        "baseline": baseline,
        "results_file": (attempt_dir / f"{attempt_id}-results.json").relative_to(repo_root).as_posix(),
    }
    state["state_digest"] = hashlib.sha256(
        json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    state_path = attempt_dir / f"{attempt_id}.json"
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0, {
        "ok": True,
        "action": "DISPATCH",
        "attempt_id": attempt_id,
        "task_ids": expected_ids,
        "worker_envelopes": envelopes,
        "state_file": state_path.relative_to(repo_root).as_posix(),
        "results_file": state["results_file"],
    }


def attempt_finish(
    feature_dir_value: str,
    attempt_id: str,
    results_file_value: str,
) -> tuple[int, dict[str, Any]]:
    repo_root = get_repo_root().resolve()
    try:
        feature_dir = safe_feature_dir(feature_dir_value, repo_root)
    except ValueError as exc:
        return stop("invalid_feature_dir", str(exc))
    if not attempt_id or any(char not in "0123456789abcdef" for char in attempt_id):
        return stop("invalid_attempt_id", "attempt ID must be lowercase hexadecimal")
    state_path = feature_dir / ATTEMPT_STATE_DIR / f"{attempt_id}.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        results_path = Path(results_file_value).resolve()
        results_path.relative_to(repo_root)
        if results_path.relative_to(repo_root).as_posix() != state.get("results_file"):
            raise ValueError("results file does not match attempt-owned result path")
        results = json.loads(results_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return stop("invalid_attempt_input", str(exc))
    if state.get("attempt_id") != attempt_id or state.get("version") != 1:
        return stop("invalid_attempt_state", "attempt state identity or version mismatch")
    state_digest = state.pop("state_digest", None)
    expected_digest = hashlib.sha256(
        json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if state_digest != expected_digest:
        return stop("invalid_attempt_state", "attempt state integrity check failed")
    if isinstance(results, dict):
        results = [results]
    if not isinstance(results, list) or not all(isinstance(item, dict) for item in results):
        return stop("invalid_worker_results", "results file must contain one result object or an array")
    result_ids = [item.get("task_id") for item in results]
    if result_ids != state.get("task_ids"):
        return stop(
            "worker_result_task_mismatch",
            f"worker result task IDs {result_ids} do not match attempt {state.get('task_ids')}",
        )
    result_errors = []
    for result in results:
        errors = validate_worker_result(
            result,
            bool(state.get("verification_required", {}).get(result["task_id"])),
        )
        if errors:
            result_errors.append({"task_id": result["task_id"], "errors": errors})
    if result_errors:
        return 2, {
            "ok": False,
            "action": "STOP",
            "terminal": True,
            "error": "invalid_worker_results",
            "results": result_errors,
        }

    current, snapshot_error = snapshot_repository(repo_root)
    if snapshot_error:
        return stop("attempt_snapshot_failed", snapshot_error)
    framework_owned = {
        state_path.relative_to(repo_root).as_posix(),
        state["results_file"],
    }
    baseline = dict(state["baseline"])
    for path in framework_owned:
        baseline.pop(path, None)
        current.pop(path, None)
    observed = changed_paths(baseline, current)
    owners: dict[str, str] = {}
    for task_id, paths in state["write_paths"].items():
        for path in paths:
            if path in owners:
                return stop("invalid_attempt_state", f"shared write path in attempt: {path}")
            owners[path] = task_id
    unexpected = [path for path in observed if path not in owners]
    observed_by_task = {
        task_id: sorted(path for path in observed if owners.get(path) == task_id)
        for task_id in state["task_ids"]
    }
    mismatches = []
    for result in results:
        reported = result.get("changed_files")
        expected = observed_by_task[result["task_id"]]
        if not isinstance(reported, list) or sorted(reported) != expected:
            mismatches.append({
                "task_id": result["task_id"],
                "reported": reported,
                "observed": expected,
            })
        elif (
            result.get("status") == "SUCCESS"
            and state["write_paths"][result["task_id"]]
            and expected != sorted(state["write_paths"][result["task_id"]])
        ):
            mismatches.append({
                "task_id": result["task_id"],
                "reported": reported,
                "observed": expected,
                "error": "successful write task did not change every declared write path",
            })
    if unexpected or mismatches:
        return 2, {
            "ok": False,
            "action": "STOP",
            "terminal": True,
            "error": "attempt_changes_rejected",
            "unexpected_changed_paths": unexpected,
            "result_mismatches": mismatches,
            "observed_by_task": observed_by_task,
        }
    failed = [
        {"task_id": item["task_id"], "status": item.get("status")}
        for item in results
        if item.get("status") != "SUCCESS"
    ]
    if failed:
        return 2, {
            "ok": False,
            "action": "STOP",
            "terminal": True,
            "error": "worker_failed",
            "workers": failed,
            "observed_by_task": observed_by_task,
        }
    return 0, {
        "ok": True,
        "action": "READY_TO_VERIFY_AND_MARK",
        "attempt_id": attempt_id,
        "task_ids": state["task_ids"],
        "observed_by_task": observed_by_task,
        "results": results,
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

    def update_status(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        status_rc, status = run_json(
            [
                sys.executable,
                str(SCRIPT_DIR / "active_feature.py"),
                "status",
                "--feature-id",
                feature_id,
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

    attempt_begin_parser = subparsers.add_parser("attempt-begin")
    attempt_begin_parser.add_argument("--mode", required=True, choices=sorted(FULL_MODES | {"LOCAL_PHASE"}))
    attempt_begin_parser.add_argument("--feature-dir", required=True)
    attempt_begin_parser.add_argument("--task-id", action="append", required=True)
    attempt_begin_parser.add_argument("--selected-phase")

    attempt_finish_parser = subparsers.add_parser("attempt-finish")
    attempt_finish_parser.add_argument("--feature-dir", required=True)
    attempt_finish_parser.add_argument("--attempt-id", required=True)
    attempt_finish_parser.add_argument("--results-file", required=True)

    finish_parser = subparsers.add_parser("finish")
    finish_parser.add_argument("--mode", required=True, choices=sorted(FULL_MODES | {"LOCAL_PHASE"}))
    finish_parser.add_argument("--feature-dir", required=True)
    finish_parser.add_argument("--outcome", required=True, choices=["COMPLETE", "PHASE_COMPLETE", "HALTED"])

    args = parser.parse_args()
    if args.command == "preflight":
        rc, payload = preflight(args.mode, args.force)
    elif args.command == "next":
        rc, payload = next_packets(args.mode, args.feature_dir, args.selected_phase)
    elif args.command == "attempt-begin":
        rc, payload = attempt_begin(args.mode, args.feature_dir, args.task_id, args.selected_phase)
    elif args.command == "attempt-finish":
        rc, payload = attempt_finish(args.feature_dir, args.attempt_id, args.results_file)
    else:
        rc, payload = finish(args.mode, args.feature_dir, args.outcome)
    emit(payload)
    return rc


if __name__ == "__main__":
    sys.exit(main())
