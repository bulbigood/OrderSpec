#!/usr/bin/env python3
"""Feature-spec frontmatter and nested-field validation regressions."""

from support.frontmatter import *  # noqa: F403

# ═══════════════════════════════════════════════════════════════════════════════
# spec tests (edge cases and nested field validation)
# ═══════════════════════════════════════════════════════════════════════════════

# 68. spec orderspec block is not a mapping
p = write_file("spec_bad_mapping.md", (
    "---\n"
    "orderspec: not_a_mapping\n"
    "---\n"
    "# Spec\n"
))
rc, data = run_vfm("spec", p)
if rc == 1 and not data["ok"]:
    msgs = " ".join(e["message"] for e in data["errors"])
    if "not a mapping" in msgs:
        ok("68. spec orderspec not a mapping → error")
    else:
        bad("68. spec orderspec not a mapping", f"msgs={msgs}")
else:
    bad("68. spec orderspec not a mapping", f"rc={rc} data={data}")

# 69. spec with malformed YAML (unclosed frontmatter)
p = write_file("spec_bad_yaml.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  feature_id: FEAT-001-test\n"
    "  slug: test\n"
    "  status: draft\n"
    "# Missing closing ---\n"
))
rc, data = run_vfm("spec", p)
if rc == 1 and not data["ok"]:
    if any("No YAML frontmatter" in e["message"] for e in data["errors"]):
        ok("69. spec malformed YAML (unclosed) → no frontmatter found")
    else:
        ok(f"69. spec malformed YAML (unclosed) → error as expected: {data['errors']}")
else:
    bad("69. spec malformed YAML (unclosed)", f"rc={rc} data={data}")

# 70. spec with feature_id wrong number format
p = write_file("spec_bad_featid.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  feature_id: FEAT-1-test\n"
    "  slug: test\n"
    "  status: draft\n"
    "---\n"
    "# Spec\n"
))
rc, data = run_vfm("spec", p)
if rc == 1 and not data["ok"]:
    msgs = " ".join(e["message"] for e in data["errors"])
    if "feature_id must match" in msgs:
        ok("70. spec feature_id wrong number format → error")
    else:
        bad("70. spec feature_id wrong number format", f"msgs={msgs}")
else:
    bad("70. spec feature_id wrong number format", f"rc={rc} data={data}")

# 71. valid spec with all refs and generator fields
p = write_file("spec_full_refs.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  feature_id: FEAT-001-test\n"
    "  slug: test\n"
    "  status: draft\n"
    "  refs:\n"
    "    framework_rules: \".orderspec/framework/orderspec-rules.md\"\n"
    "    constitution: \"constitution.md\"\n"
    "    stack: \"stack.md\"\n"
    "    architecture: \"architecture.md\"\n"
    "    conventions: \"conventions.md\"\n"
    "  generator:\n"
    "    command: order.spec\n"
    "    model: claude-3.5-sonnet\n"
    "---\n"
    "# Spec\n"
))
rc, data = run_vfm("spec", p)
if rc == 0 and data["ok"]:
    ok("71. valid spec with all refs and generator fields")
else:
    bad("71. valid spec with all refs and generator", f"rc={rc} data={data}")

# 72. spec missing refs.framework_rules
p = write_file("spec_no_fw_rules.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  feature_id: FEAT-001-test\n"
    "  slug: test\n"
    "  status: draft\n"
    "  refs:\n"
    "    constitution: \"constitution.md\"\n"
    "    stack: \"stack.md\"\n"
    "    architecture: \"architecture.md\"\n"
    "    conventions: \"conventions.md\"\n"
    "  generator:\n"
    "    command: order.spec\n"
    "    model: claude-3.5-sonnet\n"
    "---\n"
    "# Spec\n"
))
rc, data = run_vfm("spec", p)
if rc == 1 and not data["ok"]:
    fields = [e["field"] for e in data["errors"]]
    if "orderspec.refs.framework_rules" in fields:
        ok("72. spec missing refs.framework_rules → error")
    else:
        bad("72. spec missing refs.framework_rules", f"fields={fields}")
else:
    bad("72. spec missing refs.framework_rules", f"rc={rc} data={data}")

# 73. spec missing refs.constitution
p = write_file("spec_no_const.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  feature_id: FEAT-001-test\n"
    "  slug: test\n"
    "  status: draft\n"
    "  refs:\n"
    "    framework_rules: \".orderspec/framework/orderspec-rules.md\"\n"
    "    stack: \"stack.md\"\n"
    "    architecture: \"architecture.md\"\n"
    "    conventions: \"conventions.md\"\n"
    "  generator:\n"
    "    command: order.spec\n"
    "    model: claude-3.5-sonnet\n"
    "---\n"
    "# Spec\n"
))
rc, data = run_vfm("spec", p)
if rc == 1 and not data["ok"]:
    fields = [e["field"] for e in data["errors"]]
    if "orderspec.refs.constitution" in fields:
        ok("73. spec missing refs.constitution → error")
    else:
        bad("73. spec missing refs.constitution", f"fields={fields}")
else:
    bad("73. spec missing refs.constitution", f"rc={rc} data={data}")

