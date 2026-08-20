from __future__ import annotations

import threading
from contextlib import contextmanager


_LOCKS_GUARD = threading.Lock()
_PORT_LOCKS: dict[str, threading.RLock] = {}


def get_serial_bus_lock(port: str) -> threading.RLock:
    """Return the process-wide transaction lock for one physical serial port."""
    with _LOCKS_GUARD:
        return _PORT_LOCKS.setdefault(str(port), threading.RLock())


@contextmanager
def serial_bus_session(port: str, timeout: float):
    """Keep one complete request/response exchange atomic on a serial port."""
    lock = get_serial_bus_lock(port)
    wait_s = max(1.0, float(timeout) * 4.0)
    if not lock.acquire(timeout=wait_s):
        raise TimeoutError(f"Timed out waiting for Modbus serial bus {port}")
    try:
        yield
    finally:
        lock.release()
