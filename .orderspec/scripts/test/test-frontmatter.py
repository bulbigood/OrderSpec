#!/usr/bin/env python3
"""test-frontmatter.py — regression tests for frontmatter validation across all artifact types."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PY = sys.executable
TRACE = SCRIPT_DIR.parent / "traceability.py"

if not TRACE.exists():
    print(f"FATAL: traceability.py not found at {TRACE}", file=sys.stderr)
    sys.exit(2)

WORK = Path(tempfile.mkdtemp(prefix="orderspec-test-fm-"))

pass_count = 0
fail_count = 0


def ok(name):
    global pass_count
    pass_count += 1
    print(f"PASS: {name}", flush=True)


def bad(name, detail=""):
    global fail_count
    fail_count += 1
    msg = f"FAIL: {name}"
    if detail:
        msg += f" :: {detail}"
    print(msg, flush=True)


def run_vfm(artifact_type, file_path, use_json=True):
    """Run validate-frontmatter and return (rc, data_or_text)."""
    cmd = [PY, str(TRACE), "validate-frontmatter"]
    if use_json:
        cmd.append("--json")
    cmd.extend([artifact_type, str(file_path)])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if use_json:
        try:
            return proc.returncode, json.loads(proc.stdout)
        except Exception:
            return proc.returncode, proc.stdout + proc.stderr
    return proc.returncode, proc.stdout + proc.stderr


def write_file(name, content):
    path = WORK / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


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


# ═══════════════════════════════════════════════════════════════════════════════
# project_contract tests
# ═══════════════════════════════════════════════════════════════════════════════

# 51. valid project_contract (stack)
p = write_file("pc_stack.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: project_contract\n"
    "  kind: stack\n"
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


# ═══════════════════════════════════════════════════════════════════════════════
# CLI edge cases
# ═══════════════════════════════════════════════════════════════════════════════

# 80. unknown artifact type
p = write_file("any.md", "---\norderspec:\n  artifact: x\n---\n")
rc, data = run_vfm("unknown_type", p)
if rc == 64:
    ok("80. unknown artifact type → exit 64")
else:
    bad("80. unknown artifact type", f"rc={rc}")

# 81. file not found
rc, data = run_vfm("spec", str(WORK / "nonexistent.md"))
if rc == 2:
    ok("81. file not found → exit 2")
else:
    bad("81. file not found", f"rc={rc}")

# 82. non-JSON output
p = write_file("cp_text.md", (
    "---\n"
    "orderspec:\n"
    "  artifact: command_prompt\n"
    "  command: order.spec\n"
    "  phase: specify\n"
    "description: Test\n"
    "---\n"
    "# Content\n"
))
cmd = [PY, str(TRACE), "validate-frontmatter", "command_prompt", str(p)]
proc = subprocess.run(cmd, capture_output=True, text=True)
if proc.returncode == 0 and "errors" not in proc.stdout:
    ok("73. non-JSON output mode")
else:
    bad("73. non-JSON output mode", f"rc={proc.returncode} out={proc.stdout[:100]}")


# ── Cleanup ──────────────────────────────────────────────────────────────────

import shutil
if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
sys.exit(0 if fail_count == 0 else 1)
