import unittest
from src.engine.hardware.generator.models.generator_state import GeneratorState


class TestGeneratorStateDefaults(unittest.TestCase):
    def test_is_on_default_false(self):
        self.assertFalse(GeneratorState().is_on)

    def test_is_healthy_default_false(self):
        self.assertFalse(GeneratorState().is_healthy)

    def test_communication_errors_default_empty(self):
        self.assertEqual(GeneratorState().communication_errors, [])

    def test_elapsed_seconds_default_none(self):
        self.assertIsNone(GeneratorState().elapsed_seconds)

    def test_has_errors_false_when_no_errors(self):
        self.assertFalse(GeneratorState().has_errors)


class TestGeneratorStateHasErrors(unittest.TestCase):
    def test_has_errors_true_when_errors_present(self):
        s = GeneratorState(communication_errors=["timeout"])
        self.assertTrue(s.has_errors)

    def test_has_errors_false_when_list_empty(self):
        s = GeneratorState(communication_errors=[])
        self.assertFalse(s.has_errors)


class TestGeneratorStateStr(unittest.TestCase):
    def test_str_on_healthy(self):
        s = GeneratorState(is_on=True, is_healthy=True)
        result = str(s)
        self.assertIn("ON", result)
        self.assertIn("healthy", result)

    def test_str_off_unhealthy(self):
        s = GeneratorState(is_on=False, is_healthy=False)
        result = str(s)
        self.assertIn("OFF", result)
        self.assertIn("unhealthy", result)

    def test_str_includes_elapsed_when_set(self):
        s = GeneratorState(elapsed_seconds=42.0)
        self.assertIn("42.0", str(s))

    def test_str_excludes_elapsed_when_none(self):
        s = GeneratorState(elapsed_seconds=None)
        self.assertNotIn("elapsed", str(s))


class TestGeneratorStateImmutableErrors(unittest.TestCase):
    def test_separate_instances_have_independent_error_lists(self):
        s1 = GeneratorState()
        s2 = GeneratorState()
        s1.communication_errors.append("err")
        self.assertEqual(s2.communication_errors, [])

