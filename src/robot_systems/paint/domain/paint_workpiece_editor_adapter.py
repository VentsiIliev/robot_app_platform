from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from contour_editor.persistence.data.editor_data_model import ContourEditorData

from src.applications.workpiece_editor.editor_core.adapters.adapter_utils import (
    contour_layer_name,
    ensure_complete_settings,
    fill_layer_name,
    normalize_layer_data,
    print_summary,
    segment_to_contour_array,
    segments_to_contour_array,
    unwrap_raw_contour_entry,
    workpiece_layer_name,
)
from src.applications.workpiece_editor.editor_core.adapters.i_workpiece_data_adapter import IWorkpieceDataAdapter

_logger = logging.getLogger(__name__)


class PaintWorkpieceEditorAdapter(IWorkpieceDataAdapter):
    """Paint-specific editor adapter.

    Paint owns the mapping between editor layers and persisted process geometry.
    The generic editor no longer needs to know that paint currently stores
    optional execution paths under ``sprayPattern``.
    """

    _PROCESS_KEY = "sprayPattern"
    _MAIN_SETTING_KEYS = (
        "velocity",
        "acceleration",
        "rz_angle",
        "preprocess_min_spacing_mm",
        "interpolation_spacing_mm",
        "dense_sampling_factor",
        "execution_spacing_mm",
        "path_tangent_lookahead_mm",
        "path_tangent_deadband_deg",
    )

    def from_workpiece(self, workpiece) -> ContourEditorData:
        main_contour = workpiece.get_main_contour()
        main_settings = workpiece.get_main_contour_settings()
        process_contours = workpiece.get_spray_pattern_contours()
        process_fills = workpiece.get_spray_pattern_fills()
        layer_data = {
            workpiece_layer_name(): [{"contour": main_contour, "settings": main_settings}],
            contour_layer_name(): process_contours,
            fill_layer_name(): process_fills,
        }
        return ContourEditorData.from_legacy_format(normalize_layer_data(layer_data))

    def to_workpiece_data(
        self,
        editor_data: ContourEditorData,
        default_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        workpiece_layer = (
            editor_data.get_layer(workpiece_layer_name())
            or editor_data.get_layer("Workpiece")
            or editor_data.get_layer("Main")
        )
        contour_layer = editor_data.get_layer(contour_layer_name()) or editor_data.get_layer("Contour")
        fill_layer = editor_data.get_layer(fill_layer_name()) or editor_data.get_layer("Fill")

        _logger.debug(
            "paint to_workpiece_data — Workpiece/Main segs=%d Contour segs=%d Fill segs=%d",
            len(workpiece_layer.segments) if workpiece_layer else 0,
            len(contour_layer.segments) if contour_layer else 0,
            len(fill_layer.segments) if fill_layer else 0,
        )

        if workpiece_layer and len(workpiece_layer.segments) > 0:
            result["contour"] = segments_to_contour_array(workpiece_layer.segments)
            result.update(
                ensure_complete_settings(
                    workpiece_layer.segments[0].settings
                    if hasattr(workpiece_layer.segments[0], "settings") else None
                )
            )
        else:
            result["contour"] = []

        process_pattern = {"Contour": [], "Fill": []}
        if contour_layer:
            for seg in contour_layer.segments:
                arr = segment_to_contour_array(seg)
                if arr is not None and len(arr) > 0:
                    process_pattern["Contour"].append({
                        "contour": arr,
                        "settings": ensure_complete_settings(
                            seg.settings if hasattr(seg, "settings") else None,
                            default_settings,
                        ),
                    })
        if fill_layer:
            for seg in fill_layer.segments:
                arr = segment_to_contour_array(seg)
                if arr is not None and len(arr) > 0:
                    process_pattern["Fill"].append({
                        "contour": arr,
                        "settings": ensure_complete_settings(
                            seg.settings if hasattr(seg, "settings") else None,
                            default_settings,
                        ),
                    })
        result[self._PROCESS_KEY] = process_pattern
        return result

    def from_raw(self, raw: dict) -> ContourEditorData:
        raw_contour = unwrap_raw_contour_entry(raw.get("contour", []))
        main_settings = {
            key: raw.get(key)
            for key in self._MAIN_SETTING_KEYS
            if raw.get(key) is not None
        }
        layer_data = {
            workpiece_layer_name(): [{"contour": raw_contour, "settings": main_settings}],
            contour_layer_name(): raw.get(self._PROCESS_KEY, {}).get("Contour", []),
            fill_layer_name(): raw.get(self._PROCESS_KEY, {}).get("Fill", []),
        }
        return ContourEditorData.from_legacy_format(normalize_layer_data(layer_data))

    def print_summary(self, editor_data: ContourEditorData) -> None:
        print_summary(editor_data)
