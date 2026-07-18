#!/usr/bin/env python3
"""Gate-report frontmatter validation regressions."""

from support.frontmatter import *  # noqa: F403

# ═══════════════════════════════════════════════════════════════════════════════
# gate_report tests
# ═══════════════════════════════════════════════════════════════════════════════

# 44. valid gate_report frontmatter
p = write_file("gr_ok.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: gate_report\n"
    "  command: order.spec-check\n"
    "  model: claude-3.5-sonnet\n"
    "  generated_at: 2026-01-01\n"
    "  verdict: PASS\n"
    "  feature_id: FEAT-001-user-auth\n"
    "  feature_directory: .orderspec/features/001-user-auth\n"
    "---\n"
    "# Report\n"
))
rc, data = run_vfm("gate_report", p)
if rc == 0 and data["ok"]:
    ok("44. valid gate_report frontmatter")
else:
    bad("44. valid gate_report frontmatter", f"rc={rc} data={data}")

# 45. gate_report missing required field
p = write_file("gr_no_cmd.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: gate_report\n"
    "  model: claude-3.5-sonnet\n"
    "  generated_at: 2026-01-01\n"
    "  verdict: PASS\n"
    "  feature_id: FEAT-001-user-auth\n"
    "  feature_directory: .orderspec/features/001-user-auth\n"
    "---\n"
    "# Report\n"
))
rc, data = run_vfm("gate_report", p)
if rc == 1 and not data["ok"]:
    fields = [e["field"] for e in data["errors"]]
    if "orderspec.command" in fields:
        ok("45. gate_report missing command → error")
    else:
        bad("45. gate_report missing command", f"fields={fields}")
else:
    bad("45. gate_report missing command", f"rc={rc} data={data}")

# 46. gate_report invalid verdict enum
p = write_file("gr_bad_verdict.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: gate_report\n"
    "  command: order.spec-check\n"
    "  model: claude-3.5-sonnet\n"
    "  generated_at: 2026-01-01\n"
    "  verdict: maybe\n"
    "  feature_id: FEAT-001-user-auth\n"
    "  feature_directory: .orderspec/features/001-user-auth\n"
    "---\n"
    "# Report\n"
))
rc, data = run_vfm("gate_report", p)
if rc == 1 and not data["ok"]:
    msgs = " ".join(e["message"] for e in data["errors"])
    if "orderspec.verdict must be one of" in msgs:
        ok("46. gate_report invalid verdict → error")
    else:
        bad("46. gate_report invalid verdict", f"msgs={msgs}")
else:
    bad("46. gate_report invalid verdict", f"rc={rc} data={data}")

# 47. gate_report invalid artifact
p = write_file("gr_bad_art.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  command: order.spec-check\n"
    "  model: claude-3.5-sonnet\n"
    "  generated_at: 2026-01-01\n"
    "  verdict: PASS\n"
    "  feature_id: FEAT-001-user-auth\n"
    "  feature_directory: .orderspec/features/001-user-auth\n"
    "---\n"
    "# Report\n"
))
rc, data = run_vfm("gate_report", p)
if rc == 1 and not data["ok"]:
    msgs = " ".join(e["message"] for e in data["errors"])
    if "must be 'gate_report'" in msgs:
        ok("47. gate_report invalid artifact → error")
    else:
        bad("47. gate_report invalid artifact", f"msgs={msgs}")
else:
    bad("47. gate_report invalid artifact", f"rc={rc} data={data}")

# 48. gate_report no frontmatter
p = write_file("gr_no_fm.md", "# Report\n\nSome content.\n")
rc, data = run_vfm("gate_report", p)
if rc == 1 and not data["ok"]:
    if any("No YAML frontmatter" in e["message"] for e in data["errors"]):
        ok("48. gate_report no frontmatter → error")
    else:
        bad("48. gate_report no frontmatter", f"errors={data['errors']}")
else:
    bad("48. gate_report no frontmatter", f"rc={rc} data={data}")

# 49. gate_report missing all fields
p = write_file("gr_empty.md", "---\norderspec:\n  artifact: gate_report\n---\n# Report\n")
rc, data = run_vfm("gate_report", p)
if rc == 1 and not data["ok"]:
    expected = {"orderspec.command", "orderspec.model", "orderspec.generated_at",
                "orderspec.verdict", "orderspec.feature_id", "orderspec.feature_directory"}
    fields = {e["field"] for e in data["errors"]}
    if expected.issubset(fields):
        ok("49. gate_report missing all required fields → all flagged")
    else:
        bad("49. gate_report missing all required fields", f"fields={fields} expected={expected}")
else:
    bad("49. gate_report missing all required fields", f"rc={rc} data={data}")

# 50. gate_report with placeholder values (template) → flagged as unresolved
p = write_file("gr_template.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: gate_report\n"
    "  command: {generator_cmd}\n"
    "  model: {model_name}\n"
    "  generated_at: {DATE}\n"
    "  verdict: {VERDICT}\n"
    "  feature_id: {FEATURE_ID}\n"
    "  feature_directory: {FEATURE_DIR}\n"
    "---\n"
    "# Report\n"
))
rc, data = run_vfm("gate_report", p)
# Template placeholders start with { → treated as unresolved → validation fails
# This is correct: templates are not valid artifacts until placeholders are filled
if rc == 1 and not data["ok"]:
    fields = {e["field"] for e in data["errors"]}
    expected = {"orderspec.command", "orderspec.model", "orderspec.generated_at",
                "orderspec.verdict", "orderspec.feature_id", "orderspec.feature_directory"}
    if expected.issubset(fields):
        ok("50. gate_report template placeholders → flagged as unresolved")
    else:
        bad("50. gate_report template placeholders", f"fields={fields} expected={expected}")
else:
    bad("50. gate_report template placeholders", f"rc={rc} data={data}")



finish()  # noqa: F405
