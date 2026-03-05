import sys
import unittest
from unittest.mock import MagicMock

from src.engine.robot.configuration import MovementGroup
from src.applications.robot_settings.view.movement_groups_tab import (
    MovementGroupDef, MovementGroupType, MovementGroupsTab,
    MovementGroupWidget, PositionEditorDialog, MOVEMENT_GROUP_DEFINITIONS,
)


# ── No-Qt tests ───────────────────────────────────────────────────────────────

class TestPositionEditorDialogParse(unittest.TestCase):

    def test_valid_six_floats(self):
        self.assertEqual(
            PositionEditorDialog._parse("[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]"),
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        )

    def test_empty_string_returns_zeros(self):
        self.assertEqual(PositionEditorDialog._parse(""), [0.0] * 6)

    def test_invalid_string_returns_zeros(self):
        self.assertEqual(PositionEditorDialog._parse("not_a_list"), [0.0] * 6)

    def test_too_few_values_returns_zeros(self):
        self.assertEqual(PositionEditorDialog._parse("[1.0, 2.0, 3.0]"), [0.0] * 6)

    def test_too_many_values_returns_zeros(self):
        self.assertEqual(PositionEditorDialog._parse("[1,2,3,4,5,6,7]"), [0.0] * 6)

    def test_integer_values_parsed_as_float(self):
        result = PositionEditorDialog._parse("[0, 0, 300, 180, 0, 0]")
        self.assertEqual(result, [0.0, 0.0, 300.0, 180.0, 0.0, 0.0])


class TestMovementGroupsTabInferDef(unittest.TestCase):

    def test_pickup_in_name_gives_multi_position(self):
        defn = MovementGroupsTab._infer_def("SLOT 1 PICKUP", MovementGroup())
        self.assertEqual(defn.group_type, MovementGroupType.MULTI_POSITION)
        self.assertTrue(defn.has_trajectory_execution)

    def test_dropoff_in_name_gives_multi_position(self):
        defn = MovementGroupsTab._infer_def("SLOT 2 DROPOFF", MovementGroup())
        self.assertEqual(defn.group_type, MovementGroupType.MULTI_POSITION)

    def test_group_with_position_gives_single_position(self):
        group = MovementGroup(position="[0,0,0,0,0,0]")
        defn  = MovementGroupsTab._infer_def("HOME", group)
        self.assertEqual(defn.group_type, MovementGroupType.SINGLE_POSITION)

    def test_group_with_points_gives_multi_position(self):
        group = MovementGroup(points=["[0,0,0,0,0,0]"])
        defn  = MovementGroupsTab._infer_def("TRAJ", group)
        self.assertEqual(defn.group_type, MovementGroupType.MULTI_POSITION)

    def test_group_with_nothing_gives_velocity_only(self):
        defn = MovementGroupsTab._infer_def("JOG", MovementGroup())
        self.assertEqual(defn.group_type, MovementGroupType.VELOCITY_ONLY)

    def test_name_preserved(self):
        defn = MovementGroupsTab._infer_def("MY_GROUP", MovementGroup())
        self.assertEqual(defn.name, "MY_GROUP")


class TestMovementGroupDefinitions(unittest.TestCase):

    def test_home_pos_is_single_position(self):
        self.assertEqual(MOVEMENT_GROUP_DEFINITIONS["HOME_POS"].group_type, MovementGroupType.SINGLE_POSITION)

    def test_jog_is_velocity_only(self):
        self.assertEqual(MOVEMENT_GROUP_DEFINITIONS["JOG"].group_type, MovementGroupType.VELOCITY_ONLY)

    def test_nozzle_clean_has_iterations(self):
        self.assertTrue(MOVEMENT_GROUP_DEFINITIONS["NOZZLE CLEAN"].has_iterations)

    def test_tool_changer_has_trajectory_execution(self):
        self.assertTrue(MOVEMENT_GROUP_DEFINITIONS["TOOL CHANGER"].has_trajectory_execution)


# ── Qt-dependent tests ────────────────────────────────────────────────────────

