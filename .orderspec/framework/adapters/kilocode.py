import os
import hashlib
import shutil
from typing import Optional, Dict, Any, List
from .base import AgentAdapter, AgentInfo
from .jsonc_utils import read_jsonc, write_jsonc

class KiloCodeAdapter(AgentAdapter):
    """Adapter for Kilo Code AI agent.
    
    Supports both new format (.kilo/ + kilo.jsonc) and legacy format (.kilocode/).
    Prefers new format when available.
    """
    agent_id: str = "kilocode"
    display_name: str = "Kilo Code"

    # New format locations
    NEW_CONFIG_FILE = "kilo.jsonc"
    NEW_COMMANDS_DIR = ".kilo/commands"
    NEW_DIR = ".kilo"

    # Legacy format locations
    LEGACY_DIR = ".kilocode"
    LEGACY_WORKFLOWS_DIR = ".kilocode/workflows"

    # Rules
    RULES_FILENAME = "AGENTS.md"

    def _detect_format(self, project_root: str) -> Optional[str]:
        """Determine if using new (.kilo/) or legacy (.kilocode/) format.
        
        Returns 'new', 'legacy', or None.
        """
        if os.path.isdir(os.path.join(project_root, self.NEW_DIR)):
            return "new"
        if os.path.isfile(os.path.join(project_root, self.NEW_CONFIG_FILE)):
            return "new"
        if os.path.isdir(os.path.join(project_root, self.LEGACY_DIR)):
            return "legacy"
        return None

    def _get_config_path(self, project_root: str) -> str:
        return os.path.join(project_root, self.NEW_CONFIG_FILE)

    def _get_prompts_target_dir(self, project_root: str) -> str:
        """Get the target directory for prompts based on detected format."""
        fmt = self._detect_format(project_root)
        if fmt == "new":
            return self.NEW_COMMANDS_DIR
        elif fmt == "legacy":
            return self.LEGACY_WORKFLOWS_DIR
        # Default to new format if nothing detected yet
        return self.NEW_COMMANDS_DIR

    def _hash_file(self, filepath: str) -> Optional[str]:
        if not os.path.isfile(filepath):
            return None
        h = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    def detect(self, project_root: str) -> Optional[AgentInfo]:
        fmt = self._detect_format(project_root)
        if fmt is None:
            return None

        if fmt == "new":
            prompts_dir = self.NEW_COMMANDS_DIR
            detection_reason = f"Found .kilo/ directory or kilo.jsonc (new format)"
        else:
            prompts_dir = self.LEGACY_WORKFLOWS_DIR
            detection_reason = f"Found .kilocode/ directory (legacy format, consider migrating to .kilo/)"

        config_path = self._get_config_path(project_root)
        config_paths = [self.NEW_CONFIG_FILE] if os.path.isfile(config_path) else []

        return AgentInfo(
            agent_id=self.agent_id,
            display_name=self.display_name,
            detected=True,
            detection_reason=detection_reason,
            config_paths=config_paths,
            prompts_dir=prompts_dir,
            supports_symlinks=False,
            rules_files=[self.RULES_FILENAME]
        )

    def sync_skills_dir(self, project_root: str, skills_dir: str) -> Dict[str, Any]:
        """Add skills_dir to kilo.jsonc skills.paths array.
        
        This tells Kilo Code to scan .orderspec/skills/ for skill definitions,
        keeping a single source of truth (no copying/symlinking needed).
        """
        report = {
            "agent": self.agent_id,
            "action": "sync_skills_dir",
            "skills_dir": skills_dir,
            "status": "unknown",
            "details": ""
        }

        config_path = self._get_config_path(project_root)

        try:
            config = read_jsonc(config_path)
        except ValueError as e:
            report["status"] = "error"
            report["details"] = f"Failed to read {config_path}: {e}"
            return report

        # Ensure structure exists
        if "skills" not in config:
            config["skills"] = {}
        if "paths" not in config["skills"]:
            config["skills"]["paths"] = []

        existing_paths = config["skills"]["paths"]

        if skills_dir in existing_paths:
            report["status"] = "already_configured"
            report["details"] = f"Path '{skills_dir}' already in skills.paths"
        else:
            existing_paths.append(skills_dir)
            try:
                write_jsonc(config_path, config)
                report["status"] = "updated"
                report["details"] = f"Added '{skills_dir}' to skills.paths in {self.NEW_CONFIG_FILE}"
            except Exception as e:
                report["status"] = "error"
                report["details"] = f"Failed to write {config_path}: {e}"

        return report

    def sync_prompts(self, project_root: str, prompts_source: str) -> Dict[str, Any]:
        """Copy prompt files from source to Kilo Code's commands/workflows directory.
        
        Uses SHA-256 hashing to only copy files that changed.
        Reports files in target that are missing in source (for manual cleanup).
        """
        source_dir = os.path.join(project_root, prompts_source)
        target_subdir = self._get_prompts_target_dir(project_root)
        target_dir = os.path.join(project_root, target_subdir)

        os.makedirs(target_dir, exist_ok=True)

        report = {
            "agent": self.agent_id,
            "action": "sync_prompts",
            "source": prompts_source,
            "target": target_subdir,
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
        """Read external rule files that Kilo Code uses.
        
        Sources:
        1. AGENTS.md (if exists at project root)
        2. Files referenced in kilo.jsonc "instructions" array
        3. Legacy .kilocode/rules/ directory (if exists)
        
        Returns dict with combined rules content for bootstrap integration.
        """
        result = {
            "agent": self.agent_id,
            "files": [],
            "contents": {},
            "errors": []
        }

        # 1. Read AGENTS.md
        agents_md_path = os.path.join(project_root, self.RULES_FILENAME)
        if os.path.isfile(agents_md_path):
            try:
                with open(agents_md_path, 'r', encoding='utf-8') as f:
                    result["contents"][self.RULES_FILENAME] = f.read()
                    result["files"].append(self.RULES_FILENAME)
            except Exception as e:
                result["errors"].append(f"Failed to read {self.RULES_FILENAME}: {e}")

        # 2. Read files from kilo.jsonc instructions array
        config_path = self._get_config_path(project_root)
        try:
            config = read_jsonc(config_path)
            instructions = config.get("instructions", [])
            for pattern in instructions:
                # Handle glob patterns (simple: just check if it's a direct file or use glob)
                import glob
                full_pattern = os.path.join(project_root, pattern)
                for matched_path in glob.glob(full_pattern):
                    if os.path.isfile(matched_path):
                        rel_path = os.path.relpath(matched_path, project_root)
                        if rel_path not in result["contents"]:
                            try:
                                with open(matched_path, 'r', encoding='utf-8') as f:
                                    result["contents"][rel_path] = f.read()
                                    result["files"].append(rel_path)
                            except Exception as e:
                                result["errors"].append(f"Failed to read {rel_path}: {e}")
        except ValueError as e:
            result["errors"].append(f"Failed to read kilo.jsonc: {e}")
        except Exception as e:
            result["errors"].append(f"Unexpected error reading kilo.jsonc: {e}")

        # 3. Read legacy .kilocode/rules/ directory
        legacy_rules_dir = os.path.join(project_root, self.LEGACY_DIR, "rules")
        if os.path.isdir(legacy_rules_dir):
            for root, _, files in os.walk(legacy_rules_dir):
                for file in files:
                    if file.endswith(".md"):
                        abs_path = os.path.join(root, file)
                        rel_path = os.path.relpath(abs_path, project_root)
                        if rel_path not in result["contents"]:
                            try:
                                with open(abs_path, 'r', encoding='utf-8') as f:
                                    result["contents"][rel_path] = f.read()
                                    result["files"].append(rel_path)
                            except Exception as e:
                                result["errors"].append(f"Failed to read {rel_path}: {e}")

        return result
