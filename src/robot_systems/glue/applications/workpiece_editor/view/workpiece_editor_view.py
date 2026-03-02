import logging
from typing import List

from PyQt6.QtWidgets import QVBoxLayout, QLabel
from PyQt6.QtCore import pyqtSignal
from contour_editor import SettingsGroup, BezierSegmentManager, SettingsConfig

from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.config import WorkpieceFormSchema
from src.robot_systems.glue.settings.glue import GlueSettingKey

from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.config.glue_settings_provider import \
    GlueSettingsProvider

from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor import WorkpieceEditorBuilder

from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.config import WorkpieceFormFactory, \
    SegmentSettingsProvider

from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.config.virtual_keyboard_widget_factory import \
    VirtualKeyboardWidgetFactory
from src.applications.base.i_application_view import IApplicationView
from src.robot_systems.glue.workpieces.model.glue_workpiece_filed import GlueWorkpieceField

_logger = logging.getLogger(__name__)


class WorkpieceEditorView(IApplicationView):

    save_requested    = pyqtSignal(dict)
    execute_requested = pyqtSignal(dict)

    def __init__(self,schema: WorkpieceFormSchema, parent=None):
        self._schema = schema
        self._editor           = None
        self._capture_handler  = None   # set by controller via set_capture_handler()
        super().__init__("WorkpieceEditor", parent)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        try:
            self._editor = self._build_editor()
            layout.addWidget(self._editor)
        except Exception as exc:
            _logger.exception("WorkpieceEditorView: failed to build editor")
            layout.addWidget(QLabel(f"WorkpieceEditor failed:\n{exc}"))

    def clean_up(self) -> None:
        pass

    def _build_editor(self):


        glue_types = self._schema.get_options(GlueWorkpieceField.GLUE_TYPE.value)
        settings_provider = SegmentSettingsProvider(material_types=glue_types)
        default_settings  = settings_provider.get_default_values()

        config = SettingsConfig(
            default_settings=default_settings,
            groups=[
                SettingsGroup("General", [
                    GlueSettingKey.SPRAY_WIDTH.value,
                    GlueSettingKey.SPRAYING_HEIGHT.value,
                    GlueSettingKey.GLUE_TYPE.value,
                ]),
                SettingsGroup("Forward Motion", [
                    GlueSettingKey.FORWARD_RAMP_STEPS.value,
                    GlueSettingKey.INITIAL_RAMP_SPEED.value,
                    GlueSettingKey.INITIAL_RAMP_SPEED_DURATION.value,
                    GlueSettingKey.MOTOR_SPEED.value,
                ]),
                SettingsGroup("Reverse Motion", [
                    GlueSettingKey.REVERSE_DURATION.value,
                    GlueSettingKey.SPEED_REVERSE.value,
                    GlueSettingKey.REVERSE_RAMP_STEPS.value,
                ]),
                SettingsGroup("Robot", [
                    "velocity", "acceleration",
                    GlueSettingKey.RZ_ANGLE.value,
                    "adaptive_spacing_mm",
                    "spline_density_multiplier",
                    "smoothing_lambda",
                ]),
                SettingsGroup("Generator", [
                    GlueSettingKey.TIME_BETWEEN_GENERATOR_AND_GLUE.value,
                    GlueSettingKey.GENERATOR_TIMEOUT.value,
                ]),
                SettingsGroup("Thresholds (mm)", [
                    GlueSettingKey.REACH_START_THRESHOLD.value,
                    GlueSettingKey.REACH_END_THRESHOLD.value,
                ]),
                SettingsGroup("Pump Speed", [
                    "glue_speed_coefficient",
                    "glue_acceleration_coefficient",
                ]),
            ],
            combo_field_key=GlueSettingKey.GLUE_TYPE.value,
        )

        form_factory = WorkpieceFormFactory(
            schema=self._schema)  # was: WorkpieceFormFactory(glue_types=self._glue_types)

        provider = GlueSettingsProvider(
            default_settings  = default_settings,
            material_types    = glue_types,
            material_type_key = GlueSettingKey.GLUE_TYPE.value,
        )

        return (
            WorkpieceEditorBuilder()
            .with_segment_manager(BezierSegmentManager)
            .with_settings(config, provider)
            .with_form(form_factory)
            .with_widgets(VirtualKeyboardWidgetFactory())
            .on_save(self._on_save_cb)
            .on_capture(self._on_capture_cb)
            .on_execute(self._on_execute_cb)
            .on_update_camera_feed(self._on_camera_feed_cb)
            .build()
        )

    def set_capture_handler(self, handler) -> None:
        """Controller injects its get_contours callable here."""
        self._capture_handler = handler

    # ── Callbacks from editor → emit signals ─────────────────────────

    def _on_save_cb(self, data: dict) -> None:
        self.save_requested.emit(data)

    def _on_execute_cb(self, data: dict) -> None:
        self.execute_requested.emit(data)

    def _on_capture_cb(self) -> list:
        """Called synchronously by the editor — must return contours."""
        if self._capture_handler is not None:
            try:
                return self._capture_handler() or []
            except Exception as exc:
                _logger.error("capture handler failed: %s", exc)
        return []

    def _on_camera_feed_cb(self) -> None:
        pass

    # ── Public API ────────────────────────────────────────────────────

    def update_camera_feed(self, image) -> None:
        if self._editor is not None and image is not None:
            if hasattr(self._editor, "set_image"):
                self._editor.set_image(image)

    def update_contours(self, contours: list) -> None:
        if self._editor is None:
            return
        try:
            editor = self._editor.contourEditor.editor_with_rulers.editor
            if hasattr(editor, "set_contours"):
                editor.set_contours(contours)
        except AttributeError:
            pass