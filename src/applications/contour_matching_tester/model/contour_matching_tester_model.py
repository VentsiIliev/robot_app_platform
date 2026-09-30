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
        self._selected_index:    Optional[int] = None
        self._last_result:        Optional[dict] = None
        self._logger = logging.getLogger(self.__class__.__name__)

    def load(self) -> None:
        pass

    def save(self, *args, **kwargs) -> None:
        pass

    def load_workpieces(self) -> list:
        self._workpieces = self._service.get_workpieces()
        self._selected_index = None
        self._last_result = None
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

    def select_workpiece(self, index: int) -> bool:
        if index < 0 or index >= len(self._workpieces):
            self._selected_index = None
            self._last_result = None
            return False
        self._selected_index = index
        self._last_result = None
        return True

    def run_matching(self, selected_index: int) -> Tuple[dict, int, List, List]:
        if selected_index < 0 or selected_index >= len(self._workpieces):
            raise ValueError("Select a saved workpiece before matching")
        contours = self._captured_contours if self._is_captured else self._service.get_latest_contours()
        selected = self._workpieces[selected_index]
        result, no_match_count, matched, unmatched = self._service.run_matching([selected], contours)
        self._last_result = result
        self._logger.info(
            "Matching selected workpiece %r: %d matched, %d unmatched",
            getattr(selected, "name", selected_index),
            len(result.get("workpieces", [])),
            no_match_count,
        )
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
    def selected_index(self) -> Optional[int]:
        return self._selected_index

    @property
    def captured_contours(self) -> list:
        return self._captured_contours

    @property
    def last_result(self) -> Optional[dict]:
        return self._last_result
