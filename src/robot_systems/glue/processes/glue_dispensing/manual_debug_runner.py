from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[5]))

from src.engine.process.executable_state_machine import StateMachineSnapshot
from src.robot_systems.glue.processes.glue_dispensing.dispensing_config import GlueDispensingConfig
from src.robot_systems.glue.processes.glue_dispensing.dispensing_context import DispensingContext
from src.robot_systems.glue.processes.glue_dispensing.dispensing_machine_factory import DispensingMachineFactory
from src.robot_systems.glue.processes.glue_dispensing.dispensing_path import (
    DispensingPathEntry,
    normalize_dispensing_paths,
)
from src.robot_systems.glue.processes.glue_dispensing.glue_pump_controller import GluePumpController

_logger = logging.getLogger(__name__)


def _point(x: float, y: float = 0.0, z: float = 0.0) -> list[float]:
    return [float(x), float(y), float(z), 0.0, 0.0, 0.0]


def _default_paths() -> list[tuple[list[list[float]], dict[str, Any]]]:
    settings = {
        "glue_type": "Type A",
        "reach_start_threshold": 1.0,
        "reach_end_threshold": 1.0,
        "motor_speed": 10000,
        "forward_ramp_steps": 1,
        "initial_ramp_speed": 5000,
        "initial_ramp_speed_duration": 1.0,
        "speed_reverse": 1000,
        "reverse_duration": 1.0,
        "reverse_ramp_steps": 1,
        "glue_speed_coefficient": 5.0,
        "glue_acceleration_coefficient": 0.0,
    }
    return [
        ([_point(1.0), _point(2.0), _point(3.0)], settings),
        ([_point(10.0), _point(11.0)], {**settings, "glue_type": "Type B"}),
    ]


@dataclass
class DebugRobotService:
    current_position: list[float] = field(default_factory=lambda: _point(0.0))
    current_velocity: float = 10.0
    current_acceleration: float = 30.0
    ptp_commands: list[dict[str, Any]] = field(default_factory=list)
    linear_commands: list[dict[str, Any]] = field(default_factory=list)
    stop_count: int = 0

    def move_ptp(self, **kwargs) -> bool:
        self.ptp_commands.append(dict(kwargs))
        return True

    def move_linear(self, **kwargs) -> bool:
        self.linear_commands.append(dict(kwargs))
        return True

    def get_current_position(self):
        return list(self.current_position)

    def get_current_velocity(self) -> float:
        return float(self.current_velocity)

    def get_current_acceleration(self) -> float:
        return float(self.current_acceleration)

    def stop_motion(self) -> None:
        self.stop_count += 1

    def set_current_position(self, position: list[float]) -> None:
        self.current_position = list(position)


@dataclass
class DebugMotorService:
    commands: list[dict[str, Any]] = field(default_factory=list)

    def turn_on(self, **kwargs) -> bool:
        self.commands.append({"command": "turn_on", **kwargs})
        return True

    def turn_off(self, **kwargs) -> bool:
        self.commands.append({"command": "turn_off", **kwargs})
        return True

    def set_speed(self, **kwargs) -> bool:
        self.commands.append({"command": "set_speed", **kwargs})
        return True


@dataclass
class DebugGeneratorController:
    commands: list[str] = field(default_factory=list)
    is_on: bool = False

    def turn_on(self) -> None:
        self.commands.append("turn_on")
        self.is_on = True

    def turn_off(self) -> None:
        self.commands.append("turn_off")
        self.is_on = False


class DebugGlueTypeResolver:
    def __init__(self, mapping: dict[str, int] | None = None) -> None:
        self._mapping = mapping or {"Type A": 1, "Type B": 2, "Type C": 3}

    def resolve(self, glue_type: str) -> int:
        return self._mapping.get(glue_type, -1)


