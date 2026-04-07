from __future__ import annotations

from dataclasses import dataclass
import logging

import cv2
import numpy as np

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TargetSelectionPlan:
    selected_ids: list[int]
    neighbor_ids: dict[int, list[int]]
    report: dict
    homography_ids: list[int] | None = None
    residual_ids: list[int] | None = None
    validation_ids: list[int] | None = None
    execution_ids: list[int] | None = None


def build_target_selection_plan(
    marker_points_px: dict[int, np.ndarray | tuple[float, float]],
    *,
    image_width: int,
    image_height: int,
    min_targets: int,
    max_targets: int,
    min_target_separation_px: float,
    preferred_ids: list[int] | set[int] | None = None,
) -> TargetSelectionPlan:
    normalized = {
        int(marker_id): np.asarray(point, dtype=np.float64).reshape(2)
        for marker_id, point in marker_points_px.items()
    }
    if not normalized:
        return TargetSelectionPlan(selected_ids=[], neighbor_ids={}, report={"available_ids": [], "selected_ids": []})

    available_ids = sorted(normalized)
    preferred_id_set = {int(marker_id) for marker_id in (preferred_ids or [])}
    preferred_available_ids = [marker_id for marker_id in available_ids if marker_id in preferred_id_set]
    max_targets = max(1, int(max_targets or len(available_ids)))
    min_targets = max(1, int(min_targets))
    max_targets = max(max_targets, len(preferred_available_ids))
    max_targets = min(max_targets, len(available_ids))
    min_targets = min(min_targets, max_targets)

    selected_ids = _select_spread_ids(
        normalized,
        image_width=image_width,
        image_height=image_height,
        min_targets=min_targets,
        max_targets=max_targets,
        min_target_separation_px=float(min_target_separation_px),
        preferred_ids=preferred_available_ids,
    )
    added_ids = [marker_id for marker_id in selected_ids if marker_id not in preferred_available_ids]
    rejected_ids = [marker_id for marker_id in available_ids if marker_id not in selected_ids]
    neighbor_ids = _build_neighbor_ids(normalized)
    report = {
        "available_ids": available_ids,
        "preferred_available_ids": preferred_available_ids,
        "selected_ids": selected_ids,
        "added_ids": added_ids,
        "rejected_ids": rejected_ids,
        "available_count": len(available_ids),
        "preferred_available_count": len(preferred_available_ids),
        "selected_count": len(selected_ids),
        "hull_area_px2": _convex_hull_area([normalized[marker_id] for marker_id in selected_ids]),
        "min_pair_distance_px": _minimum_pair_distance([normalized[marker_id] for marker_id in selected_ids]),
    }
    _logger.info(
        "Target planning: available_ids=%s preferred_available_ids=%s selected_ids=%s added_ids=%s rejected_ids=%s min_targets=%d max_targets=%d min_separation_px=%.1f hull_area_px2=%.1f",
        available_ids,
        preferred_available_ids,
        selected_ids,
        added_ids,
        rejected_ids,
        min_targets,
        max_targets,
        float(min_target_separation_px),
        float(report["hull_area_px2"]),
    )
    return TargetSelectionPlan(selected_ids=selected_ids, neighbor_ids=neighbor_ids, report=report)


