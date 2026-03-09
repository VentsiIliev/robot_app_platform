import logging

from src.engine.hardware.communication.i_register_transport import IRegisterTransport
from src.engine.hardware.laser.i_laser_control import ILaserControl

_logger = logging.getLogger(__name__)

_LASER_REGISTER = 14 # FIXME
_ON  = 1
_OFF = 0


class GlueLaserControl(ILaserControl):
    def __init__(self, transport: IRegisterTransport):
        self._transport = transport

    def turn_on(self) -> None:
        self._transport.write_register(_LASER_REGISTER, _ON)
        _logger.debug("Laser ON")

    def turn_off(self) -> None:
        self._transport.write_register(_LASER_REGISTER, _OFF)
        _logger.debug("Laser OFF")

