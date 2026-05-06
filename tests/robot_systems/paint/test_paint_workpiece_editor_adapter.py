import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from src.applications.workpiece_editor.editor_core.adapters.adapter_utils import (
    contour_layer_name,
    fill_layer_name,
    normalize_layer_data,
    workpiece_layer_name,
)
from src.robot_systems.paint.domain.paint_workpiece_editor_adapter import PaintWorkpieceEditorAdapter
from contour_editor.persistence.data.editor_data_model import ContourEditorData


class TestPaintWorkpieceEditorAdapter(unittest.TestCase):

    def setUp(self):
        self.adapter = PaintWorkpieceEditorAdapter()

    def test_from_workpiece_maps_main_contour_and_spray_pattern_layers(self):
        workpiece = MagicMock()
        workpiece.get_main_contour.return_value = np.array([[1, 2], [3, 4]], dtype=np.float32)
        workpiece.get_main_contour_settings.return_value = {"velocity": 5}
        workpiece.get_spray_pattern_contours.return_value = [
            {"contour": np.array([[5, 6], [7, 8]], dtype=np.float32), "settings": {"offset": 1}},
        ]
        workpiece.get_spray_pattern_fills.return_value = [
            {"contour": np.array([[9, 10], [11, 12]], dtype=np.float32), "settings": {"offset": 2}},
        ]

        editor_data = self.adapter.from_workpiece(workpiece)

        main_layer = editor_data.get_layer(workpiece_layer_name())
        contour_layer = editor_data.get_layer(contour_layer_name())
        fill_layer = editor_data.get_layer(fill_layer_name())
        self.assertEqual(len(main_layer.segments), 1)
        self.assertEqual(main_layer.segments[0].settings["velocity"], 5)
        self.assertEqual(len(contour_layer.segments), 1)
        self.assertEqual(contour_layer.segments[0].settings["offset"], 1)
        self.assertEqual(len(fill_layer.segments), 1)
        self.assertEqual(fill_layer.segments[0].settings["offset"], 2)

    def test_to_workpiece_data_preserves_main_settings_and_process_defaults(self):
        editor_data = ContourEditorData.from_legacy_format(
            normalize_layer_data(
                {
                    workpiece_layer_name(): [
                        {"contour": np.array([[1, 2], [3, 4]], dtype=np.float32), "settings": {"velocity": 7, "offset": None}},
                    ],
                    contour_layer_name(): [
                        {"contour": np.array([[5, 6], [7, 8]], dtype=np.float32), "settings": {"rz_angle": 15}},
                    ],
                    fill_layer_name(): [
                        {"contour": np.array([[9, 10], [11, 12]], dtype=np.float32), "settings": {}},
                    ],
                }
            )
        )

        result = self.adapter.to_workpiece_data(
            editor_data,
            default_settings={"velocity": 10, "acceleration": 20},
        )

        self.assertEqual(result["contour"].shape, (2, 1, 2))
        self.assertEqual(result["velocity"], 7)
        self.assertNotIn("offset", result)
        self.assertEqual(len(result["sprayPattern"]["Contour"]), 1)
        self.assertEqual(result["sprayPattern"]["Contour"][0]["settings"]["velocity"], 10)
        self.assertEqual(result["sprayPattern"]["Contour"][0]["settings"]["acceleration"], 20)
        self.assertEqual(result["sprayPattern"]["Contour"][0]["settings"]["rz_angle"], 15)
        self.assertEqual(len(result["sprayPattern"]["Fill"]), 1)
        self.assertEqual(result["sprayPattern"]["Fill"][0]["settings"], {"velocity": 10, "acceleration": 20})

    def test_to_workpiece_data_uses_legacy_layer_fallbacks_and_empty_main_contour(self):
        editor_data = ContourEditorData.from_legacy_format(
            normalize_layer_data(
                {
                    "Workpiece": [],
                    "Contour": [{"contour": np.array([[1, 1], [2, 2]], dtype=np.float32), "settings": {"velocity": 3}}],
                    "Fill": [{"contour": np.array([[3, 3], [4, 4]], dtype=np.float32), "settings": {"velocity": 4}}],
                }
            )
        )

        result = self.adapter.to_workpiece_data(editor_data)

        self.assertEqual(result["contour"], [])
        self.assertEqual(len(result["sprayPattern"]["Contour"]), 1)
        self.assertEqual(len(result["sprayPattern"]["Fill"]), 1)

    def test_from_raw_extracts_main_settings_and_process_layers(self):
        raw = {
            "contour": {"contour": [[1, 2], [3, 4]]},
            "velocity": 5,
            "acceleration": 6,
            "rz_angle": None,
            "sprayPattern": {
                "Contour": [{"contour": [[5, 6], [7, 8]], "settings": {"offset": 1}}],
                "Fill": [{"contour": [[9, 10], [11, 12]], "settings": {"offset": 2}}],
            },
        }

        editor_data = self.adapter.from_raw(raw)

        main_layer = editor_data.get_layer(workpiece_layer_name())
        self.assertEqual(main_layer.segments[0].settings, {"velocity": 5, "acceleration": 6})
        self.assertEqual(len(editor_data.get_layer(contour_layer_name()).segments), 1)
        self.assertEqual(len(editor_data.get_layer(fill_layer_name()).segments), 1)

    def test_print_summary_delegates_to_shared_helper(self):
        editor_data = ContourEditorData()

        with patch("src.robot_systems.paint.domain.paint_workpiece_editor_adapter.print_summary") as print_summary:
            self.adapter.print_summary(editor_data)

        print_summary.assert_called_once_with(editor_data)
