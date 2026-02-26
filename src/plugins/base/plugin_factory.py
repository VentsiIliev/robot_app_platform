from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from pl_gui.shell.base_app_widget.AppWidget import AppWidget
from src.plugins.base.i_plugin_controller import IPluginController
from src.plugins.base.i_plugin_model import IPluginModel
from src.plugins.base.i_plugin_view import IPluginView


class PluginFactory(ABC):
    """
    Template-method factory for all MVC plugins.

    Subclasses implement the three abstract factory methods.
    This base class owns:
      - the wiring order  (model → view → controller)
      - the GC fix        (view._controller = controller)
      - the load call     (controller.load())

    Usage:
        class MyPluginFactory(PluginFactory):
            def _create_model(self, service): return MyModel(service)
            def _create_view(self):           return MyView()
            def _create_controller(self, model, view): return MyController(model, view)

        widget = MyPluginFactory().build(service)
    """

    _logger = logging.getLogger("PluginFactory")

    @abstractmethod
    def _create_model(self, service) -> IPluginModel: ...

    @abstractmethod
    def _create_view(self) -> IPluginView: ...

    @abstractmethod
    def _create_controller(self, model: IPluginModel, view: IPluginView) -> IPluginController: ...

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