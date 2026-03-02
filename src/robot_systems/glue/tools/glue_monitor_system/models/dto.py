"""
Data Transfer Objects for API communication between backend and UI.

These DTOs provide clean serialization/deserialization for glue monitor system data,
enabling type-safe communication without circular dependencies.
"""
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from .cells import CellConfig, CalibrationConfig, MeasurementConfig


@dataclass
class CalibrationConfigDTO:
    """DTO for calibration configuration."""
    zero_offset: float
    scale_factor: float
    temperature_compensation: bool
    
    @classmethod
    def from_calibration_config(cls, config: CalibrationConfig) -> 'CalibrationConfigDTO':
        """Convert CalibrationConfig to DTO."""
        return cls(
            zero_offset=config.zero_offset,
            scale_factor=config.scale_factor,
            temperature_compensation=config.temperature_compensation
        )
    
    def to_calibration_config(self) -> CalibrationConfig:
        """Convert DTO to CalibrationConfig."""
        return CalibrationConfig(
            zero_offset=self.zero_offset,
            scale_factor=self.scale_factor,
            temperature_compensation=self.temperature_compensation
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class MeasurementConfigDTO:
    """DTO for measurement configuration."""
    sampling_rate: int
    filter_cutoff: float
    averaging_samples: int
    min_weight_threshold: float
    max_weight_threshold: float
    
    @classmethod
    def from_measurement_config(cls, config: MeasurementConfig) -> 'MeasurementConfigDTO':
        """Convert MeasurementConfig to DTO."""
        return cls(
            sampling_rate=config.sampling_rate,
            filter_cutoff=config.filter_cutoff,
            averaging_samples=config.averaging_samples,
            min_weight_threshold=config.min_weight_threshold,
            max_weight_threshold=config.max_weight_threshold
        )
    
    def to_measurement_config(self) -> MeasurementConfig:
        """Convert DTO to MeasurementConfig."""
        return MeasurementConfig(
            sampling_rate=self.sampling_rate,
            filter_cutoff=self.filter_cutoff,
            averaging_samples=self.averaging_samples,
            min_weight_threshold=self.min_weight_threshold,
            max_weight_threshold=self.max_weight_threshold
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class CellConfigDTO:
    """DTO for cell configuration API responses."""
    id: int
    type: str  # String instead of enum for JSON serialization
    url: str
    capacity: float
    fetch_timeout: int
    calibration: CalibrationConfigDTO
    measurement: MeasurementConfigDTO
    motor_address: int = 0  # Motor address for this cell's pump

    @classmethod
    def from_cell_config(cls, cell_config: CellConfig) -> 'CellConfigDTO':
        """Convert CellConfig to DTO."""
        return cls(
            id=cell_config.id,
            type=cell_config.type,
            url=cell_config.url,
            capacity=cell_config.capacity,
            fetch_timeout=cell_config.fetch_timeout,
            calibration=CalibrationConfigDTO.from_calibration_config(cell_config.calibration),
            measurement=MeasurementConfigDTO.from_measurement_config(cell_config.measurement),
            motor_address=getattr(cell_config, 'motor_address', 0)  # Get motor address from config
        )
    
    def to_cell_config(self) -> CellConfig:
        """Convert DTO to CellConfig."""
        return CellConfig(
            id=self.id,
            type=self.type,
            url=self.url,
            capacity=self.capacity,
            fetch_timeout=self.fetch_timeout,
            calibration=self.calibration.to_calibration_config(),
            measurement=self.measurement.to_measurement_config(),
            motor_address=self.motor_address  # Include motor address when creating CellConfig
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type,
            "url": self.url,
            "capacity": self.capacity,
            "fetch_timeout": self.fetch_timeout,
            "calibration": self.calibration.to_dict(),
            "measurement": self.measurement.to_dict(),
            "motor_address": self.motor_address  # Include motor address in serialization
        }


@dataclass
class GlueCellsResponseDTO:
    """DTO for glue cells API responses."""
    environment: str
    server_url: str
    cells: List[CellConfigDTO]
    
    @classmethod
    def from_cell_configs(cls, environment: str, server_url: str, cell_configs: List[CellConfig]) -> 'GlueCellsResponseDTO':
        """Create response DTO from cell configurations."""
        cell_dtos = [CellConfigDTO.from_cell_config(cell) for cell in cell_configs]
        return cls(
            environment=environment,
            server_url=server_url,
            cells=cell_dtos
        )
    
    def get_cell_by_id(self, cell_id: int) -> Optional[CellConfigDTO]:
        """Get a cell DTO by its ID."""
        return next((cell for cell in self.cells if cell.id == cell_id), None)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "environment": self.environment,
            "server_url": self.server_url,
            "cells": [cell.to_dict() for cell in self.cells]
        }


@dataclass  
class CellUpdateRequestDTO:
    """DTO for cell update requests."""
    cell_id: int
    field: str  # 'type', 'calibration', 'measurement', etc.
    value: Any
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class CellOperationResponseDTO:
    """DTO for cell operation responses (tare, calibrate, etc.)."""
    cell_id: int
    operation: str
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)