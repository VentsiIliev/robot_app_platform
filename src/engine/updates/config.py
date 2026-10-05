"""Machine-owned update configuration, never taken from a release archive."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
from urllib.parse import urlparse


def default_config_path(product: str | None = None) -> Path:
    override = os.environ.get("ROBOT_PLATFORM_UPDATE_CONFIG")
    if override:
        return Path(override).expanduser()
    product = product or os.environ.get("ROBOT_PLATFORM_PRODUCT", "paint-robot")
    # Preserve the first paint install's configuration location.
    legacy = Path.home() / ".config/robot-platform/updates.json"
    if product == "paint-robot" and legacy.is_file():
        return legacy
    return Path.home() / ".config/robot-platform" / product / "updates.json"


def default_install_root(product: str) -> Path:
    base = Path.home() / ".local/share/robot-platform"
    if product == "paint-robot" and ((base / "current").exists() or (base / "data").is_dir()):
        return base
    return base / "products" / product


@dataclass(frozen=True)
class UpdateConfig:
    install_root: Path
    repository_url: str
    public_key: Path | None
    product: str = "paint-robot"
    channel: str = "stable"
    enabled: bool = False
    timeout_seconds: int = 30
    max_download_bytes: int = 4 * 1024**3
    max_extracted_bytes: int = 8 * 1024**3

    @property
    def local_repository(self) -> Path | None:
        return Path(self.repository_url) if self.repository_url.startswith("/") else None

    @classmethod
    def load(cls, path: Path | None = None):
        path = path or default_config_path()
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Update configuration must be an object")
        enabled = raw.get("enabled", False)
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean")
        root = Path(raw["install_root"]).expanduser()
        if not root.is_absolute():
            raise ValueError("install_root must be absolute")
        repository = raw.get("repository_url", "")
        if not isinstance(repository, str):
            raise ValueError("repository_url must be a string")
        parsed = urlparse(repository)
        local = Path(repository).is_absolute()
        if enabled and not local and (parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Enabled updates require an absolute local folder or HTTPS repository_url without credentials/query")
        for name in ("product", "channel"):
            value = raw.get(name, "paint-robot" if name == "product" else "stable")
            if not isinstance(value, str) or not value or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in value):
                raise ValueError(f"Invalid {name}")
        key_value = raw.get("public_key")
        if key_value is not None and not isinstance(key_value, str):
            raise ValueError("public_key must be a quoted file path or null")
        key = Path(key_value).expanduser() if key_value else None
        if key is not None and not key.is_absolute():
            raise ValueError("public_key must be absolute")
        if enabled and ((key is not None and not key.is_file()) or (not local and key is None)):
            raise ValueError("Enabled updates require an installed public_key")
        limits = {}
        for name, default in (("timeout_seconds", 30), ("max_download_bytes", 4 * 1024**3), ("max_extracted_bytes", 8 * 1024**3)):
            value = raw.get(name, default)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
            limits[name] = value
        return cls(root.resolve(), repository.rstrip("/") + "/", key,
                   raw.get("product", "paint-robot"), raw.get("channel", "stable"), enabled, **limits)
