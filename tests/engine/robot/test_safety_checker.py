import unittest
from unittest.mock import MagicMock

from src.engine.robot.safety.safety_checker import SafetyChecker
from src.robot_systems.glue.settings_ids import SettingsID

settings_key = SettingsID.ROBOT_CONFIG
class TestSafetyChecker(unittest.TestCase):

    def setUp(self):
        self.checker = SafetyChecker(settings_key=settings_key,settings_service=None)

    # ------------------------------------------------------------------
    # No settings — always allow
    # ------------------------------------------------------------------

    def test_no_settings_allows_any_position(self):
        self.assertTrue(self.checker.is_within_safety_limits([100.0, 200.0, 300.0, 0, 0, 0]))

    def test_empty_position_blocked(self):
        self.assertFalse(self.checker.is_within_safety_limits([]))

    def test_none_position_blocked(self):
        self.assertFalse(self.checker.is_within_safety_limits(None))

    def test_position_too_short_blocked(self):
        self.assertFalse(self.checker.is_within_safety_limits([10.0, 20.0]))

    # ------------------------------------------------------------------
    # Settings with no limits attr — allow
    # ------------------------------------------------------------------

    def test_settings_without_limits_allows(self):
        settings = MagicMock()
        settings.get.return_value = MagicMock(spec=[])  # no safety_limits attr
        checker = SafetyChecker(settings_key,settings)
        self.assertTrue(checker.is_within_safety_limits([100.0, 200.0, 300.0]))

    # ------------------------------------------------------------------
    # Settings with limits
    # ------------------------------------------------------------------

    def _checker_with_limits(self, x_min, x_max, y_min, y_max, z_min, z_max):
        limits = MagicMock()
        limits.x_min, limits.x_max = x_min, x_max
        limits.y_min, limits.y_max = y_min, y_max
        limits.z_min, limits.z_max = z_min, z_max
        cfg = MagicMock()
        cfg.safety_limits = limits
        settings = MagicMock()
        settings.get.return_value = cfg
        return SafetyChecker(settings_key=settings_key,settings_service=settings)

    def test_position_within_limits_allowed(self):
        checker = self._checker_with_limits(-500, 500, -500, 500, 0, 800)
        self.assertTrue(checker.is_within_safety_limits([100.0, -200.0, 400.0, 0, 0, 0]))

    def test_x_exceeds_max_blocked(self):
        checker = self._checker_with_limits(-500, 500, -500, 500, 0, 800)
        self.assertFalse(checker.is_within_safety_limits([600.0, 0.0, 400.0]))

    def test_z_below_min_blocked(self):
        checker = self._checker_with_limits(-500, 500, -500, 500, 0, 800)
        self.assertFalse(checker.is_within_safety_limits([0.0, 0.0, -10.0]))

    def test_settings_exception_fails_open(self):
        settings = MagicMock()
        settings.get.side_effect = RuntimeError("config error")
        checker = SafetyChecker(settings_key,settings)
        self.assertTrue(checker.is_within_safety_limits([100.0, 200.0, 300.0]))