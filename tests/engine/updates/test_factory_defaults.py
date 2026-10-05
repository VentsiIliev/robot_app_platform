import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.engine.updates.factory_defaults import seed_factory_defaults


class FactoryDefaultsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.resources = self.root / "resources"
        self.source = self.resources / "config/factory-defaults.json"
        self.source.parent.mkdir(parents=True)
        self.data = self.root / "data"
        self.identity = dict(product="paint-tray-dry-robot", robot_system="paint_tray_dry",
                             profile="tray_dryer", storage_system="paint")
        self.document = {"format": 1, **self.identity,
                         "files": {"hardware/peripherals.json": {"tray_fan": {"enabled": True}}}}
        self.save()
        self.destination = self.data / "paint/profiles/tray_dryer/storage/settings/hardware/peripherals.json"

    def save(self):
        self.source.write_text(json.dumps(self.document))

    def test_standalone_seed_creates_profile_settings_once(self):
        self.assertEqual(["hardware/peripherals.json"], seed_factory_defaults(self.resources, self.data, self.identity))
        self.assertTrue(json.loads(self.destination.read_text())["tray_fan"]["enabled"])
        self.destination.write_text('{}\n')
        self.assertEqual([], seed_factory_defaults(self.resources, self.data, self.identity))
        self.assertEqual('{}\n', self.destination.read_text())

    def test_an_existing_empty_file_is_preserved(self):
        self.destination.parent.mkdir(parents=True)
        self.destination.write_text('{}')
        seed_factory_defaults(self.resources, self.data, self.identity)
        self.assertEqual('{}', self.destination.read_text())

    def test_rejects_wrong_profile_before_writing(self):
        self.document['profile'] = 'automatic_dryer'
        self.save()
        with self.assertRaises(ValueError):
            seed_factory_defaults(self.resources, self.data, self.identity)
        self.assertFalse(self.data.exists())

    def test_rejects_accounts_and_calibration_as_factory_files(self):
        for name in ('users.json', '../hardware/peripherals.json', 'vision/calibration.json'):
            self.document['files'] = {name: {}}
            self.save()
            with self.assertRaises(ValueError):
                seed_factory_defaults(self.resources, self.data, self.identity)

    def test_symlink_cannot_redirect_factory_settings(self):
        outside = self.root / 'outside'
        outside.mkdir()
        self.destination.parent.parent.mkdir(parents=True)
        self.destination.parent.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            seed_factory_defaults(self.resources, self.data, self.identity)
        self.assertEqual([], list(outside.iterdir()))

    def test_a_competing_writer_wins(self):
        def competing_link(source, destination):
            destination.write_text('{"operator": true}')
            raise FileExistsError()
        with patch('src.engine.updates.factory_defaults.os.link', competing_link):
            seed_factory_defaults(self.resources, self.data, self.identity)
        self.assertEqual('{"operator": true}', self.destination.read_text())
        self.assertFalse(list(self.destination.parent.glob('.factory-*')))
