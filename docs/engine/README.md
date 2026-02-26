# `src/engine/` — Engine Overview

The `engine` package is the core of the robot app platform. It provides the foundational infrastructure that all robot applications and plugins build on: messaging, robot control, hardware I/O, and settings persistence. Nothing in `engine` depends on `pl_gui` (the Qt layer) or on any specific robot application.

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
│   └── weight/                 ← Weight cell service + HTTP transport
│       ├── interfaces/
│       └── http/
├── repositories/               ← JSON-backed settings persistence
│   ├── interfaces/
│   └── json/
├── robot/                      ← Robot control stack
│   ├── interfaces/             ← IRobot, IMotionService, IRobotService, …
│   ├── configuration/          ← RobotSettings, RobotCalibrationSettings
│   ├── enums/                  ← RobotAxis, Direction, ImageToRobotMapping
│   ├── safety/                 ← SafetyChecker (workspace bounds)
│   ├── features/               ← NavigationService, RobotToolService
│   ├── services/               ← MotionService, RobotStateManager, RobotService
│   └── drivers/
│       └── fairino/            ← FairinoRobot, TestRobotWrapper
└── vision/                     ← VisionService (stub)
```

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────┐
│                     robot_apps / plugins                 │
│           (GlueRobotApp, ModbusSettingsPlugin, …)        │
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
└────────────────────────────────┘
```

---

## Subsystem Summary

| Subsystem | Key Entry Point | Docs |
|-----------|----------------|------|
| Messaging | `MessagingService` | [core/](core/README.md) |
| Modbus | `ModbusActionService` | [hardware/communication/modbus/](hardware/communication/modbus/README.md) |
| Weight cells | `WeightCellService` | [hardware/weight/](hardware/weight/README.md) |
| Settings | `SettingsService` | [repositories/](repositories/README.md) |
| Robot control | `RobotService` | [robot/](robot/README.md) |
| Vision | `VisionService` | [vision/](vision/README.md) |

---

## Startup Integration

The engine is wired together during platform startup (`src/bootstrap/main.py`):

```
1. EngineContext.build()
       └─ creates MessagingService singleton

2. AppBuilder.build(GlueRobotApp)
       ├─ build_from_specs(settings_specs, …) → SettingsService
       ├─ FairinoRobot(ip)  →  create_robot_service(robot, messaging, settings)
       └─ app.start(services, settings_service)
```

All engine objects are created once and injected as interfaces — no engine module instantiates itself at import time.

---

## Design Principles

- **No Qt dependency** — every class in `engine/` is pure Python, testable without a `QApplication`.
- **Interface-first** — all cross-module calls go through abstract base classes (`IRobotService`, `ISettingsService`, `IMessagingService`). Concrete classes are an implementation detail.
- **Dependency injection** — factories wire dependencies explicitly; no global state except the `MessageBroker` singleton.
- **Daemon threads** — background polling loops (`RobotStateManager`, `WeightCellService`) use daemon threads so they don't block process exit.
