import json
from src.engine.updates.config import UpdateConfig, default_config_path
from src.engine.updates.updater import PlatformUpdater
from .i_software_update_service import ISoftwareUpdateService


class SoftwareUpdateService(ISoftwareUpdateService):
    def __init__(self, can_schedule):
        self._can_schedule = can_schedule

    def _updater(self):
        path = default_config_path()
        if not path.is_file():
            raise RuntimeError(f"Update configuration is missing: {path}")
        return PlatformUpdater(UpdateConfig.load(path))

    def get_status(self) -> dict:
        path = default_config_path()
        if not path.exists():
            return {"installed": "", "staged": "", "configuration": str(path), "enabled": False}
        updater = self._updater()
        installed = updater.installed() or {}
        staged_path = updater.state / "staged.json"
        staged = json.loads(staged_path.read_text()) if staged_path.exists() else {}
        result_path = updater.state / "result.json"
        result = json.loads(result_path.read_text()) if result_path.exists() else {}
        return {"installed": installed.get("version", ""), "staged": staged.get("version", ""),
                "configuration": str(path), "enabled": updater.config.enabled, "result": result}

    def check(self) -> dict:
        return self._updater().check()

    def download(self) -> dict:
        return self._updater().stage_latest()

    def schedule_installation(self) -> None:
        if not self._can_schedule():
            raise RuntimeError("Stop the production process before scheduling an update")
        self._updater().queue()
