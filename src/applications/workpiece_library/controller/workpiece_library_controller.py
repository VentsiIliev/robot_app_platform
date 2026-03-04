import logging

from PyQt6.QtWidgets import QMessageBox

from src.applications.base.i_application_controller import IApplicationController
from src.applications.workpiece_library.domain import WorkpieceSchema
from src.applications.workpiece_library.model.workpiece_library_model import WorkpieceLibraryModel
from src.applications.workpiece_library.view.workpiece_library_view import WorkpieceLibraryView
from src.applications.base.styled_message_box import ask_yes_no, show_warning

from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.workpiece_events import WorkpieceTopics
_logger = logging.getLogger(__name__)

class WorkpieceLibraryController(IApplicationController):

    def __init__(self, model: WorkpieceLibraryModel, view: WorkpieceLibraryView,
                 messaging: IMessagingService):
        self._model   = model
        self._view    = view
        self._broker  = messaging
        self._all_records = []

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

    # ── Handlers ──────────────────────────────────────────────────────


    def _refresh(self) -> None:
        self._all_records = self._model.load()  # already there
        schema = self._model.get_schema()  # ← re-fetch schema fresh
        self._view.set_schema(schema)  # ← new setter
        self._view.set_records(self._all_records)
        self._view.set_status(f"{len(self._all_records)} workpiece(s) loaded")

    def _on_search(self, text: str) -> None:
        text = text.strip().lower()
        if not text:
            self._view.set_records(self._all_records)
            return
        schema = self._model.schema
        filtered = [
            r for r in self._all_records
            if text in str(r.get(schema.id_key, "")).lower()
            or text in str(r.get(schema.name_key, "")).lower()
        ]
        self._view.set_records(filtered)
        self._view.set_status(f"{len(filtered)} match(es)")

    def _on_selection(self, record) -> None:
        if record is None:
            self._view.set_thumbnail(None)
            return
        workpiece_id = str(record.get_id(self._model.schema.id_key))
        thumbnail = self._model.get_thumbnail(workpiece_id)
        self._view.set_thumbnail(thumbnail)

    def _on_delete(self, workpiece_id: str) -> None:
        if not ask_yes_no(self._view, "Delete Workpiece",
                          f"Delete workpiece '{workpiece_id}'?"):
            return
        ok, msg = self._model.delete(workpiece_id)
        self._view.set_status(msg)
        if ok:
            self._view.set_records(self._model.get_all())
            self._view.set_detail(None)
        else:
            show_warning(self._view, "Delete Failed", msg)
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
            show_warning(self._view, "Save Failed", msg)
        _logger.info("Edit %s: %s — %s", storage_id, ok, msg)

    def _on_open_in_editor(self, record) -> None:
        storage_id = str(record.get_id(self._model.schema.id_key))
        raw = self._model.load_raw(storage_id)
        if raw is None:
            show_warning(self._view, "Open Failed", f"Could not load workpiece '{storage_id}'")
            return
        self._broker.publish(WorkpieceTopics.OPEN_IN_EDITOR, {"raw": raw, "storage_id": storage_id})
        self._broker.publish("shell/navigate", {"app": "WorkpieceEditor"})
        _logger.info("Published OPEN_IN_EDITOR storage_id=%s", storage_id)


