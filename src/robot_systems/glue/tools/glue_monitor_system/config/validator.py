"""
Strict configuration validator for glue monitor system.
NO DEFAULTS ALLOWED - all values must be explicitly provided.

This module provides validation logic while using shared models to avoid
circular dependencies between backend and UI layers.
"""
import json
from pathlib import Path
from typing import List, Dict, Any

from modules.shared.tools.glue_monitor_system.models import (
    CalibrationConfig,
    MeasurementConfig,
    CellConfig,
    ServerConfig,
    EndpointsConfig,
    GlobalSettings,
    GlueMonitorConfig
)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing required values."""
    pass


# Models are now imported from shared location - no need to redefine them


class ConfigValidator:
    """Strict configuration validator with NO defaults."""
    
    REQUIRED_ROOT_KEYS = {
        "environment", "server", "endpoints", "global_settings", "cells"
    }
    
    REQUIRED_SERVER_KEYS = {
        "host", "port", "protocol"
    }
    
    REQUIRED_ENDPOINTS_KEYS = {
        "weights", "tare", "get_config", "update_config"
    }
    
    REQUIRED_GLOBAL_SETTINGS_KEYS = {
        "fetch_timeout_seconds", "data_fetch_interval_ms", "ui_update_interval_ms"
    }
    
    REQUIRED_CELL_KEYS = {
        "id", "type", "url", "capacity", "fetch_timeout", "calibration", "measurement", "motor_address"
    }
    
    REQUIRED_CALIBRATION_KEYS = {
        "zero_offset", "scale_factor", "temperature_compensation"
    }
    
    REQUIRED_MEASUREMENT_KEYS = {
        "sampling_rate", "filter_cutoff", "averaging_samples", 
        "min_weight_threshold", "max_weight_threshold"
    }
    
    VALID_ENVIRONMENTS = {"test", "production", "development", "staging"}
    VALID_PROTOCOLS = {"http", "https"}
    
    @classmethod
    def validate_and_load(cls, config_path: Path) -> GlueMonitorConfig:
        """
        Load and validate configuration file.
        Raises ConfigurationError if any required value is missing.
        """
        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")
        
        try:
            with config_path.open("r") as f:
                raw_config = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in config file: {e}")
        
        return cls._validate_config(raw_config)
    
    @classmethod
    def _validate_config(cls, config: Dict[str, Any]) -> GlueMonitorConfig:
        """Validate complete configuration structure."""
        cls._ensure_keys_present(config, cls.REQUIRED_ROOT_KEYS, "root")
        
        # Validate environment
        environment = config["environment"]
        if environment not in cls.VALID_ENVIRONMENTS:
            raise ConfigurationError(
                f"Invalid environment '{environment}'. Must be one of: {cls.VALID_ENVIRONMENTS}"
            )
        
        # Validate server config
        server_config = cls._validate_server_config(config["server"])
        
        # Validate endpoints config
        endpoints_config = cls._validate_endpoints_config(config["endpoints"])
        
        # Validate global settings
        global_settings = cls._validate_global_settings(config["global_settings"])
        
        # Validate cells
        cells = cls._validate_cells(config["cells"])
        
        return GlueMonitorConfig(
            environment=environment,
            server=server_config,
            endpoints=endpoints_config,
            global_settings=global_settings,
            cells=cells
        )
    
    @classmethod
    def _validate_server_config(cls, server_data: Dict[str, Any]) -> ServerConfig:
        """Validate server configuration."""
        cls._ensure_keys_present(server_data, cls.REQUIRED_SERVER_KEYS, "server")
        
        protocol = server_data["protocol"]
        if protocol not in cls.VALID_PROTOCOLS:
            raise ConfigurationError(
                f"Invalid protocol '{protocol}'. Must be one of: {cls.VALID_PROTOCOLS}"
            )
        
        port = server_data["port"]
        if not isinstance(port, int) or port <= 0 or port > 65535:
            raise ConfigurationError(f"Invalid port '{port}'. Must be integer between 1-65535")
        
        return ServerConfig(
            host=str(server_data["host"]),
            port=port,
            protocol=protocol
        )
    
    @classmethod
    def _validate_endpoints_config(cls, endpoints_data: Dict[str, Any]) -> EndpointsConfig:
        """Validate endpoints configuration."""
        cls._ensure_keys_present(endpoints_data, cls.REQUIRED_ENDPOINTS_KEYS, "endpoints")
        
        return EndpointsConfig(
            weights=str(endpoints_data["weights"]),
            tare=str(endpoints_data["tare"]),
            get_config=str(endpoints_data["get_config"]),
            update_config=str(endpoints_data["update_config"])
        )
    
    @classmethod
    def _validate_global_settings(cls, settings_data: Dict[str, Any]) -> GlobalSettings:
        """Validate global settings."""
        cls._ensure_keys_present(settings_data, cls.REQUIRED_GLOBAL_SETTINGS_KEYS, "global_settings")
        
        for key in ["fetch_timeout_seconds", "data_fetch_interval_ms", "ui_update_interval_ms"]:
            value = settings_data[key]
            if not isinstance(value, int) or value <= 0:
                raise ConfigurationError(f"Invalid {key} '{value}'. Must be positive integer")
        
        return GlobalSettings(
            fetch_timeout_seconds=settings_data["fetch_timeout_seconds"],
            data_fetch_interval_ms=settings_data["data_fetch_interval_ms"],
            ui_update_interval_ms=settings_data["ui_update_interval_ms"]
        )
    
    @classmethod
    def _validate_cells(cls, cells_data: List[Dict[str, Any]]) -> List[CellConfig]:
        """Validate all cell configurations."""
        if not isinstance(cells_data, list) or len(cells_data) == 0:
            raise ConfigurationError("cells must be a non-empty list")
        
        cells = []
        used_ids = set()
        
        for i, cell_data in enumerate(cells_data):
            if not isinstance(cell_data, dict):
                raise ConfigurationError(f"Cell {i} must be an object")
            
            cell_config = cls._validate_cell(cell_data, i)
            
            # Ensure unique IDs
            if cell_config.id in used_ids:
                raise ConfigurationError(f"Duplicate cell ID {cell_config.id}")
            used_ids.add(cell_config.id)
            
            cells.append(cell_config)
        
        return cells
    
    @classmethod
    def _validate_cell(cls, cell_data: Dict[str, Any], index: int) -> CellConfig:
        """Validate individual cell configuration."""
        cls._ensure_keys_present(cell_data, cls.REQUIRED_CELL_KEYS, f"cell[{index}]")
        
        # Validate cell ID
        cell_id = cell_data["id"]
        if not isinstance(cell_id, int) or cell_id <= 0:
            raise ConfigurationError(f"Cell {index} ID '{cell_id}' must be positive integer")
        
        # Validate glue type
        type_str = cell_data["type"]

        # Map old enum names to full names for backward compatibility
        enum_mapping = {
            "TypeA": "Type A",
            "TypeB": "Type B",
            "TypeC": "Type C",
            "TypeD": "Type D",
        }

        if type_str in enum_mapping:
            glue_type = enum_mapping[type_str]
        elif isinstance(type_str, str):
            glue_type = type_str.strip()
        else:
            raise ConfigurationError(
                f"Cell {index} invalid type '{type_str}'. Must be a string."
            )

        # Note: Validation against registered types happens during runtime
        # to allow custom types. We just ensure it's a non-empty string here.
        if not glue_type:
            raise ConfigurationError(f"Cell {index} type cannot be empty")

        # Validate capacity and timeout
        capacity = cell_data["capacity"]
        if not isinstance(capacity, (int, float)) or capacity <= 0:
            raise ConfigurationError(f"Cell {index} capacity '{capacity}' must be positive number")
        
        fetch_timeout = cell_data["fetch_timeout"]
        if not isinstance(fetch_timeout, int) or fetch_timeout <= 0:
            raise ConfigurationError(f"Cell {index} fetch_timeout '{fetch_timeout}' must be positive integer")
        
        # Validate calibration
        calibration = cls._validate_calibration(cell_data["calibration"], cell_id)
        
        # Validate measurement
        measurement = cls._validate_measurement(cell_data["measurement"], cell_id)
        
        # Validate motor_address (REQUIRED field - no defaults)
        motor_address = cell_data["motor_address"]
        if not isinstance(motor_address, int) or motor_address < 0:
            raise ConfigurationError(
                f"Cell {cell_id} motor_address '{motor_address}' must be non-negative integer"
            )

        return CellConfig(
            id=cell_id,
            type=glue_type,
            url=str(cell_data["url"]),
            capacity=float(capacity),
            fetch_timeout=fetch_timeout,
            calibration=calibration,
            measurement=measurement,
            motor_address=motor_address
        )
    
    @classmethod
    def _validate_calibration(cls, cal_data: Dict[str, Any], cell_id: int) -> CalibrationConfig:
        """Validate calibration configuration."""
        cls._ensure_keys_present(cal_data, cls.REQUIRED_CALIBRATION_KEYS, f"cell[{cell_id}].calibration")
        
        scale_factor = cal_data["scale_factor"]
        if not isinstance(scale_factor, (int, float)) or scale_factor <= 0:
            raise ConfigurationError(
                f"Cell {cell_id} scale_factor '{scale_factor}' must be positive number"
            )
        
        return CalibrationConfig(
            zero_offset=float(cal_data["zero_offset"]),
            scale_factor=float(scale_factor),
            temperature_compensation=bool(cal_data["temperature_compensation"])
        )
    
    @classmethod
    def _validate_measurement(cls, meas_data: Dict[str, Any], cell_id: int) -> MeasurementConfig:
        """Validate measurement configuration."""
        cls._ensure_keys_present(meas_data, cls.REQUIRED_MEASUREMENT_KEYS, f"cell[{cell_id}].measurement")
        
        # Validate positive numeric values
        for key in ["sampling_rate", "averaging_samples"]:
            value = meas_data[key]
            if not isinstance(value, int) or value <= 0:
                raise ConfigurationError(
                    f"Cell {cell_id} {key} '{value}' must be positive integer"
                )
        
        for key in ["filter_cutoff", "min_weight_threshold", "max_weight_threshold"]:
            value = meas_data[key]
            if not isinstance(value, (int, float)) or value < 0:
                raise ConfigurationError(
                    f"Cell {cell_id} {key} '{value}' must be non-negative number"
                )
        
        # Validate threshold ordering
        min_thresh = meas_data["min_weight_threshold"]
        max_thresh = meas_data["max_weight_threshold"]
        if min_thresh >= max_thresh:
            raise ConfigurationError(
                f"Cell {cell_id} min_weight_threshold ({min_thresh}) must be less than max_weight_threshold ({max_thresh})"
            )
        
        return MeasurementConfig(
            sampling_rate=meas_data["sampling_rate"],
            filter_cutoff=float(meas_data["filter_cutoff"]),
            averaging_samples=meas_data["averaging_samples"],
            min_weight_threshold=float(meas_data["min_weight_threshold"]),
            max_weight_threshold=float(meas_data["max_weight_threshold"])
        )
    
    @classmethod
    def _ensure_keys_present(cls, data: Dict[str, Any], required_keys: set, context: str):
        """Ensure all required keys are present in data."""
        missing_keys = required_keys - set(data.keys())
        if missing_keys:
            raise ConfigurationError(
                f"Missing required keys in {context}: {sorted(missing_keys)}"
            )