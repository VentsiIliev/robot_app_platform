# Plate-Layout Drop-Off Strategy Plan

## Goal

Add an optional `plate_layout` paint drop-off strategy that places consecutive
workpieces onto available positions on a rectangular plate. The plate is defined
by four measured robot-space corners, and each calculated placement center is
returned directly in robot coordinates.

Preserve the existing `pickup_origin` and `movement_group` strategies unchanged.

## Proposed configuration

Extend the paint drop-off configuration with:

- `strategy`: allow `plate_layout` in addition to the existing values.
- Four ordered plate corners in robot space.
- Corner order: bottom-left, bottom-right, top-right, top-left.
- Plate release Z and release orientation RX/RY/RZ.
- Safe approach clearance above the release point.
- Left, right, bottom, and top margins.
- Horizontal and vertical workpiece spacing.
- Optional placement direction and starting corner if later required.
- Full-plate behavior and an explicit layout reset mechanism.

For the first implementation, require a horizontal plate and store XY corners.
If tilted plates are required, use four XYZ corners and calculate the plate plane,
release Z, and tool orientation from that plane instead of adding offsets later.

## Geometry model

1. Validate that exactly four finite corners are configured in the required order.
2. Calculate plate width as the average length of its bottom and top edges.
3. Calculate plate height as the average length of its left and right edges.
4. Perform packing in plate-local millimetres.
5. Map local placement coordinates into robot XY with bilinear interpolation.
6. Reject degenerate, self-intersecting, or implausibly distorted corner sets.
7. Apply margins and spacing in physical millimetres before coordinate mapping.

Bilinear mapping allows small measurement skew between the four taught corners.
It must not be used to hide a substantially non-rectangular or incorrectly ordered
plate definition.

## Placement model

Use deterministic shelf placement initially:

1. Place workpieces left-to-right in the active row.
2. Track the tallest workpiece in the row.
3. Start a new row when the next workpiece does not fit horizontally.
4. Return a `plate full` result when it cannot fit vertically.
5. Do not modify placement state when a workpiece cannot fit.

Rectangle footprints are conservative and suitable for the first version.
Irregular contour packing can be considered separately if plate utilization later
becomes more important than simplicity and predictability.

## Transactional placement lifecycle

Do not consume a position when planning starts. Use a reservation lifecycle:

```text
reserve(width, height, orientation) -> reservation
    |
    +-- release verified -> commit(reservation)
    |
    +-- motion/release failed -> cancel(reservation)
```

Only commit after:

1. The robot reaches the calculated release pose.
2. The vacuum pump is switched off.
3. The vacuum sensor verifies that the workpiece was released.

This prevents failed moves, pauses, retries, and sensor failures from creating
phantom occupied positions.

Only one reservation may be active at a time unless the service is later designed
and tested for concurrent production requests.

## Workpiece footprint

Determine one authoritative source of physical workpiece width and height.

Preferred approach:

1. Calculate an oriented minimum bounding rectangle from the prepared physical
   workpiece contour before execution.
2. Store the resulting footprint explicitly on `WorkpieceExecutionPlan` or in a
   narrow paint-owned placement input object.
3. Include the final drop-off orientation in the calculation.
4. Swap width and height for an intentional 90-degree rotation, or recompute the
   axis-aligned footprint for arbitrary rotations.

Do not infer dimensions from image pixels at drop-off time and do not depend on
debug-only rectangle metrics.

The footprint should include configurable safety allowance for:

- Robot positioning tolerance.
- Workpiece measurement uncertainty.
- Tool/suction-cup clearance.
- Desired physical spacing.

## Runtime integration

Implement the production layout logic as a paint-domain service, not by importing
the demonstration script from `scripts/plate_workpiece_placer.py`.

Suggested responsibilities:

- `PlateLayoutGeometry`: validated corners and local-to-robot mapping.
- `PlatePlacementService`: reservation, commit, cancel, reset, and occupancy.
- `PlateLayoutDropoffStrategy`: converts the next reservation into approach,
  release, and retract waypoints.

Inject the placement service into the paint path executor or active drop-off
planning seam through robot-system composition.

Before implementation, confirm which drop-off implementation is authoritative at
runtime. The repository currently contains strategy logic in both:

- `processes/paint/execute/dropoff_executor.py`
- `execution_machine/handlers/dropoff/dropoff_handlers.py`

Avoid implementing independent copies of plate-layout behavior in both locations.
Prefer one strategy abstraction used by the active execution machine.

## Motion and safety behavior

For every reserved placement:

