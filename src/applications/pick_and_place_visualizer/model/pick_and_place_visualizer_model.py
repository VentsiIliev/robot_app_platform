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

    def start_process(self) -> None:  self._service.start_process()
    def stop_process(self) -> None:   self._service.stop_process()
    def pause_process(self) -> None:  self._service.pause_process()
    def reset_process(self) -> None:  self._service.reset_process()

