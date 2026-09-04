from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from typing import Any, Callable

from src.engine.core.i_health_checkable import IHealthCheckable
from src.engine.hardware.peripherals.peripherals import PeripheralConfig

_logger = logging.getLogger(__name__)


class BinaryDeviceAdapter:
    """Expose a device with turn_on/turn_off through the shared app contract."""

    def __init__(self, key: str, label: str, device: Any, *, enabled: bool = True,
                 persist_enabled: Callable[[str, bool], None] | None = None,
                 enable_check: Callable[[], object] | None = None,
                 commands: Mapping[str, int] | None = None) -> None:
        self.key = key
        self.label = label
        self._device = device
        self._active: bool | None = None
        self._enabled = bool(enabled)
        self._persist_enabled = persist_enabled
        self._enable_check = enable_check
        self._commands = dict(commands or {})
        self._last_error: str | None = None

    def set_enabled(self, enabled: bool) -> bool:
        if enabled and self._enable_check is not None:
            try:
                self._enable_check()
            except Exception as exc:
                self._enabled = False
                self._last_error = str(exc) or f"{self.label} register read failed"
                if self._persist_enabled is not None:
                    self._persist_enabled(self.key, False)
                _logger.exception("%s enable check failed", self.label)
                return False
        if not enabled:
            try:
                self._device.turn_off()
            except Exception as exc:
                self._last_error = str(exc)
                return False
        self._enabled = bool(enabled)
        if self._persist_enabled is not None:
            self._persist_enabled(self.key, self._enabled)
        self._last_error = None
        return self._enabled == bool(enabled)

    def is_enabled(self) -> bool:
        return self._enabled

    def last_error(self) -> str | None:
        return self._last_error

    def actions(self) -> Mapping[str, str]:
        return {
            command: command.replace("_", " ").upper()
            for command in self._commands
            if command in ("on", "off")
        }

    def execute(self, action: str) -> bool:
        if not self._enabled:
            self._last_error = f"{self.label} is disabled"
            return False
        if action not in self._commands:
            _logger.warning("Unconfigured binary action %s.%s", self.key, action)
            return False
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
        return {"enabled": self._enabled, "active": self._active,
                "healthy": self._cached_health(), "error": self._last_error or ""}

    def _cached_health(self) -> bool | None:
        if isinstance(self._device, IHealthCheckable):
            return bool(self._device.is_healthy())
        return None


class VacuumSensorDeviceAdapter:
    def __init__(self, device: Any, *, enabled: bool = True,
                 persist_enabled: Callable[[str, bool], None] | None = None) -> None:
        self.key = "vacuum_sensor"
        self.label = "Vacuum Sensor"
        self._device = device
        self._enabled = bool(enabled)
        self._persist_enabled = persist_enabled
        self._last_error: str | None = None

    def set_enabled(self, enabled: bool) -> bool:
        if enabled:
            # is_vacuum_detected performs the real register read and records
            # communication health independently of the detected value.
            self._device.is_vacuum_detected()
            if not self._device.is_healthy():
                self._enabled = False
                self._last_error = "Vacuum sensor register read failed"
                if self._persist_enabled is not None:
                    self._persist_enabled(self.key, False)
                return False
        self._enabled = bool(enabled)
        if self._persist_enabled is not None:
            self._persist_enabled(self.key, self._enabled)
        self._last_error = None
        return True

    def is_enabled(self) -> bool: return self._enabled
    def last_error(self) -> str | None: return self._last_error

    def actions(self) -> Mapping[str, str]:
        return {}

    def execute(self, action: str) -> bool:
        _logger.warning("Vacuum sensor does not support action %s", action)
        return False

    def read_state(self) -> Mapping[str, object]:
        if not self._enabled:
            return {"enabled": False, "healthy": False, "error": "Vacuum Sensor is disabled"}
        detected = bool(self._device.is_vacuum_detected())
        return {
            "detected": detected,
            "raw": getattr(self._device, "last_raw_value", None),
            "healthy": bool(self._device.is_healthy()),
        }


class PhysicalButtonsDeviceAdapter:
    def __init__(self, device: Any, output_names: Mapping[str, str] | None = None,
                 *, enabled: bool = True,
                 persist_enabled: Callable[[str, bool], None] | None = None,
                 commands: Mapping[str, int] | None = None) -> None:
        self.key = "physical_control_buttons"
        self.label = "Physical Control Buttons"
        self._device = device
        self._output_names = dict(output_names or {})
        self._commands = dict(commands or {})
        self._enabled = bool(enabled)
        self._persist_enabled = persist_enabled
        self._last_error: str | None = None

    def set_enabled(self, enabled: bool) -> bool:
        if enabled:
            try:
                self._device.read_states()
            except Exception as exc:
                self._enabled = False
                self._last_error = str(exc) or "Physical controls register read failed"
                if self._persist_enabled is not None:
                    self._persist_enabled(self.key, False)
                _logger.exception("Physical controls enable check failed")
                return False
        self._enabled = bool(enabled)
        if self._persist_enabled is not None:
            self._persist_enabled(self.key, self._enabled)
        self._last_error = None
        return True

    def is_enabled(self) -> bool: return self._enabled
    def last_error(self) -> str | None: return self._last_error

    def actions(self) -> Mapping[str, str]:
        return {
            command: command.replace("_", " ").title()
            for command in self._commands
            if self._button_command(command) is not None
        }

    def execute(self, action: str) -> bool:
        if not self._enabled:
            return False
        try:
            parsed = self._button_command(action)
            if parsed is None or action not in self._commands:
                return False
            name, _operation = parsed
            self._device.set_button(name, bool(self._commands[action]))
            return True
        except KeyError:
            _logger.exception("Invalid physical button action: %s", action)
            return False

    def _button_command(self, command: str) -> tuple[str, str] | None:
        name, separator, operation = command.rpartition("_")
        if not separator or name not in self._output_names or operation not in ("on", "off"):
            return None
        return name, operation

    def read_state(self) -> Mapping[str, object]:
        if not self._enabled:
            return {"enabled": False, "healthy": False, "error": "Physical controls are disabled"}
        return {
            "inputs": dict(self._device.read_states()),
            "outputs": dict(self._device.read_output_states()),
            "healthy": (
                bool(self._device.is_healthy())
                if isinstance(self._device, IHealthCheckable)
                else None
            ),
        }


