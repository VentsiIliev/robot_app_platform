"""
Comprehensive tests for src/robot_systems/glue/processes/.

Critical business logic — robot lifecycle hooks and the GlueOperationCoordinator
coordination layer.

Covered:
- CleanProcess:        state transitions, requirements
- PickAndPlaceProcess: identical pattern with process_id "pick_and_place"
- GlueProcess:         state transitions (mirrors CleanProcess)
- GlueOperationCoordinator: mode switching, correct sequence selection and delegation
                       for SPRAY_ONLY and PICK_AND_SPRAY modes, calibration path

Note: Timers in CleanProcess and PickAndPlaceProcess are simulation-only and are
not tested here. Only state flow and correct execution order are verified.

Note: The auto-advance chain between processes (pick_and_place → glue in
PICK_AND_SPRAY mode) is implemented inside ProcessSequence and is tested
separately in tests/engine/process/test_process_sequence.py.
"""
import unittest
from unittest.mock import MagicMock, patch

from src.engine.process.process_requirements import ProcessRequirements
from src.engine.process.process_sequence import ProcessSequence
from src.robot_systems.glue.process_ids import ProcessID
from src.robot_systems.glue.processes.clean_process import CleanProcess
from src.robot_systems.glue.processes.glue_operation_mode import GlueOperationMode
from src.robot_systems.glue.processes.glue_operation_coordinator import GlueOperationCoordinator
from src.robot_systems.glue.processes.glue_dispensing.dispensing_config import GlueDispensingConfig
from src.robot_systems.glue.processes.glue_dispensing.dispensing_context import DispensingContext
from src.robot_systems.glue.processes.glue_dispensing.dispensing_error import (
    DispensingErrorCode,
    DispensingErrorInfo,
    DispensingErrorKind,
)
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState
from src.robot_systems.glue.processes.glue_process import GlueProcess
from src.robot_systems.glue.processes.pick_and_place_process import PickAndPlaceProcess
from src.robot_systems.glue.processes.robot_calibration_process import RobotCalibrationProcess
from src.shared_contracts.events.glue_process_events import GlueProcessTopics
from src.shared_contracts.events.pick_and_place_events import PickAndPlaceDiagnosticsEvent, PickAndPlaceTopics
from src.shared_contracts.events.process_events import (
    ProcessState, ProcessStateEvent, ProcessTopics,
)
from src.robot_systems.glue.domain.glue_job_execution_service import GlueExecutionResult
from src.robot_systems.glue.settings.glue import GlueSettings


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _ms():   return MagicMock()
def _robot(): return MagicMock()
def _navigation_service(): return MagicMock()
def _motor(): return MagicMock()
def _resolver(): return MagicMock()
def _glue_process(): return GlueProcess(robot_service=_robot(), motor_service=_motor(), resolver=_resolver(), config=GlueDispensingConfig(), navigation_service=_navigation_service(), messaging=_ms())

# ══════════════════════════════════════════════════════════════════════════════
# CleanProcess
# ══════════════════════════════════════════════════════════════════════════════

class TestCleanProcessIdentity(unittest.TestCase):

    def test_process_id_is_clean(self):
        p = CleanProcess(robot_service=_robot(), messaging=_ms())
        self.assertEqual(p.process_id, "clean")

    def test_initial_state_is_idle(self):
        p = CleanProcess(robot_service=_robot(), messaging=_ms())
        self.assertEqual(p.state, ProcessState.IDLE)


