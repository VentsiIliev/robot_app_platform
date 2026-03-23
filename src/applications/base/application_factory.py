from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from pl_gui.shell.base_app_widget.AppWidget import AppWidget
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.jog_controller import JogController


def finalize_application_build(
    *,
    logger: logging.Logger,
    factory_name: str,
    model: IApplicationModel,
    view: IApplicationView,
    controller: IApplicationController,
    messaging=None,
    jog_service=None,
) -> AppWidget:
    jog = None
    if getattr(view, "SHOW_JOG_WIDGET", False) and messaging is not None and jog_service is not None:
        jog = JogController(view, jog_service, messaging)
        jog.start()
        view._jog_controller = jog

    controller.load()
    view._controller = controller  # transfers ownership — prevents GC killing signal connections

    _original_clean_up = view.clean_up

    def _clean_up():
        if jog is not None:
            jog.stop()
        controller.stop()
        _original_clean_up()

    view.clean_up = _clean_up

    logger.debug(
        "%s built: %s / %s / %s",
        factory_name,
        type(model).__name__,
        type(view).__name__,
        type(controller).__name__,
    )
    return view


class ApplicationFactory(ABC):
    """
    Template-method factory for all MVC applications.

    Subclasses implement the three abstract factory methods.
    This base class owns:
      - the wiring order        (model → view → controller)
      - the GC fix              (view._controller = controller)
      - the load call           (controller.load())
      - the teardown wiring     (view.clean_up → controller.stop())

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

    def _finalize_build(
        self,
        *,
        model: IApplicationModel,
        view: IApplicationView,
        controller: IApplicationController,
        messaging=None,
        jog_service=None,
    ) -> AppWidget:
        return finalize_application_build(
            logger=self._logger,
            factory_name=self.__class__.__name__,
            model=model,
            view=view,
            controller=controller,
            messaging=messaging,
            jog_service=jog_service,
        )

    def build(self, service, messaging=None, jog_service=None) -> AppWidget:
        model      = self._create_model(service)
        view       = self._create_view()
        controller = self._create_controller(model, view)
        return self._finalize_build(
            model=model,
            view=view,
            controller=controller,
            messaging=messaging,
            jog_service=jog_service,
        )
