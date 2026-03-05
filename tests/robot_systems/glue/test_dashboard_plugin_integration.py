import unittest
from unittest.mock import MagicMock, patch

from src.robot_systems.glue.applications.dashboard.service.glue_dashboard_service import GlueDashboardService
from src.robot_systems.glue.process_ids import ProcessID
from src.applications.base.widget_application import WidgetApplication
from src.engine.system.i_system_manager import ISystemManager
from src.robot_systems.glue.glue_robot_system import GlueRobotSystem
from src.robot_systems.glue.processes.glue_operation_mode import GlueOperationMode
from src.robot_systems.glue.processes.glue_operation_coordinator import GlueOperationCoordinator
from src.robot_systems.glue.processes.glue_process import GlueProcess
from src.shared_contracts.events.process_events import ProcessState, ProcessTopics
from src.engine.process.process_requirements import ProcessRequirements
from src.robot_systems.glue.settings.cells import (
    GlueCellsConfig, CellConfig, CalibrationConfig, MeasurementConfig,
)
from src.robot_systems.glue.settings.glue_types import Glue, GlueCatalog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cell(cell_id: int, glue_type: str = "Type A", capacity: float = 5000.0) -> CellConfig:
    return CellConfig(
        id=cell_id, type=glue_type, url=f"http://cell{cell_id}", capacity=capacity,
        fetch_timeout_seconds=5.0, data_fetch_interval_ms=500,
        calibration=CalibrationConfig(zero_offset=0.0, scale_factor=1.0, temperature_compensation=False),
        measurement=MeasurementConfig(
            sampling_rate=10, filter_cutoff=1.0, averaging_samples=5,
            min_weight_threshold=0.0, max_weight_threshold=10000.0,
        ),
    )

def _make_cells(*cell_ids: int) -> GlueCellsConfig:
    return GlueCellsConfig(cells=[_make_cell(cid) for cid in cell_ids])

def _make_catalog(*names: str) -> GlueCatalog:
    return GlueCatalog(glue_types=[Glue(name=n) for n in names])

def _make_messaging():
    return MagicMock()

def _make_robot_service():
    return MagicMock()

def _make_navigation_service():
    return MagicMock()

def _make_settings_service(cells=None, catalog=None):
    ss       = MagicMock()
    _cells   = cells   or _make_cells(1, 2, 3)
    _catalog = catalog or _make_catalog("Type A", "Type B")
    ss.get.side_effect = lambda key: (
        _cells   if key == "glue_cells"   else
        _catalog if key == "glue_catalog" else None
    )
    return ss, _cells, _catalog

def _make_runner():
    return MagicMock(spec=GlueOperationCoordinator)

def _make_dashboard_service(cells=None, catalog=None, runner=None, weight_service=None):
    ss, _c, _cat = _make_settings_service(cells, catalog)
    _runner      = runner or _make_runner()
    svc          = GlueDashboardService(runner=_runner, settings_service=ss, weight_service=weight_service)
    return svc, _runner, ss, _c, _cat

def _make_robot_system(cells=None, catalog=None):
    ss, _, _ = _make_settings_service(cells, catalog)
    rs       = _make_robot_service()
    app      = MagicMock()
    app.get_service.return_value          = rs
    app.get_optional_service.return_value = None
    app._settings_service                 = ss
    app.coordinator                       = _make_runner()
    # app.health_registry is auto-created by MagicMock; .check(name) returns truthy
    return app, rs, ss


# ---------------------------------------------------------------------------
# ApplicationSpec declaration
# ---------------------------------------------------------------------------

class TestDashboardApplicationSpec(unittest.TestCase):

    def _spec(self):
        return next(
            (s for s in GlueRobotSystem.shell.applications if s.name == "GlueDashboard"), None,
        )

    def test_spec_declared(self):
        self.assertIsNotNone(self._spec(), "GlueDashboard ApplicationSpec missing")

    def test_spec_folder_id(self):
        self.assertEqual(self._spec().folder_id, 1)

    def test_spec_has_factory(self):
        self.assertIsNotNone(self._spec().factory)

    def test_spec_icon_set(self):
        self.assertIsNotNone(self._spec().icon)


# ---------------------------------------------------------------------------
# Factory builds a WidgetApplication
# ---------------------------------------------------------------------------

