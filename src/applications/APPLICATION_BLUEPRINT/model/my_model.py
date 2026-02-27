import logging
from typing import Optional

from src.applications.base.i_application_model import IApplicationModel
from src.applications.APPLICATION_BLUEPRINT.service.i_my_service import IMyService


class MyModel(IApplicationModel):

    def __init__(self, service: IMyService):
        self._service = service
        self._value: Optional[str] = None
        self._logger  = logging.getLogger(self.__class__.__name__)

    def load(self) -> str:
        self._value = self._service.get_value()
        self._logger.debug("Loaded: %s", self._value)
        return self._value

    def save(self, value: str, **kwargs) -> None:
        self._service.save_value(value)
        self._value = value
        self._logger.info("Saved: %s", value)

    @property
    def value(self) -> Optional[str]:
        return self._value
