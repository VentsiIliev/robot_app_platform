# Shaft Alignment application

This is a shared, self-contained platform application. It is deliberately not
coupled to Paint through its MVC layers. It is currently registered as an enabled
test application in `PaintRobotSystem` through Paint's composition module.

The application owns the Qt presentation and MVC interaction flow. All camera,
robot-pose, calibration, detection, reference-capture, and misalignment work is
behind `IShaftAlignmentService`. Robot-system composition injects an implementation
of that interface through `ShaftAlignmentFactory`; the view, model, and controller
do not import the robot system.

Run the platform-style UI with the real Paint vision composition:

```bash
python src/applications/shaft_alignment/example_usage.py
```

This example creates the same Paint `VisionService`, detector, homography/TCP
transformer, tracker, stabilizer, and pose compensation used by the hardware
runner. Acquisition runs in the service's background thread. The shared
application package remains independent of `PaintRobotSystem`.
When launched inside Paint, it borrows the system-owned vision service and reads
the current robot TCP pose for every processed frame. The planar compensation
uses current X/Y and RZ relative to the calibration pose; the standalone runner
uses its configured fallback capture pose.
Camera acquisition starts when the application loads and stops during application
cleanup, so the alignment screen does not expose redundant Start/Stop controls.
When a reference comparison is available, the preview shows the required signed
tool-frame correction (`-dX`, `-dY`, and `-dRZ`) with directional arrow guides.

`StubShaftAlignmentService` remains available for tests and hardware-free UI
development.

The original hardware proving runner remains available separately:

```bash
./.venv/bin/python scripts/paint_shaft_alignment/__main__.py
```

To integrate later, provide a non-blocking service whose `get_snapshot()`
returns the latest immutable `AlignmentSnapshot`. Long-running acquisition
belongs in the service/backend, not the Qt thread. The backend reads the selected
work area's normalized detection region and converts its bounding rectangle
against the actual source-frame size.

Application-owned defaults and persisted standalone values live in
`settings/config.json`. The Settings tab exposes the editable configuration and saves changes
through the service boundary. The real backend atomically rebuilds its detector,
mapper, tracker, and stabilizer on the acquisition thread, so saved values update
in memory without restarting the application. A completed reference
capture saves the averaged TCP X/Y, orientation, and measured marker width/height;
it also saves the median normalized marker corners and restores their dotted
outline on the camera preview as a placement guide.
The configured POI offset is defined in the aligned marker's image axes
(`+X` right, `+Y` down). During reference capture it is converted through each
accepted marker's pixel basis; the median POI is persisted and drawn as a circle
at the aligned target location rather than following the live marker.
The Alignment tab also shows the saved reference TCP X/Y, orientation, and marker
dimensions between the live measurements and the threshold controls.
Alignment controls are placed to the left of the central camera preview. In the
Paint composition, the platform's shared robot jog drawer is available on the
right-hand side and is wired through the standard jog service/controller path.
The Paint system declares a dedicated `vertical_shaft_alignment` work area. It
is activated when navigating to the `Vertical Shaft Alignment` movement group
and has its own configurable detection, brightness, and height-mapping regions.
changing any misalignment threshold slider also saves and applies all five
thresholds immediately. The reference and thresholds are restored on the next
launch. Starting a new
reference capture clears the previous baseline immediately, then updates memory
and disk together when all requested samples have been accepted. The included
serializer can be registered later by a robot system without changing the
application layers.

`IShaftAlignmentService.check_alignment()` is the boolean integration method for
a robot system. It uses the median of the latest consecutive valid measurements,
with the batch size controlled by `alignment_check_samples`. It returns `True`
only when acquisition is running, a baseline and a complete batch exist, and none
of the five median values exceeds its threshold. Missing or incomplete data is
fail-safe and returns `False`.

The Alignment tab offers two presentation modes. **Continuous** updates the
verdict from every snapshot. **Check once** keeps the last verdict unchanged
until **Check alignment** is pressed, then calls the same boolean service method
that production orchestration can use.