class TestDashboardApplicationFactory(unittest.TestCase):

    def _build(self, cells=None, catalog=None):
        app, rs, ss = _make_robot_system(cells, catalog)
        spec        = next(s for s in GlueRobotSystem.shell.applications if s.name == "GlueDashboard")
        application = spec.factory(app)
        return application, rs, ss

    def test_factory_returns_widget_application(self):
        application, _, _ = self._build()
        self.assertIsInstance(application, WidgetApplication)

    def test_factory_accesses_coordinator(self):
        app, _, _ = _make_robot_system()
        spec = next(s for s in GlueRobotSystem.shell.applications if s.name == "GlueDashboard")
        spec.factory(app)
        _ = app.coordinator  # coordinator is accessed at factory time, not widget creation time

    def test_register_stores_messaging_service(self):
        application, _, _ = self._build()
        ms = MagicMock()
        application.register(ms)
        self.assertIs(application._messaging_service, ms)

    def test_widget_factory_forwards_messaging_service(self):
        application, _, _ = self._build()
        ms = MagicMock()
        application.register(ms)
        with patch("src.robot_systems.glue.applications.dashboard.glue_dashboard.GlueDashboard.create") as mock_create:
            mock_create.return_value = MagicMock()
            application.create_widget()
            _, kwargs = mock_create.call_args
            self.assertIs(kwargs.get("messaging_service"), ms)


# ---------------------------------------------------------------------------
# GlueDashboardService — command delegation to GlueOperationCoordinator
# ---------------------------------------------------------------------------

class TestGlueDashboardServiceCommands(unittest.TestCase):

    def test_start_delegates_to_runner(self):
        svc, runner, *_ = _make_dashboard_service()
        svc.start()
        runner.start.assert_called_once()

    def test_stop_delegates_to_runner(self):
        svc, runner, *_ = _make_dashboard_service()
        svc.stop()
        runner.stop.assert_called_once()

    def test_pause_delegates_to_runner(self):
        svc, runner, *_ = _make_dashboard_service()
        svc.pause()
        runner.pause.assert_called_once()

    def test_resume_delegates_to_runner(self):
        svc, runner, *_ = _make_dashboard_service()
        svc.resume()
        runner.resume.assert_called_once()

    def test_reset_errors_delegates_to_runner(self):
        svc, runner, *_ = _make_dashboard_service()
        svc.reset_errors()
        runner.reset_errors.assert_called_once()

    def test_clean_delegates_to_runner(self):
        svc, runner, *_ = _make_dashboard_service()
        svc.clean()
        runner.clean.assert_called_once()


# ---------------------------------------------------------------------------
# GlueDashboardService — set_mode label parsing
# ---------------------------------------------------------------------------

class TestGlueDashboardServiceSetMode(unittest.TestCase):

    def test_set_mode_spray_only_passes_enum_to_runner(self):
        svc, runner, *_ = _make_dashboard_service()
        svc.set_mode("Spray Only")
        runner.set_mode.assert_called_once_with(GlueOperationMode.SPRAY_ONLY)

    def test_set_mode_pick_and_spray_passes_enum_to_runner(self):
        svc, runner, *_ = _make_dashboard_service()
        svc.set_mode("Pick And Spray")
        runner.set_mode.assert_called_once_with(GlueOperationMode.PICK_AND_SPRAY)


# ---------------------------------------------------------------------------
# GlueDashboardService — queries
# ---------------------------------------------------------------------------

