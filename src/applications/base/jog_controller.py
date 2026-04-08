import logging
import threading
from functools import partial

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal, pyqtSlot

from src.applications.base.robot_jog_service import RobotJogService
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.robot_events import RobotTopics

_logger = logging.getLogger(__name__)


class _Bridge(QObject):
    frame_options_received = pyqtSignal(object, str)

    def __init__(self, view, apply_frame_options):
        super().__init__()
        self._view = view
        self._apply_frame_options = apply_frame_options
        self._lock = threading.Lock()
        self._latest_position: list = []
        self._position_dirty = False
        self._position_timer = QTimer(self)
        self._position_timer.setInterval(100)
        self._position_timer.timeout.connect(self.flush_position)
        self._position_timer.start()
        self.frame_options_received.connect(self.handle_frame_options)
        self._destroy_slot_connected = True
        view.destroyed.connect(self.handle_view_destroyed)

    def ingest_position(self, pos: list) -> None:
        with self._lock:
            self._latest_position = list(pos or [])
            self._position_dirty = True

    @pyqtSlot()
    def flush_position(self) -> None:
        if self._view is None:
            return
        with self._lock:
            if not self._position_dirty:
                return
            position = list(self._latest_position)
            self._position_dirty = False
        self._view.set_jog_position(position)

    @pyqtSlot(object, str)
    def handle_frame_options(self, names_obj, default: str) -> None:
        if self._view is None:
            return
        self._apply_frame_options(names_obj, default)

    @pyqtSlot()
    def handle_view_destroyed(self) -> None:
        self.stop()

    def stop(self) -> None:
        self._position_timer.stop()
        try:
            self.frame_options_received.disconnect(self.handle_frame_options)
        except (RuntimeError, TypeError):
            pass
        if self._view is not None and self._destroy_slot_connected:
            try:
                self._view.destroyed.disconnect(self.handle_view_destroyed)
            except (RuntimeError, TypeError):
                pass
            self._destroy_slot_connected = False
        self._view = None


class _FireAndForget(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self._fn = fn
        self.setAutoDelete(True)

    def run(self):
        try:
            self._fn()
        except Exception:
            pass


class JogController:
    """Reusable controller fragment — wires a jog-capable view to robot jog + live position display.

    The host view must expose:
        - jog_requested  pyqtSignal(str, str, str, float)   # command, axis, direction, step
        - jog_stopped    pyqtSignal(str)                     # key
        - set_jog_position(pos: list) -> None

    Usage inside a host application controller::

        class MyController(IApplicationController):
            def __init__(self, model, view, messaging, jog_service):
                ...
                self._jog = JogController(view, jog_service, messaging)

            def load(self):
                ...
                self._jog.start()

            def stop(self):
                self._jog.stop()
                ...
    """

    def __init__(self, view, jog_service: RobotJogService, messaging: IMessagingService):
        self._view      = view
        self._service   = jog_service
        self._messaging = messaging
        self._bridge    = _Bridge(view, self._apply_frame_options)
        self._subs      = []
        view.jog_requested.connect(self._on_jog)
        view.jog_stopped.connect(self._on_jog_stop)

    def start(self) -> None:
        if bool(getattr(self._view, "JOG_LIVE_POSITION_ENABLED", True)):
            cb = self._on_position
            self._messaging.subscribe(RobotTopics.POSITION, cb)
            self._subs.append((RobotTopics.POSITION, cb))
        targeting_cb = self._on_targeting_definitions_changed
        self._messaging.subscribe(RobotTopics.TARGETING_DEFINITIONS_CHANGED, targeting_cb)
        self._subs.append((RobotTopics.TARGETING_DEFINITIONS_CHANGED, targeting_cb))
        self._refresh_frame_options()

    def stop(self) -> None:
        for topic, cb in self._subs:
            self._messaging.unsubscribe(topic, cb)
        self._subs.clear()
        try:
            self._view.jog_requested.disconnect(self._on_jog)
        except (RuntimeError, TypeError):
            pass
        try:
            self._view.jog_stopped.disconnect(self._on_jog_stop)
        except (RuntimeError, TypeError):
            pass
        self._bridge.stop()
        self._bridge.deleteLater()

    def _on_position(self, pos: list) -> None:
        self._bridge.ingest_position(pos if pos else [])

    def _on_targeting_definitions_changed(self, _payload=None) -> None:
        self._refresh_frame_options()

    def _refresh_frame_options(self) -> None:
        get_frames = getattr(self._service, "get_available_frames", None)
        get_default = getattr(self._service, "get_default_frame", None)
        if not callable(get_frames):
            return
        names = list(get_frames())
        default = str(get_default() or "").strip() if callable(get_default) else ""
        self._bridge.frame_options_received.emit(names, default)

    def _apply_frame_options(self, names_obj, default: str) -> None:
        set_options = getattr(self._view, "set_jog_frame_options", None)
        if not callable(set_options):
            return
        names = list(names_obj or [])
        current = getattr(self._view, "get_jog_frame", lambda: "")()
        selected = current if current in names else default
        set_options(names, default=selected or default)
        if selected:
            set_frame = getattr(self._service, "set_frame", None)
            if callable(set_frame):
                set_frame(selected)

    def _on_jog(self, _command: str, axis: str, direction: str, step: float) -> None:
        frame_getter = getattr(self._view, "get_jog_frame", None)
        if callable(frame_getter) and hasattr(self._service, "set_frame"):
            self._service.set_frame(frame_getter())
        QThreadPool.globalInstance().start(
            _FireAndForget(partial(self._service.jog, axis, direction, step))
        )

    def _on_jog_stop(self, _key: str) -> None:
        _logger.debug(f"Commented out jog stop: {_key}")
        #START JOG IS ASYNC SO SHOULD NOT CALL STOP JOG IMMEDIATELY
        # QThreadPool.globalInstance().start(_FireAndForget(self._service.stop_jog))
