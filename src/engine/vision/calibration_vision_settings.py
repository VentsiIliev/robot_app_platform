from dataclasses import dataclass
from typing import Any, Dict

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer


@dataclass
class CalibrationVisionSettings:
    chessboard_width: int = 32
    chessboard_height: int = 20
    square_size_mm: float = 25.0
    calibration_skip_frames: int = 30

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Calibration": {
                "Chessboard width": self.chessboard_width,
                "Chessboard height": self.chessboard_height,
                "Square size (mm)": self.square_size_mm,
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
