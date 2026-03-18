# `src/robot_systems/glue/processes/pick_and_place/` — Pick-And-Place Workflow

This package contains the planning and execution pieces used by [PickAndPlaceProcess](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/processes/pick_and_place_process.py). The process owns the outer `BaseProcess` lifecycle and worker thread; this package owns the workflow internals.

---

## Structure

| File | Responsibility |
|------|----------------|
| [config/pick_and_place_config.py](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/processes/pick_and_place/config/pick_and_place_config.py) | Runtime config for plane layout, motion profiles, orientation, and height source |
| [workflow/pick_and_place_workflow.py](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/processes/pick_and_place/workflow/pick_and_place_workflow.py) | Thin workflow orchestrator over small stage handlers |
| [workflow/handlers](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/processes/pick_and_place/workflow/handlers) | Stage-level handlers for startup, matching, transform, tooling, height, planning, pick, place, completion, and shutdown |
| [context/pick_and_place_context.py](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/processes/pick_and_place/context/pick_and_place_context.py) | Runtime execution context and diagnostics snapshot state |
| [execution/motion_executor.py](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/processes/pick_and_place/execution/motion_executor.py) | Centralizes robot/tool motions and converts failures into typed results |
| [errors/pick_and_place_error.py](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/processes/pick_and_place/errors/pick_and_place_error.py) | Typed workflow stages, error codes, and workflow results |
| [execution/height_resolution_service.py](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/processes/pick_and_place/execution/height_resolution_service.py) | Resolves effective pickup height from config policy |
| [planning/selection_policy.py](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/processes/pick_and_place/planning/selection_policy.py) | Selects and orders matched workpieces for processing |
| [planning/placement_strategy.py](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/processes/pick_and_place/planning/placement_strategy.py) | Strategy seam over placement calculation |
| [planning/pickup_calculator.py](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/processes/pick_and_place/planning/pickup_calculator.py) | Computes pickup poses from transformed pickup point and orientation |
| [planning/placement_calculator.py](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/processes/pick_and_place/planning/placement_calculator.py) | Computes plane placement target and drop-off poses without mutating the caller’s contour |
| [plane/plane.py](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/processes/pick_and_place/plane/plane.py) | Mutable plane state for the current run |
| [plane/plane_management_service.py](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/processes/pick_and_place/plane/plane_management_service.py) | Plane packing rules and row-advance logic |
| [planning/models.py](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/processes/pick_and_place/planning/models.py) | Pose and placement dataclasses |

---

## Workflow Contract

`PickAndPlaceWorkflow.run(stop_event, run_allowed)` now returns a typed [PickAndPlaceWorkflowResult](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/processes/pick_and_place/errors/pick_and_place_error.py) instead of only an ad hoc `(state, message)` pair internally.

The workflow entrypoint is intentionally thin. Its main job is to:
- run startup
- wait on `run_allowed`
- run a matching cycle
- prepare one workpiece
- plan and execute placement
- shut down cleanly on terminal conditions

The detailed work for those steps lives under [workflow/handlers](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/processes/pick_and_place/workflow/handlers), so no single handler owns transform, tooling, height, planning, pick, place, and completion at once.

The outer process still behaves the same:
- `STOPPED` on normal completion
- `ERROR` on failure

But failures now retain:
- `stage`
- `code`
- `message`
- optional `detail`
- `recoverable`

This makes it easier to add operator feedback, retries, or stage-specific recovery later.

The workflow also maintains a dedicated runtime context and emits diagnostics snapshots through `PickAndPlaceProcess` on `PickAndPlaceTopics.DIAGNOSTICS`.

---

## Error Handling

The main failure stages are:
- `startup`
- `matching`
- `transform`
- `height`
- `tooling`
- `pick`
- `place`
- `plane`
- `shutdown`

Examples of typed codes:
- `MOVE_HOME_FAILED`
- `MATCHING_FAILED`
- `TRANSFORM_FAILED`
- `HEIGHT_MEASUREMENT_FAILED`
- `TOOL_CHANGE_FAILED`
- `PICK_MOTION_FAILED`
- `PLACE_MOTION_FAILED`
- `DROP_GRIPPER_FAILED`
- `PLANE_FULL`

