import logging
import threading
import unittest
from unittest.mock import MagicMock

from src.engine.vision.implementation.VisionSystem.core.models.contour import Contour
from src.robot_systems.glue.domain.workpieces.model.glue_workpiece import GlueWorkpiece
from src.robot_systems.glue.processes.pick_and_place.config import PickAndPlaceConfig, PlaneConfig
from src.robot_systems.glue.processes.pick_and_place.errors import PickAndPlaceErrorCode, PickAndPlaceStage
from src.robot_systems.glue.processes.pick_and_place.execution import HeightResolutionService
from src.robot_systems.glue.processes.pick_and_place.plane import Plane, PlaneManagementService
from src.robot_systems.glue.processes.pick_and_place.planning import (
    PickupCalculator,
    PlacementCalculator,
    WorkpieceSelectionPolicy,
)
from src.robot_systems.glue.processes.pick_and_place.workflow import PickAndPlaceWorkflow
from src.shared_contracts.events.process_events import ProcessState


class TestPickupCalculator(unittest.TestCase):

    def test_calculate_preserves_current_rotation_and_offset_behavior(self):
        config = PickAndPlaceConfig()
        calc = PickupCalculator(config)

        positions = calc.calculate(
            robot_x=10.0,
            robot_y=20.0,
            workpiece_height=2.0,
            gripper_id=0,
            orientation=0.0,
        )

        self.assertAlmostEqual(positions.descent.x, 10.0)
        self.assertAlmostEqual(positions.descent.y, 20.0)
        self.assertAlmostEqual(positions.pickup.z, 352.0)
        self.assertEqual(positions.descent.rx, 180.0)
        self.assertEqual(positions.descent.ry, 0.0)
        self.assertEqual(positions.descent.rz, 90.0)


class TestPlacementCalculator(unittest.TestCase):

    def test_calculate_does_not_mutate_input_contour(self):
        config = PickAndPlaceConfig(plane=PlaneConfig())
        plane_mgr = PlaneManagementService(Plane(config.plane))
        calc = PlacementCalculator(plane_mgr, config)
        original = Contour([[0, 0], [20, 0], [20, 10], [0, 10]])
        before = original.get()

        result = calc.calculate(
            cnt_obj=original,
            orientation=0.0,
            workpiece_height=2.0,
            gripper_id=0,
        )

        self.assertTrue(result.success)
        self.assertEqual(before.tolist(), original.get().tolist())

    def test_plane_management_uses_configured_row_gap(self):
        config = PickAndPlaceConfig(plane=PlaneConfig(x_min=0, x_max=100, y_min=0, y_max=100, row_gap=12))
        plane_mgr = PlaneManagementService(Plane(config.plane))
        target = plane_mgr.next_target(width=120, height=10)
        plane_mgr.update_tallest(20)

        overflowed = plane_mgr.handle_row_overflow(width=120, height=10, target=target)

        self.assertTrue(overflowed)
        self.assertEqual(plane_mgr.plane.yOffset, 32)


