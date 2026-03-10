import logging
from typing import Tuple, Optional

from src.robot_systems.glue.domain.matching.i_matching_service import IMatchingService
from src.robot_systems.glue.processes.pick_and_place.config import PickAndPlaceConfig
from src.robot_systems.glue.processes.pick_and_place.plane import Plane
from src.robot_systems.glue.processes.pick_and_place.plane_management import PlaneManagementService
from src.robot_systems.glue.processes.pick_and_place.placement_calculator import PlacementCalculator
from src.engine.vision.implementation.VisionSystem.core.models.contour import Contour
from src.engine.process.i_process import IProcess
from src.applications.pick_and_place_visualizer.service.i_pick_and_place_visualizer_service import (
    IPickAndPlaceVisualizerService, SimResult, MatchedItem, PlacedItem,
)

_logger = logging.getLogger(__name__)


class PickAndPlaceVisualizerService(IPickAndPlaceVisualizerService):

    def __init__(
        self,
        matching_service:       IMatchingService,
        config:                 PickAndPlaceConfig,
        pick_and_place_process: Optional[IProcess] = None,
    ):
        self._matching  = matching_service
        self._config    = config
        self._process   = pick_and_place_process

    def start_process(self) -> None:
        if self._process:
            self._process.start()

    def stop_process(self) -> None:
        if self._process:
            self._process.stop()

    def pause_process(self) -> None:
        if self._process:
            self._process.pause()

    def reset_process(self) -> None:
        if self._process:
            self._process.reset_errors()

    def run_simulation(self) -> SimResult:
        try:
            result, no_match_count, _, _ = self._matching.run_matching()
            workpieces   = result.get("workpieces", [])
            orientations = result.get("orientations", [])

            if not workpieces:
                if no_match_count == 0:
                    return SimResult(error="No contours detected — check camera and lighting")
                return SimResult(unmatched_count=no_match_count,
                                 error="No workpieces matched any known template")

            plane     = Plane(self._config.plane)
            plane_mgr = PlaneManagementService(plane)
            calc      = PlacementCalculator(plane_mgr, self._config)

            matched_items: list = []
            placed_items:  list = []

            for wp, orientation in zip(workpieces, orientations):
                cnt_obj = Contour(wp.get_main_contour())
                r = calc.calculate(cnt_obj, float(orientation), float(wp.height), wp.gripperID)

                matched_items.append(MatchedItem(
                    workpiece_name=str(getattr(wp, "name",      "?")),
                    workpiece_id  =str(getattr(wp, "id",        "?")),
                    gripper_id    =int(wp.gripperID),
                    orientation   =float(orientation),
                ))

                if r.success and r.placement:
                    dims = r.placement.dimensions
                    tgt  = r.placement.target_position
                    placed_items.append(PlacedItem(
                        workpiece_name=str(getattr(wp, "name", "?")),
                        gripper_id    =int(wp.gripperID),
                        plane_x       =tgt.x,
                        plane_y       =tgt.y,
                        width         =dims.width,
                        height        =dims.height,
                    ))
                    plane_mgr.advance_for_next(dims.width)

            return SimResult(
                matched=matched_items,
                placements=placed_items,
                unmatched_count=no_match_count,
            )

        except Exception:
            _logger.exception("Simulation failed")
            return SimResult(error="Simulation failed — see logs for details")

    def get_plane_bounds(self) -> Tuple[float, float, float, float, float]:
        pc = self._config.plane
        return pc.x_min, pc.x_max, pc.y_min, pc.y_max, pc.spacing