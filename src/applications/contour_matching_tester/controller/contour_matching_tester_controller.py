import logging
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from src.applications.base.i_application_controller import IApplicationController
from src.applications.contour_matching_tester.model.contour_matching_tester_model import ContourMatchingTesterModel
from src.applications.contour_matching_tester.view.contour_matching_tester_view import ContourMatchingTesterView
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.vision_events import VisionTopics

_logger = logging.getLogger(__name__)

# ── colour palette ────────────────────────────────────────────────────────
# All tuples are BGR (OpenCV). Displayed after cv2.cvtColor(BGR→RGB), so
# tuple (B, G, R) displays as RGB(R, G, B).
_CLR_DETECTED  = (  0, 200, 255)   # display: yellow   (R=255, G=200, B=0)
_CLR_MATCHED   = (  0, 200,   0)   # display: green    (R=0,   G=200, B=0)
_CLR_ALIGNED   = (220, 220,   0)   # display: cyan     (R=0,   G=220, B=220)
_CLR_SPRAY_C   = (  0, 165, 255)   # display: orange   (R=255, G=165, B=0)
_CLR_SPRAY_F   = (255,   0, 180)   # display: violet   (R=180, G=0,   B=255)
_CLR_PICKUP    = (  0,   0, 255)   # display: red      (R=255, G=0,   B=0)
_CLR_UNMATCHED = (220,   0,   0)   # display: blue     (R=0,   G=0,   B=220)




class _Bridge(QObject):
    camera_frame = pyqtSignal(object)


class _Worker(QObject):
    finished = pyqtSignal(object)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        self.finished.emit(self._fn())


