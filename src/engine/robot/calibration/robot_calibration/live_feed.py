import logging
import queue
import threading

import cv2

from src.engine.robot.calibration.robot_calibration.overlay import (
    build_overlay_status,
    draw_live_overlay,
)


_logger = logging.getLogger(__name__)

_live_feed_queue = queue.Queue(maxsize=2)
_live_feed_thread = None
_live_feed_thread_stop = threading.Event()


def show_live_feed(
    context,
    frame,
    current_error_mm=None,
    window_name="Calibration Live Feed",
    draw_overlay=True,
    broadcast_image=False,
):
    """Show live camera feed with overlays in a background display thread."""
    if broadcast_image and context.broker and context.CALIBRATION_IMAGE_TOPIC:
        overlay_payload = build_overlay_status(context, current_error_mm)
    else:
        overlay_payload = None

    if not context.live_visualization:
        if broadcast_image and context.broker and context.CALIBRATION_IMAGE_TOPIC:
            context.broker.publish(
                context.CALIBRATION_IMAGE_TOPIC,
                {"image": frame, "overlay": overlay_payload},
            )
        return False

    if draw_overlay:
        display_frame = draw_live_overlay(context, frame.copy(), current_error_mm)
    else:
        display_frame = frame.copy()

    if broadcast_image and context.broker and context.CALIBRATION_IMAGE_TOPIC:
        context.broker.publish(
            context.CALIBRATION_IMAGE_TOPIC,
            {"image": display_frame, "overlay": overlay_payload},
        )

    try:
        while _live_feed_queue.full():
            try:
                _live_feed_queue.get_nowait()
            except queue.Empty:
                break
        _live_feed_queue.put_nowait((window_name, display_frame))
    except queue.Full:
        pass

    global _live_feed_thread
    if _live_feed_thread is None or not _live_feed_thread.is_alive():
        _live_feed_thread_stop.clear()
        _live_feed_thread = threading.Thread(
            target=_live_feed_display_worker,
            daemon=True,
            name="LiveFeedDisplayThread",
        )
        _live_feed_thread.start()

    return False


def stop_live_feed_thread():
    """Stop the live feed display thread gracefully."""
    global _live_feed_thread
    _live_feed_thread_stop.set()
    if _live_feed_thread and _live_feed_thread.is_alive():
        _live_feed_thread.join(timeout=2.0)
    _live_feed_thread = None
    while not _live_feed_queue.empty():
        try:
            _live_feed_queue.get_nowait()
        except queue.Empty:
            break


def _live_feed_display_worker():
    while not _live_feed_thread_stop.is_set():
        try:
            window_name, display_frame = _live_feed_queue.get(timeout=0.1)
            cv2.imshow(window_name, display_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                _logger.info("Live feed stopped by user (q pressed)")
                _live_feed_thread_stop.set()
                break
            if key == ord("s"):
                import time

                cv2.imwrite(f"live_capture_{time.time():.0f}.png", display_frame)
            elif key == ord("p"):
                cv2.waitKey(0)

        except queue.Empty:
            cv2.waitKey(1)
            continue
        except Exception as exc:
            _logger.error("Error in live feed display thread: %s", exc)
            break
