import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from src.engine.hardware.weight.config import (
    CalibrationConfig, CellConfig, CellsConfig, MeasurementConfig,
)
from src.engine.hardware.weight.http.http_cell_transport import HttpCellTransport
from src.engine.hardware.weight.http.http_weight_cell_factory import build_http_weight_cell_service
from src.engine.hardware.weight.weight_cell_service import WeightCellService


# ── Helpers ───────────────────────────────────────────────────────────────────

def _calib():
    return CalibrationConfig(zero_offset=1.5, scale_factor=0.97)

def _meas():
    return MeasurementConfig(10, 1.0, 5, 0.0, 1000.0)

def _cell(cid=0, url="http://192.168.1.100/weight1"):
    return CellConfig(
        id=cid, type="T", url=url, capacity=500.0,
        fetch_timeout_seconds=3.0, data_fetch_interval_ms=500,
        calibration=_calib(), measurement=_meas(),
    )

def _cells(*ids):
    return CellsConfig(cells=[_cell(i, f"http://host/w{i}") for i in ids])

def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp

def _mock_error_response():
    from requests.exceptions import HTTPError
    resp = MagicMock()
    resp.raise_for_status.side_effect = HTTPError("404 Not Found")
    return resp


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

class TestHttpCellTransportInit(unittest.TestCase):

    def test_base_url_strips_trailing_slash(self):
        t = HttpCellTransport(_cell(url="http://host/w1/"))
        self.assertEqual(t._base_url, "http://host/w1")

    def test_timeout_from_config(self):
        t = HttpCellTransport(_cell())
        self.assertAlmostEqual(t._timeout, 3.0)

    def test_initially_disconnected(self):
        t = HttpCellTransport(_cell())
        self.assertFalse(t.is_connected)


# ---------------------------------------------------------------------------
# connect / disconnect
# ---------------------------------------------------------------------------

class TestHttpCellTransportConnect(unittest.TestCase):

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_connect_success(self, mock_req):
        mock_req.get.return_value = _mock_response(42.0)
        t = HttpCellTransport(_cell())
        self.assertTrue(t.connect())
        self.assertTrue(t.is_connected)

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_connect_http_error_returns_false(self, mock_req):
        mock_req.get.return_value = _mock_error_response()
        t = HttpCellTransport(_cell())
        self.assertFalse(t.connect())
        self.assertFalse(t.is_connected)

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_connect_connection_error_returns_false(self, mock_req):
        mock_req.get.side_effect = ConnectionError("timeout")
        t = HttpCellTransport(_cell())
        self.assertFalse(t.connect())
        self.assertFalse(t.is_connected)

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_connect_calls_base_url(self, mock_req):
        mock_req.get.return_value = _mock_response(1.0)
        t = HttpCellTransport(_cell(url="http://myhost/weight3"))
        t.connect()
        mock_req.get.assert_called_once_with("http://myhost/weight3", timeout=3.0)

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_disconnect_sets_not_connected(self, mock_req):
        mock_req.get.return_value = _mock_response(1.0)
        t = HttpCellTransport(_cell())
        t.connect()
        t.disconnect()
        self.assertFalse(t.is_connected)

    def test_disconnect_without_connect_no_raise(self):
        t = HttpCellTransport(_cell())
        t.disconnect()   # must not raise


# ---------------------------------------------------------------------------
# read_weight — response format variants
# ---------------------------------------------------------------------------

class TestHttpCellTransportReadWeight(unittest.TestCase):

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_read_raw_float(self, mock_req):
        mock_req.get.return_value = _mock_response(7.0)
        t = HttpCellTransport(_cell())
        self.assertAlmostEqual(t.read_weight(), 7.0)

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_read_raw_int(self, mock_req):
        mock_req.get.return_value = _mock_response(42)
        t = HttpCellTransport(_cell())
        self.assertAlmostEqual(t.read_weight(), 42.0)

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_read_dict_weight_key(self, mock_req):
        mock_req.get.return_value = _mock_response({"weight": 123.4})
        t = HttpCellTransport(_cell())
        self.assertAlmostEqual(t.read_weight(), 123.4)

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_read_dict_value_key(self, mock_req):
        mock_req.get.return_value = _mock_response({"value": 55.5})
        t = HttpCellTransport(_cell())
        self.assertAlmostEqual(t.read_weight(), 55.5)

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_read_dict_weight_key_takes_priority(self, mock_req):
        mock_req.get.return_value = _mock_response({"weight": 10.0, "value": 99.0})
        t = HttpCellTransport(_cell())
        self.assertAlmostEqual(t.read_weight(), 10.0)

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_read_unexpected_format_raises(self, mock_req):
        mock_req.get.return_value = _mock_response("bad_string")
        t = HttpCellTransport(_cell())
        with self.assertRaises(ValueError):
            t.read_weight()

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_read_uses_base_url(self, mock_req):
        mock_req.get.return_value = _mock_response(1.0)
        t = HttpCellTransport(_cell(url="http://esp/w2"))
        t.read_weight()
        mock_req.get.assert_called_once_with("http://esp/w2", timeout=3.0)

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_read_http_error_propagates(self, mock_req):
        mock_req.get.return_value = _mock_error_response()
        t = HttpCellTransport(_cell())
        with self.assertRaises(Exception):
            t.read_weight()


