import os
import tempfile
import unittest
from unittest.mock import MagicMock

import ezdxf
import numpy as np

from src.engine.cad import (
    DxfContourExporter,
    DxfContourExportOptions,
    export_contours_to_dxf,
    parse_dxf_to_geometry,
)
from src.engine.vision.i_capture_snapshot_service import VisionCaptureSnapshot


def _rect(x=0.0, y=0.0, w=10.0, h=5.0):
    return np.asarray(
        [
            [[x, y]],
            [[x + w, y]],
            [[x + w, y + h]],
            [[x, y + h]],
        ],
        dtype=np.float32,
    )


def _jagged_rect():
    return np.asarray(
        [
            [[0.0, 0.0]],
            [[4.0, 0.4]],
            [[8.0, -0.3]],
            [[12.0, 0.0]],
            [[12.3, 4.0]],
            [[12.0, 8.0]],
            [[8.0, 8.4]],
            [[4.0, 7.7]],
            [[0.0, 8.0]],
            [[-0.2, 4.0]],
        ],
        dtype=np.float32,
    )


class TestDxfContourExporter(unittest.TestCase):
    def test_export_contours_writes_autocad_compatible_closed_lwpolyline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "outer_contour.dxf")

            result = export_contours_to_dxf(
                [_rect()],
                path,
                options=DxfContourExportOptions(image_coordinates=False),
            )

            self.assertEqual(result.exported_count, 1)
            self.assertEqual(result.skipped_count, 0)
            self.assertTrue(os.path.exists(path))

            doc = ezdxf.readfile(path)
            self.assertEqual(doc.dxfversion, "AC1024")
            self.assertEqual(doc.header["$INSUNITS"], 4)
            entities = list(doc.modelspace())
            self.assertEqual(len(entities), 1)
            self.assertEqual(entities[0].dxftype(), "LWPOLYLINE")
            self.assertTrue(entities[0].closed)
            self.assertEqual(entities[0].dxf.layer, "OUTER_CONTOURS")

    def test_exported_dxf_round_trips_through_existing_geometry_parser(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "round_trip.dxf")
            export_contours_to_dxf(
                [_rect(w=30.0, h=20.0)],
                path,
                options=DxfContourExportOptions(image_coordinates=False),
            )

            geometry = parse_dxf_to_geometry(path)

            self.assertEqual(len(geometry.closed_paths), 1)
            self.assertGreaterEqual(len(geometry.largest_closed_path()), 4)

    def test_export_can_write_legacy_r12_polyline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "legacy_r12.dxf")
            export_contours_to_dxf(
                [_rect(w=30.0, h=20.0)],
                path,
                options=DxfContourExportOptions(dxf_version="R12", image_coordinates=False),
            )

            doc = ezdxf.readfile(path)
            entities = list(doc.modelspace())

            self.assertEqual(doc.dxfversion, "AC1009")
            self.assertEqual(entities[0].dxftype(), "POLYLINE")
            self.assertTrue(entities[0].is_closed)

    def test_export_latest_uses_snapshot_service_contours_and_frame_height(self):
        snapshot_service = MagicMock()
        snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame=np.zeros((100, 200, 3), dtype=np.uint8),
            contours=[_rect(y=10.0, h=20.0)],
            source="test",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "snapshot.dxf")
            result = DxfContourExporter(snapshot_service).export_latest(path, source="unit_test")

            self.assertEqual(result.exported_count, 1)
            snapshot_service.capture_snapshot.assert_called_once_with(source="unit_test")
            self.assertEqual(result.bounds, (0.0, 70.0, 10.0, 90.0))

    def test_largest_only_exports_only_largest_contour(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "largest.dxf")

            result = export_contours_to_dxf(
                [_rect(w=2.0, h=2.0), _rect(w=20.0, h=10.0)],
                path,
                options=DxfContourExportOptions(image_coordinates=False, largest_only=True),
            )

            self.assertEqual(result.exported_count, 1)
            self.assertEqual(result.skipped_count, 1)
            entities = list(ezdxf.readfile(path).modelspace())
            points = list(entities[0].get_points("xy"))
            self.assertEqual(len(points), 4)

    def test_filters_degenerate_and_small_contours(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "filtered.dxf")

            result = export_contours_to_dxf(
                [
                    np.asarray([[[0.0, 0.0]], [[1.0, 0.0]]], dtype=np.float32),
                    _rect(w=1.0, h=1.0),
                    _rect(w=10.0, h=10.0),
                ],
                path,
                options=DxfContourExportOptions(image_coordinates=False, min_area=5.0),
            )

            self.assertEqual(result.exported_count, 1)
            self.assertEqual(result.skipped_count, 2)

    def test_chaikin_postprocessing_smooths_by_adding_vertices(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "chaikin.dxf")

            result = export_contours_to_dxf(
                [_jagged_rect()],
                path,
                options=DxfContourExportOptions(
                    image_coordinates=False,
                    postprocess_mode="chaikin",
                    smooth_iterations=1,
                ),
            )

            self.assertEqual(result.exported_count, 1)
            points = list(ezdxf.readfile(path).modelspace()[0].get_points("xy"))
            self.assertEqual(len(points), 20)

    def test_moving_average_postprocessing_preserves_vertex_count(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "moving_average.dxf")

            export_contours_to_dxf(
                [_jagged_rect()],
                path,
                options=DxfContourExportOptions(
                    image_coordinates=False,
                    postprocess_mode="moving_average",
                    smooth_window=3,
                    smooth_iterations=1,
                ),
            )

            points = list(ezdxf.readfile(path).modelspace()[0].get_points("xy"))
            self.assertEqual(len(points), 10)
            self.assertNotEqual(points[0], (0.0, 0.0))

    def test_smooth_then_simplify_can_reduce_exported_vertices(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "smooth_simplify.dxf")

            export_contours_to_dxf(
                [_jagged_rect()],
                path,
                options=DxfContourExportOptions(
                    image_coordinates=False,
                    postprocess_mode="moving_average_simplify",
                    smooth_window=3,
                    smooth_iterations=1,
                    simplify_tolerance=2.0,
                ),
            )

            points = list(ezdxf.readfile(path).modelspace()[0].get_points("xy"))
            self.assertLess(len(points), 10)


if __name__ == "__main__":
    unittest.main()
