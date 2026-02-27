from src.engine.hardware.communication.i_register_transport import IRegisterTransport


class IGeneratorTransport(IRegisterTransport):
    """
    Semantic type alias — constrains injection sites to generator-specific transports.
    All registered I/O contracts are inherited from IRegisterTransport.
    """