The workflow now explicitly checks place motion success. A failed place move no longer silently advances the plane state.

---

## Height Source

[PickAndPlaceConfig](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/processes/pick_and_place/config/pick_and_place_config.py) now makes the height source explicit:
- `zero`
- `measured`
- `workpiece`

Default is currently `zero` to preserve the existing runtime behavior that was previously implemented as an inline override in the workflow.

---

## Motion Config

Motion assumptions are no longer spread across the workflow. `PickAndPlaceConfig` now owns:
- `pick_motion`
- `place_motion`
- `orientation_rx`
- `orientation_ry`
- `rz_orientation`
- plane `row_gap`

This keeps the geometry logic unchanged while making tool/user/speed changes local to config instead of buried in workflow code.

---

## Coordinate Transform Flow

Pickup-point conversion is now split into three explicit layers:
- `HomographyTransformer.transform(...)` converts camera pixels into calibration-plane robot XY
- `CalibrationToPickupPlaneMapper` converts calibration-plane XY into pickup-plane / home-frame XY using the declared `CALIBRATION` and `HOME` movement-group poses
- `PickupCalculator` applies gripper XY offsets, gripper Z offsets, safe heights, and final `rz`

This replaces the older implicit `(-y, x)` rotation inside `PickupCalculator`. The 90 degree relationship between the calibration and pickup planes is now handled as a proper rigid frame conversion with both:
- rotation from `CALIBRATION.rz` to `HOME.rz`
- translation from the `CALIBRATION` origin to the `HOME` origin

As a result:
- the homography remains valid only for the calibration plane
- the pickup-plane conversion is explicit, logged, and testable independently
- gripper compensation stays isolated from plane-frame conversion

The transform handler now logs the full chain:
- image pickup point
- calibration-plane robot point from homography
- pickup-plane robot point after calibration-to-pickup mapping

## Diagnostics

`PickAndPlaceProcess` now publishes structured diagnostics snapshots during startup, matching, transform, tooling, height resolution, pick, place, plane planning, and shutdown.

The snapshot currently includes:
- process state
- workflow stage
- match attempt count
- processed workpiece count
- active workpiece id/name
- active gripper id
- pickup point in image and robot space
- resolved height source and value
- plane offsets/state
- last typed error
- step-mode enabled flag
- queued step budget
- whether the workflow is currently waiting for a step
- the current checkpoint id

This gives visualizers and future dashboards a broker-native way to inspect progress without scraping logs.

The visualizer now uses these diagnostics to drive a stage-by-stage operator flow. The main checkpoints are:
- `startup.move_home`
- `matching.run`
- `preparation.begin`
- `transform.pickup_point`
- `tooling.ensure_gripper`
- `tooling.return_home`
- `height.resolve`
- `plane.plan`
- `pick.descent`
- `pick.pickup`
- `pick.lift`
- `place.approach`
- `place.drop`
- `placement.finalize`
- `placement.move_to_calibration`
- `placement.return_home`
- `shutdown.drop_gripper`

---

## Routing Note

`GlueNavigationService.move_home()` now goes directly to `HOME`. It may still apply the configured vision capture Z offset, but it no longer inserts a `CALIBRATION` waypoint automatically.

Pick-and-place now requests calibration moves explicitly where the workflow needs them:
- after a real gripper pickup/change, the tooling stage returns home before continuing
- after a workpiece is dropped on the plane, the workflow moves to `CALIBRATION`, then `HOME`, and only then starts the next matching cycle

---

## Preservation Notes

The pickup and placement math was intentionally separated by responsibility:
- homography remains the camera-to-calibration-plane transform
- pickup-plane conversion is now handled by a dedicated calibration-to-pickup mapper
- pickup calculation now assumes its input XY is already in the pickup-plane frame and only applies gripper offsets / heights / final orientation
- placement still uses the same contour orientation handling and plane packing logic
- only the execution seams and failure reporting were tightened

This package is now organized into subpackages by concern:
- `config/`
- `context/`
- `errors/`
- `execution/`
- `planning/`
- `plane/`
- `workflow/`
