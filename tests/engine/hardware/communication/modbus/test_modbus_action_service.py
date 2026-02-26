import unittest
from unittest.mock import MagicMock, patch, patch as mock_patch
import sys

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.communication.modbus.modbus_action_service import ModbusActionService
from src.engine.hardware.communication.modbus.i_modbus_action_service import IModbusActionService


# ---------------------------------------------------------------------------
# Interface contract
# ---------------------------------------------------------------------------

class TestModbusActionServiceInterface(unittest.TestCase):

    def test_implements_i_modbus_action_service(self):
        self.assertIsInstance(ModbusActionService(), IModbusActionService)

    def test_has_detect_ports_method(self):
        self.assertTrue(hasattr(ModbusActionService(), "detect_ports"))

    def test_has_test_connection_method(self):
        self.assertTrue(hasattr(ModbusActionService(), "test_connection"))

    def test_does_not_depend_on_settings_service(self):
        import inspect
        src = inspect.getsource(ModbusActionService)
        self.assertNotIn("ISettingsService", src)
        self.assertNotIn("settings_service", src)

    def test_does_not_depend_on_settings_repository(self):
        import inspect
        src = inspect.getsource(ModbusActionService)
        self.assertNotIn("ISettingsRepository", src)


# ---------------------------------------------------------------------------
# detect_ports() — serial available
# ---------------------------------------------------------------------------

class TestModbusActionServiceDetectPortsSuccess(unittest.TestCase):

    def _run_with_ports(self, devices):
        mock_port = lambda d: MagicMock(device=d)
        mock_serial = MagicMock()
        mock_serial.tools.list_ports.comports.return_value = [
            mock_port(d) for d in devices
        ]
        with patch.dict(sys.modules, {
            "serial":                  mock_serial,
            "serial.tools":            mock_serial.tools,
            "serial.tools.list_ports": mock_serial.tools.list_ports,
        }):
            svc = ModbusActionService()
            return svc.detect_ports()

    def test_returns_list(self):
        self.assertIsInstance(self._run_with_ports(["COM1"]), list)

    def test_returns_correct_port_names(self):
        result = self._run_with_ports(["COM1", "COM3", "/dev/ttyUSB0"])
        self.assertEqual(result, ["COM1", "COM3", "/dev/ttyUSB0"])

    def test_returns_single_port(self):
        self.assertEqual(self._run_with_ports(["COM5"]), ["COM5"])

    def test_returns_empty_when_no_ports(self):
        self.assertEqual(self._run_with_ports([]), [])

    def test_calls_comports(self):
        mock_serial = MagicMock()
        mock_serial.tools.list_ports.comports.return_value = []
        with patch.dict(sys.modules, {
            "serial":                  mock_serial,
            "serial.tools":            mock_serial.tools,
            "serial.tools.list_ports": mock_serial.tools.list_ports,
        }):
            ModbusActionService().detect_ports()
        mock_serial.tools.list_ports.comports.assert_called_once()


# ---------------------------------------------------------------------------
# detect_ports() — serial unavailable / exception
# ---------------------------------------------------------------------------

class TestModbusActionServiceDetectPortsFailure(unittest.TestCase):

    def test_returns_empty_list_when_serial_not_installed(self):
        with patch.dict(sys.modules, {
            "serial":                  None,
            "serial.tools":            None,
            "serial.tools.list_ports": None,
        }):
            result = ModbusActionService().detect_ports()
        self.assertEqual(result, [])

    def test_returns_list_type_on_import_error(self):
        with patch.dict(sys.modules, {
            "serial":                  None,
            "serial.tools":            None,
            "serial.tools.list_ports": None,
        }):
            result = ModbusActionService().detect_ports()
        self.assertIsInstance(result, list)

    def test_returns_empty_list_when_comports_raises(self):
        mock_serial = MagicMock()
        mock_serial.tools.list_ports.comports.side_effect = OSError("device error")
        with patch.dict(sys.modules, {
            "serial":                  mock_serial,
            "serial.tools":            mock_serial.tools,
            "serial.tools.list_ports": mock_serial.tools.list_ports,
        }):
            result = ModbusActionService().detect_ports()
        self.assertEqual(result, [])

    def test_does_not_raise_on_any_exception(self):
        mock_serial = MagicMock()
        mock_serial.tools.list_ports.comports.side_effect = RuntimeError("unexpected")
        with patch.dict(sys.modules, {
            "serial":                  mock_serial,
            "serial.tools":            mock_serial.tools,
            "serial.tools.list_ports": mock_serial.tools.list_ports,
        }):
            ModbusActionService().detect_ports()   # must not raise


# ---------------------------------------------------------------------------
# test_connection() — success
# ---------------------------------------------------------------------------