class DispensingManualDriver:
    def __init__(
        self,
        paths: list[Any] | None = None,
        spray_on: bool = False,
        config: GlueDispensingConfig | None = None,
    ) -> None:
        self._raw_paths = list(paths or _default_paths())
        self._spray_on = spray_on
        self._config = config or GlueDispensingConfig(
            adjust_pump_speed_while_spray=spray_on,
        )
        self.robot_service = DebugRobotService()
        self.motor_service = DebugMotorService()
        self.generator = DebugGeneratorController()
        self.resolver = DebugGlueTypeResolver()
        self.context: DispensingContext | None = None
        self.machine = None
        self.reset()

    def reset(self) -> None:
        ctx = DispensingContext()
        ctx.stop_event.clear()
        ctx.run_allowed.set()
        ctx.paths = normalize_dispensing_paths(self._raw_paths)
        ctx.spray_on = self._spray_on
        ctx.motor_service = self.motor_service
        ctx.generator = self.generator
        ctx.robot_service = self.robot_service
        ctx.resolver = self.resolver
        ctx.robot_tool = self._config.robot_tool
        ctx.robot_user = self._config.robot_user
        ctx.global_velocity = self._config.global_velocity
        ctx.global_acceleration = self._config.global_acceleration
        ctx.use_segment_motion_settings = self._config.use_segment_motion_settings
        ctx.move_to_first_point_poll_s = self._config.move_to_first_point_poll_s
        ctx.move_to_first_point_timeout_s = self._config.move_to_first_point_timeout_s
        ctx.pump_thread_wait_poll_s = self._config.pump_thread_wait_poll_s
        ctx.final_position_poll_s = self._config.final_position_poll_s
        ctx.pump_ready_timeout_s = self._config.pump_ready_timeout_s
        ctx.pump_thread_join_timeout_s = self._config.pump_thread_join_timeout_s
        ctx.pump_adjuster_poll_s = self._config.pump_adjuster_poll_s
        ctx.pump_controller = GluePumpController(
            self.motor_service,
            use_segment_settings=self._config.use_segment_settings,
        )
        self.context = ctx
        self.machine = DispensingMachineFactory().build(ctx, self._config)
        self.machine.reset()

    def step(self, count: int = 1) -> bool:
        ok = True
        for _ in range(max(count, 1)):
            ok = self.machine.step()
            if not ok:
                break
        return ok

    def request_pause(self) -> None:
        self.context.run_allowed.clear()

    def resume(self) -> None:
        self.context.is_resuming = True
        self.context.run_allowed.set()

    def request_stop(self) -> None:
        self.context.stop_event.set()
        self.context.run_allowed.set()

    def clear_stop(self) -> None:
        self.context.stop_event.clear()

    def set_robot_position(self, position: list[float]) -> None:
        self.robot_service.set_current_position(position)

    def move_robot_to_current_start(self) -> None:
        if self.context.current_path:
            self.set_robot_position(self.context.current_path[0])

    def move_robot_to_current_end(self) -> None:
        if self.context.current_path:
            self.set_robot_position(self.context.current_path[-1])

    def get_snapshot(self) -> dict[str, Any]:
        machine_snapshot: StateMachineSnapshot = self.machine.get_snapshot()
        return {
            "machine": {
                "initial_state": machine_snapshot.initial_state.name,
                "current_state": machine_snapshot.current_state.name,
                "is_running": machine_snapshot.is_running,
                "step_count": machine_snapshot.step_count,
                "last_state": getattr(machine_snapshot.last_state, "name", None),
                "last_next_state": getattr(machine_snapshot.last_next_state, "name", None),
                "last_error": machine_snapshot.last_error,
            },
            "context": self.context.build_debug_snapshot(),
            "robot": {
                "current_position": list(self.robot_service.current_position),
                "current_velocity": self.robot_service.current_velocity,
                "current_acceleration": self.robot_service.current_acceleration,
                "ptp_commands": list(self.robot_service.ptp_commands),
                "linear_commands": list(self.robot_service.linear_commands),
                "stop_count": self.robot_service.stop_count,
            },
            "motor": {
                "commands": list(self.motor_service.commands),
            },
            "generator": {
                "is_on": self.generator.is_on,
                "commands": list(self.generator.commands),
            },
        }

    def format_snapshot(self) -> str:
        return json.dumps(self.get_snapshot(), indent=2, sort_keys=True)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manual glue dispensing state-machine driver")
    parser.add_argument("--spray-on", action="store_true", help="Enable generator/pump states")
    parser.add_argument(
        "--adjust-pump",
        action="store_true",
        help="Enable dynamic pump-speed adjustment thread",
    )
    parser.add_argument(
        "--log-level",
        default="DEBUG",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Python logging level",
    )
    return parser


def _print_help() -> None:
    print("Commands:")
    print("  show                     print machine + context snapshot")
    print("  step [n]                 execute one or more states")
    print("  start-point              move fake robot to current path start")
    print("  end-point                move fake robot to current path end")
    print("  pos x y z [rx ry rz]     set fake robot position")
    print("  motion vel acc           set fake robot velocity/acceleration")
    print("  pause                    clear run_allowed")
    print("  resume                   set is_resuming=True and allow running")
    print("  stop                     set stop_event")
    print("  clear-stop               clear stop_event")
    print("  reset                    rebuild fresh context + machine")
    print("  help                     show this help")
    print("  quit                     exit")


def _run_cli(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s %(name)s: %(message)s",
    )

    driver = DispensingManualDriver(
        spray_on=args.spray_on,
        config=GlueDispensingConfig(
            adjust_pump_speed_while_spray=args.adjust_pump,
            turn_off_pump_between_paths=True,
        ),
    )

    print("Manual glue dispensing driver")
    print("Type 'help' for commands.")
    print(driver.format_snapshot())

    while True:
        try:
            raw = input("> ").strip()
        except EOFError:
            print()
            return 0

        if not raw:
            continue

        parts = raw.split()
        command = parts[0].lower()

        try:
            if command == "help":
                _print_help()
                continue
            if command == "show":
                print(driver.format_snapshot())
                continue
            if command == "step":
                count = int(parts[1]) if len(parts) > 1 else 1
                driver.step(count)
                print(driver.format_snapshot())
                continue
            if command == "start-point":
                driver.move_robot_to_current_start()
                print(driver.format_snapshot())
                continue
            if command == "end-point":
                driver.move_robot_to_current_end()
                print(driver.format_snapshot())
                continue
            if command == "pos":
                if len(parts) not in {4, 7}:
                    raise ValueError("pos expects 3 or 6 numeric values")
                position = [float(value) for value in parts[1:]]
                if len(position) == 3:
                    position.extend([0.0, 0.0, 0.0])
                driver.set_robot_position(position)
                print(driver.format_snapshot())
                continue
            if command == "motion":
                if len(parts) != 3:
                    raise ValueError("motion expects velocity and acceleration")
                driver.robot_service.current_velocity = float(parts[1])
                driver.robot_service.current_acceleration = float(parts[2])
                print(driver.format_snapshot())
                continue
            if command == "pause":
                driver.request_pause()
                print(driver.format_snapshot())
                continue
            if command == "resume":
                driver.resume()
                print(driver.format_snapshot())
                continue
            if command == "stop":
                driver.request_stop()
                print(driver.format_snapshot())
                continue
            if command == "clear-stop":
                driver.clear_stop()
                print(driver.format_snapshot())
                continue
            if command == "reset":
                driver.reset()
                print(driver.format_snapshot())
                continue
            if command in {"quit", "exit"}:
                return 0

            print(f"Unknown command: {command}")
        except Exception as exc:
            _logger.exception("Command failed")
            print(f"Command failed: {exc}")


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()
    return _run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
