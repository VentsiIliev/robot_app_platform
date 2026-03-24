import unittest

from src.engine.hardware.weight.config import (
    CalibrationConfig, MeasurementConfig, CellConfig, CellsConfig, CellsConfigSerializer,
)

def _calib(offset=0.0, scale=1.0):
    return CalibrationConfig(zero_offset=offset, scale_factor=scale)


def _meas(sr=10, fc=1.0, avg=5, mn=0.0, mx=1000.0):
    return MeasurementConfig(sampling_rate=sr, filter_cutoff=fc, averaging_samples=avg,
                             min_weight_threshold=mn, max_weight_threshold=mx)


def _cell(cid=0, url="http://host/w0"):
    return CellConfig(id=cid, type="T", url=url, capacity=500.0,
                      fetch_timeout_seconds=5.0, data_fetch_interval_ms=500,
                      calibration=_calib(), measurement=_meas(), motor_address=0)


class TestCalibrationConfig(unittest.TestCase):

    def test_defaults_from_empty_dict(self):
        c = CalibrationConfig.from_dict({})
        self.assertEqual(c.zero_offset, 0.0)
        self.assertEqual(c.scale_factor, 1.0)

    def test_from_dict_values(self):
        c = CalibrationConfig.from_dict({"zero_offset": 2.5, "scale_factor": 0.98})
        self.assertAlmostEqual(c.zero_offset, 2.5)
        self.assertAlmostEqual(c.scale_factor, 0.98)

    def test_roundtrip(self):
        c = _calib(1.1, 2.2)
        self.assertEqual(CalibrationConfig.from_dict(c.to_dict()), c)

    def test_frozen(self):
        c = _calib()
        with self.assertRaises(Exception):
            c.zero_offset = 9.9  # type: ignore[misc]


class TestMeasurementConfig(unittest.TestCase):

    def test_defaults_from_empty_dict(self):
        m = MeasurementConfig.from_dict({})
        self.assertEqual(m.sampling_rate, 10)
        self.assertAlmostEqual(m.filter_cutoff, 1.0)
        self.assertEqual(m.averaging_samples, 5)

    def test_roundtrip(self):
        m = _meas(20, 5.0, 3, 0.1, 9999.0)
        self.assertEqual(MeasurementConfig.from_dict(m.to_dict()), m)


class TestCellConfig(unittest.TestCase):

    def test_roundtrip(self):
        c = _cell(1, "http://a/w1")
        self.assertEqual(CellConfig.from_dict(c.to_dict()), c)

    def test_from_dict_id_required(self):
        with self.assertRaises(KeyError):
            CellConfig.from_dict({})

    def test_fetch_timeout_default(self):
        c = CellConfig.from_dict({"id": 0})
        self.assertAlmostEqual(c.fetch_timeout_seconds, 5.0)

    def test_data_fetch_interval_default(self):
        c = CellConfig.from_dict({"id": 0})
        self.assertEqual(c.data_fetch_interval_ms, 500)

    def test_motor_address_default(self):
        c = CellConfig.from_dict({"id": 0})
        self.assertEqual(c.motor_address, 0)


class TestCellsConfig(unittest.TestCase):

    def setUp(self):
        self.cells = CellsConfig(cells=[_cell(0), _cell(1), _cell(2)])

    def test_cell_count(self):
        self.assertEqual(self.cells.cell_count, 3)

    def test_get_cell_by_id_found(self):
        self.assertEqual(self.cells.get_cell_by_id(1).id, 1)

    def test_get_cell_by_id_not_found(self):
        self.assertIsNone(self.cells.get_cell_by_id(99))

    def test_get_all_cell_ids(self):
        self.assertEqual(self.cells.get_all_cell_ids(), [0, 1, 2])

    def test_get_cells_by_type(self):
        self.assertEqual(len(self.cells.get_cells_by_type("T")), 3)
        self.assertEqual(len(self.cells.get_cells_by_type("NOPE")), 0)

    def test_roundtrip(self):
        restored = CellsConfig.from_dict(self.cells.to_dict())
        self.assertEqual(restored.cell_count, 3)
        self.assertEqual(restored.get_cell_by_id(0), _cell(0))

    def test_empty(self):
        empty = CellsConfig(cells=[])
        self.assertEqual(empty.cell_count, 0)
        self.assertEqual(empty.get_all_cell_ids(), [])


class TestCellsConfigSerializer(unittest.TestCase):

    def setUp(self):
        self.serializer = CellsConfigSerializer()

    def test_settings_type(self):
        self.assertEqual(self.serializer.settings_type, "cells_config")

    def test_get_default_empty(self):
        d = self.serializer.get_default()
        self.assertEqual(d.cell_count, 0)

    def test_roundtrip(self):
        cells = CellsConfig(cells=[_cell(0), _cell(1)])
        restored = self.serializer.from_dict(self.serializer.to_dict(cells))
        self.assertEqual(restored.cell_count, 2)
        self.assertEqual(restored.get_cell_by_id(0).url, "http://host/w0")
