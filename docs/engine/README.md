# `src/engine/` — Engine Overview

The `engine` package is the core of the robot system platform. It provides the foundational infrastructure that all robot applications and applications build on: messaging, robot control, hardware I/O, and settings persistence. Nothing in `engine` depends on `pl_gui` (the Qt layer) or on any specific robot application.

---

## Package Structure

```
src/engine/
├── core/                       ← Pub/sub messaging system
│   ├── i_messaging_service.py
│   ├── message_broker.py
│   └── messaging_service.py
├── hardware/                   ← Hardware I/O drivers
│   ├── communication/
│   │   └── modbus/             ← Serial/Modbus port management
│   ├── generator/              ← Relay-switched generator controller + run timer
│   ├── motor/                  ← Motor controller service (IMotorService)
│   ├── laser/                  ← ILaserControl interface
│   ├── vacuum_pump/            ← IVacuumPumpController, IVacuumPumpTransport
│   └── weight/                 ← Weight cell service + HTTP transport
│       ├── interfaces/
│       └── http/
├── process/                    ← Process lifecycle state machine
│   ├── i_process.py            ← IProcess ABC
│   ├── base_process.py         ← Thread-safe BaseProcess with template hooks
│   ├── process_requirements.py ← Service pre-condition declarations
│   └── process_sequence.py     ← Auto-advancing ordered process chain
│   (ProcessState, ProcessStateEvent, ProcessTopics → src/shared_contracts/events/process_events.py)
├── localization/               ← Runtime language service over Qt translators
│   ├── i_localization_service.py
│   ├── dict_translator.py
│   └── localization_service.py
├── auth/                       ← Authentication, authorization, and session
│   ├── i_authenticated_user.py
│   ├── i_auth_user_repository.py
│   ├── i_authentication_service.py
│   ├── i_authorization_service.py
│   ├── i_permissions_admin_service.py
│   ├── i_session_service.py
│   ├── authentication_service.py
│   ├── authorization_service.py
│   ├── user_session.py
│   ├── json_permissions_repository.py
│   └── permissions_migrator.py
├── system/                     ← Single-process exclusivity lock
│   ├── i_system_manager.py     ← ISystemManager ABC
│   ├── system_manager.py       ← Thread-safe SystemManager
│   └── system_state.py         ← SystemBusyState, SystemStateEvent, SystemTopics
├── repositories/               ← JSON-backed settings persistence
│   ├── interfaces/
│   └── json/
├── robot/                      ← Robot control stack
│   ├── interfaces/             ← IRobot, IMotionService, IRobotService, …
│   ├── configuration/          ← RobotSettings, RobotCalibrationSettings
│   ├── enums/                  ← RobotAxis, Direction, ImageToRobotMapping
│   ├── safety/                 ← SafetyChecker (workspace bounds)
│   ├── features/               ← NavigationService, RobotToolService
│   ├── targeting/              ← VisionTargetResolver, JogFramePoseResolver, PointRegistry
│   ├── height_measuring/       ← Laser height sensor services + correction interpolation
│   ├── path_interpolation/     ← Linear + spline path densification utilities
│   ├── services/               ← MotionService, RobotStateManager, RobotService
│   └── drivers/
│       └── fairino/            ← FairinoRobot, TestRobotWrapper
├── work_areas/                 ← IWorkAreaService, WorkAreaService, normalised polygon storage
└── vision/                     ← IVisionService interface + VisionSystem implementation
    ├── i_vision_service.py     ← IVisionService ABC
    ├── camera_settings_serializer.py
    └── implementation/
        └── VisionSystem/       ← Full camera + contour + calibration system
```

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────┐
│                     robot_apps / applications            │
│           (GlueRobotSystem, ModbusSettingsApplication, …)│
└────────────┬───────────────────────────┬─────────────────┘
             │ ISettingsService           │ IRobotService / IMessagingService
             ▼                           ▼
┌────────────────────┐     ┌──────────────────────────────┐
│   repositories/    │     │          robot/              │
│                    │     │                              │
│ SettingsService    │     │  RobotService                │
│   └ BaseJson       │     │    ├ MotionService            │
│     Repository     │     │    │   ├ IRobot               │
└────────────────────┘     │    │   └ SafetyChecker        │
                           │    └ RobotStateManager        │