class TestMovementGroupWidgetLoad(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def _single(self):
        return MovementGroupWidget(MovementGroupDef("HOME", MovementGroupType.SINGLE_POSITION))

    def _multi(self):
        return MovementGroupWidget(MovementGroupDef("TRAJ", MovementGroupType.MULTI_POSITION))

    def _multi_iter(self):
        return MovementGroupWidget(
            MovementGroupDef("CLEAN", MovementGroupType.MULTI_POSITION, has_iterations=True)
        )

    def test_load_sets_velocity(self):
        w = self._single()
        w.load(MovementGroup(velocity=75))
        self.assertEqual(int(w._velocity_spin.value()), 75)

    def test_load_sets_acceleration(self):
        w = self._single()
        w.load(MovementGroup(acceleration=50))
        self.assertEqual(int(w._acceleration_spin.value()), 50)

    def test_load_sets_position_display_for_single(self):
        w = self._single()
        w.load(MovementGroup(position="[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]"))
        self.assertEqual(w._position_display.text(), "[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]")

    def test_load_no_position_display_for_multi(self):
        w = self._multi()
        self.assertIsNone(w._position_display)

    def test_load_populates_points_list(self):
        w = self._multi()
        w.load(MovementGroup(points=["[0,0,0,0,0,0]", "[1,1,1,1,1,1]"]))
        self.assertEqual(w._points_list.count(), 2)

    def test_load_clears_previous_points(self):
        w = self._multi()
        w.load(MovementGroup(points=["[0,0,0,0,0,0]", "[1,1,1,1,1,1]"]))
        w.load(MovementGroup(points=["[9,9,9,9,9,9]"]))
        self.assertEqual(w._points_list.count(), 1)

    def test_load_sets_iterations(self):
        w = self._multi_iter()
        w.load(MovementGroup(iterations=5))
        self.assertEqual(int(w._iterations_spin.value()), 5)

    def test_load_does_not_emit_signals(self):
        w = self._single()
        received = []
        w.velocity_changed.connect(lambda n, v: received.append(v))
        w.load(MovementGroup(velocity=80))
        self.assertEqual(received, [])


class TestMovementGroupWidgetGetValues(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_get_values_velocity(self):
        w = MovementGroupWidget(MovementGroupDef("H", MovementGroupType.SINGLE_POSITION))
        w.load(MovementGroup(velocity=100))
        self.assertEqual(w.get_values().velocity, 100)

    def test_get_values_acceleration(self):
        w = MovementGroupWidget(MovementGroupDef("H", MovementGroupType.SINGLE_POSITION))
        w.load(MovementGroup(acceleration=60))
        self.assertEqual(w.get_values().acceleration, 60)

    def test_get_values_position(self):
        w = MovementGroupWidget(MovementGroupDef("H", MovementGroupType.SINGLE_POSITION))
        w.load(MovementGroup(position="[1,2,3,4,5,6]"))
        self.assertEqual(w.get_values().position, "[1,2,3,4,5,6]")

    def test_get_values_points(self):
        w = MovementGroupWidget(MovementGroupDef("T", MovementGroupType.MULTI_POSITION))
        w.load(MovementGroup(points=["[0,0,0,0,0,0]"]))
        self.assertEqual(w.get_values().points, ["[0,0,0,0,0,0]"])

    def test_get_values_velocity_only_has_no_position(self):
        w = MovementGroupWidget(MovementGroupDef("J", MovementGroupType.VELOCITY_ONLY))
        w.load(MovementGroup())
        self.assertIsNone(w.get_values().position)

    def test_get_values_reflects_has_iterations_flag(self):
        w = MovementGroupWidget(
            MovementGroupDef("C", MovementGroupType.MULTI_POSITION, has_iterations=True)
        )
        w.load(MovementGroup(iterations=3))
        self.assertEqual(w.get_values().iterations, 3)
        self.assertTrue(w.get_values().has_iterations)


class TestMovementGroupWidgetPublicAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_set_position_updates_display(self):
        w = MovementGroupWidget(MovementGroupDef("H", MovementGroupType.SINGLE_POSITION))
        w.set_position("[9,8,7,6,5,4]")
        self.assertEqual(w._position_display.text(), "[9,8,7,6,5,4]")

    def test_set_position_emits_position_changed(self):
        w = MovementGroupWidget(MovementGroupDef("H", MovementGroupType.SINGLE_POSITION))
        received = []
        w.position_changed.connect(lambda n, v: received.append(v))
        w.set_position("[1,2,3,4,5,6]")
        self.assertEqual(received, ["[1,2,3,4,5,6]"])

    def test_add_point_appends_to_list(self):
        w = MovementGroupWidget(MovementGroupDef("T", MovementGroupType.MULTI_POSITION))
        w.add_point("[1,2,3,4,5,6]")
        self.assertEqual(w._points_list.count(), 1)
        self.assertEqual(w._points_list.item(0).text(), "[1,2,3,4,5,6]")

    def test_add_point_multiple_appends(self):
        w = MovementGroupWidget(MovementGroupDef("T", MovementGroupType.MULTI_POSITION))
        w.add_point("[1,2,3,4,5,6]")
        w.add_point("[7,8,9,10,11,12]")
        self.assertEqual(w._points_list.count(), 2)

    def test_add_point_emits_points_changed(self):
        w = MovementGroupWidget(MovementGroupDef("T", MovementGroupType.MULTI_POSITION))
        received = []
        w.points_changed.connect(lambda n, pts: received.append(pts))
        w.add_point("[1,2,3,4,5,6]")
        self.assertEqual(len(received), 1)
        self.assertIn("[1,2,3,4,5,6]", received[0])

    def test_set_position_noop_for_multi(self):
        w = MovementGroupWidget(MovementGroupDef("T", MovementGroupType.MULTI_POSITION))
        w.set_position("[1,2,3,4,5,6]")  # _position_display is None — must not raise

    def test_add_point_noop_for_single(self):
        w = MovementGroupWidget(MovementGroupDef("H", MovementGroupType.SINGLE_POSITION))
        w.add_point("[1,2,3,4,5,6]")    # _points_list is None — must not raise


class TestMovementGroupsTab(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_load_creates_widget_for_each_group(self):
        tab = MovementGroupsTab()
        tab.load({"HOME": MovementGroup(), "TRAJ": MovementGroup()})
        self.assertIsNotNone(tab.get_widget("HOME"))
        self.assertIsNotNone(tab.get_widget("TRAJ"))

    def test_get_widget_returns_none_for_unknown(self):
        tab = MovementGroupsTab()
        self.assertIsNone(tab.get_widget("GHOST"))

    def test_get_values_returns_all_groups(self):
        tab = MovementGroupsTab()
        tab.load({"HOME": MovementGroup(velocity=50)})
        values = tab.get_values()
        self.assertIn("HOME", values)
        self.assertEqual(values["HOME"].velocity, 50)

    def test_load_uses_known_definition(self):
        tab = MovementGroupsTab()
        tab.load({"HOME_POS": MovementGroup()})
        self.assertEqual(
            tab.get_widget("HOME_POS")._def.group_type,
            MovementGroupType.SINGLE_POSITION,
        )

    def test_load_does_not_duplicate_widget(self):
        tab = MovementGroupsTab()
        tab.load({"HOME": MovementGroup(velocity=10)})
        tab.load({"HOME": MovementGroup(velocity=99)})
        self.assertEqual(len(tab._widgets), 1)
        self.assertEqual(tab.get_widget("HOME").get_values().velocity, 99)

    def test_add_group_creates_widget(self):
        tab  = MovementGroupsTab()
        defn = MovementGroupDef("CUSTOM", MovementGroupType.VELOCITY_ONLY)
        tab.add_group("CUSTOM", defn, MovementGroup())
        self.assertIsNotNone(tab.get_widget("CUSTOM"))

    def test_add_group_does_not_duplicate(self):
        tab  = MovementGroupsTab()
        defn = MovementGroupDef("DUPE", MovementGroupType.VELOCITY_ONLY)
        tab.add_group("DUPE", defn, MovementGroup())
        tab.add_group("DUPE", defn, MovementGroup())
        self.assertEqual(len(tab._widgets), 1)

    def test_remove_group_deletes_widget(self):
        tab = MovementGroupsTab()
        tab.load({"HOME": MovementGroup()})
        tab.remove_group("HOME")
        self.assertIsNone(tab.get_widget("HOME"))

    def test_remove_nonexistent_group_does_not_raise(self):
        tab = MovementGroupsTab()
        tab.remove_group("GHOST")   # must not raise

    def test_set_current_forwarded_from_widget(self):
        tab = MovementGroupsTab()
        tab.load({"HOME_POS": MovementGroup()})
        received = []
        tab.set_current_requested.connect(lambda n: received.append(n))
        tab.get_widget("HOME_POS").set_current_requested.emit("HOME_POS")
        self.assertEqual(received, ["HOME_POS"])

    def test_load_with_extra_defs_uses_provided_definition(self):
        tab  = MovementGroupsTab()
        defn = MovementGroupDef("CUSTOM", MovementGroupType.MULTI_POSITION, has_trajectory_execution=True)
        tab.load({"CUSTOM": MovementGroup()}, extra_defs={"CUSTOM": defn})
        self.assertEqual(
            tab.get_widget("CUSTOM")._def.group_type,
            MovementGroupType.MULTI_POSITION,
        )


if __name__ == "__main__":
    unittest.main()