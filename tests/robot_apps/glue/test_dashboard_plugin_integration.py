import unittest
from unittest.mock import MagicMock, patch, call
from dataclasses import replace

from src.plugins.base.widget_plugin import WidgetPlugin
from src.robot_apps.glue.dashboard.service.glue_dashboard_service import GlueDashboardService
from src.robot_apps.glue.glue_robot_app import GlueRobotApp
from src.robot_apps.glue.settings.cells import (
    GlueCellsConfig, CellConfig, CalibrationConfig, MeasurementConfig,
)
from src.robot_apps.glue.settings.glue_types import Glue, GlueCatalog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cell(cell_id: int, glue_type: str = "Type A", capacity: float = 5000.0) -> CellConfig:
    return CellConfig(
        id=cell_id,
        type=glue_type,
        url=f"http://cell{cell_id}",
        capacity=capacity,
        fetch_timeout_seconds=5.0,
        data_fetch_interval_ms=500,
        calibration=CalibrationConfig(zero_offset=0.0, scale_factor=1.0, temperature_compensation=False),
        measurement=MeasurementConfig(
            sampling_rate=10, filter_cutoff=1.0, averaging_samples=5,
            min_weight_threshold=0.0, max_weight_threshold=10000.0,
        ),
    )

def _make_messaging():
    return MagicMock()


def _make_cells(*cell_ids: int) -> GlueCellsConfig:
    return GlueCellsConfig(cells=[_make_cell(cid) for cid in cell_ids])


def _make_catalog(*names: str) -> GlueCatalog:
    return GlueCatalog(glue_types=[Glue(name=n) for n in names])


def _make_settings_service(cells=None, catalog=None):
    ss = MagicMock()
    _cells   = cells   or _make_cells(1, 2, 3)
    _catalog = catalog or _make_catalog("Type A", "Type B")
    ss.get.side_effect = lambda key: (
        _cells   if key == "glue_cells"   else
        _catalog if key == "glue_catalog" else None
    )
    return ss, _cells, _catalog


def _make_robot_service():
    rs = MagicMock()
    return rs


def _make_dashboard_service(cells=None, catalog=None):
    _cells   = cells   or _make_cells(1, 2, 3)
    _catalog = catalog or _make_catalog("Type A", "Type B")
    rs = _make_robot_service()
    ss, _cells, _catalog = _make_settings_service(_cells, _catalog)  # unpack correctly
    svc = GlueDashboardService(
        process_id       = "test_dashboard",
        robot_service    = rs,
        settings_service = ss,
        messaging        = _make_messaging(),
    )
    return svc, rs, ss, _cells, _catalog



def _make_robot_app(cells=None, catalog=None):
    ss, _, _ = _make_settings_service(cells, catalog)
    rs = _make_robot_service()
    app = MagicMock()
    app.get_service.return_value  = rs
    app._settings_service         = ss
    return app, rs, ss


# ---------------------------------------------------------------------------
# PluginSpec declaration
# ---------------------------------------------------------------------------

class TestDashboardPluginSpec(unittest.TestCase):

    def _spec(self):
        return next(
            (s for s in GlueRobotApp.shell.plugins if s.name == "GlueDashboard"),
            None,
        )

    def test_spec_declared(self):
        self.assertIsNotNone(self._spec(), "GlueDashboard PluginSpec missing from GlueRobotApp.shell.plugins")

    def test_spec_folder_id(self):
        self.assertEqual(self._spec().folder_id, 1)

    def test_spec_has_factory(self):
        self.assertIsNotNone(self._spec().factory)

    def test_spec_icon_set(self):
        self.assertIsNotNone(self._spec().icon)


# ---------------------------------------------------------------------------
# Factory builds a WidgetPlugin
# ---------------------------------------------------------------------------

