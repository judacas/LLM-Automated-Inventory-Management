from typing import Any, Callable

from database_tools.tools.business_tools import (
    tool_create_business_account,
    tool_get_business_by_domain,
)


class MCPToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, func: Callable[..., Any]) -> None:
        self._tools[name] = func

    def get(self, name: str) -> Callable[..., Any]:
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not registered")
        return self._tools[name]

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())


registry = MCPToolRegistry()

registry.register("create_business_account", tool_create_business_account)
registry.register("get_business_by_domain", tool_get_business_by_domain)