class TestGlueDashboardServiceQueries(unittest.TestCase):

    def test_get_cells_count_correct(self):
        svc, *_ = _make_dashboard_service(cells=_make_cells(1, 2, 3))
        self.assertEqual(svc.get_cells_count(), 3)

    def test_get_cells_count_single(self):
        svc, *_ = _make_dashboard_service(cells=_make_cells(1))
        self.assertEqual(svc.get_cells_count(), 1)

    def test_get_cells_count_returns_zero_on_error(self):
        ss = MagicMock()
        ss.get.side_effect = RuntimeError("boom")
        svc = GlueDashboardService(runner=_make_runner(), settings_service=ss)
        self.assertEqual(svc.get_cells_count(), 0)

    def test_get_cell_capacity_returns_correct_value(self):
        cells = GlueCellsConfig(cells=[_make_cell(1, capacity=9999.0)])
        svc, *_ = _make_dashboard_service(cells=cells)
        self.assertEqual(svc.get_cell_capacity(1), 9999.0)

    def test_get_cell_capacity_fallback_on_missing_cell(self):
        svc, *_ = _make_dashboard_service(cells=_make_cells(1))
        self.assertEqual(svc.get_cell_capacity(99), 0.0)

    def test_get_cell_capacity_fallback_on_error(self):
        ss = MagicMock()
        ss.get.side_effect = RuntimeError("boom")
        svc = GlueDashboardService(runner=_make_runner(), settings_service=ss)
        self.assertEqual(svc.get_cell_capacity(1), 0.0)

    def test_get_cell_glue_type_correct(self):
        cells = GlueCellsConfig(cells=[_make_cell(2, glue_type="Type B")])
        svc, *_ = _make_dashboard_service(cells=cells)
        self.assertEqual(svc.get_cell_glue_type(2), "Type B")

    def test_get_cell_glue_type_none_on_missing(self):
        svc, *_ = _make_dashboard_service(cells=_make_cells(1))
        self.assertIsNone(svc.get_cell_glue_type(99))

    def test_get_all_glue_types_returns_names(self):
        catalog = _make_catalog("Type A", "Type B", "Type C")
        svc, *_ = _make_dashboard_service(catalog=catalog)
        self.assertEqual(svc.get_all_glue_types(), ["Type A", "Type B", "Type C"])

    def test_get_all_glue_types_empty_on_error(self):
        ss = MagicMock()
        ss.get.side_effect = RuntimeError("boom")
        svc = GlueDashboardService(runner=_make_runner(), settings_service=ss)
        self.assertEqual(svc.get_all_glue_types(), [])

    def test_get_initial_cell_state_returns_none(self):
        svc, *_ = _make_dashboard_service()
        self.assertIsNone(svc.get_initial_cell_state(1))


# ---------------------------------------------------------------------------
# GlueDashboardService — connection state (weight service integration)
# ---------------------------------------------------------------------------

class TestGlueDashboardServiceConnectionState(unittest.TestCase):

    def test_disconnected_when_no_weight_service(self):
        svc, *_ = _make_dashboard_service(weight_service=None)
        self.assertEqual(svc.get_cell_connection_state(1), "disconnected")

    def test_delegates_to_weight_service_get_cell_state(self):
        ws = MagicMock()
        ws.get_cell_state.return_value = MagicMock(value="connected")
        svc, *_ = _make_dashboard_service(weight_service=ws)
        result = svc.get_cell_connection_state(1)
        ws.get_cell_state.assert_called_once_with(1)
        self.assertEqual(result, "connected")

    def test_disconnected_on_weight_service_exception(self):
        ws = MagicMock()
        ws.get_cell_state.side_effect = RuntimeError("hardware error")
        svc, *_ = _make_dashboard_service(weight_service=ws)
        self.assertEqual(svc.get_cell_connection_state(1), "disconnected")


# ---------------------------------------------------------------------------
# GlueDashboardService — change_glue
# ---------------------------------------------------------------------------

class TestGlueDashboardServiceChangeGlue(unittest.TestCase):

    def _make_svc_with_cells(self, *cell_ids):
        cells = GlueCellsConfig(cells=[_make_cell(cid, glue_type="Type A") for cid in cell_ids])
        ss    = MagicMock()
        ss.get.side_effect = lambda key: cells if key == "glue_cells" else None
        svc   = GlueDashboardService(runner=_make_runner(), settings_service=ss)
        return svc, ss

    def test_change_glue_saves_updated_cells(self):
        svc, ss = self._make_svc_with_cells(1, 2, 3)
        svc.change_glue(1, "Type B")
        ss.save.assert_called_once()
        saved: GlueCellsConfig = ss.save.call_args[0][1]
        self.assertEqual(saved.get_cell_by_id(1).type, "Type B")

    def test_change_glue_only_updates_target_cell(self):
        svc, ss = self._make_svc_with_cells(1, 2, 3)
        svc.change_glue(2, "Type C")
        saved: GlueCellsConfig = ss.save.call_args[0][1]
        self.assertEqual(saved.get_cell_by_id(1).type, "Type A")
        self.assertEqual(saved.get_cell_by_id(2).type, "Type C")
        self.assertEqual(saved.get_cell_by_id(3).type, "Type A")

    def test_change_glue_saves_with_correct_key(self):
        svc, ss = self._make_svc_with_cells(1)
        svc.change_glue(1, "Type B")
        self.assertEqual(ss.save.call_args[0][0], "glue_cells")

    def test_change_glue_missing_cell_does_not_save(self):
        svc, ss = self._make_svc_with_cells(1, 2)
        svc.change_glue(99, "Type B")
        ss.save.assert_not_called()

    def test_change_glue_exception_does_not_propagate(self):
        ss = MagicMock()
        ss.get.side_effect = RuntimeError("db error")
        svc = GlueDashboardService(runner=_make_runner(), settings_service=ss)
        svc.change_glue(1, "Type B")  # must not raise


