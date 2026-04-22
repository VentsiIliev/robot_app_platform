from __future__ import annotations

import copy
import logging
from typing import Callable, Optional

from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController

from src.engine.cad import import_dxf_to_workpiece_data
from src.robot_systems.paint.processes.workpiece_alignment import (
    align_raw_workpiece_to_contour,
    contour_to_workpiece_raw,
    pick_largest_contour,
)

_logger = logging.getLogger(__name__)


class PaintProductionService:
    def __init__(
        self,
        *,
        workpiece_editor_service,
        capture_snapshot_service,
        vacuum_pump: Optional[IVacuumPumpController] = None,
    ) -> None:
        # TODO EDITOR SHOULD NOT BE HERE THIS IS A VIOLATION OF LAYERING, NEED TO SPLIT OUT THE WORKPIECE PREPARATION TO A SEPARATE SERVICE
        self._editor = workpiece_editor_service
        self._capture_snapshot_service = capture_snapshot_service
        self._vacuum_pump = vacuum_pump

    def run_once(self, stop_requested: Optional[Callable[[], bool]] = None) -> tuple[bool, str]:
        should_stop = stop_requested or (lambda: False)

        snapshot = self._capture_snapshot_service.capture_snapshot(source="paint_process")
        if should_stop():
            return False, "Paint process stopped"

        contour = pick_largest_contour(snapshot.contours)
        if contour is None:
            return False, "No usable contour detected"

        raw_workpiece, description = self._prepare_workpiece(contour, snapshot.frame)
        if should_stop():
            return False, "Paint process stopped"

        ok, msg = self._editor.execute_workpiece({"form_data": raw_workpiece})
        if not ok:
            return False, f"Preview generation failed: {msg}"

        if should_stop():
            return False, "Paint process stopped"

        ok, msg = self._editor.execute_pickup_and_pivot_paint()
        if not ok:
            return False, f"{description}: {msg}"

        return True, f"{description}: {msg}"

    def _prepare_workpiece(self, captured_contour, frame) -> tuple[dict, str]:
        if self._editor.can_match_saved_workpieces():
            ok, payload, _ = self._editor.match_saved_workpieces(captured_contour)
            if ok and payload:
                raw = self._build_matched_workpiece_raw(payload, captured_contour, frame)
                if raw is not None:
                    label = payload.get("workpieceId") or payload.get("name") or "matched workpiece"
                    return raw, f"Executed {label}"

        return (
            contour_to_workpiece_raw(captured_contour, workpiece_id="captured", name="Captured contour"),
            "Executed captured contour",
        )

    def _build_matched_workpiece_raw(self, payload: dict, captured_contour, frame) -> dict | None:
        matched_raw = copy.deepcopy(payload.get("raw") or {})
        if not matched_raw:
            return None

        dxf_path = str(matched_raw.get("dxfPath", "") or "").strip()
        if dxf_path:
            image_h, image_w = self._resolve_frame_size(frame)
            dxf_raw = import_dxf_to_workpiece_data(dxf_path)
            placed = self._editor.prepare_dxf_test_raw_for_image(dxf_raw, image_w, image_h)
            aligned = align_raw_workpiece_to_contour(placed, captured_contour)
            for key, value in matched_raw.items():
                if key in {"contour", "sprayPattern"}:
                    continue
                aligned[key] = copy.deepcopy(value)
            aligned["dxfPath"] = dxf_path
            aligned.setdefault("sprayPattern", {"Contour": [], "Fill": []})
            return aligned

        if matched_raw.get("contour"):
            return align_raw_workpiece_to_contour(matched_raw, captured_contour)

        return None

    @staticmethod
    def _resolve_frame_size(frame) -> tuple[float, float]:
        if frame is None:
            return 720.0, 1280.0
        try:
            return float(frame.shape[0]), float(frame.shape[1])
        except Exception:
            _logger.debug("Failed to read frame shape for DXF placement", exc_info=True)
            return 720.0, 1280.0
