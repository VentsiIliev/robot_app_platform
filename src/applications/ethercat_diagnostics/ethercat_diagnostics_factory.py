from __future__ import annotations

from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.ethercat_diagnostics.controller.ethercat_diagnostics_controller import (
    EthercatDiagnosticsController,
)
from src.applications.ethercat_diagnostics.model.ethercat_diagnostics_model import (
    EthercatDiagnosticsModel,
)
from src.applications.ethercat_diagnostics.service.i_ethercat_diagnostics_service import (
    IEthercatDiagnosticsService,
)
from src.applications.ethercat_diagnostics.view.ethercat_diagnostics_view import (
    EthercatDiagnosticsView,
)


class EthercatDiagnosticsFactory(ApplicationFactory):
    def _create_model(self, service: IEthercatDiagnosticsService) -> IApplicationModel:
        return EthercatDiagnosticsModel(service)

    def _create_view(self) -> IApplicationView:
        return EthercatDiagnosticsView()

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        return EthercatDiagnosticsController(model, view)
