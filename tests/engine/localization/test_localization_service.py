import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QApplication

from src.engine.localization.dict_translator import DictTranslator
from src.engine.localization.localization_service import LocalizationService
from src.shared_contracts.events.localization_events import LocalizationTopics


class TestDictTranslator(unittest.TestCase):

    def test_translate_returns_empty_string_on_miss(self):
        translator = DictTranslator({"Ctx": {"Hello": "Hallo"}})

        self.assertEqual(translator.translate("Ctx", "Missing"), "")
        self.assertEqual(translator.translate("Other", "Hello"), "")

    def test_is_empty_reflects_loaded_data(self):
        self.assertTrue(DictTranslator({}).isEmpty())
        self.assertFalse(DictTranslator({"Ctx": {"Hello": "Hallo"}}).isEmpty())


class TestLocalizationService(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._dir = Path(self._tmp.name)
        self._state_file = self._dir / "localization_state.json"
        self._write_catalog(
            "en",
            {
                "__meta__": {"display_name": "English"},
                "GlueDashboard": {
                    "Pick And Spray": "Pick And Spray",
                    "Reset Errors": "Reset Errors",
                },
                "ControlButtonsWidget": {
                    "Start": "Start",
                },
            },
        )
        self._write_catalog(
            "bg",
            {
                "__meta__": {"display_name": "Български"},
                "GlueDashboard": {
                    "Pick And Spray": "Вземи и пръскай",
                },
            },
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _write_catalog(self, code: str, payload: dict):
        (self._dir / f"{code}.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_available_languages_discovers_json_catalogs(self):
        self._write_catalog(".language_state", {"language_code": "bg"})
        service = LocalizationService(str(self._dir), state_file=str(self._state_file))

        self.assertEqual(
            service.available_languages(),
            [("en", "English"), ("bg", "Български")],
        )

    def test_set_language_installs_selected_translation(self):
        service = LocalizationService(str(self._dir), state_file=str(self._state_file))

        service.set_language("bg")

        self.assertEqual(service.get_language(), "bg")
        self.assertEqual(
            QCoreApplication.translate("GlueDashboard", "Pick And Spray"),
            "Вземи и пръскай",
        )

    def test_set_language_falls_back_to_english_for_missing_key(self):
        service = LocalizationService(str(self._dir), state_file=str(self._state_file))

        service.set_language("bg")

        self.assertEqual(
            QCoreApplication.translate("ControlButtonsWidget", "Start"),
            "Start",
        )

    def test_translate_uses_qt_translation_chain(self):
        service = LocalizationService(str(self._dir), state_file=str(self._state_file))
        service.set_language("bg")

        self.assertEqual(
            service.translate("GlueDashboard", "Pick And Spray"),
            "Вземи и пръскай",
        )
        self.assertEqual(
            service.translate("GlueDashboard", "Reset Errors", fallback="Reset Errors"),
            "Reset Errors",
        )

    def test_missing_language_falls_back_to_default_language(self):
        service = LocalizationService(str(self._dir), state_file=str(self._state_file))

        service.set_language("de")

        self.assertEqual(service.get_language(), "en")
        self.assertEqual(
            QCoreApplication.translate("GlueDashboard", "Reset Errors"),
            "Reset Errors",
        )

    def test_publishes_language_changed_event(self):
        messaging = MagicMock()
        service = LocalizationService(
            str(self._dir),
            messaging_service=messaging,
            state_file=str(self._state_file),
        )

        service.set_language("bg")

        messaging.publish.assert_called_once()
        topic, event = messaging.publish.call_args[0]
        self.assertEqual(topic, LocalizationTopics.LANGUAGE_CHANGED)
        self.assertEqual(event.language_code, "bg")

    def test_persists_selected_language(self):
        service = LocalizationService(str(self._dir), state_file=str(self._state_file))

        service.set_language("bg")

        self.assertTrue(self._state_file.exists())
        payload = json.loads(self._state_file.read_text(encoding="utf-8"))
        self.assertEqual(payload["language_code"], "bg")

    def test_initializes_from_persisted_language(self):
        self._state_file.write_text(json.dumps({"language_code": "bg"}), encoding="utf-8")

        service = LocalizationService(str(self._dir), state_file=str(self._state_file))

        self.assertEqual(service.get_language(), "bg")
