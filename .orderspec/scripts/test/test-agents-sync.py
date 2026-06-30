#!/usr/bin/env python3
"""test-agents-sync.py — regression tests for agents_sync.py and adapters

Tests:
- Detection of Kilo Code and Claude Code
- Prompt synchronization (copy, hash-skip, stale detection)
- Skills directory registration (kilo.jsonc for Kilo, symlink for Claude)
- External rules reading (AGENTS.md, CLAUDE.md)
- State management (agents.json)
- Idempotency (re-sync)
- Multi-agent support
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PY = sys.executable
SYNC = SCRIPT_DIR.parent / "agents_sync.py"

if not SYNC.exists():
    print(f"FATAL: agents_sync.py not found at {SYNC}", file=sys.stderr)
    sys.exit(2)

# ── Configuration ────────────────────────────────────────────────────────────

LOG_TO_FILE = False

TEST_DIR = SCRIPT_DIR
TEST_DIR.mkdir(parents=True, exist_ok=True)
LOG = TEST_DIR / "test-agents-sync.log"

if LOG_TO_FILE:
    LOG.write_text("", encoding="utf-8")

WORK = Path(tempfile.mkdtemp(prefix="orderspec-agents-test-"))

pass_count = 0
fail_count = 0


def ok(name):
    global pass_count
    pass_count += 1
    msg = f"PASS: {name}"
    print(msg, flush=True)
    if LOG_TO_FILE:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")


def bad(name):
    global fail_count
    fail_count += 1
    msg = f"FAIL: {name}"
    print(msg, flush=True)
    if LOG_TO_FILE:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")


def reset_work():
    if WORK.exists():
        shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)


def mkdirp(path):
    path.mkdir(parents=True, exist_ok=True)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read(path):
    return path.read_text(encoding="utf-8")


def read_json(path):
    return json.loads(read(path))


def _strip_jsonc_comments(text):
    """Remove // line comments and /* */ block comments from JSONC text."""
    import re
    # Remove /* */ block comments
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    # Remove // line comments (not inside strings)
    lines = text.split('\n')
    result = []
    for line in lines:
        in_string = False
        escape = False
        for i, c in enumerate(line):
            if escape:
                escape = False
                continue
            if c == '\\\\':
                escape = True
                continue
            if c == '"':
                in_string = not in_string
            if c == '/' and i + 1 < len(line) and line[i + 1] == '/' and not in_string:
                line = line[:i]
                break
        result.append(line)
    return '\n'.join(result)


def read_jsonc(path):
    """Read a JSONC file (JSON with comments) and return parsed dict."""
    text = read(path)
    if not text.strip():
        return {}
    stripped = _strip_jsonc_comments(text)
    return json.loads(stripped)


