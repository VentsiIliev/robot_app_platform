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


_COLOR = "#FF8C32"


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
                icon=FieldIcon.from_qta("fa5s.barcode", color=_COLOR),
            ),
            WorkpieceFormFieldSpec(
                key="name",
                label="Name",
                field_type="text",
                mandatory=False,
                icon=FieldIcon.from_qta("fa5s.tag", color=_COLOR),
            ),
            WorkpieceFormFieldSpec(
                key="description",
                label="Description",
                field_type="text",
                mandatory=False,
                icon=FieldIcon.from_qta("fa5s.align-left", color=_COLOR),
            ),
            WorkpieceFormFieldSpec(
                key="height_mm",
                label="Height (mm)",
                field_type="text",
                mandatory=False,
                icon=FieldIcon.from_qta("fa5s.ruler-vertical", color=_COLOR),
                placeholder="0.0",
                default_value=0.0,
            ),
            WorkpieceFormFieldSpec(
                key="dxfPath",
                label="DXF Path",
                field_type="text",
                mandatory=False,
                icon=FieldIcon.from_qta("fa5s.file-code", color=_COLOR),
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
            SegmentSettingSpec("rz_angle", "Rz Angle", "0", "Robot"),
            SegmentSettingSpec("preprocess_min_spacing_mm", "Preprocess Spacing (mm)", "2.5", "Interpolation"),
            SegmentSettingSpec("interpolation_spacing_mm", "Sampled Spacing (mm)", "10.0", "Interpolation"),
            SegmentSettingSpec("dense_sampling_factor", "Dense Factor", "0.25", "Interpolation"),
            SegmentSettingSpec("execution_spacing_mm", "Execution Spacing (mm)", "7.5", "Interpolation"),
            SegmentSettingSpec("path_tangent_lookahead_mm", "Tangent Lookahead (mm)", "15.0", "Interpolation"),
            SegmentSettingSpec("path_tangent_deadband_deg", "Tangent Deadband (deg)", "5.0", "Interpolation"),
        ],
    )