# ---------------------------------------------------------------------------
# GlueProcess — state machine (comprehensive)
# ---------------------------------------------------------------------------

class TestGlueProcess(unittest.TestCase):

    def _make(self):
        rs = _make_robot_service()
        p  = GlueProcess(robot_service=rs, messaging=_make_messaging(),navigation_service = _make_navigation_service())
        return p, rs

    # ── Basic state transitions ───────────────────────────────────────

    def test_initial_state_idle(self):
        p, _ = self._make()
        self.assertEqual(p.state, ProcessState.IDLE)

    def test_process_id_is_glue(self):
        p, _ = self._make()
        self.assertEqual(p.process_id, "glue")

    def test_start_transitions_to_running(self):
        p, _ = self._make()
        p.start()
        self.assertEqual(p.state, ProcessState.RUNNING)

    def test_stop_from_running_transitions_to_stopped(self):
        p, _ = self._make()
        p.start(); p.stop()
        self.assertEqual(p.state, ProcessState.STOPPED)

    def test_pause_transitions_to_paused(self):
        p, _ = self._make()
        p.start(); p.pause()
        self.assertEqual(p.state, ProcessState.PAUSED)

    def test_resume_from_paused_transitions_to_running(self):
        p, _ = self._make()
        p.start(); p.pause(); p.resume()
        self.assertEqual(p.state, ProcessState.RUNNING)

    def test_restart_from_stopped(self):
        p, rs = self._make()
        p.start(); p.stop()
        rs.reset_mock()
        p.start()
        self.assertEqual(p.state, ProcessState.RUNNING)
        rs.enable_robot.assert_called_once()

    def test_set_error_forces_error_state(self):
        p, _ = self._make()
        p.set_error("motor fault")
        self.assertEqual(p.state, ProcessState.ERROR)

    def test_reset_errors_returns_to_idle(self):
        p, _ = self._make()
        p.set_error(); p.reset_errors()
        self.assertEqual(p.state, ProcessState.IDLE)

    # ── Blocked transitions ───────────────────────────────────────────

    def test_stop_from_idle_is_blocked(self):
        p, _ = self._make()
        p.stop()
        self.assertEqual(p.state, ProcessState.IDLE)

    def test_pause_from_idle_is_blocked(self):
        p, _ = self._make()
        p.pause()
        self.assertEqual(p.state, ProcessState.IDLE)

    # ── Robot service hook calls ──────────────────────────────────────

    def test_start_calls_enable_robot(self):
        p, rs = self._make()
        p.start()
        rs.enable_robot.assert_called_once()

    def test_stop_calls_stop_motion_and_disable_robot(self):
        p, rs = self._make()
        p.start(); p.stop()
        rs.stop_motion.assert_called_once()
        rs.disable_robot.assert_called_once()

    def test_pause_calls_stop_motion(self):
        p, rs = self._make()
        p.start(); p.pause()
        rs.stop_motion.assert_called_once()

    def test_resume_calls_enable_robot(self):
        p, rs = self._make()
        p.start(); p.pause()
        rs.reset_mock()
        p.resume()
        rs.enable_robot.assert_called_once()

    def test_start_from_paused_calls_on_resume_not_on_start(self):
        """start() from PAUSED must call _on_resume (enable_robot), not _on_start."""
        p, rs = self._make()
        p.start(); p.pause()
        rs.reset_mock()
        p.start()          # same as resume when paused
        rs.enable_robot.assert_called_once()
        rs.stop_motion.assert_not_called()  # _on_start only calls enable, not stop

    # ── Hook errors ───────────────────────────────────────────────────

    def test_hook_error_forces_error_state(self):
        rs = _make_robot_service()
        rs.enable_robot.side_effect = RuntimeError("motor fault")
        p  = GlueProcess(robot_service=rs, messaging=_make_messaging(),navigation_service = _make_navigation_service())
        p.start()
        self.assertEqual(p.state, ProcessState.ERROR)

    def test_hook_error_does_not_propagate_to_caller(self):
        rs = _make_robot_service()
        rs.enable_robot.side_effect = RuntimeError("motor fault")
        p  = GlueProcess(robot_service=rs, messaging=_make_messaging(),navigation_service = _make_navigation_service())
        p.start()  # must not raise

    def test_hook_error_publishes_error_event_with_message(self):
        ms = _make_messaging()
        rs = _make_robot_service()
        rs.enable_robot.side_effect = RuntimeError("motor fault")
        p  = GlueProcess(robot_service=rs, messaging=ms,navigation_service = _make_navigation_service())
        p.start()
        published_events = [c.args[1] for c in ms.publish.call_args_list]
        error_events = [e for e in published_events if e.state == ProcessState.ERROR]
        self.assertGreaterEqual(len(error_events), 1)   # published to ACTIVE + specific topic
        self.assertIn("motor fault", error_events[0].message)

    # ── Broker publishing ─────────────────────────────────────────────

    def test_publishes_active_topic_on_start(self):
        ms = _make_messaging()
        p  = GlueProcess(robot_service=_make_robot_service(), messaging=ms,navigation_service = _make_navigation_service())
        p.start()
        topics = [c.args[0] for c in ms.publish.call_args_list]
        self.assertIn(ProcessTopics.ACTIVE, topics)

    def test_publishes_process_specific_topic_on_start(self):
        ms = _make_messaging()
        p  = GlueProcess(robot_service=_make_robot_service(), messaging=ms,navigation_service = _make_navigation_service())
        p.start()
        topics = [c.args[0] for c in ms.publish.call_args_list]
        self.assertIn(ProcessTopics.state(ProcessID.GLUE), topics)

    def test_active_topic_published_before_specific_topic(self):
        ms = _make_messaging()
        p  = GlueProcess(robot_service=_make_robot_service(), messaging=ms,navigation_service = _make_navigation_service())
        p.start()
        topics = [c.args[0] for c in ms.publish.call_args_list]
        self.assertLess(
            topics.index(ProcessTopics.ACTIVE),
            topics.index(ProcessTopics.state(ProcessID.GLUE)),
        )

    # ── System manager ────────────────────────────────────────────────

    def test_system_manager_acquire_blocks_start_when_false(self):
        sm = MagicMock(spec=ISystemManager)
        sm.acquire.return_value = False
        p  = GlueProcess(
            robot_service=_make_robot_service(), messaging=_make_messaging(), system_manager=sm,
            navigation_service=_make_navigation_service()
        )
        p.start()
        self.assertEqual(p.state, ProcessState.IDLE)

    def test_system_manager_acquire_called_with_process_id(self):
        sm = MagicMock(spec=ISystemManager)
        sm.acquire.return_value = True
        p  = GlueProcess(
            robot_service=_make_robot_service(), messaging=_make_messaging(), system_manager=sm,
            navigation_service=_make_navigation_service()
        )
        p.start()
        sm.acquire.assert_called_once_with("glue")

    def test_system_manager_release_called_on_stop(self):
        sm = MagicMock(spec=ISystemManager)
        sm.acquire.return_value = True
        p  = GlueProcess(
            robot_service=_make_robot_service(), messaging=_make_messaging(), system_manager=sm,
        navigation_service = _make_navigation_service()
        )
        p.start(); p.stop()
        sm.release.assert_called_with("glue")

    def test_system_manager_release_called_on_reset_errors_idle(self):
        sm = MagicMock(spec=ISystemManager)
        sm.acquire.return_value = True
        p  = GlueProcess(
            robot_service=_make_robot_service(), messaging=_make_messaging(), system_manager=sm,
            navigation_service=_make_navigation_service()
        )
        p.start(); p.stop(); p.reset_errors()
        # release called at STOPPED and again at IDLE
        release_calls = [c.args[0] for c in sm.release.call_args_list]
        self.assertIn("glue", release_calls)

    # ── ProcessRequirements ───────────────────────────────────────────

    def test_requirements_blocks_start_when_service_missing(self):
        p = GlueProcess(
            robot_service   = _make_robot_service(),
            messaging       = _make_messaging(),
            requirements    = ProcessRequirements.requires("vision"),
            service_checker = lambda _: False,
            navigation_service=_make_navigation_service()
        )
        p.start()
        self.assertEqual(p.state, ProcessState.IDLE)

    def test_requirements_allows_start_when_services_available(self):
        p = GlueProcess(
            robot_service   = _make_robot_service(),
            messaging       = _make_messaging(),
            requirements    = ProcessRequirements.requires("robot"),
            service_checker = lambda _: True,
            navigation_service=_make_navigation_service()
        )
        p.start()
        self.assertEqual(p.state, ProcessState.RUNNING)


if __name__ == "__main__":
    unittest.main()
