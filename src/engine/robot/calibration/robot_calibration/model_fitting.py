from __future__ import annotations

from dataclasses import dataclass

from src.engine.robot.calibration.robot_calibration import metrics


@dataclass(frozen=True)
class CalibrationDataset:
    used_marker_ids: list[int]
    dropped_camera_ids: list[int]
    homography_training_ids: list[int]
    residual_training_ids: list[int]
    validation_ids: list[int]
    homography_camera_points: dict[int, tuple[float, float]]
    homography_robot_positions: dict[int, tuple[float, ...]]
    residual_camera_points: dict[int, tuple[float, float]]
    residual_robot_positions: dict[int, tuple[float, ...]]
    validation_camera_points: dict[int, tuple[float, float]]
    validation_robot_positions: dict[int, tuple[float, ...]]


@dataclass(frozen=True)
class CalibrationModelResult:
    labels: list[int]
    src_pts: object
    dst_pts: object
    homography_matrix: object
    homography_status: list[int] | None
    average_error_mm: float
    model_report: dict
    sorted_robot_items: list[tuple[int, tuple[float, ...]]]
    sorted_camera_items: list[tuple[int, tuple[float, float]]]


def build_calibration_dataset(context) -> CalibrationDataset:
    artifacts = context.artifacts
    target_plan = context.target_plan
    robot_positions = artifacts.robot_positions_for_calibration
    camera_points = artifacts.camera_points_for_homography

    used_marker_ids = sorted(int(marker_id) for marker_id in robot_positions.keys())
    effective_camera_points = {
        int(marker_id): camera_points[marker_id]
        for marker_id in used_marker_ids
        if marker_id in camera_points
    }
    dropped_camera_ids = sorted(
        int(marker_id)
        for marker_id in camera_points.keys()
        if int(marker_id) not in effective_camera_points
    )
    context.camera_points_for_homography = effective_camera_points
    artifacts.camera_points_for_homography = dict(effective_camera_points)

    homography_training_ids = [
        int(marker_id)
        for marker_id in target_plan.homography_marker_ids
        if int(marker_id) in effective_camera_points
        and int(marker_id) in robot_positions
    ]
    residual_training_ids = [
        int(marker_id)
        for marker_id in target_plan.residual_marker_ids
        if int(marker_id) in effective_camera_points
        and int(marker_id) in robot_positions
    ]
    validation_ids = [
        int(marker_id)
        for marker_id in target_plan.validation_marker_ids
        if int(marker_id) in effective_camera_points
        and int(marker_id) in robot_positions
    ]

    return CalibrationDataset(
        used_marker_ids=used_marker_ids,
        dropped_camera_ids=dropped_camera_ids,
        homography_training_ids=homography_training_ids,
        residual_training_ids=residual_training_ids,
        validation_ids=validation_ids,
        homography_camera_points={
            int(marker_id): effective_camera_points[int(marker_id)]
            for marker_id in homography_training_ids
        },
        homography_robot_positions={
            int(marker_id): robot_positions[int(marker_id)]
            for marker_id in homography_training_ids
        },
        residual_camera_points={
            int(marker_id): effective_camera_points[int(marker_id)]
            for marker_id in residual_training_ids
        },
        residual_robot_positions={
            int(marker_id): robot_positions[int(marker_id)]
            for marker_id in residual_training_ids
        },
        validation_camera_points={
            int(marker_id): effective_camera_points[int(marker_id)]
            for marker_id in validation_ids
        },
        validation_robot_positions={
            int(marker_id): robot_positions[int(marker_id)]
            for marker_id in validation_ids
        },
    )


def build_calibration_model(dataset: CalibrationDataset, *, use_ransac: bool, metadata: dict) -> CalibrationModelResult:
    labels, src_pts, dst_pts = metrics.prepare_correspondence_points(
        dataset.homography_camera_points,
        dataset.homography_robot_positions,
    )
    sorted_robot_items = [
        (label, dataset.homography_robot_positions[label])
        for label in labels
    ]
    sorted_camera_items = [
        (label, dataset.homography_camera_points[label])
        for label in labels
    ]

    homography_matrix, homography_status = metrics.compute_homography_from_arrays(
        src_pts,
        dst_pts,
        use_ransac=use_ransac,
    )
    average_error_mm, _ = metrics.test_calibration(
        homography_matrix,
        src_pts,
        dst_pts,
        "transformation_to_camera_center",
    )
    model_report = metrics.build_split_calibration_model_report(
        dataset.homography_camera_points,
        dataset.homography_robot_positions,
        dataset.residual_camera_points,
        dataset.residual_robot_positions,
        use_ransac=use_ransac,
        metadata=metadata,
        validation_camera_points=dataset.validation_camera_points,
        validation_robot_positions=dataset.validation_robot_positions,
    )

    return CalibrationModelResult(
        labels=list(labels),
        src_pts=src_pts,
        dst_pts=dst_pts,
        homography_matrix=homography_matrix,
        homography_status=homography_status,
        average_error_mm=float(average_error_mm),
        model_report=model_report,
        sorted_robot_items=sorted_robot_items,
        sorted_camera_items=sorted_camera_items,
    )
