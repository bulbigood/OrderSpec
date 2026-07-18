#!/usr/bin/env python3
"""Project-contract, framework-rules, and protocol frontmatter regressions."""

from support.frontmatter import *  # noqa: F403

# ═══════════════════════════════════════════════════════════════════════════════
# project_contract tests
# ═══════════════════════════════════════════════════════════════════════════════

# 51. valid project_contract (stack)
p = write_file("pc_stack.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: project_contract\n"
    "  kind: stack\n"
    "  scope: project\n"
    "  owner_command: order.bootstrap\n"
    "  id_prefix: STACK\n"
    "---\n"
    "# Project Stack\n"
))
rc, data = run_vfm("project_contract", p)
if rc == 0 and data["ok"]:
    ok("51. valid project_contract (stack)")
else:
    bad("51. valid project_contract (stack)", f"rc={rc} data={data}")

# 52. valid project_contract (constitution)
p = write_file("pc_const.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: project_contract\n"
    "  kind: constitution\n"
    "  scope: project\n"
    "  owner_command: order.bootstrap\n"
    "  id_prefix: GOV\n"
    "---\n"
    "# Constitution\n"
))
rc, data = run_vfm("project_contract", p)
if rc == 0 and data["ok"]:
    ok("52. valid project_contract (constitution)")
else:
    bad("52. valid project_contract (constitution)", f"rc={rc} data={data}")

# 53. project_contract missing kind
p = write_file("pc_no_kind.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: project_contract\n"
    "---\n"
    "# Contract\n"
))
rc, data = run_vfm("project_contract", p)
if rc == 1 and not data["ok"]:
    fields = [e["field"] for e in data["errors"]]
    if "orderspec.kind" in fields:
        ok("53. project_contract missing kind → error")
    else:
        bad("53. project_contract missing kind", f"fields={fields}")
else:
    bad("53. project_contract missing kind", f"rc={rc} data={data}")

# 54. project_contract invalid kind
p = write_file("pc_bad_kind.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: project_contract\n"
    "  kind: invalid_kind\n"
    "---\n"
    "# Contract\n"
))
rc, data = run_vfm("project_contract", p)
if rc == 1 and not data["ok"]:
    msgs = " ".join(e["message"] for e in data["errors"])
    if "orderspec.kind must be one of" in msgs:
        ok("54. project_contract invalid kind → error")
    else:
        bad("54. project_contract invalid kind", f"msgs={msgs}")
else:
    bad("54. project_contract invalid kind", f"rc={rc} data={data}")

# 55. project_contract invalid artifact
p = write_file("pc_bad_art.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  kind: stack\n"
    "---\n"
    "# Contract\n"
))
rc, data = run_vfm("project_contract", p)
if rc == 1 and not data["ok"]:
    msgs = " ".join(e["message"] for e in data["errors"])
    if "must be 'project_contract'" in msgs:
        ok("55. project_contract invalid artifact → error")
    else:
        bad("55. project_contract invalid artifact", f"msgs={msgs}")
else:
    bad("55. project_contract invalid artifact", f"rc={rc} data={data}")

# 56. project_contract no frontmatter
p = write_file("pc_no_fm.md", "# Contract\n\nContent.\n")
rc, data = run_vfm("project_contract", p)
if rc == 1 and not data["ok"]:
    if any("No YAML frontmatter" in e["message"] for e in data["errors"]):
        ok("56. project_contract no frontmatter → error")
    else:
        bad("56. project_contract no frontmatter", f"errors={data['errors']}")
else:
    bad("56. project_contract no frontmatter", f"rc={rc} data={data}")

# 57. project_contract missing artifact and kind
p = write_file("pc_missing_both.md", (
    "---\n"
    "orderspec:\n"
    "  title: Stack\n"
    "---\n"
    "# Contract\n"
))
rc, data = run_vfm("project_contract", p)
if rc == 1 and not data["ok"]:
    fields = {e["field"] for e in data["errors"]}
    if "orderspec.artifact" in fields and "orderspec.kind" in fields:
        ok("57. project_contract missing artifact and kind → both flagged")
    else:
        bad("57. project_contract missing artifact and kind", f"fields={fields}")
else:
    bad("57. project_contract missing artifact and kind", f"rc={rc} data={data}")


# ═══════════════════════════════════════════════════════════════════════════════
# framework_rules tests
# ═══════════════════════════════════════════════════════════════════════════════

# 58. valid framework_rules frontmatter
p = write_file("fr_ok.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: framework_rules\n"
    "  authority: framework\n"
    "  customization: forbidden\n"
    "---\n"
    "# Rules\n"
))
rc, data = run_vfm("framework_rules", p)
if rc == 0 and data["ok"]:
    ok("58. valid framework_rules frontmatter")
else:
    bad("58. valid framework_rules frontmatter", f"rc={rc} data={data}")

