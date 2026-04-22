from __future__ import annotations

import time

import cv2
import numpy as np
import requests


STREAM_URL = "http://192.168.222.35:5001/video_feed"
WINDOW_NAME = "Raw HTTP Camera Viewer (requests)"
CHUNK_SIZE = 16384


def _iter_jpegs(url: str):
    with requests.get(url, stream=True, timeout=(3.0, 5.0)) as response:
        response.raise_for_status()
        buffer = bytearray()

        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if not chunk:
                continue
            buffer.extend(chunk)

            while True:
                start = buffer.find(b"\xff\xd8")
                if start < 0:
                    if len(buffer) > CHUNK_SIZE * 4:
                        del buffer[:-CHUNK_SIZE]
                    break

                end = buffer.find(b"\xff\xd9", start + 2)
                if end < 0:
                    if start > 0:
                        del buffer[:start]
                    break

                jpeg = bytes(buffer[start:end + 2])
                del buffer[:end + 2]
                yield jpeg


def main() -> int:
    print("Press 'q' or ESC to quit.")
    last_log = time.perf_counter()
    frames = 0

    try:
        for jpeg in _iter_jpegs(STREAM_URL):
            frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None or frame.size == 0:
                continue

            frames += 1
            now = time.perf_counter()
            if now - last_log >= 1.0:
                fps = frames / (now - last_log)
                print(f"decode_fps={fps:.1f}")
                frames = 0
                last_log = now

            cv2.imshow(WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
    finally:
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
