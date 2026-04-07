from dataclasses import dataclass
from typing import Any, Dict

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer


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
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalibrationVisionSettings":
        calibration = data.get("Calibration", {})
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
