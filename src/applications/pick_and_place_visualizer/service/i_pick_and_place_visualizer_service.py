from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class MatchedItem:
    workpiece_name: str
    workpiece_id:   str
    gripper_id:     int
    orientation:    float


@dataclass
class PlacedItem:
    workpiece_name: str
    gripper_id:     int
    plane_x:        float
    plane_y:        float
    width:          float
    height:         float


@dataclass
class SimResult:
    matched:         List[MatchedItem] = field(default_factory=list)
    placements:      List[PlacedItem]  = field(default_factory=list)
    unmatched_count: int               = 0
    error:           Optional[str]     = None


class IPickAndPlaceVisualizerService(ABC):

    # ── Simulation (dry-run) ──────────────────────────────────────────

    @abstractmethod
    def run_simulation(self) -> SimResult: ...

    @abstractmethod
    def get_plane_bounds(self) -> Tuple[float, float, float, float, float]: ...

    # ── Live process control ──────────────────────────────────────────

    @abstractmethod
    def set_simulation(self, value: bool) -> None: ...

    @abstractmethod
    def start_process(self) -> None: ...

    @abstractmethod
    def stop_process(self) -> None: ...

    @abstractmethod
    def pause_process(self) -> None: ...

    @abstractmethod
    def reset_process(self) -> None: ...

    @abstractmethod
    def get_process_state(self) -> str: ...

    @abstractmethod
    def set_step_mode(self, value: bool) -> None: ...

    @abstractmethod
    def is_step_mode_enabled(self) -> bool: ...

    @abstractmethod
    def step_process(self) -> None: ...
