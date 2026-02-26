from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer


@dataclass(frozen=True)
class CalibrationConfig:
    zero_offset: float
    scale_factor: float
    temperature_compensation: bool

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CalibrationConfig':
        return cls(
            zero_offset=data.get("zero_offset", 0.0),
            scale_factor=data.get("scale_factor", 1.0),
            temperature_compensation=data.get("temperature_compensation", False),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zero_offset": self.zero_offset,
            "scale_factor": self.scale_factor,
            "temperature_compensation": self.temperature_compensation,
        }


@dataclass(frozen=True)
class MeasurementConfig:
    sampling_rate: int
    filter_cutoff: float
    averaging_samples: int
    min_weight_threshold: float
    max_weight_threshold: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MeasurementConfig':
        return cls(
            sampling_rate=data.get("sampling_rate", 10),
            filter_cutoff=data.get("filter_cutoff", 1.0),
            averaging_samples=data.get("averaging_samples", 5),
            min_weight_threshold=data.get("min_weight_threshold", 0.0),
            max_weight_threshold=data.get("max_weight_threshold", 1000.0),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sampling_rate": self.sampling_rate,
            "filter_cutoff": self.filter_cutoff,
            "averaging_samples": self.averaging_samples,
            "min_weight_threshold": self.min_weight_threshold,
            "max_weight_threshold": self.max_weight_threshold,
        }


@dataclass(frozen=True)
class CellConfig:
    id: int
    type: str
    url: str
    capacity: float
    fetch_timeout_seconds: float
    data_fetch_interval_ms: int
    calibration: CalibrationConfig
    measurement: MeasurementConfig
    motor_address: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CellConfig':
        return cls(
            id=data["id"],
            type=data.get("type", ""),
            url=data.get("url", ""),
            capacity=data.get("capacity", 0.0),
            fetch_timeout_seconds=data.get("fetch_timeout_seconds", 5.0),
            data_fetch_interval_ms=data.get("data_fetch_interval_ms", 500),
            calibration=CalibrationConfig.from_dict(data.get("calibration", {})),
            measurement=MeasurementConfig.from_dict(data.get("measurement", {})),
            motor_address=data.get("motor_address", 0),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "url": self.url,
            "capacity": self.capacity,
            "fetch_timeout_seconds": self.fetch_timeout_seconds,
            "data_fetch_interval_ms": self.data_fetch_interval_ms,
            "calibration": self.calibration.to_dict(),
            "measurement": self.measurement.to_dict(),
            "motor_address": self.motor_address,
        }


@dataclass(frozen=True)
class CellsConfig:
    cells: List[CellConfig]

    def get_cell_by_id(self, cell_id: int) -> Optional[CellConfig]:
        return next((c for c in self.cells if c.id == cell_id), None)

    def get_all_cell_ids(self) -> List[int]:
        return [c.id for c in self.cells]

    def get_cells_by_type(self, cell_type: str) -> List[CellConfig]:
        return [c for c in self.cells if c.type == cell_type]

    @property
    def cell_count(self) -> int:
        return len(self.cells)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CellsConfig':
        return cls(cells=[CellConfig.from_dict(c) for c in data.get("cells", [])])

    def to_dict(self) -> Dict[str, Any]:
        return {"cells": [c.to_dict() for c in self.cells]}


class CellsConfigSerializer(ISettingsSerializer['CellsConfig']):

    @property
    def settings_type(self) -> str:
        return "cells_config"

    def get_default(self) -> 'CellsConfig':
        return CellsConfig(cells=[])

    def to_dict(self, settings: 'CellsConfig') -> Dict[str, Any]:
        return settings.to_dict()

    def from_dict(self, data: Dict[str, Any]) -> 'CellsConfig':
        return CellsConfig.from_dict(data)
