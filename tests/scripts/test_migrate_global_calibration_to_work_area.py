import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "migrate_global_calibration_to_work_area.py"
_SPEC = importlib.util.spec_from_file_location("migrate_global_calibration", _SCRIPT_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MODULE)
migrate = _MODULE.migrate


class TestMigrateGlobalCalibrationToWorkArea(unittest.TestCase):
    def _args(self, root: Path, **overrides):
        settings_path = root / "calibration_settings.json"
        values = {
            "settings": settings_path,
            "source": root / "source.npy",
            "destination": root / "calibrations" / "paint" / "camera.npy",
            "area": "paint",
            "profile": "paint_local",
            "reference_frame": "calibration",
            "enable_per_area": False,
            "overwrite": False,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def _write_source_and_settings(self, root: Path) -> None:
        (root / "source.npy").write_bytes(b"matrix")
        (root / "source_homography_residual.json").write_text("{}", encoding="utf-8")
        (root / "calibration_settings.json").write_text(
            json.dumps({"Calibration": {}}), encoding="utf-8"
        )

    def test_migrates_without_enabling_per_area_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_source_and_settings(root)

            migrate(self._args(root))

            saved = json.loads((root / "calibration_settings.json").read_text(encoding="utf-8"))
            coordinate = saved["Coordinate calibration"]
            self.assertEqual(coordinate["Mode"], "global")
            self.assertEqual(coordinate["Work area profiles"]["paint"], "paint_local")
            self.assertEqual(
                (root / "calibrations" / "paint" / "camera.npy").read_bytes(), b"matrix"
            )

    def test_existing_profile_requires_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_source_and_settings(root)
            settings_path = root / "calibration_settings.json"
            settings_path.write_text(
                json.dumps({
                    "Coordinate calibration": {
                        "Profiles": {"paint_local": {}},
                        "Work area profiles": {},
                    }
                }),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(SystemExit, "already exists"):
                migrate(self._args(root))


if __name__ == "__main__":
    unittest.main()
