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


# ── canonical OrderSpec paths ────────────────────────────────────────────────

ORDERSPEC_DIR = Path(".orderspec")

FRAMEWORK_DIR = ORDERSPEC_DIR / "framework"
FRAMEWORK_TEMPLATES_DIR = FRAMEWORK_DIR / "templates"
FRAMEWORK_PROTOCOLS_DIR = FRAMEWORK_DIR / "protocols"
FRAMEWORK_SCHEMAS_DIR = FRAMEWORK_DIR / "schemas"
FRAMEWORK_RULES = FRAMEWORK_DIR / "orderspec-rules.md"

ORDERSPEC_JSON = ORDERSPEC_DIR / "orderspec.json"

CONFIG_DIR = ORDERSPEC_DIR / "config"
TEMPLATE_OVERRIDES_DIR = CONFIG_DIR / "templates" / "overrides"
HOOKS_CONFIG = CONFIG_DIR / "hooks.yml"
STATE_DIR = ORDERSPEC_DIR / "state"
ACTIVE_FEATURE_STATE = STATE_DIR / "active-feature.json"

# All generated artifacts live under .orderspec/. Nothing is written to the
# repository root.
CONTRACTS_DIR = ORDERSPEC_DIR / "contracts"
CONTRACT_FILES = {
    "constitution": CONTRACTS_DIR / "constitution.md",
    "stack": CONTRACTS_DIR / "stack.md",
    "architecture": CONTRACTS_DIR / "architecture.md",
    "conventions": CONTRACTS_DIR / "conventions.md",
}

FEATURES_DIR = ORDERSPEC_DIR / "features"
SPECS_ROOT = FEATURES_DIR

SCRIPTS_DIR = ORDERSPEC_DIR / "scripts"

# Presets are kept as an optional compatibility layer. Extensions are not.
PRESETS_DIR = ORDERSPEC_DIR / "presets"


# ── repository root ──────────────────────────────────────────────────────────

def script_dir():
    """Return the directory containing this script."""
    return Path(__file__).resolve().parent


def find_orderspec_root(start_dir=None):
    """Search upward for a directory containing `.orderspec/`.

    Returns the Path or None if not found.

    NOTE: Feature-level state directories are named `.state` (not
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
        if (current / ORDERSPEC_DIR).is_dir():
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
         (repo/.orderspec/framework/scripts/ → repo).
    """
    root = find_orderspec_root()
    if root is not None:
        return root

    env_root = os.environ.get("ORDERSPEC_ROOT")
    if env_root:
        return Path(env_root).resolve()

    return script_dir().parent.parent


# ── framework metadata ───────────────────────────────────────────────────────

def load_orderspec_meta(repo_root=None):
    """Load and return the parsed contents of orderspec.json.

    Returns a dict. Raises FileNotFoundError if the file is missing,
    ValueError if it is not valid JSON or not a dict.
    """
    root = Path(repo_root) if repo_root else get_repo_root()
    path = root / ORDERSPEC_JSON
    if not path.exists():
        raise FileNotFoundError(f"orderspec.json not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"orderspec.json invalid: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("orderspec.json must be a JSON object")
    return data


def get_framework_version(repo_root=None):
    """Return framework_version string from orderspec.json.

    Raises FileNotFoundError / ValueError on missing or malformed file.
    Raises KeyError if framework_version is absent.
    """
    meta = load_orderspec_meta(repo_root)
    version = meta.get("framework_version")
    if not isinstance(version, str) or not version:
        raise KeyError("framework_version missing or empty in orderspec.json")
    return version


def get_schema_version(schema_name, repo_root=None):
    """Return an integer schema version for the given schema_name.

    schema_name must be a key in orderspec.json → schema_versions
    (e.g. "frontmatter", "artifacts", "lifecycle", "traceability").

    Raises FileNotFoundError / ValueError on missing or malformed file.
    Raises KeyError if schema_name is absent.
    """
    meta = load_orderspec_meta(repo_root)
    versions = meta.get("schema_versions")
    if not isinstance(versions, dict):
        raise KeyError("schema_versions missing or not an object in orderspec.json")
    if schema_name not in versions:
        raise KeyError(
            f"Schema '{schema_name}' not in orderspec.json schema_versions. "
            f"Available: {sorted(versions.keys())}"
        )
    return versions[schema_name]


# ── feature state ────────────────────────────────────────────────────────────

def get_current_branch():
    """Return the current feature name from `SPECIFY_FEATURE` env var,
    or empty string if not set."""
    return os.environ.get("SPECIFY_FEATURE", "")


def active_feature_state_path(repo_root):
    """Return the canonical active feature state path."""
    return Path(repo_root) / ACTIVE_FEATURE_STATE


def read_active_feature_state(repo_root):
    """Safely read `.orderspec/state/active-feature.json`.

    Returns a dict. If the file is missing, unparseable, or not a JSON object,
    returns an empty dict. Never raises on parse failure.
    """
    state_file = active_feature_state_path(repo_root)
    if not state_file.exists():
        return {}

    try:
        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}
    except (json.JSONDecodeError, OSError):
        return {}


def read_active_feature_state_feature_directory(repo_root):
    """Read `feature_directory` from `.orderspec/state/active-feature.json`.

    Returns the raw value, possibly relative, or an empty string if unavailable.
    Always returns a string.
    """
    data = read_active_feature_state(repo_root)
    value = data.get("feature_directory") or ""
    return value if isinstance(value, str) else ""


