import json
import os
import logging
from typing import Optional, TypeVar, Generic

from ..interfaces.settings_repository import (
    ISettingsRepository, SettingsLoadError, SettingsSaveError
)
from ..interfaces.settings_serializer import ISettingsSerializer

T = TypeVar('T')


class BaseJsonSettingsRepository(ISettingsRepository[T], Generic[T]):

    def __init__(self, serializer: ISettingsSerializer[T], file_path: Optional[str] = None):
        super().__init__(file_path)
        self._serializer = serializer
        self.logger = logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # ISettingsRepository contract
    # ------------------------------------------------------------------

    def load(self) -> T:
        try:
            if not self.file_path:
                self.logger.warning(
                    "No file path specified for '%s' settings. Using defaults.",
                    self._serializer.settings_type,
                )
                return self._serializer.get_default()

            if not os.path.exists(self.file_path):
                default_settings = self._serializer.get_default()
                self._write_file(self._serializer.to_dict(default_settings))
                self.logger.info(
                    "Settings file not found: '%s'. Created with defaults.", self.file_path
                )
                return default_settings

            with open(self.file_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            settings = self._serializer.from_dict(data)
            self.logger.info(
                "Loaded '%s' settings from '%s'.", self._serializer.settings_type, self.file_path
            )
            return settings

        except (json.JSONDecodeError, FileNotFoundError) as exc:
            self.logger.error(
                "Failed to load '%s' settings: %s. Returning defaults.",
                self._serializer.settings_type, exc,
            )
            return self._serializer.get_default()
        except SettingsLoadError:
            raise
        except Exception as exc:
            raise SettingsLoadError(
                f"Failed to load '{self._serializer.settings_type}' settings: {exc}"
            ) from exc

    def save(self, settings: T) -> None:
        if not self.file_path:
            raise SettingsSaveError(
                f"No file path specified for '{self._serializer.settings_type}' settings"
            )
        try:
            self._write_file(self._serializer.to_dict(settings))
            self.logger.info(
                "Saved '%s' settings to '%s'.", self._serializer.settings_type, self.file_path
            )
        except SettingsSaveError:
            raise
        except Exception as exc:
            raise SettingsSaveError(
                f"Failed to save '{self._serializer.settings_type}' settings: {exc}"
            ) from exc

    def exists(self) -> bool:
        return bool(self.file_path) and os.path.exists(self.file_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write_file(self, data: dict) -> None:
        dir_path = os.path.dirname(self.file_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        try:
            with open(self.file_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except Exception as exc:
            raise SettingsLoadError(
                f"Failed to write settings file '{self.file_path}': {exc}"
            ) from exc
