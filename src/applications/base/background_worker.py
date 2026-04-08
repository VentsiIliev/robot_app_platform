"""
BackgroundWorker — mixin that provides a thread-safe _run_in_thread() helper.

Eliminates the private ``_Worker`` class + ``_active`` list + ``_run_in_thread``
boilerplate that was duplicated across modbus_settings, robot_settings,
height_measuring, and device_control controllers.

Usage::

    class MyController(IApplicationController, BackgroundWorker):

        def __init__(self, ...):
            BackgroundWorker.__init__(self)
            ...

        def _do_something(self) -> None:
            self._run_in_thread(
                fn       = self._model.slow_operation,
                on_done  = self._on_done,       # called on GUI thread
                on_error = self._on_error,       # optional
            )

        def stop(self) -> None:
            self._stop_threads()
            ...

Notes
-----
- ``BackgroundWorker`` is NOT a ``QObject`` subclass — it does not interfere
  with Qt's meta-object system.  Always put Qt base classes first in the MRO.
- A strong reference to every ``(QThread, _Worker)`` pair is kept in
  ``self._active`` so Python's GC cannot destroy the worker while its thread
  is still running.
- ``_on_thread_finished`` is connected to ``thread.finished``; it prunes
  completed pairs automatically, so ``_active`` stays lean.
"""
from __future__ import annotations

import logging
from typing import Callable, List, Optional, Tuple

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot


class _Worker(QObject):
    """Runs *fn* off the GUI thread; emits ``finished`` or ``failed``."""

    finished = pyqtSignal(object)
    failed   = pyqtSignal(str)

    def __init__(self, fn: Callable) -> None:
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            self.finished.emit(self._fn())
        except Exception as exc:
            self.failed.emit(str(exc))


class _UiRelay(QObject):
    """Ensures result/error callbacks run on the GUI thread."""

    def __init__(self, on_done: Callable, on_error: Optional[Callable] = None) -> None:
        super().__init__()
        self._on_done = on_done
        self._on_error = on_error

    @pyqtSlot(object)
    def handle_finished(self, result) -> None:
        self._on_done(result)

    @pyqtSlot(str)
    def handle_failed(self, message: str) -> None:
        if self._on_error is not None:
            self._on_error(message)


class BackgroundWorker:
    """
    Mixin that provides ``_run_in_thread()`` for controller classes.

    Mix in after ``IApplicationController`` (or any QObject base)::

        class MyController(IApplicationController, BackgroundWorker):
            ...
    """

    def __init__(self) -> None:
        self._active: List[Tuple[QThread, _Worker, _UiRelay]] = []
        self._logger = logging.getLogger(self.__class__.__name__)

    def _run_in_thread(
        self,
        fn: Callable,
        on_done: Callable,
        on_error: Optional[Callable] = None,
    ) -> None:
        """
        Run *fn* on a new ``QThread`` and deliver the result to the main thread.

        Parameters
        ----------
        fn:
            Blocking callable executed on the worker thread.  Its return value
            is passed to *on_done*.
        on_done:
            Slot or callable invoked on the GUI thread with ``fn()``'s return
            value.  May also be a ``pyqtBoundSignal`` — signal chaining works.
        on_error:
            Optional slot/callable invoked on the GUI thread with the
            exception message string if *fn* raises.
        """
        thread = QThread()
        worker = _Worker(fn)
        relay = _UiRelay(on_done=on_done, on_error=on_error)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(relay.handle_finished)
        worker.finished.connect(thread.quit)
        if on_error is not None:
            worker.failed.connect(relay.handle_failed)
            worker.failed.connect(thread.quit)
        thread.finished.connect(self._on_thread_finished)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(relay.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._active.append((thread, worker, relay))
        thread.start()

    def _stop_threads(self, timeout_ms: int = 3000) -> None:
        """Quit and wait for every running thread.  Call from ``stop()``."""
        still_running: List[Tuple[QThread, _Worker, _UiRelay]] = []
        for thread, worker, relay in self._active:
            if not thread.isRunning():
                continue
            thread.quit()
            if thread.wait(timeout_ms):
                continue

            self._logger.warning(
                "Background worker thread did not stop within %d ms; waiting for completion to avoid QThread shutdown crash",
                timeout_ms,
            )
            thread.wait()
            still_running.append((thread, worker, relay))
        self._active = [(t, w, r) for t, w, r in still_running if t.isRunning()]

    def _on_thread_finished(self) -> None:
        self._active = [(t, w, r) for t, w, r in self._active if t.isRunning()]
