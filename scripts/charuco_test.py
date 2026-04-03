import cv2
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple




@dataclass
class DetectionResult:
    mode: str
    charuco_corners: Optional[np.ndarray]
    charuco_ids: Optional[np.ndarray]
    marker_corners: Tuple[np.ndarray, ...]
    marker_ids: Optional[np.ndarray]
    vis: np.ndarray
    rvec: Optional[np.ndarray]
    tvec: Optional[np.ndarray]


class CharucoBoardDetector:
    """
    Single ChArUco detector for one board convention.
    """

    def __init__(
        self,
        squares_x: int = 5,
        squares_y: int = 6,
        square_length: float = 0.04,
        marker_length: float = 0.02,
        dictionary_id: int = cv2.aruco.DICT_4X4_50,
        legacy_pattern: bool = False,
    ) -> None:
        self.squares_x = squares_x
        self.squares_y = squares_y
        self.square_length = square_length
        self.marker_length = marker_length
        self.dictionary_id = dictionary_id
        self.legacy_pattern = legacy_pattern

        self.dictionary = cv2.aruco.getPredefinedDictionary(dictionary_id)
        self.board = cv2.aruco.CharucoBoard(
            (squares_x, squares_y),
            square_length,
            marker_length,
            self.dictionary,
        )

        if legacy_pattern:
            if hasattr(self.board, "setLegacyPattern"):
                self.board.setLegacyPattern(True)
            else:
                raise RuntimeError(
                    "This OpenCV build does not support setLegacyPattern(). "
                    "Install/upgrade opencv-contrib-python."
                )

        self.detector = cv2.aruco.CharucoDetector(self.board)

    def generate_board_image(
        self,
        out_size: Tuple[int, int] = (900, 1100),
        margin_size: int = 20,
        border_bits: int = 1,
    ) -> np.ndarray:
        return self.board.generateImage(
            out_size,
            marginSize=margin_size,
            borderBits=border_bits,
        )

    def detect_raw(self, image: np.ndarray):
        if image is None:
            raise ValueError("Input image is None")

        if len(image.shape) == 2:
            gray = image
        else:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        return self.detector.detectBoard(gray)


