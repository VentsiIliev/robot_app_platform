import logging
from enum import Enum
from typing import List

from ..interfaces.i_safety_checker import ISafetyChecker


class SafetyChecker(ISafetyChecker):

    def __init__(self, settings_key, settings_service=None):
        if not isinstance(settings_key, Enum):
            raise TypeError(
                f"SafetyChecker: settings_key must be an Enum value, got {type(settings_key).__name__!r}. "
                f"Use a constant from settings_ids, not a bare string."
            )
        self._settings = settings_service
        self.settings_key = settings_key
        self._logger = logging.getLogger(self.__class__.__name__)

    def _compute_violations(self, position: List[float]) -> List[str]:
        if not position or len(position) < 3:
            return ["Position is empty or has fewer than 3 coordinates"]
        if self._settings is None:
            return []
        config = self._settings.get(self.settings_key)
        limits = getattr(config, "safety_limits", None)
        if limits is None:
            return []
        x, y, z = position[0], position[1], position[2]
        violations = []
        if not (limits.x_min <= x <= limits.x_max):
            violations.append(f"X={x:.2f} not in [{limits.x_min}, {limits.x_max}]")
        if not (limits.y_min <= y <= limits.y_max):
            violations.append(f"Y={y:.2f} not in [{limits.y_min}, {limits.y_max}]")
        if not (limits.z_min <= z <= limits.z_max):
            violations.append(f"Z={z:.2f} not in [{limits.z_min}, {limits.z_max}]")
        return violations

    def get_violations(self, position: List[float]) -> List[str]:
        try:
            return self._compute_violations(position)
        except Exception:
            self._logger.warning("Safety limit check failed", exc_info=True)
            return []

    def is_within_safety_limits(self, position: List[float]) -> bool:
        try:
            return len(self._compute_violations(position)) == 0
        except Exception:
            self._logger.warning("Safety limit check failed — allowing motion", exc_info=True)
            return True

    def is_escape_move(self, current: List[float], target: List[float]) -> bool:
        if not current or not target or len(current) < 3 or len(target) < 3:
            return False
        if self._settings is None:
            return True
        try:
            config = self._settings.get(self.settings_key)
            limits = getattr(config, "safety_limits", None)
            if limits is None:
                return True
            cx, cy, cz = current[0], current[1], current[2]
            tx, ty, tz = target[0], target[1], target[2]
            if cx < limits.x_min and tx < cx: return False
            if cx > limits.x_max and tx > cx: return False
            if cy < limits.y_min and ty < cy: return False
            if cy > limits.y_max and ty > cy: return False
            if cz < limits.z_min and tz < cz: return False
            if cz > limits.z_max and tz > cz: return False
            return True
        except Exception:
            self._logger.warning("is_escape_move check failed — allowing", exc_info=True)
            return True
