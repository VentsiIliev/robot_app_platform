import unittest
from unittest.mock import MagicMock

from src.engine.hardware.weight.config import (
    CalibrationConfig, CellConfig, CellsConfig, MeasurementConfig,
)
from src.engine.hardware.weight.http.http_cell_transport import HttpCellTransport
from src.engine.hardware.weight.http.http_weight_cell_factory import build_http_weight_cell_service
from src.engine.hardware.weight.weight_cell_service import WeightCellService


# ── Helpers ───────────────────────────────────────────────────────────────────

def _calib():
    return CalibrationConfig(zero_offset=0.0, scale_factor=1.0, temperature_compensation=False)

def _meas():
    return MeasurementConfig(10, 1.0, 5, 0.0, 1000.0)

def _cell(cid, url=None):
    return CellConfig(
        id=cid, type="T", url=url or f"http://host/w{cid}", capacity=500.0,
        fetch_timeout_seconds=3.0, data_fetch_interval_ms=500,
        calibration=_calib(), measurement=_meas(),
    )

def _cells(*ids):
    return CellsConfig(cells=[_cell(i) for i in ids])


# ---------------------------------------------------------------------------

class TestBuildHttpWeightCellServiceType(unittest.TestCase):

    def test_returns_weight_cell_service(self):
        svc = build_http_weight_cell_service(_cells(0, 1), MagicMock())
        self.assertIsInstance(svc, WeightCellService)

    def test_creates_one_context_per_cell(self):
        svc = build_http_weight_cell_service(_cells(0, 1, 2), MagicMock())
        self.assertEqual(len(svc._cells), 3)

    def test_empty_cells_creates_no_contexts(self):
        svc = build_http_weight_cell_service(CellsConfig(cells=[]), MagicMock())
        self.assertEqual(len(svc._cells), 0)


class TestBuildHttpWeightCellServiceTransport(unittest.TestCase):

    def test_transport_is_http_cell_transport(self):
        svc = build_http_weight_cell_service(_cells(0), MagicMock())
        self.assertIsInstance(svc._cells[0].transport, HttpCellTransport)

    def test_calibrator_is_http_cell_transport(self):
        svc = build_http_weight_cell_service(_cells(0), MagicMock())
        self.assertIsInstance(svc._cells[0].calibrator, HttpCellTransport)

    def test_transport_and_calibrator_same_instance(self):
        """HttpCellTransport implements both interfaces — must be same object."""
        svc = build_http_weight_cell_service(_cells(0), MagicMock())
        self.assertIs(svc._cells[0].transport, svc._cells[0].calibrator)

    def test_each_cell_gets_own_transport(self):
        svc = build_http_weight_cell_service(_cells(0, 1), MagicMock())
        self.assertIsNot(svc._cells[0].transport, svc._cells[1].transport)

    def test_cell_url_assigned(self):
        svc = build_http_weight_cell_service(_cells(0), MagicMock())
        transport = svc._cells[0].transport
        self.assertEqual(transport._base_url, "http://host/w0")

    def test_cell_timeout_assigned(self):
        svc = build_http_weight_cell_service(_cells(0), MagicMock())
        transport = svc._cells[0].transport
        self.assertAlmostEqual(transport._timeout, 3.0)

    def test_multiple_cells_urls_independent(self):
        svc = build_http_weight_cell_service(_cells(0, 1, 2), MagicMock())
        urls = [svc._cells[i].transport._base_url for i in range(3)]
        self.assertEqual(urls, ["http://host/w0", "http://host/w1", "http://host/w2"])


class TestBuildHttpWeightCellServiceMessaging(unittest.TestCase):

    def test_messaging_service_passed(self):
        messaging = MagicMock()
        svc = build_http_weight_cell_service(_cells(0), messaging)
        self.assertIs(svc._messaging, messaging)
