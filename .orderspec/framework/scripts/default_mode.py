#!/usr/bin/env python3
"""Resolve the safest obvious mode for an argument-free OrderSpec command.

Explicit controls and semantic input remain owned by command_input.py and the
command prompt. This resolver handles only the empty-input default from
observable pipeline state, so authoring prompts do not invent different STOP
rules for the same state.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


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
CHECK_COMMANDS = {
    "order.spec-check",
    "order.plan-check",
    "order.tasks-check",
    "order.code-check",
}
TASK_RE = re.compile(r"^- \[(?P<status>[ xX])\] T\d{3}\b", re.MULTILINE)


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def safe_feature_dir(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value).resolve()
    if not path.is_dir() or ".orderspec" not in path.parts or "features" not in path.parts:
        raise ValueError("feature directory must be an existing .orderspec/features directory")
    return path


def open_feedback(feature: Path | None, target: str) -> list[str]:
    if feature is None:
        return []
    result: list[str] = []
    for path in sorted((feature / ".state" / "feedback").glob("FB-*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid feedback report {path}: {exc}") from exc
        if value.get("status") == "open" and value.get("target") == target:
            result.append(str(value.get("id", path.stem)))
    return result


def newer(left: Path, right: Path) -> bool:
    return left.is_file() and right.is_file() and left.stat().st_mtime_ns > right.stat().st_mtime_ns


def task_progress(feature: Path | None) -> tuple[int, int]:
    if feature is None:
        return 0, 0
    tasks = feature / "tasks.md"
    if not tasks.is_file():
        return 0, 0
    matches = list(TASK_RE.finditer(tasks.read_text(encoding="utf-8")))
    completed = sum(match.group("status").lower() == "x" for match in matches)
    return completed, len(matches) - completed


def resolve(command: str, feature: Path | None, semantic_input: str) -> dict[str, Any]:
    if command not in COMMANDS:
        raise ValueError(f"unsupported command: {command}")
    if semantic_input.strip():
        return {
            "ok": True,
            "action": "EXPLICIT_INPUT",
            "mode": None,
            "reason": "non-empty semantic input owns mode selection",
            "ask_user": False,
        }
    if command in CHECK_COMMANDS:
        return {"ok": True, "action": "RUN", "mode": "CHECK", "reason": "check commands have one obvious read-only mode", "ask_user": False}
    if command == "order.feature":
        return {"ok": True, "action": "RUN", "mode": "INSPECT", "reason": "empty input means report current selection and candidates", "ask_user": False}
    if command == "order.bootstrap":
        return {"ok": True, "action": "DEFER", "mode": None, "reason": "bootstrap_workflow.py owns Init versus Refine", "ask_user": False}
    if command == "order.code":
        return {"ok": True, "action": "RUN", "mode": "RESUME", "reason": "resume is the safe implementation default", "ask_user": False}

    artifact_name = {
        "order.spec": "spec.md",
        "order.code-to-spec": "spec.md",
        "order.plan": "plan.md",
        "order.tasks": "tasks.md",
    }[command]
    artifact = feature / artifact_name if feature else None
    exists = bool(artifact and artifact.is_file())
    feedback = open_feedback(feature, command)
    completed, unchecked = task_progress(feature)
    base = {
        "ok": True,
        "feature_dir": str(feature) if feature else None,
        "artifact": str(artifact) if artifact else None,
        "artifact_exists": exists,
        "open_feedback": feedback,
        "completed_tasks": completed,
        "unchecked_tasks": unchecked,
        "ask_user": False,
    }

    if command == "order.spec":
        if not exists:
            return {**base, "action": "ASK", "mode": None, "reason": "a new specification needs a feature description", "ask_user": True}
        reason = "open owner feedback selects surgical refinement" if feedback else "the active specification is the obvious refinement target"
        return {**base, "action": "RUN", "mode": "REFINE", "reason": reason}

    if command == "order.code-to-spec":
        plan_exists = bool(feature and (feature / "plan.md").is_file())
        if exists and plan_exists:
            return {**base, "action": "RUN", "mode": "REFINE", "reason": "the active plan supplies a bounded existing code scope"}
        return {**base, "action": "ASK", "mode": None, "reason": "no bounded code scope can be inferred safely", "ask_user": True}

    if command == "order.plan":
        if not exists:
            return {**base, "action": "RUN", "mode": "GENERATE", "reason": "plan.md is absent"}
        spec = feature / "spec.md" if feature else Path("spec.md")
        stale = newer(spec, artifact) if artifact else False
        return {
            **base,
            "action": "RUN",
            "mode": "RECONCILE",
            "reason": "open owner feedback" if feedback else ("spec.md is newer than plan.md" if stale else "inspect the current plan and keep it unchanged when already aligned"),
            "upstream_newer": stale,
            "classify_impact_before_write": completed > 0,
        }

    if command == "order.tasks":
        if not exists:
            return {**base, "action": "RUN", "mode": "GENERATE", "reason": "tasks.md is absent"}
        plan = feature / "plan.md" if feature else Path("plan.md")
        spec = feature / "spec.md" if feature else Path("spec.md")
        plan_newer = newer(plan, artifact) if artifact else False
        spec_newer = newer(spec, artifact) if artifact else False
        stale = plan_newer or spec_newer
        mode = "REFINE" if feedback or stale else "INSPECT"
        stale_reason = "plan.md is newer than tasks.md" if plan_newer else "spec.md has newer contract detail"
        return {
            **base,
            "action": "RUN",
            "mode": mode,
            "reason": "open owner feedback" if feedback else (stale_reason if stale else "preserve the existing work order and inspect current progress"),
            "upstream_newer": stale,
        }

    raise AssertionError(command)


def main() -> int:
    parser = argparse.ArgumentParser(description="OrderSpec empty-input default mode resolver")
    parser.add_argument("resolve", nargs="?")
    parser.add_argument("--command", required=True, choices=sorted(COMMANDS))
    parser.add_argument("--feature-dir")
    parser.add_argument("--semantic-input", default="")
    args = parser.parse_args()
    try:
        feature = safe_feature_dir(args.feature_dir)
        emit(resolve(args.command, feature, args.semantic_input))
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
