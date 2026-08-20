import unittest
from unittest.mock import MagicMock

from src.applications.dryer_settings.service.dryer_settings_application_service import (
    DryerSettingsApplicationService,
)
from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.peripherals import PeripheralBinding, PeripheralConfig


class TestDryerPeripheralSettings(unittest.TestCase):
    def test_load_and_save_use_dryer_peripheral_commands(self) -> None:
        settings = MagicMock()
        settings.get.side_effect = lambda key: {
            "dryer": DryerConfig(),
            "peripherals": PeripheralConfig(peripherals={
                "dryer": PeripheralBinding(
                    slave_id=10,
                    outputs={"plate": "1"},
                    commands={"open_plate": 2, "close_plate": 0},
                ),
            }),
            "modbus": ModbusConfig(),
        }[key]
        service = DryerSettingsApplicationService(
            settings_service=settings,
            dryer_config_key="dryer",
            modbus_config_key="modbus",
            peripherals_config_key="peripherals",
        )

        config = service.load_config()
        self.assertEqual(config.plate_register, 1)
        self.assertEqual(config.open_plate_value, 2)
        self.assertEqual(config.close_plate_value, 0)

        service.save_config(DryerConfig(plate_register=3, open_plate_value=4, close_plate_value=5))
        saved_peripherals = settings.save.call_args_list[1].args[1]
        saved = saved_peripherals.get("dryer")
        self.assertEqual(saved.outputs["plate"], "3")
        self.assertEqual(saved.commands, {"open_plate": 4, "close_plate": 5})


if __name__ == "__main__":
    unittest.main()