class TestCleanProcessStateTransitions(unittest.TestCase):

    def _make(self):
        return CleanProcess(robot_service=_robot(), messaging=_ms())

    def test_start_transitions_to_running(self):
        p = self._make()
        p.start()
        self.assertEqual(p.state, ProcessState.RUNNING)

    def test_stop_from_running_transitions_to_stopped(self):
        p = self._make()
        p.start(); p.stop()
        self.assertEqual(p.state, ProcessState.STOPPED)

    def test_pause_from_running_transitions_to_paused(self):
        p = self._make()
        p.start(); p.pause()
        self.assertEqual(p.state, ProcessState.PAUSED)

    def test_resume_from_paused_transitions_to_running(self):
        p = self._make()
        p.start(); p.pause(); p.resume()
        self.assertEqual(p.state, ProcessState.RUNNING)

    def test_stop_from_idle_is_blocked(self):
        p = self._make()
        p.stop()
        self.assertEqual(p.state, ProcessState.IDLE)

    def test_pause_from_idle_is_blocked(self):
        p = self._make()
        p.pause()
        self.assertEqual(p.state, ProcessState.IDLE)

    def test_set_error_forces_error_state(self):
        p = self._make()
        p.set_error("overload")
        self.assertEqual(p.state, ProcessState.ERROR)

    def test_reset_errors_returns_to_idle(self):
        p = self._make()
        p.set_error(); p.reset_errors()
        self.assertEqual(p.state, ProcessState.IDLE)

    def test_restart_from_stopped(self):
        p = self._make()
        p.start(); p.stop(); p.start()
        self.assertEqual(p.state, ProcessState.RUNNING)



class TestCleanProcessRequirements(unittest.TestCase):

    def test_requirements_block_start_when_service_unavailable(self):
        p = CleanProcess(
            robot_service   = _robot(),
            messaging       = _ms(),
            requirements    = ProcessRequirements.requires("robot"),
            service_checker = lambda _: False,
        )
        p.start()
        self.assertEqual(p.state, ProcessState.IDLE)

    def test_requirements_allow_start_when_service_available(self):
        p = CleanProcess(
            robot_service   = _robot(),
            messaging       = _ms(),
            requirements    = ProcessRequirements.requires("robot"),
            service_checker = lambda _: True,
        )
        p.start()
        self.assertEqual(p.state, ProcessState.RUNNING)
        p.stop()


# ══════════════════════════════════════════════════════════════════════════════
# PickAndPlaceProcess
# ══════════════════════════════════════════════════════════════════════════════

class TestPickAndPlaceProcessIdentity(unittest.TestCase):

    def test_process_id_is_pick_and_place(self):
        p = PickAndPlaceProcess(robot_service=_robot(), messaging=_ms(),navigation_service=_navigation_service())
        self.assertEqual(p.process_id, "pick_and_place")

    def test_initial_state_is_idle(self):
        p = PickAndPlaceProcess(robot_service=_robot(), messaging=_ms(),navigation_service=_navigation_service())
        self.assertEqual(p.state, ProcessState.IDLE)


class TestPickAndPlaceProcessStateTransitions(unittest.TestCase):

    def _make(self):
        return PickAndPlaceProcess(robot_service=_robot(), messaging=_ms(),navigation_service=_navigation_service())

    def test_start_transitions_to_running(self):
        p = self._make()
        p.start()
        self.assertEqual(p.state, ProcessState.RUNNING)

    def test_stop_from_running_transitions_to_stopped(self):
        p = self._make()
        p.start(); p.stop()
        self.assertEqual(p.state, ProcessState.STOPPED)

    def test_pause_from_running_transitions_to_paused(self):
        p = self._make()
        p.start(); p.pause()
        self.assertEqual(p.state, ProcessState.PAUSED)

    def test_resume_from_paused_transitions_to_running(self):
        p = self._make()
        p.start(); p.pause(); p.resume()
        self.assertEqual(p.state, ProcessState.RUNNING)

    def test_stop_from_idle_is_blocked(self):
        p = self._make()
        p.stop()
        self.assertEqual(p.state, ProcessState.IDLE)

    def test_set_error_forces_error_state(self):
        p = self._make()
        p.set_error("encoder lost")
        self.assertEqual(p.state, ProcessState.ERROR)

    def test_reset_errors_returns_to_idle(self):
        p = self._make()
        p.set_error(); p.reset_errors()
        self.assertEqual(p.state, ProcessState.IDLE)

    def test_start_publishes_pick_and_place_diagnostics(self):
        messaging = MagicMock()
        p = PickAndPlaceProcess(robot_service=_robot(), messaging=messaging, navigation_service=_navigation_service())

        p.start()

        published_topics = [call.args[0] for call in messaging.publish.call_args_list]
        self.assertIn(PickAndPlaceTopics.PLANE_RESET, published_topics)
        self.assertIn(PickAndPlaceTopics.DIAGNOSTICS, published_topics)
        diagnostics_call = next(
            call for call in messaging.publish.call_args_list
            if call.args[0] == PickAndPlaceTopics.DIAGNOSTICS
        )
        self.assertIsInstance(diagnostics_call.args[1], PickAndPlaceDiagnosticsEvent)

    def test_step_mode_can_be_toggled(self):
        p = self._make()

        p.set_step_mode(True)
        self.assertTrue(p.is_step_mode_enabled())

        p.set_step_mode(False)
        self.assertFalse(p.is_step_mode_enabled())

    def test_step_once_requires_running_process(self):
        p = self._make()
        p.set_step_mode(True)

        with self.assertRaisesRegex(RuntimeError, "must be running"):
            p.step_once()



