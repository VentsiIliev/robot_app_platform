import threading
import time
import unittest
from unittest.mock import MagicMock, call

from src.engine.hardware.weight.config import (
    CalibrationConfig, CellConfig, CellsConfig, MeasurementConfig,
)
from src.engine.hardware.weight.weight_cell_service import WeightCellService
from src.shared_contracts.events.weight_events import CellState, CellStateEvent, WeightReading, WeightTopics


def _calib():
    return CalibrationConfig(0.0, 1.0, False)

def _meas():
    return MeasurementConfig(10, 1.0, 5, 0.0, 1000.0)

def _cell(cid):
    return CellConfig(id=cid, type="T", url=f"http://h/w{cid}", capacity=500.0,
                      fetch_timeout_seconds=5.0, data_fetch_interval_ms=100,
                      calibration=_calib(), measurement=_meas())

def _cells(*ids):
    return CellsConfig(cells=[_cell(i) for i in ids])

def _make_transport(connect_ok=True, weight=42.0):
    t = MagicMock()
    t.connect.return_value    = connect_ok
    t.read_weight.return_value = weight
    t.disconnect.return_value = None
    return t

def _make_calibrator(tare_ok=True, update_ok=True):
    c = MagicMock()
    c.tare.return_value          = tare_ok
    c.update_offset.return_value = update_ok
    c.update_scale.return_value  = update_ok
    c.update_config.return_value = update_ok
    c.get_config.return_value    = _calib()
    return c

def _make_service(cell_ids=(0,), connect_ok=True, weight=42.0):
    transports   = {i: _make_transport(connect_ok, weight) for i in cell_ids}
    calibrators  = {i: _make_calibrator() for i in cell_ids}
    messaging    = MagicMock()
    svc = WeightCellService(
        cells_config       = _cells(*cell_ids),
        transport_factory  = lambda cfg: transports[cfg.id],
        calibrator_factory = lambda cfg: calibrators[cfg.id],
        messaging          = messaging,
    )
    return svc, transports, calibrators, messaging


# ---------------------------------------------------------------------------
class TestWeightCellServiceInit(unittest.TestCase):

    def test_creates_context_per_cell(self):
        svc, *_ = _make_service((0, 1, 2))
        self.assertEqual(len(svc._cells), 3)

    def test_initial_state_disconnected(self):
        svc, *_ = _make_service((0,))
        self.assertEqual(svc.get_cell_state(0), CellState.DISCONNECTED)

    def test_unknown_cell_returns_disconnected(self):
        svc, *_ = _make_service((0,))
        self.assertEqual(svc.get_cell_state(99), CellState.DISCONNECTED)


# ---------------------------------------------------------------------------
class TestWeightCellServiceConnect(unittest.TestCase):

    def test_connect_success(self):
        svc, transports, _, messaging = _make_service((0,), connect_ok=True)
        result = svc.connect(0)
        self.assertTrue(result)
        self.assertEqual(svc.get_cell_state(0), CellState.CONNECTED)

    def test_connect_failure(self):
        svc, *_ = _make_service((0,), connect_ok=False)
        result = svc.connect(0)
        self.assertFalse(result)
        self.assertEqual(svc.get_cell_state(0), CellState.ERROR)

    def test_connect_unknown_cell_returns_false(self):
        svc, *_ = _make_service((0,))
        self.assertFalse(svc.connect(99))

    def test_connect_publishes_connecting_then_connected(self):
        svc, _, _, messaging = _make_service((0,))
        svc.connect(0)
        topics = [c.args[0] for c in messaging.publish.call_args_list]
        self.assertIn(WeightTopics.state(0), topics)

    def test_connect_transport_exception_sets_error(self):
        svc, transports, _, _ = _make_service((0,))
        transports[0].connect.side_effect = RuntimeError("boom")
        svc.connect(0)
        self.assertEqual(svc.get_cell_state(0), CellState.ERROR)

    def test_disconnect_sets_disconnected(self):
        svc, *_ = _make_service((0,))
        svc.connect(0)
        svc.disconnect(0)
        self.assertEqual(svc.get_cell_state(0), CellState.DISCONNECTED)

    def test_disconnect_unknown_cell_no_raise(self):
        svc, *_ = _make_service((0,))
        svc.disconnect(99)  # must not raise

    def test_disconnect_all(self):
        svc, *_ = _make_service((0, 1))
        svc.connect(0); svc.connect(1)
        svc.disconnect_all()
        self.assertEqual(svc.get_cell_state(0), CellState.DISCONNECTED)
        self.assertEqual(svc.get_cell_state(1), CellState.DISCONNECTED)

    def test_get_connected_cell_ids(self):
        svc, *_ = _make_service((0, 1))
        svc.connect(0)
        self.assertEqual(svc.get_connected_cell_ids(), [0])


