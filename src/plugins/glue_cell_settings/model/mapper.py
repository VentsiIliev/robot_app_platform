from dataclasses import replace
from typing import Dict

from src.engine.hardware.weight.config import (
    CellConfig, CellsConfig, CalibrationConfig, MeasurementConfig,
)


class GlueCellMapper:

    @staticmethod
    def cell_to_flat(cell: CellConfig) -> Dict:
        return {
            "url":                   cell.url,
            "type":                  cell.type,
            "capacity":              cell.capacity,
            "fetch_timeout_seconds": cell.fetch_timeout_seconds,
            "data_fetch_interval_ms": cell.data_fetch_interval_ms,
            "motor_address":         cell.motor_address,
            "zero_offset":           cell.calibration.zero_offset,
            "scale_factor":          cell.calibration.scale_factor,
            "temperature_compensation": cell.calibration.temperature_compensation,
            "sampling_rate":         cell.measurement.sampling_rate,
            "filter_cutoff":         cell.measurement.filter_cutoff,
            "averaging_samples":     cell.measurement.averaging_samples,
            "min_weight_threshold":  cell.measurement.min_weight_threshold,
            "max_weight_threshold":  cell.measurement.max_weight_threshold,
        }

    @staticmethod
    def flat_to_cell(flat: Dict, original: CellConfig) -> CellConfig:
        calibration = replace(
            original.calibration,
            zero_offset             = float(flat.get("zero_offset",           original.calibration.zero_offset)),
            scale_factor            = float(flat.get("scale_factor",          original.calibration.scale_factor)),
            temperature_compensation= str(flat.get("temperature_compensation", original.calibration.temperature_compensation)) == "True",
        )
        measurement = replace(
            original.measurement,
            sampling_rate        = int(flat.get("sampling_rate",        original.measurement.sampling_rate)),
            filter_cutoff        = float(flat.get("filter_cutoff",      original.measurement.filter_cutoff)),
            averaging_samples    = int(flat.get("averaging_samples",    original.measurement.averaging_samples)),
            min_weight_threshold = float(flat.get("min_weight_threshold", original.measurement.min_weight_threshold)),
            max_weight_threshold = float(flat.get("max_weight_threshold", original.measurement.max_weight_threshold)),
        )
        return replace(
            original,
            url                    = str(flat.get("url",                    original.url)),
            type                   = str(flat.get("type",                   original.type)),
            capacity               = float(flat.get("capacity",             original.capacity)),
            fetch_timeout_seconds  = float(flat.get("fetch_timeout_seconds", original.fetch_timeout_seconds)),
            data_fetch_interval_ms = int(flat.get("data_fetch_interval_ms", original.data_fetch_interval_ms)),
            motor_address          = int(flat.get("motor_address",          original.motor_address)),
            calibration            = calibration,
            measurement            = measurement,
        )