import json
from pathlib import Path
from typing import Optional, Tuple

from src.engine.vision.implementation.VisionSystem.features.contour_matching.settings.contour_matching_settings_data import ContourMatchingSettingsData
from src.engine.vision.implementation.VisionSystem.features.contour_matching.settings.contour_matching_settings_serializer import ContourMatchingSettingsSerializer


class ContourMatchingSettings:
    def __init__(self, settings_file_path: Optional[Path] = None):
        self._serializer = ContourMatchingSettingsSerializer()
        self._data: ContourMatchingSettingsData = self._serializer.get_default()
        self.settings_file_path = settings_file_path
        if settings_file_path:
            if Path(settings_file_path).exists():
                self.load_from_file(settings_file_path)
            else:
                self.save_to_file(settings_file_path)

    # --- Getters ---

    def get_similarity_threshold(self) -> float:
        return self._data.similarity_threshold

    def get_refinement_threshold(self) -> float:
        return self._data.refinement_threshold

    def get_debug_similarity(self) -> bool:
        return self._data.debug_similarity

    def get_debug_calculate_differences(self) -> bool:
        return self._data.debug_calculate_differences

    def get_debug_align_contours(self) -> bool:
        return self._data.debug_align_contours

    def get_use_comparison_model(self) -> bool:
        return self._data.use_comparison_model

    # --- Setters ---

    def set_similarity_threshold(self, value: float) -> None:
        self._data.similarity_threshold = value

    def set_refinement_threshold(self, value: float) -> None:
        self._data.refinement_threshold = value

    def set_debug_similarity(self, value: bool) -> None:
        self._data.debug_similarity = value

    def set_debug_calculate_differences(self, value: bool) -> None:
        self._data.debug_calculate_differences = value

    def set_debug_align_contours(self, value: bool) -> None:
        self._data.debug_align_contours = value

    def set_use_comparison_model(self, value: bool) -> None:
        self._data.use_comparison_model = value

    # --- Serialization ---

    def to_dict(self) -> dict:
        return self._serializer.to_dict(self._data)

    def from_dict(self, data: dict) -> None:
        self._data = self._serializer.from_dict(data)

    # --- Persistence ---

    def save_to_file(self, file_path: Optional[Path] = None) -> None:
        path = file_path or self.settings_file_path
        if not path:
            raise ValueError("No file path specified for saving settings")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def load_from_file(self, file_path: Optional[Path] = None) -> None:
        path = file_path or self.settings_file_path
        if not path or not Path(path).exists():
            return
        try:
            with open(path, "r") as f:
                self.from_dict(json.load(f))
        except Exception as e:
            print(f"Error loading contour matching settings from {path}: {e}")

    # --- Update helpers ---

    def update_settings(self, settings: dict) -> Tuple[bool, str]:
        try:
            self.from_dict(settings)
            return True, "Settings updated successfully"
        except Exception as e:
            return False, f"Error updating settings: {e}"

    def updateSettings(self, settings: dict) -> Tuple[bool, str]:
        return self.update_settings(settings)
