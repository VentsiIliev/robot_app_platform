from __future__ import annotations
import logging

from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

_logger = logging.getLogger(__name__)


def handle_loading_path(context) -> GlueDispensingState:
    S = GlueDispensingState

    if not context.path_ops.has_remaining_paths():
        return S.COMPLETED

    entry = context.path_ops.get_current_path_entry()

    if entry.is_empty():
        _logger.debug("Empty path at index %s, skipping", context.current_path_index)
        context.path_ops.skip_current_path()
        return S.LOADING_PATH

    return S.LOADING_CURRENT_PATH
