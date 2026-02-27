import unittest
from unittest.mock import MagicMock, patch

from src.robot_systems.glue.settings_ids import SettingsID
from src.robot_systems.glue.service_ids import ServiceID
from src.engine.hardware.weight.config import (
    CalibrationConfig, CellConfig, CellsConfig, MeasurementConfig,
)
from src.applications.base.widget_application import WidgetApplication
from src.robot_systems.glue.glue_robot_system import GlueRobotSystem
from src.robot_systems.glue.settings.cells import GlueCellsConfigSerializer


# ── Helpers ──────────────────────────────────────────────────────────────────

def _calib():
    return CalibrationConfig(0.0, 1.0, False)

def _meas():
    return MeasurementConfig(10, 1.0, 5, 0.0, 1000.0)

def _cell(cid):
    return CellConfig(id=cid, type="T", url=f"http://h/w{cid}", capacity=500.0,
                      fetch_timeout_seconds=5.0, data_fetch_interval_ms=500,
                      calibration=_calib(), measurement=_meas())

def _cells(*ids):
    return CellsConfig(cells=[_cell(i) for i in ids])

def _make_robot_system(cells=None):
    cfg = cells or _cells(0, 1, 2)
    ss  = MagicMock()
    ss.get.side_effect = lambda key: cfg if key == "glue_cells" else MagicMock()
    app                   = MagicMock()
    app._settings_service = ss
    app.get_service.return_value          = MagicMock()
    app.get_optional_service.return_value = MagicMock()
    return app

def _spec():
    return next(
        (s for s in GlueRobotSystem.shell.applications if s.name == "CellSettings"),
        None,
    )


# ---------------------------------------------------------------------------
# ApplicationSpec declaration
# ---------------------------------------------------------------------------

class TestGlueCellSettingsApplicationSpec(unittest.TestCase):

    def test_spec_declared(self):
        self.assertIsNotNone(_spec(), "CellSettings ApplicationSpec missing from GlueRobotSystem.shell.applications")

    def test_spec_folder_id(self):
        self.assertEqual(_spec().folder_id, 2)

    def test_spec_has_factory(self):
        self.assertIsNotNone(_spec().factory)

    def test_spec_icon_set(self):
        self.assertIsNotNone(_spec().icon)

    def test_spec_name(self):
        self.assertEqual(_spec().name, "CellSettings")


# ---------------------------------------------------------------------------
# Factory — WidgetApplication construction
# ---------------------------------------------------------------------------

class TestGlueCellSettingsApplicationFactory(unittest.TestCase):

    def test_factory_returns_widget_application(self):
        application = _spec().factory(_make_robot_system())
        self.assertIsInstance(application, WidgetApplication)

    def test_factory_passes_weight_service(self):
        app = _make_robot_system()
        _spec().factory(app)
        app.get_optional_service.assert_any_call(ServiceID.WEIGHT)

    def test_factory_works_without_weight_service(self):
        app = _make_robot_system()
        app.get_optional_service.return_value = None   # no weight hardware
        application = _spec().factory(app)
        self.assertIsInstance(application, WidgetApplication)

    def test_widget_factory_callable(self):
        application = _spec().factory(_make_robot_system())
        ms     = MagicMock()
        with patch(
            "src.applications.glue_cell_settings.glue_cell_settings_factory.GlueCellSettingsFactory.build",
            return_value=MagicMock(),
        ) as mock_build:
            application._widget_factory(ms)
            mock_build.assert_called_once()


# ---------------------------------------------------------------------------
# SettingsSpec — glue_cells
# ---------------------------------------------------------------------------

class TestGlueCellsSettingsSpec(unittest.TestCase):

    def _spec(self):
        return next(
            (s for s in GlueRobotSystem.settings_specs if s.name == "glue_cells"),  # ← name, not storage_key
            None,
        )

    def test_spec_declared(self):
        self.assertIsNotNone(self._spec(), "glue_cells SettingsSpec missing")

    def test_spec_serializer_type(self):
        self.assertIsInstance(self._spec().serializer, GlueCellsConfigSerializer)

    def test_spec_path(self):
        self.assertEqual(self._spec().storage_key, "glue/cells.json")   # ← storage_key, not path

    def test_serializer_default_has_cells(self):
        default = self._spec().serializer.get_default()
        self.assertGreater(default.cell_count, 0)

    def test_serializer_roundtrip(self):
        ser      = self._spec().serializer
        cells    = _cells(0, 1, 2)
        restored = ser.from_dict(ser.to_dict(cells))
        self.assertEqual(restored.cell_count, 3)
        self.assertEqual(restored.get_cell_by_id(0).id, 0)

    def test_serializer_settings_type(self):
        self.assertEqual(self._spec().serializer.settings_type, "glue_cells")


# ---------------------------------------------------------------------------
# ServiceSpec — weight
# ---------------------------------------------------------------------------

class TestWeightServiceSpec(unittest.TestCase):

    def _spec(self):
        return next(
            (s for s in GlueRobotSystem.services if s.name == ServiceID.WEIGHT),
            None,
        )

    def test_weight_service_spec_declared(self):
        self.assertIsNotNone(self._spec(), "weight ServiceSpec missing")

    def test_weight_service_optional(self):
        self.assertTrue(self._spec().required)

    def test_weight_service_has_builder(self):
        self.assertIsNotNone(self._spec().builder)


# ---------------------------------------------------------------------------
# End-to-end: service → save → push_calibration
# ---------------------------------------------------------------------------

class TestGlueCellSettingsServiceSaveAndPush(unittest.TestCase):

    def test_save_persists_and_pushes(self):
        from src.applications.glue_cell_settings.service.glue_cell_settings_service import GlueCellSettingsService
        from src.applications.glue_cell_settings.model.glue_cell_settings_model import GlueCellSettingsModel
        from src.applications.glue_cell_settings.model.mapper import GlueCellMapper

        cells_cfg = _cells(0)
        ss        = MagicMock()
        ss.get.return_value  = cells_cfg
        ws        = MagicMock()
        ws.update_config.return_value = True

        svc   = GlueCellSettingsService(ss,settings_key=SettingsID.GLUE_CELLS, weight_service=ws)
        model = GlueCellSettingsModel(svc)
        model.load()

        flat = GlueCellMapper.cell_to_flat(_cell(0))
        flat["zero_offset"]  = "3.14"
        flat["scale_factor"] = "0.99"

        model.save(0, flat)

        ss.save.assert_called_once()
        ws.update_config.assert_called_once_with(0, 3.14, 0.99)

    def test_save_without_weight_service_still_persists(self):
        from src.applications.glue_cell_settings.service.glue_cell_settings_service import GlueCellSettingsService
        from src.applications.glue_cell_settings.model.glue_cell_settings_model import GlueCellSettingsModel
        from src.applications.glue_cell_settings.model.mapper import GlueCellMapper

        cells_cfg = _cells(0)
        ss        = MagicMock()
        ss.get.return_value = cells_cfg

        svc   = GlueCellSettingsService(ss,settings_key=SettingsID.GLUE_CELLS, weight_service=None)
        model = GlueCellSettingsModel(svc)
        model.load()

        flat = GlueCellMapper.cell_to_flat(_cell(0))
        model.save(0, flat)

        ss.save.assert_called_once()   # settings persisted even without hardware