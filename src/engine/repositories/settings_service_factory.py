import inspect
import os
from typing import List, Type

from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.engine.repositories.json.base_json_settings_repository import BaseJsonSettingsRepository
from src.engine.repositories.settings_service import SettingsService
from src.robot_apps.base_robot_app import SettingsSpec


def build_from_specs(
    specs: List[SettingsSpec],
    settings_root: str,
    app_class: Type,
) -> ISettingsService:
    app_dir = os.path.dirname(inspect.getfile(app_class))
    repos = {}
    for spec in specs:
        path = os.path.join(app_dir, settings_root, spec.storage_key)
        repos[spec.name] = BaseJsonSettingsRepository(
            serializer=spec.serializer,
            file_path=path,
        )
    return SettingsService(repos)