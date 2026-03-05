import unittest
from src.engine.hardware.generator.models.generator_config import GeneratorConfig


class TestGeneratorConfigDefaults(unittest.TestCase):
    def test_default_relay_register(self):
        self.assertEqual(GeneratorConfig().relay_register, 9)

    def test_default_state_register(self):
        self.assertEqual(GeneratorConfig().state_register, 10)

    def test_default_timeout_minutes(self):
        self.assertEqual(GeneratorConfig().timeout_minutes, 5.0)


class TestGeneratorConfigCustomValues(unittest.TestCase):
    def _make(self):
        return GeneratorConfig(relay_register=1, state_register=2, timeout_minutes=10.0)

    def test_relay_register_set(self):
        self.assertEqual(self._make().relay_register, 1)

    def test_state_register_set(self):
        self.assertEqual(self._make().state_register, 2)

    def test_timeout_minutes_set(self):
        self.assertEqual(self._make().timeout_minutes, 10.0)

