# `src/applications/work_area_settings/` — Work Area Settings

Shared application for editing robot-system-declared work areas and their ROI overlays.

It is intentionally separate from `CameraSettings`:
- `WorkAreaSettings` owns ROI editing
- `CameraSettings` owns camera and detection tuning

The app is reusable by any robot system that declares:
- `CommonServiceID.WORK_AREAS`
- `CommonSettingsID.WORK_AREA_SETTINGS`
- `work_areas`

If a vision service is also present, the app shows a live preview and keeps the active work area synced into the running vision stack.

## MVC Structure

```
work_area_settings/
├── service/
├── model/
├── view/
├── controller/
├── work_area_settings_factory.py
└── example_usage.py
```

## Behavior

- lists declared work areas from the robot system
- edits detection ROI and brightness ROI
- loads and saves normalized polygons through `IWorkAreaService`
- keeps the selected work area active through `IWorkAreaService`
- forwards that active area into `IVisionService` when available
- shows live camera frames through `VisionTopics`

The preview uses the shared `CameraView` widget and the shared application style helpers from
[app_styles.py](/home/ilv/Desktop/robot_app_platform/src/applications/base/app_styles.py).