class DryerDeviceAdapter:
    def __init__(self, device: Any,
                 persist_enabled: Callable[[str, bool], None] | None = None,
                 commands: Mapping[str, int] | None = None) -> None:
        self.key = "dryer"
        self.label = "Dryer"
        self._device = device
        self._persist_enabled = persist_enabled
        self._commands = dict(commands or {})

    def set_enabled(self, enabled: bool) -> bool:
        ok = bool(self._device.enable()) if enabled else (self._device.disable() is None)
        actual = bool(self._device.is_enabled())
        if self._persist_enabled is not None:
            self._persist_enabled(self.key, actual)
        return ok and actual == bool(enabled)

    def is_enabled(self) -> bool: return bool(self._device.is_enabled())
    def last_error(self) -> str | None: return self._device.last_error

    def actions(self) -> Mapping[str, str]:
        labels = {
            "eject": "Eject",
            "close_plate": "Close Plate",
            "next_position": "Next Position",
        }
        return {command: labels[command] for command in self._commands if command in labels}

    def execute(self, action: str) -> bool:
        if not self.is_enabled():
            return False
        if action not in self._commands:
            return False
        named_command = getattr(self._device, action, None)
        if callable(named_command):
            if action == "next_position":
                return self._execute_next_position(named_command)
            return bool(named_command())
        return bool(self._device.execute_command(self._commands[action]))

    def _execute_next_position(self, command: Callable[[], object]) -> bool:
        """Send NEXT_POSITION and wait for a fresh moving-to-done status cycle."""
        initial = self._device.get_state()
        initial_healthy = bool(getattr(initial, "is_healthy", False))
        initial_done = bool(getattr(initial, "next_position_done", False))
        movement_observed = initial_healthy and not initial_done
        if not bool(command()):
            return False

        deadline = time.monotonic() + 10.0
        while True:
            state = self._device.get_state()
            healthy = bool(getattr(state, "is_healthy", False))
            moving = bool(getattr(state, "next_position_moving", False))
            done = bool(getattr(state, "next_position_done", False))
            if healthy and (moving or not done):
                movement_observed = True
            if healthy and movement_observed and done and not moving:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.1)

    def read_state(self) -> Mapping[str, object]:
        state = self._device.get_state()
        return {
            "healthy": bool(state.is_healthy),
            "ready": bool(state.is_ready),
            "eject": bool(state.ejecting),
            "eject_done": bool(state.eject_done),
            "next_pos_moving": bool(state.next_position_moving),
            "next_pos_done": bool(state.next_position_done),
            "raw": state.raw_status,
            "error": state.communication_errors[0] if state.communication_errors else "",
        }


def build_device_control_adapters(
    peripheral_config: PeripheralConfig,
    services: Mapping[str, object],
    persist_enabled: Callable[[str, bool], None] | None = None,
) -> list[object]:
    """Build shared-app adapters for configured, already-constructed devices."""
    labels = {
        "vacuum_pump": "Vacuum Pump",
        "fan": "Fan",
        "tray_fan": "Tray Fan",
        "laser": "Laser",
    }
    adapters: list[object] = []
    for key in ("vacuum_pump", "fan", "tray_fan", "laser"):
        binding = peripheral_config.peripherals.get(key)
        if binding is None or services.get(key) is None:
            continue
        device = services[key]
        enable_check = getattr(device, "read_state", None)
        adapters.append(BinaryDeviceAdapter(
            key, labels[key], device, enabled=binding.enabled,
            persist_enabled=persist_enabled,
            enable_check=enable_check if callable(enable_check) else None,
            commands=binding.commands,
        ))

    vacuum_binding = peripheral_config.peripherals.get("vacuum_sensor")
    if vacuum_binding is not None and services.get("vacuum_sensor") is not None:
        adapters.append(VacuumSensorDeviceAdapter(
            services["vacuum_sensor"], enabled=vacuum_binding.enabled,
            persist_enabled=persist_enabled,
        ))
    buttons_binding = peripheral_config.peripherals.get("physical_control_buttons")
    if buttons_binding is not None and services.get("physical_control_buttons") is not None:
        adapters.append(
            PhysicalButtonsDeviceAdapter(
                services["physical_control_buttons"],
                buttons_binding.outputs,
                enabled=buttons_binding.enabled,
                persist_enabled=persist_enabled,
                commands=buttons_binding.commands,
            )
        )
    if peripheral_config.peripherals.get("dryer") is not None and services.get("dryer") is not None:
        dryer_binding = peripheral_config.peripherals["dryer"]
        adapters.append(DryerDeviceAdapter(
            services["dryer"], persist_enabled, dryer_binding.commands,
        ))
    return adapters
