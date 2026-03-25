import unittest
from unittest.mock import MagicMock

from src.robot_systems.glue.component_ids import SettingsID
from src.engine.hardware.weight.config import (
    CalibrationConfig, CellConfig, CellsConfig, MeasurementConfig,
)
from src.applications.glue_cell_settings.service.glue_cell_settings_service import GlueCellSettingsService


def _cells():
    return CellsConfig(cells=[
        CellConfig(id=0, type="T", url="http://h/w0", capacity=500.0,
                   fetch_timeout_seconds=5.0, data_fetch_interval_ms=500,
                   calibration=CalibrationConfig(0.0, 1.0),
                   measurement=MeasurementConfig(10, 1.0, 5, 0.0, 1000.0)),
    ])


def _make_settings(cells=None):
    ss = MagicMock()
    ss.get.side_effect = lambda key: (cells or _cells()) if key == "glue_cells" else None
    return ss


class TestGlueCellSettingsServiceLoad(unittest.TestCase):

    def test_load_cells_calls_settings_get(self):
        ss  = _make_settings()
        svc = GlueCellSettingsService(ss,SettingsID.GLUE_CELLS,)
        svc.load_cells()
        ss.get.assert_called_once_with("glue_cells")

    def test_load_cells_returns_cells_config(self):
        svc = GlueCellSettingsService(_make_settings(),SettingsID.GLUE_CELLS,)
        self.assertEqual(svc.load_cells().cell_count, 1)


class TestGlueCellSettingsServiceSave(unittest.TestCase):

    def test_save_calls_settings_save(self):
        ss  = _make_settings()
        svc = GlueCellSettingsService(ss,SettingsID.GLUE_CELLS,)
        cfg = _cells()
        svc.save_cells(cfg)
        ss.save.assert_called_once_with("glue_cells", cfg)


class TestGlueCellSettingsServiceTare(unittest.TestCase):

    def test_tare_with_no_weight_service_returns_false(self):
        svc = GlueCellSettingsService(_make_settings(), SettingsID.GLUE_CELLS,weight_service=None)
        self.assertFalse(svc.tare(0))

    def test_tare_delegates_to_weight_service(self):
        ws = MagicMock()
        ws.tare.return_value = True
        svc = GlueCellSettingsService(_make_settings(), SettingsID.GLUE_CELLS,weight_service=ws)
        self.assertTrue(svc.tare(0))
        ws.tare.assert_called_once_with(0)

    def test_tare_propagates_false(self):
        ws = MagicMock()
        ws.tare.return_value = False
        svc = GlueCellSettingsService(_make_settings(),settings_key= SettingsID.GLUE_CELLS, weight_service=ws)
        self.assertFalse(svc.tare(0))


class TestGlueCellSettingsServicePushCalibration(unittest.TestCase):

    def test_push_with_no_weight_service_returns_false(self):
        svc = GlueCellSettingsService(_make_settings(), SettingsID.GLUE_CELLS,weight_service=None)
        self.assertFalse(svc.push_calibration(0, 1.0, 2.0))

    def test_push_delegates_to_update_config(self):
        ws = MagicMock()
        ws.update_config.return_value = True
        svc = GlueCellSettingsService(_make_settings(), SettingsID.GLUE_CELLS,weight_service=ws)
        result = svc.push_calibration(0, 1.5, 0.98)
        self.assertTrue(result)
        ws.update_config.assert_called_once_with(0, 1.5, 0.98)

    def test_push_propagates_false(self):
        ws = MagicMock()
        ws.update_config.return_value = False
        svc = GlueCellSettingsService(_make_settings(), SettingsID.GLUE_CELLS,weight_service=ws)
        self.assertFalse(svc.push_calibration(0, 0.0, 1.0))


class TestGlueCellSettingsServiceGetCellIds(unittest.TestCase):

    def test_get_cell_ids(self):
        svc = GlueCellSettingsService(_make_settings(),SettingsID.GLUE_CELLS)
        self.assertEqual(svc.get_cell_ids(), [0])

    def test_get_cell_ids_settings_exception_returns_empty(self):
        ss = MagicMock()
        ss.get.side_effect = RuntimeError("db error")
        svc = GlueCellSettingsService(ss,SettingsID.GLUE_CELLS,)
        self.assertEqual(svc.get_cell_ids(), [])