# ══════════════════════════════════════════════════════════════════════════════
# GlueOperationCoordinator helpers
# ══════════════════════════════════════════════════════════════════════════════

def _make_runner_mocks(execution_service=None, spray_on=True):
    """
    Build a GlueOperationCoordinator with real processes (needed for construction),
    then replace the internal ProcessSequence objects with mocks so tests can
    verify delegation without executing real sequence logic.

    Returns (runner, spray_seq, pick_seq, clean_seq).
    """
    glue  = MagicMock(); glue.process_id  = "glue";          glue.state  = ProcessState.IDLE
    pick  = MagicMock(); pick.process_id  = "pick_and_place"; pick.state  = ProcessState.IDLE
    clean = MagicMock(); clean.process_id = "clean";          clean.state = ProcessState.IDLE
    calib = MagicMock(); calib.process_id = "robot_calibration"; calib.state = ProcessState.IDLE

    runner = GlueOperationCoordinator(
        glue_process           = glue,
        pick_and_place_process = pick,
        clean_process          = clean,
        calibration_process    = calib,
        messaging              = _ms(),
        execution_service      = execution_service,
        settings_service       = MagicMock(get=MagicMock(return_value=GlueSettings(spray_on=spray_on))),
    )

    # Replace internal sequences with mocks — tests verify runner's delegation
    spray_seq = MagicMock(spec=ProcessSequence)
    pick_seq  = MagicMock(spec=ProcessSequence)
    clean_seq = MagicMock(spec=ProcessSequence)
    runner._sequences[GlueOperationMode.SPRAY_ONLY]     = spray_seq
    runner._sequences[GlueOperationMode.PICK_AND_SPRAY] = pick_seq
    runner._clean_sequence                               = clean_seq

    return runner, spray_seq, pick_seq, clean_seq


# ══════════════════════════════════════════════════════════════════════════════
# GlueOperationCoordinator — mode
# ══════════════════════════════════════════════════════════════════════════════

class TestGlueOperationCoordinatorMode(unittest.TestCase):

    def test_default_mode_is_spray_only(self):
        runner, *_ = _make_runner_mocks()
        self.assertEqual(runner._mode, GlueOperationMode.SPRAY_ONLY)

    def test_set_mode_changes_to_pick_and_spray(self):
        runner, *_ = _make_runner_mocks()
        runner.set_mode(GlueOperationMode.PICK_AND_SPRAY)
        self.assertEqual(runner._mode, GlueOperationMode.PICK_AND_SPRAY)

    def test_set_mode_can_revert_to_spray_only(self):
        runner, *_ = _make_runner_mocks()
        runner.set_mode(GlueOperationMode.PICK_AND_SPRAY)
        runner.set_mode(GlueOperationMode.SPRAY_ONLY)
        self.assertEqual(runner._mode, GlueOperationMode.SPRAY_ONLY)

    def test_glue_process_property_returns_spray_only_process(self):
        glue = MagicMock()
        glue.process_id = "glue"
        pick = MagicMock()
        pick.process_id = "pick_and_place"
        clean = MagicMock()
        calib = MagicMock()
        runner = GlueOperationCoordinator(
            glue_process=glue,
            pick_and_place_process=pick,
            clean_process=clean,
            calibration_process=calib,
            messaging=_ms(),
        )

        self.assertIs(runner.glue_process, glue)


