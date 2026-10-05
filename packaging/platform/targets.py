"""Declarative build identities; importing this module never constructs hardware."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "config/release_targets.json"


def load_target(name: str) -> dict:
    targets = json.loads(CATALOG.read_text(encoding="utf-8"))
    if name not in targets:
        raise ValueError(f"Unknown release target {name!r}; choose: {', '.join(targets)}")
    target = dict(targets[name], target=name)
    target["executable"] = target["product"]
    return target


def prepare_target(name: str, destination: Path) -> dict:
    target = load_target(name)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "platform.json").write_text(json.dumps({
        "robot_system": target["robot_system"],
        "supported_robot_systems": [target["robot_system"]],
        **({"ros_backend": {"auto_launch": False, "auto_stop": False}} if name == "twin_robot" else {}),
    }, indent=2), encoding="utf-8")
    (destination / "release-target.json").write_text(json.dumps(target, indent=2), encoding="utf-8")
    factory = ROOT / "config/factory_defaults" / f"{name}.json"
    (destination / "factory-defaults.json").write_text(factory.read_text(encoding="utf-8"), encoding="utf-8")
    return target