def build_partitioned_target_selection_plan(
    marker_points_px: dict[int, np.ndarray | tuple[float, float]],
    *,
    image_width: int,
    image_height: int,
    homography_targets: int,
    residual_targets: int,
    validation_targets: int,
    min_target_separation_px: float,
    preferred_ids: list[int] | set[int] | None = None,
) -> TargetSelectionPlan:
    normalized = {
        int(marker_id): np.asarray(point, dtype=np.float64).reshape(2)
        for marker_id, point in marker_points_px.items()
    }
    if not normalized:
        empty_report = {
            "available_ids": [],
            "selected_ids": [],
            "homography_ids": [],
            "residual_ids": [],
            "validation_ids": [],
            "execution_ids": [],
        }
        return TargetSelectionPlan(
            selected_ids=[],
            neighbor_ids={},
            report=empty_report,
            homography_ids=[],
            residual_ids=[],
            validation_ids=[],
            execution_ids=[],
        )

    available_ids = sorted(normalized)
    preferred_available_ids = [
        marker_id for marker_id in available_ids
        if marker_id in {int(v) for v in (preferred_ids or [])}
    ]

    homography_ids = _select_partition_ids(
        normalized,
        candidate_ids=available_ids,
        image_width=image_width,
        image_height=image_height,
        target_count=max(0, int(homography_targets)),
        min_target_separation_px=float(min_target_separation_px),
        preferred_ids=preferred_available_ids,
        seed_ids=[],
    )
    residual_ids = _select_partition_ids(
        normalized,
        candidate_ids=[marker_id for marker_id in available_ids if marker_id not in set(homography_ids)],
        image_width=image_width,
        image_height=image_height,
        target_count=max(0, int(residual_targets)),
        min_target_separation_px=float(min_target_separation_px),
        preferred_ids=[],
        seed_ids=homography_ids,
    )
    validation_ids = _select_partition_ids(
        normalized,
        candidate_ids=[
            marker_id
            for marker_id in available_ids
            if marker_id not in set(homography_ids) and marker_id not in set(residual_ids)
        ],
        image_width=image_width,
        image_height=image_height,
        target_count=max(0, int(validation_targets)),
        min_target_separation_px=float(min_target_separation_px),
        preferred_ids=[],
        seed_ids=[*homography_ids, *residual_ids],
    )
    # Sort all selected markers by ascending ID (≈ left-to-right, top-to-bottom
    # on the ChArUco board).  Each group independently selects spread-out markers
    # including corners, so the old group-concatenation order caused the robot to
    # revisit the same spatial regions once per group.  Merging and sorting
    # globally minimises total travel distance while the per-group label lists
    # (homography_ids / residual_ids / validation_ids) are unchanged and still
    # used at finalization to route each point to the correct model.
    execution_ids = sorted({*homography_ids, *residual_ids, *validation_ids})
    report = {
        "available_ids": available_ids,
        "preferred_available_ids": preferred_available_ids,
        "homography_ids": homography_ids,
        "residual_ids": residual_ids,
        "validation_ids": validation_ids,
        "execution_ids": execution_ids,
        "selected_ids": execution_ids,
        "homography_count": len(homography_ids),
        "residual_count": len(residual_ids),
        "validation_count": len(validation_ids),
        "selected_count": len(execution_ids),
        "hull_area_px2": _convex_hull_area([normalized[marker_id] for marker_id in execution_ids]),
        "min_pair_distance_px": _minimum_pair_distance([normalized[marker_id] for marker_id in execution_ids]),
    }
    _logger.info(
        "Partitioned target planning: available_ids=%s homography_ids=%s residual_ids=%s validation_ids=%s execution_ids=%s min_separation_px=%.1f hull_area_px2=%.1f",
        available_ids,
        homography_ids,
        residual_ids,
        validation_ids,
        execution_ids,
        float(min_target_separation_px),
        float(report["hull_area_px2"]),
    )
    return TargetSelectionPlan(
        selected_ids=execution_ids,
        neighbor_ids=_build_neighbor_ids(normalized),
        report=report,
        homography_ids=homography_ids,
        residual_ids=residual_ids,
        validation_ids=validation_ids,
        execution_ids=execution_ids,
    )


def _select_spread_ids(
    points_by_id: dict[int, np.ndarray],
    *,
    image_width: int,
    image_height: int,
    min_targets: int,
    max_targets: int,
    min_target_separation_px: float,
    preferred_ids: list[int] | None = None,
    seed_ids: list[int] | None = None,
) -> list[int]:
    all_ids = list(points_by_id)
    if len(all_ids) <= max_targets:
        return _sort_ids_for_execution(points_by_id, all_ids)

    corner_refs = [
        np.array([0.0, 0.0], dtype=np.float64),
        np.array([float(image_width), 0.0], dtype=np.float64),
        np.array([0.0, float(image_height)], dtype=np.float64),
        np.array([float(image_width), float(image_height)], dtype=np.float64),
    ]

    seed_ids = [int(marker_id) for marker_id in (seed_ids or []) if int(marker_id) in points_by_id]
    selected: list[int] = list(dict.fromkeys(seed_ids))
    for marker_id in preferred_ids or []:
        if marker_id in points_by_id and marker_id not in selected:
            selected.append(int(marker_id))
    if len(selected) - len(seed_ids) >= max_targets:
        return _sort_ids_for_execution(points_by_id, selected[len(seed_ids):len(seed_ids) + max_targets])

    for corner in corner_refs:
        marker_id = min(all_ids, key=lambda marker: float(np.linalg.norm(points_by_id[marker] - corner)))
        if marker_id not in selected:
            selected.append(marker_id)
        if len(selected) - len(seed_ids) >= max_targets:
            return _sort_ids_for_execution(points_by_id, selected[len(seed_ids):])

    remaining = [marker_id for marker_id in all_ids if marker_id not in selected]
    while remaining and (len(selected) - len(seed_ids)) < max_targets:
        best_id = None
        best_score = None
        for marker_id in remaining:
            point = points_by_id[marker_id]
            if selected:
                distances = [float(np.linalg.norm(point - points_by_id[selected_id])) for selected_id in selected]
                min_distance = min(distances)
            else:
                min_distance = float("inf")
            area_before = _convex_hull_area([points_by_id[selected_id] for selected_id in selected])
            area_after = _convex_hull_area([points_by_id[selected_id] for selected_id in selected] + [point])
            area_gain = area_after - area_before
            score = (area_gain, min_distance)
            if best_score is None or score > best_score:
                best_score = score
                best_id = marker_id

        if best_id is None:
            break

        best_point = points_by_id[best_id]
        if selected:
            best_min_distance = min(
                float(np.linalg.norm(best_point - points_by_id[selected_id]))
                for selected_id in selected
            )
        else:
            best_min_distance = float("inf")

        if (len(selected) - len(seed_ids)) >= min_targets and best_min_distance < min_target_separation_px:
            break

        selected.append(best_id)
        remaining.remove(best_id)

    return _sort_ids_for_execution(points_by_id, selected[len(seed_ids):])


