from src.applications.base.i_application_model import IApplicationModel
from src.applications.software_update.service.i_software_update_service import ISoftwareUpdateService


class SoftwareUpdateModel(IApplicationModel):
    def __init__(self, service: ISoftwareUpdateService):
        self._service = service

    def load(self) -> dict:
        return self._service.get_status()

    def save(self) -> None:
        self._service.schedule_installation()

    def check(self) -> dict:
        return self._service.check()

    def download(self) -> dict:
        return self._service.download()
