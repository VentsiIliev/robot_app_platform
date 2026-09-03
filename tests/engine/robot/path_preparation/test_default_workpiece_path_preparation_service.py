import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from src.engine.robot.path_preparation.default_workpiece_path_preparation_service import (
    DefaultWorkpiecePathPreparationService,
    PIXEL_TO_MM_MODE_HOMOGRAPHY_RESIDUAL,
    _submit_debug_plot,
)
from src.engine.robot.path_preparation.geometry import (
    compute_pickup_rz_from_initial_paint_segment,
    compute_pickup_rz_from_min_rect_long_axis,
    compute_pickup_rz_from_stable_paint_segment,
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
        "transformer_getter": None,
        "resolver_getter": None,
        "base_position_provider": lambda: [0, 0, 100, 0, 0, 0],
    }
    params.update(kwargs)
    return DefaultWorkpiecePathPreparationService(**params)


class TestDefaultWorkpiecePathPreparationService(unittest.TestCase):
    def test_submit_debug_plot_allows_plot_function_label_keyword(self):
        logger = MagicMock()
        plot_fn = MagicMock()

        with patch(
            "src.engine.robot.path_preparation.default_workpiece_path_preparation_service._ensure_debug_plot_worker"
        ), patch(
            "src.engine.robot.path_preparation.default_workpiece_path_preparation_service._DEBUG_PLOT_QUEUE"
        ) as queue:
            _submit_debug_plot(logger, "debug_plot", plot_fn, label="workpiece_layer")

        queue.put_nowait.assert_called_once_with(
            (logger, "debug_plot", plot_fn, (), {"label": "workpiece_layer"})
        )

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
        pickup_rz.assert_called_once()

    def test_transform_to_robot_uses_dynamic_calibration_frame_name_getter(self):
        registry = MagicMock()
        registry.by_name.return_value = SimpleNamespace(offset_x=0.0, offset_y=0.0)
        resolver = MagicMock()
        resolver.registry = registry
        resolver.resolve.return_value = SimpleNamespace(final_xy=(10.0, 20.0), z=100.0)
        service = _make_service(
            resolver=resolver,
            target_point_name="tool",
            calibration_frame_name="calibration",
            calibration_frame_name_getter=lambda: "magazine",
            pixel_to_mm_mode=PIXEL_TO_MM_MODE_HOMOGRAPHY_RESIDUAL,
        )

        result = service._transform_to_robot(
            np.asarray([[1.0, 2.0]], dtype=np.float64),
            {"spraying_height": "0", "rz_angle": "0"},
        )

        self.assertEqual(10.0, result[0][0])
        self.assertEqual(20.0, result[0][1])
        self.assertEqual("magazine", resolver.resolve.call_args.kwargs["frame"])

    def test_build_execution_plan_resolves_pickup_xy_with_normalized_axis_rz(self):
        registry = MagicMock()
        registry.by_name.return_value = SimpleNamespace(offset_x=0.0, offset_y=0.0)
        resolver = MagicMock()
        resolver.registry = registry
        resolver.get_frame.return_value = SimpleNamespace(
            mapper=SimpleNamespace(target_pose=SimpleNamespace(rz=0.0))
        )
        service = _make_service(
            resolver=resolver,
            target_point_name="tool",
            pickup_target_point_name="tool",
            calibration_frame_name="paint_frame",
        )
        workpiece = {
            "pickupPoint": [15, 25],
            "sprayPattern": {
                "Contour": [
                    {
                        "contour": [[0, 0], [10, 0], [10, 10]],
                        "settings": {},
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
        ) as transform_pickup, patch(
            "src.engine.robot.path_preparation.default_workpiece_path_preparation_service.compute_pickup_rz_from_robot_path",
            return_value=174.0,
        ):
            plan = service.build_execution_plan(workpiece)

        job = plan.execution_jobs[0]
        self.assertEqual([700.0, 800.0], job["pickup_xy"])
        self.assertAlmostEqual(-6.0, job["pickup_rz"], places=6)
        self.assertNotIn("rz_override", transform_pickup.call_args_list[0].kwargs)
        self.assertAlmostEqual(-6.0, transform_pickup.call_args_list[1].kwargs["rz_override"], places=6)

    def test_build_execution_plan_applies_pickup_axis_alignment_sign_before_resolving_xy(self):
        registry = MagicMock()
        registry.by_name.return_value = SimpleNamespace(offset_x=0.0, offset_y=0.0)
        resolver = MagicMock()
        resolver.registry = registry
        resolver.get_frame.return_value = SimpleNamespace(
            mapper=SimpleNamespace(target_pose=SimpleNamespace(rz=0.0))
        )
        service = _make_service(
            resolver=resolver,
            target_point_name="tool",
            pickup_target_point_name="tool",
            calibration_frame_name="paint_frame",
            pickup_axis_alignment_sign=-1.0,
        )
        workpiece = {
            "pickupPoint": [15, 25],
            "sprayPattern": {
                "Contour": [
                    {
                        "contour": [[0, 0], [10, 0], [10, 10]],
                        "settings": {},
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
        ) as transform_pickup, patch(
            "src.engine.robot.path_preparation.default_workpiece_path_preparation_service.compute_pickup_rz_from_robot_path",
            return_value=174.0,
        ):
            plan = service.build_execution_plan(workpiece)

        job = plan.execution_jobs[0]
        self.assertEqual([700.0, 800.0], job["pickup_xy"])
        self.assertAlmostEqual(6.0, job["pickup_rz"], places=6)
        self.assertAlmostEqual(6.0, transform_pickup.call_args_list[1].kwargs["rz_override"], places=6)

    def test_build_execution_plan_uses_transformed_path_when_no_contour_processor_is_configured(self):
        service = _make_service()
        workpiece = {
            "sprayPattern": {
                "Contour": [
                    {
                        "contour": [[0, 0], [10, 0], [10, 10], [0, 0]],
                        "settings": {},
                    }
                ]
            },
        }
        robot_path = [
            [0.0, 0.0, 0.0, 180.0, 0.0, 0.0],
            [10.0, 0.0, 0.0, 180.0, 0.0, 0.0],
            [10.0, 10.0, 0.0, 180.0, 0.0, 0.0],
            [0.0, 10.0, 0.0, 180.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 180.0, 0.0, 0.0],
        ]

        with patch.object(
            service,
            "_transform_to_robot",
            return_value=robot_path,
        ):
            plan = service.build_execution_plan(workpiece)

        self.assertEqual(robot_path, plan.prepared_paths[0])
        self.assertEqual(robot_path, plan.sampled_paths[0])
        self.assertEqual(robot_path, plan.execution_jobs[0]["execution_path"])

    def test_build_execution_plan_uses_injected_contour_processor_output(self):
        def contour_processor(_path_pts, _settings):
            return {
                "method": "test_processor",
                "prepared_xy": [[0.0, 0.0], [5.0, 0.0], [10.0, 0.0]],
                "curve_xy": [[0.0, 0.0], [10.0, 0.0]],
            }

        service = _make_service(contour_processor=contour_processor)
        workpiece = {
            "sprayPattern": {
                "Contour": [
                    {
                        "contour": [[0, 0], [10, 0], [10, 10]],
                        "settings": {},
                    }
                ]
            },
        }
        robot_path = [
            [0.0, 0.0, 0.0, 180.0, 0.0, 0.0],
            [10.0, 0.0, 0.0, 180.0, 0.0, 0.0],
            [10.0, 10.0, 0.0, 180.0, 0.0, 0.0],
        ]

        with patch.object(
            service,
            "_transform_to_robot",
            return_value=robot_path,
        ):
            plan = service.build_execution_plan(workpiece)

        self.assertEqual(3, len(plan.prepared_paths[0]))
        self.assertEqual(3, len(plan.sampled_paths[0]))
        self.assertEqual(3, len(plan.execution_jobs[0]["execution_path"]))
        self.assertEqual([5.0, 0.0], plan.execution_jobs[0]["execution_path"][1][:2])

    def test_build_execution_plan_paint_job_prefers_segment_offset_over_workpiece_offset(self):
        service = _make_service()
        workpiece = {
            "offset": 8.0,
            "sprayPattern": {
                "Contour": [
                    {
                        "contour": [[0, 0], [10, 0], [10, 10]],
                        "settings": {"offset": "12.5"},
                    }
                ]
            },
        }

        with patch.object(
            service,
            "_transform_to_robot",
            return_value=[[100, 200, 300, 180, 0, 10], [110, 210, 300, 180, 0, 20]],
        ):
            plan = service.build_execution_plan(workpiece)

        job = plan.execution_jobs[0]
        self.assertEqual(12.5, job["pivot_offset_mm"])

    def test_build_execution_plan_workpiece_layer_uses_min_rect_pickup_rz(self):
        service = _make_service(
            execute_from_workpiece_layer=True,
            target_point_name="tool",
        )
        workpiece = {
            "contour": [[0, 0], [10, 0], [10, 10], [0, 10]],
            "pickupPoint": {"x": 5, "y": 6},
            "sprayPattern": {},
        }

        with patch.object(
            service,
            "_transform_to_robot",
            return_value=[
                [10, 20, 30, 180, 0, 0],
                [40, 50, 30, 180, 0, 0],
                [45, 55, 30, 180, 0, 0],
            ],
        ), patch.object(
            service,
            "_transform_single_pixel_to_robot",
            side_effect=[(11.0, 12.0), (13.0, 14.0)],
        ), patch(
            "src.engine.robot.path_preparation.default_workpiece_path_preparation_service.compute_pickup_rz_from_min_rect_long_axis",
            return_value=44.0,
        ) as min_rect_rz, patch(
            "src.engine.robot.path_preparation.default_workpiece_path_preparation_service.compute_pickup_rz_from_robot_path",
        ) as path_rz:
            plan = service.build_execution_plan(workpiece)

        job = plan.execution_jobs[0]
        self.assertTrue(job["use_workpiece_layer"])
        self.assertEqual([13.0, 14.0], job["pickup_xy"])
        self.assertEqual(44.0, job["pickup_rz"])
        min_rect_rz.assert_called_once()
        path_rz.assert_not_called()

    def test_build_execution_plan_accepts_nested_workpiece_contour_payload(self):
        service = _make_service(
            execute_from_workpiece_layer=True,
            target_point_name="tool",
        )
        workpiece = {
            "contour": {"contour": [[0, 0], [10, 0], [10, 10], [0, 10]]},
            "sprayPattern": {},
        }

        with patch.object(
            service,
            "_transform_to_robot",
            return_value=[
                [10, 20, 30, 180, 0, 0],
                [40, 50, 30, 180, 0, 0],
                [45, 55, 30, 180, 0, 0],
            ],
        ), patch.object(
            service,
            "_transform_single_pixel_to_robot",
            side_effect=[(11.0, 12.0), (13.0, 14.0)],
        ), patch(
            "src.engine.robot.path_preparation.default_workpiece_path_preparation_service.compute_pickup_rz_from_min_rect_long_axis",
            return_value=44.0,
        ):
            plan = service.build_execution_plan(workpiece)

        job = plan.execution_jobs[0]
        self.assertTrue(job["use_workpiece_layer"])
        self.assertEqual([13.0, 14.0], job["pickup_xy"])
        service._logger.warning.assert_not_called()

    def test_build_execution_plan_accepts_numpy_nested_workpiece_contour_payload(self):
        service = _make_service(
            execute_from_workpiece_layer=True,
            target_point_name="tool",
        )
        workpiece = {
            "contour": {"contour": np.asarray([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float32)},
            "sprayPattern": {},
        }

        with patch.object(
            service,
            "_transform_to_robot",
            return_value=[
                [10, 20, 30, 180, 0, 0],
                [40, 50, 30, 180, 0, 0],
                [45, 55, 30, 180, 0, 0],
            ],
        ), patch.object(
            service,
            "_transform_single_pixel_to_robot",
            side_effect=[(11.0, 12.0), (13.0, 14.0)],
        ), patch(
            "src.engine.robot.path_preparation.default_workpiece_path_preparation_service.compute_pickup_rz_from_min_rect_long_axis",
            return_value=44.0,
        ):
            plan = service.build_execution_plan(workpiece)

        job = plan.execution_jobs[0]
        self.assertTrue(job["use_workpiece_layer"])
        self.assertEqual([13.0, 14.0], job["pickup_xy"])
        service._logger.warning.assert_not_called()

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

    def test_transform_single_pixel_to_robot_uses_live_transformer_getter(self):
        transformer = MagicMock()
        transformer.is_available.return_value = True
        transformer.transform.return_value = (123.0, 456.0)
        service = _make_service(
            transformer=None,
            transformer_getter=lambda: transformer,
        )

        result = service._transform_single_pixel_to_robot(
            10.0,
            20.0,
            {"spraying_height": "5", "rz_angle": "7"},
        )

        self.assertEqual((123.0, 456.0), result)
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

    def test_transform_single_pixel_to_robot_uses_live_resolver_getter(self):
        registry = MagicMock()
        registry.by_name.return_value = SimpleNamespace(offset_x=0.0, offset_y=0.0)
        resolver = MagicMock()
        resolver.registry = registry
        resolver.resolve.return_value = SimpleNamespace(final_xy=(401.0, 402.0))
        service = _make_service(
            resolver=None,
            resolver_getter=lambda: resolver,
            target_point_name="tool",
        )

        result = service._transform_single_pixel_to_robot(
            10.0,
            20.0,
            {"height_mm": 12.0, "spraying_height": "5", "rz_angle": "7"},
            target_point_name="pickup",
            frame_name="paint_frame",
            rz_override=33.0,
        )

        self.assertEqual((401.0, 402.0), result)
        registry.by_name.assert_called_once_with("pickup")
        self.assertEqual("paint_frame", resolver.resolve.call_args.kwargs["frame"])

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
                [100.0, 200.0, 105.0, 0.0, 0.0, 45.0],
                [110.0, 210.0, 105.0, 0.0, 0.0, 50.0],
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
                [1.0, 2.0, 301.0, 0.0, 0.0, 7.0],
                [3.0, 4.0, 302.0, 0.0, 0.0, 7.0],
            ],
            result,
        )
        first_request = resolver.resolve.call_args_list[0].args[0]
        self.assertEqual(10.0, first_request.x_pixels)
        self.assertEqual(20.0, first_request.y_pixels)
        self.assertEqual(105.0, first_request.z_mm)
        registry.by_name.assert_called_once_with("tool")

    def test_transform_to_robot_homography_residual_mode_skips_geometry_ppm(self):
        registry = MagicMock()
        registry.by_name.return_value = SimpleNamespace(offset_x=0.0, offset_y=0.0)
        resolver = MagicMock()
        resolver.registry = registry
        resolver.resolve.side_effect = [
            SimpleNamespace(final_xy=(101.0, 201.0), z=301.0),
            SimpleNamespace(final_xy=(102.0, 202.0), z=302.0),
        ]
        service = _make_service(
            resolver=resolver,
            target_point_name="tool",
            calibration_frame_name="paint_frame",
            pixel_to_mm_mode=PIXEL_TO_MM_MODE_HOMOGRAPHY_RESIDUAL,
        )

        with patch.object(service._geometry_ppm_strategy, "convert") as geometry_ppm:
            result = service._transform_to_robot(
                [[10.0, 20.0], [30.0, 40.0]],
                {"spraying_height": "5", "rz_angle": "7"},
            )

        self.assertEqual(
            [
                [101.0, 201.0, 301.0, 0.0, 0.0, 7.0],
                [102.0, 202.0, 302.0, 0.0, 0.0, 7.0],
            ],
            result,
        )
        geometry_ppm.assert_not_called()
        self.assertEqual("paint_frame", resolver.resolve.call_args_list[0].kwargs["frame"])
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

    def test_extract_pickup_pixel_accepts_nested_contour_payload(self):
        service = _make_service()

        result = service._extract_pickup_pixel(
            {
                "contour": {"contour": [[0, 0], [10, 0], [10, 10], [0, 10]]},
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

    def test_stable_paint_segment_pickup_rz_prefers_straight_low_rotation_segment(self):
        path = [
            [0.0, 0.0, 0.0, 180.0, 0.0, 0.0],
            [-10.0, 0.5, 0.0, 180.0, 0.0, 0.0],
            [-20.0, 1.0, 0.0, 180.0, 0.0, 0.0],
            [-30.0, 1.6, 0.0, 180.0, 0.0, 0.0],
            [-31.0, 8.0, 0.0, 180.0, 0.0, 0.0],
            [-28.0, 16.0, 0.0, 180.0, 0.0, 0.0],
            [-20.0, 20.0, 0.0, 180.0, 0.0, 0.0],
        ]

        pickup_rz = compute_pickup_rz_from_stable_paint_segment(path, reference_rz=0.0)

        self.assertAlmostEqual(-2.862, pickup_rz, places=3)

    def test_initial_paint_segment_pickup_rz_uses_first_directed_run(self):
        path = [
            [0.0, 0.0, 0.0, 180.0, 0.0, 0.0],
            [10.0, 1.763, 0.0, 180.0, 0.0, 0.0],
            [20.0, 3.527, 0.0, 180.0, 0.0, 0.0],
            [25.0, 20.0, 0.0, 180.0, 0.0, 0.0],
            [35.0, 20.0, 0.0, 180.0, 0.0, 0.0],
        ]

        pickup_rz = compute_pickup_rz_from_initial_paint_segment(path, reference_rz=0.0)

        self.assertAlmostEqual(10.0, pickup_rz, places=2)

    def test_initial_paint_segment_pickup_rz_preserves_reverse_direction(self):
        path = [
            [0.0, 0.0, 0.0, 180.0, 0.0, 0.0],
            [-10.0, 0.0, 0.0, 180.0, 0.0, 0.0],
            [-20.0, 0.0, 0.0, 180.0, 0.0, 0.0],
        ]

        pickup_rz = compute_pickup_rz_from_initial_paint_segment(path, reference_rz=0.0)

        self.assertAlmostEqual(180.0, pickup_rz, places=6)

    def test_min_rect_long_axis_pickup_rz_ignores_contour_direction(self):
        contour = [
            [100.0, 10.0],
            [0.0, 10.0],
            [0.0, 0.0],
            [100.0, 0.0],
        ]

        pickup_rz = compute_pickup_rz_from_min_rect_long_axis(contour, reference_rz=0.0)

        self.assertAlmostEqual(0.0, pickup_rz, places=6)

    def test_min_rect_long_axis_pickup_rz_uses_long_side(self):
        contour = [
            [0.0, 0.0],
            [10.0, 0.0],
            [10.0, 100.0],
            [0.0, 100.0],
        ]

        pickup_rz = compute_pickup_rz_from_min_rect_long_axis(contour, reference_rz=0.0)

        self.assertAlmostEqual(90.0, abs(pickup_rz), places=6)


if __name__ == "__main__":
    unittest.main()
