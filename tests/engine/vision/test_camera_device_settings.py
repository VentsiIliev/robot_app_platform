import unittest

from src.engine.vision.camera_device_settings import (
    CameraDeviceSpec,
    CameraDevicesConfig,
    CameraDevicesConfigSerializer,
)


class TestCameraDevicesConfigSerializer(unittest.TestCase):
    def setUp(self) -> None:
        self.serializer = CameraDevicesConfigSerializer()

    def test_round_trip_preserves_path_and_index_devices(self) -> None:
        settings = CameraDevicesConfig(
            cameras={
                "primary_vision": CameraDeviceSpec(
                    device="/dev/v4l/by-path/primary-video-index0",
                    width=1280,
                    height=720,
                    required=True,
                    flip_horizontal=True,
                    flip_vertical=False,
                    rotate_degrees=90,
                ),
                "auxiliary": CameraDeviceSpec(
                    device=2,
                    width=640,
                    height=480,
                    flip_vertical=True,
                    rotate_degrees=180,
                ),
            }
        )

        restored = self.serializer.from_dict(self.serializer.to_dict(settings))

        self.assertEqual(restored, settings)

    def test_missing_orientation_flags_use_identity_defaults(self) -> None:
        restored = self.serializer.from_dict({"cameras": {"primary_vision": {"device": 0}}})
        spec = restored.get("primary_vision")
        self.assertFalse(spec.flip_horizontal)
        self.assertFalse(spec.flip_vertical)
        self.assertEqual(spec.rotate_degrees, 0)

    def test_rotation_is_folded_to_a_canonical_value(self) -> None:
        restored = self.serializer.from_dict({"cameras": {"primary_vision": {
            "device": 0,
            "rotate_degrees": 450,
        }}})
        self.assertEqual(restored.get("primary_vision").rotate_degrees, 90)

    def test_rejects_rotation_that_is_not_a_multiple_of_ninety(self) -> None:
        with self.assertRaisesRegex(ValueError, "rotation must be one of 0, 90, 180 or 270"):
            self.serializer.from_dict({"cameras": {"primary_vision": {
                "device": 0,
                "rotate_degrees": 45,
            }}})

    def test_rejects_non_integer_rotation(self) -> None:
        with self.assertRaisesRegex(ValueError, "rotation must be one of 0, 90, 180 or 270"):
            self.serializer.from_dict({"cameras": {"primary_vision": {
                "device": 0,
                "rotate_degrees": "90",
            }}})

    def test_rejects_non_boolean_flip(self) -> None:
        with self.assertRaisesRegex(ValueError, "flip_horizontal must be true or false"):
            self.serializer.from_dict({"cameras": {"primary_vision": {
                "device": 0,
                "flip_horizontal": "true",
            }}})

    def test_rejects_empty_device_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            self.serializer.from_dict(
                {"cameras": {"primary_vision": {"device": "  "}}}
            )

    def test_rejects_metadata_free_invalid_device_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "integer index or device path"):
            self.serializer.from_dict(
                {"cameras": {"primary_vision": {"device": None}}}
            )


if __name__ == "__main__":
    unittest.main()
