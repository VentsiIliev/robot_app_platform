import unittest
from unittest.mock import MagicMock, call

from src.engine.hardware.weight.config import (
    CalibrationConfig, CellConfig, CellsConfig, MeasurementConfig,
)
from src.plugins.glue_cell_settings.model.glue_cell_settings_model import GlueCellSettingsModel


def _calib(offset=0.0, scale=1.0):
    return CalibrationConfig(offset, scale, False)

def _meas():
    return MeasurementConfig(10, 1.0, 5, 0.0, 1000.0)

def _cell(cid):
    return CellConfig(id=cid, type="T", url=f"http://h/w{cid}", capacity=500.0,
                      fetch_timeout_seconds=5.0, data_fetch_interval_ms=500,
                      calibration=_calib(), measurement=_meas())

def _cells(*ids):
    return CellsConfig(cells=[_cell(i) for i in ids])

def _make_service(cell_ids=(0, 1)):
    svc = MagicMock()
    svc.load_cells.return_value      = _cells(*cell_ids)
    svc.save_cells.return_value      = None
    svc.tare.return_value            = True
    svc.push_calibration.return_value = True
    svc.get_cell_ids.return_value    = list(cell_ids)
    return svc


class TestGlueCellSettingsModelLoad(unittest.TestCase):

    def test_load_calls_service(self):
        svc   = _make_service()
        model = GlueCellSettingsModel(svc)
        model.load()
        svc.load_cells.assert_called_once()

    def test_load_returns_cells_config(self):
        svc   = _make_service((0, 1))
        model = GlueCellSettingsModel(svc)
        config = model.load()
        self.assertEqual(config.cell_count, 2)

    def test_load_caches_config(self):
        svc   = _make_service()
        model = GlueCellSettingsModel(svc)
        model.load()
        model.load()
        # service called twice because load() always fetches
        self.assertEqual(svc.load_cells.call_count, 2)


class TestGlueCellSettingsModelGetFlat(unittest.TestCase):

    def test_get_flat_returns_dict(self):
        svc   = _make_service((0,))
        model = GlueCellSettingsModel(svc)
        model.load()
        flat = model.get_cell_flat(0)
        self.assertIsInstance(flat, dict)
        self.assertIn("url", flat)
        self.assertIn("zero_offset", flat)

    def test_get_flat_unknown_cell_returns_none(self):
        svc   = _make_service((0,))
        model = GlueCellSettingsModel(svc)
        model.load()
        self.assertIsNone(model.get_cell_flat(99))

    def test_get_flat_lazy_loads(self):
        svc   = _make_service((0,))
        model = GlueCellSettingsModel(svc)
        # no explicit load() call
        flat = model.get_cell_flat(0)
        self.assertIsNotNone(flat)
        svc.load_cells.assert_called_once()


class TestGlueCellSettingsModelSave(unittest.TestCase):

    def _model_and_svc(self):
        svc   = _make_service((0, 1))
        model = GlueCellSettingsModel(svc)
        model.load()
        return model, svc

    def test_save_calls_save_cells(self):
        model, svc = self._model_and_svc()
        flat = {"url": "http://new", "zero_offset": "2.5", "scale_factor": "0.95",
                "temperature_compensation": "False", "capacity": "500.0",
                "fetch_timeout_seconds": "5.0", "data_fetch_interval_ms": "500",
                "motor_address": "0", "type": "T",
                "sampling_rate": "10", "filter_cutoff": "1.0",
                "averaging_samples": "5", "min_weight_threshold": "0.0",
                "max_weight_threshold": "1000.0"}
        model.save(0, flat)
        svc.save_cells.assert_called_once()

    def test_save_pushes_calibration(self):
        model, svc = self._model_and_svc()
        flat = {"url": "http://x", "zero_offset": "3.0", "scale_factor": "0.9",
                "temperature_compensation": "False", "capacity": "500.0",
                "fetch_timeout_seconds": "5.0", "data_fetch_interval_ms": "500",
                "motor_address": "0", "type": "T",
                "sampling_rate": "10", "filter_cutoff": "1.0",
                "averaging_samples": "5", "min_weight_threshold": "0.0",
                "max_weight_threshold": "1000.0"}
        model.save(0, flat)
        svc.push_calibration.assert_called_once_with(
            cell_id=0, offset=3.0, scale=0.9
        )

    def test_save_updates_cached_config(self):
        model, svc = self._model_and_svc()
        flat = {"url": "http://updated", "zero_offset": "0.0", "scale_factor": "1.0",
                "temperature_compensation": "False", "capacity": "500.0",
                "fetch_timeout_seconds": "5.0", "data_fetch_interval_ms": "500",
                "motor_address": "0", "type": "T",
                "sampling_rate": "10", "filter_cutoff": "1.0",
                "averaging_samples": "5", "min_weight_threshold": "0.0",
                "max_weight_threshold": "1000.0"}
        model.save(0, flat)
        updated = model.get_cell_flat(0)
        self.assertEqual(updated["url"], "http://updated")

    def test_save_unknown_cell_no_call_to_service(self):
        model, svc = self._model_and_svc()
        model.save(99, {"url": "http://x"})
        svc.save_cells.assert_not_called()

    def test_save_does_not_affect_other_cells(self):
        model, svc = self._model_and_svc()
        original_cell1 = model.get_cell_flat(1)
        flat = {"url": "http://changed", "zero_offset": "0.0", "scale_factor": "1.0",
                "temperature_compensation": "False", "capacity": "500.0",
                "fetch_timeout_seconds": "5.0", "data_fetch_interval_ms": "500",
                "motor_address": "0", "type": "T",
                "sampling_rate": "10", "filter_cutoff": "1.0",
                "averaging_samples": "5", "min_weight_threshold": "0.0",
                "max_weight_threshold": "1000.0"}
        model.save(0, flat)
        self.assertEqual(model.get_cell_flat(1)["url"], original_cell1["url"])


class TestGlueCellSettingsModelTare(unittest.TestCase):

    def test_tare_delegates_to_service(self):
        svc   = _make_service((0,))
        model = GlueCellSettingsModel(svc)
        self.assertTrue(model.tare(0))
        svc.tare.assert_called_once_with(0)

    def test_tare_failure_propagates(self):
        svc              = _make_service((0,))
        svc.tare.return_value = False
        model            = GlueCellSettingsModel(svc)
        self.assertFalse(model.tare(0))


class TestGlueCellSettingsModelGetCellIds(unittest.TestCase):

    def test_get_cell_ids_lazy_loads(self):
        svc   = _make_service((0, 1, 2))
        model = GlueCellSettingsModel(svc)
        ids   = model.get_cell_ids()
        self.assertEqual(ids, [0, 1, 2])