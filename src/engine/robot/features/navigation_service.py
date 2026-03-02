import logging
from enum import Enum
from typing import Optional, List

from ..interfaces.i_motion_service import IMotionService

# TODO REMOVE THE HARDCODED GROUP NAMES
_GROUP_HOME        = "HOME"
_GROUP_LOGIN       = "LOGIN"
_GROUP_CALIBRATION = "CALIBRATION"


class NavigationService:

    def __init__(self, motion: IMotionService,settings_key, settings_service=None):
        if not isinstance(settings_key, Enum):
            raise TypeError(
                f"SafetyChecker: settings_key must be an Enum value, got {type(settings_key).__name__!r}. "
                f"Use a constant from settings_ids, not a bare string."
            )
        self._motion = motion
        self.settings_key = settings_key
        self._settings = settings_service
        self._logger = logging.getLogger(self.__class__.__name__)

    def move_home(self, z_offset: float = 0.0) -> bool:
        try:
            config = self._get_config()
            group  = self._get_group(config, _GROUP_HOME)
            position = group.parse_position()
            if position is None:
                self._logger.error("HOME position not configured")
                return False
            position = list(position)
            position[2] += z_offset
            return self._motion.move_ptp(
                position=position,
                tool=config.robot_tool,
                user=config.robot_user,
                velocity=group.velocity,
                acceleration=group.acceleration,
                wait_to_reach=True,
            )
        except Exception:
            self._logger.exception("move_home failed")
            return False

    def move_to_calibration_position(self, z_offset: float = 0.0) -> bool:
        try:
            config = self._get_config()
            group  = self._get_group(config, _GROUP_CALIBRATION)
            position = group.parse_position()
            if position is None:
                self._logger.error("CALIBRATION position not configured")
                return False
            position = list(position)
            position[2] += z_offset
            return self._motion.move_ptp(
                position=position,
                tool=config.robot_tool,
                user=config.robot_user,
                velocity=group.velocity,
                acceleration=group.acceleration,
                wait_to_reach=True,
            )
        except Exception:
            self._logger.exception("move_to_calibration_position failed")
            return False

    def move_to_login_position(self) -> bool:
        try:
            config = self._get_config()
            group  = self._get_group(config, _GROUP_LOGIN)
            position = group.parse_position()
            if position is None:
                self._logger.error("LOGIN position not configured")
                return False
            return self._motion.move_ptp(
                position=list(position),
                tool=config.robot_tool,
                user=config.robot_user,
                velocity=group.velocity,
                acceleration=group.acceleration,
                wait_to_reach=True,
            )
        except Exception:
            self._logger.exception("move_to_login_position failed")
            return False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_config(self):
        if self._settings is None:
            raise RuntimeError("NavigationService has no settings_service — cannot navigate")
        return self._settings.get(self.settings_key)

    def _get_group(self, config, name: str):
        groups = getattr(config, "movement_groups", {})
        group = groups.get(name)
        if group is None:
            raise KeyError(
                f"Movement group '{name}' not found in robot config. "
                f"Available: {list(groups.keys())}"
            )
        return group