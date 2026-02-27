"""
Comprehensive tests for src/robot_systems/glue/processes/.

Critical business logic — robot lifecycle hooks and the GlueOperationCoordinator
coordination layer.

Covered:
- CleanProcess:        state transitions, requirements
- PickAndPlaceProcess: identical pattern with process_id "pick_and_place"
- GlueOperationCoordinator: mode switching, correct sequence selection and delegation
                       for SPRAY_ONLY and PICK_AND_SPRAY modes

Note: Timers in CleanProcess and PickAndPlaceProcess are simulation-only and are
not tested here. Only state flow and correct execution order are verified.

Note: The auto-advance chain between processes (pick_and_place → glue in
PICK_AND_SPRAY mode) is implemented inside ProcessSequence and is tested
separately in tests/engine/process/test_process_sequence.py.
"""
import unittest
from unittest.mock import MagicMock

from src.engine.process.process_requirements import ProcessRequirements
from src.engine.process.process_sequence import ProcessSequence
from src.robot_systems.glue.processes.clean_process import CleanProcess
from src.robot_systems.glue.processes.glue_operation_mode import GlueOperationMode
from src.robot_systems.glue.processes.glue_operation_coordinator import GlueOperationCoordinator
from src.robot_systems.glue.processes.glue_process import GlueProcess
from src.robot_systems.glue.processes.pick_and_place_process import PickAndPlaceProcess
from src.shared_contracts.events.process_events import (
    ProcessState, ProcessStateEvent, ProcessTopics,
)


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _ms():   return MagicMock()
def _robot(): return MagicMock()


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
        p = PickAndPlaceProcess(robot_service=_robot(), messaging=_ms())
        self.assertEqual(p.process_id, "pick_and_place")

    def test_initial_state_is_idle(self):
        p = PickAndPlaceProcess(robot_service=_robot(), messaging=_ms())
        self.assertEqual(p.state, ProcessState.IDLE)


class TestPickAndPlaceProcessStateTransitions(unittest.TestCase):

    def _make(self):
        return PickAndPlaceProcess(robot_service=_robot(), messaging=_ms())

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



# ══════════════════════════════════════════════════════════════════════════════
# GlueOperationCoordinator helpers
# ══════════════════════════════════════════════════════════════════════════════

def _make_runner_mocks():
    """
    Build a GlueOperationCoordinator with real processes (needed for construction),
    then replace the internal ProcessSequence objects with mocks so tests can
    verify delegation without executing real sequence logic.

    Returns (runner, spray_seq, pick_seq, clean_seq).
    """
    glue  = MagicMock(); glue.process_id  = "glue";          glue.state  = ProcessState.IDLE
    pick  = MagicMock(); pick.process_id  = "pick_and_place"; pick.state  = ProcessState.IDLE
    clean = MagicMock(); clean.process_id = "clean";          clean.state = ProcessState.IDLE

    runner = GlueOperationCoordinator(
        glue_process           = glue,
        pick_and_place_process = pick,
        clean_process          = clean,
        messaging              = _ms(),
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


if __name__ == "__main__":
    unittest.main()
