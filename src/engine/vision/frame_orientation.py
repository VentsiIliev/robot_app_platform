"""Shared capture-frame orientation transform.

Every camera capture path applies the same flip/rotate transform before a frame
is handed to any consumer: the primary ``FrameGrabber`` and each auxiliary
``CameraStreamPublisher``.  The transform lives here so the two paths cannot
drift apart.

Ordering is fixed and load-bearing: rotation is applied first, then the mirror.
That keeps ``flip_vertical`` meaning "mirror the image as displayed" regardless
of the configured rotation.
"""
from __future__ import annotations

import cv2


VALID_ROTATION_DEGREES = (0, 90, 180, 270)

# 90 and 270 are the only rotations that transpose the frame.
TRANSPOSING_ROTATION_DEGREES = (90, 270)

_ROTATE_CODES = {
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}

_ROTATION_ERROR = "Camera rotation must be one of 0, 90, 180 or 270"


def normalize_rotation(degrees) -> int:
    """Validate a configured rotation and return its canonical value.

    Accepts any integer degree count and folds it into 0/90/180/270.  ``bool`` is
    rejected explicitly because it is an ``int`` subclass and would otherwise
    silently normalize to 0 or 1.
    """
    if isinstance(degrees, bool) or not isinstance(degrees, int):
        raise ValueError(_ROTATION_ERROR)
    value = degrees % 360
    if value not in VALID_ROTATION_DEGREES:
        raise ValueError(_ROTATION_ERROR)
    return value


def is_transposing(rotate_degrees: int) -> bool:
    """True when *rotate_degrees* swaps the frame width and height."""
    return normalize_rotation(rotate_degrees) in TRANSPOSING_ROTATION_DEGREES


def apply_orientation(
    frame,
    horizontal: bool = False,
    vertical: bool = False,
    rotate_degrees: int = 0,
):
    """Rotate then mirror *frame*, returning a new array.

    The input is never modified.  An identity orientation returns *frame*
    unchanged, so the caller pays nothing for the default configuration.
    """
    rotation = normalize_rotation(rotate_degrees)
    if rotation:
        frame = cv2.rotate(frame, _ROTATE_CODES[rotation])
    if horizontal or vertical:
        flip_code = -1 if horizontal and vertical else (1 if horizontal else 0)
        frame = cv2.flip(frame, flip_code)
    return frame
