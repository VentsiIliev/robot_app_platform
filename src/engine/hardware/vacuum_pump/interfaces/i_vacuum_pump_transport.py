from src.engine.hardware.communication.i_register_transport import IRegisterTransport


class IVacuumPumpTransport(IRegisterTransport):
    """
    Semantic type alias — constrains injection sites to vacuum-pump-specific transports.
    All register I/O contract is inherited from IRegisterTransport.
    """

