from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

from src.robot_systems.robot_system_bootstrap_provider import (
    RobotSystemBootstrapProvider,
)


_SYSTEM_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_PROVIDER_FACTORY_NAME = "create_bootstrap_provider"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "platform.json"


@dataclass(frozen=True)
class StartupConfig:
    robot_system: str
    supported_robot_systems: tuple[str, ...]


def load_startup_config(config_path: Path = DEFAULT_CONFIG_PATH) -> StartupConfig:
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Startup configuration not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid startup configuration JSON: {config_path}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Startup configuration must contain a JSON object")

    robot_system = _validate_system_name(payload.get("robot_system"), "robot_system")
    raw_supported = payload.get("supported_robot_systems")
    if not isinstance(raw_supported, list) or not raw_supported:
        raise RuntimeError(
            "'supported_robot_systems' must be a non-empty list"
        )

    supported_robot_systems = tuple(
        _validate_system_name(name, "supported_robot_systems")
        for name in raw_supported
    )
    if len(set(supported_robot_systems)) != len(supported_robot_systems):
        raise RuntimeError("'supported_robot_systems' must not contain duplicates")
    if robot_system not in supported_robot_systems:
        raise RuntimeError(
            f"Robot system '{robot_system}' is not listed in "
            "'supported_robot_systems'"
        )

    return StartupConfig(
        robot_system=robot_system,
        supported_robot_systems=supported_robot_systems,
    )


def _validate_system_name(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not _SYSTEM_NAME_PATTERN.fullmatch(value):
        raise RuntimeError(
            f"'{field_name}' entries must be lowercase identifiers containing only "
            "letters, numbers, and underscores"
        )
    return value


def load_bootstrap_provider(
    config: StartupConfig,
) -> RobotSystemBootstrapProvider:
    module_name = f"src.robot_systems.{config.robot_system}.bootstrap_provider"
    try:
        module = import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name or (
            exc.name is not None and module_name.startswith(f"{exc.name}.")
        ):
            raise RuntimeError(
                f"Robot system '{config.robot_system}' is not installed"
            ) from exc
        raise

    factory = getattr(module, _PROVIDER_FACTORY_NAME, None)
    if not callable(factory):
        raise RuntimeError(
            f"Robot system '{config.robot_system}' must expose "
            f"{_PROVIDER_FACTORY_NAME}()"
        )

    provider = factory()
    if not isinstance(provider, RobotSystemBootstrapProvider):
        raise RuntimeError(
            f"{module_name}.{_PROVIDER_FACTORY_NAME}() returned an invalid provider"
        )
    return provider
