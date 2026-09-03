from src.engine.hardware.communication.i_register_transport import IRegisterTransport


class IDryerTransport(IRegisterTransport):
    """
    Semantic type alias — constrains injection sites to dryer-specific transports.
    All register I/O contracts are inherited from IRegisterTransport.
    """
