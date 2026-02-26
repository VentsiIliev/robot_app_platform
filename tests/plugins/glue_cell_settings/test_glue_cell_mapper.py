import unittest

from src.engine.hardware.weight.config import (
    CalibrationConfig, CellConfig, CellsConfig, MeasurementConfig,
)
from src.plugins.glue_cell_settings.model.mapper import GlueCellMapper


def _cell():
    return CellConfig(
        id=0, type="TypeA", url="http://host/w0", capacity=1000.0,
        fetch_timeout_seconds=5.0, data_fetch_interval_ms=500,
        calibration=CalibrationConfig(1.5, 0.97, True),
        measurement=MeasurementConfig(20, 5.0, 3, 0.1, 9999.0),
        motor_address=2,
    )


class TestGlueCellMapperToFlat(unittest.TestCase):

    def setUp(self):
        self.flat = GlueCellMapper.cell_to_flat(_cell())

    def test_url(self):            self.assertEqual(self.flat["url"], "http://host/w0")
    def test_type(self):           self.assertEqual(self.flat["type"], "TypeA")
    def test_capacity(self):       self.assertAlmostEqual(self.flat["capacity"], 1000.0)
    def test_fetch_timeout(self):  self.assertAlmostEqual(self.flat["fetch_timeout_seconds"], 5.0)
    def test_interval_ms(self):    self.assertEqual(self.flat["data_fetch_interval_ms"], 500)
    def test_motor_address(self):  self.assertEqual(self.flat["motor_address"], 2)
    def test_zero_offset(self):    self.assertAlmostEqual(self.flat["zero_offset"], 1.5)
    def test_scale_factor(self):   self.assertAlmostEqual(self.flat["scale_factor"], 0.97)
    def test_temp_comp(self):      self.assertTrue(self.flat["temperature_compensation"])
    def test_sampling_rate(self):  self.assertEqual(self.flat["sampling_rate"], 20)
    def test_filter_cutoff(self):  self.assertAlmostEqual(self.flat["filter_cutoff"], 5.0)
    def test_averaging(self):      self.assertEqual(self.flat["averaging_samples"], 3)
    def test_min_threshold(self):  self.assertAlmostEqual(self.flat["min_weight_threshold"], 0.1)
    def test_max_threshold(self):  self.assertAlmostEqual(self.flat["max_weight_threshold"], 9999.0)


class TestGlueCellMapperFromFlat(unittest.TestCase):

    def setUp(self):
        self.original = _cell()
        self.flat     = GlueCellMapper.cell_to_flat(self.original)
        self.restored = GlueCellMapper.flat_to_cell(self.flat, self.original)

    def test_roundtrip_url(self):           self.assertEqual(self.restored.url, self.original.url)
    def test_roundtrip_type(self):          self.assertEqual(self.restored.type, self.original.type)
    def test_roundtrip_capacity(self):      self.assertAlmostEqual(self.restored.capacity, self.original.capacity)
    def test_roundtrip_timeout(self):       self.assertAlmostEqual(self.restored.fetch_timeout_seconds, self.original.fetch_timeout_seconds)
    def test_roundtrip_interval(self):      self.assertEqual(self.restored.data_fetch_interval_ms, self.original.data_fetch_interval_ms)
    def test_roundtrip_motor(self):         self.assertEqual(self.restored.motor_address, self.original.motor_address)
    def test_roundtrip_zero_offset(self):   self.assertAlmostEqual(self.restored.calibration.zero_offset, 1.5)
    def test_roundtrip_scale_factor(self):  self.assertAlmostEqual(self.restored.calibration.scale_factor, 0.97)
    def test_roundtrip_temp_comp(self):     self.assertTrue(self.restored.calibration.temperature_compensation)
    def test_roundtrip_sampling_rate(self): self.assertEqual(self.restored.measurement.sampling_rate, 20)
    def test_roundtrip_max_threshold(self): self.assertAlmostEqual(self.restored.measurement.max_weight_threshold, 9999.0)

    def test_partial_flat_uses_original_fallback(self):
        restored = GlueCellMapper.flat_to_cell({"url": "http://new"}, self.original)
        self.assertEqual(restored.url, "http://new")
        self.assertAlmostEqual(restored.calibration.zero_offset, self.original.calibration.zero_offset)

    def test_temp_comp_false_string(self):
        flat = dict(self.flat)
        flat["temperature_compensation"] = "False"
        restored = GlueCellMapper.flat_to_cell(flat, self.original)
        self.assertFalse(restored.calibration.temperature_compensation)

    def test_temp_comp_true_string(self):
        flat = dict(self.flat)
        flat["temperature_compensation"] = "True"
        restored = GlueCellMapper.flat_to_cell(flat, self.original)
        self.assertTrue(restored.calibration.temperature_compensation)