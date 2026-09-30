import unittest
from unittest.mock import MagicMock, patch

from src.engine.vision.implementation.VisionSystem.camera_initialization import (
    CameraInitializer,
)
from src.engine.vision.implementation.VisionSystem.VisionSystem import VisionSystem


class TestCameraInitializer(unittest.TestCase):
    @patch(
        "src.engine.vision.implementation.VisionSystem.camera_initialization.Camera"
    )
    def test_passes_device_path_to_camera_backend(self, camera_cls) -> None:
        camera = MagicMock()
        camera.cap.isOpened.return_value = True
        camera.cap.read.return_value = (True, object())
        camera_cls.return_value = camera
        device = "/dev/v4l/by-path/primary-video-index0"

        result, resolved = CameraInitializer(1280, 720).initializeCameraWithRetry(
            device,
            max_retries=1,
            allow_fallback=False,
        )

        self.assertIs(result, camera)
        self.assertEqual(resolved, device)
        camera_cls.assert_called_once_with(
            width=1280,
            height=720,
            device=device,
            fps=30,
        )

    @patch(
        "src.engine.vision.implementation.VisionSystem.camera_initialization.Camera"
    )
    def test_strict_device_failure_does_not_scan_for_another_camera(
        self, camera_cls
    ) -> None:
        camera = MagicMock()
        camera.cap.isOpened.return_value = False
        camera_cls.return_value = camera
        initializer = CameraInitializer(1280, 720)
        initializer._findAndInitializeCamera = MagicMock()

        result, resolved = initializer.initializeCameraWithRetry(
            "/dev/missing-camera",
            max_retries=1,
            allow_fallback=False,
        )

        self.assertIsNone(result)
        self.assertIsNone(resolved)
        initializer._findAndInitializeCamera.assert_not_called()


class TestVisionSystemConfiguredCamera(unittest.TestCase):
    @patch(
        "src.engine.vision.implementation.VisionSystem.VisionSystem.CameraInitializer"
    )
    def test_setup_uses_configured_device_and_resolution_strictly(
        self, initializer_cls
    ) -> None:
        camera = MagicMock()
        initializer_cls.return_value.initializeCameraWithRetry.return_value = (
            camera,
            "/dev/primary",
        )
        system = VisionSystem.__new__(VisionSystem)
        system._camera_device = "/dev/primary"
        system._camera_resolution = (1920, 1080)
        system._allow_camera_fallback = False
        system.camera_settings = MagicMock()
        system.camera = None
        system._configure_hardware_auto_exposure = MagicMock()

        system.setup_camera()

        system.camera_settings.set_resolution.assert_called_once_with(1920, 1080)
        initializer_cls.assert_called_once_with(width=1920, height=1080)
        initializer_cls.return_value.initializeCameraWithRetry.assert_called_once_with(
            "/dev/primary",
            should_cancel=None,
            allow_fallback=False,
        )
        system.camera_settings.set_camera_index.assert_not_called()


if __name__ == "__main__":
    unittest.main()