# ══════════════════════════════════════════════════════════════════════════════
# GlueOperationCoordinator — SPRAY_ONLY start
# ══════════════════════════════════════════════════════════════════════════════

class TestGlueOperationCoordinatorSprayOnly(unittest.TestCase):

    def test_start_calls_spray_sequence_start(self):
        runner, spray_seq, pick_seq, _ = _make_runner_mocks()
        runner.start()
        spray_seq.start.assert_called_once()
        pick_seq.start.assert_not_called()

    def test_start_sets_active_to_spray_sequence(self):
        runner, spray_seq, *_ = _make_runner_mocks()
        runner.start()
        self.assertIs(runner._active, spray_seq)

    def test_start_in_spray_only_prepares_glue_before_sequence_start(self):
        execution_service = MagicMock()
        execution_service.prepare_and_load.return_value = GlueExecutionResult(
            success=True,
            stage="load",
            message="loaded",
            matched_ids=["wp-1"],
            workpiece_count=1,
            segment_count=2,
            loaded=True,
            started=False,
        )
        runner, spray_seq, _, _ = _make_runner_mocks(
            execution_service=execution_service,
            spray_on=False,
        )

        runner.start()

        execution_service.prepare_and_load.assert_called_once_with(spray_on=False)
        spray_seq.start.assert_called_once()

    def test_start_in_spray_only_blocks_sequence_when_preparation_fails(self):
        execution_service = MagicMock()
        execution_service.prepare_and_load.return_value = GlueExecutionResult(
            success=False,
            stage="positioning",
            message="Robot could not move to calibration capture position",
            matched_ids=[],
            workpiece_count=0,
            segment_count=0,
            loaded=False,
            started=False,
        )
        runner, spray_seq, _, _ = _make_runner_mocks(execution_service=execution_service)
        runner._messaging = MagicMock()

        runner.start()

        spray_seq.start.assert_not_called()
        runner._messaging.publish.assert_called_once()
        topic, event = runner._messaging.publish.call_args.args
        self.assertEqual(topic, ProcessTopics.busy(ProcessID.COORDINATOR))
        self.assertIn("Glue spray-only start failed at positioning", event.message)

    def test_stop_cancels_pending_spray_only_preparation(self):
        execution_service = MagicMock()
        runner, spray_seq, _, _ = _make_runner_mocks(execution_service=execution_service)
        runner._preparing_glue = True

        runner.stop()

        execution_service.cancel_pending.assert_called_once_with()
        spray_seq.stop.assert_not_called()

    def test_resume_in_spray_only_does_not_reprepare_glue(self):
        execution_service = MagicMock()
        runner, spray_seq, _, _ = _make_runner_mocks(execution_service=execution_service)
        runner._active_sequence = spray_seq
        runner.glue_process.state = ProcessState.PAUSED

        runner.resume()

        spray_seq.start.assert_called_once()
        execution_service.prepare_and_load.assert_not_called()

    def test_start_again_after_stopped_spray_run_reprepares_glue(self):
        execution_service = MagicMock()
        execution_service.prepare_and_load.return_value = GlueExecutionResult(
            success=True,
            stage="load",
            message="loaded",
            matched_ids=["wp-1"],
            workpiece_count=1,
            segment_count=2,
            loaded=True,
            started=False,
        )
        runner, spray_seq, _, _ = _make_runner_mocks(
            execution_service=execution_service,
            spray_on=False,
        )
        runner._active_sequence = spray_seq
        runner.glue_process.state = ProcessState.STOPPED

        runner.start()

        execution_service.prepare_and_load.assert_called_once_with(spray_on=False)
        spray_seq.start.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# GlueOperationCoordinator — PICK_AND_SPRAY start
