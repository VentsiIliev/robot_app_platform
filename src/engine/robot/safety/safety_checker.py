import logging
from typing import List

from ..interfaces.i_safety_checker import ISafetyChecker


class SafetyChecker(ISafetyChecker):

    def __init__(self, settings_service=None):
        self._settings = settings_service
        self._logger = logging.getLogger(self.__class__.__name__)

    def is_within_safety_limits(self, position: List[float]) -> bool:
        if not position or len(position) < 3:
            return False
        if self._settings is None:
            return True
        try:
            config = self._settings.get("robot_config") # TODO
            limits = getattr(config, "safety_limits", None)
            if limits is None:
                return True
            x, y, z = position[0], position[1], position[2]
            return (
                limits.x_min <= x <= limits.x_max
                and limits.y_min <= y <= limits.y_max
                and limits.z_min <= z <= limits.z_max
            )
        except Exception:
            self._logger.warning("Safety limit check failed — allowing motion", exc_info=True)
            return True