┌────────────────────┐     │        └ RobotStatePublisher  │
│      core/         │◄────┤                              │
│                    │     │  NavigationService            │
│ MessagingService   │     │  RobotToolService             │
│   └ MessageBroker  │     └──────────────────────────────┘
│     (singleton)    │
└────────────────────┘
             ▲
             │  IMessagingService
┌────────────┴───────────────────┐
│         hardware/              │
│                                │
│  WeightCellService             │
│    ├ HttpCellTransport         │
│    └ ICellCalibrator           │
│                                │
│  ModbusActionService           │
│  MotorService                  │
│  GeneratorController           │
└────────────────────────────────┘

┌────────────────────┐     ┌────────────────────┐
│      system/       │     │       auth/         │
│                    │     │                     │
│ SystemManager      │     │ AuthenticationService│
│ ISystemManager     │     │ AuthorizationService │
│ SystemBusyState    │     │ UserSession          │
└────────────────────┘     └────────────────────┘
```

---

## Subsystem Summary

| Subsystem | Key Entry Point | Docs |
|-----------|----------------|------|
| Messaging | `MessagingService` | [core/](core/README.md) |
| Modbus | `ModbusActionService` | [hardware/communication/modbus/](hardware/communication/modbus/README.md) |
| Weight cells | `WeightCellService` | [hardware/weight/](hardware/weight/README.md) |
| Process lifecycle | `BaseProcess` / `IProcess` | [process/](process/README.md) |
| Localization | `LocalizationService` | [localization/](localization/README.md) |
| Auth | `AuthenticationService` / `AuthorizationService` / `UserSession` | [auth/](auth/README.md) |
| System manager | `SystemManager` / `ISystemManager` | [system/](system/README.md) |
| Settings | `SettingsService` | [repositories/](repositories/README.md) |
| Robot control | `RobotService` | [robot/](robot/README.md) |
| Targeting | `VisionTargetResolver`, `JogFramePoseResolver` | [robot/targeting/](robot/targeting/README.md) |
| Height measuring | `IHeightMeasuringService`, `HeightCorrectionService` | [robot/height_measuring/](robot/height_measuring/README.md) |
| Path interpolation | `interpolate_path_two_stage` | [robot/path_interpolation/](robot/path_interpolation/README.md) |
| Work areas | `IWorkAreaService`, `WorkAreaService` | [work_areas/](work_areas/README.md) |
| Laser | `ILaserControl` | [hardware/laser/](hardware/laser/README.md) |
| Vacuum pump | `IVacuumPumpController`, `IVacuumPumpTransport` | [hardware/vacuum_pump/](hardware/vacuum_pump/README.md) |
| Vision | `VisionSystem` / `IVisionService` | [vision/](vision/README.md) |

---

## Startup Integration

The engine is wired together during platform startup (`src/bootstrap/main.py`):

```
1. EngineContext.build()
       └─ creates MessagingService singleton

2. SystemBuilder.build(GlueRobotSystem)
       ├─ build_from_specs(settings_specs, …) → SettingsService
       ├─ FairinoRobot(ip)  →  create_robot_service(robot, messaging, settings)
       └─ app.start(services, settings_service)
```

All engine objects are created once and injected as interfaces — no engine module instantiates itself at import time.

Robot-system-specific startup composition does not belong in `engine/` and should not be hardcoded in `src/bootstrap/main.py`. Concrete robot driver selection, login/auth wiring, and authorization/permissions filtering should live in the active robot system's bootstrap provider.

---

## Design Principles

- **No Qt dependency** — every class in `engine/` is pure Python, testable without a `QApplication`.
- **Interface-first** — all cross-module calls go through abstract base classes (`IRobotService`, `ISettingsService`, `IMessagingService`). Concrete classes are an implementation detail.
- **Dependency injection** — factories wire dependencies explicitly; no global state except the `MessageBroker` singleton.
- **Daemon threads** — background polling loops (`RobotStateManager`, `WeightCellService`) use daemon threads so they don't block process exit.

Note: `engine/localization/` is the one engine subsystem that intentionally touches Qt core translation APIs (`QCoreApplication`, `QTranslator`). It still remains GUI-agnostic: it does not import views, widgets, or application-specific code. It also persists the selected language in a small JSON state file so the shell selector and installed translator stay in sync across restarts.
