"""Download signed releases and activate them only while the platform is closed."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
import uuid

from .config import UpdateConfig
from .environment import subprocess_environment
from .files import atomic_json, lock, sync_directory, sync_tree
from .migrations import migrate
from .releases import extract_release, validate_manifest, version_tuple, release_executable, release_identity


class _HttpsRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        if urllib.parse.urlparse(new_url).scheme != "https":
            raise ValueError("Update redirects must remain HTTPS")
        return super().redirect_request(request, response, code, message, headers, new_url)


class PlatformUpdater:
    def __init__(self, config: UpdateConfig):
        self.config = config
        self.root = config.install_root
        self.state = self.root / "update-state"
        self.data = self.root / "data"
        current = self.installed()
        if current and current["product"] != config.product:
            raise ValueError("Installed robot system/profile cannot be changed through update configuration")

    def installed(self) -> dict | None:
        pointer = self.root / "current"
        if not pointer.exists():
            return None
        return json.loads((pointer / "manifest.json").read_text(encoding="utf-8"))

    def _fetch(self, url: str, target: Path, limit: int) -> None:
        if self.config.local_repository is not None:
            source = Path(url)
            if source.resolve().parent != self._local_feed().resolve():
                raise ValueError("Local release files must remain in the configured feed folder")
            if not source.is_file():
                raise ValueError(f"Local release file is missing: {source}")
            stream = source.open("rb")
        else:
            if urllib.parse.urlparse(url).scheme != "https":
                raise ValueError("Update downloads require HTTPS")
            opener = urllib.request.build_opener(_HttpsRedirect())
            stream = opener.open(url, timeout=self.config.timeout_seconds)
        with stream as response, target.open("wb") as output:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > limit:
                    raise ValueError("Update download limit exceeded")
                output.write(chunk)

    def _local_feed(self) -> Path:
        folder = self.config.local_repository
        if folder is None:
            raise ValueError("No local release folder configured")
        return folder if folder.name == self.config.channel else folder / self.config.channel

    def _release_location(self, name: str) -> str:
        if self.config.local_repository is not None:
            return str(self._local_feed() / name)
        return f"{self.config.repository_url}{self.config.channel}/{name}"

    def check(self) -> dict:
        if not self.config.enabled:
            raise RuntimeError("Updates are disabled in the platform configuration")
        url = self._release_location("latest.json")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest_file = directory / "latest.json"
            signature = directory / "latest.json.sig"
            self._fetch(url, manifest_file, 1024 * 1024)
            if self.config.local_repository is None or self.config.public_key is not None:
                self._fetch(url + ".sig", signature, 16384)
                subprocess.run(["openssl", "dgst", "-sha256", "-verify", str(self.config.public_key),
                            "-signature", str(signature), str(manifest_file)],
                           check=True, capture_output=True, timeout=15, env=subprocess_environment())
            manifest = validate_manifest(json.loads(manifest_file.read_text()), self.config.product)
        if manifest.get("channel") != self.config.channel:
            raise ValueError("Release channel mismatch")
        archive = manifest.get("archive")
        if not isinstance(archive, str) or Path(archive).name != archive or not archive.endswith(".tar.gz") or "\\" in archive or "?" in archive or "#" in archive:
            raise ValueError("Manifest archive must be a tar.gz file name")
        digest = manifest.get("sha256", "")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Invalid archive checksum")
        current = self.installed()
        if current and release_identity(current) != release_identity(manifest):
            raise ValueError("Release belongs to another robot system/profile")
        manifest["available"] = current is None or version_tuple(manifest["version"]) > version_tuple(current["version"])
        return manifest

    def stage_latest(self) -> dict:
        with lock(self.state / "update.lock"):
            manifest = self.check()
            if not manifest["available"]:
                raise RuntimeError("No newer platform release is available")
            with tempfile.TemporaryDirectory(dir=self.state) as temporary:
                archive = Path(temporary) / "release.tar.gz"
                self._fetch(self._release_location(manifest['archive']),
                            archive, self.config.max_download_bytes)
                if self._digest(archive) != manifest["sha256"]:
                    raise ValueError("Release checksum mismatch")
                return self._stage(archive, expected=manifest)

    def stage_local(self, archive: Path) -> dict:
        """Bootstrap a trusted local release; remote releases always require signatures."""
        with lock(self.state / "update.lock"):
            return self._stage(archive)

    def _stage(self, archive: Path, expected: dict | None = None) -> dict:
        releases = self.root / "releases"
        releases.mkdir(parents=True, exist_ok=True)
        temporary = releases / (".staging-" + uuid.uuid4().hex)
        extract_release(archive, temporary, self.config.max_extracted_bytes)
        try:
            manifest = validate_manifest(json.loads((temporary / "manifest.json").read_text()), self.config.product)
            if expected and any(manifest.get(k) != expected.get(k) for k in ("version", "product", "architecture", "os", "storage_schema", "robot_system", "profile", "storage_system", "executable")):
                raise ValueError("Signed manifest does not match release contents")
            if manifest["format"] == 2:
                marker = temporary / "platform/_internal/config/release-target.json"
                embedded = json.loads(marker.read_text())
                if any(embedded.get(key) != manifest[key] for key in ("product", "robot_system", "profile", "storage_system", "executable")):
                    raise ValueError("Bundled target does not match the release manifest")
                startup = json.loads((temporary / "platform/_internal/config/platform.json").read_text())
                if startup.get("robot_system") != manifest["robot_system"] or startup.get("supported_robot_systems") != [manifest["robot_system"]]:
                    raise ValueError("Bundled startup configuration does not match release target")
                from .factory_defaults import load_factory_defaults
                load_factory_defaults(temporary / "platform/_internal", manifest)
            current = self.installed()
            if current and release_identity(current) != release_identity(manifest):
                raise ValueError("Release belongs to another robot system/profile")
            environment = subprocess_environment()
            environment["QT_QPA_PLATFORM"] = "offscreen"
            subprocess.run([str(temporary / "platform" / release_executable(manifest)), "--self-test"],
                           cwd=temporary / "platform", env=environment,
                           check=True, capture_output=True, timeout=30)
            destination = releases / manifest["version"]
            if destination.exists():
                raise ValueError("Release version already installed/staged; publish a new version")
            # Persist extracted files before making a release visible.
            sync_tree(temporary)
            os.rename(temporary, destination)
            sync_directory(releases)
            atomic_json(self.state / "staged.json", manifest)
            return manifest
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)

    def queue(self) -> None:
        with lock(self.state / "update.lock"):
            staged = json.loads((self.state / "staged.json").read_text())
            atomic_json(self.state / "pending.json", {"version": staged["version"]})

    @contextmanager
    def offline(self):
        with lock(self.state / "runtime.lock"), lock(self.state / "update.lock"):
            yield

    def _pointer(self, version: str) -> None:
        version_tuple(version)
        target = self.root / "releases" / version
        if not target.is_dir():
            raise ValueError("Release does not exist")
        temporary = self.root / ".current-new"
        temporary.unlink(missing_ok=True)
        temporary.symlink_to(Path("releases") / version)
        os.replace(temporary, self.root / "current")
        sync_directory(self.root)

    def recover(self) -> None:
        """Roll back an interrupted activation before opening the application."""
        with self.offline():
            self._recover()

    def _recover(self) -> None:
        journal = self.state / "transaction.json"
        if not journal.exists():
            return
        record = json.loads(journal.read_text())
        backup = self.root / "backups" / record["backup"]
        if backup.exists():
            if self.data.exists():
                abandoned = self.root / (".failed-data-" + uuid.uuid4().hex)
                os.rename(self.data, abandoned)
            os.rename(backup, self.data)
        if record["previous"]:
            self._pointer(record["previous"])
        else:
            (self.root / "current").unlink(missing_ok=True)
        sync_directory(self.root)
        atomic_json(self.state / "result.json", {"status": "recovered", "version": record["previous"]})
        (self.state / "pending.json").unlink(missing_ok=True)
        journal.unlink()
        sync_directory(self.state)

    def apply_pending(self) -> bool:
        with self.offline():
            self._recover()
            pending = self.state / "pending.json"
            if not pending.exists():
                return False
            version = json.loads(pending.read_text())["version"]
            version_tuple(version)
            release = self.root / "releases" / version
            manifest = validate_manifest(json.loads((release / "manifest.json").read_text()), self.config.product)
            previous = self.installed()
            if previous and release_identity(previous) != release_identity(manifest):
                raise ValueError("Release belongs to another robot system/profile")
            if previous and version_tuple(version) <= version_tuple(previous["version"]):
                raise ValueError("Updates must advance the installed version")
            self.data.mkdir(parents=True, exist_ok=True)
            if self.data.is_symlink() or any(p.is_symlink() for p in self.data.rglob("*")):
                raise ValueError("Data symlinks must be resolved before updating")
            staged_data = self.root / (".data-new-" + uuid.uuid4().hex)
            backup_name = uuid.uuid4().hex
            backup = self.root / "backups" / backup_name
            backup.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copytree(self.data, staged_data)
                migrate(staged_data, release, previous["storage_schema"] if previous else 1, manifest["storage_schema"])
                if manifest.get("format") == 2:
                    from .factory_defaults import seed_factory_defaults
                    seed_factory_defaults(release / "platform/_internal", staged_data, manifest)
                sync_tree(staged_data)
                atomic_json(self.state / "transaction.json", {"previous": previous["version"] if previous else None, "backup": backup_name})
                os.rename(self.data, backup)
                sync_directory(backup.parent)
                sync_directory(self.root)
                os.rename(staged_data, self.data)
                sync_directory(self.root)
                self._pointer(version)
                atomic_json(self.state / "rollback.json", {"previous": previous["version"] if previous else None, "backup": backup_name})
                atomic_json(self.state / "result.json", {"status": "installed", "version": version})
                pending.unlink()
                (self.state / "staged.json").unlink(missing_ok=True)
                (self.state / "transaction.json").unlink()
                sync_directory(self.state)
                return True
            except BaseException as exc:
                self._recover()
                pending.unlink(missing_ok=True)
                atomic_json(self.state / "result.json", {"status": "failed", "message": str(exc)})
                raise
            finally:
                if staged_data.exists():
                    shutil.rmtree(staged_data)

    def rollback(self) -> None:
        """Explicitly restore previous software AND its pre-update data snapshot."""
        with self.offline():
            self._recover()
            record = json.loads((self.state / "rollback.json").read_text())
            if not record["previous"]:
                raise ValueError("No previous release available")
            backup = self.root / "backups" / record["backup"]
            if not backup.is_dir():
                raise ValueError("Rollback snapshot missing")
            # Preserve post-update data too; rollback is itself recoverable.
            saved_name = uuid.uuid4().hex
            current = self.installed()
            atomic_json(self.state / "transaction.json", {"previous": current["version"], "backup": saved_name})
            os.rename(self.data, self.root / "backups" / saved_name)
            sync_directory(self.root / "backups")
            sync_directory(self.root)
            shutil.copytree(backup, self.data)
            sync_tree(self.data)
            sync_directory(self.root)
            self._pointer(record["previous"])
            atomic_json(self.state / "result.json", {"status": "rolled_back", "version": record["previous"]})
            (self.state / "rollback.json").unlink()
            (self.state / "pending.json").unlink(missing_ok=True)
            (self.state / "transaction.json").unlink()
            sync_directory(self.state)

    @staticmethod
    def _digest(path: Path) -> str:
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
