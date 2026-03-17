from __future__ import annotations
import logging

from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

_logger = logging.getLogger(__name__)


def handle_advancing_path(context) -> GlueDispensingState:
    S = GlueDispensingState

    context.path_ops.advance_to_next_path()

    if not context.path_ops.has_remaining_paths():
        _logger.debug("All paths completed")
        return S.COMPLETED

    _logger.debug("Transitioning to path %s", context.current_path_index)
    return S.STARTING
