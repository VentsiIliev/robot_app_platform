import unittest
from copy import deepcopy

from src.robot_systems.glue.applications.glue_settings.model.mapper import GlueSettingsMapper
from src.robot_systems.glue.settings.glue import GlueSettings


class TestGlueSettingsMapperToFlatDict(unittest.TestCase):

    def setUp(self):
        self.settings = GlueSettings()
        self.flat     = GlueSettingsMapper.to_flat_dict(self.settings)

    def test_all_expected_keys_present(self):
        expected = {
            "spray_width", "spraying_height", "fan_speed",
            "time_between_generator_and_glue", "motor_speed",
            "reverse_duration", "speed_reverse", "rz_angle",
            "glue_type", "generator_timeout", "time_before_motion",
            "time_before_stop", "reach_start_threshold", "reach_end_threshold",
            "initial_ramp_speed", "forward_ramp_steps", "reverse_ramp_steps",
            "initial_ramp_speed_duration", "spray_on",
        }
        self.assertEqual(expected, set(self.flat.keys()))

    def test_spray_width_value(self):
        s = GlueSettings(spray_width=7.5)
        self.assertEqual(GlueSettingsMapper.to_flat_dict(s)["spray_width"], 7.5)

    def test_spray_on_value(self):
        s = GlueSettings(spray_on=True)
        self.assertTrue(GlueSettingsMapper.to_flat_dict(s)["spray_on"])

    def test_glue_type_value(self):
        s = GlueSettings(glue_type="Type B")
        self.assertEqual(GlueSettingsMapper.to_flat_dict(s)["glue_type"], "Type B")

    def test_motor_speed_value(self):
        s = GlueSettings(motor_speed=8000.0)
        self.assertEqual(GlueSettingsMapper.to_flat_dict(s)["motor_speed"], 8000.0)

    def test_forward_ramp_steps_value(self):
        s = GlueSettings(forward_ramp_steps=5)
        self.assertEqual(GlueSettingsMapper.to_flat_dict(s)["forward_ramp_steps"], 5)


class TestGlueSettingsMapperFromFlatDict(unittest.TestCase):

    def setUp(self):
        self.base = GlueSettings()
        self.flat = GlueSettingsMapper.to_flat_dict(self.base)

    def test_spray_width_updated(self):
        flat = dict(self.flat, spray_width=12.5)
        r = GlueSettingsMapper.from_flat_dict(flat, self.base)
        self.assertEqual(r.spray_width, 12.5)

    def test_spray_on_updated_true(self):
        flat = dict(self.flat, spray_on=True)
        r = GlueSettingsMapper.from_flat_dict(flat, self.base)
        self.assertTrue(r.spray_on)

    def test_spray_on_updated_false(self):
        flat = dict(self.flat, spray_on=False)
        r = GlueSettingsMapper.from_flat_dict(flat, self.base)
        self.assertFalse(r.spray_on)

    def test_glue_type_updated(self):
        flat = dict(self.flat, glue_type="Type C")
        r = GlueSettingsMapper.from_flat_dict(flat, self.base)
        self.assertEqual(r.glue_type, "Type C")

    def test_motor_speed_updated(self):
        flat = dict(self.flat, motor_speed=9999.0)
        r = GlueSettingsMapper.from_flat_dict(flat, self.base)
        self.assertEqual(r.motor_speed, 9999.0)

    def test_forward_ramp_steps_cast_to_int(self):
        flat = dict(self.flat, forward_ramp_steps=3)
        r = GlueSettingsMapper.from_flat_dict(flat, self.base)
        self.assertIsInstance(r.forward_ramp_steps, int)
        self.assertEqual(r.forward_ramp_steps, 3)

    def test_missing_keys_fall_back_to_base(self):
        r = GlueSettingsMapper.from_flat_dict({}, self.base)
        self.assertEqual(r.spray_width,   self.base.spray_width)
        self.assertEqual(r.motor_speed,   self.base.motor_speed)
        self.assertEqual(r.glue_type,     self.base.glue_type)

    def test_does_not_mutate_base(self):
        original = deepcopy(self.base)
        GlueSettingsMapper.from_flat_dict({"spray_width": 99.0}, self.base)
        self.assertEqual(self.base.spray_width, original.spray_width)

    def test_full_roundtrip(self):
        s    = GlueSettings(spray_width=3.3, motor_speed=7777.0, glue_type="Type B", spray_on=True)
        flat = GlueSettingsMapper.to_flat_dict(s)
        r    = GlueSettingsMapper.from_flat_dict(flat, s)
        self.assertEqual(r.spray_width,  s.spray_width)
        self.assertEqual(r.motor_speed,  s.motor_speed)
        self.assertEqual(r.glue_type,    s.glue_type)
        self.assertEqual(r.spray_on,     s.spray_on)


if __name__ == "__main__":
    unittest.main()