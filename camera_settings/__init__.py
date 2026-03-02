from PyQt6.QtWidgets import QWidget

from src.plugin.base_settings_plugin.base_settings_plugin import BaseSettingsPlugin
from src.plugin.utils_widgets.clickable_label import ClickableLabel

from src.plugin.camera_settings.controller import CameraSettingsController
from src.plugin.camera_settings.model import CameraSettingsModel
from src.plugin.camera_settings.ICameraSettingsService import ISettingsPersistenceService, ICameraActionsService
from src.plugin.camera_settings.ISettingsMapper import ISettingsMapper
from src.plugin.camera_settings.view.camera_tab import camera_tab_factory
from src.plugin.camera_settings.view.camera_settings_view import CameraSettingsView


class CameraSettingsPlugin(
    BaseSettingsPlugin[
        ISettingsPersistenceService,  # Service (persistence only)
        CameraSettingsModel,
        CameraSettingsController,
        CameraSettingsView
    ]
):
    """
    Camera settings plugin.

    Accepts three injected dependencies — all plugin-owned protocols:
        persistence : ISettingsPersistenceService  — load / save settings
        actions     : ICameraActionsService        — raw mode, capture, calibration
        mapper      : ISettingsMapper              — CameraSettingsData ↔ flat dict

    Usage:
        plugin = CameraSettingsPlugin(persistence=..., actions=..., mapper=...)
        plugin.load()
        window.setCentralWidget(plugin.widget)
    """

    def __init__(
        self,
        persistence: ISettingsPersistenceService,
        actions: ICameraActionsService,
        mapper: ISettingsMapper,
    ):
        self._actions = actions
        self._mapper = mapper
        super().__init__(persistence)

    # ── BaseSettingsPlugin overrides ──────────────────────────────────────

    def _create_model(self, service: ISettingsPersistenceService) -> CameraSettingsModel:
        return CameraSettingsModel(service)

    def _create_view(self) -> CameraSettingsView:
        view, settings_view = camera_tab_factory(mapper=self._mapper.to_flat_dict)
        self._connect_actions(view)
        return view

    def _create_controller(self, model: CameraSettingsModel, view: CameraSettingsView) -> CameraSettingsController:
        return CameraSettingsController(model, view, self._mapper)

    # ── Private helpers ───────────────────────────────────────────────────

    def _connect_actions(self, view: CameraSettingsView) -> None:
        ctrl = view.controls
        ctrl.raw_mode_toggled.connect(self._actions.set_raw_mode)
        ctrl.capture_requested.connect(self._actions.capture_image)
        ctrl.calibrate_camera_requested.connect(self._actions.calibrate_camera)
        ctrl.calibrate_robot_requested.connect(self._actions.calibrate_robot)

    # ── Convenience accessors ────────────────────────────────────────────

    @property
    def preview_label(self) -> ClickableLabel | None:
        return self.widget.preview_label

    def set_preview_widget(self, widget: QWidget) -> None:
        self.widget.set_preview_widget(widget)

