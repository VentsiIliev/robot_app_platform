import math
import argparse
from typing import Iterable

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def cumulative_arc_length(points: np.ndarray) -> np.ndarray:
    if len(points) < 2:
        return np.array([0.0])
    diffs = np.diff(points[:, :2], axis=0)
    seg = np.linalg.norm(diffs, axis=1)
    return np.concatenate([[0.0], np.cumsum(seg)])


def resample_linear(points: np.ndarray, spacing: float) -> np.ndarray:
    if len(points) < 2:
        return points.copy()

    arc = cumulative_arc_length(points)
    total = float(arc[-1])
    if total <= 1e-9:
        return points.copy()

    sample_s = np.arange(0.0, total, max(spacing, 1e-6))
    if sample_s[-1] != total:
        sample_s = np.append(sample_s, total)

    out = np.column_stack([
        np.interp(sample_s, arc, points[:, 0]),
        np.interp(sample_s, arc, points[:, 1]),
    ])
    return out


def resample_spline(points: np.ndarray, spacing: float, smoothing: float, degree: int = 3) -> np.ndarray:
    if len(points) < max(2, degree + 1):
        return resample_linear(points, spacing)

    # 1. Изчисляване на дъгата
    arc = cumulative_arc_length(points)
    total_length = arc[-1]

    # Премахване на дублиращи се точки (критично за сплайни)
    _, unique_indices = np.unique(arc, return_index=True)
    points = points[unique_indices]
    arc = arc[unique_indices]

    from scipy.interpolate import splprep, splev

    try:
        # 2. splprep е по-подходящ за пътища (парамитрично изглаждане)
        # s=smoothing контролира колко "стриктно" да минава през пикселите
        tck, u = splprep([points[:, 0], points[:, 1]], s=smoothing, k=degree)

        # 3. Генериране на равномерно разпределени точки по дължината u [0, 1]
        # За да поддържаме constant velocity, броят точки трябва да зависи от дължината
        num_samples = int(total_length / spacing) + 1
        u_new = np.linspace(0, 1, num_samples)

        new_points = splev(u_new, tck)
        out = np.column_stack(new_points)

        # Гарантираме точно начало и край
        out[0] = points[0]
        out[-1] = points[-1]
        return out
    except Exception as e:
        print(f"Spline error: {e}, falling back to linear")
        return resample_linear(points, spacing)


def plot_paths(original: np.ndarray, interpolated: np.ndarray, out_path: str, title: str) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    ax1.set_title(title)
    ax1.plot(original[:, 0], original[:, 1], 'o-', label='original')
    ax1.plot(interpolated[:, 0], interpolated[:, 1], '.-', label='interpolated')
    ax1.axis('equal')
    ax1.grid(True)
    ax1.legend()
    ax1.set_xlabel('X')
    ax1.set_ylabel('Y')

    ax2.set_title('Point count / order')
    ax2.plot(np.arange(len(original)), original[:, 0], 'o-', label='orig x')
    ax2.plot(np.linspace(0, len(original) - 1, len(interpolated)), interpolated[:, 0], '.-', label='interp x')
    ax2.grid(True)
    ax2.legend()
    ax2.set_xlabel('Point index')
    ax2.set_ylabel('X')

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def make_rectangle() -> np.ndarray:
    return np.array([
        [0, 0],
        [200, 0],
        [200, 100],
        [0, 100],
        [0, 0],
    ], dtype=float)


def make_triangle() -> np.ndarray:
    h = 150 * math.sqrt(3) / 2
    return np.array([
        [0, 0],
        [150, 0],
        [75, h],
        [0, 0],
    ], dtype=float)


def make_circle(n: int = 12, r: float = 80) -> np.ndarray:
    pts = []
    for i in range(n + 1):
        a = 2 * math.pi * (i % n) / n
        pts.append([r * math.cos(a), r * math.sin(a)])
    return np.array(pts, dtype=float)


def make_custom() -> np.ndarray:
    return np.array([
        [0, 0],
        [80, 10],
        [140, 90],
        [220, 70],
        [260, 10],
        [320, 0],
    ], dtype=float)


def parse_points(text: str) -> np.ndarray:
    pairs = []
    for chunk in text.split(';'):
        chunk = chunk.strip()
        if not chunk:
            continue
        x_str, y_str = chunk.split(',')
        pairs.append([float(x_str), float(y_str)])
    return np.array(pairs, dtype=float)


def get_points(shape: str, points_text: str | None) -> np.ndarray:
    if points_text:
        return parse_points(points_text)
    if shape == 'rectangle':
        return make_rectangle()
    if shape == 'triangle':
        return make_triangle()
    if shape == 'circle':
        return make_circle()
    return make_custom()


def main() -> None:
    parser = argparse.ArgumentParser(description='Simple shape interpolation tester')
    parser.add_argument('--shape', choices=['custom', 'rectangle', 'triangle', 'circle'], default='custom')
    parser.add_argument('--points', help='Custom points as x,y;x,y;x,y')
    parser.add_argument('--method', choices=['linear', 'spline'], default='spline')
    parser.add_argument('--spacing', type=float, default=5.0)
    parser.add_argument('--smoothing', type=float, default=0.2)
    parser.add_argument('--degree', type=int, default=3)
    parser.add_argument('--output', default='simple_interpolation.png')
    args = parser.parse_args()

    original = get_points(args.shape, args.points)
    if args.method == 'linear':
        interpolated = resample_linear(original, args.spacing)
    else:
        interpolated = resample_spline(original, args.spacing, args.smoothing, args.degree)

    plot_paths(
        original,
        interpolated,
        args.output,
        title=f'{args.method} interpolation | spacing={args.spacing}, smoothing={args.smoothing}',
    )

    print('Done')
    print(f'original points     : {len(original)}')
    print(f'interpolated points : {len(interpolated)}')
    print(f'output plot         : {args.output}')
    print('source points:')
    print(original)


if __name__ == '__main__':
    main()
