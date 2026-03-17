import sys
import unittest
import os
from unittest.mock import MagicMock

from src.engine.core.i_messaging_service import IMessagingService
from src.robot_systems.glue.applications.glue_process_driver.glue_process_driver_factory import (
    GlueProcessDriverFactory,
)
from src.robot_systems.glue.applications.glue_process_driver.controller.glue_process_driver_controller import (
    GlueProcessDriverController,
)
from src.robot_systems.glue.applications.glue_process_driver.model.glue_process_driver_model import (
    GlueProcessDriverModel,
)
from src.robot_systems.glue.applications.glue_process_driver.view.glue_process_driver_view import (
    GlueProcessDriverView,
)
from src.robot_systems.glue.applications.glue_process_driver.service.i_glue_process_driver_service import (
    IGlueProcessDriverService,
)


class TestGlueProcessDriverFactory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_build_returns_view(self):
        service = MagicMock(spec=IGlueProcessDriverService)
        service.get_process_snapshot.return_value = {"process_state": "idle", "dispensing": None}

        view = GlueProcessDriverFactory(MagicMock(spec=IMessagingService)).build(service)

        self.assertIsInstance(view, GlueProcessDriverView)

    def test_build_attaches_controller(self):
        service = MagicMock(spec=IGlueProcessDriverService)
        service.get_process_snapshot.return_value = {"process_state": "idle", "dispensing": None}

        view = GlueProcessDriverFactory(MagicMock(spec=IMessagingService)).build(service)

        self.assertIsInstance(view._controller, GlueProcessDriverController)

    def test_build_creates_model(self):
        service = MagicMock(spec=IGlueProcessDriverService)
        service.get_process_snapshot.return_value = {"process_state": "idle", "dispensing": None}

        view = GlueProcessDriverFactory(MagicMock(spec=IMessagingService)).build(service)

        self.assertIsInstance(view._controller._model, GlueProcessDriverModel)


if __name__ == "__main__":
    unittest.main()
