from __future__ import annotations

import json
import logging
from pathlib import Path
import re
from typing import Dict, List, Tuple

from PyQt6.QtCore import QCoreApplication

from src.engine.core.i_messaging_service import IMessagingService
from src.engine.localization.dict_translator import DictTranslator
from src.engine.localization.i_localization_service import ILocalizationService
from src.shared_contracts.events.localization_events import LanguageChangedEvent, LocalizationTopics


class LocalizationService(ILocalizationService):
    _LANGUAGE_CODE_RE = re.compile(r"^[a-z]{2}(?:[-_][A-Za-z]{2,8})?$")

    def __init__(
        self,
        translations_dir: str,
        messaging_service: IMessagingService | None = None,
        default_language: str = "en",
        state_file: str | None = None,
    ) -> None:
        self._translations_dir = Path(translations_dir)
        self._messaging = messaging_service
        self._default_language = default_language
        self._state_file = Path(state_file) if state_file is not None else self._translations_dir / ".language_state.json"
        self._current_language = self._load_persisted_language()
        self._current_translator: DictTranslator | None = None
        self._languages = self._discover_languages()
        self._logger = logging.getLogger(self.__class__.__name__)

    def set_language(self, code: str) -> None:
        app = QCoreApplication.instance()
        if app is None:
            return

        self._remove_installed_translator(app)

        resolved_language = self._default_language
        merged_catalog = self._load_catalog(self._default_language) or {}

        if code != self._default_language:
            active_data = self._load_catalog(code)
            if active_data is None:
                self._logger.warning("Missing translation catalog for '%s' — falling back to '%s'", code, self._default_language)
            else:
                merged_catalog = self._merge_catalogs(merged_catalog, active_data)
                resolved_language = code

        if merged_catalog:
            translator = DictTranslator(merged_catalog)
            app.installTranslator(translator)
            self._current_translator = translator

        self._current_language = resolved_language
        self._persist_language(resolved_language)
        if self._messaging is not None:
            self._messaging.publish(
                LocalizationTopics.LANGUAGE_CHANGED,
                LanguageChangedEvent(language_code=resolved_language),
            )

    def get_language(self) -> str:
        return self._current_language

    def available_languages(self) -> List[Tuple[str, str]]:
        return list(self._languages)

    def translate(self, context: str, source_text: str, fallback: str | None = None) -> str:
        translated = QCoreApplication.translate(context, source_text)
        if translated == source_text and fallback is not None:
            return fallback
        return translated

    def sync_selector(self, selector) -> None:
        try:
            selector.blockSignals(True)
            selector.current_language = self._current_language
            selector.updateSelectedLang()
        finally:
            selector.blockSignals(False)

    def _remove_installed_translator(self, app: QCoreApplication) -> None:
        if self._current_translator is not None:
            app.removeTranslator(self._current_translator)
            self._current_translator = None

    def _discover_languages(self) -> List[Tuple[str, str]]:
        discovered: List[Tuple[str, str]] = []
        if self._translations_dir.exists():
            for file_path in sorted(self._translations_dir.glob("*.json")):
                code = file_path.stem
                if not self._LANGUAGE_CODE_RE.fullmatch(code):
                    continue
                payload = self._read_json(file_path)
                if payload is None:
                    continue
                meta = payload.get("__meta__", {})
                display_name = meta.get("display_name") if isinstance(meta, dict) else None
                discovered.append((code, display_name or code))
        if not discovered:
            return [(self._default_language, "English")]
        by_code = {code: display for code, display in discovered}
        ordered: List[Tuple[str, str]] = []
        if self._default_language in by_code:
            ordered.append((self._default_language, by_code.pop(self._default_language)))
        ordered.extend(sorted(by_code.items()))
        return ordered

    def _load_catalog(self, code: str) -> Dict[str, Dict[str, str]] | None:
        file_path = self._translations_dir / f"{code}.json"
        payload = self._read_json(file_path)
        if payload is None:
            return None

        catalog: Dict[str, Dict[str, str]] = {}
        for context, entries in payload.items():
            if context == "__meta__":
                continue
            if not isinstance(entries, dict):
                self._logger.warning("Ignoring invalid translation context '%s' in %s", context, file_path)
                continue
            catalog[context] = {
                str(source): str(text)
                for source, text in entries.items()
            }
        return catalog

    @staticmethod
    def _merge_catalogs(
        base_catalog: Dict[str, Dict[str, str]],
        overlay_catalog: Dict[str, Dict[str, str]],
    ) -> Dict[str, Dict[str, str]]:
        merged: Dict[str, Dict[str, str]] = {
            context: dict(entries)
            for context, entries in base_catalog.items()
        }
        for context, entries in overlay_catalog.items():
            merged.setdefault(context, {}).update(entries)
        return merged

    def _read_json(self, file_path: Path) -> dict | None:
        if not file_path.exists():
            return None
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            self._logger.exception("Failed to read translations from %s", file_path)
            return None
        if not isinstance(payload, dict):
            self._logger.warning("Translation catalog %s is not a JSON object", file_path)
            return None
        return payload

    def _load_persisted_language(self) -> str:
        if not self._state_file.exists():
            return self._default_language
        try:
            payload = json.loads(self._state_file.read_text(encoding="utf-8"))
        except Exception:
            self._logger.exception("Failed to read localization state from %s", self._state_file)
            return self._default_language
        if not isinstance(payload, dict):
            return self._default_language
        language_code = payload.get("language_code")
        return str(language_code) if language_code else self._default_language

    def _persist_language(self, code: str) -> None:
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(
                json.dumps({"language_code": code}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            self._logger.exception("Failed to persist localization state to %s", self._state_file)
