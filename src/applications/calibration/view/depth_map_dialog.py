import numpy as np
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib import colors
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 — registers 3d projection

from src.engine.robot.height_measuring.piecewise_bilinear_height_model import (
    MARKER_LABELS,
    PiecewiseBilinearHeightModel,
)
from src.engine.robot.height_measuring.area_grid_height_model import AreaGridHeightModel


_GRID_RES = 60


class DepthMapDialog(QDialog):
    def __init__(self, depth_map_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Robot Calibration — Surface Depth Map")
        self.setMinimumSize(1100, 560)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._build_ui(depth_map_data)

    def _build_ui(self, data) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(8)

        n_pts = len(data.points)
        marker_model = PiecewiseBilinearHeightModel.from_depth_map(data)
        grid_model = AreaGridHeightModel.from_depth_map(data)
        is_grid = grid_model.is_supported()
        if marker_model.is_supported():
            mode_text = "piecewise triangles"
        elif is_grid:
            mode_text = f"area grid {data.grid_rows}x{data.grid_cols}"
            missing = len(getattr(data, "unavailable_point_labels", []) or [])
            if missing:
                mode_text += f", {missing} unavailable (filled)"
        else:
            mode_text = "scatter / fallback"
        info = QLabel(f"Surface depth map — <b>{n_pts}</b> measured points ({mode_text})")
        info.setStyleSheet("color: #555; font-size: 9pt;")
        layout.addWidget(info)

        fig = Figure(figsize=(13, 5.5), tight_layout=True)
        fig.patch.set_facecolor("#FFFFFF")

        ax3d = fig.add_subplot(121, projection="3d")
        ax2d = fig.add_subplot(122)

        pts = np.array(data.points) if data.points else None
        if pts is not None and len(pts) >= 4:
            if marker_model.is_supported():
                self._populate_piecewise(ax3d, ax2d, marker_model)
            elif grid_model.is_supported():
                self._populate_area_grid(ax3d, ax2d, grid_model)
            else:
                self._populate_3d(ax3d, pts)
                self._populate_2d(ax2d, pts, getattr(data, "point_labels", []))
        else:
            for ax in (ax3d, ax2d):
                ax.text(0.5, 0.5, "Not enough data (need ≥ 4 points)",
                        ha="center", va="center", transform=ax.transAxes,
                        fontsize=11, color="gray")

        canvas = FigureCanvasQTAgg(fig)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(canvas, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    @staticmethod
    def _populate_3d(ax, pts: np.ndarray) -> None:
        from scipy.interpolate import griddata

        x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]

        xi = np.linspace(x.min(), x.max(), _GRID_RES)
        yi = np.linspace(y.min(), y.max(), _GRID_RES)
        XI, YI = np.meshgrid(xi, yi)
        ZI = griddata((x, y), z, (XI, YI), method="cubic")

        surf = ax.plot_surface(
            XI, YI, ZI,
            cmap="viridis",
            linewidth=0,
            antialiased=True,
            alpha=0.90,
        )

        ax.scatter(x, y, z, c="red", s=40, edgecolors="black", zorder=5)

        ax.figure.colorbar(surf, ax=ax, shrink=0.55, pad=0.1, label="Height (mm)")
        ax.set_xlabel("X (mm)", fontweight="bold", fontsize=9)
        ax.set_ylabel("Y (mm)", fontweight="bold", fontsize=9)
        ax.set_zlabel("Height (mm)", fontweight="bold", fontsize=9)
        ax.set_title("3D Surface", fontsize=11, fontweight="bold")

    @staticmethod
    def _populate_2d(ax, pts: np.ndarray, point_labels: list[str] | None = None) -> None:
        x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]

        sc = ax.scatter(x, y, c=z, cmap="viridis", s=80, zorder=3,
                        edgecolors="black", linewidths=0.5)
        ax.figure.colorbar(sc, ax=ax, label="Height (mm)")

        labels = list(point_labels or [])
        for idx, (xi, yi, zi) in enumerate(zip(x, y, z)):
            text = f"{zi:.2f}"
            if idx < len(labels):
                text = f"[{labels[idx]}] {text}"
            ax.annotate(text, (xi, yi),
                        textcoords="offset points", xytext=(5, 5),
                        fontsize=8, color="#222")

        ax.set_xlabel("X (mm)", fontsize=10)
        ax.set_ylabel("Y (mm)", fontsize=10)
        ax.set_title("Top-down view", fontsize=11, fontweight="bold")
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(True, linestyle="--", alpha=0.35)
        ax.set_facecolor("#FAFAFA")

    @staticmethod
    def _populate_piecewise(ax3d, ax2d, model: PiecewiseBilinearHeightModel) -> None:
        point_items = sorted(model.points_by_id().items())
        all_z = np.array([point[2] for _, point in point_items], dtype=float)
        norm = colors.Normalize(vmin=float(all_z.min()), vmax=float(all_z.max()))
        cmap = "viridis"
        triangulation = model.triangulation()
        x = np.array([point[0] for _, point in point_items], dtype=float)
        y = np.array([point[1] for _, point in point_items], dtype=float)
        z = np.array([point[2] for _, point in point_items], dtype=float)

        last_surface = None
        last_mesh = None
        if triangulation is not None:
            last_surface = ax3d.plot_trisurf(
                triangulation,
                z,
                cmap=cmap,
                norm=norm,
                linewidth=0.3,
                edgecolor=(0, 0, 0, 0.15),
                antialiased=True,
                alpha=0.92,
            )
            last_mesh = ax2d.tripcolor(
                triangulation,
                z,
                cmap=cmap,
                norm=norm,
                shading="gouraud",
            )

        ax3d.scatter(x, y, z, c="red", s=40, edgecolors="black", zorder=5)
        if last_surface is not None:
            ax3d.figure.colorbar(last_surface, ax=ax3d, shrink=0.55, pad=0.1, label="Height (mm)")
        ax3d.set_xlabel("X (mm)", fontweight="bold", fontsize=9)
        ax3d.set_ylabel("Y (mm)", fontweight="bold", fontsize=9)
        ax3d.set_zlabel("Height (mm)", fontweight="bold", fontsize=9)
        ax3d.set_title("3D Piecewise Triangle Surface", fontsize=11, fontweight="bold")

        ax2d.scatter(x, y, c=z, cmap=cmap, norm=norm, s=80, zorder=4,
                     edgecolors="black", linewidths=0.5)
        if last_mesh is not None:
            ax2d.figure.colorbar(last_mesh, ax=ax2d, label="Height (mm)")
        for marker_id, (xi, yi, zi) in point_items:
            label = MARKER_LABELS.get(marker_id)
            text = f"[{marker_id}] {zi:.2f}"
            if label:
                text += f"\n{label}"
            ax2d.annotate(
                text,
                (xi, yi),
                textcoords="offset points",
                xytext=(5, 5),
                fontsize=8,
                color="#222",
            )
        ax2d.set_xlabel("X (mm)", fontsize=10)
        ax2d.set_ylabel("Y (mm)", fontsize=10)
        ax2d.set_title("Top-down Piecewise Triangle Surface", fontsize=11, fontweight="bold")
        ax2d.set_aspect("equal", adjustable="datalim")
        ax2d.grid(True, linestyle="--", alpha=0.35)
        ax2d.set_facecolor("#FAFAFA")

    @staticmethod
    def _populate_area_grid(ax3d, ax2d, model: AreaGridHeightModel) -> None:
        point_items = model.point_items()
        status_items = model.point_status_items()
        all_z = np.array([point[2] for _, point in point_items], dtype=float)
        norm = colors.Normalize(vmin=float(all_z.min()), vmax=float(all_z.max()))
        cmap = "viridis"
        triangulation = model.triangulation()
        x = np.array([point[0] for _, point in point_items], dtype=float)
        y = np.array([point[1] for _, point in point_items], dtype=float)
        z = np.array([point[2] for _, point in point_items], dtype=float)

        last_surface = None
        last_mesh = None
        if triangulation is not None:
            last_surface = ax3d.plot_trisurf(
                triangulation,
                z,
                cmap=cmap,
                norm=norm,
                linewidth=0.3,
                edgecolor=(0, 0, 0, 0.15),
                antialiased=True,
                alpha=0.90,
            )
            last_mesh = ax2d.tripcolor(
                triangulation,
                z,
                cmap=cmap,
                norm=norm,
                shading="gouraud",
            )

        ax3d.scatter(x, y, z, c="red", s=40, edgecolors="black", zorder=5)
        if last_surface is not None:
            ax3d.figure.colorbar(last_surface, ax=ax3d, shrink=0.55, pad=0.1, label="Height (mm)")
        ax3d.set_xlabel("X (mm)", fontweight="bold", fontsize=9)
        ax3d.set_ylabel("Y (mm)", fontweight="bold", fontsize=9)
        ax3d.set_zlabel("Height (mm)", fontweight="bold", fontsize=9)
        ax3d.set_title("3D Area Grid Surface", fontsize=11, fontweight="bold")

        ax2d.scatter(x, y, c=z, cmap=cmap, norm=norm, s=80, zorder=4,
                     edgecolors="black", linewidths=0.5)
        if last_mesh is not None:
            ax2d.figure.colorbar(last_mesh, ax=ax2d, label="Height (mm)")
        for label, (xi, yi, zi), status in status_items:
            suffix = ""
            if status != "measured":
                suffix = f"\n{status}"
            ax2d.annotate(
                f"[{label}] {zi:.2f}{suffix}",
                (xi, yi),
                textcoords="offset points",
                xytext=(5, 5),
                fontsize=8,
                color="#222",
            )
        ax2d.set_xlabel("X (mm)", fontsize=10)
        ax2d.set_ylabel("Y (mm)", fontsize=10)
        ax2d.set_title("Top-down Area Grid Surface", fontsize=11, fontweight="bold")
        ax2d.set_aspect("equal", adjustable="datalim")
        ax2d.grid(True, linestyle="--", alpha=0.35)
        ax2d.set_facecolor("#FAFAFA")