class TestDashboardPluginFactory(unittest.TestCase):

    def _build(self, cells=None, catalog=None):
        app, rs, ss = _make_robot_app(cells, catalog)
        spec        = next(s for s in GlueRobotApp.shell.plugins if s.name == "GlueDashboard")
        plugin      = spec.factory(app)
        return plugin, rs, ss

    def test_factory_returns_widget_plugin(self):
        plugin, _, _ = self._build()
        self.assertIsInstance(plugin, WidgetPlugin)

    def test_factory_requests_robot_service(self):
        app, rs, ss = _make_robot_app()
        spec = next(s for s in GlueRobotApp.shell.plugins if s.name == "GlueDashboard")
        spec.factory(app)
        app.get_service.assert_called_with("robot")

    def test_register_stores_messaging_service(self):
        plugin, _, _ = self._build()
        ms = MagicMock()
        plugin.register(ms)
        self.assertIs(plugin._messaging_service, ms)

    def test_widget_factory_forwards_messaging_service(self):
        plugin, _, _ = self._build()
        ms = MagicMock()
        plugin.register(ms)
        with patch(
            "src.robot_apps.glue.dashboard.glue_dashboard.GlueDashboard.create"
        ) as mock_create:
            mock_create.return_value = MagicMock()
            plugin.create_widget()
            _, kwargs = mock_create.call_args
            self.assertIs(kwargs.get("messaging_service"), ms)


# ---------------------------------------------------------------------------
# GlueDashboardService — commands
# ---------------------------------------------------------------------------

class TestGlueDashboardServiceCommands(unittest.TestCase):

    def test_start_calls_enable_robot(self):
        svc, rs, *_ = _make_dashboard_service()
        svc.start()
        rs.enable_robot.assert_called_once()

    # test_stop_calls_stop_motion
    def test_stop_calls_stop_motion(self):
        svc, rs, *_ = _make_dashboard_service()
        svc.start()  # ← must be in RUNNING state before stop() is valid
        svc.stop()
        rs.stop_motion.assert_called_once()

    # test_stop_calls_disable_robot
    def test_stop_calls_disable_robot(self):
        svc, rs, *_ = _make_dashboard_service()
        svc.start()
        svc.stop()
        rs.disable_robot.assert_called_once()

    # test_pause_calls_stop_motion
    def test_pause_calls_stop_motion(self):
        svc, rs, *_ = _make_dashboard_service()
        svc.start()  # ← must be RUNNING before pause() is valid
        svc.pause()
        rs.stop_motion.assert_called_once()

    def test_clean_does_not_raise(self):
        svc, *_ = _make_dashboard_service()
        svc.clean()   # no-op, must not raise

    def test_reset_errors_does_not_raise(self):
        svc, *_ = _make_dashboard_service()
        svc.reset_errors()

    def test_set_mode_does_not_raise(self):
        svc, *_ = _make_dashboard_service()
        svc.set_mode("spray_only")


# ---------------------------------------------------------------------------
# GlueDashboardService — queries
# ---------------------------------------------------------------------------

