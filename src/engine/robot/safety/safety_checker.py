import logging
from enum import Enum
from typing import List

from ..interfaces.i_safety_checker import ISafetyChecker


class SafetyChecker(ISafetyChecker):

    def __init__(self, settings_key,settings_service=None):
        if not isinstance(settings_key, Enum):
            raise TypeError(
                f"SafetyChecker: settings_key must be an Enum value, got {type(settings_key).__name__!r}. "
                f"Use a constant from settings_ids, not a bare string."
            )
        self._settings = settings_service
        self.settings_key = settings_key

        self._logger = logging.getLogger(self.__class__.__name__)

    def is_within_safety_limits(self, position: List[float]) -> bool:
        if not position or len(position) < 3:
            return False
        if self._settings is None:
            return True
        try:
            config = self._settings.get(self.settings_key)
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