class TestPickAndPlaceWorkflow(unittest.TestCase):

    def _make_workpiece(self) -> GlueWorkpiece:
        return GlueWorkpiece(
            workpieceId="wp-1",
            name="wp-1",
            description="demo",
            gripperID=1,
            glueType="Type A",
            contour={"contour": [[0, 0], [20, 0], [20, 10], [0, 10]]},
            height=4.0,
            glueQty=1.0,
            pickupPoint=[10, 5],
            sprayPattern={},
        )

    def test_workflow_reports_place_motion_failure(self):
        diagnostics = []
        robot = MagicMock()
        robot.move_linear.side_effect = [True, True, True, True, False]
        navigation = MagicMock()
        navigation.move_home.return_value = True
        navigation.move_to_calibration_position.return_value = True
        matching = MagicMock()
        matching.run_matching.side_effect = [
            ({"workpieces": [self._make_workpiece()], "orientations": [0.0]}, 0, [], []),
            ({"workpieces": [], "orientations": []}, 1, [], []),
        ]
        tools = MagicMock()
        tools.current_gripper = None
        tools.drop_off_gripper.return_value = (True, "")
        tools.pickup_gripper.return_value = (True, "")
        transformer = MagicMock()
        transformer.transform.return_value = (10.0, 20.0)
        run_allowed = threading.Event()
        run_allowed.set()

        workflow = PickAndPlaceWorkflow(
            robot=robot,
            navigation=navigation,
            matching=matching,
            tools=tools,
            height=None,
            transformer=transformer,
            config=PickAndPlaceConfig(),
            logger=logging.getLogger("pick-and-place-test"),
            on_diagnostics=lambda snapshot: diagnostics.append(snapshot),
        )

        result = workflow.run(stop_event=threading.Event(), run_allowed=run_allowed)

        self.assertEqual(result.state, ProcessState.ERROR)
        self.assertEqual(result.error.code, PickAndPlaceErrorCode.PLACE_MOTION_FAILED)
        self.assertEqual(result.error.stage, PickAndPlaceStage.PLACE)
        self.assertTrue(any(item["stage"] == "place" for item in diagnostics))

    def test_workflow_zero_height_mode_preserves_current_effective_pick_height(self):
        robot = MagicMock()
        robot.move_linear.side_effect = [True, True, True, True, True]
        navigation = MagicMock()
        navigation.move_home.return_value = True
        navigation.move_to_calibration_position.return_value = True
        matching = MagicMock()
        matching.run_matching.side_effect = [
            ({"workpieces": [self._make_workpiece()], "orientations": [0.0]}, 0, [], []),
            ({"workpieces": [], "orientations": []}, 1, [], []),
        ]
        tools = MagicMock()
        tools.current_gripper = None
        tools.drop_off_gripper.return_value = (True, "")
        tools.pickup_gripper.return_value = (True, "")
        transformer = MagicMock()
        transformer.transform.return_value = (10.0, 20.0)
        config = PickAndPlaceConfig()
        run_allowed = threading.Event()
        run_allowed.set()

        workflow = PickAndPlaceWorkflow(
            robot=robot,
            navigation=navigation,
            matching=matching,
            tools=tools,
            height=None,
            transformer=transformer,
            config=config,
            logger=logging.getLogger("pick-and-place-test"),
        )

        result = workflow.run(stop_event=threading.Event(), run_allowed=run_allowed)

        self.assertEqual(result.state, ProcessState.STOPPED)
        pickup_call = robot.move_linear.call_args_list[1]
        pickup_pos = pickup_call.args[0]
        self.assertAlmostEqual(pickup_pos[2], config.z_safe + config.height_adjustment_mm)

    def test_workflow_reports_step_checkpoints_in_order(self):
        checkpoints = []
        robot = MagicMock()
        robot.move_linear.side_effect = [True, True, True, True, True]
        navigation = MagicMock()
        navigation.move_home.return_value = True
        navigation.move_to_calibration_position.return_value = True
        matching = MagicMock()
        matching.run_matching.side_effect = [
            ({"workpieces": [self._make_workpiece()], "orientations": [0.0]}, 0, [], []),
            ({"workpieces": [], "orientations": []}, 1, [], []),
        ]
        tools = MagicMock()
        tools.current_gripper = None
        tools.drop_off_gripper.return_value = (True, "")
        tools.pickup_gripper.return_value = (True, "")
        transformer = MagicMock()
        transformer.transform.return_value = (10.0, 20.0)
        run_allowed = threading.Event()
        run_allowed.set()

        workflow = PickAndPlaceWorkflow(
            robot=robot,
            navigation=navigation,
            matching=matching,
            tools=tools,
            height=None,
            transformer=transformer,
            config=PickAndPlaceConfig(),
            logger=logging.getLogger("pick-and-place-test"),
            step_gate=lambda name, _snapshot: checkpoints.append(name) or True,
        )

        result = workflow.run(stop_event=threading.Event(), run_allowed=run_allowed)

        self.assertEqual(result.state, ProcessState.STOPPED)
        self.assertEqual(
            checkpoints[:11],
            [
                "startup.move_home",
                "matching.run",
                "preparation.begin",
                "transform.pickup_point",
                "tooling.ensure_gripper",
                "tooling.return_home",
                "height.resolve",
                "plane.plan",
                "pick.descent",
                "pick.pickup",
                "pick.lift",
            ],
        )
        self.assertIn("place.approach", checkpoints)
        self.assertIn("place.drop", checkpoints)
        self.assertIn("placement.finalize", checkpoints)
        self.assertIn("placement.move_to_calibration", checkpoints)
        self.assertIn("placement.return_home", checkpoints)

    def test_workflow_can_stop_from_step_gate(self):
        robot = MagicMock()
        navigation = MagicMock()
        matching = MagicMock()
        tools = MagicMock()
        transformer = MagicMock()
        run_allowed = threading.Event()
        run_allowed.set()

        workflow = PickAndPlaceWorkflow(
            robot=robot,
            navigation=navigation,
            matching=matching,
            tools=tools,
            height=None,
            transformer=transformer,
            config=PickAndPlaceConfig(),
            logger=logging.getLogger("pick-and-place-test"),
            step_gate=lambda _name, _snapshot: False,
        )

        result = workflow.run(stop_event=threading.Event(), run_allowed=run_allowed)

        self.assertEqual(result.state, ProcessState.STOPPED)
        navigation.move_home.assert_not_called()


class TestPickAndPlacePolicies(unittest.TestCase):

    def test_height_resolution_zero_mode_preserves_current_behavior(self):
        service = HeightResolutionService(
            config=PickAndPlaceConfig(height_source="zero", height_adjustment_mm=2.0),
            height_service=None,
            logger=logging.getLogger("pick-and-place-test"),
        )

        result = service.resolve(fallback_height_mm=12.0, robot_x=0.0, robot_y=0.0)

        self.assertEqual(result.source, "zero")
        self.assertEqual(result.value_mm, 2.0)
        self.assertIsNone(result.error)

    def test_selection_policy_preserves_match_order(self):
        workpieces = ["a", "b", "c"]
        orientations = [1.0, 2.0, 3.0]

        selected = WorkpieceSelectionPolicy().select(workpieces, orientations)

        self.assertEqual([item.workpiece for item in selected], workpieces)
        self.assertEqual([item.orientation for item in selected], orientations)
