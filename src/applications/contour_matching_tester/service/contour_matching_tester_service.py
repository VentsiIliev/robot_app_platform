from typing import Tuple

from src.applications.contour_matching_tester.service.i_contour_matching_tester_service import IContourMatchingTesterService


class ContourMatchingTesterService(IContourMatchingTesterService):

    def __init__(self, vision_service=None, workpiece_service=None):
        self._vision_service = vision_service
        self._workpiece_service = workpiece_service

    def get_workpieces(self) -> list:
        if self._workpiece_service is None:
            return []
        workpieces = []
        for meta in self._workpiece_service.list_all():
            wp = self._workpiece_service.load(meta["id"])
            if wp is not None:
                workpieces.append(wp)
        return workpieces


    def get_latest_contours(self) -> list:
        if self._vision_service is None:
            return []
        return self._vision_service.get_latest_contours()

    def run_matching(self, workpieces: list, contours: list) -> Tuple[dict, int]:
        from src.engine.vision.implementation.VisionSystem.features.contour_matching import find_matching_workpieces
        result, no_matches, _ = find_matching_workpieces(workpieces, contours)
        return result, len(no_matches)

