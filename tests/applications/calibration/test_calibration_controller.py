import sys
import unittest
from unittest.mock import MagicMock

from src.applications.calibration.controller.calibration_controller import CalibrationController
from src.applications.calibration.model.calibration_model import CalibrationModel
from src.shared_contracts.events.vision_events import VisionTopics


def _make_model(**overrides):
    m = MagicMock(spec=CalibrationModel)
    m.capture_calibration_image.return_value = overrides.get("capture",  (True,  "captured"))
    m.calibrate_camera.return_value           = overrides.get("camera",   (True,  "cam ok"))
    m.calibrate_robot.return_value            = overrides.get("robot",    (False, "not impl"))
    m.calibrate_camera_and_robot.return_value = overrides.get("sequence", (True,  "all ok"))
    return m


def _make_view():
    v = MagicMock()
    v.destroyed = MagicMock()
    v.destroyed.connect = MagicMock()
    v.capture_requested = MagicMock()
    v.capture_requested.connect = MagicMock()
    v.calibrate_camera_requested = MagicMock()
    v.calibrate_camera_requested.connect = MagicMock()
    v.calibrate_robot_requested = MagicMock()
    v.calibrate_robot_requested.connect = MagicMock()
    v.calibrate_sequence_requested = MagicMock()
    v.calibrate_sequence_requested.connect = MagicMock()
    return v


def _make_broker():
    b = MagicMock()
    b.subscribe = MagicMock()
    b.unsubscribe = MagicMock()
    return b


def _make_ctrl(**model_overrides):
    model       = _make_model(**model_overrides)
    view        = _make_view()
    broker      = _make_broker()
    ctrl        = CalibrationController(model, view, broker)
    return ctrl, model, view, broker


class TestCalibrationControllerInit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._qt_app = QApplication.instance() or QApplication(sys.argv)

    def test_not_active_before_load(self):
        ctrl, *_ = _make_ctrl()
        self.assertFalse(ctrl._active)



