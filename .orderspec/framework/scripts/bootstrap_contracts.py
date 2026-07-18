#!/usr/bin/env python3
"""Inspect, generate, migrate, and validate deterministic project contracts."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    tomllib = None

try:
    import xml.etree.ElementTree as ET
except ImportError:
    ET = None


ROOT = Path(".")

from common import CONTRACTS_DIR, CONTRACT_FILES
from frontmatter import validate_project_contract_frontmatter
from validate_tooling import (
    check_installed_skills as check_tooling_skills,
    load_tooling,
    validate_structure as validate_tooling_structure,
)

PROJECT_DOCS = {
    "stack": CONTRACT_FILES["stack"],
    "architecture": CONTRACT_FILES["architecture"],
    "conventions": CONTRACT_FILES["conventions"],
    "constitution": CONTRACT_FILES["constitution"],
}

TOOLING_CONFIG_PATH = Path(".orderspec/config/tooling.json")
BOOTSTRAP_STATE_PATH = Path(".orderspec/state/bootstrap.json")
ORDERSPEC_META_PATH = Path(".orderspec/orderspec.json")
FRAMEWORK_RULES_PATH = Path(".orderspec/framework/orderspec-rules.md")
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "contracts"
CONTRACT_PREFIXES = {
    "constitution": "GOV",
    "stack": "STACK",
    "architecture": "ARCH",
    "conventions": "CONV",
}
SUPPORTED_MANIFESTS = ["package.json", "go.mod", "pyproject.toml", "Cargo.toml", "pom.xml"]

KEY_NODE_PACKAGES = {
    "express": ("Express", "Web framework", "HTTP API framework"),
    "mongoose": ("Mongoose", "ODM", "MongoDB object data modeling"),
    "mongodb": ("MongoDB Node Driver", "Database driver", "MongoDB driver"),
    "joi": ("Joi", "Validation", "Input validation library"),
    "passport": ("Passport", "Authentication", "Authentication middleware"),
    "passport-jwt": ("Passport JWT", "Authentication", "JWT authentication strategy"),
    "winston": ("Winston", "Logging", "Application logging"),
    "swagger-jsdoc": ("swagger-jsdoc", "API documentation", "OpenAPI spec generation from annotations"),
    "swagger-ui-express": ("swagger-ui-express", "API documentation", "Swagger UI middleware"),
    "bcryptjs": ("bcryptjs", "Password hashing", "Password hashing library"),
    "jsonwebtoken": ("jsonwebtoken", "JWT tokens", "JWT signing and verification"),
    "helmet": ("Helmet", "Security", "HTTP security headers"),
    "cors": ("cors", "CORS", "CORS middleware"),
    "nodemailer": ("Nodemailer", "Email", "Email transport"),
    "dotenv": ("dotenv", "Configuration", "Environment variable loading"),
    "morgan": ("Morgan", "HTTP logging", "HTTP request logging middleware"),
    "http-status": ("http-status", "HTTP status codes", "HTTP status constants"),
}

KEY_PYTHON_PACKAGES = {
    "fastapi": ("FastAPI", "Web framework", "Modern, fast web framework"),
    "django": ("Django", "Web framework", "High-level Python web framework"),
    "flask": ("Flask", "Web framework", "Micro web framework"),
    "sqlalchemy": ("SQLAlchemy", "ORM", "SQL toolkit and ORM"),
    "pydantic": ("Pydantic", "Validation", "Data validation using Python type hints"),
    "redis": ("Redis-py", "Caching", "Python client for Redis"),
    "celery": ("Celery", "Task queue", "Asynchronous task queue/job queue"),
    "psycopg2": ("psycopg2", "Database driver", "PostgreSQL adapter"),
    "psycopg2-binary": ("psycopg2", "Database driver", "PostgreSQL adapter"),
    "asyncpg": ("asyncpg", "Database driver", "PostgreSQL adapter for asyncio"),
}

KEY_GO_PACKAGES = {
    "github.com/gin-gonic/gin": ("Gin", "Web framework", "HTTP web framework"),
    "github.com/labstack/echo": ("Echo", "Web framework", "High performance web framework"),
    "github.com/gofiber/fiber": ("Fiber", "Web framework", "Express inspired web framework"),
    "gorm.io/gorm": ("GORM", "ORM", "ORM library for Golang"),
    "github.com/jackc/pgx": ("pgx", "Database driver", "PostgreSQL driver and toolkit"),
    "github.com/redis/go-redis": ("go-redis", "Caching", "Redis client for Golang"),
}

KEY_RUST_PACKAGES = {
    "tokio": ("Tokio", "Runtime", "Asynchronous runtime"),
    "axum": ("Axum", "Web framework", "Web framework for Rust"),
    "actix-web": ("Actix Web", "Web framework", "Web framework for Rust"),
    "sqlx": ("SQLx", "Database driver", "Async SQL driver"),
    "diesel": ("Diesel", "ORM", "ORM for Rust"),
    "serde": ("Serde", "Serialization", "Serialization framework"),
    "reqwest": ("Reqwest", "HTTP client", "HTTP client for Rust"),
}

KEY_JAVA_PACKAGES = {
    "org.springframework.boot:spring-boot-starter-web": ("Spring Boot Web", "Web framework", "Spring Boot web starter"),
    "org.springframework.boot:spring-boot-starter-data-jpa": ("Spring Data JPA", "ORM", "Spring Data JPA starter"),
    "org.hibernate:hibernate-core": ("Hibernate", "ORM", "Object/relational mapping"),
    "org.postgresql:postgresql": ("PostgreSQL JDBC", "Database driver", "PostgreSQL JDBC driver"),
    "mysql:mysql-connector-java": ("MySQL Connector", "Database driver", "MySQL JDBC driver"),
    "redis.clients:jedis": ("Jedis", "Caching", "Redis client for Java"),
}

API_HEAVY_PURPOSES = {
    "Web framework",
    "ODM",
    "ORM",
    "Database driver",
    "Validation",
    "Authentication",
    "API documentation",
    "JWT tokens",
    "Email",
    "Task queue",
    "Caching",
    "Runtime",
}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today() -> str:
    return dt.date.today().isoformat()


def file_sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def value_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def framework_version() -> str:
    try:
        value = json.loads(ORDERSPEC_META_PATH.read_text(encoding="utf-8"))
        return str(value.get("framework_version") or "unknown")
    except (OSError, json.JSONDecodeError):
        return "unknown"


def load_bootstrap_state() -> dict[str, Any]:
    try:
        value = json.loads(BOOTSTRAP_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def current_fingerprints() -> dict[str, str | None]:
    return {
        **{name: file_sha256(path) for name, path in PROJECT_DOCS.items()},
        "tooling": file_sha256(TOOLING_CONFIG_PATH),
    }


def skills_inventory() -> list[dict[str, str]]:
    skills_dir = Path(".orderspec/skills")
    if not skills_dir.is_dir():
        return []
    return [
        {"name": entry.name, "skill_md": file_sha256(entry / "SKILL.md") or "missing"}
        for entry in sorted(skills_dir.iterdir(), key=lambda item: item.name.lower())
        if entry.is_dir()
    ]


def project_evidence() -> dict[str, Any]:
    manifests = {
        name: file_sha256(Path(name))
        for name in SUPPORTED_MANIFESTS
        if Path(name).is_file()
    }
    project_documents = {}
    for name in ("README.md", "PROJECT.md", "CONTRIBUTING.md"):
        path = Path(name)
        if path.is_file():
            project_documents[name] = file_sha256(path)
    docs = Path("docs")
    if docs.is_dir():
        for path in sorted(docs.glob("*.md"))[:20]:
            project_documents[path.as_posix()] = file_sha256(path)
    return {
        "framework_rules": file_sha256(FRAMEWORK_RULES_PATH),
        "manifests": manifests,
        "source_directories": sorted(detect_dirs()),
        "skills": skills_inventory(),
        "project_documents": project_documents,
    }


def evidence_fingerprints() -> dict[str, str]:
    evidence = project_evidence()
    return {key: value_sha256(value) for key, value in evidence.items()}


def write_bootstrap_state() -> dict[str, Any]:
    payload = {
        "version": 2,
        "initialized": True,
        "completed_at": now_iso(),
        "framework_version": framework_version(),
        "manifest": detect_manifest(),
        "fingerprints": current_fingerprints(),
        "evidence_fingerprints": evidence_fingerprints(),
    }
    BOOTSTRAP_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{BOOTSTRAP_STATE_PATH.name}.",
        dir=str(BOOTSTRAP_STATE_PATH.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, BOOTSTRAP_STATE_PATH)
    finally:
        Path(temp_name).unlink(missing_ok=True)
    return payload


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))




def write_text_no_overwrite(path: Path, content: str, created: list[str]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    created.append(str(path))


def contract_frontmatter(kind: str) -> str:
    return (
        "---\n"
        "orderspec:\n"
        "  artifact: project_contract\n"
        f"  kind: {kind}\n"
        "  scope: project\n"
        "  owner_command: order.bootstrap\n"
        f"  id_prefix: {CONTRACT_PREFIXES[kind]}\n"
        "---\n\n"
    )


def migrate_legacy_frontmatter(path: Path, kind: str, migrated: list[str]) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        return
    path.write_text(contract_frontmatter(kind) + text, encoding="utf-8")
    migrated.append(str(path))


def render_contract(kind: str, **values: str) -> str:
    template_path = TEMPLATE_DIR / f"{kind}.md"
    if not template_path.is_file():
        raise RuntimeError(f"contract template missing: {template_path}")
    return template_path.read_text(encoding="utf-8").format(**values).rstrip() + "\n"


def detect_project_name() -> str:
    return ROOT.resolve().name


def missing_project_docs() -> list[str]:
    return [name for name, path in PROJECT_DOCS.items() if not path.exists()]


def detect_manifest() -> str | None:
    for name in SUPPORTED_MANIFESTS:
        if Path(name).exists():
            return name
    return None


def infer_node_stack() -> list[dict[str, str]]:
    package_path = Path("package.json")
    if not package_path.exists():
        return []

    package = read_json(package_path)
    deps = package.get("dependencies", {}) or {}
    engines = package.get("engines", {}) or {}

    rows: list[dict[str, str]] = []

    node_version = engines.get("node", "[UNRESOLVED: Node.js version not declared in package.json engines]")
    rows.append(
        {
            "id": "STACK-001",
            "technology": "Node.js",
            "version": str(node_version),
            "purpose": "Runtime",
            "notes": "JavaScript runtime",
        }
    )

    next_id = 2
    for package_name in sorted(deps.keys()):
        if package_name not in KEY_NODE_PACKAGES:
            continue
        tech, purpose, notes = KEY_NODE_PACKAGES[package_name]
        rows.append(
            {
                "id": f"STACK-{next_id:03d}",
                "technology": tech,
                "version": str(deps[package_name]),
                "purpose": purpose,
                "notes": f"npm package: {package_name}; {notes}",
            }
        )
        next_id += 1

    if "mongoose" in deps and "mongodb" not in deps:
        existing = {row["technology"] for row in rows}
        if "MongoDB" not in existing:
            rows.insert(
                2,
                {
                    "id": "STACK-003",
                    "technology": "MongoDB",
                    "version": "[UNRESOLVED: MongoDB server version not declared in package.json]",
                    "purpose": "Database",
                    "notes": "Accessed through Mongoose; confirm server version via deployment config",
                },
            )
            renumber_stack(rows)

    return rows


def infer_python_stack() -> list[dict[str, str]]:
    if not tomllib:
        return [
            {
                "id": "STACK-001",
                "technology": "Python",
                "version": "[UNRESOLVED: tomllib not available]",
                "purpose": "Runtime",
                "notes": "Requires Python 3.11+ for pyproject.toml parsing",
            }
        ]

    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        return []

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    rows: list[dict[str, str]] = []

    python_version = data.get("project", {}).get("requires-python", "[UNRESOLVED: requires-python not declared]")
    rows.append(
        {
            "id": "STACK-001",
            "technology": "Python",
            "version": str(python_version),
            "purpose": "Runtime",
            "notes": "Python runtime",
        }
    )

    # Support both PEP 621 [project.dependencies] and Poetry [tool.poetry.dependencies]
    deps = data.get("project", {}).get("dependencies", [])
    poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})

    # Merge and clean dependencies
    merged_deps = {}
    for dep in deps:
        # PEP 621 deps are strings like "fastapi[all]>=0.1"
        match = re.match(r"^([a-zA-Z0-9_-]+)", dep)
        if match:
            name = match.group(1).lower()
            version_str = dep[len(match.group(1)):]
            merged_deps[name] = version_str if version_str else "latest"

    for name, ver in poetry_deps.items():
        if name.lower() == "python":
            continue
        if isinstance(ver, dict):
            ver = ver.get("version", "latest")
        merged_deps[name.lower()] = str(ver)

    next_id = 2
    for package_name in sorted(merged_deps.keys()):
        if package_name not in KEY_PYTHON_PACKAGES:
            continue
        tech, purpose, notes = KEY_PYTHON_PACKAGES[package_name]
        rows.append(
            {
                "id": f"STACK-{next_id:03d}",
                "technology": tech,
                "version": merged_deps[package_name],
                "purpose": purpose,
                "notes": f"pypi package: {package_name}; {notes}",
            }
        )
        next_id += 1

    return rows


def infer_go_stack() -> list[dict[str, str]]:
    go_mod_path = Path("go.mod")
    if not go_mod_path.exists():
        return []

    text = go_mod_path.read_text(encoding="utf-8")
    rows: list[dict[str, str]] = []

    go_version_match = re.search(r"^go\s+(\d+\.\d+(?:\.\d+)?)", text, flags=re.M)
    go_version = go_version_match.group(1) if go_version_match else "[UNRESOLVED: go version not found]"
    rows.append(
        {
            "id": "STACK-001",
            "technology": "Go",
            "version": go_version,
            "purpose": "Runtime",
            "notes": "Go runtime",
        }
    )

    # Parse require block
    req_pattern = r"require\s*\((.*?)\)"
    req_match = re.search(req_pattern, text, flags=re.S)
    deps = {}
    if req_match:
        for line in req_match.group(1).strip().splitlines():
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                deps[parts[0]] = parts[1]

    # Also support single-line requires
    single_req_pattern = r"^require\s+([^\s]+)\s+([^\s]+)"
    for line in text.splitlines():
        m = re.match(single_req_pattern, line.strip())
        if m:
            deps[m.group(1)] = m.group(2)

    next_id = 2
    for package_name in sorted(deps.keys()):
        if package_name not in KEY_GO_PACKAGES:
            continue
        tech, purpose, notes = KEY_GO_PACKAGES[package_name]
        rows.append(
            {
                "id": f"STACK-{next_id:03d}",
                "technology": tech,
                "version": deps[package_name],
                "purpose": purpose,
                "notes": f"go module: {package_name}; {notes}",
            }
        )
        next_id += 1

    return rows


def infer_rust_stack() -> list[dict[str, str]]:
    if not tomllib:
        return [
            {
                "id": "STACK-001",
                "technology": "Rust",
                "version": "[UNRESOLVED: tomllib not available]",
                "purpose": "Runtime",
                "notes": "Requires Python 3.11+ for Cargo.toml parsing",
            }
        ]

    cargo_path = Path("Cargo.toml")
    if not cargo_path.exists():
        return []

    with open(cargo_path, "rb") as f:
        data = tomllib.load(f)

    rows: list[dict[str, str]] = []

    rust_version = data.get("package", {}).get("rust-version", "[UNRESOLVED: rust-version not declared]")
    rows.append(
        {
            "id": "STACK-001",
            "technology": "Rust",
            "version": str(rust_version),
            "purpose": "Runtime",
            "notes": "Rust runtime",
        }
    )

    deps = data.get("dependencies", {})
    next_id = 2
    for package_name in sorted(deps.keys()):
        if package_name not in KEY_RUST_PACKAGES:
            continue
        tech, purpose, notes = KEY_RUST_PACKAGES[package_name]
        ver = deps[package_name]
        if isinstance(ver, dict):
            ver = ver.get("version", "latest")
        rows.append(
            {
                "id": f"STACK-{next_id:03d}",
                "technology": tech,
                "version": str(ver),
                "purpose": purpose,
                "notes": f"crate: {package_name}; {notes}",
            }
        )
        next_id += 1

    return rows


def infer_java_stack() -> list[dict[str, str]]:
    if not ET:
        return [
            {
                "id": "STACK-001",
                "technology": "Java",
                "version": "[UNRESOLVED: xml.etree.ElementTree not available]",
                "purpose": "Runtime",
                "notes": "Cannot parse pom.xml without ElementTree",
            }
        ]

    pom_path = Path("pom.xml")
    if not pom_path.exists():
        return []

    tree = ET.parse(pom_path)
    root = tree.getroot()

    # Handle XML namespaces
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0][1:]
        ns_prefix = f"{{{ns}}}"
    else:
        ns_prefix = ""

    # Detect Java version from properties
    props = root.find(f"{ns_prefix}properties")
    java_version = "[UNRESOLVED: java version not found in pom.xml properties]"
    if props is not None:
        for prop in props:
            if prop.tag.replace(ns_prefix, "") in ["maven.compiler.source", "java.version", "maven.compiler.release"]:
                java_version = prop.text or java_version
                break

    rows: list[dict[str, str]] = []
    rows.append(
        {
            "id": "STACK-001",
            "technology": "Java",
            "version": java_version,
            "purpose": "Runtime",
            "notes": "Java runtime",
        }
    )

    deps = {}
    deps_node = root.find(f"{ns_prefix}dependencies")
    if deps_node is not None:
        for dep in deps_node.findall(f"{ns_prefix}dependency"):
            group_id = dep.findtext(f"{ns_prefix}groupId", default="")
            artifact_id = dep.findtext(f"{ns_prefix}artifactId", default="")
            version = dep.findtext(f"{ns_prefix}version", default="[UNRESOLVED: version not declared]")
            if not group_id or not artifact_id:
                continue
            deps[f"{group_id}:{artifact_id}"] = version

    next_id = 2
    for package_name in sorted(deps.keys()):
        if package_name not in KEY_JAVA_PACKAGES:
            continue
        tech, purpose, notes = KEY_JAVA_PACKAGES[package_name]
        rows.append(
            {
                "id": f"STACK-{next_id:03d}",
                "technology": tech,
                "version": deps[package_name],
                "purpose": purpose,
                "notes": f"maven artifact: {package_name}; {notes}",
            }
        )
        next_id += 1

    return rows


def renumber_stack(rows: list[dict[str, str]]) -> None:
    for index, row in enumerate(rows, start=1):
        row["id"] = f"STACK-{index:03d}"


def stack_markdown(rows: list[dict[str, str]]) -> str:
    lines = []
    for row in rows:
        lines.append(
            f"| {row['id']} | {row['technology']} | {row['version']} | {row['purpose']} | {row['notes']} |"
        )
    return render_contract("stack", rows="\n".join(lines))


def detect_dirs() -> set[str]:
    dirs = set()
    src = Path("src")
    if src.exists():
        for path in src.iterdir():
            if path.is_dir():
                dirs.add(path.name)
    return dirs


def architecture_markdown() -> str:
    dirs = detect_dirs()

    if {"routes", "controllers", "services", "models"}.issubset(dirs):
        return """# Project Architecture

