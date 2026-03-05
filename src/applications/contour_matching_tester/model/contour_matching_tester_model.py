import logging
from typing import Optional, Tuple

from src.applications.base.i_application_model import IApplicationModel
from src.applications.contour_matching_tester.service.i_contour_matching_tester_service import IContourMatchingTesterService


class ContourMatchingTesterModel(IApplicationModel):

    def __init__(self, service: IContourMatchingTesterService):
        self._service = service
        self._workpieces: list = []
        self._last_result: Optional[dict] = None
        self._logger = logging.getLogger(self.__class__.__name__)

    def load(self) -> None:
        pass

    def save(self, *args, **kwargs) -> None:
        pass

    def load_workpieces(self) -> list:
        self._workpieces = self._service.get_workpieces()
        self._logger.info("Loaded %d workpieces", len(self._workpieces))
        return self._workpieces

    def run_matching(self) -> Tuple[dict, int]:
        contours = self._service.get_latest_contours()
        result, no_match_count = self._service.run_matching(self._workpieces, contours)
        self._last_result = result
        self._logger.info(
            "Matching done: %d matched, %d unmatched",
            len(result.get("workpieces", [])),
            no_match_count,
        )
        return result, no_match_count

    @property
    def workpieces(self) -> list:
        return self._workpieces

    @property
    def last_result(self) -> Optional[dict]:
        return self._last_result

