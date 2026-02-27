"""
Tests for src/engine/process/process_sequence.py

ProcessSequence orchestrates a list of IProcess instances in order,
auto-advancing to the next process when the current one stops.

Covered:
- Init: empty list raises ValueError
- start(): fresh start, subscribe to first process, set _current
- start(): resume from PAUSED — no re-subscribe, no index reset
- stop(): delegate to current, unsubscribe, safe when no active
- pause(): delegate to current, safe when no active
- reset_errors(): delegate, clear _current, unsubscribe, safe when no active
- _on_current_stopped chain: STOPPED → advance, subscribe next, start next
- _on_current_stopped: non-STOPPED events are ignored
- _on_current_stopped on last process: _current cleared, index reset
- Full three-process chain end-to-end
"""
import unittest
from unittest.mock import MagicMock

from src.engine.process.process_sequence import ProcessSequence
from src.shared_contracts.events.process_events import (
    ProcessState, ProcessStateEvent, ProcessTopics,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_proc(pid: str, state: ProcessState = ProcessState.IDLE):
    p = MagicMock()
    p.process_id = pid
    p.state = state
    return p


def _ms():
    return MagicMock()


def _stopped(pid: str) -> ProcessStateEvent:
    return ProcessStateEvent(pid, ProcessState.STOPPED, ProcessState.RUNNING)


def _running(pid: str) -> ProcessStateEvent:
    return ProcessStateEvent(pid, ProcessState.RUNNING, ProcessState.IDLE)


def _get_callback(ms, topic):
    """Return the callback registered for *topic* (last one wins)."""
    found = None
    for call in ms.subscribe.call_args_list:
        t, cb = call.args
        if t == topic:
            found = cb
    return found


# ══════════════════════════════════════════════════════════════════════════════
# Init
# ══════════════════════════════════════════════════════════════════════════════

class TestProcessSequenceInit(unittest.TestCase):

    def test_empty_list_raises_value_error(self):
        with self.assertRaises(ValueError):
            ProcessSequence([], _ms())

    def test_single_process_accepted(self):
        seq = ProcessSequence([_make_proc("a")], _ms())
        self.assertIsNotNone(seq)

    def test_initial_current_is_none(self):
        seq = ProcessSequence([_make_proc("a")], _ms())
        self.assertIsNone(seq._current)

    def test_initial_index_is_zero(self):
        seq = ProcessSequence([_make_proc("a")], _ms())
        self.assertEqual(seq._current_index, 0)


# ══════════════════════════════════════════════════════════════════════════════
# start() — fresh start
# ══════════════════════════════════════════════════════════════════════════════

class TestProcessSequenceFreshStart(unittest.TestCase):

    def test_start_calls_first_process_start(self):
        proc = _make_proc("a")
        seq = ProcessSequence([proc], _ms())
        seq.start()
        proc.start.assert_called_once()

    def test_start_sets_current_to_first_process(self):
        proc = _make_proc("a")
        seq = ProcessSequence([proc], _ms())
        seq.start()
        self.assertIs(seq._current, proc)

    def test_start_sets_index_to_zero(self):
        proc_a = _make_proc("a")
        proc_b = _make_proc("b")
        seq = ProcessSequence([proc_a, proc_b], _ms())
        seq.start()
        self.assertEqual(seq._current_index, 0)

    def test_start_subscribes_to_first_process_state_topic(self):
        proc = _make_proc("a")
        ms = _ms()
        seq = ProcessSequence([proc], ms)
        seq.start()
        subscribed = [c.args[0] for c in ms.subscribe.call_args_list]
        self.assertIn(ProcessTopics.state("a"), subscribed)

    def test_restart_after_completion_resets_to_first_process(self):
        proc_a = _make_proc("a")
        proc_b = _make_proc("b")
        ms = _ms()
        seq = ProcessSequence([proc_a, proc_b], ms)
        seq.start()
        # Simulate sequence completing: advance to end
        cb = _get_callback(ms, ProcessTopics.state("a"))
        cb(_stopped("a"))   # now proc_b is current at index 1
        cb_b = _get_callback(ms, ProcessTopics.state("b"))
        cb_b(_stopped("b"))  # sequence done — _current = None
        self.assertIsNone(seq._current)
        # Fresh start: must go back to proc_a
        proc_a.reset_mock()
        seq.start()
        self.assertIs(seq._current, proc_a)
        self.assertEqual(seq._current_index, 0)
        proc_a.start.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# start() — resume from PAUSED
# ══════════════════════════════════════════════════════════════════════════════

class TestProcessSequenceResume(unittest.TestCase):

    def test_start_when_current_paused_calls_process_start(self):
        proc = _make_proc("a", state=ProcessState.PAUSED)
        ms = _ms()
        seq = ProcessSequence([proc], ms)
        seq._current = proc
        seq._current_index = 0
        proc.reset_mock()
        seq.start()
        proc.start.assert_called_once()

    def test_start_when_current_paused_does_not_re_subscribe(self):
        proc = _make_proc("a", state=ProcessState.PAUSED)
        ms = _ms()
        seq = ProcessSequence([proc], ms)
        seq._current = proc
        seq._current_index = 0
        ms.reset_mock()
        seq.start()
        self.assertEqual(ms.subscribe.call_count, 0)

    def test_start_when_current_paused_does_not_change_current(self):
        proc_a = _make_proc("a", state=ProcessState.PAUSED)
        proc_b = _make_proc("b")
        ms = _ms()
        seq = ProcessSequence([proc_a, proc_b], ms)
        seq._current = proc_a
        seq._current_index = 0
        seq.start()
        self.assertIs(seq._current, proc_a)


# ══════════════════════════════════════════════════════════════════════════════
# stop()
# ══════════════════════════════════════════════════════════════════════════════

class TestProcessSequenceStop(unittest.TestCase):

    def test_stop_calls_current_process_stop(self):
        proc = _make_proc("a")
        seq = ProcessSequence([proc], _ms())
        seq.start()
        seq.stop()
        proc.stop.assert_called_once()

    def test_stop_unsubscribes_from_current_topic(self):
        proc = _make_proc("a")
        ms = _ms()
        seq = ProcessSequence([proc], ms)
        seq.start()
        seq.stop()
        unsubscribed = [c.args[0] for c in ms.unsubscribe.call_args_list]
        self.assertIn(ProcessTopics.state("a"), unsubscribed)

    def test_stop_when_no_active_does_not_raise(self):
        seq = ProcessSequence([_make_proc("a")], _ms())
        seq.stop()   # _current is None — must not raise


# ══════════════════════════════════════════════════════════════════════════════
# pause()
# ══════════════════════════════════════════════════════════════════════════════

class TestProcessSequencePause(unittest.TestCase):

    def test_pause_calls_current_process_pause(self):
        proc = _make_proc("a")
        seq = ProcessSequence([proc], _ms())
        seq.start()
        seq.pause()
        proc.pause.assert_called_once()

    def test_pause_when_no_active_does_not_raise(self):
        seq = ProcessSequence([_make_proc("a")], _ms())
        seq.pause()


# ══════════════════════════════════════════════════════════════════════════════
# reset_errors()
# ══════════════════════════════════════════════════════════════════════════════

class TestProcessSequenceResetErrors(unittest.TestCase):

    def test_reset_errors_calls_current_process_reset_errors(self):
        proc = _make_proc("a")
        seq = ProcessSequence([proc], _ms())
        seq.start()
        seq.reset_errors()
        proc.reset_errors.assert_called_once()

    def test_reset_errors_clears_current(self):
        proc = _make_proc("a")
        seq = ProcessSequence([proc], _ms())
        seq.start()
        seq.reset_errors()
        self.assertIsNone(seq._current)

    def test_reset_errors_resets_index_to_zero(self):
        proc_a = _make_proc("a")
        proc_b = _make_proc("b")
        seq = ProcessSequence([proc_a, proc_b], _ms())
        seq.start()
        seq._current_index = 1   # simulate mid-sequence
        seq.reset_errors()
        self.assertEqual(seq._current_index, 0)

    def test_reset_errors_unsubscribes_from_current_topic(self):
        proc = _make_proc("a")
        ms = _ms()
        seq = ProcessSequence([proc], ms)
        seq.start()
        seq.reset_errors()
        unsubscribed = [c.args[0] for c in ms.unsubscribe.call_args_list]
        self.assertIn(ProcessTopics.state("a"), unsubscribed)

    def test_reset_errors_when_no_active_does_not_raise(self):
        seq = ProcessSequence([_make_proc("a")], _ms())
        seq.reset_errors()


# ══════════════════════════════════════════════════════════════════════════════
# Auto-advance chain
# ══════════════════════════════════════════════════════════════════════════════

class TestProcessSequenceChaining(unittest.TestCase):

    def _two_proc_seq(self):
        proc_a = _make_proc("a")
        proc_b = _make_proc("b")
        ms = _ms()
        seq = ProcessSequence([proc_a, proc_b], ms)
        seq.start()
        cb = _get_callback(ms, ProcessTopics.state("a"))
        return seq, proc_a, proc_b, ms, cb

    def test_stopped_event_advances_current_to_next(self):
        seq, _, proc_b, _, cb = self._two_proc_seq()
        cb(_stopped("a"))
        self.assertIs(seq._current, proc_b)

    def test_stopped_event_increments_index(self):
        seq, _, _, _, cb = self._two_proc_seq()
        cb(_stopped("a"))
        self.assertEqual(seq._current_index, 1)

    def test_stopped_event_starts_next_process(self):
        _, _, proc_b, _, cb = self._two_proc_seq()
        cb(_stopped("a"))
        proc_b.start.assert_called_once()

    def test_stopped_event_subscribes_to_next_topic(self):
        _, _, _, ms, cb = self._two_proc_seq()
        ms.reset_mock()
        cb(_stopped("a"))
        subscribed = [c.args[0] for c in ms.subscribe.call_args_list]
        self.assertIn(ProcessTopics.state("b"), subscribed)

    def test_stopped_event_unsubscribes_from_completed_topic(self):
        _, _, _, ms, cb = self._two_proc_seq()
        cb(_stopped("a"))
        unsubscribed = [c.args[0] for c in ms.unsubscribe.call_args_list]
        self.assertIn(ProcessTopics.state("a"), unsubscribed)

    def test_non_stopped_events_do_not_advance(self):
        seq, proc_a, proc_b, _, cb = self._two_proc_seq()
        for evt in [
            _running("a"),
            ProcessStateEvent("a", ProcessState.PAUSED, ProcessState.RUNNING),
            ProcessStateEvent("a", ProcessState.ERROR,  ProcessState.RUNNING),
        ]:
            cb(evt)
        self.assertIs(seq._current, proc_a)
        proc_b.start.assert_not_called()

    def test_last_process_stopped_clears_current(self):
        proc = _make_proc("a")
        ms = _ms()
        seq = ProcessSequence([proc], ms)
        seq.start()
        cb = _get_callback(ms, ProcessTopics.state("a"))
        cb(_stopped("a"))
        self.assertIsNone(seq._current)

    def test_last_process_stopped_resets_index_to_zero(self):
        proc = _make_proc("a")
        ms = _ms()
        seq = ProcessSequence([proc], ms)
        seq.start()
        cb = _get_callback(ms, ProcessTopics.state("a"))
        cb(_stopped("a"))
        self.assertEqual(seq._current_index, 0)

    def test_last_process_stopped_does_not_start_anything(self):
        proc = _make_proc("a")
        ms = _ms()
        seq = ProcessSequence([proc], ms)
        seq.start()
        proc.reset_mock()
        cb = _get_callback(ms, ProcessTopics.state("a"))
        cb(_stopped("a"))
        proc.start.assert_not_called()

    def test_full_three_process_sequence(self):
        proc_a = _make_proc("a")
        proc_b = _make_proc("b")
        proc_c = _make_proc("c")
        ms = _ms()
        seq = ProcessSequence([proc_a, proc_b, proc_c], ms)

        seq.start()
        self.assertIs(seq._current, proc_a)

        cb_a = _get_callback(ms, ProcessTopics.state("a"))
        cb_a(_stopped("a"))
        self.assertIs(seq._current, proc_b)
        proc_b.start.assert_called_once()

        cb_b = _get_callback(ms, ProcessTopics.state("b"))
        self.assertIsNotNone(cb_b, "no subscription found for proc_b")
        cb_b(_stopped("b"))
        self.assertIs(seq._current, proc_c)
        proc_c.start.assert_called_once()

        cb_c = _get_callback(ms, ProcessTopics.state("c"))
        self.assertIsNotNone(cb_c, "no subscription found for proc_c")
        cb_c(_stopped("c"))
        self.assertIsNone(seq._current)
        self.assertEqual(seq._current_index, 0)


if __name__ == "__main__":
    unittest.main()