# 74. spec missing generator.command
p = write_file("spec_no_gen_cmd.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  feature_id: FEAT-001-test\n"
    "  slug: test\n"
    "  status: draft\n"
    "  refs:\n"
    "    framework_rules: \".orderspec/framework/orderspec-rules.md\"\n"
    "    constitution: \"constitution.md\"\n"
    "    stack: \"stack.md\"\n"
    "    architecture: \"architecture.md\"\n"
    "    conventions: \"conventions.md\"\n"
    "  generator:\n"
    "    model: claude-3.5-sonnet\n"
    "---\n"
    "# Spec\n"
))
rc, data = run_vfm("spec", p)
if rc == 1 and not data["ok"]:
    fields = [e["field"] for e in data["errors"]]
    if "orderspec.generator.command" in fields:
        ok("74. spec missing generator.command → error")
    else:
        bad("74. spec missing generator.command", f"fields={fields}")
else:
    bad("74. spec missing generator.command", f"rc={rc} data={data}")

# 75. spec missing generator.model
p = write_file("spec_no_gen_model.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  feature_id: FEAT-001-test\n"
    "  slug: test\n"
    "  status: draft\n"
    "  refs:\n"
    "    framework_rules: \".orderspec/framework/orderspec-rules.md\"\n"
    "    constitution: \"constitution.md\"\n"
    "    stack: \"stack.md\"\n"
    "    architecture: \"architecture.md\"\n"
    "    conventions: \"conventions.md\"\n"
    "  generator:\n"
    "    command: order.spec\n"
    "---\n"
    "# Spec\n"
))
rc, data = run_vfm("spec", p)
if rc == 1 and not data["ok"]:
    fields = [e["field"] for e in data["errors"]]
    if "orderspec.generator.model" in fields:
        ok("75. spec missing generator.model → error")
    else:
        bad("75. spec missing generator.model", f"fields={fields}")
else:
    bad("75. spec missing generator.model", f"rc={rc} data={data}")

# 76. spec missing entire refs block
p = write_file("spec_no_refs_block.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  feature_id: FEAT-001-test\n"
    "  slug: test\n"
    "  status: draft\n"
    "  generator:\n"
    "    command: order.spec\n"
    "    model: claude-3.5-sonnet\n"
    "---\n"
    "# Spec\n"
))
rc, data = run_vfm("spec", p)
if rc == 1 and not data["ok"]:
    fields = [e["field"] for e in data["errors"]]
    refs_fields = [f for f in fields if "refs" in f]
    if len(refs_fields) == 5:
        ok("76. spec missing entire refs block → all 5 refs fields flagged")
    else:
        bad("76. spec missing entire refs block", f"refs_fields={refs_fields}")
else:
    bad("76. spec missing entire refs block", f"rc={rc} data={data}")

# 77. spec missing entire generator block
p = write_file("spec_no_gen_block.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  feature_id: FEAT-001-test\n"
    "  slug: test\n"
    "  status: draft\n"
    "  refs:\n"
    "    framework_rules: \".orderspec/framework/orderspec-rules.md\"\n"
    "    constitution: \"constitution.md\"\n"
    "    stack: \"stack.md\"\n"
    "    architecture: \"architecture.md\"\n"
    "    conventions: \"conventions.md\"\n"
    "---\n"
    "# Spec\n"
))
rc, data = run_vfm("spec", p)
if rc == 1 and not data["ok"]:
    fields = [e["field"] for e in data["errors"]]
    gen_fields = [f for f in fields if "generator" in f]
    if len(gen_fields) == 2:
        ok("77. spec missing entire generator block → both generator fields flagged")
    else:
        bad("77. spec missing entire generator block", f"gen_fields={gen_fields}")
else:
    bad("77. spec missing entire generator block", f"rc={rc} data={data}")

# 78. spec with quoted YAML values → parsed correctly
p = write_file("spec_quoted.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: \"spec\"\n"
    "  feature_id: \"FEAT-001-test\"\n"
    "  slug: 'test'\n"
    "  status: 'draft'\n"
    "  refs:\n"
    "    framework_rules: \".orderspec/framework/orderspec-rules.md\"\n"
    "    constitution: \"constitution.md\"\n"
    "    stack: \"stack.md\"\n"
    "    architecture: \"architecture.md\"\n"
    "    conventions: \"conventions.md\"\n"
    "  generator:\n"
    "    command: order.spec\n"
    "    model: claude-3.5-sonnet\n"
    "---\n"
    "# Spec\n"
))
rc, data = run_vfm("spec", p)
if rc == 0 and data["ok"]:
    ok("78. spec with quoted YAML values → parsed correctly")
else:
    bad("78. spec with quoted YAML values", f"rc={rc} data={data}")

# 79. spec refs.framework_rules with unresolved placeholder
p = write_file("spec_refs_placeholder.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  feature_id: FEAT-001-test\n"
    "  slug: test\n"
    "  status: draft\n"
    "  refs:\n"
    "    framework_rules: \"__FRAMEWORK_RULES__\"\n"
    "    constitution: \"constitution.md\"\n"
    "    stack: \"stack.md\"\n"
    "    architecture: \"architecture.md\"\n"
    "    conventions: \"conventions.md\"\n"
    "  generator:\n"
    "    command: order.spec\n"
    "    model: claude-3.5-sonnet\n"
    "---\n"
    "# Spec\n"
))
rc, data = run_vfm("spec", p)
if rc == 1 and not data["ok"]:
    fields = [e["field"] for e in data["errors"]]
    if "orderspec.refs.framework_rules" in fields:
        ok("79. spec refs.framework_rules with placeholder → error")
    else:
        bad("79. spec refs.framework_rules with placeholder", f"fields={fields}")
else:
    bad("79. spec refs.framework_rules with placeholder", f"rc={rc} data={data}")



finish()  # noqa: F405
