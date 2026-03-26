# `src/applications/calibration_settings/` — Calibration Settings

Shared settings application for calibration-related configuration.

This screen owns:

- camera calibration board settings
- robot calibration settings
- laser calibration and detection settings
- height-mapping settings

`CameraSettings` no longer owns the chessboard calibration fields.

`CalibrationSettings` remains the dedicated full settings screen, while the `Calibration` workflow now embeds the same phase settings inline on the matching tabs for convenience.

## Settings Owned

`CalibrationSettings` edits and saves these three persisted settings together:

- `CommonSettingsID.CALIBRATION_VISION_SETTINGS`
- `CommonSettingsID.ROBOT_CALIBRATION`
- `CommonSettingsID.HEIGHT_MEASURING_SETTINGS`

It also mirrors the camera-calibration section back into `CommonSettingsID.VISION_CAMERA_SETTINGS` so the current vision/calibration runtime keeps working while those runtime readers are still merged.

The `Calibration` workflow uses this same persistence path through a small `CalibrationSettingsBridge`, so inline workflow edits and the dedicated settings screen stay consistent.

## UI Layout

The application uses the shared `CollapsibleSettingsView` pattern and is reusable across robot systems.

Tabs:

- `Camera`
- `Robot`
- `Laser`
- `Height Mapping`

Each group starts collapsed by default, matching the rest of the settings applications.