class AutoCharucoBoardDetector:
    """
    Try new convention first, then legacy convention, and keep the better result.
    Also estimates board pose and draws coordinate axes when enough ChArUco
    corners are detected.
    """

    def __init__(
        self,
        squares_x: int = 5,
        squares_y: int = 6,
        square_length: float = 0.04,
        marker_length: float = 0.02,
        dictionary_id: int = cv2.aruco.DICT_4X4_50,
    ) -> None:
        self.normal = CharucoBoardDetector(
            squares_x=squares_x,
            squares_y=squares_y,
            square_length=square_length,
            marker_length=marker_length,
            dictionary_id=dictionary_id,
            legacy_pattern=False,
        )
        self.legacy = CharucoBoardDetector(
            squares_x=squares_x,
            squares_y=squares_y,
            square_length=square_length,
            marker_length=marker_length,
            dictionary_id=dictionary_id,
            legacy_pattern=True,
        )
        self.square_length = square_length

    @staticmethod
    def _build_demo_camera_matrix(image_shape: Tuple[int, int, int]) -> np.ndarray:
        h, w = image_shape[:2]
        fx = float(w)
        fy = float(w)
        cx = w / 2.0
        cy = h / 2.0
        return np.array(
            [
                [fx, 0.0, cx],
                [0.0, fy, cy],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float32,
        )

    @staticmethod
    def _estimate_pose(
        board,
        charuco_corners: Optional[np.ndarray],
        charuco_ids: Optional[np.ndarray],
        camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray,
    ):
        if charuco_ids is None or charuco_corners is None or len(charuco_ids) < 4:
            return None, None

        try:
            obj_points, img_points = board.matchImagePoints(charuco_corners, charuco_ids)
        except Exception:
            return None, None

        if obj_points is None or img_points is None:
            return None, None
        if len(obj_points) < 4 or len(img_points) < 4:
            return None, None

        ok, rvec, tvec = cv2.solvePnP(
            obj_points,
            img_points,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )

        if not ok:
            return None, None

        return rvec, tvec

    def _make_result(
        self,
        mode: str,
        board_detector: CharucoBoardDetector,
        image: np.ndarray,
        charuco_corners,
        charuco_ids,
        marker_corners,
        marker_ids,
    ) -> DetectionResult:
        if len(image.shape) == 2:
            vis = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            vis = image.copy()

        if marker_ids is not None and len(marker_ids) > 0:
            cv2.aruco.drawDetectedMarkers(vis, marker_corners, marker_ids)

        if charuco_ids is not None and len(charuco_ids) > 0:
            cv2.aruco.drawDetectedCornersCharuco(
                vis,
                charuco_corners,
                charuco_ids,
                (0, 255, 0),
            )

        camera_matrix = self._build_demo_camera_matrix(vis.shape)
        dist_coeffs = np.zeros((5, 1), dtype=np.float32)

        rvec, tvec = self._estimate_pose(
            board_detector.board,
            charuco_corners,
            charuco_ids,
            camera_matrix,
            dist_coeffs,
        )

        if rvec is not None and tvec is not None:
            axis_length = self.square_length * 2.0
            cv2.drawFrameAxes(vis, camera_matrix, dist_coeffs, rvec, tvec, axis_length, 2)

        return DetectionResult(
            mode=mode,
            charuco_corners=charuco_corners,
            charuco_ids=charuco_ids,
            marker_corners=marker_corners,
            marker_ids=marker_ids,
            vis=vis,
            rvec=rvec,
            tvec=tvec,
        )

    def detect(self, image: np.ndarray) -> DetectionResult:
        normal_raw = self.normal.detect_raw(image)
        legacy_raw = self.legacy.detect_raw(image)

        normal_charuco_corners, normal_charuco_ids, normal_marker_corners, normal_marker_ids = normal_raw
        legacy_charuco_corners, legacy_charuco_ids, legacy_marker_corners, legacy_marker_ids = legacy_raw

        normal_score = 0 if normal_charuco_ids is None else len(normal_charuco_ids)
        legacy_score = 0 if legacy_charuco_ids is None else len(legacy_charuco_ids)

        if legacy_score > normal_score:
            return self._make_result(
                mode="legacy",
                board_detector=self.legacy,
                image=image,
                charuco_corners=legacy_charuco_corners,
                charuco_ids=legacy_charuco_ids,
                marker_corners=legacy_marker_corners,
                marker_ids=legacy_marker_ids,
            )

        return self._make_result(
            mode="normal",
            board_detector=self.normal,
            image=image,
            charuco_corners=normal_charuco_corners,
            charuco_ids=normal_charuco_ids,
            marker_corners=normal_marker_corners,
            marker_ids=normal_marker_ids,
        )


class CharucoCalibrator:
    def __init__(self, board):
        self.board = board
        self.all_charuco_corners = []
        self.all_charuco_ids = []
        self.image_size = None

    def add_frame(self, image: np.ndarray, charuco_corners, charuco_ids) -> bool:
        if image is None:
            return False

        if charuco_corners is None or charuco_ids is None:
            return False

        if len(charuco_ids) < 4:
            return False

        h, w = image.shape[:2]
        if self.image_size is None:
            self.image_size = (w, h)

        self.all_charuco_corners.append(charuco_corners)
        self.all_charuco_ids.append(charuco_ids)
        return True

    def calibrate(self):
        if self.image_size is None:
            raise RuntimeError("No valid calibration frames added.")

        if len(self.all_charuco_corners) < 5:
            raise RuntimeError("Need more calibration frames.")

        all_obj_points = []
        all_img_points = []

        chessboard_corners = self.board.getChessboardCorners()

        for corners, ids in zip(self.all_charuco_corners, self.all_charuco_ids):
            if ids is None or corners is None:
                continue

            obj = chessboard_corners[ids.flatten()].reshape(-1, 1, 3).astype(np.float32)
            img = corners.reshape(-1, 1, 2).astype(np.float32)

            if len(obj) < 4:
                continue

            all_obj_points.append(obj)
            all_img_points.append(img)

        if len(all_obj_points) < 5:
            raise RuntimeError("Not enough valid frames after filtering.")

        retval, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
            objectPoints=all_obj_points,
            imagePoints=all_img_points,
            imageSize=self.image_size,
            cameraMatrix=None,
            distCoeffs=None,
        )

        return retval, camera_matrix, dist_coeffs, rvecs, tvecs


