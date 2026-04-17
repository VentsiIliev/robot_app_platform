
from __future__ import annotations

import os
import sys
import time
import traceback

import cv2
import numpy as np

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QSpinBox, QTabWidget, QTextEdit, QVBoxLayout, QWidget
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from src.engine.robot.path_interpolation.new_interpolation.interpolation_pipeline import (
    ContourPathPipeline,
    InterpolationConfig,
    PipelineResult,
    PreprocessConfig,
    RuckigConfig,
    contour_area_xy,
    normalize_contours,
    select_contour,
)


# ---------------------------------------------------------------------
# Project vision bootstrap
# ---------------------------------------------------------------------

def try_build_vision_service(project_root: str | None = None, active_area: str | None = None):
    search_roots = []
    if project_root:
        search_roots.append(project_root)
    search_roots.extend([os.getcwd(), os.path.dirname(os.getcwd())])

    for root in search_roots:
        if not root:
            continue
        candidate = os.path.join(root, "src")
        if os.path.isdir(candidate) and root not in sys.path:
            sys.path.insert(0, root)

    from src.engine.common_settings_ids import CommonSettingsID
    from src.engine.core.message_broker import MessageBroker
    from src.engine.repositories.settings_service_factory import build_from_specs
    from src.engine.vision.implementation.VisionSystem.VisionSystem import VisionSystem
    from src.engine.vision.implementation.VisionSystem.core.service.internal_service import Service
    from src.engine.vision.vision_service import VisionService
    from src.engine.work_areas.work_area_service import WorkAreaService
    from src.robot_systems.glue.glue_robot_system import GlueRobotSystem

    settings_service = build_from_specs(
        GlueRobotSystem.settings_specs,
        GlueRobotSystem.metadata.settings_root,
        GlueRobotSystem,
    )
    work_area_service = WorkAreaService(
        settings_service=settings_service,
        definitions=GlueRobotSystem.work_areas,
        default_active_area_id="spray",
    )
    if active_area is not None:
        work_area_service.set_active_area_id(active_area)

    settings_repo = settings_service.get_repo(CommonSettingsID.VISION_CAMERA_SETTINGS)
    data_storage_path = GlueRobotSystem.storage_path("settings", "vision", "data")
    os.makedirs(data_storage_path, exist_ok=True)

    internal_service = Service(
        data_storage_path=data_storage_path,
        settings_file_path=settings_repo.file_path,
    )
    vision_system = VisionSystem(
        storage_path=data_storage_path,
        messaging_service=MessageBroker(),
        service=internal_service,
        work_area_service=work_area_service,
    )
    return VisionService(vision_system, work_area_service=work_area_service)


def parse_points(text: str) -> np.ndarray:
    pts = []
    for raw in text.strip().splitlines():
        line = raw.strip().replace(";", ",")
        if not line:
            continue
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) < 2:
            continue
        pts.append([float(parts[0]), float(parts[1])])
    if len(pts) < 2:
        raise ValueError("Need at least 2 valid points.")
    return np.asarray(pts, dtype=float)


DEFAULT_FIGURE8 = """100, 100
140, 110
170, 140
180, 180
170, 220
140, 250
100, 260
60, 250
30, 220
20, 180
30, 140
60, 110
100, 100
140, 90
170, 60
180, 20
170, -20
140, -50
100, -60
60, -50
30, -20
20, 20
30, 60
60, 90
100, 100"""


def make_shape(name: str) -> np.ndarray:
    if name == "rectangle":
        return np.array([[0, 0], [200, 0], [200, 100], [0, 100], [0, 0]], dtype=float)
    if name == "triangle":
        return np.array([[0, 0], [150, 0], [75, 130], [0, 0]], dtype=float)
    if name == "l_shape":
        return np.array([[0, 0], [0, 180], [40, 180], [40, 80], [150, 80], [150, 0]], dtype=float)
    if name == "circle_poly":
        ang = np.linspace(0, 2 * np.pi, 16, endpoint=False)
        pts = np.c_[80 * np.cos(ang), 80 * np.sin(ang)]
        return np.vstack([pts, pts[:1]])
    if name == "figure8":
        return parse_points(DEFAULT_FIGURE8)
    raise ValueError(f"Unknown shape: {name}")


