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
import tempfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKER_PROTOCOL_PATH = SCRIPT_DIR.parent / "protocols" / "worker-execution.json"
ATTEMPT_STATE_DIR = ".state/code-attempts"
ATTEMPT_CURRENT_NAME = "current.json"
ATTEMPT_HISTORY_DIR = "history"
ATTEMPT_VERSION = 3
sys.path.insert(0, str(SCRIPT_DIR))

from common import get_feature_paths, get_repo_root  # noqa: E402
from task_context import READ_ONLY_TASK_TARGET, load_and_validate  # noqa: E402
from task_contract_context import resolve as resolve_contract, validate as validate_contracts  # noqa: E402
from task_progress import parse_tasks, validate_phase_gates  # noqa: E402
from workflow_feedback import load_open_for_command  # noqa: E402


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
    verification_fields = {"required", "source", "expected"}
    if (
        not isinstance(verification, dict)
        or frozenset(verification) not in {
            frozenset(verification_fields), frozenset(verification_fields | {"mode"})
        }
    ):
        errors.append("worker envelope verification fields are invalid")
    elif verification.get("source") != "task_line":
        errors.append("worker envelope verification source must be task_line")
    if not isinstance(task.get("inline_context"), list):
        errors.append("worker envelope inline_context must be an array")
    return errors


def validate_worker_result(
    result: dict[str, Any], verification_required: bool, verification_mode: str
) -> list[str]:
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
    allowed_verification = {"status", "evidence", "expected_outcome", "observed_outcome"}
    if (
        not isinstance(verification, dict)
        or not {"status", "evidence"}.issubset(verification)
        or set(verification) - allowed_verification
    ):
        errors.append("worker result verification fields are invalid")
    else:
        if verification.get("status") not in {"PASS", "FAIL", "NOT_RUN"}:
            errors.append("worker verification status is invalid")
        if not isinstance(verification.get("evidence"), str) or not verification["evidence"].strip():
            errors.append("worker verification evidence is empty")
        if result.get("status") == "SUCCESS" and verification_required and verification.get("status") != "PASS":
            errors.append("successful task requires PASS verification")
        if result.get("status") == "SUCCESS" and verification_mode == "red":
            if verification.get("expected_outcome") != "FAIL":
                errors.append("red-first task requires expected_outcome FAIL")
            if verification.get("observed_outcome") != "FAIL":
                errors.append("red-first task requires observed_outcome FAIL")
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
                parts = path.relative_to(repo_root).parts
                if name.startswith(".") and any(
                    parts[index:index + 2] == (".state", "code-attempts")
                    for index in range(len(parts) - 1)
                ):
                    continue
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
        "terminal": True,
        "continuation_required": False,
        "error": error,
        "message": message,
    }
    if route:
        payload["route"] = route
    return 2, payload


def continuing(payload: dict[str, Any], next_action: str) -> dict[str, Any]:
    """Mark a machine state that must not become a conversational boundary."""
    return {
        **payload,
        "terminal": False,
        "continuation_required": True,
        "next_action": next_action,
        "final_response": {
            "permitted": False,
            "reason": "NON_TERMINAL_WORKFLOW_STATE",
        },
    }