def put_label(img: np.ndarray, text: str) -> np.ndarray:
    out = img.copy()
    cv2.rectangle(out, (10, 10), (1050, 55), (255, 255, 255), -1)
    cv2.putText(
        out,
        text,
        (20, 42),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    return out


def create_partial_view(
    board_img: np.ndarray,
    canvas_size=(1200, 900),
    mode: str = "left_cut",
) -> np.ndarray:
    canvas_w, canvas_h = canvas_size
    canvas = np.full((canvas_h, canvas_w, 3), 255, dtype=np.uint8)

    board_bgr = cv2.cvtColor(board_img, cv2.COLOR_GRAY2BGR)
    h, w = board_img.shape[:2]

    src_points = np.array(
        [
            [0, 0],
            [w - 1, 0],
            [w - 1, h - 1],
            [0, h - 1],
        ],
        dtype=np.float32,
    )

    if mode == "left_cut":
        dst_points = np.array(
            [
                [-180, 100],
                [850, 20],
                [1150, 760],
                [50, 980],
            ],
            dtype=np.float32,
        )
    elif mode == "top_cut":
        dst_points = np.array(
            [
                [100, -150],
                [980, 120],
                [1080, 950],
                [-120, 780],
            ],
            dtype=np.float32,
        )
    else:
        raise ValueError(f"Unknown mode: {mode}")

    H = cv2.getPerspectiveTransform(src_points, dst_points)
    warped = cv2.warpPerspective(board_bgr, H, (canvas_w, canvas_h))

    mask = np.full((h, w), 255, dtype=np.uint8)
    warped_mask = cv2.warpPerspective(mask, H, (canvas_w, canvas_h))
    canvas[warped_mask > 0] = warped[warped_mask > 0]

    return canvas


def print_detection_stats(title: str, result: DetectionResult) -> None:
    marker_count = 0 if result.marker_ids is None else len(result.marker_ids)
    charuco_count = 0 if result.charuco_ids is None else len(result.charuco_ids)
    has_pose = result.rvec is not None and result.tvec is not None

    print(title)
    print(f"  selected mode    : {result.mode}")
    print(f"  markers detected : {marker_count}")
    print(f"  charuco corners  : {charuco_count}")
    print(f"  pose estimated   : {has_pose}")


def run_fake_calibration_smoke_test(
    auto_detector: AutoCharucoBoardDetector,
    board_img: np.ndarray,
) -> None:
    print("\n" + "=" * 80)
    print("FAKE CALIBRATION SMOKE TEST")
    print("=" * 80)

    calibrator = CharucoCalibrator(auto_detector.normal.board)

    fake_views = [
        cv2.cvtColor(board_img, cv2.COLOR_GRAY2BGR),
        create_partial_view(board_img, canvas_size=(1200, 900), mode="left_cut"),
        create_partial_view(board_img, canvas_size=(1200, 900), mode="top_cut"),
    ]

    for angle in [5, -8, 12]:
        base = cv2.cvtColor(board_img, cv2.COLOR_GRAY2BGR)
        h, w = base.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        rotated = cv2.warpAffine(base, M, (w, h), borderValue=(255, 255, 255))
        fake_views.append(rotated)

    added = 0
    for idx, img in enumerate(fake_views):
        result = auto_detector.detect(img)
        ok = calibrator.add_frame(img, result.charuco_corners, result.charuco_ids)
        corners = 0 if result.charuco_ids is None else len(result.charuco_ids)

        print(f"view {idx:02d}: mode={result.mode}, corners={corners}, added={ok}")
        if ok:
            added += 1

    print(f"\nTotal frames added to calibrator: {added}")

    if added < 5:
        print("Not enough valid frames for calibration.")
        return

    retval, camera_matrix, dist_coeffs, rvecs, tvecs = calibrator.calibrate()

    print("\nCalibration finished")
    print(f"Reprojection error: {retval}")
    print("Camera intrinsic matrix:")
    print(camera_matrix)
    print("Distortion coefficients:")
    print(dist_coeffs.ravel())


def run_real_image_test(
    image_path: str,
    auto_detector: AutoCharucoBoardDetector,
    output_dir: Path,
) -> None:
    print("\n" + "=" * 80)
    print("REAL IMAGE TEST")
    print("=" * 80)
    print(f"Image path: {image_path}")

    image = cv2.imread(image_path)
    if image is None:
        print("Failed to load real image.")
        return

    result = auto_detector.detect(image)
    print_detection_stats("Real image", result)

    if result.charuco_ids is not None:
        print("  charuco ids      :", result.charuco_ids.flatten().tolist())

    out_path = output_dir / "real_image_detected.png"
    cv2.imwrite(str(out_path), result.vis)
    print(f"Saved detected real image to: {out_path.resolve()}")

    cv2.imshow(
        "Real Image - Input",
        put_label(image, "Real image input"),
    )
    cv2.imshow(
        "Real Image - Detection",
        put_label(result.vis, f"Real image auto mode: {result.mode} + axes"),
    )


def run_example(
    example_name: str,
    board_img: np.ndarray,
    auto_detector: AutoCharucoBoardDetector,
    output_dir: Path,
) -> None:
    print("\n" + "=" * 80)
    print(f"EXAMPLE: {example_name}")
    print("=" * 80)

    full_input = cv2.cvtColor(board_img, cv2.COLOR_GRAY2BGR)
    partial_input = create_partial_view(board_img, mode="left_cut")

    full_result = auto_detector.detect(full_input)
    partial_result = auto_detector.detect(partial_input)

    print_detection_stats("Full image", full_result)
    print_detection_stats("Partial image", partial_result)

    prefix = example_name.lower().replace(" ", "_")

    cv2.imwrite(str(output_dir / f"{prefix}_board.png"), board_img)
    cv2.imwrite(str(output_dir / f"{prefix}_full_input.png"), full_input)
    cv2.imwrite(str(output_dir / f"{prefix}_partial_input.png"), partial_input)
    cv2.imwrite(str(output_dir / f"{prefix}_full_detected.png"), full_result.vis)
    cv2.imwrite(str(output_dir / f"{prefix}_partial_detected.png"), partial_result.vis)

    cv2.imshow(
        f"{example_name} - Board",
        put_label(cv2.cvtColor(board_img, cv2.COLOR_GRAY2BGR), f"{example_name} board"),
    )
    cv2.imshow(
        f"{example_name} - Full Input",
        put_label(full_input, f"{example_name} full input"),
    )
    cv2.imshow(
        f"{example_name} - Full Detection",
        put_label(full_result.vis, f"{example_name} full auto mode: {full_result.mode} + axes"),
    )
    cv2.imshow(
        f"{example_name} - Partial Input",
        put_label(partial_input, f"{example_name} partial input"),
    )
    cv2.imshow(
        f"{example_name} - Partial Detection",
        put_label(partial_result.vis, f"{example_name} partial auto mode: {partial_result.mode} + axes"),
    )


if __name__ == "__main__":
    output_dir = Path("charuco_output")
    output_dir.mkdir(exist_ok=True)
    #
    squares_x = 11
    squares_y = 8
    square_length = 0.015
    marker_length = 0.011
    dictionary_id = cv2.aruco.DICT_5X5_250
    #
    auto_detector = AutoCharucoBoardDetector(
        squares_x=squares_x,
        squares_y=squares_y,
        square_length=square_length,
        marker_length=marker_length,
        dictionary_id=dictionary_id,
    )
    #
    # new_board_generator = CharucoBoardDetector(
    #     squares_x=squares_x,
    #     squares_y=squares_y,
    #     square_length=square_length,
    #     marker_length=marker_length,
    #     dictionary_id=dictionary_id,
    #     legacy_pattern=False,
    # )
    #
    # old_board_generator = CharucoBoardDetector(
    #     squares_x=squares_x,
    #     squares_y=squares_y,
    #     square_length=square_length,
    #     marker_length=marker_length,
    #     dictionary_id=dictionary_id,
    #     legacy_pattern=True,
    # )
    #
    # new_board_img = new_board_generator.generate_board_image(out_size=(900, 1100), margin_size=20)
    # old_board_img = old_board_generator.generate_board_image(out_size=(900, 1100), margin_size=20)
    #
    # run_example(
    #     example_name="NEW Convention",
    #     board_img=new_board_img,
    #     auto_detector=auto_detector,
    #     output_dir=output_dir,
    # )
    #
    # run_example(
    #     example_name="OLD Convention",
    #     board_img=old_board_img,
    #     auto_detector=auto_detector,
    #     output_dir=output_dir,
    # )
    #
    # run_fake_calibration_smoke_test(
    #     auto_detector=auto_detector,
    #     board_img=new_board_img,
    # )

    real_image_path = r"D:\GitHub\robot_app_platform\scripts\20260403_062514.jpg"
    # resize to 1280 720 for faster processing and better visualization on smaller screens
    real_image = cv2.imread(real_image_path)
    if real_image is not None:
        real_image = cv2.resize(real_image, (1280, 720), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(output_dir / "real_image_resized.png"), real_image)
    resized_path = output_dir / "real_image_resized.png"
    run_real_image_test(
        image_path=resized_path,
        auto_detector=auto_detector,
        output_dir=output_dir,
    )

    print("\nSaved outputs to:", output_dir.resolve())
    print("Note: axis drawing uses a demo camera matrix for visualization.")
    print("For real pose accuracy, replace it with your calibrated camera intrinsics.")
    print("Press any key to close all windows.")
    cv2.waitKey(0)
    cv2.destroyAllWindows()