"""Standalone paint entry point with external data and update exclusion."""
import os
import sys
from pathlib import Path

from src.engine.updates.config import UpdateConfig, default_config_path
from src.engine.updates.files import lock


def main():
    if "--self-test" in sys.argv:
        self_test()
        return
    config_path = default_config_path()
    root = (UpdateConfig.load(config_path).install_root if config_path.exists()
            else Path.home() / ".local/share/robot-platform")
    os.environ.setdefault("ROBOT_PLATFORM_DATA_ROOT", str(root / "data"))
    # Also guard direct executable launches, not just the installed launcher.
    with lock(root / "update-state/runtime.lock", shared=True):
        if (root / "update-state/transaction.json").exists():
            raise RuntimeError("Interrupted update: use the installed launcher to recover first")
        from src.bootstrap.run_main import main as run_platform
        run_platform()


def self_test():
    """Verify frozen imports, startup resources and Qt without touching hardware."""
    from PyQt6.QtWidgets import QApplication
    from src.bootstrap.startup_config import load_startup_config, load_bootstrap_provider
    from src.applications.software_update.software_update_factory import SoftwareUpdateFactory
    from src.applications.software_update.service.stub_software_update_service import StubSoftwareUpdateService
    from src.engine.localization.localization_service import LocalizationService

    from src.bootstrap.run_main import main as _run_platform
    config = load_startup_config()
    load_bootstrap_provider(config)
    app = QApplication([])
    import tempfile
    temporary = tempfile.TemporaryDirectory()
    resource_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    catalog = resource_root / "src/applications/software_update/localization"
    localization = LocalizationService(str(catalog), state_file=str(Path(temporary.name) / "language.json"))
    localization.set_language("bg")
    view = SoftwareUpdateFactory().build(StubSoftwareUpdateService())
    if view._title.text() != "Актуализация на софтуера":
        raise RuntimeError("Bundled Bulgarian update catalog missing")
    localization.set_language("en")
    app.processEvents()
    if view._title.text() != "Software Update":
        raise RuntimeError("Bundled update retranslation failed")
    view.clean_up()
    temporary.cleanup()
    print("Platform self-test passed (no hardware/backend started)")


if __name__ == "__main__":
    main()
