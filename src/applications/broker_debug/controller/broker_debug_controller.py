import html
import logging
from typing import Callable, Dict

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from src.applications.base.i_application_controller import IApplicationController
from src.applications.broker_debug.model.broker_debug_model import BrokerDebugModel
from src.applications.broker_debug.view.broker_debug_view import BrokerDebugView
from src.engine.core.i_messaging_service import IMessagingService


class _Bridge(QObject):
    message_received = pyqtSignal(str, object)


class _SpyCallback:
    """Bound-method wrapper — keeps the callback alive and usable with WeakMethod."""

    def __init__(self, topic: str, bridge: _Bridge):
        self._topic  = topic
        self._bridge = bridge

    def __call__(self, msg) -> None:
        self._bridge.message_received.emit(self._topic, msg)


class BrokerDebugController(IApplicationController):

    def __init__(self, model: BrokerDebugModel, view: BrokerDebugView,
                 messaging: IMessagingService):
        self._model    = model
        self._view     = view
        self._messaging = messaging
        self._bridge   = _Bridge()
        self._active   = False
        self._spies:   Dict[str, _SpyCallback] = {}   # strong refs — keep alive
        self._logger   = logging.getLogger(self.__class__.__name__)

        self._timer = QTimer()
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._refresh)

    def load(self) -> None:
        self._active = True
        self._bridge.message_received.connect(self._on_message_received)
        self._connect_signals()
        self._refresh()
        self._timer.start()
        self._view.destroyed.connect(self.stop)

    def stop(self) -> None:
        self._active = False
        self._timer.stop()
        for topic, cb in list(self._spies.items()):
            try:
                self._model.unsubscribe_spy(topic, cb)
            except Exception:
                pass
        self._spies.clear()

    # ── Signals ───────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._view.refresh_requested.connect(self._refresh)
        self._view.publish_requested.connect(self._on_publish)
        self._view.spy_requested.connect(self._on_spy)
        self._view.unspy_requested.connect(self._on_unspy)
        self._view.clear_topic_requested.connect(self._on_clear_topic)

    # ── Handlers ──────────────────────────────────────────────────────

    def _refresh(self) -> None:
        if not self._active:
            return
        self._view.set_topic_map(self._model.refresh())

    def _on_publish(self, topic: str, message: str) -> None:
        self._model.publish(topic, message)
        self._view.append_log(
            f'<b style="color:#905BA9;">PUB</b> '
            f'<b>{topic}</b> → <code>{html.escape(message or "(empty)")}</code>'
        )
        self._refresh()

    def _on_spy(self, topic: str) -> None:
        if topic in self._spies:
            self._view.append_log(
                f'<span style="color:#888;">Already spying on <b>{topic}</b></span>'
            )
            return
        cb = _SpyCallback(topic, self._bridge)   # strong ref stored in self._spies
        self._spies[topic] = cb
        self._model.subscribe_spy(topic, cb)
        self._view.append_log(
            f'<b style="color:#2E7D32;">SPY ON</b> <b>{topic}</b>'
        )
        self._refresh()

    def _on_unspy(self, topic: str) -> None:
        if topic not in self._spies:
            self._view.append_log(
                f'<span style="color:#888;">No active spy on <b>{topic}</b></span>'
            )
            return
        cb = self._spies.pop(topic)
        self._model.unsubscribe_spy(topic, cb)
        self._view.append_log(
            f'<b style="color:#D32F2F;">SPY OFF</b> <b>{topic}</b>'
        )
        self._refresh()

    def _on_clear_topic(self, topic: str) -> None:
        self._model.clear_topic(topic)
        self._view.append_log(
            f'<b style="color:#D32F2F;">CLEARED</b> <b>{topic}</b>'
        )
        self._refresh()

    def _on_message_received(self, topic: str, message: object) -> None:
        if not self._active:
            return
        preview = str(message)
        if len(preview) > 120:
            preview = preview[:120] + "…"
        self._view.append_log(
            f'<b style="color:#1565C0;">MSG</b> '
            f'<b>{topic}</b> ← <code>{html.escape(preview)}</code>'
        )
