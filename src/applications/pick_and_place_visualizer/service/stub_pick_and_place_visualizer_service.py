from src.applications.pick_and_place_visualizer.service.i_pick_and_place_visualizer_service import (
    IPickAndPlaceVisualizerService, SimResult, MatchedItem, PlacedItem,
)


class StubPickAndPlaceVisualizerService(IPickAndPlaceVisualizerService):
    def __init__(self):
        self._step_mode = False


    def run_simulation(self) -> SimResult:
        return SimResult(
            matched=[
                MatchedItem("Alpha",  "1", gripper_id=11, orientation=45.0),
                MatchedItem("Beta",   "2", gripper_id=11, orientation=20.0),
                MatchedItem("Gamma",  "3", gripper_id=12, orientation=90.0),
            ],
            placements=[
                PlacedItem("Alpha", 11, plane_x=-360.0, plane_y=380.0, width=100.0, height=80.0),
                PlacedItem("Beta",  11, plane_x=-240.0, plane_y=380.0, width=90.0,  height=70.0),
                PlacedItem("Gamma", 12, plane_x=-130.0, plane_y=380.0, width=110.0, height=85.0),
            ],
            unmatched_count=1,
        )

    def get_plane_bounds(self):
        return -450.0, 350.0, 300.0, 700.0, 30.0

    def start_process(self) -> None:
        print("[Stub] start_process")

    def stop_process(self) -> None:
        print("[Stub] stop_process")

    def pause_process(self) -> None:
        print("[Stub] pause_process")

    def reset_process(self) -> None:
        print("[Stub] reset_process")

    def set_simulation(self, value: bool) -> None:
        print(f"[Stub] set_simulation({value})")

    def get_process_state(self) -> str:
        return "idle"

    def set_step_mode(self, value: bool) -> None:
        self._step_mode = bool(value)
        print(f"[Stub] set_step_mode({value})")

    def is_step_mode_enabled(self) -> bool:
        return self._step_mode

    def step_process(self) -> None:
        print("[Stub] step_process")
