import os
import threading
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget

from src.applications.base.jog_controller import JogController


class _JogView(QWidget):
    from PyQt6.QtCore import pyqtSignal

    jog_requested = pyqtSignal(str, str, str, float)
    jog_stopped = pyqtSignal(str)


class TestJogController(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_servo_stop_is_executed_after_queued_start(self):
        start_entered = threading.Event()
        allow_start_to_finish = threading.Event()
        stop_called = threading.Event()
        calls = []

        service = MagicMock()

        def jog(*_args):
            calls.append("start")
            start_entered.set()
            allow_start_to_finish.wait(timeout=1.0)

        def stop_jog():
            calls.append("stop")
            stop_called.set()

        service.jog.side_effect = jog
        service.stop_jog.side_effect = stop_jog
        view = _JogView()
        controller = JogController(view, service, MagicMock())

        view.jog_requested.emit("SERVO_JOG", "X", "Plus", 5.0)
        self.assertTrue(start_entered.wait(timeout=1.0))
        view.jog_stopped.emit("x_plus")
        self.assertFalse(stop_called.wait(timeout=0.05))

        allow_start_to_finish.set()
        self.assertTrue(stop_called.wait(timeout=1.0))
        self.assertEqual(["start", "stop"], calls)

        controller.stop()
        self.assertTrue(controller._jog_pool.waitForDone(1000))
        view.deleteLater()


if __name__ == "__main__":
    unittest.main()
