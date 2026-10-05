"""Stage the independent support installer for a product release bundle."""

import argparse
import shutil
from pathlib import Path


def build_payload(destination: Path, vendor_installer: Path | None = None) -> None:
    source = Path(__file__).resolve().parent
    vendor_installer = vendor_installer or source / "install_pl_remote_support.sh"
    if "--provision-only" not in vendor_installer.read_text():
        raise ValueError("Vendor installer must support --provision-only")
    project = source.parents[1]
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("install.sh", "plproject-remote-support.service",
                 "plproject-remote-support.socket.in", "README.md"):
        shutil.copy2(source / name, destination / name)
    dropins = destination / "rustdesk.service.d"
    dropins.mkdir(exist_ok=True)
    shutil.copy2(source / "rustdesk.service.d/plproject-remote-support.conf", dropins)
    shutil.copy2(project / "src/engine/remote_support/controller.py",
                 destination / "controller.py")
    shutil.copy2(vendor_installer, destination / "install_pl_remote_support.sh")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--vendor-installer", type=Path)
    args = parser.parse_args()
    build_payload(args.destination, args.vendor_installer)