class TestGlueDashboardServiceQueries(unittest.TestCase):

    def test_get_cells_count_correct(self):
        cells = _make_cells(1, 2, 3)
        svc, *_ = _make_dashboard_service(cells=cells)
        self.assertEqual(svc.get_cells_count(), 3)

    def test_get_cells_count_single(self):
        svc, *_ = _make_dashboard_service(cells=_make_cells(1))
        self.assertEqual(svc.get_cells_count(), 1)

    def test_get_cells_count_returns_zero_on_error(self):
        rs = _make_robot_service()
        ss = MagicMock()
        ss.get.side_effect = RuntimeError("boom")
        svc = GlueDashboardService(
            process_id="test_dashboard",
            robot_service=rs,
            settings_service=ss,
            messaging=MagicMock(),
        )

        self.assertEqual(svc.get_cells_count(), 0)

    def test_get_cell_capacity_returns_correct_value(self):
        cell  = _make_cell(1, capacity=9999.0)
        cells = GlueCellsConfig(cells=[cell])
        svc, *_ = _make_dashboard_service(cells=cells)
        self.assertEqual(svc.get_cell_capacity(1), 9999.0)

    def test_get_cell_capacity_fallback_on_missing_cell(self):
        svc, *_ = _make_dashboard_service(cells=_make_cells(1))
        self.assertEqual(svc.get_cell_capacity(99), 0.0)

    def test_get_cell_capacity_fallback_on_error(self):
        rs = _make_robot_service()
        ss = MagicMock()
        ss.get.side_effect = RuntimeError("boom")
        # Replace every bare instantiation with:
        svc = GlueDashboardService(
            process_id="test_dashboard",
            robot_service=rs,
            settings_service=ss,
            messaging=MagicMock(),
        )

        self.assertEqual(svc.get_cell_capacity(1), 0.0)


    def test_get_cell_glue_type_correct(self):
        cell  = _make_cell(2, glue_type="Type B")
        cells = GlueCellsConfig(cells=[cell])
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
        rs = _make_robot_service()
        ss = MagicMock()
        ss.get.side_effect = RuntimeError("boom")
        # Replace every bare instantiation with:
        svc = GlueDashboardService(
            process_id="test_dashboard",
            robot_service=rs,
            settings_service=ss,
            messaging=MagicMock(),
        )

        self.assertEqual(svc.get_all_glue_types(), [])

    def test_get_initial_cell_state_returns_none(self):
        svc, *_ = _make_dashboard_service()
        self.assertIsNone(svc.get_initial_cell_state(1))


# ---------------------------------------------------------------------------
# GlueDashboardService — change_glue
# ---------------------------------------------------------------------------

class TestGlueDashboardServiceChangeGlue(unittest.TestCase):

    def _make_svc_with_cells(self, *cell_ids):
        cells = GlueCellsConfig(cells=[_make_cell(cid, glue_type="Type A") for cid in cell_ids])
        ss    = MagicMock()
        ss.get.side_effect = lambda key: cells if key == "glue_cells" else None
        rs  = _make_robot_service()
        # Replace every bare instantiation with:
        svc = GlueDashboardService(
            process_id="test_dashboard",
            robot_service=rs,
            settings_service=ss,
            messaging=MagicMock(),
        )

        return svc, ss, cells

    def test_change_glue_saves_updated_cells(self):
        svc, ss, _ = self._make_svc_with_cells(1, 2, 3)
        svc.change_glue(1, "Type B")
        ss.save.assert_called_once()
        saved_cells: GlueCellsConfig = ss.save.call_args[0][1]
        self.assertEqual(saved_cells.get_cell_by_id(1).type, "Type B")

    def test_change_glue_only_updates_target_cell(self):
        svc, ss, _ = self._make_svc_with_cells(1, 2, 3)
        svc.change_glue(2, "Type C")
        saved_cells: GlueCellsConfig = ss.save.call_args[0][1]
        self.assertEqual(saved_cells.get_cell_by_id(1).type, "Type A")
        self.assertEqual(saved_cells.get_cell_by_id(2).type, "Type C")
        self.assertEqual(saved_cells.get_cell_by_id(3).type, "Type A")

    def test_change_glue_saves_with_correct_key(self):
        svc, ss, _ = self._make_svc_with_cells(1)
        svc.change_glue(1, "Type B")
        saved_key = ss.save.call_args[0][0]
        self.assertEqual(saved_key, "glue_cells")

    def test_change_glue_missing_cell_does_not_save(self):
        svc, ss, _ = self._make_svc_with_cells(1, 2)
        svc.change_glue(99, "Type B")  # cell 99 does not exist
        ss.save.assert_not_called()

    def test_change_glue_exception_does_not_propagate(self):
        rs = _make_robot_service()
        ss = MagicMock()
        ss.get.side_effect = RuntimeError("db error")
        # Replace every bare instantiation with:
        svc = GlueDashboardService(
            process_id="test_dashboard",
            robot_service=rs,
            settings_service=ss,
            messaging=MagicMock(),
        )

        svc.change_glue(1, "Type B")  # must not raise


if __name__ == "__main__":
    unittest.main()