"""Durable state files and cooperative process locks for Linux installations."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import tempfile


def sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".state-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def lock(path: Path, *, shared: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as stream:
        try:
            fcntl.flock(stream, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Platform is running or another update is in progress") from exc
        yield


def sync_tree(root: Path) -> None:
    """Persist file contents and directory entries before publishing a tree."""
    for directory, _, files in os.walk(root, topdown=False):
        directory = Path(directory)
        for name in files:
            with (directory / name).open("rb") as stream:
                os.fsync(stream.fileno())
        sync_directory(directory)