class TestModbusActionServiceTestConnectionSuccess(unittest.TestCase):

    def _mock_serial_success(self):
        mock_serial = MagicMock()
        mock_conn   = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__  = MagicMock(return_value=False)
        mock_serial.Serial.return_value = mock_conn
        return mock_serial

    def test_returns_true_on_successful_open(self):
        mock_serial = self._mock_serial_success()
        with patch.dict(sys.modules, {"serial": mock_serial}):
            result = ModbusActionService().test_connection(ModbusConfig())
        self.assertTrue(result)

    def test_returns_bool(self):
        mock_serial = self._mock_serial_success()
        with patch.dict(sys.modules, {"serial": mock_serial}):
            result = ModbusActionService().test_connection(ModbusConfig())
        self.assertIsInstance(result, bool)

    def test_passes_port_to_serial(self):
        mock_serial = self._mock_serial_success()
        cfg = ModbusConfig(port="COM3")
        with patch.dict(sys.modules, {"serial": mock_serial}):
            ModbusActionService().test_connection(cfg)
        kwargs = mock_serial.Serial.call_args[1]
        self.assertEqual(kwargs["port"], "COM3")

    def test_passes_baudrate_to_serial(self):
        mock_serial = self._mock_serial_success()
        cfg = ModbusConfig(baudrate=9600)
        with patch.dict(sys.modules, {"serial": mock_serial}):
            ModbusActionService().test_connection(cfg)
        kwargs = mock_serial.Serial.call_args[1]
        self.assertEqual(kwargs["baudrate"], 9600)

    def test_passes_parity_to_serial(self):
        mock_serial = self._mock_serial_success()
        cfg = ModbusConfig(parity="E")
        with patch.dict(sys.modules, {"serial": mock_serial}):
            ModbusActionService().test_connection(cfg)
        kwargs = mock_serial.Serial.call_args[1]
        self.assertEqual(kwargs["parity"], "E")

    def test_passes_timeout_to_serial(self):
        mock_serial = self._mock_serial_success()
        cfg = ModbusConfig(timeout=1.5)
        with patch.dict(sys.modules, {"serial": mock_serial}):
            ModbusActionService().test_connection(cfg)
        kwargs = mock_serial.Serial.call_args[1]
        self.assertAlmostEqual(kwargs["timeout"], 1.5)

    def test_passes_bytesize_to_serial(self):
        mock_serial = self._mock_serial_success()
        cfg = ModbusConfig(bytesize=7)
        with patch.dict(sys.modules, {"serial": mock_serial}):
            ModbusActionService().test_connection(cfg)
        kwargs = mock_serial.Serial.call_args[1]
        self.assertEqual(kwargs["bytesize"], 7)

    def test_passes_stopbits_to_serial(self):
        mock_serial = self._mock_serial_success()
        cfg = ModbusConfig(stopbits=2)
        with patch.dict(sys.modules, {"serial": mock_serial}):
            ModbusActionService().test_connection(cfg)
        kwargs = mock_serial.Serial.call_args[1]
        self.assertEqual(kwargs["stopbits"], 2)


# ---------------------------------------------------------------------------
# test_connection() — failure
# ---------------------------------------------------------------------------

class TestModbusActionServiceTestConnectionFailure(unittest.TestCase):

    def test_returns_false_when_serial_not_installed(self):
        with patch.dict(sys.modules, {"serial": None}):
            result = ModbusActionService().test_connection(ModbusConfig())
        self.assertFalse(result)

    def test_returns_false_on_serial_exception(self):
        mock_serial = MagicMock()
        mock_serial.Serial.side_effect = OSError("port not found")
        with patch.dict(sys.modules, {"serial": mock_serial}):
            result = ModbusActionService().test_connection(ModbusConfig(port="INVALID"))
        self.assertFalse(result)

    def test_returns_false_on_permission_error(self):
        mock_serial = MagicMock()
        mock_serial.Serial.side_effect = PermissionError("access denied")
        with patch.dict(sys.modules, {"serial": mock_serial}):
            result = ModbusActionService().test_connection(ModbusConfig())
        self.assertFalse(result)

    def test_returns_false_on_runtime_error(self):
        mock_serial = MagicMock()
        mock_serial.Serial.side_effect = RuntimeError("unexpected")
        with patch.dict(sys.modules, {"serial": mock_serial}):
            result = ModbusActionService().test_connection(ModbusConfig())
        self.assertFalse(result)

    def test_does_not_raise_on_any_exception(self):
        mock_serial = MagicMock()
        mock_serial.Serial.side_effect = Exception("catastrophic")
        with patch.dict(sys.modules, {"serial": mock_serial}):
            ModbusActionService().test_connection(ModbusConfig())   # must not raise

    def test_returns_bool_on_failure(self):
        with patch.dict(sys.modules, {"serial": None}):
            result = ModbusActionService().test_connection(ModbusConfig())
        self.assertIsInstance(result, bool)


# ---------------------------------------------------------------------------
# Isolation — detect_ports and test_connection are independent
# ---------------------------------------------------------------------------

class TestModbusActionServiceIsolation(unittest.TestCase):

    def test_detect_ports_failure_does_not_affect_test_connection(self):
        mock_serial = MagicMock()
        mock_serial.tools.list_ports.comports.side_effect = OSError("no ports")
        mock_conn   = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__  = MagicMock(return_value=False)
        mock_serial.Serial.return_value = mock_conn

        with patch.dict(sys.modules, {
            "serial":                  mock_serial,
            "serial.tools":            mock_serial.tools,
            "serial.tools.list_ports": mock_serial.tools.list_ports,
        }):
            svc   = ModbusActionService()
            ports = svc.detect_ports()
            ok    = svc.test_connection(ModbusConfig(port="COM3"))

        self.assertEqual(ports, [])
        self.assertTrue(ok)

    def test_multiple_calls_are_independent(self):
        call_count = [0]
        mock_serial = MagicMock()

        def side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError("first call fails")
            conn = MagicMock()
            conn.__enter__ = MagicMock(return_value=conn)
            conn.__exit__  = MagicMock(return_value=False)
            return conn

        mock_serial.Serial.side_effect = side_effect
        with patch.dict(sys.modules, {"serial": mock_serial}):
            svc    = ModbusActionService()
            first  = svc.test_connection(ModbusConfig())
            second = svc.test_connection(ModbusConfig())

        self.assertFalse(first)
        self.assertTrue(second)


if __name__ == "__main__":
    unittest.main()