# 59. framework_rules missing authority
p = write_file("fr_no_auth.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: framework_rules\n"
    "  customization: forbidden\n"
    "---\n"
    "# Rules\n"
))
rc, data = run_vfm("framework_rules", p)
if rc == 1 and not data["ok"]:
    fields = [e["field"] for e in data["errors"]]
    if "orderspec.authority" in fields:
        ok("59. framework_rules missing authority → error")
    else:
        bad("59. framework_rules missing authority", f"fields={fields}")
else:
    bad("59. framework_rules missing authority", f"rc={rc} data={data}")

# 60. framework_rules invalid authority
p = write_file("fr_bad_auth.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: framework_rules\n"
    "  authority: project\n"
    "  customization: forbidden\n"
    "---\n"
    "# Rules\n"
))
rc, data = run_vfm("framework_rules", p)
if rc == 1 and not data["ok"]:
    msgs = " ".join(e["message"] for e in data["errors"])
    if "orderspec.authority must be 'framework'" in msgs:
        ok("60. framework_rules invalid authority → error")
    else:
        bad("60. framework_rules invalid authority", f"msgs={msgs}")
else:
    bad("60. framework_rules invalid authority", f"rc={rc} data={data}")

# 61. framework_rules invalid customization
p = write_file("fr_bad_cust.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: framework_rules\n"
    "  authority: framework\n"
    "  customization: allowed\n"
    "---\n"
    "# Rules\n"
))
rc, data = run_vfm("framework_rules", p)
if rc == 1 and not data["ok"]:
    msgs = " ".join(e["message"] for e in data["errors"])
    if "orderspec.customization must be 'forbidden'" in msgs:
        ok("61. framework_rules invalid customization → error")
    else:
        bad("61. framework_rules invalid customization", f"msgs={msgs}")
else:
    bad("61. framework_rules invalid customization", f"rc={rc} data={data}")

# 62. framework_rules no frontmatter
p = write_file("fr_no_fm.md", "# Rules\n\nContent.\n")
rc, data = run_vfm("framework_rules", p)
if rc == 1 and not data["ok"]:
    if any("No YAML frontmatter" in e["message"] for e in data["errors"]):
        ok("62. framework_rules no frontmatter → error")
    else:
        bad("62. framework_rules no frontmatter", f"errors={data['errors']}")
else:
    bad("62. framework_rules no frontmatter", f"rc={rc} data={data}")

# 63. framework_rules missing all required fields
p = write_file("fr_empty.md", "---\norderspec:\n---\n# Rules\n")
rc, data = run_vfm("framework_rules", p)
if rc == 1 and not data["ok"]:
    expected = {"orderspec.artifact", "orderspec.authority", "orderspec.customization"}
    fields = {e["field"] for e in data["errors"]}
    if expected.issubset(fields):
        ok("63. framework_rules missing all required fields → all flagged")
    else:
        bad("63. framework_rules missing all required fields", f"fields={fields} expected={expected}")
else:
    bad("63. framework_rules missing all required fields", f"rc={rc} data={data}")


# ═══════════════════════════════════════════════════════════════════════════════
# protocol tests
# ═══════════════════════════════════════════════════════════════════════════════

# 64. valid protocol frontmatter
p = write_file("proto_ok.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: protocol\n"
    "---\n"
    "# Protocol\n"
))
rc, data = run_vfm("protocol", p)
if rc == 0 and data["ok"]:
    ok("64. valid protocol frontmatter")
else:
    bad("64. valid protocol frontmatter", f"rc={rc} data={data}")

# 65. protocol invalid artifact
p = write_file("proto_bad_art.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "---\n"
    "# Protocol\n"
))
rc, data = run_vfm("protocol", p)
if rc == 1 and not data["ok"]:
    msgs = " ".join(e["message"] for e in data["errors"])
    if "must be 'protocol'" in msgs:
        ok("65. protocol invalid artifact → error")
    else:
        bad("65. protocol invalid artifact", f"msgs={msgs}")
else:
    bad("65. protocol invalid artifact", f"rc={rc} data={data}")

# 66. protocol no frontmatter
p = write_file("proto_no_fm.md", "# Protocol\n\nContent.\n")
rc, data = run_vfm("protocol", p)
if rc == 1 and not data["ok"]:
    if any("No YAML frontmatter" in e["message"] for e in data["errors"]):
        ok("66. protocol no frontmatter → error")
    else:
        bad("66. protocol no frontmatter", f"errors={data['errors']}")
else:
    bad("66. protocol no frontmatter", f"rc={rc} data={data}")

# 67. protocol missing artifact
p = write_file("proto_no_art.md", "---\norderspec:\n---\n# Protocol\n")
rc, data = run_vfm("protocol", p)
if rc == 1 and not data["ok"]:
    fields = [e["field"] for e in data["errors"]]
    if "orderspec.artifact" in fields:
        ok("67. protocol missing artifact → error")
    else:
        bad("67. protocol missing artifact", f"fields={fields}")
else:
    bad("67. protocol missing artifact", f"rc={rc} data={data}")



finish()  # noqa: F405
