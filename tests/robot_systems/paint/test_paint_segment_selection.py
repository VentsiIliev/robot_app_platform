import unittest
from unittest.mock import MagicMock

from PyQt6.QtCore import QPointF

from contour_editor.models.segment import Layer, Segment
from src.robot_systems.paint.domain.paint_segment_selection import (
    OPEN_PATH_SETTING,
    SELECTION_SOURCE_SETTING,
    _contiguous_runs,
    apply_selected_paint_segments,
)


class _LayerConfig:
    @staticmethod
    def name_for_role(role: str) -> str:
        return {"workpiece": "Workpiece", "contour": "Paint"}[role]


class TestPaintSegmentSelection(unittest.TestCase):
    def test_contiguous_runs_split_disconnected_rectangle_hits(self):
        self.assertEqual(_contiguous_runs({1, 2, 3, 7, 8}), [[1, 2, 3], [7, 8]])

    def test_apply_replaces_paint_outline_and_preserves_matching_contour(self):
        matching = self._segment("Workpiece", range(8))
        paint = self._segment(
            "Paint",
            range(8),
            settings={"velocity": 12, SELECTION_SOURCE_SETTING: True},
        )
        manager = MagicMock()
        manager.layer_config = _LayerConfig()
        manager.segments = [matching, paint]
        manager.get_segments.return_value = manager.segments

        def create_segment(points, layer_name):
            result = Segment(layer=Layer(layer_name))
            for point in points:
                result.add_point(QPointF(point))
            return result

        manager.create_segment.side_effect = create_segment
        editor = MagicMock()
        editor.manager = manager
        editor.selection_manager.selected_points_list = [
            # Simulate the overlap selecting the same orange Workpiece points;
            # the initial cyan Paint source must win without duplicates.
            *(
                {"role": "anchor", "seg_index": 0, "point_index": index}
                for index in (1, 2, 3, 6, 7)
            ),
            *(
                {"role": "anchor", "seg_index": 1, "point_index": index}
                for index in (1, 2, 3, 6, 7)
            ),
        ]

        ok, _ = apply_selected_paint_segments(editor)

        self.assertTrue(ok)
        self.assertIs(manager.segments[0], matching)
        self.assertEqual(len(manager.segments), 3)
        self.assertEqual(
            [[point.x() for point in segment.points] for segment in manager.segments[1:]],
            [[1.0, 2.0, 3.0], [6.0, 7.0]],
        )
        self.assertTrue(all(segment.settings[OPEN_PATH_SETTING] is False for segment in manager.segments[1:]))
        self.assertTrue(all(SELECTION_SOURCE_SETTING not in segment.settings for segment in manager.segments[1:]))
        editor.selection_manager.clear_all_selections.assert_called_once_with()
        manager.save_state.assert_called_once_with()

    def test_apply_rejects_isolated_selected_points_without_mutating(self):
        paint = self._segment("Workpiece", range(5))
        manager = MagicMock()
        manager.layer_config = _LayerConfig()
        manager.segments = [paint]
        manager.get_segments.return_value = manager.segments
        editor = MagicMock()
        editor.manager = manager
        editor.selection_manager.selected_points_list = [
            {"role": "anchor", "seg_index": 0, "point_index": 1},
            {"role": "anchor", "seg_index": 0, "point_index": 3},
        ]

        ok, _ = apply_selected_paint_segments(editor)

        self.assertFalse(ok)
        self.assertEqual(manager.segments, [paint])
        manager.save_state.assert_not_called()

    def test_apply_merges_closed_seam_selection_without_rotating_main_contour(self):
        matching = self._segment("Workpiece", range(8))
        paint = self._segment(
            "Paint",
            range(8),
            settings={SELECTION_SOURCE_SETTING: True},
        )
        manager = MagicMock()
        manager.layer_config = _LayerConfig()
        manager.segments = [matching, paint]
        manager.get_segments.return_value = manager.segments

        def create_segment(points, layer_name):
            result = Segment(layer=Layer(layer_name))
            for point in points:
                result.add_point(QPointF(point))
            return result

        manager.create_segment.side_effect = create_segment
        editor = MagicMock()
        editor.manager = manager
        editor.selection_manager.selected_points_list = [
            {"role": "anchor", "seg_index": 1, "point_index": index}
            for index in (0, 1, 6, 7)
        ]

        ok, _ = apply_selected_paint_segments(editor)

        self.assertTrue(ok)
        self.assertEqual(
            [point.x() for point in matching.points],
            [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
        )
        self.assertEqual(len(manager.segments), 2)
        self.assertEqual(
            [point.x() for point in manager.segments[1].points],
            [6.0, 7.0, 0.0, 1.0],
        )

    @staticmethod
    def _segment(layer_name, xs, settings=None):
        segment = Segment(layer=Layer(layer_name), settings=settings)
        for x in xs:
            segment.add_point(QPointF(float(x), 0.0))
        return segment


if __name__ == "__main__":
    unittest.main()
