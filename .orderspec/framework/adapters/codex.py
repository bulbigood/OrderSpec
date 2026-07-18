import hashlib
import json
import os
import re
import tempfile
import tomllib
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
    PROJECT_AGENTS_DIR = ".codex/agents"
    GLOBAL_AGENTS_DIR = "~/.codex/agents"
    RULES_FILENAME = "AGENTS.md"
    RULES_OVERRIDE_FILENAME = "AGENTS.override.md"
    PLUGIN_MANIFEST = ".codex-plugin/plugin.json"

    BUILT_IN_AGENTS = {
        "default": "General-purpose fallback agent.",
        "worker": "Execution-focused agent for implementation and fixes.",
        "explorer": "Read-heavy codebase exploration agent.",
    }
    REASONING_EFFORTS = {
        "none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"
    }
    ORDERSPEC_WORKERS = (
        "orderspec.worker.weak",
        "orderspec.worker.medium",
        "orderspec.worker.strong",
    )
    REQUIRED_ORDERSPEC_WORKERS = ("orderspec.worker.weak",)
    ORDERSPEC_WORKER_INSTRUCTIONS = (
        "OrderSpec worker protocol version 1. Execute exactly one worker_envelope "
        "from the coordinator, obey its default-deny capabilities and exact read/write "
        "bounds, never start another worker, and return only the required JSON result."
    )

    def subagent_rules(self, command: str) -> str:
        if command == "order.bootstrap":
            return """## Codex worker provisioning (adapter-owned)

Codex project workers are native TOML definitions under `.codex/agents/`.
Current OrderSpec execution requires only `orderspec.worker.weak`. The reserved
medium/strong roles are not provisioned until a deterministic framework consumer
uses them.

Inspect the required role through `agents_sync.py subagents inspect --agent codex
--name orderspec.worker.weak --json`. If it is absent, invalid, or no longer an
appropriate current candidate, use the runtime's current model knowledge or
documentation to propose an exact `model` and `model_reasoning_effort`. Reliability
for bounded envelope execution is the first criterion; cost is secondary. Show the
mapping and brief capability/cost rationale, and confirm that the selected effort is
supported by that model in the current runtime. Then obtain explicit operator confirmation.
Do not let a script choose models and do not use inherited or built-in workers
for these roles. After confirmation, create/update each role only through:

```bash
python3 .orderspec/framework/scripts/agents_sync.py subagents configure \\
  --agent codex --name <role> --model <exact-model-id> \\
  --reasoning <level> --scope project [--overwrite] --json
```

Then run `agents_sync.py subagents validate-orderspec --agent codex --json`.
Bootstrap may complete only when it reports `ready: true`. Never overwrite an
existing role before showing the proposed replacement and receiving confirmation."""
        if command == "order.code":
            return """## Codex worker selection (adapter-owned)

Delegated `/order.code` MUST use the exact custom role
`orderspec.worker.weak`; this is the only OrderSpec role used by current
framework prompts. Before the first dispatch run:

```bash
python3 .orderspec/framework/scripts/agents_sync.py subagents inspect \\
  --agent codex --name orderspec.worker.weak --scope project --json
```

Continue only when it reports `configuration_ready: true`, `source: custom`,
an explicit `model`, and an explicit `reasoning_effort`. Dispatch with the runtime
agent type/name `orderspec.worker.weak` for every task in this command. Never
substitute Codex's built-in `worker`, inherit the coordinator model, create a
worker from `/order.code`, or silently select medium/strong. If the role is
missing or invalid, stop before task writes and route to `/order.bootstrap`.
If the runtime rejects the configured model/effort or dispatch/wait is unavailable,
stop before task writes and use the documented local fallback; do not treat TOML
inspection as proof of runtime availability."""
        return super().subagent_rules(command)

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

    def subagent_policy(self) -> Dict[str, Any]:
        """Return Codex's native custom-agent discovery and config rules."""
        return {
            "supports_subagents": True,
            "management": "standalone_toml",
            "project_scope": self.PROJECT_AGENTS_DIR,
            "global_scope": self.GLOBAL_AGENTS_DIR,
            "built_in_agents": sorted(self.BUILT_IN_AGENTS),
            "required_fields": ["name", "description", "developer_instructions"],
            "optional_fields": [
                "nickname_candidates",
                "model",
                "model_reasoning_effort",
                "sandbox_mode",
                "mcp_servers",
                "skills.config",
            ],
            "reasoning_efforts": sorted(self.REASONING_EFFORTS),
            "name_source_of_truth": "name field in TOML",
            "orderspec_roles": list(self.ORDERSPEC_WORKERS),
            "required_orderspec_roles": list(self.REQUIRED_ORDERSPEC_WORKERS),
            "provisioning_owner": "order.bootstrap",
            "current_framework_worker": "orderspec.worker.weak",
        }

    def _subagent_dir(self, project_root: str, scope: str) -> Optional[Path]:
        if scope == "project":
            return Path(project_root) / self.PROJECT_AGENTS_DIR
        if scope == "global":
            return Path(os.path.expanduser(self.GLOBAL_AGENTS_DIR))
        return None

    def _validate_agent_data(
        self,
        data: Any,
        expected_name: Optional[str] = None,
    ) -> list[str]:
        errors: list[str] = []
        if not isinstance(data, dict):
            return ["TOML root must be a table"]

        for field_name in ("name", "description", "developer_instructions"):
            value = data.get(field_name)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"missing or empty required field: {field_name}")

        if expected_name is not None and data.get("name") != expected_name:
            errors.append(
                f"name field is {data.get('name')!r}, expected {expected_name!r}"
            )

        reasoning = data.get("model_reasoning_effort")
        if reasoning is not None:
            if not isinstance(reasoning, str) or reasoning not in self.REASONING_EFFORTS:
                errors.append(
                    "model_reasoning_effort must be one of: "
                    + ", ".join(sorted(self.REASONING_EFFORTS))
                )

        nicknames = data.get("nickname_candidates")
        if nicknames is not None:
            if (
                not isinstance(nicknames, list)
                or not nicknames
                or any(not isinstance(item, str) or not item.strip() for item in nicknames)
                or len(set(nicknames)) != len(nicknames)
            ):
                errors.append("nickname_candidates must be a non-empty list of unique strings")

        agent_name = data.get("name")
        if agent_name in self.ORDERSPEC_WORKERS:
            model = data.get("model")
            if not isinstance(model, str) or not model.strip():
                errors.append("OrderSpec worker roles require an explicit non-empty model")
            if not isinstance(reasoning, str) or not reasoning:
                errors.append("OrderSpec worker roles require explicit model_reasoning_effort")
            if data.get("developer_instructions") != self.ORDERSPEC_WORKER_INSTRUCTIONS:
                errors.append("OrderSpec worker developer_instructions do not match protocol version 1")

        return errors

    def _read_custom_agent(self, path: Path) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "file": str(path),
            "name": None,
            "source": "custom",
            "valid": False,
            "errors": [],
        }
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            result["errors"] = [f"failed to read: {exc}"]
            return result
        except tomllib.TOMLDecodeError as exc:
            result["errors"] = [f"invalid TOML: {exc}"]
            return result

        result["name"] = data.get("name") if isinstance(data, dict) else None
        result["errors"] = self._validate_agent_data(data)
        result["valid"] = not result["errors"]
        if result["valid"]:
            result["description"] = data["description"]
            if "model" in data:
                result["model"] = data["model"]
            if "model_reasoning_effort" in data:
                result["model_reasoning_effort"] = data["model_reasoning_effort"]
        return result

    def inspect_subagents(
        self,
        project_root: str,
        requested_name: Optional[str] = None,
        scope: str = "project",
    ) -> Dict[str, Any]:
        """Inspect built-in and custom Codex agents without changing files."""
        agents_dir = self._subagent_dir(project_root, scope)
        result: Dict[str, Any] = {
            "agent": self.agent_id,
            "scope": scope,
            "directory": str(agents_dir) if agents_dir else None,
            "requested_name": requested_name,
            "status": "ok",
            "supports_subagents": True,
            "policy": self.subagent_policy(),
            "agents": [],
            "errors": [],
        }

        if agents_dir is None:
            result["status"] = "error"
            result["errors"].append(f"unsupported scope: {scope}")
            return result

        for name, description in sorted(self.BUILT_IN_AGENTS.items()):
            result["agents"].append({
                "name": name,
                "source": "builtin",
                "file": None,
                "valid": True,
                "configured": True,
                "description": description,
            })

        if agents_dir.is_dir():
            for path in sorted(agents_dir.glob("*.toml")):
                if not path.is_file():
                    continue
                entry = self._read_custom_agent(path)
                entry["file"] = os.path.relpath(path, project_root) if scope == "project" else str(path)
                entry["configured"] = bool(entry.get("valid"))
                result["agents"].append(entry)

        if requested_name is not None:
            matches = [entry for entry in result["agents"] if entry.get("name") == requested_name]
            custom_matches = [entry for entry in matches if entry.get("source") == "custom"]
            builtin_matches = [entry for entry in matches if entry.get("source") == "builtin"]
            if custom_matches:
                valid_matches = [entry for entry in custom_matches if entry.get("valid")]
                if len(custom_matches) > 1:
                    result["status"] = "invalid"
                    result["errors"].append(
                        f"multiple custom agent files declare name {requested_name!r}"
                    )
                elif not valid_matches:
                    result["status"] = "invalid"
                entry = custom_matches[0]
                result["requested"] = {
                    "name": requested_name,
                    "configured": bool(valid_matches) and len(custom_matches) == 1,
                    "valid": bool(valid_matches) and len(custom_matches) == 1,
                    "source": "custom",
                    "file": entry.get("file"),
                    "reasoning_effort": entry.get("model_reasoning_effort"),
                    "model": entry.get("model"),
                    "errors": entry.get("errors", []),
                    "configuration_ready": bool(valid_matches) and len(custom_matches) == 1,
                }
            elif builtin_matches:
                result["requested"] = {
                    "name": requested_name,
                    "configured": True,
                    "valid": True,
                    "source": "builtin",
                    "file": None,
                    "reasoning_effort": "inherited",
                }
            else:
                result["status"] = "missing"
                result["requested"] = {
                    "name": requested_name,
                    "configured": False,
                    "valid": False,
                    "source": None,
                }
        return result

    def _safe_agent_filename(self, name: str) -> Optional[str]:
        if not isinstance(name, str) or not name.strip():
            return None
        if any(char in name for char in ("/", "\\", "\x00")):
            return None
        slug = re.sub(r"[^A-Za-z0-9_-]+", "-", name.strip()).strip("-_")
        if not slug:
            return None
        return f"{slug}.toml"

    def _render_agent_toml(
        self,
        name: str,
        description: str,
        developer_instructions: str,
        reasoning_effort: str,
        model: Optional[str],
    ) -> str:
        lines = [
            f"name = {json.dumps(name, ensure_ascii=False)}",
            f"description = {json.dumps(description, ensure_ascii=False)}",
            f"developer_instructions = {json.dumps(developer_instructions, ensure_ascii=False)}",
        ]
        if model:
            lines.append(f"model = {json.dumps(model, ensure_ascii=False)}")
        lines.append(f"model_reasoning_effort = {json.dumps(reasoning_effort)}")
        return "\n".join(lines) + "\n"

    def configure_subagent(
        self,
        project_root: str,
        name: str,
        reasoning_effort: str,
        scope: str = "project",
        description: Optional[str] = None,
        developer_instructions: Optional[str] = None,
        model: Optional[str] = None,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """Create or explicitly update one native Codex custom-agent file."""
        result: Dict[str, Any] = {
            "agent": self.agent_id,
            "scope": scope,
            "name": name,
            "reasoning_effort": reasoning_effort,
            "status": "error",
            "details": "",
        }

        agents_dir = self._subagent_dir(project_root, scope)
        if agents_dir is None:
            result["details"] = f"Unsupported scope: {scope}"
            return result
        if not isinstance(reasoning_effort, str) or reasoning_effort not in self.REASONING_EFFORTS:
            result["details"] = (
                "Invalid reasoning effort. Choose one of: "
                + ", ".join(sorted(self.REASONING_EFFORTS))
            )
            return result
        if name in self.ORDERSPEC_WORKERS and (
            not isinstance(model, str) or not model.strip()
        ):
            result["details"] = (
                "OrderSpec worker roles require an explicit --model selected "
                "by the local AI agent and approved by the operator"
            )
            return result
        if name in self.ORDERSPEC_WORKERS and developer_instructions not in {
            None,
            self.ORDERSPEC_WORKER_INSTRUCTIONS,
        }:
            result["details"] = "OrderSpec worker instructions are framework-owned"
            return result

        filename = self._safe_agent_filename(name)
        if filename is None:
            result["details"] = (
                "Agent name must be non-empty and must not contain path separators "
                "or NUL characters"
            )
            return result

        inspection = self.inspect_subagents(project_root, requested_name=name, scope=scope)
        requested = inspection.get("requested", {})
        if requested.get("source") == "custom" and requested.get("configured") and not overwrite:
            result["status"] = "already_configured"
            result["details"] = f"Agent '{name}' is already configured"
            result["path"] = requested.get("file")
            return result
        if requested.get("source") == "custom" and requested.get("errors") and not overwrite:
            result["details"] = (
                f"Agent '{name}' has an invalid existing configuration; "
                "use --overwrite only after reviewing it"
            )
            result["errors"] = requested["errors"]
            return result

        role_descriptions = {
            "orderspec.worker.weak": "Executes bounded OrderSpec task packets with the approved weak model.",
            "orderspec.worker.medium": "Handles bounded OrderSpec work requiring balanced semantic capability.",
            "orderspec.worker.strong": "Handles exceptional bounded OrderSpec work requiring the strongest approved model.",
        }
        description = description or role_descriptions.get(
            name,
            "Executes one bounded worker task for an OrderSpec command or skill.",
        )
        developer_instructions = developer_instructions or self.ORDERSPEC_WORKER_INSTRUCTIONS
        if not isinstance(description, str) or not description.strip():
            result["details"] = "description must be a non-empty string"
            return result
        if not isinstance(developer_instructions, str) or not developer_instructions.strip():
            result["details"] = "developer_instructions must be a non-empty string"
            return result

        content = self._render_agent_toml(
            name=name,
            description=description,
            developer_instructions=developer_instructions,
            reasoning_effort=reasoning_effort,
            model=model,
        )
        try:
            tomllib.loads(content)
            agents_dir.mkdir(parents=True, exist_ok=True)
            target = agents_dir / filename
            if target.exists() and requested.get("source") != "custom" and not overwrite:
                existing = self._read_custom_agent(target)
                result["details"] = (
                    f"Target file {filename} already belongs to agent "
                    f"{existing.get('name')!r}; choose another name or use --overwrite"
                )
                return result
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=agents_dir,
                prefix=f".{filename}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(content)
                temporary = Path(handle.name)
            os.replace(temporary, target)
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            try:
                if "temporary" in locals() and temporary.exists():
                    temporary.unlink()
            except OSError:
                pass
            result["details"] = f"Failed to write {target if 'target' in locals() else agents_dir}: {exc}"
            return result

        result["status"] = "updated" if overwrite and requested else "created"
        result["path"] = (
            os.path.relpath(target, project_root) if scope == "project" else str(target)
        )
        result["details"] = f"Configured Codex agent '{name}'"
        return result

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
                    command, _, _ = self._parse_prompt(prompt_text)
                    prompt_text = self.render_prompt(prompt_text, command)
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
