import unittest
from unittest.mock import patch

import numpy as np

from src.robot_systems.paint.processes.paint.workpiece_preparation_service import (
    PaintWorkpiecePreparationService,
    contour_to_workpiece_raw,
)


def _square(size: float) -> np.ndarray:
    return np.array(
        [[[0.0, 0.0]], [[size, 0.0]], [[size, size]], [[0.0, size]]],
        dtype=np.float32,
    )


def _matched_payload():
    return {
        "workpieceId": "saved-1",
        "name": "Saved Workpiece",
        "raw": {
            "workpieceId": "saved-1",
            "name": "Saved Workpiece",
            "contour": {"contour": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]},
            "sprayPattern": {"Contour": [], "Fill": []},
            "pickupPoint": [1.0, 2.0],
        },
    }


class TestContourToWorkpieceRaw(unittest.TestCase):

    def test_wraps_captured_contour_into_workpiece_payload(self):
        contour = _square(2.0)

        raw = contour_to_workpiece_raw(contour, workpiece_id="cap-1", name="Captured", height_mm=3.5)

        self.assertEqual(raw["workpieceId"], "cap-1")
        self.assertEqual(raw["name"], "Captured")
        self.assertEqual(raw["height_mm"], 3.5)
        self.assertEqual(len(raw["contour"]), 4)
        self.assertEqual(raw["sprayPattern"], {"Contour": [], "Fill": []})


class TestPaintWorkpiecePreparationService(unittest.TestCase):

    def test_prepare_workpiece_falls_back_to_captured_contour_when_matching_unavailable(self):
        service = PaintWorkpiecePreparationService(
            can_match_fn=lambda: False,
            match_workpiece_fn=lambda contour: (False, None, "unused"),
        )
        contour = _square(2.0)

        raw, description = service.prepare_workpiece(contour, frame=None)

        self.assertEqual(description, "Executed captured contour")
        self.assertEqual(raw["workpieceId"], "captured")
        self.assertEqual(raw["name"], "Captured contour")

    def test_prepare_workpiece_falls_back_when_match_returns_no_payload(self):
        service = PaintWorkpiecePreparationService(
            can_match_fn=lambda: True,
            match_workpiece_fn=lambda contour: (False, None, "no match"),
        )

        raw, description = service.prepare_workpiece(_square(2.0), frame=None)

        self.assertEqual(description, "Executed captured contour")
        self.assertEqual(raw["workpieceId"], "captured")

    def test_prepare_workpiece_uses_matched_contour_branch(self):
        payload = _matched_payload()
        service = PaintWorkpiecePreparationService(
            can_match_fn=lambda: True,
            match_workpiece_fn=lambda contour: (True, payload, "matched"),
        )
        contour = _square(3.0)
        aligned = {"workpieceId": "saved-1", "name": "Aligned", "sprayPattern": {"Contour": [], "Fill": []}}

        with patch(
            "src.robot_systems.paint.processes.paint.workpiece_preparation_service.align_raw_workpiece_to_contour",
            return_value=aligned,
        ) as align:
            raw, description = service.prepare_workpiece(contour, frame=None)

        self.assertIs(raw, aligned)
        self.assertEqual(description, "Executed saved-1")
        align.assert_called_once()
        self.assertEqual(align.call_args.kwargs["strategy"], service._dxf_alignment_strategy)
        self.assertEqual(align.call_args.kwargs["max_scale_deviation"], 0.0)
        self.assertEqual(align.call_args.kwargs["reference_scale_override"], 1.0)

    def test_prepare_workpiece_uses_dxf_branch_and_preserves_metadata(self):
        payload = _matched_payload()
        payload["raw"]["dxfPath"] = "/tmp/workpiece.dxf"
        payload["raw"]["custom"] = {"a": 1}
        service = PaintWorkpiecePreparationService(
            can_match_fn=lambda: True,
            match_workpiece_fn=lambda contour: (True, payload, "matched"),
            transformer=object(),
        )
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        contour = _square(4.0)
        placed = {"contour": {"contour": [[0.0, 0.0], [1.0, 1.0]]}, "sprayPattern": {"Contour": [], "Fill": []}}
        aligned = {"workpieceId": "aligned", "contour": {"contour": [[1.0, 1.0]]}, "sprayPattern": {"Contour": [], "Fill": []}}

        with (
            patch(
                "src.robot_systems.paint.processes.paint.workpiece_preparation_service.import_dxf_to_workpiece_data",
                return_value={"dxf": True},
            ) as import_dxf,
            patch(
                "src.robot_systems.paint.processes.paint.workpiece_preparation_service.map_raw_workpiece_mm_to_image",
                return_value=placed,
            ) as place,
            patch(
                "src.robot_systems.paint.processes.paint.workpiece_preparation_service.align_raw_workpiece_to_contour",
                return_value=aligned,
            ) as align,
        ):
            raw, description = service.prepare_workpiece(contour, frame=frame)

        self.assertEqual(description, "Executed saved-1")
        self.assertIs(raw, aligned)
        self.assertEqual(raw["dxfPath"], "/tmp/workpiece.dxf")
        self.assertEqual(raw["custom"], {"a": 1})
        import_dxf.assert_called_once_with("/tmp/workpiece.dxf")
        place.assert_called_once_with({"dxf": True}, 640.0, 480.0, service._transformer)
        align.assert_called_once_with(
            placed,
            contour,
            strategy=service._dxf_alignment_strategy,
            max_scale_deviation=service._dxf_max_scale_deviation,
        )

    def test_prepare_workpiece_returns_captured_contour_when_matched_raw_empty(self):
        service = PaintWorkpiecePreparationService(
            can_match_fn=lambda: True,
            match_workpiece_fn=lambda contour: (True, {"workpieceId": "saved", "raw": {}}, "matched"),
        )

        raw, description = service.prepare_workpiece(_square(2.0), frame=None)

        self.assertEqual(description, "Executed captured contour")
        self.assertEqual(raw["workpieceId"], "captured")

    def test_resolve_frame_size_uses_defaults_for_missing_shape(self):
        class _BadFrame:
            shape = "invalid"

        height, width = PaintWorkpiecePreparationService._resolve_frame_size(_BadFrame())

        self.assertEqual((height, width), (720.0, 1280.0))


if __name__ == "__main__":
    unittest.main()
