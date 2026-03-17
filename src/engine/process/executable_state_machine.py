"""
Minimal blocking ExecutableStateMachine for the robot calibration pipeline.
Provides State, StateRegistry, ExecutableStateMachine, ExecutableStateMachineBuilder.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Set

_logger = logging.getLogger(__name__)


@dataclass
class State:
    state: Any
    handler: Callable
    on_enter: Optional[Callable] = field(default=None)
    on_exit: Optional[Callable] = field(default=None)


@dataclass(frozen=True)
class StateMachineSnapshot:
    initial_state: Any
    current_state: Any
    is_running: bool
    step_count: int
    last_state: Any = None
    last_next_state: Any = None
    last_error: Optional[str] = None


class StateRegistry:
    def __init__(self):
        self._states: Dict[Any, State] = {}

    def register_state(self, state: State) -> None:
        self._states[state.state] = state

    def get(self, state_enum) -> Optional[State]:
        return self._states.get(state_enum)


class ExecutableStateMachine:

    def __init__(
        self,
        initial_state,
        transition_rules: Dict[Any, Set[Any]],
        registry: StateRegistry,
        context,
        message_broker=None,
        state_topic: str = None,
    ):
        self._initial_state = initial_state
        self._transition_rules = transition_rules
        self._registry = registry
        self._context = context
        self._broker = message_broker
        self._state_topic = state_topic
        self._current_state = initial_state
        self._running = False
        self._step_count = 0
        self._last_state = None
        self._last_next_state = None
        self._last_error = None

    @property
    def current_state(self):
        return self._current_state

    def reset(self) -> None:
        self._current_state = self._initial_state
        self._running = False
        self._step_count = 0
        self._last_state = None
        self._last_next_state = None
        self._last_error = None

    def get_snapshot(self) -> StateMachineSnapshot:
        return StateMachineSnapshot(
            initial_state=self._initial_state,
            current_state=self._current_state,
            is_running=self._running,
            step_count=self._step_count,
            last_state=self._last_state,
            last_next_state=self._last_next_state,
            last_error=self._last_error,
        )

    def stop_execution(self) -> None:
        self._running = False
        if self._context is not None and hasattr(self._context, "stop_event"):
            self._context.stop_event.set()

    def step(self) -> bool:
        current_state = self._current_state
        self._last_state = current_state
        self._last_next_state = None
        self._last_error = None

        state_obj = self._registry.get(current_state)
        if state_obj is None:
            self._last_error = f"No handler registered for state {current_state!r}"
            _logger.error("%s — stopping.", self._last_error)
            self._running = False
            return False

        if self._broker and self._state_topic:
            try:
                self._broker.publish(self._state_topic, current_state.name)
            except Exception as exc:
                _logger.warning("Failed to publish state change: %s", exc)

        if state_obj.on_enter:
            try:
                state_obj.on_enter(self._context, current_state)
            except Exception as exc:
                _logger.warning("on_enter error for %s: %s", current_state, exc)

        try:
            next_state = state_obj.handler(self._context)
        except Exception as exc:
            self._last_error = f"Unhandled error in state {current_state!r}: {exc}"
            _logger.error(self._last_error, exc_info=True)
            self._running = False
            return False

        if state_obj.on_exit:
            try:
                state_obj.on_exit(self._context, current_state)
            except Exception as exc:
                _logger.warning("on_exit error for %s: %s", current_state, exc)

        allowed = self._transition_rules.get(current_state, set())
        if next_state not in allowed:
            self._last_error = (
                f"Invalid transition {current_state!r} -> {next_state!r} "
                f"(allowed: {allowed!r})"
            )
            _logger.error("%s — stopping.", self._last_error)
            self._running = False
            return False

        self._current_state = next_state
        self._last_next_state = next_state
        self._step_count += 1
        return True

    def start_execution(self, delay: float = 0.0) -> None:
        self.reset()
        self._running = True

        while self._running:
            if not self.step():
                break

            if delay > 0:
                time.sleep(delay)


class ExecutableStateMachineBuilder:

    def __init__(self):
        self._initial_state = None
        self._transition_rules: Dict = {}
        self._registry: Optional[StateRegistry] = None
        self._context = None
        self._broker = None
        self._state_topic: Optional[str] = None

    def with_initial_state(self, state) -> "ExecutableStateMachineBuilder":
        self._initial_state = state
        return self

    def with_transition_rules(self, rules: Dict) -> "ExecutableStateMachineBuilder":
        self._transition_rules = rules
        return self

    def with_state_registry(self, registry: StateRegistry) -> "ExecutableStateMachineBuilder":
        self._registry = registry
        return self

    def with_context(self, context) -> "ExecutableStateMachineBuilder":
        self._context = context
        return self

    def with_message_broker(self, broker) -> "ExecutableStateMachineBuilder":
        self._broker = broker
        return self

    def with_state_topic(self, topic: str) -> "ExecutableStateMachineBuilder":
        self._state_topic = topic
        return self

    def build(self) -> ExecutableStateMachine:
        if self._registry is None:
            raise ValueError("StateRegistry must be provided via with_state_registry().")
        if self._initial_state is None:
            raise ValueError("Initial state must be provided via with_initial_state().")
        return ExecutableStateMachine(
            initial_state=self._initial_state,
            transition_rules=self._transition_rules,
            registry=self._registry,
            context=self._context,
            message_broker=self._broker,
            state_topic=self._state_topic,
        )
