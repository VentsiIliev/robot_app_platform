from __future__ import annotations

from typing import Dict

from PyQt6.QtCore import QTranslator


class DictTranslator(QTranslator):
    def __init__(self, translations: Dict[str, Dict[str, str]], parent=None):
        super().__init__(parent)
        self._translations = translations

    def isEmpty(self) -> bool:
        return len(self._translations) == 0

    def translate(self, context, source_text, disambiguation=None, n=-1):
        ctx = self._translations.get(context)
        if ctx is None:
            return None
        result = ctx.get(source_text)
        return result  # None → null QString → Qt falls back to source text