# ---------------------------------------------------------------------------
class TestWeightCellServiceRead(unittest.TestCase):

    def test_read_weight_when_connected(self):
        svc, *_ = _make_service((0,), weight=123.4)
        svc.connect(0)
        reading = svc.read_weight(0)
        self.assertIsNotNone(reading)
        self.assertAlmostEqual(reading.value, 123.4)
        self.assertEqual(reading.cell_id, 0)

    def test_read_weight_when_disconnected_returns_none(self):
        svc, *_ = _make_service((0,))
        self.assertIsNone(svc.read_weight(0))

    def test_read_weight_unknown_cell_returns_none(self):
        svc, *_ = _make_service((0,))
        svc.connect(0)
        self.assertIsNone(svc.read_weight(99))

    def test_read_weight_publishes_reading_topic(self):
        svc, _, _, messaging = _make_service((0,))
        svc.connect(0)
        messaging.publish.reset_mock()
        svc.read_weight(0)
        topics = [c.args[0] for c in messaging.publish.call_args_list]
        self.assertIn(WeightTopics.reading(0), topics)
        self.assertIn(WeightTopics.all_readings(), topics)

    def test_read_weight_transport_exception_sets_error(self):
        svc, transports, _, _ = _make_service((0,))
        svc.connect(0)
        transports[0].read_weight.side_effect = RuntimeError("timeout")
        svc.read_weight(0)
        self.assertEqual(svc.get_cell_state(0), CellState.ERROR)


# ---------------------------------------------------------------------------
class TestWeightCellServiceCalibration(unittest.TestCase):

    def test_tare_delegates_to_calibrator(self):
        svc, _, calibrators, _ = _make_service((0,))
        self.assertTrue(svc.tare(0))
        calibrators[0].tare.assert_called_once_with(0)

    def test_tare_unknown_cell_returns_false(self):
        svc, *_ = _make_service((0,))
        self.assertFalse(svc.tare(99))

    def test_tare_exception_returns_false(self):
        svc, _, calibrators, _ = _make_service((0,))
        calibrators[0].tare.side_effect = RuntimeError("fail")
        self.assertFalse(svc.tare(0))

    def test_update_offset(self):
        svc, _, calibrators, _ = _make_service((0,))
        self.assertTrue(svc.update_offset(0, 1.5))
        calibrators[0].update_offset.assert_called_once_with(0, 1.5)

    def test_update_scale(self):
        svc, _, calibrators, _ = _make_service((0,))
        self.assertTrue(svc.update_scale(0, 0.98))
        calibrators[0].update_scale.assert_called_once_with(0, 0.98)

    def test_update_config(self):
        svc, _, calibrators, _ = _make_service((0,))
        self.assertTrue(svc.update_config(0, 1.1, 0.99))
        calibrators[0].update_config.assert_called_once_with(0, 1.1, 0.99)

    def test_update_config_unknown_cell_returns_false(self):
        svc, *_ = _make_service((0,))
        self.assertFalse(svc.update_config(99, 1.0, 1.0))

    def test_get_calibration(self):
        svc, _, calibrators, _ = _make_service((0,))
        result = svc.get_calibration(0)
        self.assertEqual(result, _calib())

    def test_get_calibration_unknown_returns_none(self):
        svc, *_ = _make_service((0,))
        self.assertIsNone(svc.get_calibration(99))


# ---------------------------------------------------------------------------
class TestWeightCellServiceMonitoring(unittest.TestCase):

    def test_start_monitoring_spawns_thread(self):
        svc, *_ = _make_service((0,))
        svc.start_monitoring([0], interval_s=0.05)
        self.assertTrue(svc._cells[0].monitoring)
        svc.stop_monitoring()

    def test_start_monitoring_idempotent(self):
        svc, *_ = _make_service((0,))
        svc.start_monitoring([0], interval_s=0.05)
        thread_before = svc._cells[0].monitor_thread
        svc.start_monitoring([0], interval_s=0.05)  # second call — no new thread
        self.assertIs(svc._cells[0].monitor_thread, thread_before)
        svc.stop_monitoring()

    def test_stop_monitoring_clears_flag(self):
        svc, *_ = _make_service((0,))
        svc.start_monitoring([0], interval_s=0.05)
        svc.stop_monitoring()
        self.assertFalse(svc._cells[0].monitoring)
        self.assertIsNone(svc._cells[0].monitor_thread)

    def test_monitoring_uses_cell_interval(self):
        """data_fetch_interval_ms=100 → thread sleeps 0.1s per iteration."""
        svc, _, _, messaging = _make_service((0,), weight=7.0)
        svc.connect(0)
        messaging.publish.reset_mock()
        svc.start_monitoring([0], interval_s=10.0)  # fallback=10s, cell override=0.1s
        time.sleep(0.35)
        svc.stop_monitoring()
        reading_calls = [
            c for c in messaging.publish.call_args_list
            if c.args[0] == WeightTopics.reading(0)
        ]
        self.assertGreaterEqual(len(reading_calls), 2)