def run_sync(*args, input_text=None):
    cmd = [PY, str(SYNC)] + list(args)
    proc = subprocess.run(
        cmd,
        cwd=str(WORK),
        capture_output=True,
        text=True,
        input=input_text,
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_sync_json(*args):
    rc, out, err = run_sync(*args)
    try:
        data = json.loads(out)
    except Exception as exc:
        bad(f"invalid JSON output for {' '.join(args)} :: rc={rc} err={err!r} exc={exc} out={out!r}")
        return rc, {}, err
    return rc, data, err


def setup_prompts_source(prompts=None):
    """Create .orderspec/framework/prompts/ with test prompt files."""
    prompts_dir = WORK / ".orderspec" / "framework" / "prompts"
    mkdirp(prompts_dir)
    if prompts is None:
        prompts = {
            "order.spec.md": "---\norderspec:\n  artifact: command_prompt\n  command: order.spec\n---\n# /order.spec\nTest spec prompt.",
            "order.plan.md": "---\norderspec:\n  artifact: command_prompt\n  command: order.plan\n---\n# /order.plan\nTest plan prompt.",
            "order.code.md": "---\norderspec:\n  artifact: command_prompt\n  command: order.code\n---\n# /order.code\nTest code prompt.",
        }
    for name, content in prompts.items():
        write(prompts_dir / name, content)
    return prompts_dir


def setup_kilo():
    """Create .kilo/ directory structure."""
    mkdirp(WORK / ".kilo")


def setup_kilo_legacy():
    """Create .kilocode/ directory structure (legacy)."""
    mkdirp(WORK / ".kilocode")


def setup_claude():
    """Create .claude/ directory structure."""
    mkdirp(WORK / ".claude")


def setup_kilo_jsonc(skills_paths=None):
    """Create kilo.jsonc with optional existing skills.paths.

    Writes valid JSONC with a comment header, matching what write_jsonc produces.
    """
    config = {}
    if skills_paths is not None:
        config["skills"] = {"paths": list(skills_paths)}
    # Write as JSONC with comment header to match adapter output format
    content = "// Test config\n" + json.dumps(config, indent=2) + "\n"
    write(WORK / "kilo.jsonc", content)
    return config


def setup_agents_md(content="Use pnpm instead of npm."):
    """Create AGENTS.md file."""
    write(WORK / "AGENTS.md", content)


def setup_claude_md(content="Use named exports only. Prefer async/await."):
    """Create CLAUDE.md file."""
    write(WORK / "CLAUDE.md", content)


def assert_exists(path, name):
    if (WORK / path).exists():
        ok(name)
    else:
        bad(f"{name} :: missing {path}")


def assert_not_exists(path, name):
    if not (WORK / path).exists():
        ok(name)
    else:
        bad(f"{name} :: unexpected {path}")


def assert_is_symlink(path, target, name):
    link_path = WORK / path
    if link_path.is_symlink():
        actual = os.readlink(str(link_path))
        if actual == target:
            ok(name)
        else:
            bad(f"{name} :: symlink points to {actual}, expected {target}")
    else:
        bad(f"{name} :: {path} is not a symlink")


def assert_not_symlink(path, name):
    link_path = WORK / path
    if not link_path.is_symlink():
        ok(name)
    else:
        bad(f"{name} :: {path} is unexpectedly a symlink")


# ── Tests ────────────────────────────────────────────────────────────────────

# === DETECTION TESTS ===

# 1. detect with no agents
reset_work()
setup_prompts_source()
rc, data, err = run_sync_json("detect", "--json")
if rc == 0:
    detected = [a for a in data if a.get("detected")]
    if len(detected) == 0:
        ok("detect with no agents returns empty detected list")
    else:
        bad(f"detect with no agents :: found {len(detected)} agents: {detected}")
else:
    bad(f"detect with no agents :: rc={rc} err={err!r}")


# 2. detect Kilo Code (.kilo/ directory)
reset_work()
setup_prompts_source()
setup_kilo()
rc, data, err = run_sync_json("detect", "--json")
if rc == 0:
    kilo = next((a for a in data if a["agent_id"] == "kilocode"), None)
    if kilo and kilo["detected"] and kilo["prompts_dir"] == ".kilo/commands":
        ok("detect Kilo Code (.kilo/) — prompts_dir=.kilo/commands")
    else:
        bad(f"detect Kilo Code :: {kilo}")
else:
    bad(f"detect Kilo Code :: rc={rc} err={err!r}")


# 3. detect Claude Code (.claude/ directory)
reset_work()
setup_prompts_source()
setup_claude()
rc, data, err = run_sync_json("detect", "--json")
if rc == 0:
    claude = next((a for a in data if a["agent_id"] == "claude_code"), None)
    if claude and claude["detected"] and claude["prompts_dir"] == ".claude/commands":
        ok("detect Claude Code (.claude/) — prompts_dir=.claude/commands")
    else:
        bad(f"detect Claude Code :: {claude}")
else:
    bad(f"detect Claude Code :: rc={rc} err={err!r}")


# 4. detect Claude Code (CLAUDE.md only, no .claude/ dir)
reset_work()
setup_prompts_source()
setup_claude_md()
rc, data, err = run_sync_json("detect", "--json")
if rc == 0:
    claude = next((a for a in data if a["agent_id"] == "claude_code"), None)
    if claude and claude["detected"]:
        ok("detect Claude Code (CLAUDE.md only, no .claude/ dir)")
    else:
        bad(f"detect Claude Code (CLAUDE.md only) :: {claude}")
else:
    bad(f"detect Claude Code (CLAUDE.md only) :: rc={rc} err={err!r}")


# 5. detect both agents
reset_work()
setup_prompts_source()
setup_kilo()
setup_claude()
rc, data, err = run_sync_json("detect", "--json")
if rc == 0:
    detected = [a for a in data if a.get("detected")]
    ids = sorted([a["agent_id"] for a in detected])
    if ids == ["claude_code", "kilocode"]:
        ok("detect both Kilo Code and Claude Code")
    else:
        bad(f"detect both :: found {ids}")
else:
    bad(f"detect both :: rc={rc} err={err!r}")


# 6. detect Kilo Code legacy (.kilocode/)
reset_work()
setup_prompts_source()
setup_kilo_legacy()
rc, data, err = run_sync_json("detect", "--json")
if rc == 0:
    kilo = next((a for a in data if a["agent_id"] == "kilocode"), None)
    if kilo and kilo["detected"] and "legacy" in kilo["detection_reason"].lower():
        ok("detect Kilo Code legacy (.kilocode/) — legacy in reason")
    else:
        bad(f"detect Kilo Code legacy :: {kilo}")
else:
    bad(f"detect Kilo Code legacy :: rc={rc} err={err!r}")


# === SYNC PROMPTS TESTS ===

# 7. sync prompts to Kilo Code — files copied
reset_work()
setup_prompts_source()
setup_kilo()
rc, data, err = run_sync_json("sync", "--agents", "kilocode", "--json")
if rc == 0:
    result = data["sync_results"][0]
    if len(result["prompts_sync"]["copied"]) == 3 and len(result["prompts_sync"]["skipped"]) == 0:
        ok("sync prompts to Kilo Code — 3 files copied")
    else:
        bad(f"sync prompts to Kilo Code :: copied={result['prompts_sync']['copied']} skipped={result['prompts_sync']['skipped']}")
else:
    bad(f"sync prompts to Kilo Code :: rc={rc} data={data} err={err!r}")

assert_exists(".kilo/commands/order.spec.md", "Kilo Code: order.spec.md copied")
assert_exists(".kilo/commands/order.plan.md", "Kilo Code: order.plan.md copied")
assert_exists(".kilo/commands/order.code.md", "Kilo Code: order.code.md copied")


# 8. re-sync prompts to Kilo Code — all skipped (hash match)
rc, data, err = run_sync_json("sync", "--agents", "kilocode", "--json")
if rc == 0:
    result = data["sync_results"][0]
    if len(result["prompts_sync"]["copied"]) == 0 and len(result["prompts_sync"]["skipped"]) == 3:
        ok("re-sync prompts to Kilo Code — all skipped (hash match)")
    else:
        bad(f"re-sync prompts to Kilo Code :: copied={result['prompts_sync']['copied']} skipped={result['prompts_sync']['skipped']}")
else:
    bad(f"re-sync prompts to Kilo Code :: rc={rc} err={err!r}")


# 9. sync prompts to Claude Code — files copied
reset_work()
setup_prompts_source()
setup_claude()
rc, data, err = run_sync_json("sync", "--agents", "claude_code", "--json")
if rc == 0:
    result = data["sync_results"][0]
    if len(result["prompts_sync"]["copied"]) == 3 and len(result["prompts_sync"]["skipped"]) == 0:
        ok("sync prompts to Claude Code — 3 files copied")
    else:
        bad(f"sync prompts to Claude Code :: copied={result['prompts_sync']['copied']} skipped={result['prompts_sync']['skipped']}")
else:
    bad(f"sync prompts to Claude Code :: rc={rc} err={err!r}")

assert_exists(".claude/commands/order.spec.md", "Claude Code: order.spec.md copied")
assert_exists(".claude/commands/order.plan.md", "Claude Code: order.plan.md copied")
assert_exists(".claude/commands/order.code.md", "Claude Code: order.code.md copied")


# 10. re-sync prompts to Claude Code — all skipped
rc, data, err = run_sync_json("sync", "--agents", "claude_code", "--json")
if rc == 0:
    result = data["sync_results"][0]
    if len(result["prompts_sync"]["copied"]) == 0 and len(result["prompts_sync"]["skipped"]) == 3:
        ok("re-sync prompts to Claude Code — all skipped (hash match)")
    else:
        bad(f"re-sync prompts to Claude Code :: copied={result['prompts_sync']['copied']} skipped={result['prompts_sync']['skipped']}")
else:
    bad(f"re-sync prompts to Claude Code :: rc={rc} err={err!r}")


# 11. modified source prompts — re-copied
reset_work()
setup_prompts_source()
setup_kilo()
run_sync_json("sync", "--agents", "kilocode", "--json")
# Modify a source prompt
write(WORK / ".orderspec" / "framework" / "prompts" / "order.spec.md",
      "---\norderspec:\n  artifact: command_prompt\n  command: order.spec\n---\n# /order.spec\nMODIFIED prompt.")
rc, data, err = run_sync_json("sync", "--agents", "kilocode", "--json")
if rc == 0:
    result = data["sync_results"][0]
    if "order.spec.md" in result["prompts_sync"]["copied"]:
        ok("modified source prompt — re-copied")
    else:
        bad(f"modified source prompt :: copied={result['prompts_sync']['copied']}")
else:
    bad(f"modified source prompt :: rc={rc} err={err!r}")


# 12. stale files in target — reported in missing_in_source
reset_work()
setup_prompts_source()
setup_kilo()
# Create a stale file in target
write(WORK / ".kilo" / "commands" / "order.old-prompt.md", "stale prompt")
rc, data, err = run_sync_json("sync", "--agents", "kilocode", "--json")
if rc == 0:
    result = data["sync_results"][0]
    if "order.old-prompt.md" in result["prompts_sync"]["missing_in_source"]:
        ok("stale file in target — reported in missing_in_source")
    else:
        bad(f"stale file detection :: missing_in_source={result['prompts_sync']['missing_in_source']}")
else:
    bad(f"stale file detection :: rc={rc} err={err!r}")


# === SYNC SKILLS TESTS ===

# 13. sync skills to Kilo Code — kilo.jsonc created with skills.paths
reset_work()
setup_prompts_source()
setup_kilo()
rc, data, err = run_sync_json("sync", "--agents", "kilocode", "--json")
if rc == 0:
    skills_res = data["sync_results"][0]["skills_sync"]
    if skills_res["status"] == "updated" and ".orderspec/skills" in skills_res.get("details", ""):
        ok("sync skills to Kilo Code — kilo.jsonc updated with .orderspec/skills")
    else:
        bad(f"sync skills to Kilo Code :: {skills_res}")
else:
    bad(f"sync skills to Kilo Code :: rc={rc} err={err!r}")

# Verify kilo.jsonc content
kilo_config = read_jsonc(WORK / "kilo.jsonc")
if ".orderspec/skills" in kilo_config.get("skills", {}).get("paths", []):
    ok("Kilo Code: .orderspec/skills present in kilo.jsonc skills.paths")
else:
    bad(f"Kilo Code: skills.paths = {kilo_config.get('skills', {}).get('paths', [])}")


# 14. re-sync skills to Kilo Code — already configured
rc, data, err = run_sync_json("sync", "--agents", "kilocode", "--json")
if rc == 0:
    skills_res = data["sync_results"][0]["skills_sync"]
    if skills_res["status"] == "already_configured":
        ok("re-sync skills to Kilo Code — already_configured")
    else:
        bad(f"re-sync skills to Kilo Code :: {skills_res}")
else:
    bad(f"re-sync skills to Kilo Code :: rc={rc} err={err!r}")


# 15. sync skills to Kilo Code with pre-existing kilo.jsonc — path appended
reset_work()
setup_prompts_source()
setup_kilo()
setup_kilo_jsonc(skills_paths=["some/other/path"])
rc, data, err = run_sync_json("sync", "--agents", "kilocode", "--json")
if rc == 0:
    kilo_config = read_jsonc(WORK / "kilo.jsonc")
    paths = kilo_config.get("skills", {}).get("paths", [])
    if "some/other/path" in paths and ".orderspec/skills" in paths:
        ok("sync skills to Kilo Code with pre-existing config — path appended, existing preserved")
    else:
        bad(f"sync skills pre-existing :: paths={paths}")
else:
    bad(f"sync skills pre-existing :: rc={rc} err={err!r}")


# 16. sync skills to Claude Code — symlink created
reset_work()
setup_prompts_source()
setup_claude()
rc, data, err = run_sync_json("sync", "--agents", "claude_code", "--json")
if rc == 0:
    skills_res = data["sync_results"][0]["skills_sync"]
    if skills_res["status"] == "updated":
        ok("sync skills to Claude Code — symlink created")
    else:
        bad(f"sync skills to Claude Code :: {skills_res}")
else:
    bad(f"sync skills to Claude Code :: rc={rc} err={err!r}")

assert_is_symlink(".claude/skills", ".orderspec/skills", "Claude Code: .claude/skills -> .orderspec/skills")


# 17. re-sync skills to Claude Code — already configured (symlink exists)
rc, data, err = run_sync_json("sync", "--agents", "claude_code", "--json")
if rc == 0:
    skills_res = data["sync_results"][0]["skills_sync"]
    if skills_res["status"] == "already_configured":
        ok("re-sync skills to Claude Code — already_configured (symlink exists)")
    else:
        bad(f"re-sync skills to Claude Code :: {skills_res}")
else:
    bad(f"re-sync skills to Claude Code :: rc={rc} err={err!r}")


# 18. sync skills to Claude Code — existing real directory → skip + warn
reset_work()
setup_prompts_source()
setup_claude()
mkdirp(WORK / ".claude" / "skills")  # Create real directory
write(WORK / ".claude" / "skills" / "user-skill.md", "user skill")
rc, data, err = run_sync_json("sync", "--agents", "claude_code", "--json")
if rc == 0:
    skills_res = data["sync_results"][0]["skills_sync"]
    if skills_res["status"] == "skipped" and "real directory" in skills_res.get("details", ""):
        ok("sync skills to Claude Code — existing real dir → skipped with warning")
    else:
        bad(f"sync skills Claude Code existing dir :: {skills_res}")
else:
    bad(f"sync skills Claude Code existing dir :: rc={rc} err={err!r}")

assert_not_symlink(".claude/skills", "Claude Code: .claude/skills is NOT a symlink (real dir preserved)")


# === READ RULES TESTS ===

# 19. read-rules from Kilo Code (AGENTS.md)
reset_work()
setup_prompts_source()
setup_kilo()
setup_agents_md("Use pnpm. All functions must have JSDoc.")
rc, data, err = run_sync_json("read-rules", "--agents", "kilocode", "--json")
if rc == 0:
    rules = data.get("agents", {}).get("kilocode", {})
    if "AGENTS.md" in rules.get("contents", {}) and "pnpm" in rules["contents"]["AGENTS.md"]:
        ok("read-rules Kilo Code — AGENTS.md content returned")
    else:
        bad(f"read-rules Kilo Code :: {rules}")
else:
    bad(f"read-rules Kilo Code :: rc={rc} err={err!r}")


# 20. read-rules from Claude Code (CLAUDE.md)
reset_work()
setup_prompts_source()
setup_claude()
setup_claude_md("Use named exports. Prefer async/await.")
rc, data, err = run_sync_json("read-rules", "--agents", "claude_code", "--json")
if rc == 0:
    rules = data.get("agents", {}).get("claude_code", {})
    if "CLAUDE.md" in rules.get("contents", {}) and "async/await" in rules["contents"]["CLAUDE.md"]:
        ok("read-rules Claude Code — CLAUDE.md content returned")
    else:
        bad(f"read-rules Claude Code :: {rules}")
else:
    bad(f"read-rules Claude Code :: rc={rc} err={err!r}")


# 21. read-rules with no rule files
reset_work()
setup_prompts_source()
setup_kilo()
rc, data, err = run_sync_json("read-rules", "--agents", "kilocode", "--json")
if rc == 0:
    rules = data.get("agents", {}).get("kilocode", {})
    if len(rules.get("files", [])) == 0 and len(rules.get("contents", {})) == 0:
        ok("read-rules with no rule files — empty result")
    else:
        bad(f"read-rules no files :: {rules}")
else:
    bad(f"read-rules no files :: rc={rc} err={err!r}")


# 22. read-rules from both agents — combined
reset_work()
setup_prompts_source()
setup_kilo()
setup_claude()
setup_agents_md("Use pnpm.")
setup_claude_md("Use named exports.")
rc, data, err = run_sync_json("read-rules", "--agents", "kilocode", "claude_code", "--json")
if rc == 0:
    combined_files = data.get("combined_files", [])
    combined_contents = data.get("combined_contents", {})
    if "AGENTS.md" in combined_files and "CLAUDE.md" in combined_files:
        ok("read-rules both agents — combined files include AGENTS.md and CLAUDE.md")
    else:
        bad(f"read-rules both :: combined_files={combined_files}")
else:
    bad(f"read-rules both :: rc={rc} err={err!r}")


# === STATE MANAGEMENT TESTS ===

# 23. agents.json created after sync
reset_work()
setup_prompts_source()
setup_kilo()
run_sync_json("sync", "--agents", "kilocode", "--json")
assert_exists(".orderspec/state/agents.json", "agents.json created after sync")
state = read_json(WORK / ".orderspec" / "state" / "agents.json")
if state.get("enabled_agents") == ["kilocode"] and "kilocode" in state.get("agents", {}):
    ok("agents.json has correct enabled_agents and agent info")
else:
    bad(f"agents.json content :: {state}")


# 24. agents.json updated when adding agent
setup_claude()
run_sync_json("sync", "--agents", "kilocode", "claude_code", "--json")
state = read_json(WORK / ".orderspec" / "state" / "agents.json")
if sorted(state.get("enabled_agents", [])) == ["claude_code", "kilocode"]:
    ok("agents.json updated with both agents")
else:
    bad(f"agents.json after add :: enabled_agents={state.get('enabled_agents', [])}")


# 25. agents.json — agent removed from enabled but kept in agents dict
run_sync_json("sync", "--agents", "kilocode", "--json")
state = read_json(WORK / ".orderspec" / "state" / "agents.json")
if state.get("enabled_agents") == ["kilocode"]:
    if "claude_code" in state.get("agents", {}):
        claude_info = state["agents"]["claude_code"]
        if claude_info.get("enabled") is False:
            ok("agents.json — claude_code disabled but kept in agents dict")
        else:
            bad(f"agents.json disabled agent :: enabled={claude_info.get('enabled')}")
    else:
        bad("agents.json — claude_code missing from agents dict")
else:
    bad(f"agents.json after remove :: enabled_agents={state.get('enabled_agents', [])}")


# 26. state command output
rc, out, err = run_sync("state")
if rc == 0 and "kilocode" in out:
    ok("state command — text output contains kilocode")
else:
    bad(f"state command :: rc={rc} out={out!r}")


# === MULTI-AGENT SYNC TESTS ===

# 27. sync both agents simultaneously — prompts copied to both
reset_work()
setup_prompts_source()
setup_kilo()
setup_claude()
rc, data, err = run_sync_json("sync", "--agents", "kilocode", "claude_code", "--json")
if rc == 0:
    results = data.get("sync_results", [])
    if len(results) == 2:
        kilo_res = next((r for r in results if r["agent_id"] == "kilocode"), None)
        claude_res = next((r for r in results if r["agent_id"] == "claude_code"), None)
        if (kilo_res and len(kilo_res["prompts_sync"]["copied"]) == 3 and
            claude_res and len(claude_res["prompts_sync"]["copied"]) == 3):
            ok("sync both agents — prompts copied to both")
        else:
            bad(f"sync both :: kilo={kilo_res}, claude={claude_res}")
    else:
        bad(f"sync both :: {len(results)} results")
else:
    bad(f"sync both :: rc={rc} err={err!r}")

assert_exists(".kilo/commands/order.spec.md", "Both sync: Kilo has order.spec.md")
assert_exists(".claude/commands/order.spec.md", "Both sync: Claude has order.spec.md")


# 28. sync both agents — skills registered in both
state = read_json(WORK / ".orderspec" / "state" / "agents.json")
kilo_skills = state.get("agents", {}).get("kilocode", {}).get("sync_state", {}).get("skills", {})
claude_skills = state.get("agents", {}).get("claude_code", {}).get("sync_state", {}).get("skills", {})
if kilo_skills.get("status") in ("updated", "already_configured") and \
   claude_skills.get("status") in ("updated", "already_configured"):
    ok("sync both agents — skills registered in both")
else:
    bad(f"sync both skills :: kilo={kilo_skills}, claude={claude_skills}")


# === EDGE CASES ===

# 29. sync with non-existent agent ID — error in results
reset_work()
setup_prompts_source()
rc, data, err = run_sync_json("sync", "--agents", "nonexistent", "--json")
# Should not crash, just no sync results for nonexistent
if rc == 0:
    ok("sync with nonexistent agent — does not crash")
else:
    bad(f"sync nonexistent :: rc={rc} err={err!r}")


# 30. sync with empty prompts source — error reported
reset_work()
setup_kilo()
# No .orderspec/framework/prompts/ created
rc, data, err = run_sync_json("sync", "--agents", "kilocode", "--json")
if rc == 0:
    result = data["sync_results"][0]
    if len(result["prompts_sync"]["errors"]) > 0:
        ok("sync with empty prompts source — error reported")
    else:
        bad(f"sync empty source :: errors={result['prompts_sync']['errors']}")
else:
    bad(f"sync empty source :: rc={rc} err={err!r}")


# 31. .orderspec/skills/ directory created by sync
reset_work()
setup_prompts_source()
setup_kilo()
run_sync_json("sync", "--agents", "kilocode", "--json")
assert_exists(".orderspec/skills", ".orderspec/skills/ directory created by sync")
assert_exists(".orderspec/skills/.gitkeep", ".orderspec/skills/.gitkeep created")


# 32. prompts in subdirectories — copied with structure
reset_work()
prompts = {
    "order.spec.md": "spec prompt",
    "checks/order.spec-check.md": "spec-check prompt",
}
setup_prompts_source(prompts)
setup_kilo()
run_sync_json("sync", "--agents", "kilocode", "--json")
assert_exists(".kilo/commands/order.spec.md", "Subdir test: order.spec.md at root")
assert_exists(".kilo/commands/checks/order.spec-check.md", "Subdir test: checks/order.spec-check.md copied")


# 33. Claude Code .claude/CLAUDE.md alternative location
reset_work()
setup_prompts_source()
mkdirp(WORK / ".claude")
write(WORK / ".claude" / "CLAUDE.md", "Alt location rules.")
rc, data, err = run_sync_json("read-rules", "--agents", "claude_code", "--json")
if rc == 0:
    rules = data.get("agents", {}).get("claude_code", {})
    files = rules.get("files", [])
    if ".claude/CLAUDE.md" in files:
        ok("read-rules Claude Code — .claude/CLAUDE.md alternative location read")
    else:
        bad(f"read-rules alt location :: files={files}")
else:
    bad(f"read-rules alt location :: rc={rc} err={err!r}")


# 34. Kilo Code with instructions in kilo.jsonc — read via read_rules
reset_work()
setup_prompts_source()
setup_kilo()
write(WORK / "kilo.jsonc", json.dumps({
    "instructions": ["docs/coding-standards.md"]
}))
write(WORK / "docs" / "coding-standards.md", "Use 2-space indent. No semicolons.")
rc, data, err = run_sync_json("read-rules", "--agents", "kilocode", "--json")
if rc == 0:
    rules = data.get("agents", {}).get("kilocode", {})
    if "docs/coding-standards.md" in rules.get("contents", {}):
        ok("read-rules Kilo Code — instructions file from kilo.jsonc read")
    else:
        bad(f"read-rules instructions :: files={rules.get('files', [])}")
else:
    bad(f"read-rules instructions :: rc={rc} err={err!r}")


# === SYMLINK EDGE CASES ===

# 35. Claude Code skills symlink — update wrong symlink target
reset_work()
setup_prompts_source()
setup_claude()
mkdirp(WORK / ".claude")
os.symlink("wrong/target", str(WORK / ".claude" / "skills"), target_is_directory=True)
rc, data, err = run_sync_json("sync", "--agents", "claude_code", "--json")
if rc == 0:
    skills_res = data["sync_results"][0]["skills_sync"]
    if skills_res["status"] == "updated":
        ok("Claude Code skills — wrong symlink target updated")
    else:
        bad(f"Claude Code wrong symlink :: {skills_res}")
    assert_is_symlink(".claude/skills", ".orderspec/skills", "Claude Code: symlink updated to correct target")
else:
    bad(f"Claude Code wrong symlink :: rc={rc} err={err!r}")


# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
if LOG_TO_FILE:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{pass_count} passed, {fail_count} failed\n")

sys.exit(0 if fail_count == 0 else 1)
