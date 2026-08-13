from src.engine.hardware.communication.i_register_transport import IRegisterTransport


class IVacuumSensorTransport(IRegisterTransport):
    """
    Semantic type alias — constrains injection sites to vacuum-sensor transports.
    All register I/O contract is inherited from IRegisterTransport.
    """
