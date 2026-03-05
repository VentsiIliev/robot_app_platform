import logging
from typing import Callable, List, Optional, Tuple

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from src.applications.base.i_application_controller import IApplicationController
from src.applications.contour_matching_tester.model.contour_matching_tester_model import ContourMatchingTesterModel
from src.applications.contour_matching_tester.view.contour_matching_tester_view import ContourMatchingTesterView
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.vision_events import VisionTopics


class _Bridge(QObject):
    camera_frame = pyqtSignal(object)


class _Worker(QObject):
    finished = pyqtSignal(object, int)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        result, count = self._fn()
        self.finished.emit(result, count)


class ContourMatchingTesterController(IApplicationController):

    def __init__(
        self,
        model: ContourMatchingTesterModel,
        view: ContourMatchingTesterView,
        messaging: Optional[IMessagingService] = None,
    ):
        self._model   = model
        self._view    = view
        self._broker  = messaging
        self._bridge  = _Bridge()
        self._subs:   List[Tuple[str, Callable]] = []
        self._active  = False
        self._threads: List[Tuple[QThread, _Worker]] = []
        self._logger  = logging.getLogger(self.__class__.__name__)

        self._bridge.camera_frame.connect(self._on_camera_frame)
        self._view.load_workpieces_requested.connect(self._on_load_workpieces)
        self._view.match_requested.connect(self._on_match_requested)
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

    # ── Broker → Bridge (background thread) ──────────────────────────────

    def _subscribe(self) -> None:
        self._sub(VisionTopics.LATEST_IMAGE, self._on_latest_image_raw)

    def _on_latest_image_raw(self, msg) -> None:
        if isinstance(msg, dict):
            frame = msg.get("image")
            if frame is not None:
                self._bridge.camera_frame.emit(frame)

    # ── Bridge → View (main thread) ──────────────────────────────────────

    def _on_camera_frame(self, frame) -> None:
        if self._active:
            self._view.set_camera_frame(frame)

    # ── Load workpieces ───────────────────────────────────────────────────

    def _on_load_workpieces(self) -> None:
        workpieces = self._model.load_workpieces()
        self._view.set_workpieces(workpieces)

    # ── Match (async) ─────────────────────────────────────────────────────

    def _on_match_requested(self) -> None:
        self._threads = [(t, w) for t, w in self._threads if t.isRunning()]
        self._view.set_matching_busy(True)
        self._run_async(self._model.run_matching, self._on_match_done)

    def _on_match_done(self, result: dict, no_match_count: int) -> None:
        self._view.set_matching_busy(False)
        self._view.set_match_results(result, no_match_count)

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
