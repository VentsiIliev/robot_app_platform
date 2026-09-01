from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PlateDropoffReservation:
    release_pose: list[float]
    approach_pose: list[float]
    transit_pose: list[float]
    has_space_for_same_footprint: bool
    width_mm: float
    height_mm: float


class PlateLayoutService:
    """Validate a taught plate and reserve deterministic shelf placements."""

    def __init__(self) -> None:
        self._signature: tuple | None = None
        self._next_left_mm = 0.0
        self._row_bottom_mm = 0.0
        self._row_height_mm = 0.0
        self._pending: PlateDropoffReservation | None = None
        self.has_space_for_same_footprint: bool = True
        self._margin_left_mm = 0.0
        self._spacing_y_mm = 0.0

    @property
    def pending(self) -> PlateDropoffReservation | None:
        return self._pending

    def reserve(
        self,
        config,
        *,
        width_mm: float,
        height_mm: float,
        calibration_pose: list[float],
        workpiece_rz_at_calibration_deg: float,
        pose_calculator,
    ) -> tuple[PlateDropoffReservation | None, str]:
        corners, error = validate_plate_corners(config.plate_corners)
        if error:
            return None, error
        numeric = (
            config.plate_release_z_offset_mm, config.plate_approach_clearance_mm,
            config.plate_margin_left_mm, config.plate_margin_right_mm,
            config.plate_margin_bottom_mm, config.plate_margin_top_mm,
            config.plate_spacing_x_mm, config.plate_spacing_y_mm,
        )
        try:
            numeric = tuple(float(value) for value in numeric)
        except (TypeError, ValueError):
            return None, "Plate-layout dropoff dimensions must be finite numbers"
        if not all(math.isfinite(value) for value in numeric) or any(value < 0.0 for value in numeric[1:]):
            return None, "Plate-layout dropoff dimensions must be finite and non-negative"
        width = float(width_mm)
        height = float(height_mm)
        if not math.isfinite(width) or not math.isfinite(height) or width <= 0.0 or height <= 0.0:
            return None, "Plate-layout dropoff requires a valid workpiece footprint"

        signature = _layout_signature(config, corners)
        if signature != self._signature:
            self._signature = signature
            self._next_left_mm = float(config.plate_margin_left_mm)
            self._row_bottom_mm = float(config.plate_margin_bottom_mm)
            self._row_height_mm = 0.0
            self._pending = None
            self._margin_left_mm = float(config.plate_margin_left_mm)
            self._spacing_y_mm = float(config.plate_spacing_y_mm)
        if self._pending is not None:
            return None, "Plate-layout dropoff already has an active reservation"

        plate_width = _average_edge_length(corners[0], corners[1], corners[3], corners[2])
        plate_height = _average_edge_length(corners[0], corners[3], corners[1], corners[2])
        if (
            plate_width <= float(config.plate_margin_left_mm) + float(config.plate_margin_right_mm)
            or plate_height <= float(config.plate_margin_bottom_mm) + float(config.plate_margin_top_mm)
        ):
            return None, "Plate-layout margins leave no usable plate area"
        right = plate_width - float(config.plate_margin_right_mm)
        top = plate_height - float(config.plate_margin_top_mm)
        left, bottom, row_height = self._candidate(width, height, right)
        if left + width > right or bottom + height > top:
            return None, "Drop-off plate is full"

        center_x = left + width / 2.0
        center_y = bottom + height / 2.0
        surface = _map_plate_point(corners, plate_width, plate_height, center_x, center_y)
        plate_rz = math.degrees(math.atan2(
            corners[1][1] - corners[0][1],
            corners[1][0] - corners[0][0],
        ))
        taught_pose = [
            surface[0],
            surface[1],
            surface[2] + float(config.plate_release_z_offset_mm),
            corners[0][3],
            corners[0][4],
            plate_rz,
        ]
        release_pose = pose_calculator(
            calibration_pose,
            taught_pose,
            workpiece_rz_at_calibration_deg,
        )
        if len(release_pose) < 3 or float(release_pose[2]) < 0.0:
            return None, "Plate-layout dropoff requires a release pose at or above Z=0"
        approach_pose = list(release_pose)
        approach_pose[2] += float(config.plate_approach_clearance_mm)
        plate_center = _map_plate_point(
            corners, plate_width, plate_height, plate_width / 2.0, plate_height / 2.0
        )
        transit_pose = list(approach_pose)
        transit_pose[:3] = [
            plate_center[0],
            plate_center[1],
            max(corner[2] for corner in corners)
            + float(config.plate_release_z_offset_mm)
            + float(config.plate_approach_clearance_mm),
        ]

        next_left = left + width + float(config.plate_spacing_x_mm)
        next_row_height = max(row_height, height)
        has_more = (
            next_left + width <= right
            or (
                float(config.plate_margin_left_mm) + width <= right
                and bottom + next_row_height + float(config.plate_spacing_y_mm) + height <= top
            )
        )
        self._pending = PlateDropoffReservation(
            release_pose=release_pose,
            approach_pose=approach_pose,
            transit_pose=transit_pose,
            has_space_for_same_footprint=has_more,
            width_mm=width,
            height_mm=height,
        )
        self._pending_state = (left, bottom, max(row_height, height))
        return self._pending, ""

    def commit(self, config) -> None:
        if self._pending is None:
            return
        left, bottom, row_height = self._pending_state
        self._next_left_mm = left + self._pending.width_mm + float(config.plate_spacing_x_mm)
        self._row_bottom_mm = bottom
        self._row_height_mm = row_height
        self.has_space_for_same_footprint = self._pending.has_space_for_same_footprint
        self._pending = None

    def cancel(self) -> None:
        self._pending = None

    def _candidate(self, width: float, height: float, right: float) -> tuple[float, float, float]:
        left = self._next_left_mm
        bottom = self._row_bottom_mm
        row_height = self._row_height_mm
        if left + width > right:
            left = self._margin_left_mm
            bottom += row_height + self._spacing_y_mm
            row_height = 0.0
        return left, bottom, row_height


