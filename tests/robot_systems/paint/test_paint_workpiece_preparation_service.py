import unittest

import numpy as np

from src.robot_systems.paint.processes.paint.plan.workpiece_preparation_service import (
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

    def test_wraps_captured_contour_with_default_segment_settings(self):
        contour = _square(2.0)

        raw = contour_to_workpiece_raw(
            contour,
            height_mm=3.5,
            default_settings={"velocity": "10", "acceleration": "10", "height_mm": "99"},
        )

        self.assertEqual(raw["velocity"], "10")
        self.assertEqual(raw["acceleration"], "10")
        self.assertEqual(raw["height_mm"], 3.5)


class TestPaintWorkpiecePreparationService(unittest.TestCase):

    def test_prepare_workpiece_skips_matching_when_disabled(self):
        matching_calls = []
        service = PaintWorkpiecePreparationService(
            can_match_fn=lambda: True,
            match_workpiece_fn=lambda contour: matching_calls.append(contour),
            default_settings={"velocity": "10"},
        )

        raw, description = service.prepare_workpiece(
            _square(2.0),
            frame=None,
            enable_matching=False,
        )

        self.assertEqual(matching_calls, [])
        self.assertEqual(description, "Executed captured contour")
        self.assertEqual(raw["workpieceId"], "captured")
        self.assertEqual(raw["velocity"], "10")

    def test_disabled_matching_uses_live_default_motion_settings(self):
        defaults = {"velocity": 25.0, "acceleration": 35.0, "offset": -4.5}
        service = PaintWorkpiecePreparationService(
            can_match_fn=lambda: True,
            match_workpiece_fn=lambda _contour: None,
            default_settings={"velocity": 10.0, "acceleration": 10.0},
            default_settings_getter=lambda: defaults,
        )

        raw, _description = service.prepare_workpiece(
            _square(2.0),
            frame=None,
            enable_matching=False,
        )

        self.assertEqual(25.0, raw["velocity"])
        self.assertEqual(35.0, raw["acceleration"])
        self.assertEqual(-4.5, raw["offset"])

    def test_matched_workpiece_keeps_its_own_motion_settings(self):
        payload = _matched_payload()
        payload["raw"]["velocity"] = 91.0
        payload["raw"]["acceleration"] = 42.0
        payload["raw"]["offset"] = 7.5
        service = PaintWorkpiecePreparationService(
            can_match_fn=lambda: True,
            match_workpiece_fn=lambda _contour: (True, payload, "matched"),
            default_settings_getter=lambda: {
                "velocity": 25.0,
                "acceleration": 35.0,
                "offset": -4.5,
            },
        )

        raw, _description = service.prepare_workpiece(_square(2.0), frame=None)

        self.assertEqual(91.0, raw["velocity"])
        self.assertEqual(42.0, raw["acceleration"])
        self.assertEqual(7.5, raw["offset"])

    def test_prepare_workpiece_falls_back_to_captured_contour_when_matching_unavailable(self):
        service = PaintWorkpiecePreparationService(
            can_match_fn=lambda: False,
            match_workpiece_fn=lambda contour: (False, None, "unused"),
            default_settings={"velocity": "10", "acceleration": "10"},
        )
        contour = _square(2.0)

        raw, description = service.prepare_workpiece(contour, frame=None)

        self.assertEqual(description, "Executed captured contour")
        self.assertEqual(raw["workpieceId"], "captured")
        self.assertEqual(raw["name"], "Captured contour")
        self.assertEqual(raw["velocity"], "10")
        self.assertEqual(raw["acceleration"], "10")

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

        raw, description = service.prepare_workpiece(_square(3.0), frame=None)

        self.assertEqual(raw["workpieceId"], "saved-1")
        self.assertEqual(raw["name"], "Saved Workpiece")
        self.assertEqual(raw["contour"], {"contour": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]})
        self.assertEqual(description, "Executed saved-1")

    def test_prepare_workpiece_falls_back_when_matched_raw_has_no_contour(self):
        payload = _matched_payload()
        payload["raw"].pop("contour")
        service = PaintWorkpiecePreparationService(
            can_match_fn=lambda: True,
            match_workpiece_fn=lambda contour: (True, payload, "matched"),
        )

        raw, description = service.prepare_workpiece(_square(4.0), frame=None)

        self.assertEqual(description, "Executed captured contour")
        self.assertEqual(raw["workpieceId"], "captured")

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
