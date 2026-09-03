from __future__ import annotations

import os

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.repositories.settings_service_factory import build_from_specs
from src.engine.vision.implementation.VisionSystem.VisionSystem import VisionSystem
from src.engine.vision.implementation.VisionSystem.core.service.internal_service import Service
from src.engine.vision.vision_service import VisionService
from src.engine.vision.homography_residual_transformer import HomographyResidualTransformer
from src.engine.work_areas.work_area_service import WorkAreaService
from src.robot_systems.paint.paint_robot_system import PaintRobotSystem


def build_paint_vision_service(active_area: str | None = None) -> VisionService:
    """Build vision exactly from the paint system's real specs and storage paths."""

    settings_service = build_from_specs(
        PaintRobotSystem.settings_specs,
        PaintRobotSystem.metadata.settings_root,
        PaintRobotSystem,
    )
    work_areas = WorkAreaService(
        settings_service=settings_service,
        definitions=PaintRobotSystem.work_areas,
        default_active_area_id=PaintRobotSystem.default_active_work_area_id,
    )
    if active_area is not None:
        work_areas.set_active_area_id(active_area)

    camera_settings_repo = settings_service.get_repo(CommonSettingsID.VISION_CAMERA_SETTINGS)
    data_storage_path = PaintRobotSystem.storage_path("settings", "vision", "data")
    os.makedirs(data_storage_path, exist_ok=True)
    internal_service = Service(
        data_storage_path=data_storage_path,
        settings_file_path=camera_settings_repo.file_path,
    )
    vision_system = VisionSystem(
        storage_path=data_storage_path,
        messaging_service=None,
        service=internal_service,
        work_area_service=work_areas,
    )
    return VisionService(vision_system, work_area_service=work_areas)


def build_paint_base_transformer(
    vision_service: VisionService,
) -> HomographyResidualTransformer:
    """Build the same base pixel-to-robot transformer used by paint targeting."""

    return HomographyResidualTransformer(vision_service.camera_to_robot_matrix_path)
