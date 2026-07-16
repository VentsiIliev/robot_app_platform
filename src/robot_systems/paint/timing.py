from __future__ import annotations

import csv
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from inspect import signature
from time import perf_counter
from typing import Callable, Iterator, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

_ACTIVE_RECORDER: ContextVar["TimingRecorder | None"] = ContextVar("paint_timing_recorder", default=None)

_SUMMARY_STEPS = (
    "pickup_to_pivot",
    "execute_paint_contact_paths",
    "execute_pivot_paths",
    "edge_cleanup_xy_rz_pass",
    "prepare_dropoff_unwind",
    "pre_release_dropoff",
    "return_after_paint_process",
    "return_after_pickup",
    "post_execute_return",
)


@dataclass(frozen=True)
class TimingRecord:
    order: int
    step: str
    label: str
    success: bool
    exception: bool
    elapsed_s: float
    start_offset_s: float
    end_offset_s: float


class TimingRecorder:
    """Collect process timing records and emit an end-of-run summary."""

    def __init__(self, name: str) -> None:
        self.name = str(name or "timing").strip() or "timing"
        self.started_at = perf_counter()
        self.records: list[TimingRecord] = []

    def record(
        self,
        *,
        step: str,
        label: object | None,
        success: bool,
        elapsed_s: float,
        started_at: float,
        ended_at: float,
        exception: bool = False,
    ) -> None:
        self.records.append(
            TimingRecord(
                order=len(self.records) + 1,
                step=str(step),
                label="" if label is None else str(label),
                success=bool(success),
                exception=bool(exception),
                elapsed_s=float(elapsed_s),
                start_offset_s=float(started_at - self.started_at),
                end_offset_s=float(ended_at - self.started_at),
            )
        )

    def write_csv(self, output_dir: str | None) -> str | None:
        if not output_dir:
            return None
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(output_dir, f"paint_timing_{_safe_name(self.name)}_{timestamp}.csv")
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "order",
                    "step",
                    "label",
                    "success",
                    "exception",
                    "elapsed_s",
                    "start_offset_s",
                    "end_offset_s",
                ]
            )
            for display_order, record in enumerate(self._records_by_start(), start=1):
                writer.writerow(
                    [
                        display_order,
                        record.step,
                        record.label,
                        str(record.success).lower(),
                        str(record.exception).lower(),
                        f"{record.elapsed_s:.6f}",
                        f"{record.start_offset_s:.6f}",
                        f"{record.end_offset_s:.6f}",
                    ]
                )
        return path

    def log_summary(self, logger: logging.Logger, *, csv_path: str | None = None) -> None:
        records = self._records_by_start()
        total = self._total_record(records)
        failures = [record for record in records if not record.success or record.exception]
        total_s = total.elapsed_s if total is not None else self._latest_end_offset(records)
        logger.info(
            "[TIMING_SUMMARY] name=%s success=%s total_s=%.3f operations=%d csv=%s",
            self.name,
            not failures,
            total_s,
            len(self.records),
            csv_path or "",
        )

        for record in self._summary_records(records):
            logger.info(
                "[TIMING_SUMMARY] phase=%s label=%s success=%s elapsed_s=%.3f start_s=%.3f end_s=%.3f",
                record.step,
                record.label or "-",
                record.success,
                record.elapsed_s,
                record.start_offset_s,
                record.end_offset_s,
            )

        for record in failures:
            logger.info(
                "[TIMING_SUMMARY] failure step=%s label=%s exception=%s elapsed_s=%.3f start_s=%.3f end_s=%.3f",
                record.step,
                record.label or "-",
                record.exception,
                record.elapsed_s,
                record.start_offset_s,
                record.end_offset_s,
            )

        for display_order, record in enumerate(records, start=1):
            logger.debug(
                "[TIMING_DETAIL] order=%d step=%s label=%s success=%s exception=%s elapsed_s=%.3f start_s=%.3f end_s=%.3f",
                display_order,
                record.step,
                record.label or "-",
                record.success,
                record.exception,
                record.elapsed_s,
                record.start_offset_s,
                record.end_offset_s,
            )

    def _records_by_start(self) -> list[TimingRecord]:
        return sorted(self.records, key=lambda record: (record.start_offset_s, record.end_offset_s, record.order))

    def _total_record(self, records: list[TimingRecord]) -> TimingRecord | None:
        for record in records:
            if record.step == self.name:
                return record
        return None

    @staticmethod
    def _latest_end_offset(records: list[TimingRecord]) -> float:
        if not records:
            return 0.0
        return max(record.end_offset_s for record in records)

    @staticmethod
    def _summary_records(records: list[TimingRecord]) -> list[TimingRecord]:
        by_step = {step: index for index, step in enumerate(_SUMMARY_STEPS)}
        selected = [record for record in records if record.step in by_step]
        return sorted(selected, key=lambda record: (by_step[record.step], record.start_offset_s, record.order))