def draw_contours_on_frame(frame: np.ndarray, contours: list[np.ndarray], selected_index: int | None) -> np.ndarray:
    if frame is None or frame.size == 0:
        return np.zeros((480, 640, 3), dtype=np.uint8)
    if frame.ndim == 2:
        display = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    else:
        display = frame.copy()

    for i, contour in enumerate(contours):
        pts = contour.astype(np.int32).reshape(-1, 1, 2)
        color = (0, 200, 0) if i != selected_index else (0, 0, 255)
        thickness = 1 if i != selected_index else 2
        cv2.polylines(display, [pts], isClosed=True, color=color, thickness=thickness, lineType=cv2.LINE_AA)
        if len(contour):
            x, y = contour[0].astype(int)
            cv2.putText(display, str(i), (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
    return display


def frame_to_pixmap(frame: np.ndarray, target_width: int = 520) -> QPixmap:
    if frame.ndim == 2:
        rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
    else:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    image = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
    pixmap = QPixmap.fromImage(image)
    return pixmap.scaledToWidth(target_width, Qt.TransformationMode.SmoothTransformation)


class MplCanvas(FigureCanvas):
    def __init__(self, figsize=(11, 8)):
        self.fig = Figure(figsize=figsize)
        super().__init__(self.fig)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vision Contour Interpolation Lab")
        self.resize(1650, 1050)

        self.vision = None
        self.current_frame = None
        self.current_contours: list[np.ndarray] = []
        self.selected_raw_points: np.ndarray | None = None

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(120)
        self.poll_timer.timeout.connect(self.poll_vision)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        left = QWidget()
        left.setMaximumWidth(450)
        left_layout = QVBoxLayout(left)
        form = QFormLayout()
        left_layout.addLayout(form)

        self.source_combo = QComboBox()
        self.source_combo.addItems(["demo shape", "live contours"])
        form.addRow("Source", self.source_combo)

        self.shape_combo = QComboBox()
        self.shape_combo.addItems(["figure8", "rectangle", "triangle", "l_shape", "circle_poly", "custom"])
        form.addRow("Demo shape", self.shape_combo)

        self.project_root_text = QTextEdit()
        self.project_root_text.setMaximumHeight(50)
        self.project_root_text.setPlainText(os.getcwd())
        form.addRow("Project root", self.project_root_text)

        self.work_area_text = QTextEdit()
        self.work_area_text.setMaximumHeight(38)
        self.work_area_text.setPlainText("")
        form.addRow("Work area id", self.work_area_text)

        vision_row = QHBoxLayout()
        self.start_vision_btn = QPushButton("Start vision")
        self.stop_vision_btn = QPushButton("Stop vision")
        vision_row.addWidget(self.start_vision_btn)
        vision_row.addWidget(self.stop_vision_btn)
        left_layout.addLayout(vision_row)

        self.contour_mode_combo = QComboBox()
        self.contour_mode_combo.addItems(["largest area", "index"])
        form.addRow("Contour selection", self.contour_mode_combo)

        self.contour_index_spin = QSpinBox()
        self.contour_index_spin.setRange(0, 10000)
        form.addRow("Contour index", self.contour_index_spin)

        self.capture_btn = QPushButton("Use selected contour")
        left_layout.addWidget(self.capture_btn)

        self.method_combo = QComboBox()
        self.method_combo.addItems(["linear", "pchip"])
        form.addRow("Method", self.method_combo)

        self.spacing_spin = QDoubleSpinBox()
        self.spacing_spin.setRange(0.5, 1000.0)
        self.spacing_spin.setValue(10.0)
        self.spacing_spin.setDecimals(2)
        form.addRow("Output spacing", self.spacing_spin)

        self.pre_spacing_spin = QDoubleSpinBox()
        self.pre_spacing_spin.setRange(0.0, 100.0)
        self.pre_spacing_spin.setValue(1.0)
        self.pre_spacing_spin.setDecimals(2)
        form.addRow("Min input spacing", self.pre_spacing_spin)

        self.close_tol_spin = QDoubleSpinBox()
        self.close_tol_spin.setRange(0.0, 1000.0)
        self.close_tol_spin.setValue(5.0)
        self.close_tol_spin.setDecimals(2)
        form.addRow("Close tolerance", self.close_tol_spin)

        self.use_approx_check = QCheckBox("Use approxPolyDP")
        left_layout.addWidget(self.use_approx_check)

        self.approx_epsilon_spin = QDoubleSpinBox()
        self.approx_epsilon_spin.setRange(0.0, 1.0)
        self.approx_epsilon_spin.setDecimals(4)
        self.approx_epsilon_spin.setSingleStep(0.001)
        self.approx_epsilon_spin.setValue(0.01)
        form.addRow("Approx epsilon factor", self.approx_epsilon_spin)

        self.noise_combo = QComboBox()
        self.noise_combo.addItems(["none", "moving_average", "savgol"])
        form.addRow("Noise filter", self.noise_combo)

        self.noise_strength_spin = QDoubleSpinBox()
        self.noise_strength_spin.setRange(0.0, 21.0)
        self.noise_strength_spin.setValue(5.0)
        self.noise_strength_spin.setDecimals(1)
        form.addRow("Filter strength", self.noise_strength_spin)



        self.ruckig_check = QCheckBox("Apply Ruckig after interpolation")
        left_layout.addWidget(self.ruckig_check)

        rform = QFormLayout()
        left_layout.addLayout(rform)

        self.ruckig_dt_spin = QDoubleSpinBox()
        self.ruckig_dt_spin.setRange(0.0001, 1.0)
        self.ruckig_dt_spin.setDecimals(4)
        self.ruckig_dt_spin.setValue(0.01)
        rform.addRow("Ruckig dt [s]", self.ruckig_dt_spin)

        self.ruckig_vel_spin = QDoubleSpinBox()
        self.ruckig_vel_spin.setRange(0.001, 10000.0)
        self.ruckig_vel_spin.setDecimals(3)
        self.ruckig_vel_spin.setValue(200.0)
        rform.addRow("Max velocity", self.ruckig_vel_spin)

        self.ruckig_acc_spin = QDoubleSpinBox()
        self.ruckig_acc_spin.setRange(0.001, 100000.0)
        self.ruckig_acc_spin.setDecimals(3)
        self.ruckig_acc_spin.setValue(500.0)
        rform.addRow("Max acceleration", self.ruckig_acc_spin)

        self.ruckig_jerk_spin = QDoubleSpinBox()
        self.ruckig_jerk_spin.setRange(0.001, 1000000.0)
        self.ruckig_jerk_spin.setDecimals(3)
        self.ruckig_jerk_spin.setValue(2000.0)
        rform.addRow("Max jerk", self.ruckig_jerk_spin)

        left_layout.addWidget(QLabel("Custom points (x, y per line):"))
        self.points_text = QTextEdit()
        self.points_text.setPlainText(DEFAULT_FIGURE8)
        left_layout.addWidget(self.points_text, 1)

        button_row = QHBoxLayout()
        self.update_btn = QPushButton("Update plots")
        self.save_btn = QPushButton("Save current tab")
        button_row.addWidget(self.update_btn)
        button_row.addWidget(self.save_btn)
        left_layout.addLayout(button_row)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        left_layout.addWidget(self.status)

        root.addWidget(left)

        self.tabs = QTabWidget()
        self.camera_tab = QWidget()
        cam_layout = QVBoxLayout(self.camera_tab)
        self.camera_label = QLabel("Vision preview")
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_label.setMinimumSize(640, 480)
        cam_layout.addWidget(self.camera_label)

        self.path_canvas = MplCanvas(figsize=(10, 8))
        self.profile_canvas = MplCanvas(figsize=(14, 10))
        self.tabs.addTab(self.camera_tab, "Vision")
        self.tabs.addTab(self.path_canvas, "Path")
        self.tabs.addTab(self.profile_canvas, "Axis profiles")
        root.addWidget(self.tabs, 1)

        self.start_vision_btn.clicked.connect(self.start_vision)
        self.stop_vision_btn.clicked.connect(self.stop_vision)
        self.capture_btn.clicked.connect(self.capture_selected_contour)
        self.update_btn.clicked.connect(self.recompute)
        self.save_btn.clicked.connect(self.save_current_tab)
        self.source_combo.currentTextChanged.connect(self.recompute)
        self.shape_combo.currentTextChanged.connect(self.on_shape_changed)
        self.contour_mode_combo.currentTextChanged.connect(self.refresh_camera_preview)
        self.contour_index_spin.valueChanged.connect(self.refresh_camera_preview)

        self.on_shape_changed(self.shape_combo.currentText())

    def build_pipeline(self) -> ContourPathPipeline:
        return ContourPathPipeline(
            preprocess=PreprocessConfig(
                close_tol=float(self.close_tol_spin.value()),
                min_spacing=float(self.pre_spacing_spin.value()),
                use_approx_poly_dp=self.use_approx_check.isChecked(),
                approx_epsilon_factor=float(self.approx_epsilon_spin.value()),
                noise_method=self.noise_combo.currentText(),
                noise_strength=float(self.noise_strength_spin.value()),
            ),
            interpolation=InterpolationConfig(
                method=self.method_combo.currentText(),
                output_spacing=float(self.spacing_spin.value()),

            ),
            ruckig=RuckigConfig(
                enabled=self.ruckig_check.isChecked(),
                dt=float(self.ruckig_dt_spin.value()),
                max_velocity=float(self.ruckig_vel_spin.value()),
                max_acceleration=float(self.ruckig_acc_spin.value()),
                max_jerk=float(self.ruckig_jerk_spin.value()),
            ),
        )

    def on_shape_changed(self, shape: str):
        if shape == "figure8":
            self.points_text.setPlainText(DEFAULT_FIGURE8)
        if self.source_combo.currentText() == "demo shape":
            self.recompute()

    def get_selected_contour_index(self) -> int | None:
        if not self.current_contours:
            return None
        if self.contour_mode_combo.currentText() == "largest area":
            return int(np.argmax([contour_area_xy(c) for c in self.current_contours]))
        idx = int(self.contour_index_spin.value())
        return idx if 0 <= idx < len(self.current_contours) else None

    def start_vision(self):
        try:
            if self.vision is not None:
                self.status.setText("Vision already running.")
                return
            project_root = self.project_root_text.toPlainText().strip() or None
            area = self.work_area_text.toPlainText().strip() or None
            self.vision = try_build_vision_service(project_root=project_root, active_area=area)
            self.vision.start()
            time.sleep(0.5)
            self.poll_timer.start()
            self.status.setText("Vision started. Waiting for frames and contours...")
        except Exception as e:
            self.vision = None
            self.poll_timer.stop()
            self.status.setText(f"Could not start vision: {e}\n{traceback.format_exc(limit=1)}")

    def stop_vision(self):
        self.poll_timer.stop()
        try:
            if self.vision is not None:
                self.vision.stop()
        except Exception:
            pass
        self.vision = None
        self.status.setText("Vision stopped.")

    def poll_vision(self):
        if self.vision is None:
            return
        try:
            frame = self.vision.get_latest_frame() if hasattr(self.vision, "get_latest_frame") else None
            contours = normalize_contours(self.vision.get_latest_contours()) if hasattr(self.vision, "get_latest_contours") else []
            self.current_frame = frame
            self.current_contours = contours
            self.refresh_camera_preview()
        except Exception as e:
            self.status.setText(f"Vision polling error: {e}")

    def refresh_camera_preview(self):
        display = draw_contours_on_frame(self.current_frame, self.current_contours, self.get_selected_contour_index())
        self.camera_label.setPixmap(frame_to_pixmap(display, target_width=900))

    def capture_selected_contour(self):
        idx = self.get_selected_contour_index()
        if idx is None:
            self.status.setText("No contour available.")
            return
        pts = self.current_contours[idx].copy()
        if len(pts) > 1 and not np.allclose(pts[0], pts[-1]):
            pts = np.vstack([pts, pts[0]])
        self.selected_raw_points = pts
        self.source_combo.setCurrentText("live contours")
        self.recompute()

    def get_raw_points(self) -> np.ndarray:
        source = self.source_combo.currentText()
        if source == "demo shape":
            shape = self.shape_combo.currentText()
            if shape == "custom":
                return parse_points(self.points_text.toPlainText())
            return make_shape(shape)
        if self.selected_raw_points is not None and len(self.selected_raw_points) >= 2:
            return self.selected_raw_points
        idx = self.get_selected_contour_index()
        if idx is not None:
            return select_contour(
                self.current_contours,
                mode="largest_area" if self.contour_mode_combo.currentText() == "largest area" else "index",
                index=int(self.contour_index_spin.value()),
            )
        raise ValueError("No live contour selected yet.")

    def recompute(self):
        try:
            pipeline = self.build_pipeline()
            result = pipeline.run(self.get_raw_points())
            self.draw_path(result)
            self.draw_profiles(result)
            src = self.source_combo.currentText()
            msg = f"Source: {src} | Raw: {len(result.raw)} pts | Prepared: {len(result.prepared)} pts | Curve: {len(result.curve)} pts | Final: {len(result.sampled)} pts"
            if result.ruckig is not None:
                msg += f" | Ruckig: {len(result.ruckig['points'])} samples"
            self.status.setText(msg)
        except Exception as e:
            self.status.setText(f"Recompute error: {e}")

    def draw_path(self, result: PipelineResult):
        fig = self.path_canvas.fig
        fig.clear()
        ax = fig.add_subplot(111)
        ax.plot(result.raw[:, 0], result.raw[:, 1], 'o--', alpha=0.45, label='raw')
        ax.plot(result.prepared[:, 0], result.prepared[:, 1], 's-', alpha=0.8, label='prepared')
        ax.plot(result.curve[:, 0], result.curve[:, 1], '-', alpha=0.7, label='curve')
        ax.plot(result.sampled[:, 0], result.sampled[:, 1], '.-', alpha=0.9, label='sampled')
        if result.ruckig is not None and len(result.ruckig["points"]) > 0:
            rp = result.ruckig["points"]
            ax.plot(rp[:, 0], rp[:, 1], '-', linewidth=2, alpha=0.95, label='ruckig')
        ax.set_title("Path geometry")
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.grid(True)
        ax.axis("equal")
        ax.legend()
        self.path_canvas.draw()

    def draw_axis_group(self, axes, profiles, axis_name: str, title_prefix: str, limits=None):
        t = profiles["t"]
        pos = profiles["x"] if axis_name == "x" else profiles["y"]
        vel = profiles["vx"] if axis_name == "x" else profiles["vy"]
        acc = profiles["ax"] if axis_name == "x" else profiles["ay"]
        jerk = profiles["jx"] if axis_name == "x" else profiles["jy"]
        axes[0].plot(t, pos, label=f"Position {axis_name.upper()}")
        axes[1].plot(t, vel, label=f"Velocity {axis_name.upper()}")
        axes[2].plot(t, acc, label=f"Acceleration {axis_name.upper()}")
        axes[3].plot(t, jerk, label=f"Jerk {axis_name.upper()}")

        labels = ["Position", "Velocity", "Acceleration", "Jerk"]
        for ax, lab in zip(axes, labels):
            ax.grid(True)
            ax.legend(loc="best")
            ax.set_ylabel(lab)
            if limits and lab.lower() in limits:
                lim = float(limits[lab.lower()])
                ax.axhline(lim, linestyle='--', alpha=0.7)
                ax.axhline(-lim, linestyle='--', alpha=0.7)
        axes[0].set_title(f"{title_prefix} — axis {axis_name.upper()}")
        axes[-1].set_xlabel("t")

    def draw_profiles(self, result: PipelineResult):
        fig = self.profile_canvas.fig
        fig.clear()
        interp_profiles = result.profiles
        ruckig_data = result.ruckig
        if ruckig_data is None:
            gs = fig.add_gridspec(4, 2)
            ix = [fig.add_subplot(gs[i, 0]) for i in range(4)]
            iy = [fig.add_subplot(gs[i, 1]) for i in range(4)]
            self.draw_axis_group(ix, interp_profiles, "x", "Interpolated")
            self.draw_axis_group(iy, interp_profiles, "y", "Interpolated")
        else:
            gs = fig.add_gridspec(4, 4)
            ix = [fig.add_subplot(gs[i, 0]) for i in range(4)]
            iy = [fig.add_subplot(gs[i, 1]) for i in range(4)]
            rx = [fig.add_subplot(gs[i, 2]) for i in range(4)]
            ry = [fig.add_subplot(gs[i, 3]) for i in range(4)]
            self.draw_axis_group(ix, interp_profiles, "x", "Interpolated")
            self.draw_axis_group(iy, interp_profiles, "y", "Interpolated")
            limits = {
                "velocity": self.ruckig_vel_spin.value(),
                "acceleration": self.ruckig_acc_spin.value(),
                "jerk": self.ruckig_jerk_spin.value(),
            }
            self.draw_axis_group(rx, ruckig_data, "x", "Ruckig", limits=limits)
            self.draw_axis_group(ry, ruckig_data, "y", "Ruckig", limits=limits)
        fig.tight_layout()
        self.profile_canvas.draw()

    def save_current_tab(self):
        idx = self.tabs.currentIndex()
        if idx == 0:
            if self.current_frame is None:
                QMessageBox.warning(self, "Nothing to save", "No vision frame available.")
                return
            path, _ = QFileDialog.getSaveFileName(self, "Save vision preview", "vision_preview.png", "PNG Files (*.png)")
            if not path:
                return
            display = draw_contours_on_frame(self.current_frame, self.current_contours, self.get_selected_contour_index())
            cv2.imwrite(path, display)
            QMessageBox.information(self, "Saved", f"Saved to:\n{path}")
            return

        default = "path_plot.png" if idx == 1 else "axis_profiles.png"
        path, _ = QFileDialog.getSaveFileName(self, "Save figure", default, "PNG Files (*.png)")
        if not path:
            return
        canvas = self.path_canvas if idx == 1 else self.profile_canvas
        canvas.fig.savefig(path, dpi=160, bbox_inches="tight")
        QMessageBox.information(self, "Saved", f"Saved to:\n{path}")

    def closeEvent(self, event):
        self.stop_vision()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
