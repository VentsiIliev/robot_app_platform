import logging

from src.applications.base.i_application_controller import IApplicationController
from src.applications.APPLICATION_BLUEPRINT.model.my_model import MyModel
from src.applications.APPLICATION_BLUEPRINT.view.my_view import MyView


class MyController(IApplicationController):

    def __init__(self, model: MyModel, view: MyView):
        self._model  = model
        self._view   = view
        self._logger = logging.getLogger(self.__class__.__name__)

        self._view.save_requested.connect(self._on_save)
        self._view.destroyed.connect(self.stop)

    def load(self) -> None:
        value = self._model.load()
        self._view.set_value(value)

    def stop(self) -> None:
        pass  # unsubscribe from broker topics here if needed

    def _on_save(self, value: str) -> None:
        try:
            self._model.save(value)
            self._logger.info("Saved: %s", value)
        except Exception:
            self._logger.exception("Failed to save")
