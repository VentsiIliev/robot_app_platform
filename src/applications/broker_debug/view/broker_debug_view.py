from datetime import datetime
from typing import Dict

from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QColor, QTextCursor, QFont
from PyQt6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QWidget, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QTextEdit, QLineEdit, QPushButton, QSplitter,
    QSizePolicy,
)

from pl_gui.utils.utils_widgets.MaterialButton import MaterialButton
from pl_gui.utils.utils_widgets.table_helpers import make_table
from src.applications.base.app_styles import (
    APP_BG,
    APP_CAPTION_STYLE,
    APP_PANEL_BG,
    compact_button_style,
    divider,
    input_style,
    monospace_log_style,
    panel_style,
    section_label,
    split_panel_style,
    table_style,
)
from src.applications.base.i_application_view import IApplicationView
from src.applications.broker_debug.view.graph_widget import GraphWidget

_TEXT = "#1A1A2E"
_MUTED = "#888899"
_PRIMARY = "#905BA9"
_DANGER = "#D32F2F"
_SUCCESS = "#2E7D32"

_TABLE_STYLE = table_style(header_font_pt=8.0, body_font_pt=9.0)
_INPUT_STYLE = input_style()
_BTN_PRI = compact_button_style(variant="primary", selector="MaterialButton")
_BTN_SEC = compact_button_style(variant="secondary", selector="MaterialButton")
_BTN_DANGER = compact_button_style(variant="danger", selector="MaterialButton")


