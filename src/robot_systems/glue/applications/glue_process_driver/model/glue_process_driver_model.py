import logging

from src.applications.base.i_application_model import IApplicationModel
from src.robot_systems.glue.applications.glue_process_driver.service.i_glue_process_driver_service import (
    IGlueProcessDriverService,
)


class GlueProcessDriverModel(IApplicationModel):
    def __init__(self, service: IGlueProcessDriverService):
        self._service = service
        self._process_snapshot = None
        self._match_result = None
        self._match_summary = None
        self._matched_workpieces = []
        self._latest_job = None
        self._latest_job_summary = None
        self._logger = logging.getLogger(self.__class__.__name__)

    def load(self):
        self._process_snapshot = self._service.get_process_snapshot()
        return self._process_snapshot

    def save(self, *args, **kwargs) -> None:
        pass

    def capture_and_match(self) -> dict:
        self._match_result = self._service.capture_and_match()
        self._matched_workpieces = self._service.get_latest_matched_workpieces()
        self._match_summary = self._service.get_latest_match_summary()
        return self._match_result

    def get_latest_matched_workpieces(self) -> list:
        return list(self._matched_workpieces)

    def get_match_summary(self):
        return self._match_summary

    def build_job(self, selected_indexes: list[int] | None = None):
        if selected_indexes is not None:
            self._service.select_matched_workpieces(selected_indexes)
        self._latest_job = self._service.build_job_from_latest_match()
        self._latest_job_summary = self._service.get_latest_job_summary()
        return self._latest_job

    def get_latest_job(self):
        return self._latest_job

    def get_latest_job_summary(self):
        return self._latest_job_summary

    def get_process_snapshot(self):
        return self._process_snapshot

    def refresh_process_snapshot(self):
        self._process_snapshot = self._service.get_process_snapshot()
        return self._process_snapshot

    def load_job(self, spray_on: bool) -> None:
        self._service.load_latest_job(spray_on=spray_on)

    def set_manual_mode(self, enabled: bool) -> None:
        self._service.set_manual_mode(enabled)
        self.refresh_process_snapshot()

    def step_once(self):
        self._process_snapshot = self._service.step_once()
        return self._process_snapshot

    def start(self) -> None:
        self._service.start()

    def pause(self) -> None:
        self._service.pause()

    def resume(self) -> None:
        self._service.resume()

    def stop(self) -> None:
        self._service.stop()

    def reset_errors(self) -> None:
        self._service.reset_errors()