# ══════════════════════════════════════════════════════════════════════════════

class TestGlueOperationCoordinatorPickAndSpray(unittest.TestCase):

    def test_start_calls_pick_sequence_start(self):
        runner, spray_seq, pick_seq, _ = _make_runner_mocks()
        runner.set_mode(GlueOperationMode.PICK_AND_SPRAY)
        runner.start()
        pick_seq.start.assert_called_once()
        spray_seq.start.assert_not_called()

    def test_start_sets_active_to_pick_sequence(self):
        runner, _, pick_seq, _ = _make_runner_mocks()
        runner.set_mode(GlueOperationMode.PICK_AND_SPRAY)
        runner.start()
        self.assertIs(runner._active, pick_seq)

    def test_pick_and_spray_sequence_prepares_glue_before_starting_it(self):
        execution_service = MagicMock()
        execution_service.prepare_and_load.return_value = GlueExecutionResult(
            success=True,
            stage="load",
            message="loaded",
            matched_ids=["wp-1"],
            workpiece_count=1,
            segment_count=2,
            loaded=True,
            started=False,
        )
        runner, _, _, _ = _make_runner_mocks(
            execution_service=execution_service,
            spray_on=False,
        )
        runner.set_mode(GlueOperationMode.PICK_AND_SPRAY)

        self.assertTrue(runner._prepare_glue_after_pick(runner.pick_and_place_process, runner.glue_process))
        execution_service.prepare_and_load.assert_called_once_with(spray_on=False)

    def test_pick_and_spray_sequence_sets_glue_error_when_preparation_fails(self):
        execution_service = MagicMock()
        execution_service.prepare_and_load.return_value = GlueExecutionResult(
            success=False,
            stage="matching",
            message="No matched workpieces available for glue execution",
            matched_ids=[],
            workpiece_count=0,
            segment_count=0,
            loaded=False,
            started=False,
        )
        runner, _, _, _ = _make_runner_mocks(execution_service=execution_service)
        runner.set_mode(GlueOperationMode.PICK_AND_SPRAY)
        runner.glue_process.set_error = MagicMock()

        result = runner._prepare_glue_after_pick(runner.pick_and_place_process, runner.glue_process)

        self.assertFalse(result)
        runner.glue_process.set_error.assert_called_once_with(
            "Glue preparation failed at matching: No matched workpieces available for glue execution"
        )


# ══════════════════════════════════════════════════════════════════════════════
# GlueOperationCoordinator — stop
# ══════════════════════════════════════════════════════════════════════════════

class TestGlueOperationCoordinatorStop(unittest.TestCase):

    def test_stop_calls_active_sequence_stop(self):
        runner, spray_seq, *_ = _make_runner_mocks()
        runner.start()
        runner.stop()
        spray_seq.stop.assert_called_once()

    def test_stop_when_no_active_does_not_raise(self):
        runner, *_ = _make_runner_mocks()
        runner.stop()   # _active is None


# ══════════════════════════════════════════════════════════════════════════════
# GlueOperationCoordinator — pause / resume
# ══════════════════════════════════════════════════════════════════════════════

