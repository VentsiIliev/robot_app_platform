from __future__ import annotations

from dataclasses import dataclass
import math
from threading import RLock


@dataclass(frozen=True)
class PlateDropoffReservation:
    release_pose: list[float]
    approach_pose: list[float]
    transit_pose: list[float]
    has_space_for_same_footprint: bool
    width_mm: float
    height_mm: float
    placement_id: int = 0
    left_mm: float = 0.0
    bottom_mm: float = 0.0
    outlines_mm: tuple[tuple[tuple[float, float], ...], ...] = ()


@dataclass(frozen=True)
class PlatePlacement:
    placement_id: int
    left_mm: float
    bottom_mm: float
    width_mm: float
    height_mm: float
    outlines_mm: tuple[tuple[tuple[float, float], ...], ...] = ()


class PlateLayoutService:
    """Validate a taught plate and reserve deterministic shelf placements."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._signature: tuple | None = None
        self._next_left_mm = 0.0
        self._row_bottom_mm = 0.0
        self._row_height_mm = 0.0
        self._pending: PlateDropoffReservation | None = None
        self.has_space_for_same_footprint: bool = True
        self._margin_left_mm = 0.0
        self._margin_bottom_mm = 0.0
        self._spacing_x_mm = 0.0
        self._spacing_y_mm = 0.0
        self._placements: list[PlatePlacement] = []
        self._next_placement_id = 1

    @property
    def pending(self) -> PlateDropoffReservation | None:
        with self._lock:
            return self._pending

    def snapshot(self, config) -> dict[str, object]:
        """Return an immutable dashboard-friendly view of the physical plate."""
        with self._lock:
            corners, _error = validate_plate_corners(config.plate_corners)
            width = _average_edge_length(corners[0], corners[1], corners[3], corners[2]) if corners else 0.0
            height = _average_edge_length(corners[0], corners[3], corners[1], corners[2]) if corners else 0.0
            pending = self._pending
            return {
                "width_mm": width,
                "height_mm": height,
                "placements": [vars(item).copy() for item in self._placements],
                "pending": ({
                    "placement_id": pending.placement_id,
                    "left_mm": pending.left_mm,
                    "bottom_mm": pending.bottom_mm,
                    "width_mm": pending.width_mm,
                    "height_mm": pending.height_mm,
                    "outlines_mm": pending.outlines_mm,
                } if pending is not None else None),
            }

    def clear(self) -> None:
        with self._lock:
            self._placements.clear()
            self._pending = None
            self._next_left_mm = self._margin_left_mm
            self._row_bottom_mm = self._margin_bottom_mm
            self._row_height_mm = 0.0
            self.has_space_for_same_footprint = True
            self._next_placement_id = 1

    def remove(self, placement_id: int) -> bool:
        with self._lock:
            before = len(self._placements)
            self._placements = [
                item for item in self._placements if item.placement_id != int(placement_id)
            ]
            return len(self._placements) != before

    def reserve(
        self,
        config,
        *,
        width_mm: float,
        height_mm: float,
        calibration_pose: list[float],
        workpiece_rz_at_calibration_deg: float,
        pose_calculator,
        outlines_mm=(),
    ) -> tuple[PlateDropoffReservation | None, str]:
        with self._lock:
            return self._reserve_locked(
                config,
                width_mm=width_mm,
                height_mm=height_mm,
                calibration_pose=calibration_pose,
                workpiece_rz_at_calibration_deg=workpiece_rz_at_calibration_deg,
                pose_calculator=pose_calculator,
                outlines_mm=outlines_mm,
            )

    def _reserve_locked(
        self, config, *, width_mm: float, height_mm: float,
        calibration_pose: list[float], workpiece_rz_at_calibration_deg: float,
        pose_calculator, outlines_mm=(),
    ) -> tuple[PlateDropoffReservation | None, str]:
        corners, error = validate_plate_corners(config.plate_corners)
        if error:
            return None, error
        gate_pose, error = validate_plate_passage_gate(config.plate_passage_gate_pose)
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
            self._placements.clear()
            self._next_placement_id = 1
            self._margin_left_mm = float(config.plate_margin_left_mm)
            self._margin_bottom_mm = float(config.plate_margin_bottom_mm)
            self._spacing_x_mm = float(config.plate_spacing_x_mm)
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
        left, bottom, row_height = self._candidate(width, height, right, top)
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

        occupied_with_pending = [*self._placements, PlatePlacement(
            self._next_placement_id, left, bottom, width, height
        )]
        next_left, next_bottom, _ = self._candidate(
            width, height, right, top, placements=occupied_with_pending
        )
        has_more = next_left + width <= right and next_bottom + height <= top
        self._pending = PlateDropoffReservation(
            release_pose=release_pose,
            approach_pose=approach_pose,
            transit_pose=transit_pose,
            has_space_for_same_footprint=has_more,
            width_mm=width,
            height_mm=height,
            placement_id=self._next_placement_id,
            left_mm=left,
            bottom_mm=bottom,
            outlines_mm=tuple(
                tuple((float(x), float(y)) for x, y in outline)
                for outline in outlines_mm
            ),
        )
        self._pending_state = (left, bottom, max(row_height, height))
        return self._pending, ""

    def commit(self, config) -> None:
        with self._lock:
            if self._pending is None:
                return
            left, bottom, row_height = self._pending_state
            self._placements.append(PlatePlacement(
                self._pending.placement_id, left, bottom,
                self._pending.width_mm, self._pending.height_mm,
                self._pending.outlines_mm,
            ))
            self._next_placement_id += 1
            self._next_left_mm = left + self._pending.width_mm + float(config.plate_spacing_x_mm)
            self._row_bottom_mm = bottom
            self._row_height_mm = row_height
            self.has_space_for_same_footprint = self._pending.has_space_for_same_footprint
            self._pending = None

    def cancel(self) -> None:
        with self._lock:
            self._pending = None

    def _candidate(
        self, width: float, height: float, right: float, top: float,
        *, placements: list[PlatePlacement] | None = None,
    ) -> tuple[float, float, float]:
        occupied = self._placements if placements is None else placements
        xs = {self._margin_left_mm}
        ys = {self._margin_bottom_mm}
        for item in occupied:
            xs.add(item.left_mm + item.width_mm + self._spacing_x_mm)
            ys.add(item.bottom_mm + item.height_mm + self._spacing_y_mm)
        for bottom in sorted(ys):
            if bottom + height > top:
                continue
            for left in sorted(xs):
                if left + width > right:
                    continue
                candidate = (left, bottom, width, height)
                if not any(
                    _rectangles_overlap(
                        candidate, item,
                        spacing_x=self._spacing_x_mm,
                        spacing_y=self._spacing_y_mm,
                    )
                    for item in occupied
                ):
                    return left, bottom, height
        return right + 1.0, top + 1.0, 0.0


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


def validate_plate_passage_gate(raw_pose) -> tuple[list[float], str]:
    try:
        pose = [float(value) for value in list(raw_pose)[:6]]
    except (TypeError, ValueError):
        return [], "Plate-layout dropoff requires a valid six-axis passage gate pose"
    if len(pose) != 6 or not all(math.isfinite(value) for value in pose):
        return [], "Plate-layout dropoff requires a valid six-axis passage gate pose"
    return pose, ""


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


def _rectangles_overlap(
    candidate: tuple[float, float, float, float],
    item: PlatePlacement,
    *,
    spacing_x: float = 0.0,
    spacing_y: float = 0.0,
) -> bool:
    left, bottom, width, height = candidate
    return not (
        left + width + spacing_x <= item.left_mm
        or item.left_mm + item.width_mm + spacing_x <= left
        or bottom + height + spacing_y <= item.bottom_mm
        or item.bottom_mm + item.height_mm + spacing_y <= bottom
    )