1. Resolve robot XY from the plate layout.
2. Construct the release pose using configured Z and orientation.
3. Construct an approach pose at a configured positive Z clearance.
4. Use the existing drop-off safe-travel route to reach the plate area.
5. Move to the approach pose.
6. Descend linearly to the release pose with zero blend at contact/release.
7. Turn the vacuum pump off.
8. Verify release with the vacuum sensor.
9. Retract linearly to the approach pose when required by the route.
10. Commit the reservation only after release verification succeeds.

Retain existing motion validation, sub-zero restrictions, corridor handling,
pause/stop behavior, and post-return behavior. Calculated poses must pass the same
robot safety and reachability checks as movement-group poses.

Treat the following as errors:

- Invalid plate geometry.
- Missing or invalid workpiece footprint.
- Unreachable approach or release pose.
- Vacuum pump-off failure.
- Release verification failure.
- Reservation/state persistence failure.

Treat a full plate as an expected operational terminal condition, with a specific
message such as `Drop-off plate is full`, rather than a generic robot fault.

## Persistence and reset policy

Persist committed placements so an application restart does not reuse occupied
locations while physical workpieces remain on the plate.

Persist at least:

- Plate/configuration identity or geometry fingerprint.
- Sequence/index of committed placements.
- Workpiece footprint and robot center for each placement.
- Active reservation, if crash recovery needs to flag an uncertain position.

On startup:

1. Load persisted occupancy.
2. Verify that it belongs to the current plate geometry/configuration.
3. If geometry changed, require an explicit operator decision before clearing it.
4. Treat an interrupted active reservation as uncertain rather than automatically
   free or occupied.

Provide an explicit `Reset/Clear plate` operator action with confirmation. Do not
reset automatically at the end of a paint cycle or application restart.

## Settings organization

Show plate-layout fields only when `Drop-off Strategy = Plate Layout`.

Suggested groups:

- Plate corners.
- Release pose Z/orientation and approach clearance.
- Edge margins.
- Workpiece spacing and safety allowance.
- Occupancy status and reset action.

Validate configuration before saving and provide a preview showing:

- Plate boundary.
- Usable area after margins.
- Existing committed placements.
- Active reservation.
- Next calculated placement.

Add English and Bulgarian translations for all new UI text.

## Implementation phases

### Phase 1 — Pure geometry and placement domain

- Extract the script algorithm into paint-owned, Qt-free classes.
- Add corner validation and bilinear coordinate mapping.
- Add deterministic shelf packing.
- Add reservation, commit, cancel, full-plate, and reset behavior.
- Unit-test without robot or settings services.

### Phase 2 — Workpiece footprint

- Establish the authoritative physical contour source.
- Calculate and store the final drop-off footprint.
- Account for orientation and safety allowance.
- Add tests for different dimensions and rotations.

### Phase 3 — Drop-off strategy integration

- Register `plate_layout` alongside existing strategies.
- Build safe approach, linear release, and retract waypoints.
- Reuse vacuum-off and release-verification behavior.
- Commit only after verified release; cancel on every earlier failure.
- Return a non-fault `plate full` result.

### Phase 4 — Persistence and operator controls

- Add a settings serializer for plate geometry.
- Add a separate occupancy repository/state serializer.
- Add conditional settings fields and layout preview.
- Add confirmed plate reset/clear behavior.

### Phase 5 — Robot verification

- Validate four-corner ordering on a known plate.
- Dry-run calculated approach poses with no workpiece.
- Verify first, edge-most, row-transition, and final placements at low speed.
- Verify margins using the real tool envelope.
- Verify pause, stop, failed motion, failed release, and restart recovery.
- Verify that existing drop-off strategies behave identically when selected.

## Minimum test coverage

- Width and height derived from rotated corners.
- Slightly skewed corners map centers correctly.
- Invalid corner order/geometry is rejected.
- Different workpiece heights advance rows using the tallest row member.
- Margins and spacing are respected.
- Exact boundary fit succeeds.
- Oversized and full-plate requests return no reservation.
- Failed reservation does not consume space.
- Cancelled reservation can be reused.
- Committed reservation cannot be reused.
- Release failure cancels rather than commits.
- Restart restores committed occupancy.
- Geometry changes do not silently reuse stale occupancy.
- Existing `pickup_origin` and `movement_group` strategies remain unchanged.

## Acceptance criteria

- Selecting `plate_layout` produces deterministic, non-overlapping drop-off poses
  in robot coordinates.
- Every committed workpiece remains within configured plate margins and spacing.
- No position is consumed until physical release is verified.
- Full plate is reported clearly without attempting robot motion.
- Occupancy survives application restart or is explicitly marked uncertain.
- Existing drop-off behavior is preserved when another strategy is selected.
- All calculated robot moves retain the existing safe-travel, approach, release,
  retract, pause/stop, and vacuum-verification protections.
