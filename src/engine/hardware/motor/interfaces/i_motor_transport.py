from src.engine.hardware.communication.i_register_transport import IRegisterTransport


class IMotorTransport(IRegisterTransport):
    """
    Semantic type alias — constrains injection sites to motor-specific transports.
    All register I/O contract is inherited from IRegisterTransport.
    """
