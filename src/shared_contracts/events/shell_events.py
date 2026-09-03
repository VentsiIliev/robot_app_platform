from __future__ import annotations

from dataclasses import dataclass


class ShellTopics:
    NAVIGATE = "shell/navigate"
    VISIBLE_APPLICATIONS = "shell/visible-applications"


@dataclass(frozen=True)
class ApplicationShortcut:
    app_name: str
    label: str
    icon: str
    folder_id: int = 0
    folder_name: str = ""
    folder_translation_key: str = ""
