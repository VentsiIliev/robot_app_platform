from __future__ import annotations

import time

import cv2


STREAM_URL = "http://192.168.222.178:5000/video_feed"
WINDOW_NAME = "Raw HTTP Camera Viewer"


def main() -> int:
    cap = cv2.VideoCapture(STREAM_URL)
    if not cap.isOpened():
        print(f"Failed to open stream: {STREAM_URL}")
        return 1

    print("Press 'q' or ESC to quit.")
    last_log = time.perf_counter()
    frames = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.01)
                continue

            frames += 1
            now = time.perf_counter()
            if now - last_log >= 1.0:
                fps = frames / (now - last_log)
                print(f"read_fps={fps:.1f}")
                frames = 0
                last_log = now

            cv2.imshow(WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
