import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from PyQt6.QtCore import QCoreApplication, QEvent
from PyQt6.QtWidgets import QApplication, QWidget, QStackedWidget
from pl_gui.shell.startup_splash_view import StartupSplashView
from src.bootstrap.startup_splash_runtime import StartupSplashCoordinator


class StartupSplashLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.stack = QStackedWidget()
        self.folders = QWidget()
        self.stack.addWidget(self.folders)
        self.splash = StartupSplashView()
        self.stack.addWidget(self.splash)
        shell = SimpleNamespace(stacked_widget=self.stack, folders_page=self.folders)
        self.messaging = Mock()
        self.coordinator = StartupSplashCoordinator(shell, self.splash, self.messaging)
        self.ready = SimpleNamespace(state='idle', extra={'robot_ready': True})

    def tearDown(self):
        self.coordinator.stop()
        self.stack.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_second_login_reuses_live_splash_and_completes(self):
        for cycle in range(2):
            self.coordinator.start()
            self.assertIs(self.stack.currentWidget(), self.splash)
            self.coordinator._apply_robot_state(self.ready)
            self.coordinator._hide_splash()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self.assertIs(self.stack.currentWidget(), self.folders)
            self.assertGreaterEqual(self.stack.indexOf(self.splash), 0)
            self.splash.retranslateUi()
        self.assertEqual(self.messaging.subscribe.call_count, 2)
        self.assertEqual(self.messaging.unsubscribe.call_count, 2)

    def test_queued_state_after_stop_does_not_update_splash(self):
        self.coordinator.start()
        self.coordinator.stop()
        self.coordinator._apply_robot_state(self.ready)
        self.assertFalse(self.coordinator._finished)
        self.assertFalse(self.coordinator._hide_timer.isActive())

    def test_stop_cancels_pending_hide(self):
        self.coordinator.start()
        self.coordinator._apply_robot_state(self.ready)
        self.assertTrue(self.coordinator._hide_timer.isActive())
        self.coordinator.stop()
        self.assertFalse(self.coordinator._hide_timer.isActive())
