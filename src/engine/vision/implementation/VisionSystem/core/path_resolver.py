from pathlib import Path


class PathResolver:
    """Centralized path resolution for the vision system"""

    def __init__(self, base_path: Path | str | None = None):
        if base_path is None:
            self.base_path = self._get_project_root()
        else:
            self.base_path = Path(base_path).resolve()

    @staticmethod
    def _get_project_root() -> Path:
        """Get the project root directory"""
        current_file = Path(__file__).resolve()
        return current_file.parent.parent.parent.parent

    @property
    def project_root(self) -> Path:
        """Return the project root path"""
        return self.base_path

    @property
    def src_root(self) -> Path:
        """Return the src directory path"""
        return self.base_path / "src"

    @property
    def vision_system_root(self) -> Path:
        """Return the VisionSystem directory path"""
        return self.src_root / "VisionSystem"

    @property
    def core_root(self) -> Path:
        """Return the core directory path"""
        return self.vision_system_root / "core"

    @property
    def settings_root(self) -> Path:
        """Return the settings directory path"""
        return self.core_root / "settings"

    @property
    def config_file(self) -> Path:
        """Return the config.json file path"""
        return self.settings_root / "config.json"

    @property
    def features_root(self) -> Path:
        """Return the features directory path"""
        return self.vision_system_root / "features"

    @property
    def calibration_root(self) -> Path:
        """Return the calibration directory path"""
        return self.features_root / "calibration"

    @property
    def camera_calibration_root(self) -> Path:
        """Return the camera calibration directory path"""
        return self.calibration_root / "cameraCalibration"

    @property
    def storage_path(self) -> Path:
        """Return the default storage path"""
        return self.vision_system_root / "storage"

    @property
    def external_dependencies_root(self) -> Path:
        """Return the external dependencies directory path"""
        return self.base_path / "external_dependencies"

    def ensure_path_exists(self, path: Path) -> Path:
        """Ensure the given path exists, create if not"""
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolve_relative_path(self, relative_path: str) -> Path:
        """Resolve a relative path from project root"""
        return (self.base_path / relative_path).resolve()

    def get_user_config_path(self, filename: str = "camera_settings.json") -> Path:
        """Get path for user configuration file in storage directory"""
        config_dir = self.storage_path
        self.ensure_path_exists(config_dir)
        return config_dir / filename

    def __repr__(self):
        return f"PathResolver(base_path={self.base_path})"


# Global instance for easy access
_global_resolver = None


def get_path_resolver(base_path: Path | str | None = None) -> PathResolver:
    """Get or create the global path resolver instance"""
    global _global_resolver
    if _global_resolver is None or base_path is not None:
        _global_resolver = PathResolver(base_path)
    return _global_resolver


# Convenience functions for common paths
def get_project_root() -> Path:
    return get_path_resolver().project_root


def get_config_file_path() -> Path:
    return get_path_resolver().config_file


def get_storage_path() -> Path:
    return get_path_resolver().storage_path


def get_user_config_path(filename: str = "camera_settings.json") -> Path:
    return get_path_resolver().get_user_config_path(filename)


if __name__ == "__main__":
    resolver = get_path_resolver()
    print(f"Project Root: {resolver.project_root}")
    print(f"Config File: {resolver.config_file}")
    print(f"Storage Path: {resolver.storage_path}")
    print(f"User Config: {resolver.get_user_config_path()}")