def attempt_state_digest(state: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in state.items() if key != "state_digest"}
    return hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_attempt_state(path: Path, state: dict[str, Any]) -> str | None:
    state["state_digest"] = attempt_state_digest(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
        temporary = Path(temp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    except OSError as exc:
        return str(exc)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return None


def write_json_atomic(path: Path, payload: dict[str, Any]) -> str | None:
    """Write a framework-owned JSON payload without attempt-state signing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
        temporary = Path(temp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    except OSError as exc:
        return str(exc)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return None


def create_attempt_state(path: Path, state: dict[str, Any]) -> str | None:
    """Create the singleton current slot without a check-then-create race."""
    state["state_digest"] = attempt_state_digest(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
        temporary = Path(temp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        fsync_directory(path.parent)
    except FileExistsError:
        return "attempt slot already exists"
    except OSError as exc:
        return str(exc)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return None


def load_attempt_state(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"cannot read attempt state {path.name}: {exc}"
    if not isinstance(state, dict) or state.get("version") != ATTEMPT_VERSION:
        return None, f"unsupported attempt state version in {path.name}"
    attempt_id = state.get("attempt_id")
    if not isinstance(attempt_id, str) or not attempt_id or any(
        char not in "0123456789abcdef" for char in attempt_id
    ):
        return None, f"invalid attempt state identity in {path.name}"
    if state.get("state_digest") != attempt_state_digest(state):
        return None, f"attempt state integrity check failed: {path.name}"
    required = {
        "version", "attempt_id", "mode", "feature_dir", "task_ids", "write_paths",
        "verification_required", "worker_envelopes", "baseline", "results_file", "state_digest",
    }
    optional = {
        "finish_status", "terminal_error", "reconciliation_commands", "reconciliation_files",
    }
    if not required.issubset(state) or set(state) - required - optional:
        return None, f"attempt state fields are invalid in {path.name}"
    task_ids = state.get("task_ids")
    envelopes = state.get("worker_envelopes")
    if (
        state.get("mode") not in FULL_MODES | {"LOCAL_PHASE"}
        or not isinstance(state.get("feature_dir"), str)
        or not isinstance(task_ids, list)
        or not task_ids
        or len(task_ids) != len(set(task_ids))
        or not isinstance(state.get("write_paths"), dict)
        or set(state["write_paths"]) != set(task_ids)
        or not isinstance(state.get("verification_required"), dict)
        or set(state["verification_required"]) != set(task_ids)
        or not isinstance(envelopes, list)
        or len(envelopes) != len(task_ids)
        or not isinstance(state.get("baseline"), dict)
        or not isinstance(state.get("results_file"), str)
    ):
        return None, f"attempt state structure is invalid in {path.name}"
    envelope_ids = []
    for envelope in envelopes:
        errors = validate_worker_envelope(envelope)
        if errors:
            return None, f"stored worker envelope is invalid in {path.name}: {'; '.join(errors)}"
        envelope_ids.append(envelope["task"]["task_id"])
    if envelope_ids != task_ids:
        return None, f"stored worker envelope order is invalid in {path.name}"
    expected_results = (
        Path(state["feature_dir"])
        / ATTEMPT_STATE_DIR
        / f"{state['attempt_id']}-results.json"
    ).as_posix()
    if state["results_file"] != expected_results:
        return None, f"attempt results path is invalid in {path.name}"
    finish_status = state.get("finish_status")
    if finish_status not in {
        None, "accepted", "invalid_results", "rejected", "worker_failed", "reconcile_candidate",
    }:
        return None, f"attempt finish status is invalid in {path.name}"
    reconciliation_commands = state.get("reconciliation_commands")
    reconciliation_files = state.get("reconciliation_files")
    if finish_status == "reconcile_candidate":
        if (
            not isinstance(reconciliation_commands, list)
            or not reconciliation_commands
            or any(
                not isinstance(command, list)
                or not command
                or any(not isinstance(part, str) or not part for part in command)
                for command in reconciliation_commands
            )
            or not isinstance(reconciliation_files, list)
            or not reconciliation_files
            or any(not isinstance(item, str) or not item for item in reconciliation_files)
        ):
            return None, f"attempt reconciliation state is invalid in {path.name}"
    elif reconciliation_commands is not None or reconciliation_files is not None:
        return None, f"unexpected attempt reconciliation state in {path.name}"
    state["_state_path"] = path
    return state, None


def archive_attempt_state(feature_dir: Path, state: dict[str, Any]) -> str | None:
    """Atomically remove a closed attempt from the singleton execution boundary."""
    state_path = feature_dir / ATTEMPT_STATE_DIR / ATTEMPT_CURRENT_NAME
    history_dir = state_path.parent / ATTEMPT_HISTORY_DIR
    history_path = history_dir / f"{state['attempt_id']}.json"
    try:
        history_dir.mkdir(parents=True, exist_ok=True)
        if history_path.exists():
            return f"attempt history already exists: {history_path}"
        os.replace(state_path, history_path)
        fsync_directory(history_dir)
        fsync_directory(state_path.parent)
    except OSError as exc:
        return str(exc)
    return None


def attempt_inventory(feature_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Return the sole integrity-checked current attempt, if one exists."""
    current = feature_dir / ATTEMPT_STATE_DIR / ATTEMPT_CURRENT_NAME
    if not current.exists():
        return [], []
    state, error = load_attempt_state(current)
    return ([] if state is None else [state]), ([] if error is None else [error])


def blocking_attempts(feature_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    states, errors = attempt_inventory(feature_dir)
    return states, errors


def invalid_attempt_inventory_stop(feature_dir: Path, errors: list[str]) -> tuple[int, dict[str, Any]]:
    rc, payload = stop("invalid_attempt_inventory", "; ".join(errors))
    payload["recovery"] = {
        "action": "RESET_PREVIEW",
        "command": [
            sys.executable,
            str(SCRIPT_DIR / "code_workflow.py"),
            "attempt-reset",
            "--feature-dir",
            str(feature_dir),
        ],
    }
    return rc, payload


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
            "action": "RESET_APPLY",
            "terminal": False,
            "continuation_required": True,
            "mode": mode,
            "feature_dir": str(feature_dir),
            "command": [
                sys.executable,
                str(SCRIPT_DIR / "work_order.py"),
                "rollback",
                "--feature-dir",
                str(feature_dir),
                "--apply",
            ],
            "next_action": "execute command immediately; --reset is explicit authorization",
            "final_response": {
                "permitted": False,
                "reason": "NON_TERMINAL_WORKFLOW_STATE",
            },
        }

    open_feedback: list[dict[str, Any]] = []
    feedback_errors: list[str] = []
    for target in ("order.bootstrap", "order.spec", "order.plan", "order.tasks"):
        items, errors = load_open_for_command(repo_root, feature_dir, target)
        open_feedback.extend(item for item in items if item.get("source") == "order.code")
        feedback_errors.extend(errors)
    if feedback_errors:
        return stop("invalid_feedback_state", "; ".join(feedback_errors))
    if open_feedback:
        feedback = sorted(
            open_feedback,
            key=lambda item: (str(item.get("created_at", "")), str(item.get("id", ""))),
        )[0]
        return 0, continuing(
            {
                "ok": True,
                "action": "ROUTE_EXISTING_FEEDBACK",
                "mode": mode,
                "feature_dir": str(feature_dir),
                "feedback": feedback,
                "route_feedback": {
                    "feedback_file": feedback["report"],
                    "target": feedback["target"],
                    "requested_change": feedback["requested_change"],
                    "recommended_command": feedback["recommended_command"],
                },
            },
            "call workflow_supervisor.py route-feedback with route_feedback.feedback_file immediately",
        )

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
            "terminal": True,
            "continuation_required": False,
            "error": "upstream_gate",
            "gate": gate,
        }

    records, task_errors = parse_tasks(tasks)
    task_errors.extend(validate_phase_gates(records))
    if task_errors:
        return stop("invalid_tasks", "; ".join(task_errors), route="/order.tasks")

    _, _, context_errors, missing = load_and_validate(feature_dir, repo_root)
    if context_errors:
        rc, payload = stop("invalid_task_context", "; ".join(context_errors), route="/order.tasks")
        payload["missing_required"] = missing
        return rc, payload

    contract_rc, contract_validation = validate_contracts(feature_dir, repo_root)
    if contract_rc != 0:
        failures = contract_validation.get("failures", [])
        route = (
            "/order.spec"
            if any(item.get("error") == "invalid_contract_anchors" for item in failures)
            else "/order.tasks or /order.spec"
        )
        return contract_rc, {
            "ok": False,
            "action": "STOP",
            "terminal": True,
            "continuation_required": False,
            "error": "invalid_task_contract_context",
            "route": route,
            "validation": contract_validation,
        }

    unchecked = [record for record in records if record["status"] == " "]
    phases = list(dict.fromkeys(record["phase"] for record in records))
    selected_phase = unchecked[0]["phase"] if unchecked and mode == "LOCAL_PHASE" else None
    action = "COMPLETE" if not unchecked else "READY"
    return 0, continuing({
        "ok": True,
        "action": action,
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
    }, "run terminal validation" if action == "COMPLETE" else "call code_workflow.py next immediately")


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
            "mode": record["evidence_mode"],
            "expected": (
                "PASS while recording expected_outcome FAIL and observed_outcome FAIL; evidence must name the exact failing assertions"
                if record["evidence_mode"] == "red"
                else "PASS with short observable evidence when required; otherwise PASS or NOT_RUN"
            ),
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
            return 0, continuing(
                {"ok": True, "action": "PHASE_COMPLETE", "phase": selected_phase},
                "run terminal validation immediately",
            )
    if not unchecked:
        return 0, continuing(
            {"ok": True, "action": "COMPLETE"},
            "run terminal validation immediately",
        )

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
                "terminal": True,
                "continuation_required": False,
                "error": "packet_resolution_failed",
                "task_id": record["task_id"],
                "details": packet,
            }
        packets.append(packet)

    return 0, continuing({
        "ok": True,
        "action": "EXECUTE_TASK_GROUP" if len(packets) > 1 else "EXECUTE_TASK",
        "worker_envelopes": packets,
    }, "call attempt-begin and execute the returned envelope immediately")