def persist_active_feature_state(repo_root, feature_dir_value):
    """Persist the active feature directory to `.orderspec/state/active-feature.json`.

    Writes only when relevant values differ. Accepts the raw possibly-relative
    path; callers should pass the original user-supplied value when available.

    Existing state keys are preserved. This function updates at least:

    - `feature_directory`
    - `spec_file`

    Uses temp-file + rename for atomicity.
    """
    repo_root = Path(repo_root)
    state_file = active_feature_state_path(repo_root)

    # Strip repo_root prefix if the value is absolute and under repo_root.
    try:
        feature_dir_rel = str(Path(feature_dir_value).relative_to(repo_root))
    except ValueError:
        feature_dir_rel = feature_dir_value

    spec_file_rel = str(Path(feature_dir_rel) / "spec.md")

    current = read_active_feature_state(repo_root)
    if not isinstance(current, dict):
        current = {}

    next_state = dict(current)
    next_state["feature_directory"] = feature_dir_rel
    next_state["spec_file"] = spec_file_rel

    if current == next_state:
        return

    state_file.parent.mkdir(parents=True, exist_ok=True)

    tmp = state_file.with_suffix(f".tmp.{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(next_state, f, indent=2, ensure_ascii=False)
        f.write("\n")

    shutil.move(str(tmp), str(state_file))


def read_feature_json_feature_directory(repo_root):
    """Compatibility wrapper for legacy callers.

    Prefer `read_active_feature_state_feature_directory()`.
    Canonical active feature state is stored in `ACTIVE_FEATURE_STATE`.
    """
    return read_active_feature_state_feature_directory(repo_root)


def persist_feature_json(repo_root, feature_dir_value):
    """Compatibility wrapper for legacy callers.

    Prefer `persist_active_feature_state()`.
    Canonical active feature state is stored in `ACTIVE_FEATURE_STATE`.
    """
    persist_active_feature_state(repo_root, feature_dir_value)


# ── feature paths ────────────────────────────────────────────────────────────

def get_feature_paths(persist_active_feature=True, feature_directory=None):
    """Resolve all feature paths as a dict.

    Resolution priority for the feature directory:
      1. explicit ``feature_directory`` argument;
      2. `SPECIFY_FEATURE_DIRECTORY` env var (legacy explicit override);
      3. `.orderspec/state/active-feature.json` `feature_directory` key;
      4. Error.

    Returns a dict with keys:
      REPO_ROOT, CURRENT_BRANCH, FEATURE_DIR, FEATURE_SPEC,
      IMPL_PLAN, TASKS, DATA_MODEL, QUICKSTART, CONTRACTS_DIR

    Raises RuntimeError if the feature directory cannot be resolved.
    """
    repo_root = get_repo_root()
    current_branch = get_current_branch()

    specify_feature_dir = feature_directory or os.environ.get("SPECIFY_FEATURE_DIRECTORY")

    if specify_feature_dir:
        feature_dir = Path(specify_feature_dir)
        if not feature_dir.is_absolute():
            feature_dir = repo_root / feature_dir
        feature_dir = feature_dir.resolve()

        # Persist only when the caller explicitly owns active-feature selection.
        # Gate/setup callers pass persist_active_feature=False.
        if persist_active_feature:
            persist_active_feature_state(repo_root, specify_feature_dir)
    else:
        fd = read_active_feature_state_feature_directory(repo_root)
        if fd:
            feature_dir = Path(fd)
            if not feature_dir.is_absolute():
                feature_dir = repo_root / feature_dir
            feature_dir = feature_dir.resolve()
        else:
            raise RuntimeError(
                "Feature directory not found. Set SPECIFY_FEATURE_DIRECTORY or "
                "ensure .orderspec/state/active-feature.json contains feature_directory."
            )

    return {
        "REPO_ROOT": str(repo_root),
        "CURRENT_BRANCH": current_branch,
        "FEATURE_DIR": str(feature_dir),
        "FEATURE_SPEC": str(feature_dir / "spec.md"),
        "IMPL_PLAN": str(feature_dir / "plan.md"),
        "TASKS": str(feature_dir / "tasks.md"),
        "DATA_MODEL": str(feature_dir / "data-model.md"),
        "QUICKSTART": str(feature_dir / "quickstart.md"),
        "CONTRACTS_DIR": str(feature_dir / "contracts"),
    }


# ── template resolution ──────────────────────────────────────────────────────

def resolve_template(template_name, repo_root):
    """Resolve a template name to a file path using the priority stack:

      1. `.orderspec/config/templates/overrides/`
      2. `.orderspec/presets/<preset-id>/templates/`
         sorted by `.registry` priority when available
      3. `.orderspec/framework/templates/` core templates

    Extension-provided templates are intentionally unsupported.

    Returns the path string or None if not found.

    Emits a stderr WARNING when falling back to alphabetical preset scan
    (i.e., when `.registry` is missing or unparseable).
    """
    repo_root = Path(repo_root)

    # Priority 1: Project overrides.
    override = repo_root / TEMPLATE_OVERRIDES_DIR / f"{template_name}.md"
    if override.exists():
        return str(override)

    # Priority 2: Installed presets (sorted by priority from .registry).
    presets_dir = repo_root / PRESETS_DIR
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

        # Fallback: alphabetical directory scan (no registry or parse failed).
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

    # Priority 3: Core framework templates.
    core = repo_root / FRAMEWORK_TEMPLATES_DIR / f"{template_name}.md"
    if core.exists():
        return str(core)

    return None
