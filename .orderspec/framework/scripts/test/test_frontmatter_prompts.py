#!/usr/bin/env python3
"""Command-prompt frontmatter validation regressions."""

from support.frontmatter import *  # noqa: F403

# ═══════════════════════════════════════════════════════════════════════════════
# command_prompt tests
# ═══════════════════════════════════════════════════════════════════════════════

# 32. valid command_prompt frontmatter
p = write_file("cp_ok.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: command_prompt\n"
    "  command: order.spec\n"
    "  phase: specify\n"
    "description: Create or update the feature specification.\n"
    "handoffs:\n"
    "  - label: Build Technical Plan\n"
    "    agent: order.plan\n"
    "    prompt: Create a plan\n"
    "---\n"
    "# Content\n"
))
rc, data = run_vfm("command_prompt", p)
if rc == 0 and data["ok"]:
    ok("32. valid command_prompt frontmatter")
else:
    bad("32. valid command_prompt frontmatter", f"rc={rc} data={data}")

# 33. command_prompt without handoffs (optional)
p = write_file("cp_no_handoffs.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: command_prompt\n"
    "  command: order.spec-check\n"
    "  phase: check\n"
    "description: Inspect spec.md.\n"
    "---\n"
    "# Content\n"
))
rc, data = run_vfm("command_prompt", p)
if rc == 0 and data["ok"]:
    ok("33. command_prompt without handoffs (optional)")
else:
    bad("33. command_prompt without handoffs", f"rc={rc} data={data}")

# 34. command_prompt missing description
p = write_file("cp_no_desc.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: command_prompt\n"
    "  command: order.spec\n"
    "  phase: specify\n"
    "---\n"
    "# Content\n"
))
rc, data = run_vfm("command_prompt", p)
if rc == 1 and not data["ok"]:
    fields = [e["field"] for e in data["errors"]]
    if "description" in fields:
        ok("34. command_prompt missing description → error")
    else:
        bad("34. command_prompt missing description", f"fields={fields}")
else:
    bad("34. command_prompt missing description", f"rc={rc} data={data}")

# 35. command_prompt missing orderspec.artifact
p = write_file("cp_no_artifact.md", (
    "---\n"
    "orderspec:\n"
    "  command: order.spec\n"
    "  phase: specify\n"
    "description: Test\n"
    "---\n"
    "# Content\n"
))
rc, data = run_vfm("command_prompt", p)
if rc == 1 and not data["ok"]:
    fields = [e["field"] for e in data["errors"]]
    if "orderspec.artifact" in fields:
        ok("35. command_prompt missing orderspec.artifact → error")
    else:
        bad("35. command_prompt missing orderspec.artifact", f"fields={fields}")
else:
    bad("35. command_prompt missing orderspec.artifact", f"rc={rc} data={data}")

# 36. command_prompt missing orderspec.command
p = write_file("cp_no_command.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: command_prompt\n"
    "  phase: specify\n"
    "description: Test\n"
    "---\n"
    "# Content\n"
))
rc, data = run_vfm("command_prompt", p)
if rc == 1 and not data["ok"]:
    fields = [e["field"] for e in data["errors"]]
    if "orderspec.command" in fields:
        ok("36. command_prompt missing orderspec.command → error")
    else:
        bad("36. command_prompt missing orderspec.command", f"fields={fields}")
else:
    bad("36. command_prompt missing orderspec.command", f"rc={rc} data={data}")

# 37. command_prompt missing orderspec.phase
p = write_file("cp_no_phase.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: command_prompt\n"
    "  command: order.spec\n"
    "description: Test\n"
    "---\n"
    "# Content\n"
))
rc, data = run_vfm("command_prompt", p)
if rc == 1 and not data["ok"]:
    fields = [e["field"] for e in data["errors"]]
    if "orderspec.phase" in fields:
        ok("37. command_prompt missing orderspec.phase → error")
    else:
        bad("37. command_prompt missing orderspec.phase", f"fields={fields}")
else:
    bad("37. command_prompt missing orderspec.phase", f"rc={rc} data={data}")

