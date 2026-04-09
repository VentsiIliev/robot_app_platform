from src.applications.workpiece_editor.editor_core.config.workpiece_form_schema import (
    FieldIcon,
    WorkpieceFormFieldSpec,
    WorkpieceFormSchema,
)
from src.applications.workpiece_editor.editor_core.config.segment_settings_schema import (
    SegmentSettingSpec,
    SegmentSettingsSchema,
)


_COLOR = "#FF8C32"


def build_paint_contour_form_schema() -> WorkpieceFormSchema:
    return WorkpieceFormSchema(
        id_key="workpieceId",
        combo_key="",
        fields=[
            WorkpieceFormFieldSpec(
                key="workpieceId",
                label="Contour ID",
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
            SegmentSettingSpec("blend_radius_mm", "Blend Radius (mm)", "0.0", "Robot"),
            SegmentSettingSpec(
                "pre_smooth_max_deviation_mm",
                "Pre-Smooth Deviation (mm)",
                "1.0",
                "Robot",
            ),
        ],
    )
