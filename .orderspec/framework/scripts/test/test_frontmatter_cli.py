#!/usr/bin/env python3
"""Frontmatter CLI error and text-output contract regressions."""

from support.frontmatter import *  # noqa: F403

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



finish()  # noqa: F405
