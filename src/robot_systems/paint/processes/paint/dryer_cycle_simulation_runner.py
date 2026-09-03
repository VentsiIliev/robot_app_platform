"""Simulate consecutive paint/dryer release cycles without robot or hardware.

Each cycle starts with stale NEXT_POSITION_DONE from the previous cycle, then
simulates a fresh MOVING transition, fresh DONE, and EJECT. Movement duration is
configurable to prove that slow dryer/RPM settings do not cause a false timeout.
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
import types
from pathlib import Path
from types import SimpleNamespace


REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPOSITORY_ROOT))

# Avoid importing the complete desktop paint application (and its optional UI
# plugins) when this runner only needs the coordinator module.
paint_package = types.ModuleType("src.robot_systems.paint")
paint_package.__path__ = [str(REPOSITORY_ROOT / "src/robot_systems/paint")]
sys.modules.setdefault("src.robot_systems.paint", paint_package)

from src.robot_systems.paint.processes.paint.dryer_release_coordinator import (
    DryerReleaseCoordinator,
)


class SimulatedDryer:
    def __init__(self, *, move_duration_s: float, eject_duration_s: float, start_delay_s: float) -> None:
        self._move_duration_s = max(0.0, move_duration_s)
        self._eject_duration_s = max(0.0, eject_duration_s)
        self._start_delay_s = max(0.0, start_delay_s)
        self._lock = threading.Lock()
        self._move_started_at: float | None = None
        self._eject_started_at: float | None = None
        self.next_position_commands = 0
        self.eject_commands = 0

    def next_position(self) -> bool:
        with self._lock:
            self.next_position_commands += 1
            self._move_started_at = time.monotonic()
            self._eject_started_at = None
        return True

    def eject(self) -> bool:
        with self._lock:
            self.eject_commands += 1
            self._eject_started_at = time.monotonic()
        return True

    def get_state(self):
        with self._lock:
            now = time.monotonic()
            move_elapsed = None if self._move_started_at is None else now - self._move_started_at
            eject_elapsed = None if self._eject_started_at is None else now - self._eject_started_at

        # Before the fresh movement transition, DONE deliberately remains set
        # from the previous cycle. The coordinator must not accept it.
        moving = bool(
            move_elapsed is not None
            and move_elapsed >= self._start_delay_s
            and move_elapsed < self._start_delay_s + self._move_duration_s
        )
        move_done = bool(
            move_elapsed is None
            or move_elapsed >= self._start_delay_s + self._move_duration_s
        )
        ejecting = bool(eject_elapsed is not None and eject_elapsed < self._eject_duration_s)
        eject_done = bool(eject_elapsed is None or eject_elapsed >= self._eject_duration_s)
        return SimpleNamespace(
            is_healthy=True,
            is_ready=not moving and not ejecting,
            raw_status=0,
            next_position_moving=moving,
            next_position_done=move_done,
            ejecting=ejecting,
            eject_done=eject_done,
            communication_errors=[],
        )


def run_cycles(*, cycles: int, move_duration_s: float, eject_duration_s: float) -> bool:
    dryer = SimulatedDryer(
        move_duration_s=move_duration_s,
        eject_duration_s=eject_duration_s,
        start_delay_s=0.05,
    )
    coordinator = DryerReleaseCoordinator(
        dryer,
        status_timeout_s=1.0,
        status_poll_interval_s=0.01,
        next_position_confirmation_delay_s=0.01,
        eject_confirmation_delay_s=0.05,
    )
    try:
        for cycle in range(1, cycles + 1):
            ready, reason = coordinator.wait_until_ready_for_release()
            print(f"cycle={cycle} pre_dropoff_ready={ready} reason={reason!r}")
            if not ready:
                return False
            if not coordinator.on_workpiece_release_verified():
                print(f"cycle={cycle} could not queue dryer release", file=sys.stderr)
                return False
            while coordinator._sequence_active:
                time.sleep(0.01)
            while dryer.get_state().ejecting:
                time.sleep(0.01)
            print(
                f"cycle={cycle} completed next_position_commands={dryer.next_position_commands} "
                f"eject_commands={dryer.eject_commands}"
            )
        ready, reason = coordinator.wait_until_ready_for_release()
        print(f"final_ready={ready} reason={reason!r}")
        return ready
    finally:
        coordinator.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--move-duration", type=float, default=2.0)
    parser.add_argument("--eject-duration", type=float, default=0.5)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    return 0 if run_cycles(
        cycles=max(1, args.cycles),
        move_duration_s=max(0.0, args.move_duration),
        eject_duration_s=max(0.0, args.eject_duration),
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
