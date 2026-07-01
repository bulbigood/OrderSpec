#!/usr/bin/env python3
"""feature_spec.py — deterministic feature spec directory allocator.

Portable: Python 3 standard library only. No external dependencies.

This script owns only mechanical feature-directory allocation for /order.spec.

It intentionally does NOT:
- write spec.md content;
- copy templates;
- update .orderspec/state/active-feature.json;
- initialize traceability state;
- inspect or mutate project contracts.

Canonical mapping:
- slug:              user-auth
- feature number:    001
- feature_id:        FEAT-001-user-auth
- feature_directory: .orderspec/features/001-user-auth
- spec_file:         .orderspec/features/001-user-auth/spec.md

/order.spec remains the owner of spec.md contract content.
active_feature.py remains the owner of active-feature runtime state.
traceability.py remains the owner of feature .orderspec-state traceability files.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any


from common import SPECS_ROOT

DEFAULT_SPECS_ROOT = str(SPECS_ROOT)

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FEATURE_DIR_RE = re.compile(r"^([0-9]{3})-([a-z0-9]+(?:-[a-z0-9]+)*)$")
FEATURE_ID_RE = re.compile(r"^FEAT-[0-9]{3}-[a-z0-9]+(?:-[a-z0-9]+)*$")


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def posix(path: Path | str) -> str:
    return Path(path).as_posix() if isinstance(path, Path) else str(path).replace("\\", "/")


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


def safe_rel(value: str) -> bool:
    if not isinstance(value, str) or not value:
        return False

    p = Path(value)

    if p.is_absolute():
        return False

    if value.startswith("~"):
        return False

    if any(part in {"", ".."} for part in p.parts):
        return False

    return True


def slugify(value: str) -> str:
    """Convert arbitrary human text into OrderSpec slug form.

    Rules:
    - lowercase;
    - replace non-alphanumeric runs with "-";
    - trim leading/trailing "-";
    - collapse repeated "-";
    - max 64 chars, trimmed at a token boundary when possible.
    """
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    text = text.strip("-")

    if len(text) <= 64:
        return text

    text = text[:64].rstrip("-")

    # Prefer not to cut in the middle of a token if a reasonable boundary exists.
    boundary = text.rfind("-")
    if boundary >= 16:
        text = text[:boundary]

    return text.strip("-")


def validate_slug(slug: str) -> list[str]:
    errors: list[str] = []

    if not slug:
        errors.append("slug is empty")

    if len(slug) > 64:
        errors.append("slug must be at most 64 characters")

    if not SLUG_RE.match(slug):
        errors.append("slug must match lowercase kebab-case: [a-z0-9]+(-[a-z0-9]+)*")

    return errors


def validate_specs_root(value: str) -> list[str]:
    errors: list[str] = []

    if not safe_rel(value):
        errors.append("specs_root must be a safe relative path")

    return errors


def feature_id_for(number: int, slug: str) -> str:
    return f"FEAT-{number:03d}-{slug}"


def feature_dir_for(specs_root: str, number: int, slug: str) -> Path:
    return Path(specs_root) / f"{number:03d}-{slug}"


def discover_used_numbers(root: Path, specs_root: str) -> set[int]:
    abs_specs_root = root / specs_root
    used: set[int] = set()

    if not abs_specs_root.exists():
        return used

    if not abs_specs_root.is_dir():
        return used

    for child in abs_specs_root.iterdir():
        if not child.is_dir():
            continue

        match = FEATURE_DIR_RE.match(child.name)
        if not match:
            continue

        used.add(int(match.group(1)))

    return used


def next_free_number(root: Path, specs_root: str) -> int:
    used = discover_used_numbers(root, specs_root)

    for number in range(1, 1000):
        if number not in used:
            return number

    raise RuntimeError("no free feature number available in range 001..999")


def build_metadata(root: Path, specs_root: str, number: int, slug: str) -> dict[str, Any]:
    feature_id = feature_id_for(number, slug)
    feature_dir = feature_dir_for(specs_root, number, slug)
    spec_file = feature_dir / "spec.md"

    return {
        "feature_id": feature_id,
        "slug": slug,
        "feature_number": f"{number:03d}",
        "feature_directory": posix(feature_dir),
        "spec_file": posix(spec_file),
        "absolute_feature_directory": posix((root / feature_dir).resolve()),
        "created_at": now_iso(),
    }


def cmd_slugify(args: argparse.Namespace) -> int:
    slug = slugify(args.text)
    errors = validate_slug(slug)

    if errors:
        return error(
            "invalid_slug",
            "slug is invalid after normalization",
            {
                "input": args.text,
                "slug": slug,
                "validation_errors": errors,
            },
        )

    payload = {
        "ok": True,
        "input": args.text,
        "slug": slug,
        "validation_errors": [],
    }

    json_out(payload)
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    root = Path(args.cwd).resolve()
    specs_root = args.specs_root

    specs_root_errors = validate_specs_root(specs_root)
    if specs_root_errors:
        return error(
            "invalid_specs_root",
            "specs root is invalid",
            {"validation_errors": specs_root_errors},
        )

    slug = slugify(args.slug)
    slug_errors = validate_slug(slug)
    if slug_errors:
        return error(
            "invalid_slug",
            "slug is invalid after normalization",
            {
                "input": args.slug,
                "slug": slug,
                "validation_errors": slug_errors,
            },
        )

    if args.number is not None:
        number = args.number
        if number < 1 or number > 999:
            return error(
                "invalid_feature_number",
                "feature number must be in range 1..999",
                {"feature_number": number},
            )
    else:
        try:
            number = next_free_number(root, specs_root)
        except RuntimeError as exc:
            return error("no_free_feature_number", str(exc))

    metadata = build_metadata(root, specs_root, number, slug)
    feature_dir = root / metadata["feature_directory"]

    if feature_dir.exists():
        return error(
            "feature_directory_exists",
            "feature directory already exists",
            {
                "feature_directory": metadata["feature_directory"],
                "feature_id": metadata["feature_id"],
            },
        )

    if args.dry_run:
        payload = {
            "ok": True,
            "action": "dry_run",
            "created_directory": False,
            **metadata,
        }
        json_out(payload)
        return 0

    try:
        feature_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        return error(
            "feature_directory_exists",
            "feature directory already exists",
            {
                "feature_directory": metadata["feature_directory"],
                "feature_id": metadata["feature_id"],
            },
        )
    except OSError as exc:
        return error(
            "create_failed",
            f"could not create feature directory: {exc}",
            {
                "feature_directory": metadata["feature_directory"],
                "feature_id": metadata["feature_id"],
            },
        )

    payload = {
        "ok": True,
        "action": "created",
        "created_directory": True,
        **metadata,
    }

    json_out(payload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Allocate OrderSpec feature spec directories."
    )

    parser.add_argument(
        "-C",
        "--cwd",
        default=".",
        help="project root directory",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_slugify = sub.add_parser("slugify", help="normalize text into an OrderSpec slug")
    p_slugify.add_argument("text")
    p_slugify.add_argument("--json", action="store_true")

    p_create = sub.add_parser("create", help="create a new feature directory")
    p_create.add_argument("--slug", required=True, help="slug or title to normalize")
    p_create.add_argument("--specs-root", default=DEFAULT_SPECS_ROOT)
    p_create.add_argument("--number", type=int, help="explicit feature number, 1..999")
    p_create.add_argument("--dry-run", action="store_true")
    p_create.add_argument("--json", action="store_true")

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "slugify":
        return cmd_slugify(args)

    if args.command == "create":
        return cmd_create(args)

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
