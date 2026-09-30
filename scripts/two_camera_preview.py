#!/usr/bin/env python3
"""Open two V4L2 cameras and display their live feeds side by side."""

from __future__ import annotations

import argparse
import sys
import time

import cv2
import numpy as np


DEFAULT_PRIMARY = (
    "/dev/v4l/by-path/"
    "pci-0000:00:14.0-usb-0:5:1.0-video-index0"
)
DEFAULT_AUXILIARY = (
    "/dev/v4l/by-path/"
    "pci-0000:00:14.0-usb-0:9:1.0-video-index0"
)


def _open_camera(device: str, width: int, height: int, fps: int) -> cv2.VideoCapture:
    print(f"Opening {device} ...", flush=True)
    camera = cv2.VideoCapture(device, cv2.CAP_V4L2)
    if not camera.isOpened():
        camera.release()
        raise RuntimeError(f"Could not open camera: {device}")

    camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    camera.set(cv2.CAP_PROP_FPS, fps)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return camera


def _label(frame: np.ndarray, text: str) -> np.ndarray:
    frame = frame.copy()
    cv2.rectangle(frame, (0, 0), (230, 42), (0, 0, 0), -1)
    cv2.putText(
        frame,
        text,
        (12, 29),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return frame


def _read_frame(camera: cv2.VideoCapture, name: str) -> np.ndarray:
    ok, frame = camera.read()
    if not ok or frame is None:
        raise RuntimeError(f"Lost video feed from {name}")
    return frame


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", default=DEFAULT_PRIMARY)
    parser.add_argument("--auxiliary", default=DEFAULT_AUXILIARY)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=15)
    args = parser.parse_args()

    primary = None
    auxiliary = None
    window_name = "Two camera test - q or Esc to close"

    try:
        primary = _open_camera(args.primary, args.width, args.height, args.fps)
        auxiliary = _open_camera(args.auxiliary, args.width, args.height, args.fps)

        print("Both cameras opened. Press q or Escape to close.", flush=True)
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        while True:
            primary_frame = _read_frame(primary, "primary")
            auxiliary_frame = _read_frame(auxiliary, "auxiliary")

            primary_frame = cv2.resize(primary_frame, (args.width, args.height))
            auxiliary_frame = cv2.resize(auxiliary_frame, (args.width, args.height))
            combined = np.hstack(
                (
                    _label(primary_frame, "PRIMARY (USB port 5)"),
                    _label(auxiliary_frame, "AUXILIARY (USB port 9)"),
                )
            )
            cv2.imshow(window_name, combined)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                break

        return 0
    except KeyboardInterrupt:
        return 130
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    finally:
        if auxiliary is not None:
            auxiliary.release()
        if primary is not None:
            primary.release()
        cv2.destroyAllWindows()
        time.sleep(0.1)


if __name__ == "__main__":
    raise SystemExit(main())
