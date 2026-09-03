import unittest
from unittest.mock import MagicMock

from src.applications.device_control.dryer.application_service import (
    DryerControlService,
)
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.peripherals import PeripheralConfigSerializer


class TestDeviceControlDryerPersistence(unittest.TestCase):
    def test_dryer_status_masks_survive_settings_round_trip(self) -> None:
        serializer = PeripheralConfigSerializer()
        config = serializer.from_dict({
            "dryer": {
                "slave_id": 10,
                "statuses": {"ready": 1, "next_pos_done": 64},
            },
        })

        self.assertEqual(
            config.peripherals["dryer"].statuses,
            {"ready": 1, "next_pos_done": 64},
        )
        self.assertEqual(
            serializer.to_dict(config)["dryer"]["statuses"],
            {"ready": 1, "next_pos_done": 64},
        )

    def test_device_control_loads_and_saves_dedicated_dryer_config(self) -> None:
        settings = MagicMock()
        live_controller = MagicMock()
        current = DryerConfig(pwm_open_vrytka=700, acceleration=0.2)
        settings.get.return_value = current
        service = DryerControlService(
            settings_service=settings,
            dryer_config_key="dryer",
            modbus_config_key="modbus",
            peripherals_config_key="peripherals",
            live_controller=live_controller,
        )

        self.assertIs(service.load_config(), current)

        updated = DryerConfig(pwm_open_vrytka=800)
        service.save_config(updated)
        settings.save.assert_called_once_with("dryer", updated)
        live_controller.update_config.assert_called_once_with(updated)

if __name__ == "__main__":
    unittest.main()
