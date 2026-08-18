from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from pl_gui.shell.AppShell import AppShell
from pl_gui.shell.startup_splash_view import StartupSplashView
from src.shared_contracts.events.robot_events import RobotTopics


class _StartupSplashBridge(QObject):
    state_ready = pyqtSignal(object)


def startup_splash_stage_text(snapshot) -> str:
    extra = getattr(snapshot, "extra", {}) or {}
    readiness_state = str(extra.get("readiness_state") or getattr(snapshot, "state", "") or "").strip().lower()
    note = str(extra.get("readiness_note") or "").strip().lower()

    if readiness_state == "disconnected":
        return "Connecting to robot runtime"
    if readiness_state == "starting":
        return "Starting robot runtime"
    if readiness_state == "drive_not_ready":
        if "ethercat" in note or "sdo" in note:
            return "Checking EtherCAT communication"
        if "disabled" in note or "not motion-ready" in note or "not operation" in note:
            return "Enabling robot drives"
        return "Preparing robot drives"
    if readiness_state == "tool_mismatch":
        return "Configuring robot tool"
    if readiness_state in {"error", "fault"}:
        return "Checking robot status"
    return "Waiting for robot readiness"


class StartupSplashCoordinator:
    def __init__(self, shell: AppShell, splash: StartupSplashView, messaging_service) -> None:
        self._shell = shell
        self._splash = splash
        self._messaging = messaging_service
        self._bridge = _StartupSplashBridge()
        self._bridge.state_ready.connect(self._apply_robot_state)
        self._active = False
        self._finished = False

    def start(self) -> None:
        if self._active:
            return
        self._messaging.subscribe(RobotTopics.STATE, self._on_robot_state)
        self._active = True

    def stop(self) -> None:
        if not self._active:
            return
        try:
            self._messaging.unsubscribe(RobotTopics.STATE, self._on_robot_state)
        finally:
            self._active = False

    def _on_robot_state(self, snapshot) -> None:
        self._bridge.state_ready.emit(snapshot)

    def _apply_robot_state(self, snapshot) -> None:
        if self._finished:
            return
        extra = getattr(snapshot, "extra", {}) or {}
        readiness_state = str(extra.get("readiness_state") or getattr(snapshot, "state", "") or "").strip().lower()
        robot_ready = extra.get("robot_ready") is True or readiness_state == "idle"

        if robot_ready:
            self._finished = True
            self._splash.set_active_step(3)
            self._splash.mark_complete()
            QTimer.singleShot(350, self._hide_splash)
            return

        self._splash.set_active_step(3)
        self._splash.set_message(startup_splash_stage_text(snapshot))

    def _hide_splash(self) -> None:
        self.stop()
        if self._shell.stacked_widget.currentWidget() is self._splash:
            self._shell.stacked_widget.setCurrentWidget(self._shell.folders_page)
        self._shell.stacked_widget.removeWidget(self._splash)
        self._splash.deleteLater()
