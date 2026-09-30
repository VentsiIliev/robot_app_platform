import unittest

import numpy as np

from src.robot_systems.paint.processes.paint.config import PaintSimulationConfig
from src.robot_systems.paint.processes.paint.execute.paint_contact_executor import (
    _apply_non_paint_clearance,
)
from src.robot_systems.paint.processes.paint.plan.paint_contact_motion.source_plan import (
    _trim_and_profile_selected_interval,
)
from src.robot_systems.paint.processes.paint.plan.paint_contact_motion.core import (
    _orient_open_source_path_for_contact_side,
)


class TestPaintContactSelectionExecution(unittest.TestCase):
    def test_open_selection_reverses_when_needed_to_keep_configured_paint_side(self):
        path, reversed_path = _orient_open_source_path_for_contact_side(
            np.asarray([[0.0, 0.0], [1.0, 0.0], [2.0, -1.0]]),
            pivot_xy=(0.0, 0.0),
            side_reference_heading=0.0,
            contact_segment_heading=0.0,
            side_sign=1.0,
        )

        self.assertTrue(reversed_path)
        np.testing.assert_array_equal(
            path,
            np.asarray([[2.0, -1.0], [1.0, 0.0], [0.0, 0.0]]),
        )

    def test_selection_trims_tail_and_retracts_internal_gap(self):
        source = [[float(x), 0.0, 0.0, 0.0, 0.0, 0.0] for x in range(21)]
        selections = [
            [[2.0, 0.0], [5.0, 0.0]],
            [[12.0, 0.0], [15.0, 0.0]],
        ]

        trimmed, profile = _trim_and_profile_selected_interval(source, selections)

        self.assertEqual(trimmed[0][0], 0.0)  # 2 mm matching tolerance
        self.assertEqual(trimmed[-1][0], 17.0)
        self.assertEqual(profile[2], 0.0)
        self.assertEqual(profile[15], 0.0)
        self.assertGreater(profile[8], 0.0)
        self.assertLessEqual(max(profile), 5.0)

    def test_prepared_cut_ignores_duplicate_closing_point(self):
        source = [
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [2.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [10.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ]

        trimmed, profile = _trim_and_profile_selected_interval(
            source,
            [[[0.0, 0.0], [2.0, 0.0]]],
            cut_moved_outside_selection=True,
        )

        self.assertEqual([pose[0] for pose in trimmed], [0.0, 1.0, 2.0])
        self.assertEqual(profile, [0.0, 0.0, 0.0])

    def test_clearance_offsets_only_non_contact_pose_along_paint_axis(self):
        config = PaintSimulationConfig(
            motion_plane="xy_z_rz",
            translation_axis="x",
            paint_side="negative",
            translation_direction="forward",
        )
        path = [
            [100.0, 20.0, 30.0, 0.0, 0.0, 0.0],
            [100.0, 20.0, 30.0, 0.0, 0.0, 0.0],
            [100.0, 20.0, 30.0, 0.0, 0.0, 0.0],
        ]
        diagnostics = [
            {"source_index": 0.0},
            {"source_index": 1.0},
            {"source_index": 2.0},
        ]

        result = _apply_non_paint_clearance(path, diagnostics, [0.0, 5.0, 0.0], config)

        self.assertEqual(result[0][0], 100.0)
        self.assertEqual(result[1][0], 95.0)
        self.assertEqual(result[2][0], 100.0)
        self.assertTrue(all(pose[1:] == path[index][1:] for index, pose in enumerate(result)))


if __name__ == "__main__":
    unittest.main()
