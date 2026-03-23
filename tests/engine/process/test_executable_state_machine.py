"""
Tests for src/engine/process/executable_state_machine.y_pixels

Covers stop_execution, loop exit, on_enter/on_exit callbacks, broker publishing,
and exception handling inside handlers.
"""
import threading
import time
import unittest
from unittest.mock import MagicMock, call

from src.engine.process.executable_state_machine import (
    ExecutableStateMachine,
    ExecutableStateMachineBuilder,
    State,
    StateMachineSnapshot,
    StateRegistry,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

class _StopEvent:
    """Minimal stand-in for threading.Event used as context.stop_event."""
    def __init__(self):
        self._set = False

    def set(self):
        self._set = True

    def is_set(self):
        return self._set

    def clear(self):
        self._set = False


class _FakeContext:
    def __init__(self):
        self.stop_event = _StopEvent()
        self.visited = []


from enum import Enum, auto

class S(Enum):
    A = auto()
    B = auto()
    DONE = auto()
    ERROR = auto()


def _build_simple(context=None, handler_a=None, handler_b=None, broker=None) -> ExecutableStateMachine:
    """Two-state machine: A → B → DONE."""
    ctx = context or _FakeContext()

    def _h_a(c):
        c.visited.append("A")
        return S.B

    def _h_b(c):
        c.visited.append("B")
        return S.DONE

    registry = StateRegistry()
    registry.register_state(State(S.A, handler_a or _h_a))
    registry.register_state(State(S.B, handler_b or _h_b))
    registry.register_state(State(S.DONE, lambda c: S.DONE))

    rules = {
        S.A:    {S.B, S.ERROR},
        S.B:    {S.DONE, S.ERROR},
        S.DONE: {S.DONE},
        S.ERROR: {S.ERROR},
    }

    return (
        ExecutableStateMachineBuilder()
        .with_initial_state(S.A)
        .with_transition_rules(rules)
        .with_state_registry(registry)
        .with_context(ctx)
        .with_message_broker(broker)
        .with_state_topic("state.topic")
        .build()
    )


# ══════════════════════════════════════════════════════════════════════════════
# stop_execution
# ══════════════════════════════════════════════════════════════════════════════

class TestExecutableStateMachineStop(unittest.TestCase):

    def test_stop_sets_running_false(self):
        machine = _build_simple()
        machine._running = True
        machine.stop_execution()
        self.assertFalse(machine._running)

    def test_stop_sets_context_stop_event(self):
        ctx = _FakeContext()
        machine = _build_simple(context=ctx)
        machine.stop_execution()
        self.assertTrue(ctx.stop_event.is_set())

    def test_stop_without_context_does_not_raise(self):
        registry = StateRegistry()
        registry.register_state(State(S.A, lambda c: S.A))
        machine = ExecutableStateMachine(
            initial_state=S.A,
            transition_rules={S.A: {S.A}},
            registry=registry,
            context=None,
        )
        machine.stop_execution()   # must not raise

    def test_stop_without_stop_event_attribute_does_not_raise(self):
        ctx = object()   # no stop_event attribute
        machine = _build_simple(context=ctx)
        machine.stop_execution()   # must not raise


# ══════════════════════════════════════════════════════════════════════════════
# Loop execution and exit
# ══════════════════════════════════════════════════════════════════════════════

class TestExecutableStateMachineExecution(unittest.TestCase):

    def test_step_executes_single_transition_without_resetting(self):
        ctx = _FakeContext()
        machine = _build_simple(context=ctx)

        stepped = machine.step()

        self.assertTrue(stepped)
        self.assertEqual(machine.current_state, S.B)
        self.assertEqual(ctx.visited, ["A"])
        self.assertEqual(machine.get_snapshot().step_count, 1)

    def test_step_records_timing_in_snapshot(self):
        ctx = _FakeContext()
        machine = _build_simple(context=ctx)

        machine.step()

        snapshot = machine.get_snapshot()
        self.assertIsNotNone(snapshot.last_handler_duration_s)
        self.assertIsNotNone(snapshot.last_step_duration_s)
        self.assertGreaterEqual(snapshot.last_handler_duration_s, 0.0)
        self.assertGreaterEqual(snapshot.last_step_duration_s, 0.0)

    def test_reset_restores_initial_state_and_clears_snapshot(self):
        ctx = _FakeContext()
        machine = _build_simple(context=ctx)
        machine.step()

        machine.reset()

        snapshot = machine.get_snapshot()
        self.assertEqual(machine.current_state, S.A)
        self.assertEqual(snapshot.step_count, 0)
        self.assertIsNone(snapshot.last_state)
        self.assertIsNone(snapshot.last_next_state)
        self.assertIsNone(snapshot.last_error)
        self.assertIsNone(snapshot.last_step_duration_s)

    def test_simple_run_visits_all_states(self):
        ctx = _FakeContext()
        machine = _build_simple(context=ctx)
        # Run to DONE — machine loops forever on DONE, so stop after first
        # full traversal via the stop_event set inside DONE handler
        def _h_done(c):
            machine.stop_execution()
            return S.DONE

        registry = StateRegistry()
        registry.register_state(State(S.A, lambda c: (c.visited.append("A"), S.B)[1]))
        registry.register_state(State(S.B, lambda c: (c.visited.append("B"), S.DONE)[1]))
        registry.register_state(State(S.DONE, _h_done))
        machine._registry = registry
        machine.start_execution()
        self.assertEqual(ctx.visited, ["A", "B"])

    def test_loop_exits_when_running_set_false(self):
        """Handler sets stop flag; loop must exit within timeout."""
        ctx = _FakeContext()
        call_count = [0]

        def handler(c):
            call_count[0] += 1
            machine.stop_execution()
            return S.ERROR

        registry = StateRegistry()
        registry.register_state(State(S.A, handler))
        registry.register_state(State(S.ERROR, lambda c: S.ERROR))

        machine = (
            ExecutableStateMachineBuilder()
            .with_initial_state(S.A)
            .with_transition_rules({S.A: {S.ERROR}, S.ERROR: {S.ERROR}})
            .with_state_registry(registry)
            .with_context(ctx)
            .build()
        )

        t = threading.Thread(target=machine.start_execution, daemon=True)
        t.start()
        t.join(timeout=2.0)
        self.assertFalse(t.is_alive(), "state machine did not exit after stop_execution()")

    def test_invalid_transition_exits_loop(self):
        """Handler returns a state not in transition rules → loop must exit."""
        ctx = _FakeContext()

        registry = StateRegistry()
        registry.register_state(State(S.A, lambda c: S.B))
        registry.register_state(State(S.B, lambda c: S.B))

        machine = (
            ExecutableStateMachineBuilder()
            .with_initial_state(S.A)
            .with_transition_rules({S.A: {S.ERROR}})  # B not allowed
            .with_state_registry(registry)
            .with_context(ctx)
            .build()
        )
        # Must not hang
        t = threading.Thread(target=machine.start_execution, daemon=True)
        t.start()
        t.join(timeout=2.0)
        self.assertFalse(t.is_alive())

    def test_unhandled_exception_in_handler_exits_loop(self):
        ctx = _FakeContext()

        def bad_handler(c):
            raise RuntimeError("handler exploded")

        registry = StateRegistry()
        registry.register_state(State(S.A, bad_handler))

        machine = (
            ExecutableStateMachineBuilder()
            .with_initial_state(S.A)
            .with_transition_rules({S.A: {S.ERROR}})
            .with_state_registry(registry)
            .with_context(ctx)
            .build()
        )
        t = threading.Thread(target=machine.start_execution, daemon=True)
        t.start()
        t.join(timeout=2.0)
        self.assertFalse(t.is_alive())

    def test_missing_handler_exits_loop(self):
        """No handler registered for initial state → loop exits cleanly."""
        ctx = _FakeContext()
        registry = StateRegistry()   # empty — no handlers registered

        machine = (
            ExecutableStateMachineBuilder()
            .with_initial_state(S.A)
            .with_transition_rules({S.A: {S.ERROR}})
            .with_state_registry(registry)
            .with_context(ctx)
            .build()
        )
        t = threading.Thread(target=machine.start_execution, daemon=True)
        t.start()
        t.join(timeout=2.0)
        self.assertFalse(t.is_alive())

    def test_step_records_invalid_transition_error(self):
        ctx = _FakeContext()

        registry = StateRegistry()
        registry.register_state(State(S.A, lambda c: S.B))

        machine = (
            ExecutableStateMachineBuilder()
            .with_initial_state(S.A)
            .with_transition_rules({S.A: {S.ERROR}})
            .with_state_registry(registry)
            .with_context(ctx)
            .build()
        )

        stepped = machine.step()

        self.assertFalse(stepped)
        self.assertEqual(machine.current_state, S.A)
        self.assertIn("Invalid transition", machine.get_snapshot().last_error)

    def test_get_snapshot_returns_machine_state_details(self):
        machine = _build_simple()

        snapshot = machine.get_snapshot()

        self.assertIsInstance(snapshot, StateMachineSnapshot)
        self.assertEqual(snapshot.initial_state, S.A)
        self.assertEqual(snapshot.current_state, S.A)
        self.assertFalse(snapshot.is_running)
        self.assertEqual(snapshot.step_count, 0)


# ══════════════════════════════════════════════════════════════════════════════
# on_enter / on_exit callbacks
# ══════════════════════════════════════════════════════════════════════════════

class TestExecutableStateMachineCallbacks(unittest.TestCase):

    def _run_once(self, on_enter=None, on_exit=None):
        ctx = _FakeContext()
        order = []

        def handler(c):
            order.append("handler")
            machine.stop_execution()
            return S.ERROR

        registry = StateRegistry()
        registry.register_state(State(S.A, handler, on_enter=on_enter, on_exit=on_exit))
        registry.register_state(State(S.ERROR, lambda c: S.ERROR))

        machine = (
            ExecutableStateMachineBuilder()
            .with_initial_state(S.A)
            .with_transition_rules({S.A: {S.ERROR}, S.ERROR: {S.ERROR}})
            .with_state_registry(registry)
            .with_context(ctx)
            .build()
        )
        machine.start_execution()
        return order

    def test_on_enter_called_before_handler(self):
        order = []
        self._run_once(
            on_enter=lambda c, s: order.append("enter"),
        )
        # on_enter runs before the handler modifies 'order' in this test
        # We just verify it was called (cannot share order without closure here)
        # Use a closure approach:
        ctx = _FakeContext()
        seq = []

        def _enter(c, s): seq.append("enter")
        def _handler(c):
            seq.append("handler")
            machine.stop_execution()
            return S.ERROR

        registry = StateRegistry()
        registry.register_state(State(S.A, _handler, on_enter=_enter))
        registry.register_state(State(S.ERROR, lambda c: S.ERROR))
        machine = (
            ExecutableStateMachineBuilder()
            .with_initial_state(S.A)
            .with_transition_rules({S.A: {S.ERROR}, S.ERROR: {S.ERROR}})
            .with_state_registry(registry)
            .with_context(ctx)
            .build()
        )
        machine.start_execution()
        self.assertEqual(seq, ["enter", "handler"])

    def test_on_exit_called_after_handler(self):
        ctx = _FakeContext()
        seq = []

        def _handler(c):
            seq.append("handler")
            machine.stop_execution()
            return S.ERROR

        def _exit(c, s): seq.append("exit")

        registry = StateRegistry()
        registry.register_state(State(S.A, _handler, on_exit=_exit))
        registry.register_state(State(S.ERROR, lambda c: S.ERROR))
        machine = (
            ExecutableStateMachineBuilder()
            .with_initial_state(S.A)
            .with_transition_rules({S.A: {S.ERROR}, S.ERROR: {S.ERROR}})
            .with_state_registry(registry)
            .with_context(ctx)
            .build()
        )
        machine.start_execution()
        self.assertEqual(seq, ["handler", "exit"])


# ══════════════════════════════════════════════════════════════════════════════
# Broker publishing
# ══════════════════════════════════════════════════════════════════════════════

class TestExecutableStateMachineBroker(unittest.TestCase):

    def test_state_published_to_broker_on_each_state(self):
        ctx = _FakeContext()
        broker = MagicMock()

        def _h_a(c):
            return S.B

        def _h_b(c):
            machine.stop_execution()
            return S.ERROR

        registry = StateRegistry()
        registry.register_state(State(S.A, _h_a))
        registry.register_state(State(S.B, _h_b))
        registry.register_state(State(S.ERROR, lambda c: S.ERROR))

        machine = (
            ExecutableStateMachineBuilder()
            .with_initial_state(S.A)
            .with_transition_rules({S.A: {S.B}, S.B: {S.ERROR}, S.ERROR: {S.ERROR}})
            .with_state_registry(registry)
            .with_context(ctx)
            .with_message_broker(broker)
            .with_state_topic("calib.state")
            .build()
        )
        machine.start_execution()
        published_topics = [c[0][0] for c in broker.publish.call_args_list]
        self.assertIn("calib.state", published_topics)


# ══════════════════════════════════════════════════════════════════════════════
# Builder
# ══════════════════════════════════════════════════════════════════════════════

class TestExecutableStateMachineBuilder(unittest.TestCase):

    def test_build_raises_without_registry(self):
        with self.assertRaises(ValueError):
            ExecutableStateMachineBuilder().with_initial_state(S.A).build()

    def test_build_raises_without_initial_state(self):
        with self.assertRaises(ValueError):
            ExecutableStateMachineBuilder().with_state_registry(StateRegistry()).build()

    def test_build_returns_machine(self):
        registry = StateRegistry()
        machine = (
            ExecutableStateMachineBuilder()
            .with_initial_state(S.A)
            .with_state_registry(registry)
            .build()
        )
        self.assertIsInstance(machine, ExecutableStateMachine)


if __name__ == "__main__":
    unittest.main()
