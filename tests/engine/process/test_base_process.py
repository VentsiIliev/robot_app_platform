"""
Tests for src/engine/process/base_process.py

BaseProcess is the abstract base for all robot processes.
Covers state transitions, broker publishing, hook invocation, and
service requirement enforcement.
"""
import unittest
from unittest.mock import MagicMock, call

from src.engine.process.base_process import BaseProcess
from src.engine.process.process_requirements import ProcessRequirements
from src.shared_contracts.events.process_events import ProcessState, ProcessTopics


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ms():
    return MagicMock()


class _ConcreteProcess(BaseProcess):
    """Minimal concrete subclass with tracked hook calls."""

    def __init__(self, **kwargs):
        super().__init__(process_id="test_proc", messaging=kwargs.pop("messaging", _ms()), **kwargs)
        self.hooks_called = []

    def _on_start(self)        -> None: self.hooks_called.append("start")
    def _on_stop(self)         -> None: self.hooks_called.append("stop")
    def _on_pause(self)        -> None: self.hooks_called.append("pause")
    def _on_resume(self)       -> None: self.hooks_called.append("resume")
    def _on_reset_errors(self) -> None: self.hooks_called.append("reset_errors")


def _make(messaging=None, **kwargs) -> _ConcreteProcess:
    return _ConcreteProcess(messaging=messaging or _ms(), **kwargs)


# ══════════════════════════════════════════════════════════════════════════════
# Initial state
# ══════════════════════════════════════════════════════════════════════════════

class TestBaseProcessInitialState(unittest.TestCase):

    def test_initial_state_is_idle(self):
        self.assertEqual(_make().state, ProcessState.IDLE)

    def test_process_id_stored(self):
        self.assertEqual(_make().process_id, "test_proc")


# ══════════════════════════════════════════════════════════════════════════════
# State transitions
# ══════════════════════════════════════════════════════════════════════════════

class TestBaseProcessStateTransitions(unittest.TestCase):

    def test_start_from_idle_transitions_to_running(self):
        p = _make()
        p.start()
        self.assertEqual(p.state, ProcessState.RUNNING)

    def test_stop_from_running_transitions_to_stopped(self):
        p = _make()
        p.start()
        p.stop()
        self.assertEqual(p.state, ProcessState.STOPPED)

    def test_pause_from_running_transitions_to_paused(self):
        p = _make()
        p.start()
        p.pause()
        self.assertEqual(p.state, ProcessState.PAUSED)

    def test_resume_from_paused_transitions_to_running(self):
        p = _make()
        p.start()
        p.pause()
        p.resume()
        self.assertEqual(p.state, ProcessState.RUNNING)

    def test_start_from_stopped_transitions_to_running(self):
        p = _make()
        p.start()
        p.stop()
        p.start()
        self.assertEqual(p.state, ProcessState.RUNNING)

    def test_stop_from_idle_is_no_op(self):
        p = _make()
        p.stop()
        self.assertEqual(p.state, ProcessState.IDLE)

    def test_pause_from_idle_is_no_op(self):
        p = _make()
        p.pause()
        self.assertEqual(p.state, ProcessState.IDLE)

    def test_set_error_from_running(self):
        p = _make()
        p.start()
        p.set_error("boom")
        self.assertEqual(p.state, ProcessState.ERROR)

    def test_set_error_from_idle(self):
        p = _make()
        p.set_error("boom")
        self.assertEqual(p.state, ProcessState.ERROR)

    def test_reset_errors_returns_to_idle(self):
        p = _make()
        p.set_error()
        p.reset_errors()
        self.assertEqual(p.state, ProcessState.IDLE)


# ══════════════════════════════════════════════════════════════════════════════
# Hook invocation
# ══════════════════════════════════════════════════════════════════════════════

class TestBaseProcessHooks(unittest.TestCase):

    def test_on_start_called_on_start(self):
        p = _make()
        p.start()
        self.assertIn("start", p.hooks_called)

    def test_on_stop_called_on_stop(self):
        p = _make()
        p.start()
        p.hooks_called.clear()
        p.stop()
        self.assertIn("stop", p.hooks_called)

    def test_on_pause_called_on_pause(self):
        p = _make()
        p.start()
        p.hooks_called.clear()
        p.pause()
        self.assertIn("pause", p.hooks_called)

    def test_on_resume_called_on_resume_from_paused(self):
        p = _make()
        p.start()
        p.pause()
        p.hooks_called.clear()
        p.resume()
        self.assertIn("resume", p.hooks_called)

    def test_on_start_not_called_from_idle_stop(self):
        p = _make()
        p.stop()   # invalid transition — hook must not fire
        self.assertNotIn("stop", p.hooks_called)

    def test_hook_exception_forces_error_state(self):
        class BrokenProcess(_ConcreteProcess):
            def _on_start(self):
                raise RuntimeError("broken")

        p = BrokenProcess()
        p.start()
        self.assertEqual(p.state, ProcessState.ERROR)


# ══════════════════════════════════════════════════════════════════════════════
# Broker publishing
# ══════════════════════════════════════════════════════════════════════════════

class TestBaseProcessBrokerPublishing(unittest.TestCase):

    def test_state_published_on_start(self):
        ms = _ms()
        p = _make(messaging=ms)
        p.start()
        published_topics = [c[0][0] for c in ms.publish.call_args_list]
        self.assertIn(ProcessTopics.state("test_proc"), published_topics)

    def test_active_topic_published_on_start(self):
        ms = _ms()
        p = _make(messaging=ms)
        p.start()
        published_topics = [c[0][0] for c in ms.publish.call_args_list]
        self.assertIn(ProcessTopics.ACTIVE, published_topics)

    def test_state_published_on_stop(self):
        ms = _ms()
        p = _make(messaging=ms)
        p.start()
        ms.reset_mock()
        p.stop()
        published_topics = [c[0][0] for c in ms.publish.call_args_list]
        self.assertIn(ProcessTopics.state("test_proc"), published_topics)


# ══════════════════════════════════════════════════════════════════════════════
# Service requirements
# ══════════════════════════════════════════════════════════════════════════════

class TestBaseProcessRequirements(unittest.TestCase):

    def test_requirements_block_start_when_service_unavailable(self):
        p = _make(
            requirements=ProcessRequirements.requires("robot"),
            service_checker=lambda _: False,
        )
        p.start()
        self.assertEqual(p.state, ProcessState.IDLE)

    def test_requirements_allow_start_when_service_available(self):
        p = _make(
            requirements=ProcessRequirements.requires("robot"),
            service_checker=lambda _: True,
        )
        p.start()
        self.assertEqual(p.state, ProcessState.RUNNING)
        p.stop()


if __name__ == "__main__":
    unittest.main()