Structural contracts: layers and dependency rules.
Referenced by spec.md and plan.md as ARCH-NNN.
Maintained via /order.bootstrap. IDs are append-only.

## Layers

Application follows a layered HTTP API architecture.

| Layer | Directory | Responsibility |
|-------|-----------|----------------|
| Entry | [UNRESOLVED: detect project entry files] | Process/bootstrap and application assembly |
| Config | `src/config/` | Environment variables and app configuration |
| Routes | `src/routes/` | HTTP route definitions and middleware chaining |
| Controllers | `src/controllers/` | Request handling and response formatting |
| Middlewares | `src/middlewares/` | Cross-cutting request/response concerns |
| Validations | `src/validations/` | Input validation schema definitions |
| Services | `src/services/` | Business logic and use-case orchestration |
| Models | `src/models/` | Data model and persistence access |
| Utils | `src/utils/` | Shared utilities and helpers |
| Docs | `src/docs/` | API documentation definitions |

## Dependency Rules

| ID | Rule |
|----|------|
| ARCH-001 | Application layering is routes → controllers → services → models, with validations and middlewares used at the route/controller boundary |
| ARCH-002 | Routes MAY depend on controllers, validations, middlewares, config, and utils only |
| ARCH-003 | Controllers MAY depend on services, validations, config, and utils only |
| ARCH-004 | Services MAY depend on models, config, and utils only |
| ARCH-005 | Models MUST NOT depend on routes, controllers, services, middlewares, or validations |
| ARCH-006 | Entry files MAY depend on app setup, config, routes, middlewares, docs, and utils only |
| ARCH-007 | Config MAY depend on utils only |
| ARCH-008 | Middlewares MAY depend on config, services, validations, and utils only |
| ARCH-009 | Validations MAY depend on config and utils only |
| ARCH-010 | Utils MUST NOT depend on routes, controllers, services, models, middlewares, validations, or docs |
| ARCH-011 | Docs MAY depend on route metadata, validations, config, and utils only, and MUST NOT contain business logic |
| ARCH-012 | Any dependency not explicitly allowed by ARCH-002 through ARCH-011 requires a new explicit ARCH-NNN rule |
"""

    if {"modules"}.intersection(dirs) or {"features"}.intersection(dirs) or {"domains"}.intersection(dirs):
        return """# Project Architecture