def validate_plate_corners(raw_corners) -> tuple[list[list[float]], str]:
    try:
        corners = [[float(value) for value in list(corner)[:6]] for corner in list(raw_corners)]
    except (TypeError, ValueError):
        return [], "Plate-layout dropoff requires four valid corners ordered BL, BR, TR, TL"
    if len(corners) != 4 or any(len(corner) != 6 for corner in corners):
        return [], "Plate-layout dropoff requires exactly four corners ordered BL, BR, TR, TL"
    if not all(math.isfinite(value) for corner in corners for value in corner):
        return [], "Plate-layout dropoff corners must contain finite robot poses"
    xy = [(corner[0], corner[1]) for corner in corners]
    if any(math.dist(xy[index], xy[(index + 1) % 4]) <= 1e-6 for index in range(4)):
        return [], "Plate-layout dropoff corners must be distinct"
    crosses = []
    for index in range(4):
        a, b, c = xy[index], xy[(index + 1) % 4], xy[(index + 2) % 4]
        crosses.append((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]))
    if any(abs(value) <= 1e-6 for value in crosses) or not (
        all(value > 0.0 for value in crosses) or all(value < 0.0 for value in crosses)
    ):
        return [], "Plate-layout dropoff corners are not consistently ordered BL, BR, TR, TL"
    return corners, ""


def _average_edge_length(a, b, c, d) -> float:
    return (math.dist(a[:2], b[:2]) + math.dist(c[:2], d[:2])) / 2.0


def _map_plate_point(corners, width, height, x, y) -> tuple[float, float, float]:
    u, v = x / width, y / height
    bl, br, tr, tl = corners
    return tuple(
        (1-u)*(1-v)*bl[i] + u*(1-v)*br[i] + u*v*tr[i] + (1-u)*v*tl[i]
        for i in range(3)
    )


def _layout_signature(config, corners) -> tuple:
    return (
        *(value for corner in corners for value in corner[:3]),
        float(config.plate_margin_left_mm), float(config.plate_margin_right_mm),
        float(config.plate_margin_bottom_mm), float(config.plate_margin_top_mm),
        float(config.plate_spacing_x_mm), float(config.plate_spacing_y_mm),
        float(config.plate_release_z_offset_mm),
    )
