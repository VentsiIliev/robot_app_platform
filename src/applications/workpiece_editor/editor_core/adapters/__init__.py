from .i_workpiece_data_adapter import IWorkpieceDataAdapter

__all__ = ['IWorkpieceDataAdapter', 'WorkpieceAdapter']


def __getattr__(name):
    # The legacy Paint adapter must not be imported by other systems merely
    # importing the shared adapter interface.
    if name == 'WorkpieceAdapter':
        from .workpiece_adapter import WorkpieceAdapter
        return WorkpieceAdapter
    raise AttributeError(name)
