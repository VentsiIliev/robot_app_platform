from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.engine.robot.plane_pose_mapper import PlanePoseMapper
    from src.engine.robot.height_measuring.i_height_correction_service import IHeightCorrectionService


class TargetFrame:
    """A named coordinate frame bundling its plane mapper and height correction.

    Instances are registered with ``VisionTargetResolver`` via the ``frames=``
    constructor argument. The resolver uses ``mapper`` for XY plane conversion;
    the application layer uses ``height_correction`` for Z.
    """

    def __init__(
        self,
        name: str,
        work_area_id: str = "",
        mapper: Optional["PlanePoseMapper"] = None,
        height_correction: Optional["IHeightCorrectionService"] = None,
    ) -> None:
        self.name = name
        self.work_area_id = str(work_area_id or "").strip()
        self.mapper = mapper
        self.height_correction = height_correction

    def get_z_correction(self, x: float, y: float) -> float:
        """Return the height-correction contribution in mm at robot position (x, y)."""
        if self.height_correction is None:
            return 0.0
        dz = self.height_correction.predict_z(x, y)
        return dz if dz is not None else 0.0

    def __repr__(self) -> str:
        has_mapper = self.mapper is not None
        has_hc = self.height_correction is not None
        return (
            f"TargetFrame({self.name!r}, work_area_id={self.work_area_id!r}, "
            f"mapper={has_mapper}, height_correction={has_hc})"
        )
