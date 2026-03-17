"""
BrokerSubscriptionMixin — manages broker topic subscriptions in controllers.

Eliminates the ``_subs: List[Tuple[str, Callable]]`` list + ``_sub()`` helper
+ manual unsubscribe loop that was duplicated across glue_cell_settings and
camera_settings controllers (and any future broker-subscribing controller).

Usage::

    class MyController(IApplicationController, BrokerSubscriptionMixin):

        def __init__(self, ..., messaging: IMessagingService):
            BrokerSubscriptionMixin.__init__(self)
            self._broker = messaging
            ...

        def load(self) -> None:
            self._subscribe(SomeTopic.EVENT, self._bridge.event_signal.emit)

        def stop(self) -> None:
            self._unsubscribe_all()

----

SignalBridge
------------
A base class for cross-thread signal relay objects.  Subclass it and declare
``pyqtSignal`` attributes for each piece of data that needs to travel from a
broker callback thread to the Qt main thread::

    class _Bridge(SignalBridge):
        frame_ready  = pyqtSignal(object)
        state_changed = pyqtSignal(str)

    # In controller.__init__:
    self._bridge = _Bridge()
    self._bridge.frame_ready.connect(self._view.set_frame)

    # In load() — broker callback fires on background thread, signal delivers
    # to main thread automatically:
    self._subscribe(VisionTopics.LATEST_IMAGE,
                    lambda msg: self._bridge.frame_ready.emit(msg))
"""
from __future__ import annotations

from typing import Callable, List, Tuple

from PyQt6.QtCore import QObject


class SignalBridge(QObject):
    """
    Base class for cross-thread signal relay objects.

    Subclass and add ``pyqtSignal`` fields — no other implementation needed.
    The name makes the intent obvious in controller code.
    """


class BrokerSubscriptionMixin:
    """
    Mixin that manages broker topic subscriptions for controller classes.

    Requires ``self._broker`` (an ``IMessagingService``) to be set before any
    ``_subscribe`` call — typically assigned in ``__init__``.
    """

    def __init__(self) -> None:
        self._subs: List[Tuple[str, Callable]] = []

    def _subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe *callback* to *topic* and track it for cleanup."""
        self._broker.subscribe(topic, callback)   # type: ignore[attr-defined]
        self._subs.append((topic, callback))

    def _unsubscribe_all(self) -> None:
        """Unsubscribe every tracked callback.  Call from ``stop()``."""
        for topic, cb in reversed(self._subs):
            try:
                self._broker.unsubscribe(topic, cb)  # type: ignore[attr-defined]
            except Exception:
                pass
        self._subs.clear()