def attempt_begin(
    mode: str,
    feature_dir_value: str,
    task_ids: list[str],
    selected_phase: str | None,
) -> tuple[int, dict[str, Any]]:
    if not task_ids or len(task_ids) != len(set(task_ids)):
        return stop("invalid_attempt_tasks", "attempt requires unique task IDs")
    repo_root = get_repo_root().resolve()
    try:
        feature_dir = safe_feature_dir(feature_dir_value, repo_root)
    except ValueError as exc:
        return stop("invalid_feature_dir", str(exc))

    blocking, inventory_errors = blocking_attempts(feature_dir)
    if inventory_errors:
        return invalid_attempt_inventory_stop(feature_dir, inventory_errors)
    current = blocking[0] if blocking else None
    if current and current.get("finish_status") == "accepted":
        return stop(
            "attempt_pending_mark",
            "accepted attempt must be verified, marked, and cleaned before another attempt: "
            + current["attempt_id"],
        )
    if current and current.get("finish_status") is not None:
        archive_error = archive_attempt_state(feature_dir, current)
        if archive_error:
            return stop("attempt_archive_failed", archive_error)
        return attempt_begin(mode, feature_dir_value, task_ids, selected_phase)
    if current:
        state = current
        if state.get("mode") != mode or state.get("task_ids") != task_ids:
            return stop(
                "active_attempt_mismatch",
                f"active attempt {state['attempt_id']} owns {state.get('task_ids')} in {state.get('mode')}",
            )
        envelopes = state.get("worker_envelopes")
        if not isinstance(envelopes, list) or not envelopes:
            return stop("invalid_attempt_state", "current attempt has no resumable envelopes")
        return 0, continuing({
            "ok": True,
            "action": "RESUME_ATTEMPT",
            "attempt_id": state["attempt_id"],
            "task_ids": state["task_ids"],
            "worker_envelopes": envelopes,
            "state_file": state["_state_path"].relative_to(repo_root).as_posix(),
            "results_file": state["results_file"],
        }, "execute the original envelope and finish the existing attempt")

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

    attempt_dir = feature_dir / ATTEMPT_STATE_DIR
    attempt_dir.mkdir(parents=True, exist_ok=True)
    baseline, snapshot_error = snapshot_repository(repo_root)
    if snapshot_error:
        return stop("attempt_snapshot_failed", snapshot_error)

    attempt_id = secrets.token_hex(16)
    state: dict[str, Any] = {
        "version": ATTEMPT_VERSION,
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
        "worker_envelopes": envelopes,
        "baseline": baseline,
        "results_file": (attempt_dir / f"{attempt_id}-results.json").relative_to(repo_root).as_posix(),
    }
    state_path = attempt_dir / ATTEMPT_CURRENT_NAME
    state_error = create_attempt_state(state_path, state)
    if state_error:
        if state_error == "attempt slot already exists":
            return attempt_begin(mode, feature_dir_value, task_ids, selected_phase)
        return stop("attempt_state_write_failed", state_error)
    return 0, continuing({
        "ok": True,
        "action": "DISPATCH",
        "attempt_id": attempt_id,
        "task_ids": expected_ids,
        "worker_envelopes": envelopes,
        "state_file": state_path.relative_to(repo_root).as_posix(),
        "results_file": state["results_file"],
    }, "execute the returned envelope and finish its attempt")


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
    state_path = feature_dir / ATTEMPT_STATE_DIR / ATTEMPT_CURRENT_NAME
    try:
        state, state_error = load_attempt_state(state_path)
        if state_error or state is None:
            raise ValueError(state_error or "attempt state is unavailable")
        state.pop("_state_path", None)
        results_path = Path(results_file_value).resolve()
        results_path.relative_to(repo_root)
        if results_path.relative_to(repo_root).as_posix() != state.get("results_file"):
            raise ValueError("results file does not match attempt-owned result path")
        results = json.loads(results_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return stop("invalid_attempt_input", str(exc))
    if state.get("attempt_id") != attempt_id:
        return stop("invalid_attempt_state", "attempt ID does not own the current slot")
    state.pop("state_digest", None)
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
        envelope = next(
            item for item in state["worker_envelopes"]
            if item["task"]["task_id"] == result["task_id"]
        )
        errors = validate_worker_result(
            result,
            bool(state.get("verification_required", {}).get(result["task_id"])),
            str(envelope["task"]["verification"].get("mode", "pass")),
        )
        if errors:
            result_errors.append({"task_id": result["task_id"], "errors": errors})
    if result_errors:
        state["version"] = ATTEMPT_VERSION
        state["finish_status"] = "invalid_results"
        state["terminal_error"] = {"error": "invalid_worker_results", "results": result_errors}
        state_error = write_attempt_state(state_path, state)
        if state_error:
            return stop("attempt_state_update_failed", state_error)
        archive_error = archive_attempt_state(feature_dir, state)
        if archive_error:
            return stop("attempt_archive_failed", archive_error)
        return 2, {
            "ok": False,
            "action": "STOP",
            "terminal": True,
            "continuation_required": False,
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

    preserved_retry_sources: dict[str, str] = {}
    history_dir = feature_dir / ATTEMPT_STATE_DIR / ATTEMPT_HISTORY_DIR
    if history_dir.is_dir():
        for history_path in sorted(history_dir.glob("*.json")):
            history_relative = history_path.relative_to(repo_root).as_posix()
            if history_relative not in baseline:
                continue
            prior, prior_error = load_attempt_state(history_path)
            if prior_error or prior is None or prior.get("finish_status") != "worker_failed":
                continue
            prior_terminal = prior.get("terminal_error")
            if not isinstance(prior_terminal, dict):
                continue
            prior_observed = prior_terminal.get("observed_by_task", {})
            if not isinstance(prior_observed, dict):
                continue
            prior_write_paths = prior.get("write_paths", {})
            for task_id in state["task_ids"]:
                declared_paths = sorted(state["write_paths"][task_id])
                if (
                    task_id not in preserved_retry_sources
                    and sorted(prior_write_paths.get(task_id, [])) == declared_paths
                    and sorted(prior_observed.get(task_id, [])) == declared_paths
                ):
                    preserved_retry_sources[task_id] = prior["attempt_id"]

    completed_predecessor_sources: dict[str, list[str]] = {}
    task_records, task_errors = parse_tasks(feature_dir / "tasks.md")
    if not task_errors:
        record_indexes = {
            record["task_id"]: index for index, record in enumerate(task_records)
        }
        for task_id in state["task_ids"]:
            target_index = record_indexes.get(task_id)
            if target_index is None:
                continue
            predecessors = []
            for declared_path in sorted(state["write_paths"][task_id]):
                matching = [
                    record
                    for record in task_records[:target_index]
                    if record["status"] in {"x", "X"}
                    and not record["is_verification_only"]
                    and record["path"] == declared_path
                ]
                if not matching:
                    predecessors = []
                    break
                predecessor_id = matching[-1]["task_id"]
                if predecessor_id not in predecessors:
                    predecessors.append(predecessor_id)
            if predecessors:
                completed_predecessor_sources[task_id] = predecessors

    evidenced_preexisting_tasks = set(preserved_retry_sources) | set(
        completed_predecessor_sources
    )
    preexisting_reconciliation = (
        not unexpected
        and len(mismatches) == len(results)
        and evidenced_preexisting_tasks == set(state["task_ids"])
        and all(
            result.get("status") == "SUCCESS"
            and result.get("changed_files") == []
            and result.get("verification", {}).get("status") == "PASS"
            and observed_by_task[result["task_id"]] == []
            and bool(state["write_paths"][result["task_id"]])
            and all(path in baseline for path in state["write_paths"][result["task_id"]])
            and mismatch.get("task_id") == result["task_id"]
            and mismatch.get("reported") == []
            and mismatch.get("observed") == []
            and mismatch.get("error")
            == "successful write task did not change every declared write path"
            for result, mismatch in zip(results, mismatches)
        )
    )
    if preexisting_reconciliation:
        reconciliation_files = []
        reconciliation_commands = []
        for result in results:
            task_id = result["task_id"]
            declared_paths = sorted(state["write_paths"][task_id])
            if task_id in preserved_retry_sources:
                source_observation = (
                    "prior failed attempt "
                    + preserved_retry_sources[task_id]
                    + " preserved these paths"
                )
            else:
                source_observation = (
                    "completed predecessor tasks "
                    + ", ".join(completed_predecessor_sources[task_id])
                    + " owned these paths"
                )
            reconciliation_path = (
                feature_dir
                / ATTEMPT_STATE_DIR
                / f"{attempt_id}-reconcile-{task_id}.json"
            )
            reconciliation_payload = {
                "task_id": task_id,
                "status": "ALREADY_COMPLETE",
                "changed_files": [],
                "verification": result["verification"],
                "observed_state": (
                    source_observation
                    + "; they existed at attempt start and remained byte-identical: "
                    + ", ".join(declared_paths)
                ),
                "deviation": None,
            }
            payload_error = write_json_atomic(reconciliation_path, reconciliation_payload)
            if payload_error:
                return stop("reconciliation_payload_write_failed", payload_error)
            relative_path = reconciliation_path.relative_to(repo_root).as_posix()
            reconciliation_files.append(relative_path)
            reconciliation_commands.append([
                sys.executable,
                str(SCRIPT_DIR / "task_progress.py"),
                "reconcile",
                "--tasks",
                str(feature_dir / "tasks.md"),
                "--result-file",
                str(reconciliation_path),
            ])

        state["version"] = ATTEMPT_VERSION
        state["finish_status"] = "reconcile_candidate"
        state["reconciliation_files"] = reconciliation_files
        state["reconciliation_commands"] = reconciliation_commands
        state_error = write_attempt_state(state_path, state)
        if state_error:
            return stop("attempt_state_update_failed", state_error)
        archive_error = archive_attempt_state(feature_dir, state)
        if archive_error:
            return stop("attempt_archive_failed", archive_error)
        return 0, continuing({
            "ok": True,
            "action": "RECONCILE_PREEXISTING",
            "attempt_id": attempt_id,
            "task_ids": state["task_ids"],
            "observed_by_task": observed_by_task,
            "retry_sources": preserved_retry_sources,
            "completed_predecessor_sources": completed_predecessor_sources,
            "reconciliation_files": reconciliation_files,
            "reconciliation_commands": reconciliation_commands,
        }, "execute every reconciliation command in order, then call code_workflow.py next immediately")

    if unexpected or mismatches:
        terminal_error = {
            "error": "attempt_changes_rejected",
            "unexpected_changed_paths": unexpected,
            "result_mismatches": mismatches,
            "observed_by_task": observed_by_task,
        }
        state["version"] = ATTEMPT_VERSION
        state["finish_status"] = "rejected"
        state["terminal_error"] = terminal_error
        state_error = write_attempt_state(state_path, state)
        if state_error:
            return stop("attempt_state_update_failed", state_error)
        archive_error = archive_attempt_state(feature_dir, state)
        if archive_error:
            return stop("attempt_archive_failed", archive_error)
        diagnostic_state = (
            feature_dir / ATTEMPT_STATE_DIR / ATTEMPT_HISTORY_DIR / f"{attempt_id}.json"
        ).relative_to(repo_root).as_posix()
        return 2, {
            "ok": False,
            "action": "STOP",
            "terminal": True,
            "continuation_required": False,
            **terminal_error,
            "diagnostics": {
                "attempt_state": diagnostic_state,
                "worker_results": state["results_file"],
            },
            "operator_action": {
                "action": "RESTORE_REJECTED_CHANGES_OR_RESET",
                "restore_paths": sorted(set(unexpected)),
                "resume_command": "/order.code --resume",
                "reset_command": "/order.code --reset",
                "instructions": (
                    "Preserve diagnostics. Restore every unexpected path to its attempt-start state, "
                    "then run /order.code --resume. If exact restoration is unsafe or unknown, run "
                    "/order.code --reset; the explicit flag authorizes only its bounded rollback."
                ),
            },
        }
    failed = [
        {"task_id": item["task_id"], "status": item.get("status")}
        for item in results
        if item.get("status") != "SUCCESS"
    ]
    if failed:
        state["version"] = ATTEMPT_VERSION
        state["finish_status"] = "worker_failed"
        state["terminal_error"] = {
            "error": "worker_failed",
            "workers": failed,
            "observed_by_task": observed_by_task,
        }
        state_error = write_attempt_state(state_path, state)
        if state_error:
            return stop("attempt_state_update_failed", state_error)
        archive_error = archive_attempt_state(feature_dir, state)
        if archive_error:
            return stop("attempt_archive_failed", archive_error)
        return 2, {
            "ok": False,
            "action": "STOP",
            "terminal": True,
            "continuation_required": False,
            "error": "worker_failed",
            "workers": failed,
            "observed_by_task": observed_by_task,
        }
    state["version"] = ATTEMPT_VERSION
    state["finish_status"] = "accepted"
    state_error = write_attempt_state(state_path, state)
    if state_error:
        return stop("attempt_state_update_failed", state_error)
    return 0, continuing({
        "ok": True,
        "action": "READY_TO_VERIFY_AND_MARK",
        "attempt_id": attempt_id,
        "task_ids": state["task_ids"],
        "observed_by_task": observed_by_task,
        "results": results,
    }, "verify, mark, clean up, then call code_workflow.py next")


def attempt_cleanup(feature_dir_value: str, attempt_id: str) -> tuple[int, dict[str, Any]]:
    """Remove a closed successful attempt after every owned task is marked."""
    repo_root = get_repo_root().resolve()
    try:
        feature_dir = safe_feature_dir(feature_dir_value, repo_root)
    except ValueError as exc:
        return stop("invalid_feature_dir", str(exc))
    if not attempt_id or any(char not in "0123456789abcdef" for char in attempt_id):
        return stop("invalid_attempt_id", "attempt ID must be lowercase hexadecimal")

    state_path = feature_dir / ATTEMPT_STATE_DIR / ATTEMPT_CURRENT_NAME
    state, state_error = load_attempt_state(state_path)
    if state_error or state is None:
        return stop("invalid_attempt_state", state_error or "attempt state is unavailable")
    state.pop("_state_path", None)
    if state.get("attempt_id") != attempt_id:
        return stop("invalid_attempt_state", "attempt ID does not own the current slot")
    if state.get("finish_status") != "accepted":
        return stop(
            "attempt_not_accepted",
            "preserving attempt because attempt-finish did not accept it",
        )

    records, errors = parse_tasks(feature_dir / "tasks.md")
    if errors:
        return stop("invalid_tasks", "; ".join(errors), route="/order.tasks")
    statuses = {record["task_id"]: record["status"] for record in records}
    unmarked = [task_id for task_id in state.get("task_ids", []) if statuses.get(task_id) not in {"x", "X"}]
    if unmarked:
        return stop(
            "attempt_not_marked",
            f"preserving attempt because tasks are not marked [X]: {', '.join(unmarked)}",
        )

    results_value = state.get("results_file")
    if not isinstance(results_value, str):
        return stop("invalid_attempt_state", "attempt results path is invalid")
    results_path = (repo_root / results_value).resolve()
    try:
        results_path.relative_to(repo_root)
    except ValueError:
        return stop("invalid_attempt_state", "attempt results path escapes repository root")

    removed = []
    try:
        if results_path.is_file() or results_path.is_symlink():
            results_path.unlink()
            removed.append(results_value)
        state_path.unlink()
        removed.append(state_path.relative_to(repo_root).as_posix())
        attempt_dir = state_path.parent
        try:
            attempt_dir.rmdir()
        except OSError:
            pass
    except OSError as exc:
        return stop("attempt_cleanup_failed", str(exc))
    return 0, continuing({
        "ok": True,
        "action": "ATTEMPT_CLEANED",
        "attempt_id": attempt_id,
        "removed": removed,
    }, "call code_workflow.py next immediately")


def attempt_recover(feature_dir_value: str) -> tuple[int, dict[str, Any]]:
    """Return or execute the sole legal recovery for the singleton attempt slot."""
    repo_root = get_repo_root().resolve()
    try:
        feature_dir = safe_feature_dir(feature_dir_value, repo_root)
    except ValueError as exc:
        return stop("invalid_feature_dir", str(exc))
    states, errors = attempt_inventory(feature_dir)
    if errors:
        return invalid_attempt_inventory_stop(feature_dir, errors)
    if not states:
        return 0, continuing(
            {"ok": True, "action": "NO_OPEN_ATTEMPT"},
            "retry the interrupted code_workflow command immediately",
        )
    state = states[0]
    status = state.get("finish_status")
    if status is None:
        envelopes = state.get("worker_envelopes")
        if not isinstance(envelopes, list) or not envelopes:
            return stop("invalid_attempt_state", "current attempt has no resumable envelopes")
        return 0, continuing({
            "ok": True,
            "action": "RESUME_ATTEMPT",
            "attempt_id": state["attempt_id"],
            "task_ids": state["task_ids"],
            "worker_envelopes": envelopes,
            "state_file": state["_state_path"].relative_to(repo_root).as_posix(),
            "results_file": state["results_file"],
        }, "execute the original envelope and call attempt-finish")
    if status == "accepted":
        return 0, continuing({
            "ok": True,
            "action": "MARK_AND_CLEAN",
            "attempt_id": state["attempt_id"],
            "task_ids": state["task_ids"],
            "results_file": state["results_file"],
        }, "verify and mark every result, then call attempt-cleanup")
    archive_error = archive_attempt_state(feature_dir, state)
    if archive_error:
        return stop("attempt_archive_failed", archive_error)
    return 0, continuing({
        "ok": True,
        "action": "ATTEMPT_ARCHIVED",
        "attempt_id": state["attempt_id"],
        "finish_status": status,
    }, "retry the interrupted code_workflow command immediately")


def attempt_reset(feature_dir_value: str, apply: bool) -> tuple[int, dict[str, Any]]:
    """Preview or remove only feature-local attempt runtime state."""
    repo_root = get_repo_root().resolve()
    try:
        feature_dir = safe_feature_dir(feature_dir_value, repo_root)
    except ValueError as exc:
        return stop("invalid_feature_dir", str(exc))
    attempt_dir = feature_dir / ATTEMPT_STATE_DIR
    paths = sorted(
        (path for path in attempt_dir.rglob("*") if path.is_file() or path.is_symlink()),
        key=lambda path: path.as_posix(),
    ) if attempt_dir.is_dir() else []
    relative = [path.relative_to(repo_root).as_posix() for path in paths]
    if not apply:
        return 0, {
            "ok": True,
            "action": "RESET_PREVIEW",
            "terminal": True,
            "continuation_required": False,
            "delete": relative,
            "apply_command": [
                sys.executable,
                str(SCRIPT_DIR / "code_workflow.py"),
                "attempt-reset",
                "--feature-dir",
                str(feature_dir),
                "--apply",
            ],
        }
    try:
        for path in paths:
            path.unlink()
        if attempt_dir.is_dir():
            for directory in sorted(
                (path for path in attempt_dir.rglob("*") if path.is_dir()),
                key=lambda path: len(path.parts),
                reverse=True,
            ):
                directory.rmdir()
            attempt_dir.rmdir()
    except OSError as exc:
        return stop("attempt_reset_failed", str(exc))
    return 0, {
        "ok": True,
        "action": "ATTEMPT_STATE_RESET",
        "terminal": True,
        "continuation_required": False,
        "deleted": relative,
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
    blocking, inventory_errors = blocking_attempts(feature_dir)
    if inventory_errors:
        return invalid_attempt_inventory_stop(feature_dir, inventory_errors)
    if blocking:
        state = blocking[0]
        rc, payload = stop(
            "open_attempt_boundary",
            "cannot finish order.code while an attempt is active or awaiting mark/cleanup",
        )
        payload["attempt"] = {
            "attempt_id": state["attempt_id"],
            "task_ids": state.get("task_ids", []),
            "finish_status": state.get("finish_status") or "active",
        }
        payload["boundary_recovery"] = {
            "action": "RECOVER_CURRENT_ATTEMPT",
            "command": [
                sys.executable,
                str(SCRIPT_DIR / "code_workflow.py"),
                "attempt-recover",
                "--feature-dir",
                str(feature_dir),
            ],
        }
        payload["next_action"] = "execute boundary_recovery.command, obey its action, then retry finish"
        return rc, payload
    tasks = feature_dir / "tasks.md"
    records, errors = parse_tasks(tasks)
    if errors:
        return stop("invalid_tasks", "; ".join(errors), route="/order.tasks")
    unchecked = [record["task_id"] for record in records if record["status"] == " "]
    if mode in FULL_MODES and outcome == "COMPLETE" and unchecked:
        return 1, continuing({
            "ok": False,
            "action": "CONTINUE",
            "error": "tasks_incomplete",
            "first_unchecked": unchecked[0],
            "unchecked": len(unchecked),
        }, "return to Step 4 at first_unchecked immediately")
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
            payload.update({
                "ok": False,
                "action": "STOP",
                "terminal": True,
                "continuation_required": False,
                "error": "status_update_failed",
            })
            return status_rc, payload
        return 0, payload

    if outcome == "HALTED":
        return update_status({
            "ok": True,
            "action": "HALTED",
            "terminal": True,
            "continuation_required": False,
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
            "terminal": True,
            "continuation_required": False,
            "error": "mechanism_coverage",
            "route": "/order.tasks or /order.spec",
            "details": trace,
        }
        status_rc, payload = update_status(payload)
        return trace_rc if status_rc == 0 else status_rc, payload
    return update_status({
        "ok": True,
        "action": outcome,
        "terminal": True,
        "continuation_required": False,
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

    attempt_cleanup_parser = subparsers.add_parser("attempt-cleanup")
    attempt_cleanup_parser.add_argument("--feature-dir", required=True)
    attempt_cleanup_parser.add_argument("--attempt-id", required=True)

    attempt_recover_parser = subparsers.add_parser("attempt-recover")
    attempt_recover_parser.add_argument("--feature-dir", required=True)

    attempt_reset_parser = subparsers.add_parser("attempt-reset")
    attempt_reset_parser.add_argument("--feature-dir", required=True)
    attempt_reset_parser.add_argument("--apply", action="store_true")

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
    elif args.command == "attempt-cleanup":
        rc, payload = attempt_cleanup(args.feature_dir, args.attempt_id)
    elif args.command == "attempt-recover":
        rc, payload = attempt_recover(args.feature_dir)
    elif args.command == "attempt-reset":
        rc, payload = attempt_reset(args.feature_dir, args.apply)
    else:
        rc, payload = finish(args.mode, args.feature_dir, args.outcome)
    emit(payload)
    return rc


if __name__ == "__main__":
    sys.exit(main())
