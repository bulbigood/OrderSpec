#!/usr/bin/env python3
"""Core manifest loading and context resolution regressions."""

from support.command_context import *  # noqa: F403

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



finish()  # noqa: F405