class TestGlueOperationCoordinatorPauseResume(unittest.TestCase):

    def test_pause_calls_active_sequence_pause(self):
        runner, spray_seq, *_ = _make_runner_mocks()
        runner.start()
        runner.pause()
        spray_seq.pause.assert_called_once()

    def test_pause_when_no_active_does_not_raise(self):
        runner, *_ = _make_runner_mocks()
        runner.pause()

    def test_pause_cancels_pending_spray_only_preparation(self):
        execution_service = MagicMock()
        runner, spray_seq, *_ = _make_runner_mocks(execution_service=execution_service)
        runner._active_sequence = spray_seq
        runner._preparing_glue = True

        runner.pause()

        execution_service.cancel_pending.assert_called_once_with()
        spray_seq.pause.assert_called_once()

    def test_resume_calls_start_on_active_sequence(self):
        runner, spray_seq, *_ = _make_runner_mocks()
        runner.start()
        spray_seq.reset_mock()
        runner.resume()
        spray_seq.start.assert_called_once()

    def test_resume_when_no_active_does_not_raise(self):
        runner, *_ = _make_runner_mocks()
        runner.resume()


# ══════════════════════════════════════════════════════════════════════════════
# GlueOperationCoordinator — clean
# ══════════════════════════════════════════════════════════════════════════════

class TestGlueOperationCoordinatorClean(unittest.TestCase):

    def test_clean_starts_clean_sequence(self):
        runner, _, _, clean_seq = _make_runner_mocks()
        runner.clean()
        clean_seq.start.assert_called_once()

    def test_clean_sets_active_to_clean_sequence(self):
        runner, _, _, clean_seq = _make_runner_mocks()
        runner.clean()
        self.assertIs(runner._active, clean_seq)

    def test_clean_stops_previously_active_sequence(self):
        runner, spray_seq, _, _ = _make_runner_mocks()
        runner.start()          # active = spray_seq
        runner.clean()
        spray_seq.stop.assert_called_once()

    def test_clean_does_not_stop_itself_when_already_active(self):
        runner, _, _, clean_seq = _make_runner_mocks()
        runner.clean()          # active = clean_seq
        clean_seq.reset_mock()
        runner.clean()          # clean again — must NOT stop clean_seq first
        clean_seq.stop.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# GlueOperationCoordinator — reset_errors
# ══════════════════════════════════════════════════════════════════════════════

class TestGlueOperationCoordinatorResetErrors(unittest.TestCase):

    def test_reset_errors_calls_active_sequence_reset_errors(self):
        runner, spray_seq, *_ = _make_runner_mocks()
        runner.start()
        runner.reset_errors()
        spray_seq.reset_errors.assert_called_once()

    def test_reset_errors_when_no_active_does_not_raise(self):
        runner, *_ = _make_runner_mocks()
        runner.reset_errors()   # _active is None


# ══════════════════════════════════════════════════════════════════════════════
# GlueOperationMode
# ══════════════════════════════════════════════════════════════════════════════

class TestGlueOperationMode(unittest.TestCase):

    def test_from_label_spray_only(self):
        self.assertEqual(GlueOperationMode.from_label("Spray Only"), GlueOperationMode.SPRAY_ONLY)

    def test_from_label_pick_and_spray(self):
        self.assertEqual(GlueOperationMode.from_label("Pick And Spray"), GlueOperationMode.PICK_AND_SPRAY)

    def test_from_label_unknown_returns_none(self):
        self.assertIsNone(GlueOperationMode.from_label("Unknown Mode"))

    def test_enum_values(self):
        self.assertEqual(GlueOperationMode.SPRAY_ONLY.value, "spray_only")
        self.assertEqual(GlueOperationMode.PICK_AND_SPRAY.value, "pick_and_spray")


# ══════════════════════════════════════════════════════════════════════════════
# GlueProcess
# ══════════════════════════════════════════════════════════════════════════════

class TestGlueProcessIdentity(unittest.TestCase):

    def test_process_id_is_glue(self):
        p = _glue_process()
        self.assertEqual(p.process_id, "glue")

    def test_initial_state_is_idle(self):
        p = _glue_process()
        self.assertEqual(p.state, ProcessState.IDLE)


