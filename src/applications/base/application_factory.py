from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from pl_gui.shell.base_app_widget.AppWidget import AppWidget
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView


class ApplicationFactory(ABC):
    """
    Template-method factory for all MVC applications.

    Subclasses implement the three abstract factory methods.
    This base class owns:
      - the wiring order  (model → view → controller)
      - the GC fix        (view._controller = controller)
      - the load call     (controller.load())

    Usage:
        class MyApplicationFactory(ApplicationFactory):
            def _create_model(self, service): return MyModel(service)
            def _create_view(self):           return MyView()
            def _create_controller(self, model, view): return MyController(model, view)

        widget = MyApplicationFactory().build(service)
    """

    _logger = logging.getLogger("ApplicationFactory")

    @abstractmethod
    def _create_model(self, service) -> IApplicationModel: ...

    @abstractmethod
    def _create_view(self) -> IApplicationView: ...

    @abstractmethod
    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController: ...

    def build(self, service) -> AppWidget:
        model      = self._create_model(service)
        view       = self._create_view()
        controller = self._create_controller(model, view)
        controller.load()
        view._controller = controller  # transfers ownership — prevents GC killing signal connections
        self._logger.debug(
            "%s built: %s / %s / %s",
            self.__class__.__name__,
            type(model).__name__,
            type(view).__name__,
            type(controller).__name__,
        )
        return view