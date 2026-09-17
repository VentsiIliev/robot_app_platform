# Paint Robot-System Split

## Decision

Compact paint and automatic-dryer paint are separate robot systems. They share
paint-process capabilities and the paint dashboard, but each owns its service
composition and complete storage tree.

The shared process must depend on machine-neutral contracts. It must not branch
on flags such as `has_dryer` or import automatic-dryer services.

## Target ownership

```text
Shared paint capability
  - paint state machine and execution
  - contour preparation and matching
  - common pickup/navigation strategy contracts
  - IWorkpieceDestination
  - common dashboard

CompactPaintRobotSystem
  - compact services and strategies
  - no dryer settings or services
  - no production-start guard
  - compact_paint/storage

Automatic-dryer paint composition
  - dryer service and configuration
  - AutomaticDryerDestination
  - AutomaticDryerStartGuard
  - existing paint/storage until storage migration is commissioned
```

## Implemented foundation

- Added `IWorkpieceDestination` to the shared execution boundary.
- Added `PassThroughWorkpieceDestination` for cells with no external handoff.
- Adapted the existing dryer coordinator through `AutomaticDryerDestination`.
- Removed dryer-named callbacks and fields from the shared path executor.
- Replaced dryer methods in the common dashboard contract with an optional,
  generic production-start guard.
- Added `AutomaticDryerStartGuard` outside the dashboard package.
- Added `CompactPaintRobotSystem`, excluding dryer configuration, dryer service,
  and tray-fan service declarations.
- Added an independent compact storage directory scaffold and bootstrap
  provider.

## Storage migration rule

The existing paint storage is not copied automatically into compact paint.
Calibration, targets, work areas, movement groups, hardware addresses, and
process navigation are machine-specific and must not silently cross system
boundaries.

Before enabling `compact_paint` in `config/platform.json`, commission every
declared `SettingsSpec` under:

```text
src/robot_systems/compact_paint/storage/settings/
```

The compact system must remain unavailable in the supported-system list until
that tree has been populated and validated on the compact cell.

## Remaining extraction

1. Decide whether the current `paint` package and storage are the canonical
   automatic-dryer installation, then rename that composition explicitly.
2. Populate and validate compact paint storage from compact-cell measurements.
3. Move genuinely common process/application modules into a neutral
   `paint_common` package in small, import-safe steps.
4. Move dryer-only coordinator, settings, builders, and device UI into the
   automatic-dryer system package.
5. Extract pickup, delivery, and cycle-navigation variants behind shared
   strategy interfaces where the two machines actually differ.
6. Add the commissioned systems to `supported_robot_systems` and verify their
   ROS runtime-profile mappings.

## Invariants

- Compact paint must not declare `SettingsID.DRYER_CONFIG`, `ServiceID.DRYER`,
  or the dryer tray-fan service.
- The shared dashboard must start directly when no production-start guard is
  supplied.
- Automatic-dryer readiness and enable prompts come only from its guard.
- Each concrete system uses its own storage root with no cross-system fallback.
- Profile/system changes require restart; repositories are never swapped while
  a process is running.
