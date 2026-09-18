import unittest

from src.engine.robot.relative_tool_calibration_service import RelativeToolCalibrationService
from src.engine.robot.tool_activation_service import ToolActivationService


class _Registry:
    def __init__(self):
        self.calls = []

    def update_tool(self, tool_id, name, transform, *, persist, collision_profile=None):
        self.calls.append((tool_id, name, list(transform), persist, collision_profile))
        return True, "saved"


class _Activator:
    def __init__(self):
        self.active = None

    def set_active_tool(self, tool):
        self.active = tool
        return True


class RelativeToolCalibrationServiceTests(unittest.TestCase):
    def test_solves_translation_from_same_contact_point(self):
        service = RelativeToolCalibrationService(minimum_samples=3)
        service.capture_reference(
            [100, 200, 300, 0, 0, 0],
            [0, 0, 100, 0, 0, 0],
        )
        for _ in range(3):
            service.capture_candidate([100, 200, 275, 0, 0, 0])

        result = service.solve()

        self.assertEqual(result["absolute_transform"], [0, 0, 125, 0, 0, 0])
        self.assertEqual(result["relative_transform"], [0, 0, 25, 0, 0, 0])
        self.assertEqual(result["sample_count"], 3)
        self.assertEqual(result["max_spread_mm"], 0)

    def test_requires_configured_sample_count(self):
        service = RelativeToolCalibrationService(minimum_samples=2)
        service.capture_reference([0, 0, 0, 0, 0, 0], [0, 0, 100, 0, 0, 0])
        service.capture_candidate([0, 0, 0, 0, 0, 0])
        with self.assertRaisesRegex(RuntimeError, "at least 2"):
            service.solve()

    def test_activation_composes_local_offset_and_activates(self):
        registry = _Registry()
        activator = _Activator()
        service = ToolActivationService(registry, activator)

        ok, _, resolved = service.activate(
            tool_id=2,
            name="TOOL_2",
            reference_transform=[10, 20, 100, 0, 0, 90],
            relative_transform=[5, 0, 25, 0, 0, 0],
        )

        self.assertTrue(ok)
        self.assertAlmostEqual(resolved[0], 10)
        self.assertAlmostEqual(resolved[1], 25)
        self.assertAlmostEqual(resolved[2], 125)
        self.assertEqual(activator.active, 2)
        self.assertEqual(registry.calls[0][0], 2)


if __name__ == "__main__":
    unittest.main()
