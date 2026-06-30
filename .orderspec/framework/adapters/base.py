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
