import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .base import AgentAdapter, AgentInfo


class CodexAdapter(AgentAdapter):
    """Adapter for OpenAI Codex.

    Codex discovers repository skills below ``.agents/skills``. OrderSpec keeps
    its canonical project skills in ``.orderspec/skills``; when possible this
    adapter exposes that directory through a relative symlink and writes the
    framework commands there as Codex-compatible ``SKILL.md`` files.

    Codex's old ``~/.codex/prompts`` custom-prompt surface is intentionally not
    used: repository skills are shareable and are the supported replacement.
    """

    agent_id: str = "codex"
    display_name: str = "Codex"

    CODEX_DIR = ".codex"
    CODEX_CONFIG_FILE = ".codex/config.toml"
    PROJECT_SKILLS_DIR = ".agents/skills"
    RULES_FILENAME = "AGENTS.md"
    RULES_OVERRIDE_FILENAME = "AGENTS.override.md"
    PLUGIN_MANIFEST = ".codex-plugin/plugin.json"

    def _hash_file(self, filepath: str) -> Optional[str]:
        if not os.path.isfile(filepath):
            return None
        digest = hashlib.sha256()
        with open(filepath, "rb") as handle:
            while chunk := handle.read(8192):
                digest.update(chunk)
        return digest.hexdigest()

    def _canonical_skills_dir(self, project_root: str, skills_dir: str) -> str:
        return os.path.join(project_root, skills_dir)

    def _codex_skills_dir(self, project_root: str) -> str:
        return os.path.join(project_root, self.PROJECT_SKILLS_DIR)

    def _skill_name(self, rel_prompt_path: str) -> str:
        """Convert ``order.spec-check.md`` into a valid skill directory name."""
        stem = Path(rel_prompt_path).stem
        name = stem.lower().replace("_", "-").replace(".", "-")
        name = "-".join(part for part in name.split("-") if part)
        return name or "orderspec-command"

    def _parse_prompt(self, text: str) -> tuple[str, str, str]:
        """Return command, description, and body from OrderSpec prompt text."""
        command = ""
        description = ""
        body = text

        if text.startswith("---"):
            marker = text.find("\n---", 3)
            if marker != -1:
                frontmatter = text[3:marker]
                body = text[marker + len("\n---"):].lstrip("\r\n")
                for line in frontmatter.splitlines():
                    key, separator, value = line.partition(":")
                    if not separator:
                        continue
                    value = value.strip()
                    if key.strip() == "description":
                        description = value
                    elif key.strip() == "command":
                        command = value

        if not command:
            command = "order." + self._skill_name("orderspec-command").removeprefix("order-")
        if not description:
            description = f"Run the OrderSpec {command} workflow."

        return command, description, body

    def _render_skill(self, prompt_text: str) -> str:
        command, description, body = self._parse_prompt(prompt_text)
        skill_name = self._skill_name(command + ".md")
        description_json = json.dumps(description, ensure_ascii=False)

        return (
            "---\n"
            f"name: {skill_name}\n"
            f"description: {description_json}\n"
            "---\n\n"
            f"This skill is the OrderSpec command `{command}`.\n"
            "Treat the user's message supplied with this skill as the command "
            "arguments. Whenever the source instructions below contain "
            "`$ARGUMENTS`, substitute those arguments before acting; do not "
            "expect a shell environment variable named `ARGUMENTS`.\n\n"
            f"{body.rstrip()}\n"
        )

    def detect(self, project_root: str) -> Optional[AgentInfo]:
        markers = [
            self.CODEX_DIR,
            self.PROJECT_SKILLS_DIR,
            self.RULES_FILENAME,
            self.RULES_OVERRIDE_FILENAME,
            self.PLUGIN_MANIFEST,
        ]
        found = [marker for marker in markers if os.path.exists(os.path.join(project_root, marker))]
        if not found:
            return None

        config_paths = [
            path for path in (self.CODEX_CONFIG_FILE, self.PLUGIN_MANIFEST)
            if os.path.isfile(os.path.join(project_root, path))
        ]
        rules_files = [
            path for path in (self.RULES_OVERRIDE_FILENAME, self.RULES_FILENAME)
            if os.path.isfile(os.path.join(project_root, path))
        ]

        return AgentInfo(
            agent_id=self.agent_id,
            display_name=self.display_name,
            detected=True,
            detection_reason=f"Found Codex project marker: {', '.join(found)}",
            config_paths=config_paths,
            prompts_dir=self.PROJECT_SKILLS_DIR,
            supports_symlinks=True,
            rules_files=rules_files,
        )

    def _link_existing_project_skills(self, source_dir: str, target_dir: str) -> list[str]:
        """Expose canonical skills through a pre-existing real Codex directory."""
        linked: list[str] = []
        if not os.path.isdir(source_dir) or not os.path.isdir(target_dir):
            return linked

        for entry in sorted(os.listdir(source_dir)):
            source_skill = os.path.join(source_dir, entry)
            target_skill = os.path.join(target_dir, entry)
            if not os.path.isdir(source_skill) or not os.path.isfile(os.path.join(source_skill, "SKILL.md")):
                continue
            if os.path.lexists(target_skill):
                continue
            try:
                os.symlink(os.path.relpath(source_skill, target_dir), target_skill, target_is_directory=True)
                linked.append(entry)
            except OSError:
                # A real .agents/skills directory may be on a filesystem that
                # disallows symlinks. Keep it intact and report the limitation.
                continue
        return linked

    def sync_skills_dir(self, project_root: str, skills_dir: str) -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "agent": self.agent_id,
            "action": "sync_skills_dir",
            "skills_dir": skills_dir,
            "target": self.PROJECT_SKILLS_DIR,
            "status": "unknown",
            "details": "",
            "linked": [],
        }

        source_dir = self._canonical_skills_dir(project_root, skills_dir)
        target_dir = self._codex_skills_dir(project_root)
        os.makedirs(source_dir, exist_ok=True)
        os.makedirs(os.path.dirname(target_dir), exist_ok=True)

        if not os.path.lexists(target_dir):
            try:
                os.symlink(os.path.relpath(source_dir, os.path.dirname(target_dir)), target_dir, target_is_directory=True)
                report["status"] = "updated"
                report["details"] = f"Created symlink: {self.PROJECT_SKILLS_DIR} -> {skills_dir}"
            except OSError as exc:
                report["status"] = "error"
                report["details"] = f"Failed to create symlink: {exc}"
            return report

        if os.path.islink(target_dir):
            current_real = os.path.realpath(target_dir)
            source_real = os.path.realpath(source_dir)
            if current_real == source_real:
                report["status"] = "already_configured"
                report["details"] = f"Symlink already exposes {skills_dir}"
            else:
                try:
                    os.unlink(target_dir)
                    os.symlink(os.path.relpath(source_dir, os.path.dirname(target_dir)), target_dir, target_is_directory=True)
                    report["status"] = "updated"
                    report["details"] = f"Updated symlink to {skills_dir}"
                except OSError as exc:
                    report["status"] = "error"
                    report["details"] = f"Failed to update symlink: {exc}"
            return report

        if os.path.isdir(target_dir):
            report["linked"] = self._link_existing_project_skills(source_dir, target_dir)
            report["status"] = "skipped"
            report["details"] = (
                f"{self.PROJECT_SKILLS_DIR} already exists as a real directory. "
                "Preserved it; framework skills will be copied there. "
                "Canonical project skills are linked when the filesystem allows it."
            )
            return report

        report["status"] = "error"
        report["details"] = f"{self.PROJECT_SKILLS_DIR} exists but is not a directory or symlink"
        return report

    def sync_prompts(self, project_root: str, prompts_source: str) -> Dict[str, Any]:
        source_dir = os.path.join(project_root, prompts_source)
        target_dir = self._codex_skills_dir(project_root)
        os.makedirs(target_dir, exist_ok=True)

        report: Dict[str, Any] = {
            "agent": self.agent_id,
            "action": "sync_prompts",
            "source": prompts_source,
            "target": self.PROJECT_SKILLS_DIR,
            "copied": [],
            "skipped": [],
            "missing_in_source": [],
            "errors": [],
        }

        if not os.path.isdir(source_dir):
            report["errors"].append(f"Source directory not found: {source_dir}")
            return report

        source_skills: set[str] = set()
        for root, _, files in os.walk(source_dir):
            for filename in sorted(files):
                if not filename.endswith(".md"):
                    continue
                source_path = os.path.join(root, filename)
                rel_path = os.path.relpath(source_path, source_dir)
                skill_name = self._skill_name(rel_path)
                source_skills.add(skill_name)
                skill_dir = os.path.join(target_dir, skill_name)
                target_path = os.path.join(skill_dir, "SKILL.md")
                os.makedirs(skill_dir, exist_ok=True)

                try:
                    prompt_text = Path(source_path).read_text(encoding="utf-8")
                    rendered = self._render_skill(prompt_text)
                except (OSError, UnicodeError) as exc:
                    report["errors"].append(f"Failed to read {rel_path}: {exc}")
                    continue

                current = self._hash_file(target_path)
                rendered_hash = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
                if current == rendered_hash:
                    report["skipped"].append(skill_name)
                    continue

                try:
                    Path(target_path).write_text(rendered, encoding="utf-8")
                    report["copied"].append(skill_name)
                except OSError as exc:
                    report["errors"].append(f"Failed to write {skill_name}/SKILL.md: {exc}")

        for entry in sorted(os.listdir(target_dir)):
            skill_dir = os.path.join(target_dir, entry)
            if os.path.isdir(skill_dir) and os.path.isfile(os.path.join(skill_dir, "SKILL.md")):
                if entry not in source_skills:
                    try:
                        content = Path(os.path.join(skill_dir, "SKILL.md")).read_text(encoding="utf-8")
                    except (OSError, UnicodeError):
                        continue
                    if "This skill is the OrderSpec command `" in content:
                        report["missing_in_source"].append(entry)

        return report

    def read_rules(self, project_root: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "agent": self.agent_id,
            "files": [],
            "contents": {},
            "errors": [],
        }

        override = os.path.join(project_root, self.RULES_OVERRIDE_FILENAME)
        regular = os.path.join(project_root, self.RULES_FILENAME)
        rule_path = override if os.path.isfile(override) else regular
        if os.path.isfile(rule_path):
            rel_path = os.path.relpath(rule_path, project_root)
            try:
                result["contents"][rel_path] = Path(rule_path).read_text(encoding="utf-8")
                result["files"].append(rel_path)
            except (OSError, UnicodeError) as exc:
                result["errors"].append(f"Failed to read {rel_path}: {exc}")

        return result
