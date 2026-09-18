import unittest

import numpy as np

from src.engine.vision.implementation.VisionSystem.services.brightness_service import (
    BrightnessService,
)


class _CameraSettings:
    @staticmethod
    def get_brightness_kp():
        return 0.0

    @staticmethod
    def get_brightness_ki():
        return 0.0

    @staticmethod
    def get_brightness_kd():
        return 0.0

    @staticmethod
    def get_target_brightness():
        return 100.0

    @staticmethod
    def get_brightness_area_points():
        return [[0, 0], [3, 0], [3, 3], [0, 3]]


class TestBrightnessService(unittest.TestCase):
    def test_restores_last_adjustment_when_returning_to_work_area(self):
        active_area = ["magazine"]
        service = BrightnessService(
            _CameraSettings(),
            area_key_provider=lambda: active_area[0],
        )
        image = np.full((4, 4, 3), 50, dtype=np.uint8)

        service.adjust(image)
        magazine_adjustment = service._adjustment

        active_area[0] = "paint"
        service.adjust(np.full((4, 4, 3), 180, dtype=np.uint8))
        self.assertNotEqual(magazine_adjustment, service._adjustment)

        service.lock_adjustment()
        active_area[0] = "magazine"
        service.adjust(image)

        self.assertEqual(magazine_adjustment, service._adjustment)

    def test_first_visit_to_new_area_starts_from_current_adjustment(self):
        active_area = ["magazine"]
        service = BrightnessService(
            _CameraSettings(),
            area_key_provider=lambda: active_area[0],
        )
        service._adjustment = 25.0
        service.lock_adjustment()

        service.adjust(np.full((4, 4, 3), 50, dtype=np.uint8))
        active_area[0] = "paint"
        service.adjust(np.full((4, 4, 3), 50, dtype=np.uint8))

        self.assertEqual(25.0, service._adjustment)


if __name__ == "__main__":
    unittest.main()
