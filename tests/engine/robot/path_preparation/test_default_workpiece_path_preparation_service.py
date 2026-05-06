import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.engine.robot.path_preparation.default_workpiece_path_preparation_service import (
    DefaultWorkpiecePathPreparationService,
)


class _Schema:
    @staticmethod
    def get_defaults():
        return {
            "spraying_height": "0",
            "rz_angle": "0",
        }


class _SegmentConfig:
    schema = _Schema()


def _make_service(**kwargs):
    params = {
        "logger": MagicMock(),
        "segment_config": _SegmentConfig(),
        "transformer": None,
        "resolver": None,
        "base_position_provider": lambda: [0, 0, 100, 0, 0, 0],
    }
    params.update(kwargs)
    return DefaultWorkpiecePathPreparationService(**params)


class TestDefaultWorkpiecePathPreparationService(unittest.TestCase):
    def test_build_execution_plan_paint_job_includes_pickup_and_target_metadata(self):
        registry = MagicMock()
        registry.by_name.side_effect = lambda name: {
            "tool": SimpleNamespace(offset_x=1.5, offset_y=2.5),
            "pickup": SimpleNamespace(offset_x=3.5, offset_y=4.5),
        }[name]
        resolver = MagicMock()
        resolver.registry = registry
        resolver.get_frame.return_value = SimpleNamespace(
            mapper=SimpleNamespace(target_pose=SimpleNamespace(rz=77.0))
        )
        service = _make_service(
            resolver=resolver,
            target_point_name="tool",
            pickup_target_point_name="pickup",
            calibration_frame_name="paint_frame",
        )
        workpiece = {
            "height_mm": 12.0,
            "offset": 8.0,
            "pickupPoint": [15, 25],
            "dxfPath": "/tmp/mock.dxf",
            "sprayPattern": {
                "Contour": [
                    {
                        "contour": [[0, 0], [10, 0], [10, 10]],
                        "settings": {"velocity": 80, "acceleration": 40, "spraying_height": "5"},
                    }
                ]
            },
        }

        with patch.object(
            service,
            "_transform_to_robot",
            return_value=[[100, 200, 300, 180, 0, 10], [110, 210, 300, 180, 0, 20]],
        ), patch.object(
            service,
            "_transform_single_pixel_to_robot",
            side_effect=[(500.0, 600.0), (700.0, 800.0)],
        ), patch(
            "src.engine.robot.path_preparation.default_workpiece_path_preparation_service.compute_pickup_rz_from_robot_path",
            return_value=33.0,
        ) as pickup_rz:
            plan = service.build_execution_plan(workpiece)

        job = plan.execution_jobs[0]
        self.assertEqual(8.0, job["pivot_offset_mm"])
        self.assertEqual([700.0, 800.0], job["pickup_xy"])
        self.assertEqual(33.0, job["pickup_rz"])
        self.assertEqual("pickup", job["pickup_target_point_name"])
        self.assertEqual(3.5, job["pickup_target_offset_x"])
        self.assertEqual(4.5, job["pickup_target_offset_y"])
        self.assertEqual(77.0, job["pickup_reference_rz"])
        self.assertEqual("tool", job["execution_target_point_name"])
        self.assertEqual(1.5, job["execution_target_offset_x"])
        self.assertEqual(2.5, job["execution_target_offset_y"])
        self.assertEqual(77.0, job["execution_reference_rz"])
        self.assertFalse(job["use_workpiece_layer"])
        self.assertTrue(job["source_has_dxf"])
        pickup_rz.assert_called_once()

    def test_build_execution_plan_workpiece_layer_uses_contour_directed_pickup_rz(self):
        service = _make_service(
            execute_from_workpiece_layer=True,
            target_point_name="tool",
        )
        workpiece = {
            "contour": [[0, 0], [10, 0], [10, 10], [0, 10]],
            "pickupPoint": {"x": 5, "y": 6},
            "dxfPath": "/tmp/mock.dxf",
            "sprayPattern": {},
        }

        with patch.object(
            service,
            "_transform_to_robot",
            side_effect=[
                [[1, 2, 3, 180, 0, 0], [4, 5, 3, 180, 0, 0]],
                [[10, 20, 30, 180, 0, 0], [40, 50, 30, 180, 0, 0]],
            ],
        ), patch.object(
            service,
            "_transform_single_pixel_to_robot",
            side_effect=[(11.0, 12.0), (13.0, 14.0)],
        ), patch(
            "src.engine.robot.path_preparation.default_workpiece_path_preparation_service.compute_pickup_rz_from_robot_contour_with_direction",
            return_value=44.0,
        ) as contour_rz, patch(
            "src.engine.robot.path_preparation.default_workpiece_path_preparation_service.compute_pickup_rz_from_robot_path",
        ) as path_rz:
            plan = service.build_execution_plan(workpiece)

        job = plan.execution_jobs[0]
        self.assertTrue(job["use_workpiece_layer"])
        self.assertEqual([13.0, 14.0], job["pickup_xy"])
        self.assertEqual(44.0, job["pickup_rz"])
        contour_rz.assert_called_once()
        path_rz.assert_not_called()

    def test_pickup_target_defaults_to_execution_target_when_not_configured(self):
        registry = MagicMock()
        registry.by_name.return_value = SimpleNamespace(offset_x=9.0, offset_y=10.0)
        resolver = MagicMock()
        resolver.registry = registry
        resolver.get_frame.return_value = SimpleNamespace(
            mapper=SimpleNamespace(target_pose=SimpleNamespace(rz=15.0))
        )
        service = _make_service(
            resolver=resolver,
            target_point_name="tool",
            pickup_target_point_name="",
            calibration_frame_name="paint_frame",
        )
        workpiece = {
            "pickupPoint": "1,2",
            "dxfPath": "/tmp/mock.dxf",
            "sprayPattern": {
                "Contour": [
                    {
                        "contour": [[0, 0], [1, 0], [1, 1]],
                        "settings": {},
                    }
                ]
            },
        }

        with patch.object(
            service,
            "_transform_to_robot",
            return_value=[[1, 2, 3, 180, 0, 0], [4, 5, 3, 180, 0, 0]],
        ), patch.object(
            service,
            "_transform_single_pixel_to_robot",
            side_effect=[(6.0, 7.0), (8.0, 9.0)],
        ), patch(
            "src.engine.robot.path_preparation.default_workpiece_path_preparation_service.compute_pickup_rz_from_robot_path",
            return_value=12.0,
        ):
            plan = service.build_execution_plan(workpiece)

        job = plan.execution_jobs[0]
        self.assertEqual("tool", job["execution_target_point_name"])
        self.assertEqual("tool", job["pickup_target_point_name"])
        self.assertEqual(9.0, job["execution_target_offset_x"])
        self.assertEqual(9.0, job["pickup_target_offset_x"])
        self.assertEqual(10.0, job["execution_target_offset_y"])
        self.assertEqual(10.0, job["pickup_target_offset_y"])
        self.assertEqual(15.0, job["execution_reference_rz"])
        self.assertEqual(15.0, job["pickup_reference_rz"])

    def test_transform_single_pixel_to_robot_uses_transformer_when_no_resolver(self):
        transformer = MagicMock()
        transformer.is_available.return_value = True
        transformer.transform.return_value = (101.0, 202.0)
        service = _make_service(transformer=transformer)

        result = service._transform_single_pixel_to_robot(
            10.0,
            20.0,
            {"spraying_height": "5", "rz_angle": "7"},
        )

        self.assertEqual((101.0, 202.0), result)
        transformer.transform.assert_called_once_with(10.0, 20.0)

    def test_transform_single_pixel_to_robot_uses_resolver_and_compensation(self):
        registry = MagicMock()
        registry.by_name.return_value = SimpleNamespace(offset_x=0.0, offset_y=0.0)
        resolver = MagicMock()
        resolver.registry = registry
        resolver.resolve.return_value = SimpleNamespace(final_xy=(301.0, 302.0))
        service = _make_service(
            resolver=resolver,
            target_point_name="tool",
            pixel_height_compensation_fn=lambda height_mm: (1.5, 2.5),
        )

        result = service._transform_single_pixel_to_robot(
            10.0,
            20.0,
            {"height_mm": 12.0, "spraying_height": "5", "rz_angle": "7"},
            target_point_name="pickup",
            frame_name="paint_frame",
            rz_override=33.0,
        )

        self.assertEqual((301.0, 302.0), result)
        request = resolver.resolve.call_args.args[0]
        target_point = resolver.resolve.call_args.args[1]
        self.assertEqual(8.5, request.x_pixels)
        self.assertEqual(17.5, request.y_pixels)
        self.assertEqual(105.0, request.z_mm)
        self.assertEqual(33.0, request.rz_degrees)
        self.assertEqual(target_point, registry.by_name.return_value)
        self.assertEqual("paint_frame", resolver.resolve.call_args.kwargs["frame"])
        registry.by_name.assert_called_once_with("pickup")

    def test_transform_single_pixel_to_robot_falls_back_to_raw_pixels_without_transformer(self):
        service = _make_service(transformer=None)

        result = service._transform_single_pixel_to_robot(
            10.0,
            20.0,
            {"height_mm": 5.0},
        )

        self.assertEqual((10.0, 20.0), result)

    def test_transform_to_robot_path_tangent_uses_compensation_and_computed_rz(self):
        transformer = MagicMock()
        transformer.is_available.return_value = True
        transformer.transform.side_effect = [(100.0, 200.0), (110.0, 210.0)]
        service = _make_service(
            transformer=transformer,
            rz_mode="path_tangent",
            pixel_height_compensation_fn=lambda height_mm: (1.0, 2.0),
        )

        with patch(
            "src.engine.robot.path_preparation.geometry.compute_path_aligned_rz_degrees",
            return_value=[45.0, 50.0],
        ) as compute_rz:
            result = service._transform_to_robot(
                [[10.0, 20.0], [30.0, 40.0]],
                {"height_mm": 8.0, "spraying_height": "5", "rz_angle": "7"},
            )

        self.assertEqual(
            [
                [100.0, 200.0, 105.0, 180.0, 0.0, 45.0],
                [110.0, 210.0, 105.0, 180.0, 0.0, 50.0],
            ],
            result,
        )
        transformer.transform.assert_any_call(9.0, 18.0)
        transformer.transform.assert_any_call(29.0, 38.0)
        compute_rz.assert_called_once_with(
            [(100.0, 200.0), (110.0, 210.0)],
            base_rz_offset_degrees=7.0,
        )

    def test_transform_to_robot_with_resolver_uses_seeded_z_values(self):
        registry = MagicMock()
        registry.by_name.return_value = SimpleNamespace(offset_x=0.0, offset_y=0.0)
        resolver = MagicMock()
        resolver.registry = registry
        resolver.resolve.side_effect = [
            SimpleNamespace(final_xy=(1.0, 2.0), z=301.0),
            SimpleNamespace(final_xy=(3.0, 4.0), z=302.0),
        ]
        service = _make_service(
            resolver=resolver,
            target_point_name="tool",
        )

        result = service._transform_to_robot(
            [[10.0, 20.0], [30.0, 40.0]],
            {"spraying_height": "5", "rz_angle": "7"},
        )

        self.assertEqual(
            [
                [1.0, 2.0, 301.0, 180.0, 0.0, 7.0],
                [3.0, 4.0, 302.0, 180.0, 0.0, 7.0],
            ],
            result,
        )
        first_request = resolver.resolve.call_args_list[0].args[0]
        self.assertEqual(10.0, first_request.x_pixels)
        self.assertEqual(20.0, first_request.y_pixels)
        self.assertEqual(105.0, first_request.z_mm)
        registry.by_name.assert_called_once_with("tool")

    def test_parse_pickup_point_accepts_string_sequence_and_mapping(self):
        self.assertEqual((1.5, 2.5), DefaultWorkpiecePathPreparationService._parse_pickup_point("1.5,2.5"))
        self.assertEqual((3.0, 4.0), DefaultWorkpiecePathPreparationService._parse_pickup_point([3, 4]))
        self.assertEqual((5.0, 6.0), DefaultWorkpiecePathPreparationService._parse_pickup_point({"x": 5, "y": 6}))

    def test_parse_pickup_point_rejects_invalid_shapes(self):
        self.assertIsNone(DefaultWorkpiecePathPreparationService._parse_pickup_point(None))
        self.assertIsNone(DefaultWorkpiecePathPreparationService._parse_pickup_point("bad"))
        self.assertIsNone(DefaultWorkpiecePathPreparationService._parse_pickup_point([1]))
        self.assertIsNone(DefaultWorkpiecePathPreparationService._parse_pickup_point({"x": 1}))

    def test_extract_pickup_pixel_prefers_explicit_pickup_point(self):
        service = _make_service()

        result = service._extract_pickup_pixel(
            {
                "pickupPoint": "7,8",
                "contour": [[0, 0], [100, 0], [100, 100], [0, 100]],
            }
        )

        self.assertEqual((7.0, 8.0), result)

    def test_extract_pickup_pixel_falls_back_to_contour_centroid(self):
        service = _make_service()

        result = service._extract_pickup_pixel(
            {
                "contour": [[0, 0], [10, 0], [10, 10], [0, 10]],
            }
        )

        self.assertEqual((5.0, 5.0), result)

    def test_extract_pickup_pixel_falls_back_to_mean_when_contour_area_is_zero(self):
        service = _make_service()

        with patch(
            "src.engine.robot.path_preparation.default_workpiece_path_preparation_service.cv2.moments",
            return_value={"m00": 0.0},
        ):
            result = service._extract_pickup_pixel(
                {
                    "contour": [[0, 0], [10, 10], [20, 20]],
                }
            )

        self.assertEqual((10.0, 10.0), result)

    def test_extract_pickup_pixel_returns_none_without_pickup_point_or_contour(self):
        service = _make_service()

        self.assertIsNone(service._extract_pickup_pixel({}))


if __name__ == "__main__":
    unittest.main()
