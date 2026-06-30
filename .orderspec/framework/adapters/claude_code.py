import os
import hashlib
import shutil
from typing import Optional, Dict, Any, List
from .base import AgentAdapter, AgentInfo

class ClaudeCodeAdapter(AgentAdapter):
    """Adapter for Claude Code AI agent.

    Claude Code structure:
    - .claude/ directory for project-scoped config
    - .claude/commands/ for slash commands (same as prompts)
    - .claude/skills/<name>/SKILL.md for skills
    - CLAUDE.md at project root for project instructions
    - .claude/settings.json for permissions, hooks, env vars

    Skills directory registration:
    Claude Code loads skills from .claude/skills/ natively.
    There is no config option to add custom skills paths.
    Solution: create a symlink .claude/skills -> .orderspec/skills
    so all OrderSpec skills are visible to Claude Code.
    If .claude/skills/ already exists as a real directory, skip and warn.
    """
    agent_id: str = "claude_code"
    display_name: str = "Claude Code"

    CLAUDE_DIR = ".claude"
    COMMANDS_DIR = ".claude/commands"
    SKILLS_DIR = ".claude/skills"
    SETTINGS_FILE = ".claude/settings.json"
    RULES_FILENAME = "CLAUDE.md"
    RULES_FILENAME_ALT = ".claude/CLAUDE.md"

    def _hash_file(self, filepath: str) -> Optional[str]:
        if not os.path.isfile(filepath):
            return None
        h = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    def detect(self, project_root: str) -> Optional[AgentInfo]:
        claude_dir = os.path.join(project_root, self.CLAUDE_DIR)
        claude_md = os.path.join(project_root, self.RULES_FILENAME)

        # Detect: .claude/ dir OR CLAUDE.md file
        if os.path.isdir(claude_dir) or os.path.isfile(claude_md):
            config_paths = []
            settings_path = os.path.join(project_root, self.SETTINGS_FILE)
            if os.path.isfile(settings_path):
                config_paths.append(self.SETTINGS_FILE)

            rules_files = [self.RULES_FILENAME]
            alt_rules = os.path.join(project_root, self.RULES_FILENAME_ALT)
            if os.path.isfile(alt_rules):
                rules_files.append(self.RULES_FILENAME_ALT)

            detection_reason = f"Found .claude/ directory or CLAUDE.md"

            return AgentInfo(
                agent_id=self.agent_id,
                display_name=self.display_name,
                detected=True,
                detection_reason=detection_reason,
                config_paths=config_paths,
                prompts_dir=self.COMMANDS_DIR,
                supports_symlinks=True,
                rules_files=rules_files
            )
        return None

    def sync_skills_dir(self, project_root: str, skills_dir: str) -> Dict[str, Any]:
        """Register skills directory by creating a symlink.

        Claude Code loads skills from .claude/skills/<name>/SKILL.md.
        We create a symlink: .claude/skills -> skills_dir (typically .orderspec/skills).

        Cases:
        1. .claude/skills doesn't exist -> create symlink
        2. .claude/skills is a symlink to skills_dir -> already configured
        3. .claude/skills is a symlink to something else -> update symlink
        4. .claude/skills is a real directory -> skip, warn (user has own skills)
        """
        report = {
            "agent": self.agent_id,
            "action": "sync_skills_dir",
            "skills_dir": skills_dir,
            "status": "unknown",
            "details": ""
        }

        claude_dir = os.path.join(project_root, self.CLAUDE_DIR)
        skills_link = os.path.join(project_root, self.SKILLS_DIR)

        # Ensure .claude/ exists
        os.makedirs(claude_dir, exist_ok=True)

        # Resolve target path (make relative path absolute for symlink)
        target_abs = os.path.join(project_root, skills_dir)
        os.makedirs(target_abs, exist_ok=True)

        # Case 1: doesn't exist
        if not os.path.lexists(skills_link):
            try:
                os.symlink(skills_dir, skills_link, target_is_directory=True)
                report["status"] = "updated"
                report["details"] = f"Created symlink: {self.SKILLS_DIR} -> {skills_dir}"
            except OSError as e:
                report["status"] = "error"
                report["details"] = f"Failed to create symlink: {e}"
            return report

        # Case 2: existing symlink
        if os.path.islink(skills_link):
            current_target = os.readlink(skills_link)
            if current_target == skills_dir:
                report["status"] = "already_configured"
                report["details"] = f"Symlink already points to {skills_dir}"
            else:
                # Case 3: symlink to wrong target -> update
                try:
                    os.unlink(skills_link)
                    os.symlink(skills_dir, skills_link, target_is_directory=True)
                    report["status"] = "updated"
                    report["details"] = f"Updated symlink: {current_target} -> {skills_dir}"
                except OSError as e:
                    report["status"] = "error"
                    report["details"] = f"Failed to update symlink: {e}"
            return report

        # Case 4: real directory
        if os.path.isdir(skills_link):
            report["status"] = "skipped"
            report["details"] = (
                f"{self.SKILLS_DIR} already exists as a real directory. "
                f"Cannot create symlink. Skills from {skills_dir} will NOT be visible. "
                f"Consider manually symlinking individual skills or removing the directory."
            )
            return report

        # Unexpected: file exists but not dir or symlink
        report["status"] = "error"
        report["details"] = f"{self.SKILLS_DIR} exists but is not a directory or symlink"
        return report

    def sync_prompts(self, project_root: str, prompts_source: str) -> Dict[str, Any]:
        """Copy prompt files from source to .claude/commands/.

        Claude Code treats files in .claude/commands/ as slash commands.
        Uses SHA-256 hashing for idempotent copies.
        """
        source_dir = os.path.join(project_root, prompts_source)
        target_dir = os.path.join(project_root, self.COMMANDS_DIR)

        os.makedirs(target_dir, exist_ok=True)

        report = {
            "agent": self.agent_id,
            "action": "sync_prompts",
            "source": prompts_source,
            "target": self.COMMANDS_DIR,
            "copied": [],
            "skipped": [],
            "missing_in_source": [],
            "errors": []
        }

        if not os.path.isdir(source_dir):
            report["errors"].append(f"Source directory not found: {source_dir}")
            return report

        # 1. Copy/update files from source
        source_files = []
        for root, _, files in os.walk(source_dir):
            for file in files:
                if file.endswith(".md"):
                    abs_src = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_src, source_dir)
                    source_files.append(rel_path)

                    abs_tgt = os.path.join(target_dir, rel_path)
                    os.makedirs(os.path.dirname(abs_tgt), exist_ok=True)

                    src_hash = self._hash_file(abs_src)
                    tgt_hash = self._hash_file(abs_tgt)

                    if src_hash != tgt_hash:
                        try:
                            shutil.copy2(abs_src, abs_tgt)
                            report["copied"].append(rel_path)
                        except Exception as e:
                            report["errors"].append(f"Failed to copy {rel_path}: {e}")
                    else:
                        report["skipped"].append(rel_path)

        # 2. Check for stale files in target
        for root, _, files in os.walk(target_dir):
            for file in files:
                if file.endswith(".md"):
                    abs_tgt = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_tgt, target_dir)
                    if rel_path not in source_files:
                        report["missing_in_source"].append(rel_path)

        return report

    def read_rules(self, project_root: str) -> Dict[str, Any]:
        """Read external rule files for Claude Code.

        Sources:
        1. CLAUDE.md at project root (primary)
        2. .claude/CLAUDE.md (alternative location)
        Note: CLAUDE.local.md is personal preferences, NOT project rules -> skipped
        """
        result = {
            "agent": self.agent_id,
            "files": [],
            "contents": {},
            "errors": []
        }

        rule_paths = [
            os.path.join(project_root, self.RULES_FILENAME),
            os.path.join(project_root, self.RULES_FILENAME_ALT),
        ]

        for rules_path in rule_paths:
            if os.path.isfile(rules_path):
                rel_path = os.path.relpath(rules_path, project_root)
                try:
                    with open(rules_path, 'r', encoding='utf-8') as f:
                        result["contents"][rel_path] = f.read()
                        result["files"].append(rel_path)
                except Exception as e:
                    result["errors"].append(f"Failed to read {rel_path}: {e}")

        return result
