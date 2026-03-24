from __future__ import annotations

from typing import Protocol, Callable


class IRobotSettingsNavigation(Protocol):
    def move_to_group(self, group_name: str, wait_cancelled: Callable[[], bool] | None = None) -> bool:
        ...

    def move_linear_group(self, group_name: str) -> bool:
        ...

    def move_to_position(
        self,
        position: list,
        group_name: str,
        wait_cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        ...
