#!/usr/bin/env python3
"""common.py — shared functions for OrderSpec scripts.

Portable: Python 3 standard library only. No external dependencies.
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path


# ── repository root ──────────────────────────────────────────────────────────

def script_dir():
    """Return the directory containing this script."""
    return Path(__file__).resolve().parent


def find_orderspec_root(start_dir=None):
    """Search upward for a directory containing `.orderspec/`.

    Returns the Path or None if not found.

    NOTE: Feature-level state directories are named `.specify-state` (not
    `.orderspec`) precisely so that this function does not mistake a feature
    directory for the repo root. Do not rename feature state dirs back to
    `.orderspec` — it will break root resolution.
    """
    if start_dir is None:
        start_dir = Path.cwd()
    else:
        start_dir = Path(start_dir).resolve()

    current = start_dir
    prev = None
    while True:
        if (current / ".orderspec").is_dir():
            return current
        if current == current.parent or current == prev:
            return None
        prev = current
        current = current.parent


def get_repo_root():
    """Get repository root.

    Priority:
      1. Search upward for a directory containing `.orderspec/`.
      2. `ORDERSPEC_ROOT` environment variable.
      3. Two levels up from this script's location
         (repo/.orderspec/scripts/ → repo).
    """
    root = find_orderspec_root()
    if root is not None:
        return root

    env_root = os.environ.get("ORDERSPEC_ROOT")
    if env_root:
        return Path(env_root).resolve()

    return script_dir().parent.parent


# ── feature state ────────────────────────────────────────────────────────────

def get_current_branch():
    """Return the current feature name from `SPECIFY_FEATURE` env var,
    or empty string if not set."""
    return os.environ.get("SPECIFY_FEATURE", "")


def read_feature_json_feature_directory(repo_root):
    """Safely read `.orderspec/feature.json`'s `feature_directory` value.

    Returns the raw value (possibly relative) or empty string if the file
    is missing, unparseable, or does not contain the key.
    Always returns a string — never raises on parse failure."""
    fj = Path(repo_root) / ".orderspec" / "feature.json"
    if not fj.exists():
        return ""
    try:
        with open(fj, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("feature_directory") or ""
    except (json.JSONDecodeError, OSError, KeyError):
        return ""


def persist_feature_json(repo_root, feature_dir_value):
    """Persist `feature_directory` to `.orderspec/feature.json` atomically.

    Writes only when the file is missing or the value differs from what's
    stored. Accepts the raw (possibly relative) path — callers should pass
    the original user-supplied value, not the normalised absolute path.
    Uses temp-file + rename for atomicity (safe under concurrent invocations).
    """
    repo_root = Path(repo_root)
    fj = repo_root / ".orderspec" / "feature.json"

    # Strip repo_root prefix if the value is absolute and under repo_root
    try:
        feature_dir_rel = str(Path(feature_dir_value).relative_to(repo_root))
    except ValueError:
        feature_dir_rel = feature_dir_value

    # Read current value — skip write when unchanged
    current_val = read_feature_json_feature_directory(repo_root)
    if current_val == feature_dir_rel:
        return

    # Ensure .orderspec/ directory exists
    fj.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write via temp file + rename
    tmp = fj.with_suffix(f".tmp.{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"feature_directory": feature_dir_rel}, f)
        f.write("\n")
    shutil.move(str(tmp), str(fj))


# ── feature paths ────────────────────────────────────────────────────────────

def get_feature_paths():
    """Resolve all feature paths as a dict.

    Resolution priority for the feature directory:
      1. `SPECIFY_FEATURE_DIRECTORY` env var (explicit override)
      2. `.orderspec/feature.json` `feature_directory` key
      3. Error

    Returns a dict with keys:
      REPO_ROOT, CURRENT_BRANCH, FEATURE_DIR, FEATURE_SPEC,
      IMPL_PLAN, TASKS, RESEARCH, DATA_MODEL, QUICKSTART, CONTRACTS_DIR

    Raises RuntimeError if the feature directory cannot be resolved."""
    repo_root = get_repo_root()
    current_branch = get_current_branch()

    specify_feature_dir = os.environ.get("SPECIFY_FEATURE_DIRECTORY")

    if specify_feature_dir:
        feature_dir = Path(specify_feature_dir)
        if not feature_dir.is_absolute():
            feature_dir = repo_root / feature_dir
        feature_dir = feature_dir.resolve()
        # Persist to feature.json so future sessions without the env var work
        persist_feature_json(repo_root, specify_feature_dir)
    else:
        fd = read_feature_json_feature_directory(repo_root)
        if fd:
            feature_dir = Path(fd)
            if not feature_dir.is_absolute():
                feature_dir = repo_root / feature_dir
            feature_dir = feature_dir.resolve()
        else:
            raise RuntimeError(
                "Feature directory not found. Set SPECIFY_FEATURE_DIRECTORY or "
                "ensure .orderspec/feature.json contains feature_directory."
            )

    return {
        "REPO_ROOT": str(repo_root),
        "CURRENT_BRANCH": current_branch,
        "FEATURE_DIR": str(feature_dir),
        "FEATURE_SPEC": str(feature_dir / "spec.md"),
        "IMPL_PLAN": str(feature_dir / "plan.md"),
        "TASKS": str(feature_dir / "tasks.md"),
        "RESEARCH": str(feature_dir / "research.md"),
        "DATA_MODEL": str(feature_dir / "data-model.md"),
        "QUICKSTART": str(feature_dir / "quickstart.md"),
        "CONTRACTS_DIR": str(feature_dir / "contracts"),
    }


# ── template resolution ──────────────────────────────────────────────────────

def resolve_template(template_name, repo_root):
    """Resolve a template name to a file path using the priority stack:
      1. `.orderspec/templates/overrides/`
      2. `.orderspec/presets/<preset-id>/templates/` (sorted by `.registry` priority)
      3. `.orderspec/extensions/<ext-id>/templates/`
      4. `.orderspec/templates/` (core)

    Returns the path string or None if not found.

    Emits a stderr WARNING when falling back to alphabetical preset scan
    (i.e., when .registry is missing or unparseable)."""
    repo_root = Path(repo_root)
    base = repo_root / ".orderspec" / "templates"

    # Priority 1: Project overrides
    override = base / "overrides" / f"{template_name}.md"
    if override.exists():
        return str(override)

    # Priority 2: Installed presets (sorted by priority from .registry)
    presets_dir = repo_root / ".orderspec" / "presets"
    if presets_dir.is_dir():
        registry_file = presets_dir / ".registry"
        used_registry = False

        if registry_file.exists():
            try:
                with open(registry_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                presets = data.get("presets", {})
                sorted_presets = sorted(
                    presets.items(),
                    key=lambda x: (
                        x[1].get("priority", 10) if isinstance(x[1], dict) else 10
                    ),
                )
                for preset_id, meta in sorted_presets:
                    if isinstance(meta, dict) and meta.get("enabled", True) is False:
                        continue
                    candidate = (
                        presets_dir / preset_id / "templates" / f"{template_name}.md"
                    )
                    if candidate.exists():
                        return str(candidate)
                used_registry = True
            except (json.JSONDecodeError, OSError):
                pass

        # Fallback: alphabetical directory scan (no registry or parse failed)
        if not used_registry:
            print(
                "WARNING: .registry missing or unparseable, "
                "falling back to alphabetical preset scan",
                file=sys.stderr,
            )
            for preset in sorted(presets_dir.iterdir()):
                if not preset.is_dir():
                    continue
                candidate = preset / "templates" / f"{template_name}.md"
                if candidate.exists():
                    return str(candidate)

    # Priority 3: Extension-provided templates
    ext_dir = repo_root / ".orderspec" / "extensions"
    if ext_dir.is_dir():
        for ext in sorted(ext_dir.iterdir()):
            if not ext.is_dir():
                continue
            # Skip hidden directories (e.g. .backup, .cache)
            if ext.name.startswith("."):
                continue
            candidate = ext / "templates" / f"{template_name}.md"
            if candidate.exists():
                return str(candidate)

    # Priority 4: Core templates
    core = base / f"{template_name}.md"
    if core.exists():
        return str(core)

    return None