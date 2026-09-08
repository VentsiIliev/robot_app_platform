from dataclasses import dataclass, field
from typing import Any, Dict

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer


@dataclass(frozen=True)
class CoordinateCalibrationProfile:
    """A named pixel-to-robot calibration and the frame it was captured in."""

    matrix_path: str = ""
    reference_frame: str = "calibration"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Matrix path": str(self.matrix_path),
            "Reference frame": str(self.reference_frame or "calibration").strip().lower(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoordinateCalibrationProfile":
        return cls(
            matrix_path=str(data.get("Matrix path", "")).strip(),
            reference_frame=str(data.get("Reference frame", "calibration")).strip().lower(),
        )


@dataclass
class CalibrationVisionSettings:
    chessboard_width: int = 32
    chessboard_height: int = 20
    square_size_mm: float = 25.0
    reference_board_mode: str = "auto"
    charuco_board_width: int = 0
    charuco_board_height: int = 0
    charuco_square_size_mm: float = 0.0
    charuco_marker_size_mm: float = 0.0
    calibration_skip_frames: int = 30
    coordinate_calibration_mode: str = "global"
    calibration_target_work_area: str = "global"
    coordinate_calibration_profiles: Dict[str, CoordinateCalibrationProfile] = field(default_factory=dict)
    work_area_calibration_profiles: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Calibration": {
                "Chessboard width": self.chessboard_width,
                "Chessboard height": self.chessboard_height,
                "Square size (mm)": self.square_size_mm,
                "Reference board mode": self.reference_board_mode,
                "ChArUco board width": self.charuco_board_width,
                "ChArUco board height": self.charuco_board_height,
                "ChArUco square size (mm)": self.charuco_square_size_mm,
                "ChArUco marker size (mm)": self.charuco_marker_size_mm,
                "Skip frames": self.calibration_skip_frames,
            },
            "Coordinate calibration": {
                "Mode": self.coordinate_calibration_mode,
                "Calibration target": self.calibration_target_work_area,
                "Profiles": {
                    str(profile_id): profile.to_dict()
                    for profile_id, profile in self.coordinate_calibration_profiles.items()
                },
                "Work area profiles": {
                    str(area_id): str(profile_id)
                    for area_id, profile_id in self.work_area_calibration_profiles.items()
                },
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalibrationVisionSettings":
        calibration = data.get("Calibration", {})
        coordinate = data.get("Coordinate calibration", {})
        calibration = calibration if isinstance(calibration, dict) else {}
        coordinate = coordinate if isinstance(coordinate, dict) else {}
        raw_profiles = coordinate.get("Profiles", {})
        raw_assignments = coordinate.get("Work area profiles", {})
        mode = str(coordinate.get("Mode", "global")).strip().lower()
        if mode not in {"global", "per_area"}:
            mode = "global"
        return cls(
            chessboard_width=int(calibration.get("Chessboard width", 32)),
            chessboard_height=int(calibration.get("Chessboard height", 20)),
            square_size_mm=float(calibration.get("Square size (mm)", 25.0)),
            reference_board_mode=str(calibration.get("Reference board mode", "auto")),
            charuco_board_width=int(calibration.get("ChArUco board width", 0)),
            charuco_board_height=int(calibration.get("ChArUco board height", 0)),
            charuco_square_size_mm=float(calibration.get("ChArUco square size (mm)", 0.0)),
            charuco_marker_size_mm=float(calibration.get("ChArUco marker size (mm)", 0.0)),
            calibration_skip_frames=int(calibration.get("Skip frames", 30)),
            coordinate_calibration_mode=mode,
            calibration_target_work_area=str(
                coordinate.get("Calibration target", "global") or "global"
            ).strip(),
            coordinate_calibration_profiles={
                str(profile_id).strip(): CoordinateCalibrationProfile.from_dict(profile)
                for profile_id, profile in raw_profiles.items()
                if str(profile_id).strip() and isinstance(profile, dict)
            } if isinstance(raw_profiles, dict) else {},
            work_area_calibration_profiles={
                str(area_id).strip(): str(profile_id).strip()
                for area_id, profile_id in raw_assignments.items()
                if str(area_id).strip() and str(profile_id).strip()
            } if isinstance(raw_assignments, dict) else {},
        )


class CalibrationVisionSettingsSerializer(ISettingsSerializer[CalibrationVisionSettings]):

    @property
    def settings_type(self) -> str:
        return "calibration_vision_settings"

    def get_default(self) -> CalibrationVisionSettings:
        return CalibrationVisionSettings()

    def to_dict(self, settings: CalibrationVisionSettings) -> Dict[str, Any]:
        return settings.to_dict()

    def from_dict(self, data: Dict[str, Any]) -> CalibrationVisionSettings:
        return CalibrationVisionSettings.from_dict(data)
