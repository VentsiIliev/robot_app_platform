from __future__ import annotations

import json
import logging
from pathlib import Path


_LOGGER = logging.getLogger(__name__)
_DEFAULT_ENABLED = True
_CONFIG_PATH = Path(__file__).resolve().parents[4] / "config" / "platform.json"


def _load_custom_virtual_keyboard_enabled() -> bool:
    try:
        payload = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _LOGGER.warning("Platform config not found; custom virtual keyboard remains enabled")
        return _DEFAULT_ENABLED
    except json.JSONDecodeError:
        _LOGGER.exception("Invalid platform config JSON; custom virtual keyboard remains enabled")
        return _DEFAULT_ENABLED

    if not isinstance(payload, dict):
        return _DEFAULT_ENABLED
    ui_config = payload.get("ui", {})
    if not isinstance(ui_config, dict):
        return _DEFAULT_ENABLED
    value = ui_config.get("custom_virtual_keyboard_enabled", _DEFAULT_ENABLED)
    if not isinstance(value, bool):
        _LOGGER.warning(
            "ui.custom_virtual_keyboard_enabled must be boolean; custom virtual keyboard remains enabled"
        )
        return _DEFAULT_ENABLED
    return value


ENABLE_CUSTOM_VIRTUAL_KEYBOARD = _load_custom_virtual_keyboard_enabled()
