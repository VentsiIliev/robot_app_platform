from pathlib import Path
from src.engine.vision.implementation.VisionSystem.features.contour_matching.settings.contour_matching_settings import ContourMatchingSettings

_DEFAULT_SETTINGS_PATH = Path(__file__).resolve().parent / "storage" / "contour_matching_settings.json"

_settings: ContourMatchingSettings = ContourMatchingSettings(_DEFAULT_SETTINGS_PATH)


def configure(settings_file_path: Path) -> None:
    """Override the settings storage path — call once before first use (e.g. for per-system storage)."""
    global _settings
    _settings = ContourMatchingSettings(settings_file_path)


def get_settings() -> ContourMatchingSettings:
    return _settings


def reload_settings() -> None:
    _settings.load_from_file()
