import logging
from enum import Enum
from typing import Callable

from ..interfaces.i_motion_service import IMotionService


class NavigationService:

    def __init__(self, motion: IMotionService, settings_key, settings_service=None):
        if not isinstance(settings_key, Enum):
            raise TypeError(
                f"NavigationService: settings_key must be an Enum value, "
                f"got {type(settings_key).__name__!r}."
            )
        self._motion   = motion
        self._key      = settings_key
        self._settings = settings_service
        self._logger   = logging.getLogger(self.__class__.__name__)

    def move_to_group(self, group_name: str, wait_cancelled: Callable[[], bool] | None = None) -> bool:
        try:
            config   = self._get_config()
            group    = self._get_group(config, group_name)
            position = group.parse_position()
            if position is None:
                self._logger.error("Group '%s' has no position configured", group_name)
                return False
            return self._motion.move_ptp(
                position=list(position),
                tool=config.robot_tool,
                user=config.robot_user,
                velocity=group.velocity,
                acceleration=group.acceleration,
                wait_to_reach=True,
                wait_cancelled=wait_cancelled,
            )
        except Exception:
            import traceback
            traceback.print_exc()
            self._logger.exception("move_to_group('%s') failed", group_name)
            return False

    def move_linear_group(self, group_name: str) -> bool:
        try:
            config = self._get_config()
            group  = self._get_group(config, group_name)
            points = group.parse_points()
            if not points:
                self._logger.error("Group '%s' has no points configured", group_name)
                return False
            for pt in points:
                ok = self._motion.move_linear(
                    position=pt,
                    tool=config.robot_tool,
                    user=config.robot_user,
                    velocity=group.velocity,
                    acceleration=group.acceleration,
                )
                if not ok:
                    return False
            return True
        except Exception:
            self._logger.exception("move_linear_group('%s') failed", group_name)
            return False

    def get_group_names(self) -> list[str]:
        try:
            return list(self._get_config().movement_groups.keys())
        except Exception:
            return []

    def _get_config(self):
        if self._settings is None:
            raise RuntimeError("NavigationService has no settings_service")
        return self._settings.get(self._key)

    def _get_group(self, config, name: str):
        groups = getattr(config, "movement_groups", {})
        group  = groups.get(name)
        if group is None:
            raise KeyError(
                f"Movement group '{name}' not found. "
                f"Available: {list(groups.keys())}"
            )
        return group

    def move_to_position(
        self,
        position: list,
        group_name: str,
        wait_cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        """Move to an explicit position using the velocity/acceleration of the named group."""
        try:
            config = self._get_config()
            group  = self._get_group(config, group_name)
            return self._motion.move_ptp(
                position=position,
                tool=config.robot_tool,
                user=config.robot_user,
                velocity=group.velocity,
                acceleration=group.acceleration,
                wait_to_reach=True,
                wait_cancelled=wait_cancelled,
            )
        except Exception:
            self._logger.exception("move_to_position (group='%s') failed", group_name)
            return False
