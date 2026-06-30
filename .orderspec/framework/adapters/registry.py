from .kilocode import KiloCodeAdapter
from .claude_code import ClaudeCodeAdapter
from .base import AgentAdapter
from typing import List

def get_all_adapters() -> List[AgentAdapter]:
    """Возвращает список всех доступных адаптеров."""
    return [
        KiloCodeAdapter(),
        ClaudeCodeAdapter(),
        # Сюда будут добавлены: OpenCodeAdapter(), CursorAdapter() и т.д.
    ]

def get_adapter_by_id(agent_id: str) -> AgentAdapter:
    for adapter in get_all_adapters():
        if adapter.agent_id == agent_id:
            return adapter
    raise ValueError(f"Adapter '{agent_id}' not found in registry.")
