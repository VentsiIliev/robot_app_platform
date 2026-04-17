#!/usr/bin/env python3
import sys
import os
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from PyQt6.QtWidgets import QApplication, QMainWindow

from src.applications.workpiece_editor.workpiece_editor_factory import WorkpieceEditorFactory
from src.applications.workpiece_editor.service.stub_workpiece_editor_service import StubWorkpieceEditorService
from src.applications.workpiece_editor.editor_core.config.workpiece_form_schema import (
    WorkpieceFormSchema, WorkpieceFormFieldSpec, FieldIcon,
)
from src.applications.workpiece_editor.editor_core.config.segment_settings_schema import (
    SegmentSettingsSchema, SegmentSettingSpec,
)
from src.applications.workpiece_editor.editor_core.config.segment_editor_config import SegmentEditorConfig
from src.engine.core.messaging_service import MessagingService

# ── Example form schema ───────────────────────────────────────────────────────
# Defines the fields shown in the workpiece creation form.
# Each robot vision_service provides its own — this one is illustrative only.

_PART_TYPES = ["Standard", "Heavy", "Delicate"]

ID_ICON          = "fa5s.barcode"        # Better for part/item ID
NAME_ICON        = "fa5s.tag"            # Good for item name
DESCRIPTION_ICON = "fa5s.align-left"     # Perfect for description text
HEIGHT_ICON      = "fa5s.ruler-vertical" # Correct
PART_TYPE_ICON   = "fa5s.layer-group"    # Correct
ICON_COLOR       = "#444444"

_FORM_SCHEMA = WorkpieceFormSchema(
    id_key    = "partId",
    combo_key = "partType",
    fields=[
        WorkpieceFormFieldSpec(
            key="partId",
            label="Part ID",
            field_type="text",
            mandatory=True,
            icon=FieldIcon.from_qta("fa5s.barcode", color=ICON_COLOR)
        ),
        WorkpieceFormFieldSpec(
            key="name",
            label="Name",
            field_type="text",
            mandatory=False,
            icon=FieldIcon.from_qta("fa5s.tag", color=ICON_COLOR)
        ),
        WorkpieceFormFieldSpec(
            key="height",
            label="Height (mm)",
            field_type="text",
            mandatory=True,
            placeholder="mm",
            icon=FieldIcon.from_qta("fa5s.ruler-vertical", color=ICON_COLOR)
        ),
        WorkpieceFormFieldSpec(
            key="partType",
            label="Part Type",
            field_type="dropdown",
            mandatory=True,
            options=_PART_TYPES,
            icon=FieldIcon.from_qta("fa5s.layer-group", color=ICON_COLOR)
        ),
        WorkpieceFormFieldSpec(
            key="description",
            label="Description",
            field_type="text",
            mandatory=False,
            icon=FieldIcon.from_qta("fa5s.align-left", color=ICON_COLOR)
        ),
    ],
)


# ── Example segment settings schema ──────────────────────────────────────────
# Defines the fields shown in the per-segment settings panel inside the editor.

_SEGMENT_SCHEMA = SegmentSettingsSchema(
    combo_key     = "partType",
    combo_options = _PART_TYPES,
    fields=[
        # Motion
        SegmentSettingSpec("velocity",        "Velocity (mm/s)",   "60",   "Motion"),
        SegmentSettingSpec("acceleration",    "Acceleration",      "30",   "Motion"),
        # Process
        SegmentSettingSpec("process_speed",   "Process Speed",     "500",  "Process"),
        SegmentSettingSpec("pass_height",     "Pass Height (mm)",  "5",    "Process"),
        SegmentSettingSpec("offset",          "Offset (mm)",       "0",    "Process"),
        SegmentSettingSpec("partType",        "Part Type",         "",     "Process", validator="combo"),
        # Interpolation
        SegmentSettingSpec("preprocess_min_spacing_mm", "Preprocess Spacing (mm)", "2.5",  "Interpolation"),
        SegmentSettingSpec("interpolation_spacing_mm",  "Sampled Spacing (mm)",    "10.0", "Interpolation"),
        SegmentSettingSpec("dense_sampling_factor",     "Dense Factor",            "0.25", "Interpolation"),
        SegmentSettingSpec("execution_spacing_mm",      "Execution Spacing (mm)",  "7.5",  "Interpolation"),
        SegmentSettingSpec("path_tangent_lookahead_mm", "Tangent Lookahead (mm)",  "15.0", "Interpolation"),
        SegmentSettingSpec("path_tangent_deadband_deg", "Tangent Deadband (deg)",  "5.0",  "Interpolation"),
        # Thresholds
        SegmentSettingSpec("start_threshold", "Start Threshold",   "1.0",  "Thresholds"),
        SegmentSettingSpec("end_threshold",   "End Threshold",     "30.0", "Thresholds"),
    ],
)


def run_standalone():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    )

    app       = QApplication(sys.argv)
    messaging = MessagingService()

    service = StubWorkpieceEditorService(
        form_schema    = _FORM_SCHEMA,
        segment_config = SegmentEditorConfig(schema=_SEGMENT_SCHEMA),
    )

    widget = WorkpieceEditorFactory(messaging).build(service)

    window = QMainWindow()
    window.setCentralWidget(widget)
    window.resize(1440, 900)
    window.setWindowTitle("Workpiece Editor — Standalone")
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()
