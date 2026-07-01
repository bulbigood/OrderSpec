#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
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

PROJECT_DOCS = {
    "stack": CONTRACT_FILES["stack"],
    "architecture": CONTRACT_FILES["architecture"],
    "conventions": CONTRACT_FILES["conventions"],
    "constitution": CONTRACT_FILES["constitution"],
}

TOOLING_CONFIG_PATH = Path(".orderspec/config/tooling.json")

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


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))




def write_text_no_overwrite(path: Path, content: str, created: list[str]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    created.append(str(path))


def detect_project_name() -> str:
    return ROOT.resolve().name


def missing_project_docs() -> list[str]:
    return [name for name, path in PROJECT_DOCS.items() if not path.exists()]


def detect_manifest() -> str | None:
    for name in ["package.json", "go.mod", "pyproject.toml", "Cargo.toml", "pom.xml"]:
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
    lines = [
        "# Project Stack",
        "",
        "Technologies used in this project.",
        "Referenced by spec.md and plan.md as STACK-NNN.",
        "Maintained via /order.bootstrap. IDs are append-only.",
        "",
        "| ID | Technology | Version | Purpose | Notes |",
        "|----|------------|---------|---------|-------|",
    ]

    for row in rows:
        lines.append(
            f"| {row['id']} | {row['technology']} | {row['version']} | {row['purpose']} | {row['notes']} |"
        )

    return "\n".join(lines) + "\n"


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
| Entry | `src/index.js`, `src/app.js` | Server bootstrap and app setup |
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
|-------|-----------|----------------|
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

def conventions_markdown() -> str:
    return """# Project Conventions

Implementation conventions: error handling, serialization,
validation patterns, shared plugins, etc.
Referenced by spec.md and plan.md as CONV-NNN.
Maintained via /order.bootstrap. IDs are append-only.
This file starts empty and grows as patterns are discovered.

| ID | Convention | Description | Notes |
|----|------------|-------------|-------|
"""



def tooling_json_content(stack_rows: list[dict[str, str]] | None = None) -> str:
    """Generate tooling.json with explicit defaults from tooling-protocol.md.

    The script cannot discover skills or check MCP availability — that is an
    agent task. This function creates a self-documenting baseline that the
    agent updates during the Tooling Discovery phase.
    """
    return json.dumps(
        {
            "version": 2,
            "skills": {
                "install_policy": "ask_user",
                "install_location": ".orderspec/skills/",
                "resolution_order": [
                    ".orderspec/skills/",
                    "~/.agents/skills/"
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
        test = "DENIED. Gates MUST NOT run tests; rely on static inspection."
        lint = "DENIED. Gates MUST NOT invoke a compiler or linter; rely on static inspection."
        network = "DENIED."
    elif profile == "B":
        test = f"ALLOWED. run: {test_command or '[UNRESOLVED: TEST_COMMAND]'}"
        lint = f"ALLOWED. run: {lint_command or '[UNRESOLVED: LINT_COMMAND]'}"
        network = "DENIED."
    elif profile == "C":
        test = f"ALLOWED. run: {test_command or '[UNRESOLVED: TEST_COMMAND]'}"
        lint = f"ALLOWED. run: {lint_command or '[UNRESOLVED: LINT_COMMAND]'}"
        network = "ALLOWED for package registries and configured documentation MCP servers only."
    else:
        raise SystemExit("gate profile must be A, B, or C")

    return f"""# {project_name} Constitution

Supreme governance document.
- Core Principles: rules the project must uphold (MUST/SHOULD, testable).
- Capability Grants: machine-readable permissions that gates execute literally.
LAW: any capability not explicitly granted is DENIED. Silence is never permission.
Maintained via /order.bootstrap.

## Core Principles

### I. Contract Stability
spec.md MUST remain the source of truth for behavior. Behavior changes start in spec.md, not in code.

### II. Spec-Code Separation
spec.md MUST NOT contain physical implementation details (file paths, library names, ORM annotations). These belong to plan.md or project contract documents (stack.md, architecture.md, conventions.md).

### III. Default-Deny
Any capability not explicitly granted in the Capability Grants section below is DENIED. Gates MUST degrade to static inspection on anything unstated. This is non-negotiable.

## Capability Grants

THIS SECTION IS READ BY GATES LITERALLY.
Write flat, unambiguous ALLOWED/DENIED statements with explicit commands.
A gate must answer "am I allowed to do X?" with a literal yes/no by scanning this section.
Anything omitted is DENIED.

### Test execution
{test}

### Build / compile / lint as evidence
{lint}

### Network access during a gate
{network}

### Skill discovery
DENIED unless the current chat contains explicit user approval for the exact discovery action.

### Skill installation or registration
DENIED unless the current chat contains explicit user approval for the exact skill name and source.

### Documentation lookup during authoring
ALLOWED for read-only documentation lookup required by `.orderspec/framework/protocols/tooling-protocol.md` or `.orderspec/config/tooling.json` during authoring commands. This does not allow package installation, skill installation, project command execution, arbitrary network access, or gate-time network access.

### MCP documentation lookup during gates
DENIED unless explicitly allowed above. Gates follow this constitution literally.

### Mechanical auto-fixes by gates
ALLOWED for glossary-term normalization and unambiguous stale-ID references only. Anything touching meaning or scope MUST be routed to the owning command, never applied.

## External Rules Integration

Policy: `{external_rules_policy}`

This section controls how OrderSpec interacts with external rule files owned by AI agents (AGENTS.md, .cursorrules, CLAUDE.md, etc.).

| Policy | Behavior |
|--------|----------|
| `constrain_on_bootstrap` (default) | Rule files are read only during `/order.bootstrap`. Content is offered for integration into `conventions.md`. After bootstrap, OrderSpec commands work only with their own contracts. |
| `constrain_always` | Rule files are resolved by the command context resolver as `constrain` source for every command. May conflict with OrderSpec contracts. Use with caution. |
| `ignore` | Rule files are not read by OrderSpec at all. Operator manually transfers needed content to `conventions.md`. |

To change this policy, amend this section via `/order.bootstrap` and set the policy to one of the three values above.

## Governance

- This constitution supersedes lower-level project practices and feature artifacts within the limits of `.orderspec/framework/orderspec-rules.md`.\n- On conflict with framework rules, `.orderspec/framework/orderspec-rules.md` wins.
- Amendments are made only via `/order.bootstrap`, which routes conflicting artifacts to their owning commands.
- Default-deny on capabilities is non-negotiable: unstated => denied.

**Last Amended**: {today()}
"""

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


def validate_created_files() -> list[str]:
    errors = []

    if PROJECT_DOCS["stack"].exists():
        errors.extend(validate_stack(PROJECT_DOCS["stack"]))
    else:
        errors.append("stack.md missing")

    if PROJECT_DOCS["architecture"].exists():
        errors.extend(validate_architecture(PROJECT_DOCS["architecture"]))
    else:
        errors.append("architecture.md missing")

    if not PROJECT_DOCS["conventions"].exists():
        errors.append("conventions.md missing")

    if not PROJECT_DOCS["constitution"].exists():
        errors.append("constitution.md missing")
    else:
        constitution = PROJECT_DOCS["constitution"].read_text(encoding="utf-8")
        if "[BRACKET]" in constitution or "__PLACEHOLDER__" in constitution:
            errors.append("constitution.md contains unresolved placeholder token")
        if "DENIED" not in constitution and "ALLOWED" not in constitution:
            errors.append("constitution.md contains no capability grants")

    return errors

# Note: External Rules Integration section validation is intentionally lenient.
# If the section is missing, bootstrap will add it. If policy value is missing
# or invalid, the default `constrain_on_bootstrap` applies (see orderspec-rules.md).
# This is a soft check — the constitution is still valid without this section
# for backward compatibility with projects created before multi-agent support.


def inspect_command(args: argparse.Namespace) -> int:
    manifest = detect_manifest()
    missing_docs = missing_project_docs()

    result = {
        "mode": "init" if missing_docs else "amend",
        "missing_project_docs": missing_docs,
        "manifest": manifest,
        "project_name": detect_project_name(),
        "requires_gate_question": "constitution" in missing_docs,
        "recommended_gate_profile": "A",
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def init_command(args: argparse.Namespace) -> int:
    created: list[str] = []
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
    architecture_content = architecture_markdown()
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

    errors = validate_created_files()

    result = {
        "ok": not errors,
        "mode": "init",
        "created": created,
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
        choices=["constrain_on_bootstrap", "constrain_always", "ignore"],
        default="constrain_on_bootstrap",
        help="Policy for external AI agent rule files (default: constrain_on_bootstrap)",
    )

    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.command == "inspect":
        return inspect_command(args)
    if args.command == "init":
        return init_command(args)
    if args.command == "validate":
        return validate_command(args)

    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
