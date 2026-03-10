import numpy as np
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


def _reconstruct_polynomial(coefficients, intercept, x_values):
    """Evaluate a polynomial given sklearn-style coefficients (degree N-1 features)."""
    result = np.full_like(x_values, intercept, dtype=float)
    for power, coef in enumerate(coefficients, start=1):
        result += coef * (x_values ** power)
    return result


class DepthMapDialog(QDialog):
    """Shows a chart of the laser height calibration samples + polynomial fit."""

    def __init__(self, calibration_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Height Calibration — Depth Map")
        self.setMinimumSize(720, 500)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._build_ui(calibration_data)

    def _build_ui(self, data) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        # ── Info row ──────────────────────────────────────────────────
        info_row = QHBoxLayout()
        n_pts = len(data.calibration_points)
        degree = data.polynomial_degree
        mse = data.polynomial_mse
        info_label = QLabel(
            f"Samples: <b>{n_pts}</b> &nbsp;|&nbsp; "
            f"Polynomial degree: <b>{degree}</b> &nbsp;|&nbsp; "
            f"MSE: <b>{mse:.4f} mm</b>"
        )
        info_label.setStyleSheet("color: #555; font-size: 9pt;")
        info_row.addWidget(info_label)
        info_row.addStretch()
        layout.addLayout(info_row)

        # ── Matplotlib canvas ─────────────────────────────────────────
        fig = Figure(figsize=(7, 4.2), tight_layout=True)
        ax = fig.add_subplot(111)
        self._populate_chart(ax, data)
        canvas = FigureCanvasQTAgg(fig)
        layout.addWidget(canvas, stretch=1)

        # ── Close button ──────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    @staticmethod
    def _populate_chart(ax, data) -> None:
        if not data.calibration_points:
            ax.text(0.5, 0.5, "No calibration data", ha="center", va="center",
                    transform=ax.transAxes, fontsize=12, color="gray")
            return

        pts = np.array(data.calibration_points)   # shape (N, 2): [height_mm, pixel_delta]
        heights_mm   = pts[:, 0]
        pixel_deltas = pts[:, 1]

        # Raw scatter
        ax.scatter(heights_mm, pixel_deltas,
                   s=18, color="#905BA9", alpha=0.75, zorder=3, label="Measured samples")

        # Polynomial curve (reconstructed from stored coefficients)
        if data.polynomial_coefficients:
            x_smooth = np.linspace(heights_mm.min(), heights_mm.max(), 300)
            y_fit = _reconstruct_polynomial(
                data.polynomial_coefficients, data.polynomial_intercept, x_smooth
            )
            ax.plot(x_smooth, y_fit, color="#4CAF50", linewidth=2,
                    zorder=2, label=f"Polynomial fit (degree {data.polynomial_degree})")

        ax.set_xlabel("Height (mm)", fontsize=10)
        ax.set_ylabel("Laser pixel delta (px)", fontsize=10)
        ax.set_title("Laser Height Calibration Curve", fontsize=11, fontweight="bold")
        ax.legend(fontsize=9)
        ax.grid(True, linestyle="--", alpha=0.4)
        ax.set_facecolor("#FAFAFA")
        ax.figure.patch.set_facecolor("#FFFFFF")
