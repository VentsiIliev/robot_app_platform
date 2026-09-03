"""Top-level paint-system development and diagnostic switches.

Keep temporary system-wide switches here so their active state is visible in
source control and does not depend on the shell used to launch the platform.
"""

# Diagnostic only. When True, captured contour points are transformed directly
# to robot coordinates without interpolation, smoothing, fairing, source
# cleanup, or robot-space 1 mm resampling. Coordinate transformation, tangent
# generation, paint projection, and final projected-path safety cleanup remain.
BYPASS_CONTOUR_PREPARATION = False
