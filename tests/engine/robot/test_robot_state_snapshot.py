import unittest

from src.engine.robot.services.robot_state_snapshot import RobotStateSnapshot


class TestRobotStateSnapshot(unittest.TestCase):

    def _make(self, **kwargs):
        defaults = dict(state="idle", position=[0.0]*6, velocity=0.0, acceleration=0.0)
        defaults.update(kwargs)
        return RobotStateSnapshot(**defaults)

    def test_fields_set_correctly(self):
        s = self._make(state="moving", velocity=30.0, acceleration=20.0)
        self.assertEqual(s.state, "moving")
        self.assertEqual(s.velocity, 30.0)
        self.assertEqual(s.acceleration, 20.0)

    def test_default_extra_is_empty(self):
        s = self._make()
        self.assertEqual(s.extra, {})

    def test_frozen_raises_on_mutation(self):
        s = self._make()
        with self.assertRaises(Exception):
            s.state = "moving"

    def test_with_extra_returns_new_snapshot(self):
        s = self._make()
        s2 = s.with_extra(joint_angles=[1, 2, 3])
        self.assertIsNot(s, s2)
        self.assertEqual(s2.extra["joint_angles"], [1, 2, 3])

    def test_with_extra_merges_existing_extra(self):
        s = self._make()
        s1 = s.with_extra(a=1)
        s2 = s1.with_extra(b=2)
        self.assertEqual(s2.extra, {"a": 1, "b": 2})

    def test_with_extra_preserves_original(self):
        s = self._make()
        s.with_extra(a=1)
        self.assertEqual(s.extra, {})

    def test_with_extra_preserves_other_fields(self):
        s = self._make(state="moving", velocity=50.0)
        s2 = s.with_extra(foo="bar")
        self.assertEqual(s2.state, "moving")
        self.assertEqual(s2.velocity, 50.0)