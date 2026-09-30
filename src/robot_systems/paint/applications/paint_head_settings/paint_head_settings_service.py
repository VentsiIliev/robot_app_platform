from __future__ import annotations

from dataclasses import replace

from src.engine.hardware.peripherals import PeripheralConfig
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.robot_systems.paint.component_ids import SettingsID

from .i_paint_head_settings_service import IPaintHeadSettingsService, PaintHeadSettings


class PaintHeadSettingsService(IPaintHeadSettingsService):
    """Persist paint-head calibration in the shared settings cache and JSON file."""

    MAX_PRESET_COUNT = 24

    def __init__(self, settings: ISettingsService) -> None:
        self._settings = settings

    def load(self) -> PaintHeadSettings:
        binding = self._binding()
        commands = binding.commands
        result = PaintHeadSettings(
            more_paint_sign=int(commands["more_paint_sign"]),
            preset_spacing=int(commands["preset_spacing"]),
            preset_count=int(commands["preset_count"]),
            min_value=int(commands["min_value"]),
        )
        self._validate(result)
        return result

    def save(self, sign: int, spacing: int, count: int) -> PaintHeadSettings:
        config = self._settings.get(SettingsID.PERIPHERALS)
        if not isinstance(config, PeripheralConfig):
            raise ValueError("Peripheral settings are unavailable")
        binding = self._binding()
        result = PaintHeadSettings(sign, spacing, count, int(binding.commands["min_value"]))
        self._validate(result)

        commands = {
            **binding.commands,
            "more_paint_sign": sign,
            "preset_spacing": spacing,
            "preset_count": count,
            "max_value": result.max_value,
        }
        updated = replace(binding, commands=commands)
        self._settings.save(
            SettingsID.PERIPHERALS,
            PeripheralConfig({**config.peripherals, "paint_head": updated}),
        )
        return result

    def _binding(self):
        config = self._settings.get(SettingsID.PERIPHERALS)
        if not isinstance(config, PeripheralConfig):
            raise ValueError("Peripheral settings are unavailable")
        binding = config.peripherals.get("paint_head")
        if binding is None:
            raise ValueError("Paint head is not configured")
        return binding

    @classmethod
    def _validate(cls, settings: PaintHeadSettings) -> None:
        if isinstance(settings.more_paint_sign, bool) or not isinstance(settings.more_paint_sign, int) or settings.more_paint_sign not in (-1, 1):
            raise ValueError("More-paint direction must be -1 or +1")
        if isinstance(settings.preset_spacing, bool) or not isinstance(settings.preset_spacing, int) or settings.preset_spacing < 1:
            raise ValueError("Preset spacing must be an integer >= 1")
        if isinstance(settings.preset_count, bool) or not isinstance(settings.preset_count, int) or not 1 <= settings.preset_count <= cls.MAX_PRESET_COUNT:
            raise ValueError(f"Preset count must be 1..{cls.MAX_PRESET_COUNT}")
        if not 0 <= settings.min_value <= settings.max_value <= 65535:
            raise ValueError("Configured preset values must fit in a Modbus register")
