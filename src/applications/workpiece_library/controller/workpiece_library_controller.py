import logging
from collections import OrderedDict

from PyQt6.QtCore import QCoreApplication, QTimer
from PyQt6.QtWidgets import QMessageBox

from src.applications.base.i_application_controller import IApplicationController
from src.applications.workpiece_library.domain import WorkpieceSchema
from src.applications.workpiece_library.model.workpiece_library_model import WorkpieceLibraryModel
from src.applications.workpiece_library.view.workpiece_library_view import WorkpieceLibraryView
from src.applications.base.styled_message_box import ask_yes_no, show_warning

from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.workpiece_events import WorkpieceTopics
from src.shared_contracts.events.shell_events import ShellTopics
_logger = logging.getLogger(__name__)

class WorkpieceLibraryController(IApplicationController):

    def __init__(self, model: WorkpieceLibraryModel, view: WorkpieceLibraryView,
                 messaging: IMessagingService):
        self._model   = model
        self._view    = view
        self._broker  = messaging
        self._all_records = []
        self._pending_open_payload = None
        self._search_text = ""
        self._show_selected_only = False
        self._thumbnail_cache: OrderedDict[str, bytes | None] = OrderedDict()

    def load(self) -> None:
        self._connect_signals()
        self._refresh()

    def stop(self) -> None:
        pass

    # ── Signals ───────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._view.delete_requested.connect(self._on_delete)
        self._view.refresh_requested.connect(self._refresh)
        self._view.search_changed.connect(self._on_search)
        self._view.selection_changed.connect(self._on_selection)
        self._view.edit_requested.connect(self._on_edit)
        self._view.open_in_editor_requested.connect(self._on_open_in_editor)
        if self._model.selection_enabled:
            self._view.selection_requested.connect(self._on_selection_applied)
            self._view.show_selected_changed.connect(self._on_show_selected_changed)
            self._view.visible_thumbnails_requested.connect(self._on_visible_thumbnails)

    # ── Handlers ──────────────────────────────────────────────────────


    def _refresh(self) -> None:
        self._thumbnail_cache.clear()
        self._all_records = self._model.load()  # already there
        schema = self._model.get_schema()  # ← re-fetch schema fresh
        self._view.set_schema(schema)  # ← new setter
        if self._model.selection_enabled:
            self._view.set_available_ids([
                str(record.get_id(schema.id_key)) for record in self._all_records
            ])
        if self._model.selection_enabled:
            self._view.set_selection(self._model.get_selection())
        self._apply_filter()
        self._view.set_status(f"{len(self._all_records)} workpiece(s) loaded")

    def _on_selection_applied(self, ids: tuple[str, ...] | None) -> None:
        try:
            self._model.save_selection(ids)
        except (OSError, ValueError) as exc:
            self._view.set_selection(self._model.get_selection())
            show_warning(self._view, self._t("Selection"), str(exc))
            return
        if self._show_selected_only:
            QTimer.singleShot(0, self._apply_filter)
        self._view.set_status(
            self._t("All workpieces selected") if ids is None
            else self._t("{count} workpiece(s) selected").format(count=len(ids))
        )

    def _on_show_selected_changed(self, enabled: bool) -> None:
        self._show_selected_only = enabled
        self._apply_filter()

    def _on_visible_thumbnails(self, storage_ids: list[str]) -> None:
        for storage_id in storage_ids:
            if storage_id not in self._thumbnail_cache:
                self._thumbnail_cache[storage_id] = self._model.get_thumbnail(storage_id)
                if len(self._thumbnail_cache) > 256:
                    self._thumbnail_cache.popitem(last=False)
            self._view.set_table_thumbnail(storage_id, self._thumbnail_cache[storage_id])

    def _on_search(self, text: str) -> None:
        self._search_text = text.strip().lower()
        self._apply_filter()

    def _apply_filter(self) -> None:
        text = self._search_text
        schema = self._model.schema
        checked = self._view.checked_ids() if self._show_selected_only else None
        filtered = [
            r for r in self._all_records
            if (checked is None or str(r.get_id(schema.id_key)) in checked)
            and (
                not text
                or text in str(r.get(schema.id_key, "")).lower()
                or text in str(r.get(schema.name_key, "")).lower()
            )
        ]
        self._view.set_records(filtered)
        if text or self._show_selected_only:
            self._view.set_status(f"{len(filtered)} match(es)")

    def _on_selection(self, record) -> None:
        if record is None:
            self._view.set_thumbnail(None)
            return
        workpiece_id = str(record.get_id(self._model.schema.id_key))
        thumbnail = self._model.get_thumbnail(workpiece_id)
        self._view.set_thumbnail(thumbnail)

    def _on_delete(self, workpiece_id: str) -> None:
        if not ask_yes_no(
            self._view,
            self._t("Delete Workpiece"),
            self._t("Delete workpiece '{workpiece_id}'?").format(workpiece_id=workpiece_id),
        ):
            return
        ok, msg = self._model.delete(workpiece_id)
        self._view.set_status(msg)
        if ok:
            self._all_records = self._model.get_all()
            self._view.set_records(self._all_records)
            self._view.set_detail(None)
        else:
            show_warning(self._view, self._t("Delete Failed"), msg)
        _logger.info("Delete %s: %s — %s", workpiece_id, ok, msg)

    def _on_edit(self, record, updates: dict) -> None:
        storage_id = str(record.get_id(self._model.schema.id_key))
        ok, msg = self._model.update(storage_id, updates)
        self._view.set_status(msg)
        if ok:
            self._view.set_records(self._model.get_all())
            updated = next(
                (r for r in self._model.get_all()
                 if str(r.get_id(self._model.schema.id_key)) == storage_id),
                None,
            )
            self._view.set_detail(updated)
        else:
            show_warning(self._view, self._t("Save Failed"), msg)
        _logger.info("Edit %s: %s — %s", storage_id, ok, msg)

    def _on_open_in_editor(self, record) -> None:
        storage_id = str(record.get_id(self._model.schema.id_key))
        raw = self._model.load_raw(storage_id)
        if raw is None:
            show_warning(
                self._view,
                self._t("Open Failed"),
                self._t("Could not load workpiece '{storage_id}'").format(storage_id=storage_id),
            )
            return
        payload = {"raw": raw, "storage_id": storage_id}
        self._broker.publish(WorkpieceTopics.OPEN_IN_EDITOR, payload)
        self._broker.publish(ShellTopics.NAVIGATE, {"app": "WorkpieceEditor"})
        self._pending_open_payload = payload
        QTimer.singleShot(100, self._publish_pending_open_in_editor)
        _logger.info("Published OPEN_IN_EDITOR storage_id=%s", storage_id)

    def _publish_pending_open_in_editor(self) -> None:
        payload = self._pending_open_payload
        self._pending_open_payload = None
        if payload is not None:
            self._broker.publish(WorkpieceTopics.OPEN_IN_EDITOR, payload)

    @staticmethod
    def _t(text: str) -> str:
        translated = QCoreApplication.translate("WorkpieceLibrary", text)
        return translated or text
