from __future__ import annotations

import logging

from src.engine.hardware.laser import ILaserControl

_LOGGER = logging.getLogger(__name__)


class MockLaserControl(ILaserControl):
    """Blueprint-safe laser control used until real hardware wiring exists."""

    def __init__(self) -> None:
        self._is_on = False

    def turn_on(self) -> None:
        self._is_on = True
        _LOGGER.info("Mock laser ON")

    def turn_off(self) -> None:
        self._is_on = False
        _LOGGER.info("Mock laser OFF")

    @property
    def is_on(self) -> bool:
        return self._is_on
