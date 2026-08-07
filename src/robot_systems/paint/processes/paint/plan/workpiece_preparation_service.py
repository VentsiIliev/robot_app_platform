from __future__ import annotations

import copy
import logging
from typing import Callable, Optional

from src.robot_systems.paint.processes.paint.align import (
    _normalize_contour_points,
)
from src.robot_systems.paint.processes.paint.plan.contour_utils import (
    contour_to_workpiece_raw,
    describe_contour,
    extract_points_for_log,
)

_logger = logging.getLogger(__name__)

class PaintWorkpiecePreparationService:
    """Prepare the raw workpiece payload that paint production should execute."""
    def __init__(
        self,
        *,
        can_match_fn: Callable[[], bool],
        match_workpiece_fn: Callable,
        default_settings: Optional[dict] = None,
        transformer=None,
        transformer_getter: Optional[Callable[[], object]] = None,
    ) -> None:
        """Store matching hooks and the transformer needed for contour preparation."""
        self._can_match_fn = can_match_fn
        self._match_workpiece_fn = match_workpiece_fn
        self._default_settings = dict(default_settings or {})
        self._transformer = transformer
        self._transformer_getter = transformer_getter

    def _current_transformer(self):
        if self._transformer_getter is not None:
            return self._transformer_getter()
        return self._transformer

    def prepare_workpiece(self, captured_contour, frame) -> tuple[dict, str]:
        """Choose between a matched saved workpiece and a raw captured-contour fallback."""
        _logger.info(
            "[PREP] start captured=%s can_match=%s",
            describe_contour(_normalize_contour_points(captured_contour)),
            bool(self._can_match_fn()),
        )
        if self._can_match_fn():
            ok, payload, _ = self._match_workpiece_fn(captured_contour)
            if ok and payload:
                _logger.info(
                    "[PREP] matched workpiece id=%s name=%s",
                    str(payload.get("workpieceId") or ""),
                    str(payload.get("name") or ""),
                )
                raw = self._build_matched_workpiece_raw(payload, captured_contour, frame)
                if raw is not None:
                    label = payload.get("workpieceId") or payload.get("name") or "matched workpiece"
                    return raw, f"Executed {label}"
            else:
                return None, "No matched workpiece"

        _logger.info("[PREP] fallback to captured contour")
        return (
            contour_to_workpiece_raw(
                captured_contour,
                workpiece_id="captured",
                name="Captured contour",
                default_settings=self._default_settings,
            ),
            "Executed captured contour",
        )

    def _build_matched_workpiece_raw(self, payload: dict, captured_contour, frame) -> dict | None:
        """Build an executable raw workpiece from matched storage data and the live contour."""
        matched_raw = copy.deepcopy(payload.get("raw") or {})
        if not matched_raw:
            return None

        if matched_raw.get("contour"):
            _logger.info(
                "[PREP] branch=contour workpiece_id=%s source=%s captured=%s",
                str(matched_raw.get("workpieceId") or matched_raw.get("name") or ""),
                describe_contour(extract_points_for_log(matched_raw)),
                describe_contour(_normalize_contour_points(captured_contour)),
            )
            return matched_raw

        _logger.info(
            "[PREP] matched workpiece has no saved contour; falling back to captured contour"
        )
        return None

    @staticmethod
    def _resolve_frame_size(frame) -> tuple[float, float]:
        """Extract image height and width from a captured frame with safe defaults."""
        if frame is None:
            return 720.0, 1280.0
        try:
            return float(frame.shape[0]), float(frame.shape[1])
        except Exception:
            _logger.debug("Failed to read frame shape", exc_info=True)
            return 720.0, 1280.0
