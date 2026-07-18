#!/usr/bin/env python3
"""Resource reference and group expansion regressions."""

from support.command_context import *  # noqa: F403

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



finish()  # noqa: F405
