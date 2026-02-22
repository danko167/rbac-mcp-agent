from __future__ import annotations

from typing import Iterable, Protocol


class ToolModule(Protocol):
    def register(self, mcp) -> None: ...


def register_modules(mcp, modules: Iterable[ToolModule]) -> None:
    for module in modules:
        module.register(mcp)
