from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from src.engine.hardware.peripherals.peripherals import PeripheralConfig

_logger = logging.getLogger(__name__)


class BinaryDeviceAdapter:
    """Expose a device with turn_on/turn_off through the shared app contract."""

    def __init__(self, key: str, label: str, device: Any) -> None:
        self.key = key
        self.label = label
        self._device = device
        self._active: bool | None = None

    def actions(self) -> Mapping[str, str]:
        return {"on": "ON", "off": "OFF"}

    def execute(self, action: str) -> bool:
        if action == "on":
            result = self._device.turn_on()
            ok = True if result is None else bool(result)
            self._active = True if ok else False
        elif action == "off":
            result = self._device.turn_off()
            ok = True if result is None else bool(result)
            self._active = False if ok else True
        else:
            _logger.warning("Unsupported binary action %s.%s", self.key, action)
            return False
        return ok

    def read_state(self) -> Mapping[str, object]:
        return {"active": self._active, "healthy": True}


class VacuumSensorDeviceAdapter:
    def __init__(self, device: Any) -> None:
        self.key = "vacuum_sensor"
        self.label = "Vacuum Sensor"
        self._device = device

    def actions(self) -> Mapping[str, str]:
        return {}

    def execute(self, action: str) -> bool:
        _logger.warning("Vacuum sensor does not support action %s", action)
        return False

    def read_state(self) -> Mapping[str, object]:
        detected = bool(self._device.is_vacuum_detected())
        return {
            "detected": detected,
            "raw": getattr(self._device, "last_raw_value", None),
            "healthy": bool(self._device.is_healthy()),
        }


class PhysicalButtonsDeviceAdapter:
    def __init__(self, device: Any, output_names: Mapping[str, str] | None = None) -> None:
        self.key = "physical_control_buttons"
        self.label = "Physical Control Buttons"
        self._device = device
        self._output_names = dict(output_names or {})

    def actions(self) -> Mapping[str, str]:
        outputs = self._output_names
        return {
            f"output:{name}:on": f"{name} LED ON"
            for name in outputs
        } | {
            f"output:{name}:off": f"{name} LED OFF"
            for name in outputs
        }

    def execute(self, action: str) -> bool:
        try:
            prefix, name, value = action.split(":", 2)
            if prefix != "output" or value not in ("on", "off"):
                return False
            self._device.set_button(name, value == "on")
            return True
        except (ValueError, KeyError):
            _logger.exception("Invalid physical button action: %s", action)
            return False

    def read_state(self) -> Mapping[str, object]:
        return {
            "inputs": dict(self._device.read_states()),
            "outputs": dict(self._device.read_output_states()),
            "healthy": True,
        }


class DryerDeviceAdapter:
    def __init__(self, device: Any) -> None:
        self.key = "dryer"
        self.label = "Dryer"
        self._device = device

    def actions(self) -> Mapping[str, str]:
        return {
            "open_plate": "Open Plate",
            "close_plate": "Close Plate",
            "move_servos": "Move Servos",
            "next_position": "Next Position",
        }

    def execute(self, action: str) -> bool:
        method = getattr(self._device, action, None)
        if method is None:
            return False
        return bool(method())

    def read_state(self) -> Mapping[str, object]:
        state = self._device.get_state()
        return {
            "healthy": bool(state.is_healthy),
            "ready": bool(state.is_ready),
            "plate_on_position": bool(state.plate_on_position),
            "raw": state.raw_status,
        }


def build_device_control_adapters(
    peripheral_config: PeripheralConfig,
    services: Mapping[str, object],
) -> list[object]:
    """Build shared-app adapters for configured, already-constructed devices."""
    labels = {
        "vacuum_pump": "Vacuum Pump",
        "fan": "Fan",
        "laser": "Laser",
    }
    adapters: list[object] = []
    for key in ("vacuum_pump", "fan", "laser"):
        if peripheral_config.get(key) is None or services.get(key) is None:
            continue
        adapters.append(BinaryDeviceAdapter(key, labels[key], services[key]))

    if peripheral_config.get("vacuum_sensor") is not None and services.get("vacuum_sensor") is not None:
        adapters.append(VacuumSensorDeviceAdapter(services["vacuum_sensor"]))
    if peripheral_config.get("physical_control_buttons") is not None and services.get("physical_control_buttons") is not None:
        binding = peripheral_config.get("physical_control_buttons")
        adapters.append(
            PhysicalButtonsDeviceAdapter(
                services["physical_control_buttons"],
                binding.outputs if binding is not None else None,
            )
        )
    if peripheral_config.get("dryer") is not None and services.get("dryer") is not None:
        adapters.append(DryerDeviceAdapter(services["dryer"]))
    return adapters
