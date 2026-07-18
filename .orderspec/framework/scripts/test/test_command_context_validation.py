#!/usr/bin/env python3
"""Manifest validation and stable output contract regressions."""

from support.command_context import *  # noqa: F403

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





finish()  # noqa: F405
