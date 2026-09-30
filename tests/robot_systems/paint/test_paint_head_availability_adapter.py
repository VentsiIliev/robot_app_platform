import unittest

from src.robot_systems.paint.hardware.paint_head_availability_adapter import (
    PaintHeadAvailabilityAdapter,
)


class PaintHeadAvailabilityAdapterTests(unittest.TestCase):
    def test_toggle_uses_live_state_and_persists_without_hardware(self) -> None:
        state = {"enabled": True}
        writes = []

        def persist(key: str, enabled: bool) -> None:
            writes.append((key, enabled))
            state["enabled"] = enabled

        adapter = PaintHeadAvailabilityAdapter(
            enabled_provider=lambda: state["enabled"],
            persist_enabled=persist,
        )
        self.assertTrue(adapter.is_enabled())
        self.assertTrue(adapter.set_enabled(False))
        self.assertFalse(adapter.read_state()["enabled"])
        self.assertTrue(adapter.set_enabled(True))
        self.assertEqual(writes, [("paint_head", False), ("paint_head", True)])
        self.assertEqual(adapter.actions(), {})


if __name__ == "__main__":
    unittest.main()
