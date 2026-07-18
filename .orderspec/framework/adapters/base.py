from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List

@dataclass
class AgentInfo:
    agent_id: str
    display_name: str
    detected: bool = False
    detection_reason: str = ""
    config_paths: List[str] = field(default_factory=list)
    prompts_dir: str = ""
    supports_symlinks: bool = False
    rules_files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class AgentAdapter(ABC):
    agent_id: str = "base"
    SUBAGENT_RULES_MARKER = "<!-- ORDERSPEC:ADAPTER_SUBAGENT_RULES -->"

    @abstractmethod
    def detect(self, project_root: str) -> Optional[AgentInfo]:
        """Вернуть AgentInfo если агент установлен/активен, иначе None."""
        pass

    @abstractmethod
    def sync_skills_dir(self, project_root: str, skills_dir: str) -> Dict[str, Any]:
        """Прописать директорию скиллов в конфиг агента."""
        pass

    @abstractmethod
    def sync_prompts(self, project_root: str, prompts_source: str) -> Dict[str, Any]:
        """Синхронизировать промпты из prompts_source в локальную директорию агента."""
        pass

    @abstractmethod
    def read_rules(self, project_root: str) -> Dict[str, Any]:
        """Прочитать существующие rule-файлы агента (AGENTS.md и т.д.)."""
        pass

    def subagent_policy(self) -> Dict[str, Any]:
        """Describe how this agent discovers and manages delegated workers.

        Sub-agent orchestration is a runtime concern, so adapters expose the
        agent-specific discovery/configuration rules without forcing the
        framework core to know a particular config format.
        """
        return {
            "supports_subagents": False,
            "management": "runtime_only",
            "project_scope": None,
            "global_scope": None,
            "built_in_agents": [],
        }

    def subagent_rules(self, command: str) -> str:
        """Return runtime-native delegation rules injected into a command.

        Worker discovery and dispatch syntax change with the local agent, so
        these rules belong to adapters rather than the agent-agnostic prompt
        source. ``agents_sync.py sync`` materializes them in delivered files.
        """
        return (
            "## Adapter-owned worker rules\n\n"
            "This runtime has no adapter-managed named-worker surface. Use the "
            "command's documented local mode; do not infer worker readiness from "
            "`.orderspec/state/agents.json`."
        )

    def render_prompt(self, prompt_text: str, command: str) -> str:
        """Inject adapter-owned runtime rules into a canonical prompt."""
        if self.SUBAGENT_RULES_MARKER not in prompt_text:
            return prompt_text
        return prompt_text.replace(
            self.SUBAGENT_RULES_MARKER,
            self.subagent_rules(command).rstrip(),
        )

    def inspect_subagents(
        self,
        project_root: str,
        requested_name: Optional[str] = None,
        scope: str = "project",
    ) -> Dict[str, Any]:
        """Inspect available workers for this agent.

        Agents without a known project configuration surface still return a
        deterministic report. This keeps future adapters additive and lets
        callers use one protocol for every command that may delegate work.
        """
        policy = self.subagent_policy()
        return {
            "agent": self.agent_id,
            "scope": scope,
            "requested_name": requested_name,
            "status": "unsupported",
            "supports_subagents": policy.get("supports_subagents", False),
            "policy": policy,
            "agents": [],
            "errors": [],
        }

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
        """Configure a worker using the agent's native configuration format."""
        return {
            "agent": self.agent_id,
            "scope": scope,
            "name": name,
            "status": "unsupported",
            "details": "This agent adapter has no sub-agent configuration surface.",
        }
