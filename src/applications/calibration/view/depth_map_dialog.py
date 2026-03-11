import numpy as np
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 — registers 3d projection


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
        info = QLabel(f"Surface depth map — <b>{n_pts}</b> measured points")
        info.setStyleSheet("color: #555; font-size: 9pt;")
        layout.addWidget(info)

        fig = Figure(figsize=(13, 5.5), tight_layout=True)
        fig.patch.set_facecolor("#FFFFFF")

        ax3d = fig.add_subplot(121, projection="3d")
        ax2d = fig.add_subplot(122)

        pts = np.array(data.points) if data.points else None
        if pts is not None and len(pts) >= 4:
            self._populate_3d(ax3d, pts)
            self._populate_2d(ax2d, pts)
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
    def _populate_2d(ax, pts: np.ndarray) -> None:
        x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]

        sc = ax.scatter(x, y, c=z, cmap="viridis", s=80, zorder=3,
                        edgecolors="black", linewidths=0.5)
        ax.figure.colorbar(sc, ax=ax, label="Height (mm)")

        for xi, yi, zi in zip(x, y, z):
            ax.annotate(f"{zi:.2f}", (xi, yi),
                        textcoords="offset points", xytext=(5, 5),
                        fontsize=8, color="#222")

        ax.set_xlabel("X (mm)", fontsize=10)
        ax.set_ylabel("Y (mm)", fontsize=10)
        ax.set_title("Top-down view", fontsize=11, fontweight="bold")
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(True, linestyle="--", alpha=0.35)
        ax.set_facecolor("#FAFAFA")