def _select_partition_ids(
    points_by_id: dict[int, np.ndarray],
    *,
    candidate_ids: list[int],
    image_width: int,
    image_height: int,
    target_count: int,
    min_target_separation_px: float,
    preferred_ids: list[int] | None = None,
    seed_ids: list[int] | None = None,
) -> list[int]:
    if target_count <= 0 or not candidate_ids:
        return []
    subset = {
        int(marker_id): points_by_id[int(marker_id)]
        for marker_id in candidate_ids
        if int(marker_id) in points_by_id
    }
    if not subset:
        return []
    if seed_ids:
        grid_ids = _select_grid_coverage_ids(
            subset,
            image_width=image_width,
            image_height=image_height,
            target_count=min(target_count, len(subset)),
        )
        if len(grid_ids) >= min(target_count, len(subset)):
            return _sort_ids_for_execution(points_by_id, grid_ids)
    return _select_spread_ids(
        subset,
        image_width=image_width,
        image_height=image_height,
        min_targets=min(target_count, len(subset)),
        max_targets=min(target_count, len(subset)),
        min_target_separation_px=min_target_separation_px,
        preferred_ids=[int(marker_id) for marker_id in (preferred_ids or []) if int(marker_id) in subset],
        seed_ids=[int(marker_id) for marker_id in (seed_ids or []) if int(marker_id) in points_by_id],
    )


def _select_grid_coverage_ids(
    points_by_id: dict[int, np.ndarray],
    *,
    image_width: int,
    image_height: int,
    target_count: int,
) -> list[int]:
    if target_count <= 0 or not points_by_id:
        return []

    aspect = max(0.25, float(image_width) / max(1.0, float(image_height)))
    cols = max(1, int(round(np.sqrt(target_count * aspect))))
    rows = max(1, int(np.ceil(float(target_count) / float(cols))))
    while rows * cols < target_count:
        cols += 1
        rows = max(1, int(np.ceil(float(target_count) / float(cols))))

    candidate_ids = list(points_by_id.keys())
    selected: list[int] = []
    used: set[int] = set()

    for row in range(rows):
        for col in range(cols):
            if len(selected) >= target_count:
                break
            center = np.array(
                [
                    (float(col) + 0.5) * float(image_width) / float(cols),
                    (float(row) + 0.5) * float(image_height) / float(rows),
                ],
                dtype=np.float64,
            )
            best_id = None
            best_distance = None
            for marker_id in candidate_ids:
                if marker_id in used:
                    continue
                distance = float(np.linalg.norm(points_by_id[marker_id] - center))
                if best_distance is None or distance < best_distance:
                    best_distance = distance
                    best_id = marker_id
            if best_id is not None:
                selected.append(int(best_id))
                used.add(int(best_id))

    if len(selected) < target_count:
        centroid = np.mean(np.asarray(list(points_by_id.values()), dtype=np.float64), axis=0)
        remaining = [marker_id for marker_id in candidate_ids if marker_id not in used]
        remaining.sort(
            key=lambda marker_id: float(np.linalg.norm(points_by_id[marker_id] - centroid)),
        )
        for marker_id in remaining:
            if len(selected) >= target_count:
                break
            selected.append(int(marker_id))
            used.add(int(marker_id))

    return selected


def _sort_ids_for_execution(points_by_id: dict[int, np.ndarray], marker_ids: list[int]) -> list[int]:
    del points_by_id
    return sorted(int(marker_id) for marker_id in marker_ids)


def _build_neighbor_ids(points_by_id: dict[int, np.ndarray]) -> dict[int, list[int]]:
    neighbor_ids: dict[int, list[int]] = {}
    for marker_id, point in points_by_id.items():
        neighbor_ids[marker_id] = [
            other_id
            for other_id, _ in sorted(
                (
                    (other_id, float(np.linalg.norm(point - other_point)))
                    for other_id, other_point in points_by_id.items()
                    if other_id != marker_id
                ),
                key=lambda item: item[1],
            )
        ]
    return neighbor_ids


def _convex_hull_area(points: list[np.ndarray]) -> float:
    if len(points) < 3:
        return 0.0
    pts = np.asarray(points, dtype=np.float32).reshape(-1, 1, 2)
    hull = cv2.convexHull(pts)
    return float(cv2.contourArea(hull))


def _minimum_pair_distance(points: list[np.ndarray]) -> float | None:
    if len(points) < 2:
        return None
    min_distance = None
    for index, point_a in enumerate(points):
        for point_b in points[index + 1:]:
            distance = float(np.linalg.norm(np.asarray(point_a) - np.asarray(point_b)))
            if min_distance is None or distance < min_distance:
                min_distance = distance
    return min_distance
