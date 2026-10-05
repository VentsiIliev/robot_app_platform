"""Explicit JSON field migrations; unrelated values and files are preserved."""
import json
from pathlib import Path
from .files import atomic_json


def migrate(data_root: Path, release: Path, old_schema: int, new_schema: int) -> None:
    if new_schema < old_schema:
        raise ValueError("Storage schema downgrade requires restoring a backup")
    for schema in range(old_schema + 1, new_schema + 1):
        path = release / "migrations" / f"{schema}.json"
        operations = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(operations, list):
            raise ValueError("Migration must contain a list of operations")
        for operation in operations:
            relative = Path(operation["file"])
            if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                raise ValueError("Unsafe migration file path")
            target = data_root / relative
            if not target.resolve().is_relative_to(data_root.resolve()):
                raise ValueError("Migration leaves data root")
            action = operation["action"]
            if action in {"remove", "rename"} and not target.exists():
                continue
            payload = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
            fields = operation["path"]
            if not isinstance(fields, list) or not fields or any(not isinstance(x, str) or not x for x in fields):
                raise ValueError("Migration path must be a non-empty list of object keys")
            node = payload
            for field in fields[:-1]:
                if field not in node and action in {"remove", "rename"}:
                    node = None
                    break
                node = node.setdefault(field, {})
                if not isinstance(node, dict):
                    raise ValueError("Migration path is not an object")
            if node is None:
                continue
            if not isinstance(node, dict):
                raise ValueError("Migration target is not an object")
            key = fields[-1]
            action = operation["action"]
            if action == "add":
                node.setdefault(key, operation["value"])
            elif action == "remove":
                node.pop(key, None)
            elif action == "rename":
                replacement = operation["to"]
                if not isinstance(replacement, str) or not replacement or replacement == key:
                    raise ValueError("Invalid replacement field")
                if key in node:
                    if replacement in node:
                        raise ValueError("Migration rename would overwrite an existing field")
                    node[replacement] = node.pop(key)
            else:
                raise ValueError("Unknown migration action")
            atomic_json(target, payload)