class TestGlueProcessStateTransitions(unittest.TestCase):

    def _make(self):
        return _glue_process()

    def test_start_transitions_to_running(self):
        p = self._make(); p.start()
        self.assertEqual(p.state, ProcessState.RUNNING)

    def test_stop_from_running_transitions_to_stopped(self):
        p = self._make(); p.start(); p.stop()
        self.assertEqual(p.state, ProcessState.STOPPED)

    def test_pause_from_running_transitions_to_paused(self):
        p = self._make(); p.start(); p.pause()
        self.assertEqual(p.state, ProcessState.PAUSED)

    def test_resume_from_paused_transitions_to_running(self):
        p = self._make(); p.start(); p.pause(); p.resume()
        self.assertEqual(p.state, ProcessState.RUNNING)

    def test_set_error_forces_error_state(self):
        p = self._make(); p.set_error("encoder lost")
        self.assertEqual(p.state, ProcessState.ERROR)

    def test_reset_errors_returns_to_idle(self):
        p = self._make(); p.set_error(); p.reset_errors()
        self.assertEqual(p.state, ProcessState.IDLE)

    def test_reset_errors_clears_dispensing_last_error(self):
        p = self._make()
        p._context = DispensingContext()
        p._context.last_error = DispensingErrorInfo(
            kind=DispensingErrorKind.PUMP,
            code=DispensingErrorCode.PUMP_ON_FAILED,
            state=GlueDispensingState.TURNING_ON_PUMP,
            operation="pump_on",
            message="pump_on failed",
            exception_type="RuntimeError",
            path_index=1,
            point_index=2,
        )

        p.set_error()
        p.reset_errors()

        self.assertEqual(p.state, ProcessState.IDLE)
        self.assertIsNone(p._context.last_error)

    def test_get_dispensing_snapshot_returns_idle_summary_without_context(self):
        p = self._make()

        snapshot = p.get_dispensing_snapshot()

        self.assertEqual(snapshot["process_state"], ProcessState.IDLE.value)
        self.assertFalse(snapshot["manual_mode"])
        self.assertIsNone(snapshot["machine"])
        self.assertIsNone(snapshot["dispensing"])

    def test_get_dispensing_snapshot_includes_context_debug_snapshot(self):
        p = self._make()
        p._context = DispensingContext()
        p._context.current_path_index = 2
        p._context.current_point_index = 5

        snapshot = p.get_dispensing_snapshot()

        self.assertEqual(snapshot["process_state"], ProcessState.IDLE.value)
        self.assertEqual(snapshot["dispensing"]["current_path_index"], 2)
        self.assertEqual(snapshot["dispensing"]["current_point_index"], 5)

    def test_start_in_manual_mode_builds_machine_without_worker_thread(self):
        p = self._make()
        p.set_manual_mode(True)
        p.set_paths([([[1.0, 2.0], [3.0, 4.0]], {"glue_type": "Type A", "motor_speed": "500"}, {})], spray_on=True)
        machine = MagicMock()
        machine.get_snapshot.return_value = MagicMock(
            initial_state=GlueDispensingState.STARTING,
            current_state=GlueDispensingState.STARTING,
            is_running=False,
            step_count=0,
            last_state=None,
            last_next_state=None,
            last_error=None,
        )

        with patch("src.robot_systems.glue.processes.glue_process.DispensingMachineFactory.build", return_value=machine):
            p.start()

        self.assertEqual(p.state, ProcessState.RUNNING)
        machine.reset.assert_called_once_with()
        self.assertIsNone(p._worker_thread)

    def test_start_publishes_diagnostics_snapshot(self):
        p = self._make()
        p.set_manual_mode(True)
        p.set_paths([([[1.0, 2.0], [3.0, 4.0]], {"glue_type": "Type A", "motor_speed": "500"}, {})], spray_on=True)
        machine = MagicMock()
        machine.get_snapshot.return_value = MagicMock(
            initial_state=GlueDispensingState.STARTING,
            current_state=GlueDispensingState.STARTING,
            is_running=False,
            step_count=0,
            last_state=None,
            last_next_state=None,
            last_error=None,
        )

        with patch("src.robot_systems.glue.processes.glue_process.DispensingMachineFactory.build", return_value=machine):
            p.start()

        p._messaging.publish.assert_any_call(GlueProcessTopics.DIAGNOSTICS, p.get_dispensing_snapshot())

    def test_completed_worker_run_transitions_outer_process_to_stopped(self):
        p = self._make()
        p.set_paths([([[1.0, 2.0], [3.0, 4.0]], {"glue_type": "Type A", "motor_speed": "500"}, {})], spray_on=False)
        machine = MagicMock()
        machine.get_snapshot.return_value = MagicMock(
            initial_state=GlueDispensingState.STARTING,
            current_state=GlueDispensingState.IDLE,
            is_running=False,
            step_count=10,
            last_state=GlueDispensingState.COMPLETED,
            last_next_state=GlueDispensingState.IDLE,
            last_error=None,
        )

        with patch("src.robot_systems.glue.processes.glue_process.DispensingMachineFactory.build", return_value=machine):
            p.start()
            p._worker_thread.join(timeout=1.0)

        self.assertEqual(p.state, ProcessState.STOPPED)
        self.assertIsNone(p._worker_thread)
        machine.start_execution.assert_called_once_with()

    def test_step_once_delegates_to_machine_in_manual_mode(self):
        p = self._make()
        p.set_manual_mode(True)
        p._context = DispensingContext()
        p._machine = MagicMock()
        p._machine.step.return_value = True
        p._machine.get_snapshot.return_value = MagicMock(
            initial_state=GlueDispensingState.STARTING,
            current_state=GlueDispensingState.LOADING_PATH,
            is_running=False,
            step_count=1,
            last_state=GlueDispensingState.STARTING,
            last_next_state=GlueDispensingState.LOADING_PATH,
            last_error=None,
        )
        p._state = ProcessState.RUNNING

        snapshot = p.step_once()

        p._machine.step.assert_called_once_with()
        self.assertTrue(snapshot["manual_mode"])
        self.assertTrue(snapshot["step_result"])
        self.assertEqual(snapshot["machine"]["current_state"], "LOADING_PATH")


