"""Type stubs for a2a.server.agent_execution module."""

from typing import Any

from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import AgentCard

class AgentExecutor:
    """Base class for agent executors in the A2A framework."""
    
    async def start_assistant_turns(
        self,
        context: RequestContext,
        task_updater: TaskUpdater,
        event_queue: EventQueue,
    ) -> None:
        """Start processing assistant turns."""
        ...
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        ...