# ---------------------------------------------------------------------------
# Calibration — endpoint paths
# ---------------------------------------------------------------------------

class TestHttpCellTransportCalibration(unittest.TestCase):

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_tare_calls_tare_endpoint(self, mock_req):
        mock_req.get.return_value = _mock_response({})
        t = HttpCellTransport(_cell(url="http://host/w0"))
        t.tare(0)
        mock_req.get.assert_called_once_with("http://host/w0/tare", timeout=3.0)

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_tare_success_returns_true(self, mock_req):
        mock_req.get.return_value = _mock_response({})
        t = HttpCellTransport(_cell())
        self.assertTrue(t.tare(0))

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_tare_http_error_returns_false(self, mock_req):
        mock_req.get.return_value = _mock_error_response()
        t = HttpCellTransport(_cell())
        self.assertFalse(t.tare(0))

    def test_get_config_returns_local_calibration(self):
        """No HTTP call — returns local calibration from config."""
        t = HttpCellTransport(_cell())
        result = t.get_config(0)
        self.assertEqual(result, _calib())

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_update_offset_calls_correct_endpoint(self, mock_req):
        mock_req.get.return_value = _mock_response({})
        t = HttpCellTransport(_cell(url="http://host/w0"))
        t.update_offset(0, 2.5)
        mock_req.get.assert_called_once_with(
            "http://host/w0/update-config?offset=2.5", timeout=3.0
        )

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_update_scale_calls_correct_endpoint(self, mock_req):
        mock_req.get.return_value = _mock_response({})
        t = HttpCellTransport(_cell(url="http://host/w0"))
        t.update_scale(0, 0.98)
        mock_req.get.assert_called_once_with(
            "http://host/w0/update-config?scale=0.98", timeout=3.0
        )

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_update_config_calls_correct_endpoint(self, mock_req):
        mock_req.get.return_value = _mock_response({})
        t = HttpCellTransport(_cell(url="http://host/w0"))
        t.update_config(0, 1.5, 0.97)
        mock_req.get.assert_called_once_with(
            "http://host/w0/update-config?offset=1.5&scale=0.97", timeout=3.0
        )

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_update_config_success_returns_true(self, mock_req):
        mock_req.get.return_value = _mock_response({})
        t = HttpCellTransport(_cell())
        self.assertTrue(t.update_config(0, 1.0, 1.0))

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_update_config_http_error_returns_false(self, mock_req):
        mock_req.get.return_value = _mock_error_response()
        t = HttpCellTransport(_cell())
        self.assertFalse(t.update_config(0, 1.0, 1.0))

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_update_offset_http_error_returns_false(self, mock_req):
        mock_req.get.return_value = _mock_error_response()
        t = HttpCellTransport(_cell())
        self.assertFalse(t.update_offset(0, 1.0))

    @patch("src.engine.hardware.weight.http.http_cell_transport._requests")
    def test_update_scale_http_error_returns_false(self, mock_req):
        mock_req.get.return_value = _mock_error_response()
        t = HttpCellTransport(_cell())
        self.assertFalse(t.update_scale(0, 1.0))


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestBuildHttpWeightCellService(unittest.TestCase):

    def test_returns_weight_cell_service(self):
        messaging = MagicMock()
        svc = build_http_weight_cell_service(_cells(0, 1), messaging)
        self.assertIsInstance(svc, WeightCellService)

    def test_creates_one_context_per_cell(self):
        messaging = MagicMock()
        svc = build_http_weight_cell_service(_cells(0, 1, 2), messaging)
        self.assertEqual(len(svc._cells), 3)

    def test_transport_is_http_cell_transport(self):
        messaging = MagicMock()
        svc = build_http_weight_cell_service(_cells(0), messaging)
        self.assertIsInstance(svc._cells[0].transport, HttpCellTransport)

    def test_calibrator_is_http_cell_transport(self):
        """Same HttpCellTransport instance implements both ICellTransport and ICellCalibrator."""
        messaging = MagicMock()
        svc = build_http_weight_cell_service(_cells(0), messaging)
        self.assertIsInstance(svc._cells[0].calibrator, HttpCellTransport)

    def test_transport_and_calibrator_same_instance(self):
        messaging = MagicMock()
        svc = build_http_weight_cell_service(_cells(0), messaging)
        self.assertIs(svc._cells[0].transport, svc._cells[0].calibrator)

    def test_empty_cells_creates_no_contexts(self):
        messaging = MagicMock()
        svc = build_http_weight_cell_service(CellsConfig(cells=[]), messaging)
        self.assertEqual(len(svc._cells), 0)

    def test_cell_url_correctly_assigned(self):
        messaging = MagicMock()
        svc = build_http_weight_cell_service(_cells(0), messaging)
        self.assertEqual(svc._cells[0].transport._base_url, "http://host/w0")

    def test_cell_timeout_correctly_assigned(self):
        messaging = MagicMock()
        svc = build_http_weight_cell_service(_cells(0), messaging)
        self.assertAlmostEqual(svc._cells[0].transport._timeout, 3.0)
