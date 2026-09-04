"""Top-level paint-system development and diagnostic switches.

Keep temporary system-wide switches here so their active state is visible in
source control and does not depend on the shell used to launch the platform.
"""

# Diagnostic only. When True, captured contour points are transformed directly
# to robot coordinates without interpolation, smoothing, fairing, source
# cleanup, or robot-space 1 mm resampling. Coordinate transformation, tangent
# generation, paint projection, and final projected-path safety cleanup remain.
BYPASS_CONTOUR_PREPARATION = False


# Applications exposed by PaintRobotSystem. Set a flag to False to keep the
# application out of the shell without changing the system declaration.

# Main production dashboard for monitoring and controlling the paint process.
PAINT_DASHBOARD_APP = True

# Keep the current camera-first dashboard layout. When False, the camera is
# omitted, paint/pass controls move into the main content area, and the bottom
# process buttons expand to the available width.
SHOW_DASHBOARD_CAMERA_PREVIEW = False

# Replace separate paint velocity/acceleration inputs with Speed (1..100).
# Velocity remains Speed, while acceleration is calculated as Speed² / 100.
USE_COMBINED_PAINT_SPEED_CONTROL = True

# Testing aid: show the Velocity and Acceleration percentages derived from Speed.
# This has no effect when USE_COMBINED_PAINT_SPEED_CONTROL is False.
SHOW_RESOLVED_PAINT_SPEED_VALUES = True

# Allow pass settings and process acceleration scaling to be saved while the
# process runs. Each update is captured at the start of the next workpiece cycle.
ALLOW_RUNNING_PAINT_SETTINGS_UPDATES = True

# Lists saved workpieces and provides actions for managing the library.
WORKPIECE_LIBRARY_APP = False

# Captures, creates, and edits workpiece contours and their paint paths.
WORKPIECE_EDITOR_APP = False

# Configures the robot, movement groups, calibration, tools, and target frames.
ROBOT_SETTINGS_APP = True

# Displays EtherCAT master, slave, and communication diagnostic information.
ETHERCAT_DIAGNOSTICS_APP = False

# Configures Modbus communication and tests connections to Modbus devices.
MODBUS_SETTINGS_APP = True

# Provides manual control and status for configured peripherals, including
# dryer configuration and test operations in the Dryer tab.
DEVICE_CONTROL_APP = True

# Configures vision work areas, including their regions of interest.
WORK_AREA_SETTINGS_APP = True

# Configures camera parameters and provides camera-related test operations.
CAMERA_SETTINGS_APP = True

# Configures and runs vision and robot calibration-related setup operations.
CALIBRATION_SETTINGS_APP = False

# Configures paint-process motion, pickup, cleanup, and drop-off behavior.
PAINT_PROCESS_SETTINGS_APP = True

# Runs the guided calibration workflows for the robot, camera, and work areas.
CALIBRATION_APP = True

# Developer tool for observing and publishing MessageBroker traffic.
BROKER_DEBUG_APP = False

# Manages user accounts, roles, and per-application permissions.
USER_MANAGEMENT_APP = True

# Captures image sets used to calculate intrinsic camera calibration.
INTRINSIC_CAPTURE_APP = False

# Captures samples and calculates the camera-to-robot hand-eye calibration.
HAND_EYE_CALIBRATION_APP = False

# Detects a target and validates its resolved robot pickup position.
PICK_TARGET_APP = False

# Teaches and verifies the robot movement planes used by paint execution.
PAINT_MOTION_PLANE_SETUP_APP = False

# Developer editor for configuring and testing paint motion recipes.
PAINT_MOTION_RECIPE_APP = False

# Test application for marker-based shaft alignment and robot-pose compensation.
SHAFT_ALIGNMENT_APP = True
