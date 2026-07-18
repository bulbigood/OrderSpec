#!/usr/bin/env python3
"""Regressions against the framework-owned command-context manifest."""

from support.command_context import *  # noqa: F403

# 29a. real manifest: order.plan includes tooling protocol but excludes unrelated schemas/templates
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
        ".orderspec/framework/protocols/tooling-protocol.md",
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
        ok("real manifest: order.plan includes tooling protocol + contracts and excludes unrelated resources")
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


# 29d. real manifest: order.tasks includes its tooling protocol, excludes unrelated schemas
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
        ".orderspec/framework/schemas/frontmatter.yml",
        ".orderspec/framework/schemas/artifacts.yml",
        ".orderspec/framework/schemas/lifecycle.yml",
        ".orderspec/framework/schemas/traceability.yml",
        ".orderspec/config/tooling.json",
        ".orderspec/orderspec.json",
    ]
    if (
        rc == 0
        and ".orderspec/framework/protocols/tooling-protocol.md" in p
        and all(x not in p for x in excluded)
    ):
        ok("real manifest: order.tasks includes tooling protocol and excludes unrelated resources")
    else:
        bad(f"order.tasks exclusions wrong :: rc={rc} paths={p} err={err!r}")
else:
    ok("real manifest order.tasks test skipped")


# 29e. real manifest: order.code includes its tooling protocol, excludes unrelated schemas
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
        ".orderspec/framework/schemas/frontmatter.yml",
        ".orderspec/framework/schemas/artifacts.yml",
        ".orderspec/framework/schemas/lifecycle.yml",
        ".orderspec/framework/schemas/traceability.yml",
        ".orderspec/config/tooling.json",
        ".orderspec/orderspec.json",
    ]
    if (
        rc == 0
        and ".orderspec/framework/protocols/tooling-protocol.md" in p
        and all(x not in p for x in excluded)
    ):
        ok("real manifest: order.code includes tooling protocol and excludes unrelated resources")
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


# 29h. owner command intake includes open feature feedback
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
                "status": "specified",
            }
        ),
    )
    feedback = {
        "version": 1,
        "id": "FB-001",
        "scope": "feature",
        "status": "open",
        "source": "order.tasks",
        "target": "order.plan",
        "category": "mapping",
        "summary": "missing mapping",
        "evidence": "REQ-001 has no path",
        "location": "REQ-001",
        "requested_change": "map REQ-001",
    }
    write(feature / ".state" / "feedback" / "FB-001.json", json.dumps(feedback))
    write(feature / ".state" / "feedback" / "FB-002.json", "{broken")
    project_feedback = {
        **feedback,
        "id": "PFB-001",
        "scope": "project",
        "source": "order.bootstrap",
    }
    write(
        WORK / ".orderspec" / "state" / "feedback" / "PFB-001.json",
        json.dumps(project_feedback),
    )
    rc, data, err = run_cc_json("resolve", "order.plan", "--json")
    intake = data.get("feedback", {})
    if (
        rc == 0
        and intake.get("count") == 2
        and {item.get("id") for item in intake.get("open", [])} == {"FB-001", "PFB-001"}
        and len(intake.get("errors", [])) == 1
    ):
        ok("owner context merges project/feature feedback without making malformed peers fatal")
    else:
        bad(f"owner feedback intake wrong :: rc={rc} feedback={intake} err={err!r}")



finish()  # noqa: F405
