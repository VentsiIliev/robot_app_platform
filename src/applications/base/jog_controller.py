import logging
from functools import partial

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from src.applications.base.robot_jog_service import RobotJogService
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.robot_events import RobotTopics

_logger = logging.getLogger(__name__)


class _Bridge(QObject):
    position_received = pyqtSignal(list)


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
        self._service   = jog_service
        self._messaging = messaging
        self._bridge    = _Bridge()
        self._subs      = []

        self._bridge.position_received.connect(view.set_jog_position)
        view.jog_requested.connect(self._on_jog)
        view.jog_stopped.connect(self._on_jog_stop)

    def start(self) -> None:
        cb = self._on_position
        self._messaging.subscribe(RobotTopics.POSITION, cb)
        self._subs.append((RobotTopics.POSITION, cb))

    def stop(self) -> None:
        for topic, cb in self._subs:
            self._messaging.unsubscribe(topic, cb)
        self._subs.clear()

    def _on_position(self, pos: list) -> None:
        self._bridge.position_received.emit(pos if pos else [])

    def _on_jog(self, _command: str, axis: str, direction: str, step: float) -> None:
        QThreadPool.globalInstance().start(
            _FireAndForget(partial(self._service.jog, axis, direction, step))
        )

    def _on_jog_stop(self, _key: str) -> None:
        _logger.debug(f"Commented out jod stop: {_key}")
        #START JOG IS ASYNC SO SHOULD NOT CALL STOP JOG IMMEDIATELY
        # QThreadPool.globalInstance().start(_FireAndForget(self._service.stop_jog))
