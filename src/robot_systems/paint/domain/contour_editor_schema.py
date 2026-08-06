from src.applications.workpiece_editor.editor_core.config.workpiece_form_schema import (
    FieldIcon,
    WorkpieceFormFieldSpec,
    WorkpieceFormSchema,
)
from contour_editor import ContourEditorLayerConfig, LayerRoleConfig
from src.applications.workpiece_editor.editor_core.config.segment_settings_schema import (
    SegmentSettingSpec,
    SegmentSettingsSchema,
)


_ICON_COLOR = "#905BA9"


def build_paint_layer_config() -> ContourEditorLayerConfig:
    return ContourEditorLayerConfig(
        roles={
            "workpiece": LayerRoleConfig("workpiece", "Workpiece", "#FF8C32", visible=True, enabled=True),
            "contour": LayerRoleConfig("contour", "Contour", "#00FFFF", visible=False, enabled=False),
            "fill": LayerRoleConfig("fill", "Fill", "#00FF00", visible=False, enabled=False),
        },
        default_segment_role="workpiece",
    )


def build_paint_contour_form_schema() -> WorkpieceFormSchema:
    return WorkpieceFormSchema(
        id_key="workpieceId",
        combo_key="",
        editor_layer_config=build_paint_layer_config(),
        fields=[
            WorkpieceFormFieldSpec(
                key="workpieceId",
                label="Workpiece ID",
                field_type="text",
                mandatory=True,
                icon=FieldIcon.from_qta("fa5s.barcode", color=_ICON_COLOR),
            ),
            WorkpieceFormFieldSpec(
                key="name",
                label="Name",
                field_type="text",
                mandatory=False,
                icon=FieldIcon.from_qta("fa5s.tag", color=_ICON_COLOR),
            ),
            WorkpieceFormFieldSpec(
                key="description",
                label="Description",
                field_type="text",
                mandatory=False,
                icon=FieldIcon.from_qta("fa5s.align-left", color=_ICON_COLOR),
            ),
            WorkpieceFormFieldSpec(
                key="height_mm",
                label="Height (mm)",
                field_type="text",
                mandatory=False,
                icon=FieldIcon.from_qta("fa5s.ruler-vertical", color=_ICON_COLOR),
                placeholder="0.0",
                default_value=0.0,
            ),
        ],
    )


def build_paint_segment_settings_schema() -> SegmentSettingsSchema:
    return SegmentSettingsSchema(
        combo_key="",
        combo_options=[],
        fields=[
            SegmentSettingSpec("velocity", "Velocity", "10", "Robot"),
            SegmentSettingSpec("acceleration", "Acceleration", "10", "Robot"),
            SegmentSettingSpec("offset", "Pivot Offset (mm)", "0", "Robot"),
            SegmentSettingSpec("edge_cleanup_z_offset_mm", "Cleanup Z Offset (mm)", "0", "Robot"),
        ],
    )
