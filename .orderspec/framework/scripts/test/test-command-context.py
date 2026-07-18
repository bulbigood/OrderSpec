#!/usr/bin/env python3
"""test-command-context.py — regression for command_context.py"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PY = sys.executable
COMMAND_CONTEXT = SCRIPT_DIR.parent / "command_context.py"

if not COMMAND_CONTEXT.exists():
    print(f"FATAL: command_context.py not found at {COMMAND_CONTEXT}", file=sys.stderr)
    sys.exit(2)

LOG_TO_FILE = False

TEST_DIR = SCRIPT_DIR / "test"
TEST_DIR.mkdir(parents=True, exist_ok=True)
LOG = TEST_DIR / "test-command-context.log"

if LOG_TO_FILE:
    LOG.write_text("", encoding="utf-8")

WORK = Path(tempfile.mkdtemp(prefix="orderspec-command-context-test-"))

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


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def manifest_path():
    return WORK / ".orderspec" / "framework" / "command-context.json"


def put_manifest(data):
    write(manifest_path(), json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def run_cc(*args, input_text=None):
    cmd = [PY, str(COMMAND_CONTEXT), "-C", str(WORK)] + list(args)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_text,
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_cc_json(*args):
    rc, out, err = run_cc(*args)
    try:
        data = json.loads(out)
    except Exception as exc:
        bad(f"invalid JSON output for {' '.join(args)} :: rc={rc} err={err!r} exc={exc} out={out!r}")
        return rc, {}, err
    return rc, data, err


def setup_base_files(
    with_contracts=True,
    with_tooling_protocol=True,
    with_tooling_config=False,
):
    write(WORK / ".orderspec" / "framework" / "orderspec-rules.md", "# Rules\n")
    write(WORK / ".orderspec" / "framework" / "orderspec-identifiers.md", "# IDs\n")
    write(WORK / ".orderspec" / "framework" / "schemas" / "command-context.schema.json", "{}\n")

    if with_tooling_protocol:
        write(
            WORK / ".orderspec" / "framework" / "protocols" / "tooling-protocol.md",
            "# Tooling Protocol\n",
        )
    write(
        WORK / ".orderspec" / "framework" / "protocols" / "sub-agent-execution.md",
        "# Sub-agent Execution\n",
    )
    write(
        WORK / ".orderspec" / "framework" / "protocols" / "sub-agent-rules.md",
        "# Sub-agent Rules\n",
    )
    write(
        WORK / ".orderspec" / "framework" / "protocols" / "environment-block.md",
        "# Environment Block Protocol\n",
    )
    write(WORK / ".orderspec" / "framework" / "schemas" / "task-context.schema.json", "{}\n")


    if with_contracts:
        write(WORK / "constitution.md", "# Constitution\n")
        write(WORK / "stack.md", "# Stack\n")
        write(WORK / "architecture.md", "# Architecture\n")
        write(WORK / "conventions.md", "# Conventions\n")
        write(WORK / ".orderspec" / "contracts" / "constitution.md", "# Constitution\n")
        write(WORK / ".orderspec" / "contracts" / "stack.md", "# Stack\n")
        write(WORK / ".orderspec" / "contracts" / "architecture.md", "# Architecture\n")
        write(WORK / ".orderspec" / "contracts" / "conventions.md", "# Conventions\n")

    if with_tooling_config:
        write(WORK / ".orderspec" / "config" / "tooling.json", "{}\n")


def base_manifest():
    return {
        "version": 2,
        "defaults": {
            "required": [
                {
                    "path": ".orderspec/framework/orderspec-rules.md",
                    "kind": "framework_rules",
                    "usage": "apply",
                    "authority": "framework",
                    "reason": "global framework rules",
                },
                {
                    "path": ".orderspec/framework/schemas/command-context.schema.json",
                    "kind": "schema",
                    "usage": "parse",
                    "authority": "framework",
                    "reason": "command context manifest schema",
                },
                {
                    "path": ".orderspec/framework/orderspec-identifiers.md",
                    "kind": "framework_rules",
                    "usage": "apply",
                    "authority": "framework",
                    "reason": "stable identifier prefixes and glossary",
                },
            ]
        },
        "commands": {
            "order.bootstrap": {
                "read_if_exists": [
                    {
                        "path": "constitution.md",
                        "kind": "project_contract",
                        "usage": "constrain",
                        "authority": "project",
                        "reason": "existing project governance",
                    },
                    {
                        "path": "stack.md",
                        "kind": "project_contract",
                        "usage": "constrain",
                        "authority": "project",
                        "reason": "existing project stack contract",
                    },
                    {
                        "path": "architecture.md",
                        "kind": "project_contract",
                        "usage": "constrain",
                        "authority": "project",
                        "reason": "existing project architecture contract",
                    },
                    {
                        "path": "conventions.md",
                        "kind": "project_contract",
                        "usage": "constrain",
                        "authority": "project",
                        "reason": "existing project conventions contract",
                    },
                ],
            },
            "order.spec": {
                "required": [
                    {
                        "path": "constitution.md",
                        "kind": "project_contract",
                        "usage": "constrain",
                        "authority": "project",
                        "reason": "project governance",
                    }
                ]
            },
            "order.plan": {
                "required": [
                    {
                        "path": ".orderspec/framework/protocols/tooling-protocol.md",
                        "kind": "protocol",
                        "usage": "apply",
                        "authority": "framework",
                        "reason": "tooling protocol",
                    },
                    {
                        "path": "constitution.md",
                        "kind": "project_contract",
                        "usage": "constrain",
                        "authority": "project",
                        "reason": "project governance",
                    },
                ],
                "read_if_exists": [
                    {
                        "path": ".orderspec/config/tooling.json",
                        "kind": "tooling_config",
                        "usage": "parse",
                        "authority": "operator_config",
                        "reason": "tooling config",
                    }
                ],
            },
        },
    }


def paths(data):
    return [item.get("path") for item in data.get("to_read", [])]


def item_by_path(data, path):
    for item in data.get("to_read", []):
        if item.get("path") == path:
            return item
    return None


def missing_required_paths(data):
    return [item.get("path") for item in data.get("missing_required", [])]


def skipped_paths(data):
    return [item.get("path") for item in data.get("skipped_if_missing", [])]


# ── Tests ────────────────────────────────────────────────────────────────────

# 1. missing manifest rejected
reset_work()
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
if rc != 0 and data.get("ok") is False and any("manifest not found" in e for e in data.get("validation_errors", [])):
    ok("missing manifest rejected")
else:
    bad(f"missing manifest wrong :: rc={rc} data={data} err={err!r}")


# 2. invalid manifest JSON rejected
reset_work()
write(manifest_path(), "{not json\n")
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
if rc != 0 and data.get("ok") is False and any("invalid manifest JSON" in e for e in data.get("validation_errors", [])):
    ok("invalid manifest JSON rejected")
else:
    bad(f"invalid manifest JSON wrong :: rc={rc} data={data} err={err!r}")


# 3. wrong manifest version rejected
reset_work()
put_manifest({"version": 999, "commands": {}})
rc, data, err = run_cc_json("list", "--json")
if rc != 0 and data.get("ok") is False and any("version must be 2" in e for e in data.get("validation_errors", [])):
    ok("wrong manifest version rejected")
else:
    bad(f"wrong manifest version wrong :: rc={rc} data={data} err={err!r}")


# 4. list returns sorted commands
reset_work()
setup_base_files()
put_manifest(base_manifest())
rc, data, err = run_cc_json("list", "--json")
if rc == 0 and data.get("commands") == ["order.bootstrap", "order.plan", "order.spec"]:
    ok("list returns sorted commands")
else:
    bad(f"list wrong :: rc={rc} data={data} err={err!r}")


# 5. resolve order.spec includes defaults, identifiers, and project contract
reset_work()
setup_base_files()
put_manifest(base_manifest())
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
p = paths(data)
if (
    rc == 0
    and data.get("ok") is True
    and ".orderspec/framework/orderspec-rules.md" in p
    and ".orderspec/framework/orderspec-identifiers.md" in p
    and ".orderspec/framework/schemas/command-context.schema.json" in p
    and "constitution.md" in p
    and ".orderspec/framework/protocols/tooling-protocol.md" not in p
):
    ok("resolve order.spec excludes tooling protocol, includes identifiers")
else:
    bad(f"resolve order.spec wrong :: rc={rc} data={data} err={err!r}")


# 6. resolve order.plan includes tooling protocol when explicitly required by manifest
reset_work()
setup_base_files()
put_manifest(base_manifest())
rc, data, err = run_cc_json("resolve", "order.plan", "--json")
p = paths(data)
if (
    rc == 0
    and data.get("ok") is True
    and ".orderspec/framework/protocols/tooling-protocol.md" in p
    and "constitution.md" in p
):
    ok("resolve order.plan includes tooling protocol when required by manifest")
else:
    bad(f"resolve order.plan wrong :: rc={rc} data={data} err={err!r}")


# 7. resolved items include usage and authority
reset_work()
setup_base_files()
put_manifest(base_manifest())
rc, data, err = run_cc_json("resolve", "order.plan", "--json")
rules = item_by_path(data, ".orderspec/framework/orderspec-rules.md")
tooling = item_by_path(data, ".orderspec/framework/protocols/tooling-protocol.md")
constitution = item_by_path(data, "constitution.md")
if (
    rc == 0
    and rules
    and rules.get("usage") == "apply"
    and rules.get("authority") == "framework"
    and tooling
    and tooling.get("usage") == "apply"
    and tooling.get("authority") == "framework"
    and constitution
    and constitution.get("usage") == "constrain"
    and constitution.get("authority") == "project"
):
    ok("resolved items include correct usage and authority")
else:
    bad(f"usage/authority wrong :: rc={rc} data={data} err={err!r}")


# 8. read_if_exists missing is skipped
reset_work()
setup_base_files(with_tooling_config=False)
put_manifest(base_manifest())
rc, data, err = run_cc_json("resolve", "order.plan", "--json")
if (
    rc == 0
    and ".orderspec/config/tooling.json" not in paths(data)
    and ".orderspec/config/tooling.json" in skipped_paths(data)
):
    ok("read_if_exists missing is skipped")
else:
    bad(f"read_if_exists missing wrong :: rc={rc} data={data} err={err!r}")


# 9. read_if_exists existing is included
reset_work()
setup_base_files(with_tooling_config=True)
put_manifest(base_manifest())
rc, data, err = run_cc_json("resolve", "order.plan", "--json")
tooling_config = item_by_path(data, ".orderspec/config/tooling.json")
if (
    rc == 0
    and tooling_config
    and tooling_config.get("usage") == "parse"
    and tooling_config.get("authority") == "operator_config"
):
    ok("read_if_exists existing included with parse/operator_config")
else:
    bad(f"read_if_exists existing wrong :: rc={rc} data={data} err={err!r}")


# 10. missing required rejected
reset_work()
setup_base_files(with_contracts=False)
put_manifest(base_manifest())
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
if rc != 0 and "constitution.md" in missing_required_paths(data):
    ok("missing required rejected")
else:
    bad(f"missing required wrong :: rc={rc} data={data} err={err!r}")


# 11. unknown command rejected
reset_work()
setup_base_files()
put_manifest(base_manifest())
rc, data, err = run_cc_json("resolve", "order.unknown", "--json")
if rc != 0 and any("unknown command" in e for e in data.get("validation_errors", [])):
    ok("unknown command rejected")
else:
    bad(f"unknown command wrong :: rc={rc} data={data} err={err!r}")


# 12. required glob expands matches and preserves metadata
reset_work()
setup_base_files()
write(WORK / ".orderspec" / "framework" / "schemas" / "a.yml", "a: true\n")
write(WORK / ".orderspec" / "framework" / "schemas" / "b.yml", "b: true\n")
manifest = base_manifest()
manifest["defaults"]["required"].append(
    {
        "path": ".orderspec/framework/schemas/*.yml",
        "kind": "schema",
        "usage": "parse",
        "authority": "framework",
        "reason": "framework schemas",
    }
)
put_manifest(manifest)
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
a = item_by_path(data, ".orderspec/framework/schemas/a.yml")
b = item_by_path(data, ".orderspec/framework/schemas/b.yml")
if rc == 0 and a and b and a.get("usage") == "parse" and b.get("authority") == "framework":
    ok("required glob expands matches and preserves metadata")
else:
    bad(f"glob expansion wrong :: rc={rc} data={data} err={err!r}")


# 13. required glob with no matches rejected
reset_work()
setup_base_files()
manifest = base_manifest()
manifest["defaults"]["required"].append(
    {
        "path": ".orderspec/framework/missing-schemas/*.yml",
        "kind": "schema",
        "usage": "parse",
        "authority": "framework",
        "reason": "missing schemas",
    }
)
put_manifest(manifest)
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
if rc != 0 and ".orderspec/framework/missing-schemas/*.yml" in missing_required_paths(data):
    ok("required glob with no matches rejected")
else:
    bad(f"required glob no match wrong :: rc={rc} data={data} err={err!r}")


# 14. unsafe relative path rejected
reset_work()
setup_base_files()
manifest = base_manifest()
manifest["commands"]["order.spec"]["required"].append(
    {
        "path": "../outside.md",
        "kind": "file",
        "usage": "reference",
        "authority": "external",
        "reason": "unsafe path",
    }
)
put_manifest(manifest)
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
if rc != 0 and any("safe relative path" in e for e in data.get("validation_errors", [])):
    ok("unsafe relative path rejected")
else:
    bad(f"unsafe path wrong :: rc={rc} data={data} err={err!r}")


# 15. absolute path rejected
reset_work()
setup_base_files()
manifest = base_manifest()
manifest["commands"]["order.spec"]["required"].append(
    {
        "path": str(WORK / "outside.md"),
        "kind": "file",
        "usage": "reference",
        "authority": "external",
        "reason": "absolute path",
    }
)
put_manifest(manifest)
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
if rc != 0 and any("safe relative path" in e for e in data.get("validation_errors", [])):
    ok("absolute path rejected")
else:
    bad(f"absolute path wrong :: rc={rc} data={data} err={err!r}")


# 16. invalid usage rejected
reset_work()
setup_base_files()
manifest = base_manifest()
manifest["commands"]["order.spec"]["required"].append(
    {
        "path": "stack.md",
        "kind": "project_contract",
        "usage": "execute",
        "authority": "project",
        "reason": "bad usage",
    }
)
put_manifest(manifest)
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
if rc != 0 and any("entry.usage must be one of" in e for e in data.get("validation_errors", [])):
    ok("invalid usage rejected")
else:
    bad(f"invalid usage wrong :: rc={rc} data={data} err={err!r}")


# 17. invalid authority rejected
reset_work()
setup_base_files()
manifest = base_manifest()
manifest["commands"]["order.spec"]["required"].append(
    {
        "path": "stack.md",
        "kind": "project_contract",
        "usage": "constrain",
        "authority": "agent",
        "reason": "bad authority",
    }
)
put_manifest(manifest)
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
if rc != 0 and any("entry.authority must be one of" in e for e in data.get("validation_errors", [])):
    ok("invalid authority rejected")
else:
    bad(f"invalid authority wrong :: rc={rc} data={data} err={err!r}")


# 18. missing usage and authority are rejected
reset_work()
setup_base_files()
write(WORK / "extra.md", "# Extra\\n")
manifest = {
    "version": 2,
    "defaults": {
        "required": [
            {
                "path": ".orderspec/framework/orderspec-rules.md",
                "kind": "framework_rules",
                "reason": "global framework rules",
            }
        ]
    },
    "commands": {
        "order.spec": {
            "required": [
                {
                    "path": "extra.md",
                    "kind": "reference",
                    "reason": "extra reference",
                }
            ]
        }
    }
}
put_manifest(manifest)
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
errors = data.get("validation_errors", [])
if (
    rc != 0
    and any("entry.usage must be one of" in e for e in errors)
    and any("entry.authority must be one of" in e for e in errors)
):
    ok("missing usage and authority are rejected")
else:
    bad(f"missing usage/authority should be rejected :: rc={rc} data={data} err={err!r}")

# 19. string entries are rejected
reset_work()
setup_base_files()
write(WORK / "extra.md", "# Extra\\n")
manifest = {
    "version": 2,
    "defaults": {
        "required": [".orderspec/framework/orderspec-rules.md"]
    },
    "commands": {
        "order.spec": {
            "required": ["extra.md"]
        }
    }
}
put_manifest(manifest)
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
if rc != 0 and any("string entries are not supported" in e for e in data.get("validation_errors", [])):
    ok("string entries are rejected")
else:
    bad(f"string entries should be rejected :: rc={rc} data={data} err={err!r}")

# 20. duplicate paths are de-duplicated
reset_work()
setup_base_files()
manifest = base_manifest()
manifest["commands"]["order.spec"]["required"].append(
    {
        "path": ".orderspec/framework/orderspec-rules.md",
        "kind": "framework_rules",
        "usage": "apply",
        "authority": "framework",
        "reason": "duplicate",
    }
)
put_manifest(manifest)
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
p = paths(data)
if rc == 0 and p.count(".orderspec/framework/orderspec-rules.md") == 1:
    ok("duplicate paths de-duplicated")
else:
    bad(f"dedupe wrong :: rc={rc} paths={p} data={data} err={err!r}")


# 21. validate passes when required files exist
reset_work()
setup_base_files()
put_manifest(base_manifest())
rc, data, err = run_cc_json("validate", "--json")
if rc == 0 and data.get("ok") is True and data.get("validation_errors") == []:
    ok("validate passes when required files exist")
else:
    bad(f"validate should pass :: rc={rc} data={data} err={err!r}")


# 22. validate fails when required files are missing
reset_work()
setup_base_files(with_contracts=False)
put_manifest(base_manifest())
rc, data, err = run_cc_json("validate", "--json")
if rc != 0 and data.get("ok") is False and "order.spec: invalid context" in data.get("validation_errors", []):
    ok("validate fails when required files missing")
else:
    bad(f"validate should fail :: rc={rc} data={data} err={err!r}")


# 23. unsupported alias key is rejected
reset_work()
setup_base_files(with_tooling_config=True)
manifest = base_manifest()
alias_key = "op" + "tional"
manifest["commands"]["order.plan"].pop("read_if_exists", None)
manifest["commands"]["order.plan"][alias_key] = [
    {
        "path": ".orderspec/config/tooling.json",
        "kind": "tooling_config",
        "usage": "parse",
        "authority": "operator_config",
        "reason": "unsupported alias compatibility check",
    }
]
put_manifest(manifest)
rc, data, err = run_cc_json("resolve", "order.plan", "--json")
expected = alias_key + " is not supported"
if rc != 0 and any(expected in e for e in data.get("validation_errors", [])):
    ok("unsupported alias key is rejected")
else:
    bad(f"unsupported alias should be rejected :: rc={rc} data={data} err={err!r}")

# 24. non-list required group rejected
reset_work()
setup_base_files()
manifest = base_manifest()
manifest["commands"]["order.spec"]["required"] = {"path": "constitution.md"}
put_manifest(manifest)
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
if rc != 0 and any("commands.order.spec.required must be a list" in e for e in data.get("validation_errors", [])):
    ok("non-list required group rejected")
else:
    bad(f"non-list required wrong :: rc={rc} data={data} err={err!r}")


# 25. entry without path rejected
reset_work()
setup_base_files()
manifest = base_manifest()
manifest["commands"]["order.spec"]["required"].append(
    {
        "kind": "project_contract",
        "usage": "constrain",
        "authority": "project",
        "reason": "missing path",
    }
)
put_manifest(manifest)
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
if rc != 0 and any("entry.path must be a non-empty string" in e for e in data.get("validation_errors", [])):
    ok("entry without path rejected")
else:
    bad(f"missing path wrong :: rc={rc} data={data} err={err!r}")


# 26. expand=false read_if_exists missing is skipped
reset_work()
setup_base_files()
manifest = base_manifest()
manifest["commands"]["order.spec"]["read_if_exists"] = [
    {
        "path": ".orderspec/framework/protocols/*.md",
        "kind": "protocol_catalog",
        "usage": "reference",
        "authority": "framework",
        "reason": "protocol catalog",
        "expand": False,
    }
]
put_manifest(manifest)
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
if (
    rc == 0
    and ".orderspec/framework/protocols/*.md" not in paths(data)
    and ".orderspec/framework/protocols/*.md" in skipped_paths(data)
):
    ok("expand=false read_if_exists missing skipped")
else:
    bad(f"expand=false missing wrong :: rc={rc} data={data} err={err!r}")


# 27. resolve output keeps stable top-level fields
reset_work()
setup_base_files()
put_manifest(base_manifest())
rc, data, err = run_cc_json("resolve", "order.plan", "--json")
expected = {
    "ok",
    "command",
    "manifest",
    "to_read",
    "missing_required",
    "skipped_if_missing",
    "validation_errors",
}
if rc == 0 and expected.issubset(set(data.keys())):
    ok("resolve output keeps stable top-level fields")
else:
    bad(f"stable output fields wrong :: rc={rc} keys={sorted(data.keys())} data={data} err={err!r}")


# 28. resolved items keep stable metadata fields
reset_work()
setup_base_files()
put_manifest(base_manifest())
rc, data, err = run_cc_json("resolve", "order.plan", "--json")
required_fields = {
    "path",
    "kind",
    "usage",
    "authority",
    "required",
    "reason",
    "source",
    "exists",
    "expanded_from",
}
items = data.get("to_read", [])
if rc == 0 and items and all(required_fields.issubset(set(item.keys())) for item in items):
    ok("resolved items keep stable metadata fields")
else:
    bad(f"resolved metadata wrong :: rc={rc} items={items} data={data} err={err!r}")


# 29. order.bootstrap reads existing contracts and does not load command protocols
reset_work()
setup_base_files()
put_manifest(base_manifest())
rc, data, err = run_cc_json("resolve", "order.bootstrap", "--json")
p = paths(data)
protocol_paths = [
    value for value in p
    if isinstance(value, str) and value.startswith(".orderspec/framework/protocols/")
]
constitution = item_by_path(data, "constitution.md")
if (
    rc == 0
    and data.get("ok") is True
    and protocol_paths == []
    and constitution
    and constitution.get("usage") == "constrain"
    and constitution.get("authority") == "project"
):
    ok("order.bootstrap reads existing contracts and excludes command protocols")
else:
    bad(f"bootstrap context wrong :: rc={rc} protocols={protocol_paths} data={data} err={err!r}")




# 29a. real manifest: order.plan excludes schema YAMLs and tooling protocol
reset_work()
setup_base_files()
import shutil as _shutil
_real_manifest = Path(__file__).resolve().parents[2] / "command-context.json"
if _real_manifest.exists():
    _dst = WORK / ".orderspec" / "framework" / "command-context.json"
    _dst.parent.mkdir(parents=True, exist_ok=True)
    _shutil.copy2(_real_manifest, _dst)
    # also create template/schemas that real manifest references
    for _name in ("plan-template.md", "tasks-template.md", "spec-template.md", "report-template.md"):
        write(WORK / ".orderspec" / "framework" / "templates" / _name, f"# {_name}\n")
    for _name in ("frontmatter.yml", "artifacts.yml", "lifecycle.yml", "traceability.yml"):
        write(WORK / ".orderspec" / "framework" / "schemas" / _name, "kind: schema\n")
    write(WORK / ".orderspec" / "orderspec.json", '{"framework_version":"0.3.0","schema_versions":{}}\n')
    rc, data, err = run_cc_json("resolve", "order.plan", "--json")
    p = paths(data)
    excluded = [
        ".orderspec/framework/protocols/tooling-protocol.md",
        ".orderspec/framework/schemas/frontmatter.yml",
        ".orderspec/framework/schemas/artifacts.yml",
        ".orderspec/framework/schemas/lifecycle.yml",
        ".orderspec/framework/schemas/traceability.yml",
        ".orderspec/framework/templates/plan-template.md",
        ".orderspec/config/tooling.json",
        ".orderspec/orderspec.json",
    ]
    included = [
        ".orderspec/framework/orderspec-rules.md",
        ".orderspec/contracts/constitution.md",
        ".orderspec/contracts/stack.md",
        ".orderspec/contracts/architecture.md",
        ".orderspec/contracts/conventions.md",
    ]
    if (
        rc == 0
        and data.get("ok") is True
        and all(x not in p for x in excluded)
        and all(x in p for x in included)
    ):
        ok("real manifest: order.plan excludes schemas/protocol/template/tooling, includes rules+contracts")
    else:
        bad(f"real manifest order.plan wrong :: rc={rc} paths={p} err={err!r}")
else:
    ok("real manifest test skipped (manifest not found)")


# 29b. real manifest: no command returns framework.meta in to_read
reset_work()
setup_base_files()
if _real_manifest.exists():
    _shutil.copy2(_real_manifest, manifest_path())
    for _name in ("plan-template.md", "tasks-template.md", "spec-template.md", "report-template.md"):
        write(WORK / ".orderspec" / "framework" / "templates" / _name, f"# {_name}\n")
    for _name in ("frontmatter.yml", "artifacts.yml", "lifecycle.yml", "traceability.yml"):
        write(WORK / ".orderspec" / "framework" / "schemas" / _name, "kind: schema\n")
    write(WORK / ".orderspec" / "orderspec.json", '{"framework_version":"0.3.0","schema_versions":{}}\n')
    rc_list, data_list, err_list = run_cc_json("list", "--json")
    failed = []
    if rc_list == 0:
        for cmd_name in data_list.get("commands", []):
            rc_c, data_c, err_c = run_cc_json("resolve", cmd_name, "--json")
            p_c = paths(data_c)
            if ".orderspec/orderspec.json" in p_c:
                failed.append(cmd_name)
    if not failed:
        ok("real manifest: no command returns framework.meta in to_read")
    else:
        bad(f"framework.meta leaked for commands: {failed}")
else:
    ok("real manifest framework.meta test skipped")


# 29c. real manifest: order.plan preload contains project.contracts group
reset_work()
setup_base_files()
if _real_manifest.exists():
    _shutil.copy2(_real_manifest, manifest_path())
    for _name in ("plan-template.md", "tasks-template.md", "spec-template.md", "report-template.md"):
        write(WORK / ".orderspec" / "framework" / "templates" / _name, f"# {_name}\n")
    for _name in ("frontmatter.yml", "artifacts.yml", "lifecycle.yml", "traceability.yml"):
        write(WORK / ".orderspec" / "framework" / "schemas" / _name, "kind: schema\n")
    write(WORK / ".orderspec" / "orderspec.json", '{"framework_version":"0.3.0","schema_versions":{}}\n')
    rc, data, err = run_cc_json("resolve", "order.plan", "--json")
    p = paths(data)
    expected_contracts = [
        ".orderspec/contracts/constitution.md",
        ".orderspec/contracts/stack.md",
        ".orderspec/contracts/architecture.md",
        ".orderspec/contracts/conventions.md",
    ]
    if rc == 0 and all(c in p for c in expected_contracts):
        ok("real manifest: order.plan includes all project contracts")
    else:
        bad(f"order.plan contracts wrong :: rc={rc} paths={p} err={err!r}")
else:
    ok("real manifest contracts test skipped")


# 29d. real manifest: order.tasks excludes tooling protocol and schemas
reset_work()
setup_base_files()
if _real_manifest.exists():
    _shutil.copy2(_real_manifest, manifest_path())
    for _name in ("plan-template.md", "tasks-template.md", "spec-template.md", "report-template.md"):
        write(WORK / ".orderspec" / "framework" / "templates" / _name, f"# {_name}\n")
    for _name in ("frontmatter.yml", "artifacts.yml", "lifecycle.yml", "traceability.yml"):
        write(WORK / ".orderspec" / "framework" / "schemas" / _name, "kind: schema\n")
    write(WORK / ".orderspec" / "orderspec.json", '{"framework_version":"0.3.0","schema_versions":{}}\n')
    rc, data, err = run_cc_json("resolve", "order.tasks", "--json")
    p = paths(data)
    excluded = [
        ".orderspec/framework/protocols/tooling-protocol.md",
        ".orderspec/framework/schemas/frontmatter.yml",
        ".orderspec/framework/schemas/artifacts.yml",
        ".orderspec/framework/schemas/lifecycle.yml",
        ".orderspec/framework/schemas/traceability.yml",
        ".orderspec/config/tooling.json",
        ".orderspec/orderspec.json",
    ]
    if rc == 0 and all(x not in p for x in excluded):
        ok("real manifest: order.tasks excludes tooling protocol + schemas + tooling.json + meta")
    else:
        bad(f"order.tasks exclusions wrong :: rc={rc} paths={p} err={err!r}")
else:
    ok("real manifest order.tasks test skipped")


# 29e. real manifest: order.code excludes tooling protocol and schemas
reset_work()
setup_base_files()
if _real_manifest.exists():
    _shutil.copy2(_real_manifest, manifest_path())
    for _name in ("plan-template.md", "tasks-template.md", "spec-template.md", "report-template.md"):
        write(WORK / ".orderspec" / "framework" / "templates" / _name, f"# {_name}\n")
    for _name in ("frontmatter.yml", "artifacts.yml", "lifecycle.yml", "traceability.yml"):
        write(WORK / ".orderspec" / "framework" / "schemas" / _name, "kind: schema\n")
    write(WORK / ".orderspec" / "orderspec.json", '{"framework_version":"0.3.0","schema_versions":{}}\n')
    rc, data, err = run_cc_json("resolve", "order.code", "--json")
    p = paths(data)
    excluded = [
        ".orderspec/framework/protocols/tooling-protocol.md",
        ".orderspec/framework/schemas/frontmatter.yml",
        ".orderspec/framework/schemas/artifacts.yml",
        ".orderspec/framework/schemas/lifecycle.yml",
        ".orderspec/framework/schemas/traceability.yml",
        ".orderspec/config/tooling.json",
        ".orderspec/orderspec.json",
    ]
    if rc == 0 and all(x not in p for x in excluded):
        ok("real manifest: order.code excludes tooling protocol + schemas + tooling.json + meta")
    else:
        bad(f"order.code exclusions wrong :: rc={rc} paths={p} err={err!r}")
else:
    ok("real manifest order.code test skipped")


# 29f. real manifest: feature_context materializes active feature artifacts
reset_work()
setup_base_files()
if _real_manifest.exists():
    _shutil.copy2(_real_manifest, manifest_path())
    for _name in ("plan-template.md", "tasks-template.md", "spec-template.md", "report-template.md"):
        write(WORK / ".orderspec" / "framework" / "templates" / _name, f"# {_name}\n")
    feature = WORK / ".orderspec" / "features" / "001-demo"
    for _name in ("spec.md", "plan.md", "tasks.md"):
        write(feature / _name, f"# {_name}\n")
    write(
        WORK / ".orderspec" / "state" / "active-feature.json",
        json.dumps(
            {
                "feature_id": "001-demo",
                "feature_directory": ".orderspec/features/001-demo",
                "status": "tasks",
            }
        ),
    )
    rc, data, err = run_cc_json("resolve", "order.code", "--json")
    items = {item["path"]: item for item in data.get("to_read", [])}
    expected_feature_paths = {
        ".orderspec/features/001-demo/plan.md",
        ".orderspec/features/001-demo/tasks.md",
    }
    if (
        rc == 0
        and expected_feature_paths.issubset(items)
        and all(items[path]["authority"] == "feature" for path in expected_feature_paths)
        and all(items[path]["required"] is False for path in expected_feature_paths)
        and data.get("feature_context", {}).get("active") is True
        and data.get("feature_context", {}).get("mode") == "if_active"
    ):
        ok("real manifest: order.code preloads active feature plan and tasks when available")
    else:
        bad(f"order.code feature context wrong :: rc={rc} items={items} data={data} err={err!r}")
else:
    ok("real manifest feature context test skipped")


# 29g. real manifest: code-check feature artifacts are optional lifecycle inputs
reset_work()
setup_base_files()
if _real_manifest.exists():
    _shutil.copy2(_real_manifest, manifest_path())
    feature = WORK / ".orderspec" / "features" / "001-demo"
    write(feature / "spec.md", "# spec.md\n")
    write(
        WORK / ".orderspec" / "state" / "active-feature.json",
        json.dumps(
            {
                "feature_id": "001-demo",
                "feature_directory": ".orderspec/features/001-demo",
                "status": "implementing",
            }
        ),
    )
    rc, data, err = run_cc_json("resolve", "order.code-check", "--json")
    items = {item["path"]: item for item in data.get("to_read", [])}
    spec_path = ".orderspec/features/001-demo/spec.md"
    missing_paths = {item["path"] for item in data.get("missing_required", [])}
    if (
        rc == 0
        and data.get("ok") is True
        and spec_path in items
        and items[spec_path]["required"] is False
        and ".orderspec/features/001-demo/plan.md" not in missing_paths
        and ".orderspec/features/001-demo/tasks.md" not in missing_paths
        and data.get("feature_context", {}).get("mode") == "if_active"
    ):
        ok("real manifest: order.code-check treats feature lifecycle inputs as optional")
    else:
        bad(f"order.code-check feature context wrong :: rc={rc} items={items} data={data} err={err!r}")


# 30. v2 ref and group entries expand in order
reset_work()
setup_base_files()
manifest = {
    "version": 2,
    "resources": {
        "framework.rules": {
            "path": ".orderspec/framework/orderspec-rules.md",
            "kind": "framework_rules",
            "usage": "apply",
            "authority": "framework",
            "reason": "global framework rules",
        },
        "project.constitution": {
            "path": "constitution.md",
            "kind": "project_contract",
            "usage": "constrain",
            "authority": "project",
            "reason": "project governance",
        },
        "project.stack": {
            "path": "stack.md",
            "kind": "project_contract",
            "usage": "constrain",
            "authority": "project",
            "reason": "project stack",
        },
    },
    "groups": {
        "project.min": [
            {"ref": "project.constitution"},
            {"ref": "project.stack"},
        ]
    },
    "defaults": {
        "required": [
            {"ref": "framework.rules"}
        ]
    },
    "commands": {
        "order.spec": {
            "required": [
                {"group": "project.min"}
            ]
        }
    },
}
put_manifest(manifest)
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
p = paths(data)
if (
    rc == 0
    and p == [
        ".orderspec/framework/orderspec-rules.md",
        "constitution.md",
        "stack.md",
    ]
    and item_by_path(data, "constitution.md").get("source").endswith("ref:project.constitution")
):
    ok("v2 ref and group entries expand in order")
else:
    bad(f"v2 ref/group expansion wrong :: rc={rc} paths={p} data={data} err={err!r}")


# 31. unknown resource ref rejected
reset_work()
setup_base_files()
manifest = {
    "version": 2,
    "resources": {},
    "groups": {},
    "commands": {
        "order.spec": {
            "required": [
                {"ref": "missing.resource"}
            ]
        }
    },
}
put_manifest(manifest)
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
if rc != 0 and any("unknown resource ref: missing.resource" in e for e in data.get("validation_errors", [])):
    ok("unknown resource ref rejected")
else:
    bad(f"unknown ref wrong :: rc={rc} data={data} err={err!r}")


# 32. unknown group rejected
reset_work()
setup_base_files()
manifest = {
    "version": 2,
    "resources": {},
    "groups": {},
    "commands": {
        "order.spec": {
            "required": [
                {"group": "missing.group"}
            ]
        }
    },
}
put_manifest(manifest)
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
if rc != 0 and any("unknown group: missing.group" in e for e in data.get("validation_errors", [])):
    ok("unknown group rejected")
else:
    bad(f"unknown group wrong :: rc={rc} data={data} err={err!r}")


# 33. group cycle rejected
reset_work()
setup_base_files()
manifest = {
    "version": 2,
    "resources": {},
    "groups": {
        "a": [{"group": "b"}],
        "b": [{"group": "a"}],
    },
    "commands": {
        "order.spec": {
            "required": [
                {"group": "a"}
            ]
        }
    },
}
put_manifest(manifest)
rc, data, err = run_cc_json("resolve", "order.spec", "--json")
if rc != 0 and any("group cycle detected" in e for e in data.get("validation_errors", [])):
    ok("group cycle rejected")
else:
    bad(f"group cycle wrong :: rc={rc} data={data} err={err!r}")


# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
if LOG_TO_FILE:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{pass_count} passed, {fail_count} failed\n")

sys.exit(0 if fail_count == 0 else 1)
