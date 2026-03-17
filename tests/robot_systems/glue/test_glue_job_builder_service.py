import unittest
import numpy as np
from unittest.mock import MagicMock

from src.robot_systems.glue.domain.workpieces.model.glue_workpiece import GlueWorkpiece
from src.robot_systems.glue.domain.glue_job_builder_service import (
    GlueJobBuildError,
    GlueJobBuilderService,
)


def _segment_settings(**overrides):
    values = {
        "glue_type": "Type A",
        "spray_width": "10",
        "spraying_height": "20",
        "forward_ramp_steps": "3",
        "initial_ramp_speed": "5000",
        "initial_ramp_speed_duration": "1.0",
        "motor_speed": "500",
        "reverse_duration": "0.5",
        "speed_reverse": "3000",
        "reverse_ramp_steps": "1",
        "velocity": "10",
        "acceleration": "10",
        "rz_angle": "0",
        "adaptive_spacing_mm": "10",
        "spline_density_multiplier": "2.0",
        "smoothing_lambda": "0.0",
        "time_between_generator_and_glue": "1",
        "generator_timeout": "5",
        "fan_speed": "100",
        "time_before_motion": "0.1",
        "time_before_stop": "1.0",
        "reach_start_threshold": "1.0",
        "reach_end_threshold": "30.0",
        "glue_speed_coefficient": "5",
        "glue_acceleration_coefficient": "0",
    }
    values.update(overrides)
    return values


def _raw_segment(points, settings=None):
    return {
        "contour": [[list(point)] for point in points],
        "settings": settings if settings is not None else _segment_settings(),
    }


def _workpiece(workpiece_id="111"):
    return {
        "workpieceId": workpiece_id,
        "name": workpiece_id,
        "sprayPattern": {
            "Contour": [
                _raw_segment([(1.0, 2.0), (3.0, 4.0)]),
                _raw_segment([(5.0, 6.0), (7.0, 8.0)], settings=_segment_settings(glue_type="Type B")),
            ],
            "Fill": [
                _raw_segment([(10.0, 11.0), (12.0, 13.0), (14.0, 15.0)]),
            ],
        },
    }


def _glue_workpiece(workpiece_id="111"):
    raw = _workpiece(workpiece_id)
    return GlueWorkpiece.from_dict(
        {
            "workpieceId": raw["workpieceId"],
            "name": raw["name"],
            "description": raw["name"],
            "height": "1",
            "glue_qty": "1",
            "gripperId": 1,
            "glueType": "Type A",
            "contour": {"contour": raw["sprayPattern"]["Contour"][0]["contour"], "settings": {}},
            "pickupPoint": None,
            "sprayPattern": raw["sprayPattern"],
        }
    )


class TestGlueJobBuilderService(unittest.TestCase):
    def _service(self):
        transformer = MagicMock()
        transformer.is_available.return_value = True
        transformer.transform.side_effect = lambda x, y: (x + 100.0, y + 200.0)
        return GlueJobBuilderService(transformer=transformer, z_min=50.0), transformer

    def test_build_job_extracts_segments_in_contour_then_fill_order(self):
        service, _ = self._service()

        job = service.build_job([_workpiece()])

        self.assertEqual(job.workpiece_count, 1)
        self.assertEqual(job.segment_count, 3)
        self.assertEqual([segment.pattern_type for segment in job.segments], ["Contour", "Contour", "Fill"])
        self.assertEqual([segment.segment_index for segment in job.segments], [0, 1, 0])

    def test_build_job_flattens_nested_contour_points(self):
        service, _ = self._service()

        job = service.build_job([_workpiece()])

        self.assertEqual(job.segments[0].points, [[101.0, 202.0, 70.0, 180.0, 0.0, 0.0], [103.0, 204.0, 70.0, 180.0, 0.0, 0.0]])
        self.assertEqual(job.segments[2].points, [[110.0, 211.0, 70.0, 180.0, 0.0, 0.0], [112.0, 213.0, 70.0, 180.0, 0.0, 0.0], [114.0, 215.0, 70.0, 180.0, 0.0, 0.0]])

    def test_build_job_preserves_segment_settings_and_metadata(self):
        service, _ = self._service()

        job = service.build_job([_workpiece("wp-22")])

        first = job.segments[0]
        second = job.segments[1]
        self.assertEqual(first.workpiece_id, "wp-22")
        self.assertEqual(first.settings["glue_type"], "Type A")
        self.assertEqual(second.settings["glue_type"], "Type B")

    def test_build_job_accepts_glue_workpiece_objects(self):
        service, _ = self._service()

        job = service.build_job([_glue_workpiece("wp-77")])

        self.assertEqual(job.segment_count, 3)
        self.assertEqual(job.segments[0].workpiece_id, "wp-77")
        self.assertEqual(job.segments[0].points, [[101.0, 202.0, 70.0, 180.0, 0.0, 0.0], [103.0, 204.0, 70.0, 180.0, 0.0, 0.0]])

    def test_to_process_paths_returns_glue_process_ready_tuples(self):
        service, _ = self._service()
        job = service.build_job([_workpiece("wp-88")])

        process_paths = service.to_process_paths(job)

        self.assertEqual(len(process_paths), 3)
        points, settings, metadata = process_paths[0]
        self.assertEqual(points, [[101.0, 202.0, 70.0, 180.0, 0.0, 0.0], [103.0, 204.0, 70.0, 180.0, 0.0, 0.0]])
        self.assertEqual(settings["glue_type"], "Type A")
        self.assertEqual(metadata["workpiece_id"], "wp-88")
        self.assertEqual(metadata["pattern_type"], "Contour")
        self.assertEqual(metadata["segment_index"], 0)

    def test_build_job_raises_when_segment_settings_are_missing(self):
        service, _ = self._service()
        workpiece = _workpiece()
        workpiece["sprayPattern"]["Contour"][0]["settings"] = {}

        with self.assertRaises(GlueJobBuildError):
            service.build_job([workpiece])

    def test_build_job_raises_when_segment_has_no_points(self):
        service, _ = self._service()
        workpiece = _workpiece()
        workpiece["sprayPattern"]["Fill"][0]["contour"] = []

        with self.assertRaises(GlueJobBuildError):
            service.build_job([workpiece])

    def test_build_job_accepts_numpy_array_contours(self):
        service, _ = self._service()
        workpiece = _workpiece()
        workpiece["sprayPattern"]["Contour"][0]["contour"] = np.array(
            [[[[1.0, 2.0]]], [[[3.0, 4.0]]]],
            dtype=np.float32,
        )

        job = service.build_job([workpiece])

        self.assertEqual(job.segments[0].points, [[101.0, 202.0, 70.0, 180.0, 0.0, 0.0], [103.0, 204.0, 70.0, 180.0, 0.0, 0.0]])

    def test_build_job_raises_when_transformer_is_unavailable(self):
        transformer = MagicMock()
        transformer.is_available.return_value = False
        service = GlueJobBuilderService(transformer=transformer, z_min=50.0)

        with self.assertRaises(GlueJobBuildError):
            service.build_job([_workpiece()])

    def test_build_job_uses_rz_from_segment_settings(self):
        service, _ = self._service()
        workpiece = _workpiece()
        workpiece["sprayPattern"]["Contour"][0]["settings"]["rz_angle"] = "45"

        job = service.build_job([workpiece])

        self.assertEqual(job.segments[0].points[0], [101.0, 202.0, 70.0, 180.0, 0.0, 45.0])


if __name__ == "__main__":
    unittest.main()