# ══════════════════════════════════════════════════════════════════════════════
# GlueOperationCoordinator — calibration path
# ══════════════════════════════════════════════════════════════════════════════

class TestGlueOperationCoordinatorCalibration(unittest.TestCase):

    def _make_with_calib(self):
        """Return coordinator with the real calibration process mock accessible."""
        glue  = MagicMock(); glue.process_id  = "glue";          glue.state  = ProcessState.IDLE
        pick  = MagicMock(); pick.process_id  = "pick_and_place"; pick.state  = ProcessState.IDLE
        clean = MagicMock(); clean.process_id = "clean";          clean.state = ProcessState.IDLE
        calib = MagicMock(); calib.process_id = "robot_calibration"; calib.state = ProcessState.IDLE

        runner = GlueOperationCoordinator(
            glue_process           = glue,
            pick_and_place_process = pick,
            clean_process          = clean,
            calibration_process    = calib,
            messaging              = _ms(),
        )
        return runner, calib

    def test_calibrate_calls_process_start(self):
        runner, calib = self._make_with_calib()
        runner.calibrate()
        calib.start.assert_called_once()

    def test_stop_calibration_calls_process_stop_when_active(self):
        runner, calib = self._make_with_calib()
        calib.state = ProcessState.IDLE
        runner.calibrate()
        runner.stop_calibration()
        calib.stop.assert_called_once()

    def test_stop_calibration_clears_active_process(self):
        runner, calib = self._make_with_calib()
        calib.state = ProcessState.IDLE
        runner.calibrate()
        runner.stop_calibration()
        self.assertIsNone(runner._active_process)

    def test_stop_calibration_when_not_active_does_not_raise(self):
        runner, calib = self._make_with_calib()
        runner.stop_calibration()   # never started — must not raise
        calib.stop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