Structural contracts: layers and dependency rules.
Referenced by spec.md and plan.md as ARCH-NNN.
Maintained via /order.bootstrap. IDs are append-only.

## Layers

Project appears to use modular/domain-oriented organization.

| Layer | Directory | Responsibility |
| Modules/Domains | `src/modules/`, `src/features/`, or `src/domains/` | Feature/domain boundaries |

## Dependency Rules

| ID | Rule |
|----|------|
| ARCH-001 | Feature/domain modules MUST keep their internal implementation behind explicit interfaces |
| ARCH-002 | Cross-module dependencies MUST be explicit and must not rely on private internal files |
"""

    return """# Project Architecture

Structural contracts: layers and dependency rules.
Referenced by spec.md and plan.md as ARCH-NNN.
Maintained via /order.bootstrap. IDs are append-only.

## Layers

[UNRESOLVED: architecture style not detected from repository structure]

| Layer | Directory | Responsibility |
|-------|-----------|----------------|

## Dependency Rules

| ID | Rule |
|----|------|
| ARCH-001 | [UNRESOLVED: define intended architecture and dependency direction] |
"""


def rendered_architecture_markdown() -> str:
    legacy = architecture_markdown()
    marker = "## Layers"
    body = legacy[legacy.index(marker):] if marker in legacy else legacy
    return render_contract("architecture", body=body.rstrip())

def conventions_markdown() -> str:
    return render_contract("conventions", rows="")



def tooling_json_content(stack_rows: list[dict[str, str]] | None = None) -> str:
    """Generate tooling.json with explicit defaults from tooling-protocol.md.

    The script cannot discover skills or check MCP availability — that is an
    agent task. This function creates a self-documenting baseline that the
    agent updates during the Tooling Discovery phase.
    """
    return json.dumps(
        {
            "version": 3,
            "skills": {
                "install_policy": "ask_user",
                "install_location": ".orderspec/skills/",
                "resolution_order": [
                    ".orderspec/skills/"
                ],
                "bindings": [],
            },
            "docs_sources": {
                "context7": {
                    "policy": "required_if_available",
                    "commands": ["order.plan", "order.tasks", "order.code"],
                    "fallback_when_unavailable": "block_library_specific_claims_without_other_evidence"
                }
            }
        },
        indent=2,
        ensure_ascii=False,
    ) + "\n"

def constitution_markdown(project_name: str, gate_profile: str, test_command: str | None, lint_command: str | None, external_rules_policy: str = "constrain_on_bootstrap") -> str:
    profile = gate_profile.upper()
    if profile == "A":
        test = "DENIED. Gates MUST NOT run tests."
        lint = "DENIED. Gates MUST NOT run build, compile, or lint commands."
        network = "DENIED."
    elif profile in {"B", "C"}:
        test = f"ALLOWED. run: {test_command or '[UNRESOLVED: TEST_COMMAND]'}"
        lint = f"ALLOWED. run: {lint_command or '[UNRESOLVED: LINT_COMMAND]'}"
        network = "DENIED." if profile == "B" else "ALLOWED only for configured documentation sources and package registries."
    else:
        raise SystemExit("gate profile must be A, B, or C")

    governance_rows = "\n".join([
        "| GOV-001 | Feature behavior changes MUST begin in the owning specification. | Preserve contract-first development. | OrderSpec bootstrap default |",
        "| GOV-002 | Logical specifications MUST NOT contain physical implementation details. | Keep stable truth independent of repository layout. | OrderSpec bootstrap default |",
        "| GOV-003 | Unstated capabilities MUST be treated as denied. | Prevent implicit side effects. | OrderSpec bootstrap default |",
    ])
    return render_contract(
        "constitution",
        project_name=project_name,
        mission="[UNRESOLVED: confirm project mission from operator-approved project evidence]",
        values="[UNRESOLVED: confirm project values from operator-approved project evidence]",
        governance_rows=governance_rows,
        test=test,
        lint=lint,
        network=network,
        external_rules_policy=external_rules_policy,
        date=today(),
    )

def validate_stack(path: Path) -> list[str]:
    errors = []
    text = path.read_text(encoding="utf-8")
    ids = re.findall(r"^\|\s*(STACK-\d{3})\s*\|", text, flags=re.M)
    unique = set(ids)

    if not ids:
        errors.append("stack.md has no STACK-NNN IDs")
    if len(ids) != len(unique):
        errors.append("stack.md has duplicate STACK-NNN IDs")

    for id_ in ids:
        if not re.fullmatch(r"STACK-\d{3}", id_):
            errors.append(f"invalid stack ID: {id_}")

    return errors


def table_ids(text: str, prefix: str) -> list[str]:
    return re.findall(rf"^\|\s*({prefix}-\d{{3}})\s*\|", text, flags=re.M)


def validate_frontmatter(path: Path, kind: str) -> list[str]:
    return [
        f"{path.name}: {field}: {message}"
        for field, message in validate_project_contract_frontmatter(
            path.read_text(encoding="utf-8"), expected_kind=kind
        )
    ]


def validate_architecture(path: Path) -> list[str]:
    errors = []
    text = path.read_text(encoding="utf-8")
    ids = re.findall(r"^\|\s*(ARCH-\d{3})\s*\|", text, flags=re.M)
    unique = set(ids)

    if not ids:
        errors.append("architecture.md has no ARCH-NNN IDs")
    if len(ids) != len(unique):
        errors.append("architecture.md has duplicate ARCH-NNN IDs")
    if "## Layers" not in text:
        errors.append("architecture.md missing ## Layers")
    if "## Dependency Rules" not in text:
        errors.append("architecture.md missing ## Dependency Rules")

    return errors


def validate_conventions(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    ids = table_ids(text, "CONV")
    errors = []
    if len(ids) != len(set(ids)):
        errors.append("conventions.md has duplicate CONV-NNN IDs")
    if "| ID | Convention | Description | Notes |" not in text:
        errors.append("conventions.md missing conventions table")
    return errors


def validate_constitution(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    ids = table_ids(text, "GOV")
    errors = []
    if not ids:
        errors.append("constitution.md has no GOV-NNN governance rules")
    if len(ids) != len(set(ids)):
        errors.append("constitution.md has duplicate GOV-NNN IDs")
    for line in text.splitlines():
        if re.match(r"^\|\s*GOV-\d{3}\s*\|", line) and not re.search(r"\b(?:MUST|SHOULD)\b", line):
            errors.append(f"constitution.md governance rule must use MUST or SHOULD: {line}")
    required_sections = [
        "## Project Intent (Non-Normative)",
        "## Governance Rules",
        "## Capability Grants",
        "## External Rules Integration",
    ]
    for section in required_sections:
        if section not in text:
            errors.append(f"constitution.md missing {section}")
    for capability in [
        "### Test execution",
        "### Build / compile / lint as evidence",
        "### Network access during a gate",
        "### Skill discovery",
        "### Skill installation or registration",
    ]:
        match = re.search(rf"^{re.escape(capability)}\s*$\n([^#\n].*)", text, flags=re.M)
        if not match or not re.search(r"\b(?:ALLOWED|DENIED)\b", match.group(1)):
            errors.append(f"constitution.md capability is not explicit: {capability}")
    policy = re.search(r"^Policy:\s*`([^`]+)`\s*$", text, flags=re.M)
    if not policy or policy.group(1) not in {"constrain_on_bootstrap", "ignore"}:
        errors.append("constitution.md external rules policy must be constrain_on_bootstrap or ignore")
    return errors


def validate_created_files() -> list[str]:
    errors = []

    if PROJECT_DOCS["stack"].exists():
        errors.extend(validate_frontmatter(PROJECT_DOCS["stack"], "stack"))
        errors.extend(validate_stack(PROJECT_DOCS["stack"]))
    else:
        errors.append("stack.md missing")

    if PROJECT_DOCS["architecture"].exists():
        errors.extend(validate_frontmatter(PROJECT_DOCS["architecture"], "architecture"))
        errors.extend(validate_architecture(PROJECT_DOCS["architecture"]))
    else:
        errors.append("architecture.md missing")

    if not PROJECT_DOCS["conventions"].exists():
        errors.append("conventions.md missing")
    else:
        errors.extend(validate_frontmatter(PROJECT_DOCS["conventions"], "conventions"))
        errors.extend(validate_conventions(PROJECT_DOCS["conventions"]))

    if not PROJECT_DOCS["constitution"].exists():
        errors.append("constitution.md missing")
    else:
        errors.extend(validate_frontmatter(PROJECT_DOCS["constitution"], "constitution"))
        errors.extend(validate_constitution(PROJECT_DOCS["constitution"]))

    return errors

# Note: External Rules Integration section validation is intentionally lenient.
# If the section is missing, bootstrap will add it. If policy value is missing
# or invalid, the default `constrain_on_bootstrap` applies (see orderspec-rules.md).
# This is a soft check — the constitution is still valid without this section
# for backward compatibility with projects created before multi-agent support.


def inspect_command(args: argparse.Namespace) -> int:
    manifest = detect_manifest()
    missing_docs = missing_project_docs()
    state = load_bootstrap_state()
    explicit_state = state.get("initialized") is True
    inferred_legacy_state = not missing_docs and not explicit_state

    result = {
        "mode": "init" if missing_docs else "refine",
        "initialized": explicit_state or inferred_legacy_state,
        "state_source": "state" if explicit_state else ("existing_contracts" if inferred_legacy_state else "none"),
        "state_migration_required": inferred_legacy_state,
        "last_framework_version": state.get("framework_version"),
        "current_framework_version": framework_version(),
        "missing_project_docs": missing_docs,
        "manifest": manifest,
        "project_name": detect_project_name(),
        "requires_gate_question": "constitution" in missing_docs,
        "recommended_gate_profile": "A",
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def inferred_stack_rows() -> list[dict[str, str]]:
    manifest = detect_manifest()
    if manifest == "package.json":
        return infer_node_stack()
    if manifest == "pyproject.toml":
        return infer_python_stack()
    if manifest == "go.mod":
        return infer_go_stack()
    if manifest == "Cargo.toml":
        return infer_rust_stack()
    if manifest == "pom.xml":
        return infer_java_stack()
    return []


def constitution_evidence_command(args: argparse.Namespace) -> int:
    """Collect bounded project text as candidates; never author governance."""
    paths: list[Path] = []
    for name in ("README.md", "PROJECT.md", "CONTRIBUTING.md"):
        path = Path(name)
        if path.is_file():
            paths.append(path)
    docs = Path("docs")
    if docs.is_dir():
        paths.extend(sorted(docs.glob("*.md"))[:20])

    candidates: list[dict[str, str]] = []
    normative = re.compile(r"\b(?:MUST|MUST NOT|SHOULD|SHOULD NOT|required|forbidden)\b", re.I)
    intent_heading = re.compile(r"^#{1,4}\s+.*\b(?:mission|values?|principles?|constraints?|goals?)\b", re.I)
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        active_intent = False
        for number, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                active_intent = bool(intent_heading.match(stripped))
                continue
            if not stripped or len(stripped) > 500:
                continue
            match = normative.search(stripped)
            if match or (active_intent and not stripped.startswith("|")):
                candidates.append({
                    "kind": "hard_constraint_candidate" if match else "project_intent_candidate",
                    "statement": stripped.lstrip("-* "),
                    "source": f"{path.as_posix()}:{number}",
                    "authority": "candidate_only",
                })
    print(json.dumps({
        "ok": True,
        "sources": [path.as_posix() for path in paths],
        "candidates": candidates[:100],
        "requires_operator_approval": True,
        "warning": "Candidates are evidence, not governance. Do not write GOV-NNN without operator approval.",
    }, indent=2, ensure_ascii=False))
    return 0


def audit_command(args: argparse.Namespace) -> int:
    """Emit deterministic evidence for semantic bootstrap Refine mode."""
    missing = missing_project_docs()
    if missing:
        print(json.dumps({"ok": False, "error": "project_contracts_missing", "missing": missing}, indent=2))
        return 2
    state = load_bootstrap_state()
    stack_text = PROJECT_DOCS["stack"].read_text(encoding="utf-8")
    try:
        inferred = inferred_stack_rows()
    except Exception as exc:
        print(
            json.dumps(
                {"ok": False, "error": "repository_manifest_invalid", "details": str(exc)},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 2
    missing_stack_candidates = [
        row for row in inferred if str(row.get("technology", "")).lower() not in stack_text.lower()
    ]
    inferred_technologies = {str(row.get("technology", "")).strip().lower() for row in inferred}
    existing_stack_rows = re.findall(
        r"^\|\s*(STACK-\d{3})\s*\|\s*([^|]+?)\s*\|",
        stack_text,
        flags=re.M,
    )
    unverified_stack_rows = [
        {"id": ref, "technology": technology.strip()}
        for ref, technology in existing_stack_rows
        if inferred_technologies
        and technology.strip().lower() not in inferred_technologies
        and "[removed" not in technology.lower()
    ]
    previous = state.get("fingerprints", {}) if isinstance(state.get("fingerprints"), dict) else {}
    current = current_fingerprints()
    changed_contracts = [name for name in PROJECT_DOCS if previous.get(name) not in (None, current.get(name))]
    previous_evidence = state.get("evidence_fingerprints", {}) if isinstance(state.get("evidence_fingerprints"), dict) else {}
    current_evidence = evidence_fingerprints()
    validation_errors = validate_created_files()
    items: list[dict[str, Any]] = []

    def add_item(kind: str, classification: str, evidence: list[str], **extra: Any) -> None:
        items.append({
            "id": f"DRIFT-{len(items) + 1:03d}",
            "kind": kind,
            "classification": classification,
            "evidence": evidence,
            **extra,
        })

    if state.get("framework_version") not in (None, framework_version()) or (
        previous_evidence.get("framework_rules") not in (None, current_evidence.get("framework_rules"))
    ):
        add_item(
            "framework_compatibility",
            "operator_decision",
            [".orderspec/framework/orderspec-rules.md", ".orderspec/orderspec.json"],
            proposed_action="review_project_contracts_against_current_framework_rules",
        )
    for error in validation_errors:
        mechanical = "No YAML frontmatter" in error
        add_item(
            "contract_schema_incompatibility",
            "safe_mechanical_migration" if mechanical else "operator_decision",
            [error],
            proposed_action="migrate_frontmatter" if mechanical else "amend",
        )
    for name in changed_contracts:
        add_item(
            "project_contract_changed_since_baseline",
            "operator_decision",
            [str(PROJECT_DOCS[name])],
            contract=name,
            proposed_action="confirm_or_revert_out_of_band_contract_change",
        )
    if previous_evidence.get("manifests") not in (None, current_evidence.get("manifests")):
        add_item(
            "project_state_manifest_changed",
            "operator_decision",
            list(project_evidence()["manifests"].keys()) or ["supported manifest removed"],
            proposed_action="review_stack_contract",
        )
    for row in missing_stack_candidates:
        add_item(
            "project_state_stack_candidate",
            "operator_decision",
            [detect_manifest() or "no supported manifest"],
            candidate=row,
            proposed_action="confirm_stack_amendment",
        )
    for row in unverified_stack_rows:
        add_item(
            "project_state_stack_row_unverified",
            "operator_decision",
            [detect_manifest() or "no supported manifest"],
            contract_ref=row["id"],
            technology=row["technology"],
            proposed_action="confirm_keep_or_tombstone",
        )
    if previous_evidence.get("source_directories") not in (None, current_evidence.get("source_directories")):
        add_item(
            "project_state_architecture_changed",
            "operator_decision",
            ["repository source directory topology"],
            proposed_action="review_architecture_contract",
        )
    if previous_evidence.get("skills") not in (None, current_evidence.get("skills")) or previous.get("tooling") not in (None, current.get("tooling")):
        add_item(
            "tooling_drift",
            "tooling_drift",
            [".orderspec/config/tooling.json", ".orderspec/skills/"],
            proposed_action="run_validate_tooling",
        )
    if previous_evidence.get("project_documents") not in (None, current_evidence.get("project_documents")):
        add_item(
            "project_intent_evidence_changed",
            "operator_decision",
            list(project_evidence()["project_documents"].keys()),
            proposed_action="run_constitution_evidence",
        )

    result = {
        "ok": True,
        "mode": "refine",
        "framework": {
            "previous_version": state.get("framework_version"),
            "current_version": framework_version(),
            "changed": state.get("framework_version") not in (None, framework_version()),
        },
        "repository": {
            "manifest": detect_manifest(),
            "top_level_directories": sorted(detect_dirs()),
            "inferred_stack": inferred,
            "missing_stack_candidates": missing_stack_candidates,
        },
        "contracts": {
            "validation_errors": validation_errors,
            "changed_since_last_bootstrap": changed_contracts,
            "fingerprints": current,
        },
        "tooling": {
            "config_exists": TOOLING_CONFIG_PATH.is_file(),
            "requires_validate_tooling": True,
        },
        "scope": {
            "compares": ["framework rules", "project contracts", "bounded current project evidence", "project tooling"],
            "excludes": ["feature specification drift", "plan drift", "task drift", "code-to-spec drift"],
        },
        "items": items,
        "required_semantic_checks": [
            "project contracts against current framework rules",
            "stack and architecture against current repository evidence",
            "installed skill bindings against the current project stack",
        ],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not result["contracts"]["validation_errors"] else 1


def complete_command(args: argparse.Namespace) -> int:
    errors = validate_created_files()
    tooling = load_tooling(TOOLING_CONFIG_PATH)
    if tooling is None:
        errors.append("tooling.json missing or invalid")
    else:
        errors.extend(validate_tooling_structure(tooling, ROOT.resolve()))
        install_errors, _ = check_tooling_skills(tooling, Path(".orderspec/skills"))
        errors.extend(install_errors)
    if errors:
        print(json.dumps({"ok": False, "validation_errors": errors}, indent=2, ensure_ascii=False))
        return 1
    active_process = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parent / "active_feature.py"),
            "init",
            "--last-command",
            "order.bootstrap",
            "--json",
        ],
        text=True,
        capture_output=True,
    )
    try:
        active_state = json.loads(active_process.stdout)
    except json.JSONDecodeError:
        active_state = {
            "ok": False,
            "error": "active_feature_initialization_failed",
            "details": active_process.stderr or active_process.stdout,
        }
    if active_process.returncode != 0 or not active_state.get("ok"):
        print(json.dumps({
            "ok": False,
            "validation_errors": ["active-feature.json initialization failed"],
            "active_feature": active_state,
        }, indent=2, ensure_ascii=False))
        return active_process.returncode or 1
    state = write_bootstrap_state()
    print(json.dumps({
        "ok": True,
        "state_file": str(BOOTSTRAP_STATE_PATH),
        "state": state,
        "active_feature": active_state,
    }, indent=2, ensure_ascii=False))
    return 0


def migrate_frontmatter_command(args: argparse.Namespace) -> int:
    migrated: list[str] = []
    for kind, path in PROJECT_DOCS.items():
        migrate_legacy_frontmatter(path, kind, migrated)
    errors = validate_created_files()
    print(json.dumps({
        "ok": True,
        "migrated_frontmatter": migrated,
        "contracts_valid": not errors,
        "remaining_validation_errors": errors,
    }, indent=2, ensure_ascii=False))
    return 0


def init_command(args: argparse.Namespace) -> int:
    created: list[str] = []
    migrated: list[str] = []
    manifest = detect_manifest()

    if manifest == "package.json":
        stack_rows = infer_node_stack()
    elif manifest == "pyproject.toml":
        stack_rows = infer_python_stack()
    elif manifest == "go.mod":
        stack_rows = infer_go_stack()
    elif manifest == "Cargo.toml":
        stack_rows = infer_rust_stack()
    elif manifest == "pom.xml":
        stack_rows = infer_java_stack()
    else:
        stack_rows = [
            {
                "id": "STACK-001",
                "technology": "[UNRESOLVED: runtime]",
                "version": "[UNRESOLVED: version]",
                "purpose": "Runtime",
                "notes": f"No supported manifest detected; manifest={manifest}",
            }
        ]

    # Generate content from templates
    stack_content = stack_markdown(stack_rows)
    architecture_content = rendered_architecture_markdown()
    conventions_content = conventions_markdown()
    constitution_content = constitution_markdown(
        project_name=args.project_name or detect_project_name(),
        gate_profile=args.gate_profile,
        test_command=args.test_command,
        lint_command=args.lint_command,
        external_rules_policy=args.external_rules_policy,
    )

    write_text_no_overwrite(PROJECT_DOCS["stack"], stack_content, created)
    write_text_no_overwrite(PROJECT_DOCS["architecture"], architecture_content, created)
    write_text_no_overwrite(PROJECT_DOCS["conventions"], conventions_content, created)
    write_text_no_overwrite(PROJECT_DOCS["constitution"], constitution_content, created)
    write_text_no_overwrite(TOOLING_CONFIG_PATH, tooling_json_content(stack_rows), created)

    for kind, path in PROJECT_DOCS.items():
        migrate_legacy_frontmatter(path, kind, migrated)

    errors = validate_created_files()

    result = {
        "ok": not errors,
        "mode": "init",
        "created": created,
        "migrated_frontmatter": migrated,
        "preserved_existing": [
            str(path)
            for path in PROJECT_DOCS.values()
            if path.exists() and str(path) not in created
        ],
        "manifest": manifest,
        "stack_count": len(stack_rows),
        "architecture_detected": bool({"routes", "controllers", "services", "models"}.issubset(detect_dirs())),
        "validation_errors": errors,
        "next_steps": [
            "Run /order.spec to write your first feature specification.",
            "Run /order.bootstrap again to amend project contracts as the project evolves.",
        ],
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


def validate_command(args: argparse.Namespace) -> int:
    errors = validate_created_files()
    print(
        json.dumps(
            {
                "ok": not errors,
                "validation_errors": errors,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if not errors else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="OrderSpec deterministic bootstrap contract creator")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("--json", action="store_true")

    init_parser = sub.add_parser("init")
    init_parser.add_argument("--json", action="store_true")
    init_parser.add_argument("--gate-profile", choices=["A", "B", "C"], required=True)
    init_parser.add_argument("--project-name")
    init_parser.add_argument("--test-command")
    init_parser.add_argument("--lint-command")
    init_parser.add_argument(
        "--external-rules-policy",
        choices=["constrain_on_bootstrap", "ignore"],
        default="constrain_on_bootstrap",
        help="Policy for external AI agent rule files (default: constrain_on_bootstrap)",
    )

    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--json", action="store_true")

    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--json", action="store_true")

    complete_parser = sub.add_parser("complete")
    complete_parser.add_argument("--json", action="store_true")

    evidence_parser = sub.add_parser("constitution-evidence")
    evidence_parser.add_argument("--json", action="store_true")

    migration_parser = sub.add_parser("migrate-frontmatter")
    migration_parser.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.command == "inspect":
        return inspect_command(args)
    if args.command == "init":
        return init_command(args)
    if args.command == "validate":
        return validate_command(args)
    if args.command == "audit":
        return audit_command(args)
    if args.command == "complete":
        return complete_command(args)
    if args.command == "constitution-evidence":
        return constitution_evidence_command(args)
    if args.command == "migrate-frontmatter":
        return migrate_frontmatter_command(args)

    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
