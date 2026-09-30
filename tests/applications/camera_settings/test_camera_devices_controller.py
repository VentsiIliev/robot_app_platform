import unittest
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication, QTabWidget, QWidget

from src.applications.camera_settings.controller.camera_devices_controller import (
    CameraDevicesController,
)
from src.applications.camera_settings.view.camera_devices_widget import CameraDevicesWidget
from src.applications.camera_settings.service.i_camera_settings_service import (
    CameraDeviceOption,
    CameraDevicesState,
    CameraOrientation,
)
from src.engine.core.message_broker import MessageBroker
from src.shared_contracts.events.vision_events import CameraTopics


class CameraDevicesControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_subscribes_only_while_camera_tab_is_visible(self) -> None:
        broker = MessageBroker()
        broker.clear_all()
        tabs = QTabWidget()
        other = QWidget()
        camera_view = CameraDevicesWidget()
        tabs.addTab(other, "Other")
        tabs.addTab(camera_view, "Cameras")
        model = MagicMock()
        controller = CameraDevicesController(model, camera_view, broker)
        controller._refresh = MagicMock()

        try:
            controller.load()
            tabs.show()
            self._app.processEvents()
            self.assertEqual(broker.get_subscriber_count(CameraTopics.frame("primary_vision")), 0)

            tabs.setCurrentWidget(camera_view)
            self._app.processEvents()
            self.assertEqual(broker.get_subscriber_count(CameraTopics.frame("primary_vision")), 1)

            controller._request_preview("auxiliary", "/dev/video2")
            self.assertEqual(broker.get_subscriber_count(CameraTopics.frame("primary_vision")), 0)
            self.assertEqual(broker.get_subscriber_count(CameraTopics.frame("auxiliary")), 1)

            tabs.setCurrentWidget(other)
            self._app.processEvents()
            self.assertEqual(broker.get_subscriber_count(CameraTopics.frame("auxiliary")), 0)
        finally:
            controller.stop()
            tabs.close()
            broker.clear_all()

    def test_orientation_controls_are_loaded_and_saved_for_each_role(self) -> None:
        view = CameraDevicesWidget()
        view.set_camera_devices(CameraDevicesState(
            assignments={"primary_vision": "/dev/video0", "auxiliary": "/dev/video2"},
            options=(
                CameraDeviceOption("/dev/video0", "/dev/video0", True),
                CameraDeviceOption("/dev/video2", "/dev/video2", True),
            ),
            orientation={
                "primary_vision": CameraOrientation(
                    flip_horizontal=True, rotate_degrees=90
                ),
                "auxiliary": CameraOrientation(
                    flip_vertical=True, rotate_degrees=270
                ),
            },
        ))
        saved = []

        def record_save(assignments, orientation):
            saved.append((assignments, orientation))

        view.save_requested.connect(record_save)

        view._on_save_clicked()

        self.assertEqual(saved[0][1], {
            "primary_vision": CameraOrientation(
                flip_horizontal=True, flip_vertical=False, rotate_degrees=90
            ),
            "auxiliary": CameraOrientation(
                flip_horizontal=False, flip_vertical=True, rotate_degrees=270
            ),
        })

    def test_recalibration_hint_is_shown_only_for_transposing_rotation(self) -> None:
        view = CameraDevicesWidget()
        # The panel is never shown here, so isVisible() would be False for every
        # child; isHidden() reflects the explicit show/hide state instead.
        hint = view._recalibration_hint

        def load(rotate_degrees):
            view.set_camera_devices(CameraDevicesState(
                assignments={"primary_vision": "/dev/video0", "auxiliary": "/dev/video2"},
                options=(
                    CameraDeviceOption("/dev/video0", "/dev/video0", True),
                    CameraDeviceOption("/dev/video2", "/dev/video2", True),
                ),
                orientation={
                    "primary_vision": CameraOrientation(rotate_degrees=rotate_degrees),
                    "auxiliary": CameraOrientation(),
                },
            ))

        load(0)
        self.assertTrue(hint.isHidden())
        load(180)
        self.assertTrue(hint.isHidden())
        load(90)
        self.assertFalse(hint.isHidden())
        load(0)
        self.assertTrue(hint.isHidden())

    def test_rotation_change_also_refreshes_the_recalibration_hint(self) -> None:
        view = CameraDevicesWidget()
        view.set_camera_devices(CameraDevicesState(
            assignments={"primary_vision": "/dev/video0", "auxiliary": "/dev/video2"},
            options=(
                CameraDeviceOption("/dev/video0", "/dev/video0", True),
                CameraDeviceOption("/dev/video2", "/dev/video2", True),
            ),
            orientation={
                "primary_vision": CameraOrientation(rotate_degrees=0),
                "auxiliary": CameraOrientation(),
            },
        ))
        rotation = view._orientation_controls["primary_vision"][2]
        self.assertTrue(view._recalibration_hint.isHidden())

        rotation.setCurrentIndex(rotation.findData(90))

        self.assertFalse(view._recalibration_hint.isHidden())


if __name__ == "__main__":
    unittest.main()
