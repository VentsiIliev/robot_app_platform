from __future__ import annotations

import logging
from dataclasses import replace
from typing import Dict, List, Optional

from src.engine.hardware.motor.interfaces.i_motor_service import IMotorService
from src.engine.hardware.weight.config import (
    CalibrationConfig,
    CellConfig,
    CellsConfig,
    MeasurementConfig,
)
from src.engine.hardware.weight.interfaces.i_weight_cell_service import IWeightCellService
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.robot_systems.glue.applications.dispense_channel_settings.service.i_dispense_channel_settings_service import (
    IDispenseChannelSettingsService,
)
from src.robot_systems.glue.processes.glue_dispensing.glue_pump_controller import GluePumpController
from src.robot_systems.glue.settings.dispense_channels import (
    DispenseChannelConfig,
    DispenseChannelSettings,
)
from src.shared_contracts.declarations import DispenseChannelDefinition


class DispenseChannelSettingsService(IDispenseChannelSettingsService):
    def __init__(
        self,
        settings_service: ISettingsService,
        channel_settings_key,
        cells_settings_key,
        catalog_settings_key,
        glue_settings_key,
        channel_definitions: List[DispenseChannelDefinition],
        weight_service: Optional[IWeightCellService] = None,
        motor_service: Optional[IMotorService] = None,
    ) -> None:
        self._settings = settings_service
        self._channel_settings_key = channel_settings_key
        self._cells_settings_key = cells_settings_key
        self._catalog_settings_key = catalog_settings_key
        self._glue_settings_key = glue_settings_key
        self._weight = weight_service
        self._motor = motor_service
        self._definitions = {definition.id: definition for definition in channel_definitions}
        self._logger = logging.getLogger(self.__class__.__name__)

    def get_channel_definitions(self) -> List[DispenseChannelDefinition]:
        return list(self._definitions.values())

    def get_available_glue_types(self) -> List[str]:
        try:
            catalog = self._settings.get(self._catalog_settings_key)
            return list(catalog.get_all_names()) if hasattr(catalog, "get_all_names") else []
        except Exception:
            self._logger.exception("Failed to load glue-type catalog")
            return []

    def get_channel_flat(self, channel_id: str) -> Optional[dict]:
        definition = self._definitions.get(str(channel_id))
        if definition is None:
            return None
        cells = self._load_cells()
        cell = cells.get_cell_by_id(definition.weight_cell_id)
        if cell is None:
            return None
        channel_settings = self._load_channel_settings()
        channel_cfg = channel_settings.get_channel(definition.id)
        effective_glue_type = (
            channel_cfg.glue_type.strip()
            if channel_cfg is not None and channel_cfg.glue_type.strip()
            else str(cell.type).strip()
            or str(definition.default_glue_type).strip()
        )
        return {
            "glue_type": effective_glue_type,
            "url": cell.url,
            "capacity": cell.capacity,
            "fetch_timeout_seconds": cell.fetch_timeout_seconds,
            "data_fetch_interval_ms": cell.data_fetch_interval_ms,
            "zero_offset": cell.calibration.zero_offset,
            "scale_factor": cell.calibration.scale_factor,
            "sampling_rate": cell.measurement.sampling_rate,
            "filter_cutoff": cell.measurement.filter_cutoff,
            "averaging_samples": cell.measurement.averaging_samples,
            "min_weight_threshold": cell.measurement.min_weight_threshold,
            "max_weight_threshold": cell.measurement.max_weight_threshold,
        }

    def save_channel(self, channel_id: str, flat: dict) -> None:
        definition = self._require_definition(channel_id)
        cells = self._load_cells()
        channel_settings = self._load_channel_settings()
        original = cells.get_cell_by_id(definition.weight_cell_id)
        if original is None:
            raise ValueError(f"Weight cell {definition.weight_cell_id} not found for channel '{definition.id}'")

        updated_cell = replace(
            original,
            type=str(flat.get("glue_type", original.type)).strip(),
            url=str(flat.get("url", original.url)).strip(),
            capacity=float(flat.get("capacity", original.capacity)),
            fetch_timeout_seconds=float(flat.get("fetch_timeout_seconds", original.fetch_timeout_seconds)),
            data_fetch_interval_ms=int(flat.get("data_fetch_interval_ms", original.data_fetch_interval_ms)),
            motor_address=int(definition.pump_motor_address),
            calibration=CalibrationConfig(
                zero_offset=float(flat.get("zero_offset", original.calibration.zero_offset)),
                scale_factor=float(flat.get("scale_factor", original.calibration.scale_factor)),
            ),
            measurement=MeasurementConfig(
                sampling_rate=int(flat.get("sampling_rate", original.measurement.sampling_rate)),
                filter_cutoff=float(flat.get("filter_cutoff", original.measurement.filter_cutoff)),
                averaging_samples=int(flat.get("averaging_samples", original.measurement.averaging_samples)),
                min_weight_threshold=float(flat.get("min_weight_threshold", original.measurement.min_weight_threshold)),
                max_weight_threshold=float(flat.get("max_weight_threshold", original.measurement.max_weight_threshold)),
            ),
        )
        updated_cells = CellsConfig(
            cells=[updated_cell if cell.id == updated_cell.id else cell for cell in cells.cells]
        )
        self._settings.save(self._cells_settings_key, updated_cells)

        updated_channel = DispenseChannelConfig(
            channel_id=definition.id,
            glue_type=str(flat.get("glue_type", "")).strip(),
        )
        remaining = [channel for channel in channel_settings.channels if channel.channel_id != definition.id]
        self._settings.save(
            self._channel_settings_key,
            DispenseChannelSettings(channels=[*remaining, updated_channel]),
        )

        if self._weight is not None:
            self._weight.update_config(
                updated_cell.id,
                updated_cell.calibration.zero_offset,
                updated_cell.calibration.scale_factor,
            )

    def tare(self, channel_id: str) -> bool:
        if self._weight is None:
            return False
        definition = self._require_definition(channel_id)
        return bool(self._weight.tare(definition.weight_cell_id))

    def start_pump_test(self, channel_id: str) -> bool:
        if self._motor is None:
            return False
        definition = self._require_definition(channel_id)
        controller = self._build_test_controller()
        return bool(controller.pump_on(definition.pump_motor_address))

    def stop_pump_test(self, channel_id: str) -> bool:
        if self._motor is None:
            return False
        definition = self._require_definition(channel_id)
        controller = self._build_test_controller()
        return bool(controller.pump_off(definition.pump_motor_address))

    def _load_cells(self) -> CellsConfig:
        return self._settings.get(self._cells_settings_key)

    def _load_channel_settings(self) -> DispenseChannelSettings:
        return self._settings.get(self._channel_settings_key)

    def _require_definition(self, channel_id: str) -> DispenseChannelDefinition:
        definition = self._definitions.get(str(channel_id))
        if definition is None:
            raise ValueError(f"Unknown channel '{channel_id}'")
        return definition

    def _build_test_controller(self) -> GluePumpController:
        fallback_settings = self._settings.get(self._glue_settings_key)
        return GluePumpController(
            self._motor,
            use_segment_settings=False,
            fallback_settings=fallback_settings,
        )
