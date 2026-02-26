import logging
import threading
import time
from typing import Callable, Dict, List, Optional

from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.weight_events import (
    CellState, CellStateEvent, WeightReading, WeightTopics,
)
from src.engine.hardware.weight.config import CalibrationConfig, CellConfig, CellsConfig
from src.engine.hardware.weight.interfaces.i_cell_calibrator import ICellCalibrator
from src.engine.hardware.weight.interfaces.i_cell_transport import ICellTransport
from src.engine.hardware.weight.interfaces.i_weight_cell_service import IWeightCellService

_RECONNECT_INTERVAL_S = 5.0


class _CellContext:

    def __init__(self, config: CellConfig, transport: ICellTransport, calibrator: ICellCalibrator):
        self.config         = config
        self.transport      = transport
        self.calibrator     = calibrator
        self.state          = CellState.DISCONNECTED
        self.lock           = threading.Lock()
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitoring     = False


class WeightCellService(IWeightCellService):

    def __init__(
        self,
        cells_config:       CellsConfig,
        transport_factory:  Callable[[CellConfig], ICellTransport],
        calibrator_factory: Callable[[CellConfig], ICellCalibrator],
        messaging:          IMessagingService,
    ):
        self._messaging = messaging
        self._logger    = logging.getLogger(self.__class__.__name__)
        self._cells:    Dict[int, _CellContext] = {}

        for cfg in cells_config.cells:
            self._cells[cfg.id] = _CellContext(
                config     = cfg,
                transport  = transport_factory(cfg),
                calibrator = calibrator_factory(cfg),
            )

    # ── Lifecycle ─────────────────────────────────────────────────────

    def connect(self, cell_id: int) -> bool:
        ctx = self._get(cell_id)
        if ctx is None:
            return False
        # publish CONNECTING outside the lock — no lock held during broker call
        self._set_state(ctx, CellState.CONNECTING)
        with ctx.lock:
            try:
                ok = ctx.transport.connect()
                new_state = CellState.CONNECTED if ok else CellState.ERROR
            except Exception as exc:
                self._logger.exception("Connect failed for cell %s", cell_id)
                new_state = CellState.ERROR
        self._set_state(ctx, new_state)
        return new_state == CellState.CONNECTED

    def disconnect(self, cell_id: int) -> None:
        ctx = self._get(cell_id)
        if ctx is None:
            return
        with ctx.lock:
            try:
                ctx.transport.disconnect()
            except Exception:
                self._logger.exception("Disconnect error for cell %s", cell_id)
        self._set_state(ctx, CellState.DISCONNECTED)

    def connect_all(self) -> None:
        """Non-blocking — each cell connects in its own daemon thread."""
        for cell_id in list(self._cells):
            t = threading.Thread(
                target = self.connect,
                args   = (cell_id,),
                daemon = True,
                name   = f"WeightCellConnect-{cell_id}",
            )
            t.start()

    def disconnect_all(self) -> None:
        for cell_id in list(self._cells):
            self.disconnect(cell_id)

    # ── Reading ───────────────────────────────────────────────────────

    def read_weight(self, cell_id: int) -> Optional[WeightReading]:
        ctx = self._get(cell_id)
        if ctx is None or ctx.state != CellState.CONNECTED:
            return None
        try:
            raw     = ctx.transport.read_weight()
            reading = WeightReading(cell_id=cell_id, value=raw)
            self._messaging.publish(WeightTopics.reading(cell_id), reading)
            self._messaging.publish(WeightTopics.all_readings(), reading)
            return reading
        except Exception as exc:
            self._logger.exception("Read failed for cell %s", cell_id)
            self._set_state(ctx, CellState.ERROR, str(exc))
            return None

    def get_cell_state(self, cell_id: int) -> CellState:
        ctx = self._get(cell_id)
        return ctx.state if ctx else CellState.DISCONNECTED

    def get_connected_cell_ids(self) -> List[int]:
        return [cid for cid, ctx in self._cells.items() if ctx.state == CellState.CONNECTED]

    # ── Monitoring — one thread per cell, auto-reconnects on ERROR ────

    def start_monitoring(self, cell_ids: List[int], interval_s: float = 0.5) -> None:
        for cell_id in cell_ids:
            ctx = self._get(cell_id)
            if ctx is None or ctx.monitoring:
                continue
            cell_interval_s = (
                ctx.config.data_fetch_interval_ms / 1000.0
                if ctx.config.data_fetch_interval_ms > 0
                else interval_s
            )
            ctx.monitoring     = True
            ctx.monitor_thread = threading.Thread(
                target = self._cell_monitor_loop,
                args   = (cell_id, cell_interval_s),
                daemon = True,
                name   = f"WeightCellMonitor-{cell_id}",
            )
            ctx.monitor_thread.start()
            self._logger.info(
                "Monitoring started for cell %s (interval=%.3fs, timeout=%.1fs)",
                cell_id, cell_interval_s, ctx.config.fetch_timeout_seconds,
            )

    def stop_monitoring(self) -> None:
        for ctx in self._cells.values():
            ctx.monitoring = False
        for ctx in self._cells.values():
            if ctx.monitor_thread:
                ctx.monitor_thread.join(timeout=3.0)
                ctx.monitor_thread = None
        self._logger.info("All cell monitors stopped")

    def _cell_monitor_loop(self, cell_id: int, interval_s: float) -> None:
        ctx = self._cells[cell_id]
        reconnect_acc = 0.0
        last_state = None

        while ctx.monitoring:
            if ctx.state == CellState.CONNECTED:
                # re-publish state if it changed since last tick (catches late subscribers)
                if ctx.state != last_state:
                    self._set_state(ctx, CellState.CONNECTED)
                last_state = ctx.state
                reconnect_acc = 0.0
                self.read_weight(cell_id)

            elif ctx.state in (CellState.DISCONNECTED, CellState.ERROR):
                if ctx.state != last_state:
                    self._set_state(ctx, ctx.state)
                last_state = ctx.state
                reconnect_acc += interval_s
                if reconnect_acc >= _RECONNECT_INTERVAL_S:
                    self._logger.info("Auto-reconnecting cell %s", cell_id)
                    self.connect(cell_id)
                    reconnect_acc = 0.0

            time.sleep(interval_s)

    # ── Calibration ───────────────────────────────────────────────────

    def tare(self, cell_id: int) -> bool:
        ctx = self._get(cell_id)
        if ctx is None:
            return False
        try:
            return ctx.calibrator.tare(cell_id)
        except Exception:
            self._logger.exception("Tare failed for cell %s", cell_id)
            return False

    def get_calibration(self, cell_id: int) -> Optional[CalibrationConfig]:
        ctx = self._get(cell_id)
        if ctx is None:
            return None
        try:
            return ctx.calibrator.get_config(cell_id)
        except Exception:
            self._logger.exception("get_calibration failed for cell %s", cell_id)
            return None

    def update_offset(self, cell_id: int, offset: float) -> bool:
        ctx = self._get(cell_id)
        if ctx is None:
            return False
        try:
            return ctx.calibrator.update_offset(cell_id, offset)
        except Exception:
            self._logger.exception("update_offset failed for cell %s", cell_id)
            return False

    def update_scale(self, cell_id: int, scale: float) -> bool:
        ctx = self._get(cell_id)
        if ctx is None:
            return False
        try:
            return ctx.calibrator.update_scale(cell_id, scale)
        except Exception:
            self._logger.exception("update_scale failed for cell %s", cell_id)
            return False

    def update_config(self, cell_id: int, offset: float, scale: float) -> bool:
        ctx = self._get(cell_id)
        if ctx is None:
            return False
        try:
            return ctx.calibrator.update_config(cell_id, offset, scale)
        except Exception:
            self._logger.exception("update_config failed for cell %s", cell_id)
            return False

    # ── Internal ──────────────────────────────────────────────────────

    def _get(self, cell_id: int) -> Optional[_CellContext]:
        ctx = self._cells.get(cell_id)
        if ctx is None:
            self._logger.warning("Unknown cell_id: %s", cell_id)
        return ctx

    def _set_state(self, ctx: _CellContext, state: CellState, message: str = "") -> None:
        ctx.state = state
        event = CellStateEvent(cell_id=ctx.config.id, state=state, message=message)
        self._messaging.publish(WeightTopics.state(ctx.config.id), event)
        self._logger.debug("Cell %s → %s", ctx.config.id, state.value)
