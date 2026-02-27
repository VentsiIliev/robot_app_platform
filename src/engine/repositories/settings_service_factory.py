import inspect
import os
from typing import List, Type

from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.engine.repositories.json.base_json_settings_repository import BaseJsonSettingsRepository
from src.engine.repositories.settings_service import SettingsService
from src.robot_systems.base_robot_system import SettingsSpec


# def build_from_specs(
#     specs: List[SettingsSpec],
#     settings_root: str,
#     app_class: Type,
# ) -> ISettingsService:
#     app_dir = os.path.dirname(inspect.getfile(app_class))
#     repos = {}
#     for spec in specs:
#         path = os.path.join(app_dir, settings_root, spec.storage_key)
#         repos[spec.name] = BaseJsonSettingsRepository(
#             serializer=spec.serializer,
#             file_path=path,
#         )
#     return SettingsService(repos)


import inspect
import os
from typing import List, Type

from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.engine.repositories.json.base_json_settings_repository import BaseJsonSettingsRepository
from src.engine.repositories.settings_service import SettingsService
from src.robot_systems.base_robot_system import SettingsSpec


def build_from_specs(
    specs: List[SettingsSpec],
    settings_root: str,
    app_class: Type,
) -> ISettingsService:
    app_name = app_class.__name__.lower()

    if os.path.isabs(settings_root):
        base_dir = os.path.join(settings_root, app_name)
    else:
        app_dir = os.path.dirname(inspect.getfile(app_class))
        base_dir = os.path.join(app_dir, settings_root)

    repos = {}
    for spec in specs:
        path = os.path.join(base_dir, spec.storage_key)
        repos[spec.name] = BaseJsonSettingsRepository(
            serializer=spec.serializer,
            file_path=path,
        )
    return SettingsService(repos)
