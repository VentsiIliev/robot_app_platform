import unittest
from unittest.mock import MagicMock

from src.applications.dryer_settings.service.dryer_settings_application_service import (
    DryerSettingsApplicationService,
)
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.peripherals import (
    PeripheralBinding,
    PeripheralConfig,
    PeripheralConfigSerializer,
)


class TestDryerSettingsPersistence(unittest.TestCase):
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

    def test_load_and_save_use_dedicated_dryer_settings(self) -> None:
        settings = MagicMock()
        live_controller = MagicMock()
        current = DryerConfig(pwm_open_vrytka=700, acceleration=0.2)
        settings.get.return_value = current
        service = DryerSettingsApplicationService(
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

    def test_enable_failure_is_persisted_and_reported(self) -> None:
        settings = MagicMock()
        dryer_config = DryerConfig()
        peripherals = PeripheralConfig({"dryer": PeripheralBinding(slave_id=10, enabled=False)})
        settings.get.side_effect = lambda key: {
            "dryer": dryer_config,
            "peripherals": peripherals,
        }[key]
        live_service = MagicMock()
        live_service.enable.return_value = False
        live_service.last_error = "No response from dryer"
        service = DryerSettingsApplicationService(
            settings_service=settings,
            dryer_config_key="dryer",
            modbus_config_key="modbus",
            peripherals_config_key="peripherals",
            live_controller=live_service,
        )

        with self.assertRaisesRegex(RuntimeError, "No response"):
            service.set_enabled(True)

        saved = settings.save.call_args.args[1].peripherals["dryer"]
        self.assertFalse(saved.enabled)


if __name__ == "__main__":
    unittest.main()
