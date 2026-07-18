#!/usr/bin/env python3
"""test-bootstrap-contracts.py — regression for deterministic bootstrap_contracts.py"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PY = sys.executable
BOOT = SCRIPT_DIR.parent / "bootstrap_contracts.py"

if not BOOT.exists():
    print(f"FATAL: bootstrap_contracts.py not found at {BOOT}", file=sys.stderr)
    sys.exit(2)

# ── Configuration ────────────────────────────────────────────────────────────

LOG_TO_FILE = False

TEST_DIR = SCRIPT_DIR
TEST_DIR.mkdir(parents=True, exist_ok=True)
LOG = TEST_DIR / "test-bootstrap-contracts.log"

if LOG_TO_FILE:
    LOG.write_text("", encoding="utf-8")

WORK = Path(tempfile.mkdtemp(prefix="orderspec-bootstrap-test-"))

pass_count = 0
fail_count = 0


def ok(name):
    global pass_count
    pass_count += 1
    msg = f"PASS: {name}"
    print(msg, flush=True)
    if LOG_TO_FILE:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")


def bad(name):
    global fail_count
    fail_count += 1
    msg = f"FAIL: {name}"
    print(msg, flush=True)
    if LOG_TO_FILE:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")


def reset_work():
    if WORK.exists():
        shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)


def mkdirp(path):
    path.mkdir(parents=True, exist_ok=True)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read(path):
    return path.read_text(encoding="utf-8")


def read_json(path):
    return json.loads(read(path))


def setup_package_json():
    write(
        WORK / "package.json",
        json.dumps(
            {
                "name": "node-express-boilerplate",
                "version": "1.0.0",
                "engines": {
                    "node": ">=12.0.0"
                },
                "dependencies": {
                    "bcryptjs": "^2.4.3",
                    "cors": "^2.8.5",
                    "dotenv": "^8.2.0",
                    "express": "^4.17.1",
                    "helmet": "^4.1.0",
                    "http-status": "^1.4.0",
                    "joi": "^17.3.0",
                    "jsonwebtoken": "^8.5.1",
                    "mongoose": "^5.7.7",
                    "morgan": "^1.10.0",
                    "nodemailer": "^6.3.1",
                    "passport": "^0.4.0",
                    "passport-jwt": "^4.0.0",
                    "swagger-jsdoc": "^6.0.8",
                    "swagger-ui-express": "^4.1.6",
                    "winston": "^3.2.1"
                },
                "devDependencies": {
                    "eslint": "^7.0.0"
                }
            },
            indent=2,
        )
        + "\n",
    )


def setup_pyproject_toml():
    write(
        WORK / "pyproject.toml",
        '[project]\n'
        'name = "fastapi-demo"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.11"\n'
        'dependencies = [\n'
        '    "fastapi>=0.100.0",\n'
        '    "sqlalchemy>=2.0.0",\n'
        '    "pydantic>=2.0.0",\n'
        '    "redis>=4.5.0",\n'
        '    "psycopg2-binary>=2.9.0",\n'
        ']\n'
        '\n'
        '[tool.poetry.dependencies]\n'
        'python = "^3.11"\n'
        'celery = "^5.3.0"\n'
    )


def setup_go_mod():
    write(
        WORK / "go.mod",
        "module example.com/myapp\n\n"
        "go 1.21\n\n"
        "require (\n"
        "    github.com/gin-gonic/gin v1.9.0\n"
        "    gorm.io/gorm v1.25.0\n"
        "    github.com/jackc/pgx v5.4.0\n"
        "    github.com/redis/go-redis v9.3.0\n"
        ")\n"
    )


def setup_cargo_toml():
    write(
        WORK / "Cargo.toml",
        '[package]\n'
        'name = "my-rust-app"\n'
        'version = "0.1.0"\n'
        'rust-version = "1.70"\n'
        '\n'
        '[dependencies]\n'
        'tokio = { version = "1.32", features = ["full"] }\n'
        'axum = "0.7"\n'
        'sqlx = { version = "0.7", features = ["postgres"] }\n'
        'serde = { version = "1.0", features = ["derive"] }\n'
        'reqwest = "0.11"\n'
    )


def setup_pom_xml():
    write(
        WORK / "pom.xml",
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<project xmlns="http://maven.apache.org/POM/4.0.0"\n'
        '         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n'
        '         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">\n'
        '    <modelVersion>4.0.0</modelVersion>\n'
        '    <groupId>com.example</groupId>\n'
        '    <artifactId>my-java-app</artifactId>\n'
        '    <version>1.0.0</version>\n'
        '\n'
        '    <properties>\n'
        '        <maven.compiler.source>17</maven.compiler.source>\n'
        '        <maven.compiler.target>17</maven.compiler.target>\n'
        '    </properties>\n'
        '\n'
        '    <dependencies>\n'
        '        <dependency>\n'
        '            <groupId>org.springframework.boot</groupId>\n'
        '            <artifactId>spring-boot-starter-web</artifactId>\n'
        '            <version>3.1.0</version>\n'
        '        </dependency>\n'
        '        <dependency>\n'
        '            <groupId>org.postgresql</groupId>\n'
        '            <artifactId>postgresql</artifactId>\n'
        '            <version>42.6.0</version>\n'
        '        </dependency>\n'
        '        <dependency>\n'
        '            <groupId>redis.clients</groupId>\n'
        '            <artifactId>jedis</artifactId>\n'
        '            <version>4.4.0</version>\n'
        '        </dependency>\n'
        '    </dependencies>\n'
        '</project>\n'
    )


def setup_layered_dirs():
    for name in [
        "config",
        "controllers",
        "docs",
        "middlewares",
        "models",
        "routes",
        "services",
        "utils",
        "validations",
    ]:
        mkdirp(WORK / "src" / name)


def run_boot(*args, input_text=None):
    cmd = [PY, str(BOOT)] + list(args)
    proc = subprocess.run(
        cmd,
        cwd=str(WORK),
        capture_output=True,
        text=True,
        input=input_text,
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_boot_json(*args):
    rc, out, err = run_boot(*args)
    try:
        data = json.loads(out)
    except Exception as exc:
        bad(f"invalid JSON output for {' '.join(args)} :: rc={rc} err={err!r} exc={exc} out={out!r}")
        return rc, {}, err
    return rc, data, err


def assert_exists(path, name):
    if (WORK / path).exists():
        ok(name)
    else:
        bad(f"{name} :: missing {path}")


def assert_not_exists(path, name):
    if not (WORK / path).exists():
        ok(name)
    else:
        bad(f"{name} :: unexpected {path}")


def init_a():
    return run_boot_json(
        "init",
        "--gate-profile",
        "A",
        "--json",
    )


# ── Tests ────────────────────────────────────────────────────────────────────

# 2. inspect detects init mode and gate question (no tooling defaults)
reset_work()
setup_package_json()
setup_layered_dirs()
rc, data, err = run_boot_json("inspect", "--json")
if (
    rc == 0
    and data.get("mode") == "init"
    and set(data.get("missing_project_docs", [])) == {"stack", "architecture", "conventions", "constitution"}
    and data.get("requires_gate_question") is True
    and data.get("recommended_gate_profile") == "A"
):
    ok("inspect detects init mode with all project docs missing")
else:
    bad(f"inspect init detection wrong :: rc={rc} data={data} err={err!r}")


# 3. init A creates all bootstrap-owned artifacts and passes validation
reset_work()
setup_package_json()
setup_layered_dirs()
rc, data, err = init_a()
if rc == 0 and data.get("ok") is True and not data.get("validation_errors"):
    ok("init A creates artifacts and passes validation")
else:
    bad(f"init A failed :: rc={rc} data={data} err={err!r}")

for rel in [
    ".orderspec/contracts/stack.md",
    ".orderspec/contracts/architecture.md",
    ".orderspec/contracts/conventions.md",
    ".orderspec/contracts/constitution.md",
]:
    assert_exists(rel, f"{rel} created")


# 4. init A creates tooling.json with explicit defaults
assert_exists(".orderspec/config/tooling.json", "tooling.json created by init")
tooling = read_json(WORK / ".orderspec/config/tooling.json")
if (
    tooling.get("version") == 3
    and tooling.get("skills", {}).get("install_policy") == "ask_user"
    and ".orderspec/skills/" in tooling.get("skills", {}).get("resolution_order", [])
    and tooling.get("skills", {}).get("bindings") == []
    and tooling.get("docs_sources", {}).get("context7", {}).get("policy") == "required_if_available"
):
    ok("tooling.json has correct shape with explicit defaults")
else:
    bad(f"tooling.json shape wrong :: {tooling}")

for kind, prefix in [("stack", "STACK"), ("architecture", "ARCH"), ("conventions", "CONV"), ("constitution", "GOV")]:
    contract = read(WORK / ".orderspec/contracts" / f"{kind}.md")
    if f"kind: {kind}" in contract and "scope: project" in contract and f"id_prefix: {prefix}" in contract:
        ok(f"{kind} has canonical project-contract frontmatter")
    else:
        bad(f"{kind} frontmatter wrong :: {contract[:300]!r}")

constitution = read(WORK / ".orderspec/contracts/constitution.md")
if all(value in constitution for value in ["GOV-001", "Project Intent (Non-Normative)", "## Governance Rules"]):
    ok("constitution separates non-normative intent from GOV rules")
else:
    bad(f"constitution governance structure wrong :: {constitution[:1200]!r}")


# 5. validate passes after init
rc, data, err = run_boot_json("validate", "--json")
if rc == 0 and data.get("ok") is True:
    ok("validate passes after init")
else:
    bad(f"validate failed after init :: rc={rc} data={data} err={err!r}")


# 6. contracts live under .orderspec/contracts/; old memory path is not created; nothing at repo root
assert_not_exists(".orderspec/memory/constitution.md", "old .orderspec/memory/constitution.md not created")


# 7. stack contains Node/Express/Mongoose/Joi/Passport and excludes eslint devDependency
stack = read(WORK / ".orderspec/contracts/stack.md")
if all(s in stack for s in ["STACK-001", "Node.js", "Express", "Mongoose", "Joi", "Passport"]) and "eslint" not in stack:
    ok("stack inference includes runtime/key dependencies and excludes dev tooling")
else:
    bad(f"stack inference wrong ::\n{stack}")


# 8. MongoDB server version is not misrepresented as Mongoose version
if "MongoDB" in stack and "[UNRESOLVED: MongoDB server version not declared in package.json]" in stack:
    ok("MongoDB server version unresolved instead of using Mongoose version")
else:
    bad(f"MongoDB version handling wrong ::\n{stack}")


# 9. architecture uses explicit allowed dependency rules and avoids broad contradictory blanket
arch = read(WORK / ".orderspec/contracts/architecture.md")
if (
    "ARCH-001" in arch
    and "ARCH-006" in arch
    and "No layer MAY import from a sibling or shallower layer" not in arch
):
    ok("architecture avoids broad contradictory blanket rule")
else:
    bad(f"architecture rules look unsafe ::\n{arch}")


# 10. conventions starts empty with no invented CONV-NNN rows
conv = read(WORK / ".orderspec/contracts/conventions.md")
if "CONV-001" not in conv and "| ID | Convention | Description | Notes |" in conv:
    ok("conventions starts empty with no invented CONV-NNN rows")
else:
    bad(f"conventions should be empty ::\n{conv}")


# 11. no-overwrite preserves existing valid stack.md
reset_work()
setup_package_json()
setup_layered_dirs()
write(
    WORK / ".orderspec/contracts/stack.md",
    "# Existing Stack\n"
    "\n"
    "DO NOT OVERWRITE\n"
    "\n"
    "| ID | Technology | Version | Purpose | Notes |\n"
    "|----|------------|---------|---------|-------|\n"
    "| STACK-999 | Existing Runtime | 1.x | Runtime | Existing valid row |\n"
)
rc, data, err = init_a()
stack_after = read(WORK / ".orderspec/contracts/stack.md")
if rc == 0 and "DO NOT OVERWRITE" in stack_after and ".orderspec/contracts/stack.md" not in data.get("created", []):
    ok("init preserves existing valid stack.md")
else:
    bad(f"no-overwrite failed :: rc={rc} data={data} stack={stack_after!r} err={err!r}")


# 12. no-overwrite still creates missing sibling docs
for rel in [
    ".orderspec/contracts/architecture.md",
    ".orderspec/contracts/conventions.md",
    ".orderspec/contracts/constitution.md",
]:
    assert_exists(rel, f"no-overwrite init still creates {rel}")


# 13. gate profile B records unresolved commands when commands are omitted
reset_work()
setup_package_json()
setup_layered_dirs()
rc, data, err = run_boot_json("init", "--gate-profile", "B", "--json")
constitution = read(WORK / ".orderspec/contracts/constitution.md")
if rc == 0 and "[UNRESOLVED: TEST_COMMAND]" in constitution and "[UNRESOLVED: LINT_COMMAND]" in constitution:
    ok("gate profile B records unresolved commands when omitted")
else:
    bad(f"gate profile B unresolved handling wrong :: rc={rc} data={data} constitution={constitution!r} err={err!r}")


# 14. gate profile B writes provided commands
reset_work()
setup_package_json()
setup_layered_dirs()
rc, data, err = run_boot_json(
    "init",
    "--gate-profile",
    "B",
    "--test-command",
    "npm test",
    "--lint-command",
    "npm run lint",
    "--json",
)
constitution = read(WORK / ".orderspec/contracts/constitution.md")
if rc == 0 and "ALLOWED. run: npm test" in constitution and "ALLOWED. run: npm run lint" in constitution:
    ok("gate profile B writes provided commands")
else:
    bad(f"gate profile B command handling wrong :: rc={rc} data={data} constitution={constitution!r} err={err!r}")


# 15. invalid gate profile is rejected by argparse
reset_work()
setup_package_json()
setup_layered_dirs()
rc, out, err = run_boot("init", "--gate-profile", "Z", "--json")
if rc != 0:
    ok("invalid gate profile rejected")
else:
    bad(f"invalid gate profile accepted :: out={out!r} err={err!r}")


# 16. inspect after init reports Refine and migrates persisted lifecycle state
reset_work()
setup_package_json()
setup_layered_dirs()
rc, data, err = init_a()
rc, data, err = run_boot_json("inspect", "--json")
if (
    rc == 0
    and data.get("mode") == "refine"
    and data.get("state_migration_required") is True
    and data.get("missing_project_docs") == []
):
    ok("inspect after init defaults to Refine with legacy-state migration")
else:
    bad(f"inspect after init wrong :: rc={rc} data={data} err={err!r}")

rc, completed, err = run_boot_json("complete", "--json")
rc2, inspected, err2 = run_boot_json("inspect", "--json")
if (
    rc == 0
    and completed.get("ok") is True
    and (WORK / ".orderspec/state/bootstrap.json").is_file()
    and (WORK / ".orderspec/state/active-feature.json").is_file()
    and read_json(WORK / ".orderspec/state/active-feature.json").get("active") is False
    and rc2 == 0
    and inspected.get("state_source") == "state"
    and inspected.get("state_migration_required") is False
):
    ok("complete persists bootstrap and canonical inactive feature state")
else:
    bad(f"bootstrap state persistence wrong :: complete={completed} inspect={inspected} err={err!r} {err2!r}")

rc, audit, err = run_boot_json("audit", "--json")
if (
    rc == 0
    and audit.get("mode") == "refine"
    and audit.get("items") == []
    and "feature specification drift" in audit.get("scope", {}).get("excludes", [])
    and "code-to-spec drift" in audit.get("scope", {}).get("excludes", [])
):
    ok("audit emits deterministic Refine evidence")
else:
    bad(f"bootstrap audit wrong :: rc={rc} data={audit} err={err!r}")

# Legacy contract metadata has a dedicated safe migration path.
stack_path = WORK / ".orderspec/contracts/stack.md"
stack_with_frontmatter = read(stack_path)
write(stack_path, stack_with_frontmatter.split("---\n", 2)[2].lstrip("\n"))
rc, legacy_audit, err = run_boot_json("audit", "--json")
safe_items = [item for item in legacy_audit.get("items", []) if item.get("classification") == "safe_mechanical_migration"]
rc2, migration, err2 = run_boot_json("migrate-frontmatter", "--json")
rc3, validated, err3 = run_boot_json("validate", "--json")
if rc == 1 and safe_items and rc2 == 0 and migration.get("contracts_valid") is True and rc3 == 0:
    ok("Refine routes legacy frontmatter through safe deterministic migration")
else:
    bad(f"legacy frontmatter migration wrong :: audit={legacy_audit} migration={migration} validate={validated} err={err!r} {err2!r} {err3!r}")
run_boot_json("complete", "--json")

# Refine deliberately ignores feature/code drift.
write(WORK / ".orderspec/features/001-demo/spec.md", "changed feature specification\n")
write(WORK / "src/application.py", "print('changed implementation')\n")
rc, audit, err = run_boot_json("audit", "--json")
if rc == 0 and audit.get("items") == []:
    ok("audit ignores feature and implementation drift")
else:
    bad(f"audit inspected out-of-scope feature/code drift :: rc={rc} data={audit} err={err!r}")

# Manifest state change produces structured project-rule review items.
package = read_json(WORK / "package.json")
package["dependencies"]["express"] = "^5.0.0"
write(WORK / "package.json", json.dumps(package, indent=2) + "\n")
rc, audit, err = run_boot_json("audit", "--json")
kinds = {item.get("kind") for item in audit.get("items", [])}
if rc == 0 and "project_state_manifest_changed" in kinds:
    ok("audit reports manifest state drift as structured project-rule evidence")
else:
    bad(f"manifest drift not reported :: rc={rc} data={audit} err={err!r}")

# Constitution synthesis collects bounded candidates but grants no authority.
write(WORK / "docs/governance.md", "# Mission\nBuild reliable systems.\n\n# Constraints\nPublic APIs MUST be versioned.\n")
rc, evidence, err = run_boot_json("constitution-evidence", "--json")
if (
    rc == 0
    and evidence.get("requires_operator_approval") is True
    and any(item.get("authority") == "candidate_only" for item in evidence.get("candidates", []))
    and any("Public APIs MUST be versioned" in item.get("statement", "") for item in evidence.get("candidates", []))
):
    ok("constitution synthesis emits bounded non-authoritative candidates")
else:
    bad(f"constitution evidence wrong :: rc={rc} data={evidence} err={err!r}")


# 18. malformed package.json fails cleanly
reset_work()
write(WORK / "package.json", "{not json\n")
rc, out, err = run_boot("init", "--gate-profile", "A", "--json")
if rc != 0:
    ok("malformed package.json rejected")
else:
    bad(f"malformed package.json accepted :: out={out!r} err={err!r}")


# 19. Python (pyproject.toml) inference detects FastAPI/SQLAlchemy/Pydantic/Redis/Celery
reset_work()
setup_pyproject_toml()
rc, data, err = init_a()
stack = read(WORK / ".orderspec/contracts/stack.md")
if (
    rc == 0
    and "Python" in stack
    and "FastAPI" in stack
    and "SQLAlchemy" in stack
    and "Pydantic" in stack
    and "Redis-py" in stack
    and "Celery" in stack
    and "psycopg2" in stack
):
    ok("Python inference detects all key packages from pyproject.toml")
else:
    bad(f"Python inference wrong :: rc={rc} data={data} stack={stack!r} err={err!r}")


# 20. Go (go.mod) inference detects Gin/GORM/pgx/go-redis
reset_work()
setup_go_mod()
rc, data, err = init_a()
stack = read(WORK / ".orderspec/contracts/stack.md")
if (
    rc == 0
    and "Go" in stack
    and "Gin" in stack
    and "GORM" in stack
    and "pgx" in stack
    and "go-redis" in stack
):
    ok("Go inference detects all key packages from go.mod")
else:
    bad(f"Go inference wrong :: rc={rc} data={data} stack={stack!r} err={err!r}")


# 21. Rust (Cargo.toml) inference detects Tokio/Axum/SQLx/Serde/Reqwest
reset_work()
setup_cargo_toml()
rc, data, err = init_a()
stack = read(WORK / ".orderspec/contracts/stack.md")
if (
    rc == 0
    and "Rust" in stack
    and "Tokio" in stack
    and "Axum" in stack
    and "SQLx" in stack
    and "Serde" in stack
    and "Reqwest" in stack
):
    ok("Rust inference detects all key crates from Cargo.toml")
else:
    bad(f"Rust inference wrong :: rc={rc} data={data} stack={stack!r} err={err!r}")


# 22. Java (pom.xml) inference detects Spring Boot/PostgreSQL/Jedis
reset_work()
setup_pom_xml()
rc, data, err = init_a()
stack = read(WORK / ".orderspec/contracts/stack.md")
if (
    rc == 0
    and "Java" in stack
    and "17" in stack
    and "Spring Boot Web" in stack
    and "PostgreSQL JDBC" in stack
    and "Jedis" in stack
):
    ok("Java inference detects all key artifacts from pom.xml")
else:
    bad(f"Java inference wrong :: rc={rc} data={data} stack={stack!r} err={err!r}")


# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
if LOG_TO_FILE:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{pass_count} passed, {fail_count} failed\n")

sys.exit(0 if fail_count == 0 else 1)
