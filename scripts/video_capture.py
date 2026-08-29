import argparse
from pathlib import Path
import sys
import time

import cv2

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.engine.vision.implementation.plvision.PLVision.Camera import Camera


DEFAULT_CAMERA_INDEX = 2
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
REQUESTED_FPS = 60.0
OUTPUT_PATH = "recording.avi"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record video from the shared Camera wrapper.")
    parser.add_argument("--camera", type=int, default=DEFAULT_CAMERA_INDEX)
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Stop after this many seconds; zero records until Q is pressed.",
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Record without opening a preview window.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    camera = Camera(
        cameraIndex=args.camera,
        width=DEFAULT_WIDTH,
        height=DEFAULT_HEIGHT,
        backend="ANY",
        fourcc="MJPG",
        fps=REQUESTED_FPS,
    )
    output = None
    frame_count = 0
    start_time = 0.0

    try:
        if not camera.isOpened():
            print(f"Error: Could not open camera {args.camera}.")
            return 1

        properties = camera.get_properties()
        width = int(properties["width"])
        height = int(properties["height"])
        camera_fps = float(properties["fps"])
        print(f"Requested camera FPS: {REQUESTED_FPS:.2f}")
        print(f"Camera properties: {properties}")

        if camera_fps <= 1.0 or camera_fps > 120.0:
            print(f"Camera reported unusable FPS {camera_fps:.2f}; recording at 30 FPS.")
            camera_fps = 30.0

        output = cv2.VideoWriter(
            OUTPUT_PATH,
            cv2.VideoWriter_fourcc(*"MJPG"),
            camera_fps,
            (width, height),
        )
        if not output.isOpened():
            print(f"Error: Could not create video writer at {OUTPUT_PATH}.")
            return 1

        print(f"Recording {width}x{height} at {camera_fps:.2f} FPS")
        if args.duration > 0:
            print(f"Recording will stop after {args.duration:.2f} seconds.")
        elif not args.no_preview:
            print("Press Q to stop.")

        start_time = time.monotonic()
        while True:
            if args.duration > 0 and time.monotonic() - start_time >= args.duration:
                break

            frame = camera.capture(timeout=1.0)
            if frame is None:
                print("Could not read camera frame.")
                break

            output.write(frame)
            frame_count += 1

            if not args.no_preview:
                cv2.imshow("Camera", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except KeyboardInterrupt:
        print("Recording interrupted.")
    finally:
        elapsed = time.monotonic() - start_time if start_time else 0.0
        camera.close()
        if output is not None:
            output.release()
        cv2.destroyAllWindows()

    actual_fps = frame_count / elapsed if elapsed > 0 else 0.0
    print(f"Saved as {OUTPUT_PATH}")
    print(f"Frames recorded: {frame_count}")
    print(f"Recording time: {elapsed:.2f} seconds")
    print(f"Actual capture FPS: {actual_fps:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