class ContourMatchingTesterController(IApplicationController):

    def __init__(
        self,
        model: ContourMatchingTesterModel,
        view: ContourMatchingTesterView,
        messaging: Optional[IMessagingService] = None,
    ):
        self._model           = model
        self._view            = view
        self._broker          = messaging
        self._bridge          = _Bridge()
        self._subs:           List[Tuple[str, Callable]] = []
        self._active          = False
        self._paused          = False
        self._latest_frame:   Optional[np.ndarray] = None
        self._captured_frame: Optional[np.ndarray] = None
        self._threads:        List[Tuple[QThread, _Worker]] = []
        self._logger          = logging.getLogger(self.__class__.__name__)

        self._bridge.camera_frame.connect(self._on_camera_frame)
        self._view.load_workpieces_requested.connect(self._on_load_workpieces)
        self._view.match_requested.connect(self._on_match_requested)
        self._view.capture_requested.connect(self._on_capture_clicked)
        self._view.workpiece_selected.connect(self._on_workpiece_selected)
        self._view.destroyed.connect(self.stop)

    def load(self) -> None:
        self._active = True
        if self._broker is not None:
            self._subscribe()

    def stop(self) -> None:
        self._active = False
        for topic, cb in reversed(self._subs):
            try:
                self._broker.unsubscribe(topic, cb)
            except Exception:
                pass
        self._subs.clear()
        for thread, _ in self._threads:
            thread.quit()
            thread.wait()
        self._threads.clear()

    # ── Broker → Bridge ───────────────────────────────────────────────────────

    def _subscribe(self) -> None:
        self._sub(VisionTopics.LATEST_IMAGE, self._on_latest_image_raw)

    def _on_latest_image_raw(self, msg) -> None:
        if isinstance(msg, dict):
            frame = msg.get("image")
            if frame is not None:
                self._bridge.camera_frame.emit(frame)

    # ── Bridge → View ─────────────────────────────────────────────────────────

    def _on_camera_frame(self, frame: np.ndarray) -> None:
        if not self._active:
            return
        self._latest_frame = frame
        if not self._paused:
            self._view.update_camera_view(frame)

    # ── Capture / Resume ──────────────────────────────────────────────────────

    def _on_capture_clicked(self) -> None:
        if self._paused:
            self._paused         = False
            self._captured_frame = None
            self._model.release_capture()
            self._view.set_capture_state(False)
            if self._latest_frame is not None:
                self._view.update_camera_view(self._latest_frame)
        else:
            if self._latest_frame is None:
                self._logger.warning("Capture requested but no frame available yet")
                return
            captured_contours    = self._model.capture()
            self._paused         = True
            self._captured_frame = self._latest_frame.copy()
            annotated = self._draw_capture_overlay(self._captured_frame, captured_contours)
            self._view.update_camera_view(annotated)
            self._view.set_capture_state(True)

    # ── Workpiece selection → thumbnail ──────────────────────────────────────

    def _on_workpiece_selected(self, row: int) -> None:
        workpieces = self._model.workpieces
        if row < 0 or row >= len(workpieces):
            return
        wp = workpieces[row]
        name = getattr(wp, "name", "")
        thumb = self._model.get_thumbnail(row)  # ← row index, not workpieceId
        self._view.show_thumbnail(name, thumb)

    # ── Load workpieces ───────────────────────────────────────────────────────

    def _on_load_workpieces(self) -> None:
        workpieces = self._model.load_workpieces()
        self._view.set_workpieces(workpieces)

    # ── Match (async) ─────────────────────────────────────────────────────────

    def _on_match_requested(self) -> None:
        self._threads = [(t, w) for t, w in self._threads if t.isRunning()]
        self._view.set_matching_busy(True)
        self._run_async(self._model.run_matching, self._on_match_done)

    def _on_match_done(self, payload) -> None:
        result, no_match_count, matched_contours, unmatched_contours = payload
        self._view.set_matching_busy(False)
        self._view.set_match_results(result, no_match_count)
        base = self._captured_frame if self._captured_frame is not None else self._latest_frame
        if base is not None:
            annotated = self._draw_match_overlay(base, result, matched_contours, unmatched_contours)
            self._view.update_camera_view(annotated)

    # ── Async runner ──────────────────────────────────────────────────────────

    def _run_async(self, fn, on_done) -> None:
        thread = QThread()
        worker = _Worker(fn)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(on_done)
        worker.finished.connect(thread.quit)
        self._threads.append((thread, worker))
        thread.start()

    def _sub(self, topic: str, cb: Callable) -> None:
        self._broker.subscribe(topic, cb)
        self._subs.append((topic, cb))

    # ── Overlay drawing ───────────────────────────────────────────────────────

    def _draw_capture_overlay(self, frame: np.ndarray, contours: list) -> np.ndarray:
        out = frame.copy()
        for i, c in enumerate(contours):
            pts = np.asarray(c, dtype=np.int32).reshape(-1, 1, 2)
            cv2.drawContours(out, [pts], -1, _CLR_DETECTED, 2)
            cx, cy = self._centroid(pts)
            self._label(out, f"#{i}", cx, cy, _CLR_DETECTED)
        return out

    def _draw_match_overlay(
            self,
            frame: np.ndarray,
            results: dict,
            matched_contours: list,
            unmatched_contours: list,
    ) -> np.ndarray:
        out = frame.copy()
        wps = results.get("workpieces", [])
        confs = results.get("mlConfidences", [])

        for i, (wp, c) in enumerate(zip(wps, matched_contours)):
            name = getattr(wp, "name", f"WP{i}")
            conf = confs[i] if i < len(confs) else 0.0

            # 1. Spray fills (violet) — bottom layer
            for sf in self._get_spray_fills(wp):
                cv2.drawContours(out, [sf], -1, _CLR_SPRAY_F, 1)

            # 2. Spray contours (orange)
            for sc in self._get_spray_contours(wp):
                cv2.drawContours(out, [sc], -1, _CLR_SPRAY_C, 1)

            # 3. Aligned workpiece template (cyan) — behind detected contour
            aligned = self._get_aligned_template(wp)
            if aligned is not None:
                cv2.drawContours(out, [aligned], -1, _CLR_ALIGNED, 2)

            # 4. Detected contour — ground truth on top (green)
            pts = np.asarray(c, dtype=np.int32).reshape(-1, 1, 2)
            cv2.drawContours(out, [pts], -1, _CLR_MATCHED, 2)
            cx, cy = self._centroid(pts)
            self._label(out, f"{name}  {conf:.0f}%", cx, cy, _CLR_MATCHED)

            # 5. Pickup point (red dot)
            pp = self._get_pickup_point(wp)
            if pp is not None:
                cv2.circle(out, pp, 5, _CLR_PICKUP, -1)
                cv2.circle(out, pp, 8, _CLR_PICKUP, 1)

        for c in unmatched_contours:
            pts = np.asarray(c, dtype=np.int32).reshape(-1, 1, 2)
            cv2.drawContours(out, [pts], -1, _CLR_UNMATCHED, 2)
            cx, cy = self._centroid(pts)
            self._label(out, "?", cx, cy, _CLR_UNMATCHED)

        return out

    @staticmethod
    def _get_aligned_template(wp) -> Optional[np.ndarray]:
        contour_data = getattr(wp, "contour", None)
        if contour_data is None:
            _logger.warning(f"[_get_aligned_template] No contour found")
            return None
        raw = contour_data["contour"] if isinstance(contour_data, dict) else contour_data
        if raw is None or len(raw) == 0:
            _logger.warning(f"[_get_aligned_template] No contour found")
            return None
        return np.asarray(raw, dtype=np.int32).reshape(-1, 1, 2)

    @staticmethod
    def _get_spray_contours(wp) -> list:
        spray = getattr(wp, "sprayPattern", None) or {}
        result = []
        for entry in spray.get("Contour", []):
            raw = entry.get("contour") if isinstance(entry, dict) else None
            if raw is not None and len(raw) > 0:
                result.append(np.asarray(raw, dtype=np.int32).reshape(-1, 1, 2))
        return result

    @staticmethod
    def _get_spray_fills(wp) -> list:
        spray = getattr(wp, "sprayPattern", None) or {}
        result = []
        for entry in spray.get("Fill", []):
            raw = entry.get("contour") if isinstance(entry, dict) else None
            if raw is not None and len(raw) > 0:
                result.append(np.asarray(raw, dtype=np.int32).reshape(-1, 1, 2))
        return result

    @staticmethod
    def _get_pickup_point(wp) -> Optional[Tuple[int, int]]:
        pp = getattr(wp, "pickupPoint", None)
        if pp is None:
            return None
        try:
            if isinstance(pp, str) and "," in pp:
                x, y = pp.split(",", 1)
                return int(float(x)), int(float(y))
            if hasattr(pp, "__len__") and len(pp) >= 2:
                return int(pp[0]), int(pp[1])
        except Exception:
            pass
        return None

    @staticmethod
    def _centroid(pts_n12: np.ndarray) -> Tuple[int, int]:
        M = cv2.moments(pts_n12)
        if M["m00"] > 0:
            return int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
        return int(pts_n12[0][0][0]), int(pts_n12[0][0][1])

    @staticmethod
    def _label(frame: np.ndarray, text: str, cx: int, cy: int, color: tuple) -> None:
        font  = cv2.FONT_HERSHEY_SIMPLEX
        scale, thick = 0.55, 2
        (tw, th), baseline = cv2.getTextSize(text, font, scale, thick)
        x, y = cx - tw // 2, cy - 6
        cv2.rectangle(frame, (x - 3, y - th - 3), (x + tw + 3, y + baseline + 1), (0, 0, 0), -1)
        cv2.putText(frame, text, (x, y), font, scale, color, thick, cv2.LINE_AA)