@contextmanager
def timing_session(name: str) -> Iterator[TimingRecorder]:
    recorder = TimingRecorder(name)
    token = _ACTIVE_RECORDER.set(recorder)
    try:
        yield recorder
    finally:
        _ACTIVE_RECORDER.reset(token)


def timed_step(
    logger: logging.Logger,
    step: str,
    *,
    label_arg: str | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Log elapsed time for a process/navigation step without changing behavior."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        func_signature = signature(func)

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            label = None
            if label_arg:
                try:
                    bound = func_signature.bind_partial(*args, **kwargs)
                    label = bound.arguments.get(label_arg)
                except TypeError:
                    label = None

            started = perf_counter()
            try:
                result = func(*args, **kwargs)
            except Exception:
                ended = perf_counter()
                _record_or_log(
                    logger,
                    step=step,
                    label=label,
                    success=False,
                    exception=True,
                    started=started,
                    ended=ended,
                )
                raise

            ended = perf_counter()
            success = _result_success(result)
            _record_or_log(
                logger,
                step=step,
                label=label,
                success=success,
                exception=False,
                started=started,
                ended=ended,
            )
            return result

        return wrapper

    return decorator


@contextmanager
def timed_block(
    logger: logging.Logger,
    step: str,
    *,
    label: object | None = None,
) -> Iterator[None]:
    """Record a named timing block in the active timing session."""
    started = perf_counter()
    try:
        yield
    except Exception:
        ended = perf_counter()
        _record_or_log(
            logger,
            step=step,
            label=label,
            success=False,
            exception=True,
            started=started,
            ended=ended,
        )
        raise
    ended = perf_counter()
    _record_or_log(
        logger,
        step=step,
        label=label,
        success=True,
        exception=False,
        started=started,
        ended=ended,
    )


def _result_success(result: object) -> bool:
    if isinstance(result, tuple) and result:
        return bool(result[0])
    if isinstance(result, bool):
        return result
    return True


def _record_or_log(
    logger: logging.Logger,
    *,
    step: str,
    label: object | None,
    success: bool,
    exception: bool,
    started: float,
    ended: float,
) -> None:
    recorder = _ACTIVE_RECORDER.get()
    elapsed_s = ended - started
    if recorder is not None:
        recorder.record(
            step=step,
            label=label,
            success=success,
            exception=exception,
            elapsed_s=elapsed_s,
            started_at=started,
            ended_at=ended,
        )
        return

    if label is None:
        logger.info(
            "[TIMING] %s success=%s exception=%s elapsed_s=%.3f",
            step,
            success,
            exception,
            elapsed_s,
            stacklevel=3,
        )
    else:
        logger.info(
            "[TIMING] %s label=%s success=%s exception=%s elapsed_s=%.3f",
            step,
            label,
            success,
            exception,
            elapsed_s,
            stacklevel=3,
        )


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value).strip("_") or "timing"
