from __future__ import annotations

import logging
from typing import Callable

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.communication.transport_registry import (
    DEFAULT_TRANSPORT_REGISTRY,
    TransportRegistry,
)
from src.engine.hardware.peripherals import PeripheralConfig
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.robot_systems.paint.component_ids import SettingsID
from src.robot_systems.paint.hardware.paint_head_device import PaintHeadDevice
from src.robot_systems.paint.processes.paint.incremental_adjustment import AdjustmentStep

from .i_paint_adjustment_service import IPaintAdjustmentService, PaintHeadCommandResult, PaintHeadDialConfig, PaintAdjustmentOptions


class PaintAdjustmentService(IPaintAdjustmentService):
    """Resolve the paint-head binding from live settings for each command."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        settings: ISettingsService,
        transport_registry: TransportRegistry = DEFAULT_TRANSPORT_REGISTRY,
        start_single_cycle: Callable[[], bool] | None = None,
        get_cycle_state: Callable[[], str] | None = None,
        start_adjustment: Callable[[], bool] | None = None,
        paint_next: Callable[[AdjustmentStep], bool] | None = None,
        finish_adjustment: Callable[[], bool] | None = None,
        get_adjustment_status: Callable[[], tuple[str, float, float]] | None = None,
    ) -> None:
        self._settings = settings
        self._transport_registry = transport_registry
        self._start_single_cycle = start_single_cycle
        self._get_cycle_state = get_cycle_state
        self._start_adjustment = start_adjustment
        self._paint_next = paint_next
        self._finish_adjustment = finish_adjustment
        self._get_adjustment_status = get_adjustment_status

    def get_camera_role(self) -> str:
        return "auxiliary"

    def get_preset_count(self) -> int:
        return self._resolve()[6]

    def is_paint_head_available(self) -> bool:
        try:
            self._resolve()
        except (KeyError, TypeError, ValueError):
            return False
        return True

    def get_dial_config(self) -> PaintHeadDialConfig:
        binding = self._resolve()
        return PaintHeadDialConfig(binding[3], binding[5], binding[6], binding[10])

    def read_current_position(self) -> int | None:
        if not self.get_dial_config().enabled:
            return None
        device, _more_sign, _enabled, _register = self._build_device()
        return device.read_position()

    def start_single_paint_cycle(self) -> bool:
        if self._start_single_cycle is None:
            return False
        return self._start_single_cycle()

    def get_paint_cycle_state(self) -> str:
        return self._get_cycle_state() if self._get_cycle_state is not None else "unavailable"

    def get_adjustment_options(self) -> PaintAdjustmentOptions:
        saved = self._settings.get(SettingsID.PAINT_ADJUSTMENT_SETTINGS)
        return PaintAdjustmentOptions(
            saved.length_mm,
            saved.paint_axis_offset_mm,
            saved.perpendicular_axis_offset_mm,
        )

    def _save_options(self, options: PaintAdjustmentOptions) -> AdjustmentStep:
        step = AdjustmentStep(
            options.length_mm,
            options.paint_axis_offset_mm,
            options.perpendicular_axis_offset_mm,
        )
        step.validate()
        self._settings.save(SettingsID.PAINT_ADJUSTMENT_SETTINGS, step)
        return step

    def start_adjustment_cycle(self, options: PaintAdjustmentOptions) -> bool:
        self._save_options(options)
        return bool(self._start_adjustment and self._start_adjustment())

    def paint_next_section(self, options: PaintAdjustmentOptions) -> bool:
        step = self._save_options(options)
        return bool(self._paint_next and self._paint_next(step))

    def finish_adjustment_cycle(self) -> bool:
        return bool(self._finish_adjustment and self._finish_adjustment())

    def get_adjustment_status(self) -> tuple[str, float, float]:
        return self._get_adjustment_status() if self._get_adjustment_status else ("idle", 0.0, 0.0)

    def adjust_paint(self, direction: str, degrees: int) -> PaintHeadCommandResult:
        if direction not in {"more", "less"}:
            raise ValueError("Paint adjustment direction must be 'more' or 'less'")
        if isinstance(degrees, bool) or not isinstance(degrees, int) or degrees < 1:
            raise ValueError("Paint adjustment degrees must be an integer >= 1")

        device, more_sign, enabled, register = self._build_device()
        signed_degrees = degrees * more_sign * (1 if direction == "more" else -1)
        if not enabled:
            delta = device.register_delta_for_degrees(signed_degrees)
            self._logger.info(
                "Paint head disabled: dry run register %d relative delta %+d (no read/write)",
                register, delta,
            )
            return PaintHeadCommandResult(delta, register, wrote=False, relative=True)
        value = device.move_degrees(signed_degrees)
        return PaintHeadCommandResult(value, register, wrote=True, relative=True)

    def adjust_paint_by_register_units(self, direction: str, units: int) -> PaintHeadCommandResult:
        if direction not in {"more", "less"}:
            raise ValueError("Paint adjustment direction must be 'more' or 'less'")
        if isinstance(units, bool) or not isinstance(units, int) or units < 1:
            raise ValueError("Paint adjustment register units must be an integer >= 1")
        device, more_sign, enabled, register = self._build_device()
        direction_sign = more_sign * (1 if direction == "more" else -1)
        signed_delta = units * direction_sign
        if not enabled:
            self._logger.info(
                "Paint head disabled: dry run register %d relative delta %+d (no read/write)",
                register, signed_delta,
            )
            return PaintHeadCommandResult(signed_delta, register, wrote=False, relative=True)
        value = device.move_register_delta(signed_delta)
        return PaintHeadCommandResult(value, register, wrote=True, relative=True)

    def go_to_setting(self, setting: int) -> PaintHeadCommandResult:
        if isinstance(setting, bool) or not isinstance(setting, int) or setting < 1:
            raise ValueError("Paint-head setting must be a positive integer")
        device, _more_sign, enabled, register = self._build_device()
        if not enabled:
            target = device.register_for_setting(setting)
            self._logger.info(
                "Paint head disabled: dry run register %d absolute value %d for setting %d (no write)",
                register, target, setting,
            )
            return PaintHeadCommandResult(target, register, wrote=False, relative=False)
        value = device.go_to_setting(setting)
        return PaintHeadCommandResult(value, register, wrote=True, relative=False)

    def go_to_position(self, position: int) -> PaintHeadCommandResult:
        device, _more_sign, enabled, register = self._build_device()
        if not enabled:
            target = device.validate_position(position)
            self._logger.info(
                "Paint head disabled: dry run register %d absolute value %d (no write)",
                register, target,
            )
            return PaintHeadCommandResult(target, register, wrote=False, relative=False)
        value = device.go_to_position(position)
        return PaintHeadCommandResult(value, register, wrote=True, relative=False)

    def _build_device(self) -> tuple[PaintHeadDevice, int, bool, int]:
        (
            modbus, slave_name, register, minimum, maximum, spacing,
            count, degree_numerator, degree_denominator, more_sign, enabled,
        ) = self._resolve()
        transport = self._transport_registry.build_for_slave(modbus, slave_name)
        device = PaintHeadDevice(
            transport,
            register,
            min_value=minimum,
            max_value=maximum,
            preset_spacing=spacing,
            preset_count=count,
            degree_units_numerator=degree_numerator,
            degree_units_denominator=degree_denominator,
        )
        return device, more_sign, enabled, register

    def _resolve(self) -> tuple[ModbusConfig, str, int, int, int, int, int, int, int, int, bool]:
        modbus = self._settings.get(CommonSettingsID.MODBUS_CONFIG)
        peripherals = self._settings.get(SettingsID.PERIPHERALS)
        if not isinstance(modbus, ModbusConfig) or not isinstance(peripherals, PeripheralConfig):
            raise ValueError("Paint-head Modbus configuration is unavailable")
        binding = peripherals.peripherals.get("paint_head")
        if binding is None:
            raise ValueError("Paint head is not configured")

        slave_name = modbus.find_slave_name(binding.slave_id)
        slave = modbus.get_slave(slave_name)
        if slave.transport_type != "modbus_register_fc16":
            raise ValueError("Paint head requires the FC16 register transport")

        register = int(binding.outputs["position"])
        minimum = int(binding.commands["min_value"])
        maximum = int(binding.commands["max_value"])
        spacing = int(binding.commands["preset_spacing"])
        count = int(binding.commands["preset_count"])
        degree_numerator = int(binding.commands["degree_units_numerator"])
        degree_denominator = int(binding.commands["degree_units_denominator"])
        more_sign = int(binding.commands["more_paint_sign"])
        if more_sign not in (-1, 1):
            raise ValueError("Paint-head more-paint direction must be -1 or 1")
        if not 0 <= register <= 65535:
            raise ValueError("Paint-head register address is invalid")
        if not 0 <= minimum <= maximum <= 65535:
            raise ValueError("Paint-head register range is invalid")
        if not 1 <= count <= 24 or spacing < 1 or minimum + spacing * (count - 1) != maximum:
            raise ValueError("Paint-head preset calibration is invalid")
        if degree_numerator < 1 or degree_denominator < 1:
            raise ValueError("Paint-head degree calibration is invalid")
        return (
            modbus, slave_name, register, minimum, maximum, spacing,
            count, degree_numerator, degree_denominator, more_sign, binding.enabled,
        )
