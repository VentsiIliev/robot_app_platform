import logging

from src.robot_systems.paint.processes.match import _rotate_xy

_logger = logging.getLogger(__name__)

def _camera_to_tcp_delta(
    x_offset: float,
    y_offset: float,
    current_rz: float,
    reference_rz: float = 0.0,
) -> tuple[float, float]:
    cur_x, cur_y = _rotate_xy(x_offset, y_offset, current_rz)
    ref_x, ref_y = _rotate_xy(x_offset, y_offset, reference_rz)
    return cur_x - ref_x, cur_y - ref_y


