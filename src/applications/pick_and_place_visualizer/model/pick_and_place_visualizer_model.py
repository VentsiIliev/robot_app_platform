from src.applications.base.i_application_model import IApplicationModel
from src.applications.pick_and_place_visualizer.service.i_pick_and_place_visualizer_service import (
    IPickAndPlaceVisualizerService, SimResult,
)


class PickAndPlaceVisualizerModel(IApplicationModel):

    def __init__(self, service: IPickAndPlaceVisualizerService):
        self._service = service

    def load(self):
        return self._service.get_plane_bounds()

    def save(self, *args, **kwargs) -> None:
        pass

    def run_simulation(self) -> SimResult:
        return self._service.run_simulation()

    def get_plane_bounds(self):
        return self._service.get_plane_bounds()

    def set_simulation(self, value: bool) -> None: self._service.set_simulation(value)
    def get_process_state(self) -> str:            return self._service.get_process_state()
    def set_step_mode(self, value: bool) -> None:  self._service.set_step_mode(value)
    def is_step_mode_enabled(self) -> bool:        return self._service.is_step_mode_enabled()
    def step_process(self) -> None:                self._service.step_process()
    def start_process(self) -> None:  self._service.start_process()
    def stop_process(self) -> None:   self._service.stop_process()
    def pause_process(self) -> None:  self._service.pause_process()
    def reset_process(self) -> None:  self._service.reset_process()
