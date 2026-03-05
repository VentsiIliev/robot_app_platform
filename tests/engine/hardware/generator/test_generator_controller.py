import unittest
from unittest.mock import MagicMock

from src.engine.hardware.generator.generator_controller import GeneratorController
from src.engine.hardware.generator.models.generator_config import GeneratorConfig
from src.engine.hardware.generator.models.generator_state import GeneratorState
from src.engine.hardware.generator.timer.generator_timer import NullGeneratorTimer


def _transport():
    t = MagicMock()
    t.read_register.return_value = 0      # default: reports ON (0 = ON per hardware convention)
    return t


def _config():
    return GeneratorConfig(relay_register=9, state_register=10)


def _timer():
    t = MagicMock(spec=NullGeneratorTimer)
    t.elapsed_seconds = 12.5
    return t


def _make(transport=None, config=None, timer=None):
    return GeneratorController(
        transport=transport or _transport(),
        config=config or _config(),
        timer=timer or _timer(),
    )


class TestGeneratorControllerTurnOn(unittest.TestCase):
    def test_turn_on_writes_1_to_relay_register(self):
        t = _transport()
        ctrl = _make(transport=t)
        ctrl.turn_on()
        t.write_register.assert_called_once_with(_config().relay_register, 1)

    def test_turn_on_starts_timer(self):
        tm = _timer()
        ctrl = _make(timer=tm)
        ctrl.turn_on()
        tm.start.assert_called_once()

    def test_turn_on_returns_true_on_success(self):
        self.assertTrue(_make().turn_on())

    def test_turn_on_returns_false_when_transport_raises(self):
        t = _transport()
        t.write_register.side_effect = OSError("serial error")
        ctrl = _make(transport=t)
        self.assertFalse(ctrl.turn_on())

    def test_turn_on_does_not_start_timer_when_transport_raises(self):
        t = _transport()
        t.write_register.side_effect = OSError("serial error")
        tm = _timer()
        ctrl = _make(transport=t, timer=tm)
        ctrl.turn_on()
        tm.start.assert_not_called()


class TestGeneratorControllerTurnOff(unittest.TestCase):
    def test_turn_off_writes_0_to_relay_register(self):
        t = _transport()
        ctrl = _make(transport=t)
        ctrl.turn_off()
        t.write_register.assert_called_once_with(_config().relay_register, 0)

    def test_turn_off_stops_timer(self):
        tm = _timer()
        ctrl = _make(timer=tm)
        ctrl.turn_off()
        tm.stop.assert_called_once()

    def test_turn_off_returns_true_on_success(self):
        self.assertTrue(_make().turn_off())

    def test_turn_off_returns_false_when_transport_raises(self):
        t = _transport()
        t.write_register.side_effect = OSError("serial error")
        ctrl = _make(transport=t)
        self.assertFalse(ctrl.turn_off())

    def test_turn_off_does_not_stop_timer_when_transport_raises(self):
        t = _transport()
        t.write_register.side_effect = OSError("serial error")
        tm = _timer()
        ctrl = _make(transport=t, timer=tm)
        ctrl.turn_off()
        tm.stop.assert_not_called()


class TestGeneratorControllerGetState(unittest.TestCase):
    def test_get_state_reads_state_register(self):
        t = _transport()
        ctrl = _make(transport=t)
        ctrl.get_state()
        t.read_register.assert_called_once_with(_config().state_register)

    def test_raw_0_means_is_on_true(self):
        t = _transport()
        t.read_register.return_value = 0
        state = _make(transport=t).get_state()
        self.assertTrue(state.is_on)

    def test_raw_1_means_is_on_false(self):
        t = _transport()
        t.read_register.return_value = 1
        state = _make(transport=t).get_state()
        self.assertFalse(state.is_on)

    def test_get_state_returns_healthy_true_on_success(self):
        state = _make().get_state()
        self.assertTrue(state.is_healthy)

    def test_get_state_returns_no_errors_on_success(self):
        state = _make().get_state()
        self.assertFalse(state.has_errors)

    def test_get_state_includes_elapsed_from_timer(self):
        tm = _timer()
        tm.elapsed_seconds = 99.9
        state = _make(timer=tm).get_state()
        self.assertEqual(state.elapsed_seconds, 99.9)

    def test_get_state_returns_unhealthy_when_transport_raises(self):
        t = _transport()
        t.read_register.side_effect = OSError("comm error")
        state = _make(transport=t).get_state()
        self.assertFalse(state.is_healthy)

    def test_get_state_returns_is_on_false_when_transport_raises(self):
        t = _transport()
        t.read_register.side_effect = OSError("comm error")
        state = _make(transport=t).get_state()
        self.assertFalse(state.is_on)

    def test_get_state_includes_error_message_when_transport_raises(self):
        t = _transport()
        t.read_register.side_effect = OSError("comm error")
        state = _make(transport=t).get_state()
        self.assertTrue(state.has_errors)
        self.assertIn("comm error", state.communication_errors[0])

    def test_get_state_still_includes_elapsed_when_transport_raises(self):
        t = _transport()
        t.read_register.side_effect = OSError("comm error")
        tm = _timer()
        tm.elapsed_seconds = 7.0
        state = _make(transport=t, timer=tm).get_state()
        self.assertEqual(state.elapsed_seconds, 7.0)

    def test_returns_generator_state_instance(self):
        state = _make().get_state()
        self.assertIsInstance(state, GeneratorState)


class TestGeneratorControllerUsesCustomConfig(unittest.TestCase):
    def test_uses_custom_relay_register(self):
        cfg = GeneratorConfig(relay_register=42, state_register=43)
        t = _transport()
        ctrl = _make(transport=t, config=cfg)
        ctrl.turn_on()
        t.write_register.assert_called_once_with(42, 1)

    def test_uses_custom_state_register(self):
        cfg = GeneratorConfig(relay_register=42, state_register=43)
        t = _transport()
        ctrl = _make(transport=t, config=cfg)
        ctrl.get_state()
        t.read_register.assert_called_once_with(43)


class TestGeneratorControllerDefaults(unittest.TestCase):
    def test_default_config_is_used_when_none_provided(self):
        t = _transport()
        ctrl = GeneratorController(transport=t)
        ctrl.turn_on()
        t.write_register.assert_called_once_with(GeneratorConfig().relay_register, 1)

    def test_default_timer_is_null_timer(self):
        t = _transport()
        ctrl = GeneratorController(transport=t)
        # NullGeneratorTimer.start() is a no-op — turn_on should still succeed
        self.assertTrue(ctrl.turn_on())

