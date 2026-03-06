import logging
from typing import List, Optional, Tuple

from src.applications.base.i_application_model import IApplicationModel
from src.applications.contour_matching_tester.service.i_contour_matching_tester_service import IContourMatchingTesterService


class ContourMatchingTesterModel(IApplicationModel):

    def __init__(self, service: IContourMatchingTesterService):
        self._service             = service
        self._workpieces:         list          = []
        self._captured_contours:  list          = []
        self._is_captured:        bool          = False
        self._last_result:        Optional[dict] = None
        self._logger = logging.getLogger(self.__class__.__name__)

    def load(self) -> None:
        pass

    def save(self, *args, **kwargs) -> None:
        pass

    def load_workpieces(self) -> list:
        self._workpieces = self._service.get_workpieces()
        self._logger.info("Loaded %d workpieces", len(self._workpieces))
        return self._workpieces

    def capture(self) -> list:
        self._captured_contours = self._service.get_latest_contours()
        self._is_captured       = True
        self._logger.info("Captured %d contours", len(self._captured_contours))
        return self._captured_contours

    def release_capture(self) -> None:
        self._captured_contours = []
        self._is_captured       = False

    def run_matching(self) -> Tuple[dict, int, List, List]:
        contours = self._captured_contours if self._is_captured else self._service.get_latest_contours()
        result, no_match_count, matched, unmatched = self._service.run_matching(self._workpieces, contours)
        self._last_result = result
        self._logger.info("Matching done: %d matched, %d unmatched", len(result.get("workpieces", [])), no_match_count)
        return result, no_match_count, matched, unmatched

    def get_thumbnail(self, workpiece_index: int) -> Optional[bytes]:
        return self._service.get_thumbnail(workpiece_index)

    @property
    def is_captured(self) -> bool:
        return self._is_captured

    @property
    def workpieces(self) -> list:
        return self._workpieces

    @property
    def last_result(self) -> Optional[dict]:
        return self._last_result
