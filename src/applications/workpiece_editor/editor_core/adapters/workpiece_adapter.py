from __future__ import annotations

import logging

from src.robot_systems.paint.domain.paint_workpiece_editor_adapter import PaintWorkpieceEditorAdapter

_logger = logging.getLogger(__name__)


class WorkpieceAdapter(PaintWorkpieceEditorAdapter):
    """Legacy compatibility shim.

    New code should inject a system-specific ``IWorkpieceDataAdapter`` instead of
    importing a global adapter. This alias remains only for older DXF/editor
    entry points that still expect ``WorkpieceAdapter``.
    """

    def __init__(self):
        _logger.debug("WorkpieceAdapter compatibility shim created; prefer system-specific adapters")

    @classmethod
    def from_workpiece(cls, workpiece):
        return PaintWorkpieceEditorAdapter().from_workpiece(workpiece)

    @classmethod
    def to_workpiece_data(cls, editor_data, default_settings=None):
        return PaintWorkpieceEditorAdapter().to_workpiece_data(editor_data, default_settings=default_settings)

    @classmethod
    def from_raw(cls, raw: dict):
        return PaintWorkpieceEditorAdapter().from_raw(raw)

    @classmethod
    def print_summary(cls, editor_data):
        return PaintWorkpieceEditorAdapter().print_summary(editor_data)