# 38. command_prompt invalid artifact value
p = write_file("cp_bad_artifact.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  command: order.spec\n"
    "  phase: specify\n"
    "description: Test\n"
    "---\n"
    "# Content\n"
))
rc, data = run_vfm("command_prompt", p)
if rc == 1 and not data["ok"]:
    msgs = " ".join(e["message"] for e in data["errors"])
    if "must be 'command_prompt'" in msgs:
        ok("38. command_prompt invalid artifact → error")
    else:
        bad("38. command_prompt invalid artifact", f"msgs={msgs}")
else:
    bad("38. command_prompt invalid artifact", f"rc={rc} data={data}")

# 39. command_prompt invalid phase enum
p = write_file("cp_bad_phase.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: command_prompt\n"
    "  command: order.spec\n"
    "  phase: invalid_phase\n"
    "description: Test\n"
    "---\n"
    "# Content\n"
))
rc, data = run_vfm("command_prompt", p)
if rc == 1 and not data["ok"]:
    msgs = " ".join(e["message"] for e in data["errors"])
    if "orderspec.phase must be one of" in msgs:
        ok("39. command_prompt invalid phase enum → error")
    else:
        bad("39. command_prompt invalid phase enum", f"msgs={msgs}")
else:
    bad("39. command_prompt invalid phase enum", f"rc={rc} data={data}")

# 40. command_prompt missing all fields
p = write_file("cp_empty.md", (
    "---\n"
    "title: Something\n"
    "---\n"
    "# Content\n"
))
rc, data = run_vfm("command_prompt", p)
if rc == 1 and not data["ok"]:
    fields = {e["field"] for e in data["errors"]}
    expected = {"orderspec.artifact", "orderspec.command", "orderspec.phase", "description"}
    if expected.issubset(fields):
        ok("40. command_prompt missing all required fields → all flagged")
    else:
        bad("40. command_prompt missing all required fields", f"fields={fields} expected={expected}")
else:
    bad("40. command_prompt missing all required fields", f"rc={rc} data={data}")

# 41. command_prompt handoffs present but not a list (parser limitation)
# The YAML parser converts list items into a flat dict, so the validator
# sees a dict instead of a list. This is treated as "handoffs is present"
# which satisfies the required-field check.
p = write_file("cp_bad_handoffs.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: command_prompt\n"
    "  command: order.spec\n"
    "  phase: specify\n"
    "description: Test\n"
    "handoffs:\n"
    "  - label: Build Plan\n"
    "    agent: order.plan\n"
    "---\n"
    "# Content\n"
))
rc, data = run_vfm("command_prompt", p)
# handoffs is present (as a dict due to parser limitation), so no error
if rc == 0 and data["ok"]:
    ok("41. command_prompt handoffs present (parser produces dict, not list)")
else:
    bad("41. command_prompt handoffs present", f"rc={rc} data={data}")

# 42. command_prompt no frontmatter at all
p = write_file("cp_no_fm.md", "# Just a heading\n\nSome content.\n")
rc, data = run_vfm("command_prompt", p)
if rc == 1 and not data["ok"]:
    if any("No YAML frontmatter" in e["message"] for e in data["errors"]):
        ok("42. command_prompt no frontmatter → error")
    else:
        bad("42. command_prompt no frontmatter", f"errors={data['errors']}")
else:
    bad("42. command_prompt no frontmatter", f"rc={rc} data={data}")

# 43. command_prompt with placeholder values
p = write_file("cp_placeholder.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: command_prompt\n"
    "  command: __COMMAND__\n"
    "  phase: specify\n"
    "description: Test\n"
    "---\n"
    "# Content\n"
))
rc, data = run_vfm("command_prompt", p)
if rc == 1 and not data["ok"]:
    fields = [e["field"] for e in data["errors"]]
    if "orderspec.command" in fields:
        ok("43. command_prompt placeholder in command → error")
    else:
        bad("43. command_prompt placeholder in command", f"fields={fields}")
else:
    bad("43. command_prompt placeholder in command", f"rc={rc} data={data}")



finish()  # noqa: F405