class TestCalibrationControllerLoad(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._qt_app = QApplication.instance() or QApplication(sys.argv)

    def test_load_sets_active(self):
        ctrl, _, _, _ = _make_ctrl()
        ctrl.load()
        self.assertTrue(ctrl._active)

    def test_load_subscribes_to_latest_image(self):
        ctrl, _, _, broker = _make_ctrl()
        ctrl.load()
        subscribed_topics = [c[0][0] for c in broker.subscribe.call_args_list]
        self.assertIn(VisionTopics.LATEST_IMAGE, subscribed_topics)

    def test_wires_destroyed_signal(self):
        ctrl, _, view, _ = _make_ctrl()
        ctrl.load()
        view.destroyed.connect.assert_called_once()

    def test_wires_capture_signal(self):
        ctrl, _, view, _ = _make_ctrl()
        ctrl.load()
        view.capture_requested.connect.assert_called_once()

    def test_wires_calibrate_camera_signal(self):
        ctrl, _, view, _ = _make_ctrl()
        ctrl.load()
        view.calibrate_camera_requested.connect.assert_called_once()

    def test_wires_calibrate_robot_signal(self):
        ctrl, _, view, _ = _make_ctrl()
        ctrl.load()
        view.calibrate_robot_requested.connect.assert_called_once()

    def test_wires_calibrate_sequence_signal(self):
        ctrl, _, view, _ = _make_ctrl()
        ctrl.load()
        view.calibrate_sequence_requested.connect.assert_called_once()


class TestCalibrationControllerStop(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._qt_app = QApplication.instance() or QApplication(sys.argv)

    def test_stop_sets_inactive(self):
        ctrl, _, _, _ = _make_ctrl()
        ctrl.load()
        ctrl.stop()
        self.assertFalse(ctrl._active)

    def test_stop_unsubscribes_vision_topic(self):
        ctrl, _, _, broker = _make_ctrl()
        ctrl.load()
        ctrl.stop()
        unsubbed_topics = [c[0][0] for c in broker.unsubscribe.call_args_list]
        self.assertIn(VisionTopics.LATEST_IMAGE, unsubbed_topics)

    def test_stop_clears_subs_list(self):
        ctrl, _, _, _ = _make_ctrl()
        ctrl.load()
        ctrl.stop()
        self.assertEqual(ctrl._subs, [])

    def test_stop_without_load_does_not_raise(self):
        ctrl, _, _, _ = _make_ctrl()
        ctrl.stop()  # must not raise


class TestCalibrationControllerHandlers(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._qt_app = QApplication.instance() or QApplication(sys.argv)

    def test_on_capture_calls_model(self):
        ctrl, model, _, _ = _make_ctrl()
        ctrl._on_capture()
        model.capture_calibration_image.assert_called_once()

    def test_on_calibrate_camera_calls_model(self):
        ctrl, model, _, _ = _make_ctrl()
        ctrl._on_calibrate_camera()
        for thread, _ in list(ctrl._threads):
            thread.wait(2000)
        model.calibrate_camera.assert_called_once()

    def test_on_calibrate_robot_calls_model(self):
        ctrl, model, _, _ = _make_ctrl()
        ctrl._on_calibrate_robot()
        model.calibrate_robot.assert_called_once()

    def test_on_calibrate_sequence_calls_model(self):
        ctrl, model, _, _ = _make_ctrl()
        ctrl._on_calibrate_sequence()
        for thread, _ in list(ctrl._threads):
            thread.wait(2000)
        model.calibrate_camera_and_robot.assert_called_once()


    def test_success_appends_tick_prefix(self):
        ctrl, _, view, _ = _make_ctrl(capture=(True, "done"))
        ctrl._on_capture()
        view.append_log.assert_called_once_with("✓ done")

    def test_failure_appends_cross_prefix(self):
        ctrl, _, view, _ = _make_ctrl()
        ctrl._log(False, "no cam")
        view.append_log.assert_called_once_with("✗ no cam")

    def test_log_helper_success(self):
        ctrl, _, view, _ = _make_ctrl()
        ctrl._log(True, "hello")
        view.append_log.assert_called_once_with("✓ hello")

    def test_log_helper_failure(self):
        ctrl, _, view, _ = _make_ctrl()
        ctrl._log(False, "oops")
        view.append_log.assert_called_once_with("✗ oops")


class TestCalibrationControllerCameraFrame(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._qt_app = QApplication.instance() or QApplication(sys.argv)

    def test_camera_frame_updates_view_when_active(self):
        ctrl, _, view, _ = _make_ctrl()
        ctrl._active = True
        fake_frame = object()
        ctrl._on_camera_frame(fake_frame)
        view.update_camera_view.assert_called_once_with(fake_frame)

    def test_camera_frame_ignored_when_inactive(self):
        ctrl, _, view, _ = _make_ctrl()
        ctrl._active = False
        ctrl._on_camera_frame(object())
        view.update_camera_view.assert_not_called()

    def test_camera_frame_ignored_when_none(self):
        ctrl, _, view, _ = _make_ctrl()
        ctrl._active = True
        ctrl._on_camera_frame(None)
        view.update_camera_view.assert_not_called()

    def test_latest_image_raw_forwards_image_from_dict(self):
        ctrl, _, _, _ = _make_ctrl()
        ctrl._active = True
        fake_frame = object()
        ctrl._bridge = MagicMock()
        ctrl._on_latest_image_raw({"image": fake_frame})
        ctrl._bridge.camera_frame.emit.assert_called_once_with(fake_frame)

    def test_latest_image_raw_ignores_non_dict(self):
        ctrl, _, view, _ = _make_ctrl()
        ctrl._active = True
        ctrl._on_latest_image_raw("not a dict")
        view.update_camera_view.assert_not_called()

    def test_latest_image_raw_ignores_dict_without_image_key(self):
        ctrl, _, _, _ = _make_ctrl()
        ctrl._active = True
        ctrl._bridge = MagicMock()
        ctrl._on_latest_image_raw({"other": "data"})
        ctrl._bridge.camera_frame.emit.assert_not_called()


if __name__ == "__main__":
    unittest.main()