class BrokerDebugView(IApplicationView):

    refresh_requested   = pyqtSignal()
    publish_requested   = pyqtSignal(str, str)        # topic, message
    spy_requested       = pyqtSignal(str)             # topic
    unspy_requested     = pyqtSignal(str)             # topic
    clear_topic_requested = pyqtSignal(str)           # topic

    def __init__(self, parent=None):
        super().__init__("BrokerDebug", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background: {APP_BG};")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: #E0E0E0; width: 1px; }")
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_right())
        splitter.setSizes([560, 480])

        root.addWidget(splitter)

    def clean_up(self) -> None:
        pass

    # ── Left panel: topic table + graph ──────────────────────────────

    def _build_left(self) -> QWidget:
        w = QWidget(); w.setStyleSheet(f"background:{APP_BG};")
        vl = QVBoxLayout(w); vl.setContentsMargins(12, 12, 12, 12); vl.setSpacing(8)

        # Header row
        hdr = QHBoxLayout(); hdr.setContentsMargins(0,0,0,0)
        hdr.addWidget(section_label("Active Topics"))
        hdr.addStretch()
        self._refresh_btn = MaterialButton("↻ Refresh")
        self._refresh_btn.setStyleSheet(_BTN_SEC)
        self._refresh_btn.setFixedHeight(30)
        hdr.addWidget(self._refresh_btn)
        vl.addLayout(hdr)

        # Topic table
        self._table = make_table(["Topic", "Subscribers", "Actions"], fixed_height=280)
        self._table.setStyleSheet(_TABLE_STYLE)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(1, 90)
        self._table.setColumnWidth(2, 160)
        vl.addWidget(self._table)

        vl.addWidget(divider())
        vl.addWidget(section_label("Pub/Sub Graph"))

        # Graph
        self._graph = GraphWidget()
        vl.addWidget(self._graph, stretch=1)

        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        return w

    # ── Right panel: publish + spy log ───────────────────────────────

    def _build_right(self) -> QWidget:
        w = QWidget(); w.setStyleSheet(split_panel_style(bg=APP_PANEL_BG))
        vl = QVBoxLayout(w); vl.setContentsMargins(14, 12, 14, 12); vl.setSpacing(10)

        # ── Publish ───────────────────────────────────────────────────
        vl.addWidget(section_label("Publish Message"))

        topic_lbl = QLabel("Topic")
        topic_lbl.setStyleSheet(APP_CAPTION_STYLE)
        vl.addWidget(topic_lbl)
        self._pub_topic = QLineEdit(); self._pub_topic.setPlaceholderText("e.g. vision-vision_service/latest-image")
        self._pub_topic.setStyleSheet(_INPUT_STYLE); vl.addWidget(self._pub_topic)

        payload_lbl = QLabel("Payload")
        payload_lbl.setStyleSheet(APP_CAPTION_STYLE)
        vl.addWidget(payload_lbl)
        self._pub_payload = QLineEdit(); self._pub_payload.setPlaceholderText('e.g. {"value": 42}')
        self._pub_payload.setStyleSheet(_INPUT_STYLE); vl.addWidget(self._pub_payload)

        pub_row = QHBoxLayout(); pub_row.setSpacing(8)
        self._pub_btn = MaterialButton("Publish")
        self._pub_btn.setStyleSheet(_BTN_PRI)
        self._clear_pub_btn = MaterialButton("Clear")
        self._clear_pub_btn.setStyleSheet(_BTN_SEC)
        pub_row.addWidget(self._pub_btn); pub_row.addWidget(self._clear_pub_btn)
        vl.addLayout(pub_row)

        vl.addWidget(divider())

        # ── Spy subscribe ─────────────────────────────────────────────
        vl.addWidget(section_label("Spy on Topic"))
        spy_lbl = QLabel("Topic to watch")
        spy_lbl.setStyleSheet(APP_CAPTION_STYLE)
        vl.addWidget(spy_lbl)

        spy_row = QHBoxLayout(); spy_row.setSpacing(8)
        self._spy_topic = QLineEdit(); self._spy_topic.setPlaceholderText("topic to spy on")
        self._spy_topic.setStyleSheet(_INPUT_STYLE)
        self._spy_btn   = MaterialButton("Subscribe")
        self._spy_btn.setStyleSheet(_BTN_PRI)
        self._unspy_btn = MaterialButton("Unsubscribe")
        self._unspy_btn.setStyleSheet(_BTN_DANGER)
        spy_row.addWidget(self._spy_topic, stretch=1)
        spy_row.addWidget(self._spy_btn)
        spy_row.addWidget(self._unspy_btn)
        vl.addLayout(spy_row)

        vl.addWidget(divider())

        # ── Message log ───────────────────────────────────────────────
        log_hdr = QHBoxLayout(); log_hdr.setContentsMargins(0,0,0,0)
        log_hdr.addWidget(section_label("Message Log"))
        log_hdr.addStretch()
        self._clear_log_btn = MaterialButton("Clear Log")
        self._clear_log_btn.setStyleSheet(_BTN_SEC)
        self._clear_log_btn.setFixedHeight(28)
        log_hdr.addWidget(self._clear_log_btn)
        vl.addLayout(log_hdr)

        self._log = QTextEdit(); self._log.setReadOnly(True)
        self._log.setStyleSheet(monospace_log_style(font_size_pt=8.0))
        self._log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        vl.addWidget(self._log, stretch=1)

        # Signals
        self._pub_btn.clicked.connect(self._on_publish_clicked)
        self._pub_payload.returnPressed.connect(self._on_publish_clicked)
        self._clear_pub_btn.clicked.connect(lambda: (
            self._pub_topic.clear(), self._pub_payload.clear()
        ))
        self._spy_btn.clicked.connect(self._on_spy_clicked)
        self._unspy_btn.clicked.connect(self._on_unspy_clicked)
        self._clear_log_btn.clicked.connect(self._log.clear)

        return w

    # ── Internal slots ────────────────────────────────────────────────

    def _on_publish_clicked(self) -> None:
        topic   = self._pub_topic.text().strip()
        payload = self._pub_payload.text().strip()
        if topic:
            self.publish_requested.emit(topic, payload)

    def _on_spy_clicked(self) -> None:
        topic = self._spy_topic.text().strip()
        if topic:
            self.spy_requested.emit(topic)

    def _on_unspy_clicked(self) -> None:
        topic = self._spy_topic.text().strip()
        if topic:
            self.unspy_requested.emit(topic)

    # ── Public API ────────────────────────────────────────────────────

    def set_topic_map(self, topic_map: Dict[str, int]) -> None:
        # ── preserve scroll position ──────────────────────────────────
        scrollbar = self._table.verticalScrollBar()
        scroll_pos = scrollbar.value()

        # build index of current rows by topic name
        existing: Dict[str, int] = {}
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 0)
            if item:
                existing[item.text()] = r

        new_topics = set(topic_map.keys())
        old_topics = set(existing.keys())

        # remove stale rows (iterate in reverse so indices stay valid)
        for topic in old_topics - new_topics:
            self._table.removeRow(existing[topic])

        # rebuild existing index after removals
        existing = {}
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 0)
            if item:
                existing[item.text()] = r

        for topic, count in sorted(topic_map.items()):
            if topic in existing:
                # ── update count cell only ────────────────────────────
                row = existing[topic]
                count_item = self._table.item(row, 1)
                if count_item and count_item.text() != str(count):
                    count_item.setText(str(count))
                    if count == 0:
                        count_item.setForeground(QColor(_MUTED))
                    elif count >= 3:
                        count_item.setForeground(QColor(_SUCCESS))
                    else:
                        count_item.setForeground(QColor(_TEXT))
            else:
                # ── insert new row at end ─────────────────────────────
                row = self._table.rowCount()
                self._table.insertRow(row)

                self._table.setItem(row, 0, QTableWidgetItem(topic))

                count_item = QTableWidgetItem(str(count))
                count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if count == 0:
                    count_item.setForeground(QColor(_MUTED))
                elif count >= 3:
                    count_item.setForeground(QColor(_SUCCESS))
                self._table.setItem(row, 1, count_item)

                actions = QWidget()
                al = QHBoxLayout(actions)
                al.setContentsMargins(4, 2, 4, 2)
                al.setSpacing(4)
                spy_btn = QPushButton("Spy")
                clear_btn = QPushButton("Clear")
                for btn, color in ((spy_btn, _PRIMARY), (clear_btn, _DANGER)):
                    btn.setStyleSheet(f"""
                        QPushButton {{ background:transparent; color:{color};
                            border:1px solid {color}; border-radius:4px;
                            font-size:7pt; padding:2px 6px; }}
                        QPushButton:hover {{ background:rgba(0,0,0,0.06); }}
                    """)
                spy_btn.clicked.connect(lambda _, t=topic: (
                    self._spy_topic.setText(t), self.spy_requested.emit(t)
                ))
                clear_btn.clicked.connect(lambda _, t=topic: self.clear_topic_requested.emit(t))
                al.addWidget(spy_btn)
                al.addWidget(clear_btn)
                self._table.setCellWidget(row, 2, actions)
                self._table.setRowHeight(row, 36)

        # ── restore scroll position ───────────────────────────────────
        scrollbar.setValue(scroll_pos)

        self._graph.set_topic_map(topic_map)

    def append_log(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._log.append(f'<span style="color:{_MUTED};">[{ts}]</span> {message}')
        self._log.moveCursor(QTextCursor.MoveOperation.End)

    def set_spy_topic(self, topic: str) -> None:
        self._spy_topic.setText(topic)
