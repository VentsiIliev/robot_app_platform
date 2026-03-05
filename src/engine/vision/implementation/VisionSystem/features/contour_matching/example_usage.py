#!/usr/bin/env python3
"""
Standalone runner for the contour_matching package.
Demonstrates the three layers of the pipeline:
  1. Geometric matching — find the best workpiece for each detected contour
  2. Difference calculator — compute centroid and rotation offsets
  3. Full pipeline — findMatchingWorkpieces (match + prepare + align)
No robot, no Qt, no platform required.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[7]))

import copy
import numpy as np

from src.engine.vision.implementation.VisionSystem.core.models.contour import Contour
from src.engine.vision.implementation.VisionSystem.features.contour_matching.matching.best_match_result import BestMatchResult
from src.engine.vision.implementation.VisionSystem.features.contour_matching.matching.match_info import MatchInfo
from src.engine.vision.implementation.VisionSystem.features.contour_matching.matching.strategies.geometric_matching_strategy import GeometricMatchingStrategy
from src.engine.vision.implementation.VisionSystem.features.contour_matching.alignment.difference_calculator import _calculateDifferences
from src.engine.vision.implementation.VisionSystem.features.contour_matching.contour_matcher import find_matching_workpieces


# ── Stub workpiece ─────────────────────────────────────────────────────────────

class _StubWorkpiece:
    def __init__(self, contour: np.ndarray, workpiece_id: int, name: str):
        self.workpieceId = workpiece_id
        self.name = name
        self._contour = contour
        self.contour = {"contour": contour, "settings": {}}
        self.sprayPattern = {"Contour": [], "Fill": []}
        self.pickupPoint = None

    def get_main_contour(self) -> np.ndarray:
        return self._contour

    def get_spray_pattern_contours(self) -> list:
        return []

    def get_spray_pattern_fills(self) -> list:
        return []


# ── Synthetic shape builders ───────────────────────────────────────────────────

def _make_circle(cx=128.0, cy=128.0, r=60.0, n=64) -> np.ndarray:
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    pts = np.stack([cx + r * np.cos(angles), cy + r * np.sin(angles)], axis=1)
    pts = np.vstack([pts, pts[0]])  # close
    return pts.reshape(-1, 1, 2).astype(np.float32)


def _make_rect(cx=128.0, cy=128.0, w=100.0, h=70.0) -> np.ndarray:
    pts = np.array([
        [cx - w / 2, cy - h / 2],
        [cx + w / 2, cy - h / 2],
        [cx + w / 2, cy + h / 2],
        [cx - w / 2, cy + h / 2],
    ])
    pts = np.vstack([pts, pts[0]])  # close
    return pts.reshape(-1, 1, 2).astype(np.float32)


def _make_triangle(cx=128.0, cy=128.0, r=70.0) -> np.ndarray:
    angles = [np.pi / 2, np.pi / 2 + 2 * np.pi / 3, np.pi / 2 + 4 * np.pi / 3]
    pts = np.array([[cx + r * np.cos(a), cy - r * np.sin(a)] for a in angles])
    pts = np.vstack([pts, pts[0]])  # close
    return pts.reshape(-1, 1, 2).astype(np.float32)


def _perturb(contour: np.ndarray, tx=5.0, ty=3.0, angle_deg=8.0) -> np.ndarray:
    """Apply rotation and translation to simulate a camera detection offset."""
    c = Contour(contour)
    cx, cy = c.getCentroid()
    c.rotate(angle_deg, (cx, cy))
    c.translate(tx, ty)
    return c.as_cv()


# ── Demo 1 — matching only ─────────────────────────────────────────────────────

def _demo_matching(workpieces: list, strategy: GeometricMatchingStrategy) -> list[MatchInfo]:
    print("=" * 60)
    print("  1. Geometric Matching")
    print("=" * 60)

    detections = {
        "circle  (+15°, +10px)": _perturb(_make_circle(),   tx=10,  ty=-5,  angle_deg=15),
        "rect    (+5°,  -8px)":  _perturb(_make_rect(),     tx=-8,  ty=12,  angle_deg=5),
        "triangle(+20°, +3px)":  _perturb(_make_triangle(), tx=3,   ty=-10, angle_deg=20),
        "unknown (tiny rect)":   _make_rect(cx=64, cy=64, w=15, h=10),
    }

    matched_infos = []
    for label, raw_contour in detections.items():
        contour = Contour(raw_contour)
        result: BestMatchResult = strategy.find_best_match(workpieces, contour)
        if result.is_match:
            print(f"\n  [{label}]")
            print(f"    ✅ matched → {result.workpiece.name} (id={result.workpiece.workpieceId})")
            print(f"       confidence : {result.confidence:.1f}%")
            print(f"       centroid Δ : dx={result.centroid_diff[0]:.1f}, dy={result.centroid_diff[1]:.1f}")
            print(f"       rotation Δ : {result.rotation_diff:.1f}°")
            matched_infos.append(MatchInfo(
                workpiece=result.workpiece,
                new_contour=contour.get(),
                centroid_diff=result.centroid_diff,
                rotation_diff=result.rotation_diff,
                contour_orientation=result.contour_angle,
            ))
        else:
            print(f"\n  [{label}]")
            print(f"    ❌ no match  (best confidence: {result.confidence:.1f}%)")

    return matched_infos


# ── Demo 2 — difference calculator ────────────────────────────────────────────

def _demo_difference_calculator() -> None:
    print("\n" + "=" * 60)
    print("  2. Difference Calculator")
    print("=" * 60)

    cases = [
        ("circle  vs  circle+30°", _make_circle(),   _perturb(_make_circle(),   tx=15, ty=-10, angle_deg=30)),
        ("rect    vs  rect+45°",   _make_rect(),     _perturb(_make_rect(),     tx=5,  ty=5,   angle_deg=45)),
        ("circle  vs  rect",       _make_circle(),   _make_rect()),
    ]

    for label, ref_raw, det_raw in cases:
        ref = Contour(ref_raw)
        det = Contour(det_raw)
        centroid_diff, rotation_diff, contour_angle = _calculateDifferences(ref, det)
        print(f"\n  {label}")
        print(f"    centroid Δ : dx={centroid_diff[0]:.1f}, dy={centroid_diff[1]:.1f}")
        print(f"    rotation Δ : {rotation_diff:.1f}°   |   contour °: {contour_angle:.1f}°")


# ── Demo 3 — full pipeline (match + prepare + align) ──────────────────────────

def _demo_full_pipeline(workpieces: list, debug: bool = False) -> None:
    """
    Exercises findMatchingWorkpieces — the top-level entry point.

    Pipeline inside that function:
      match_workpieces → BestMatchResult per detected contour
      prepare_data_for_alignment → attaches contourObj / sprayContourObjs / sprayFillObjs
      _alignContours → applies rotation + translation (+ optional mask refinement)
                                   and calls update_workpiece_data on each matched workpiece

    Pass debug=True to save similarity and alignment plots to
    contour_matching/debug/output/ for every comparison.
    """
    print("\n" + "=" * 60)
    print(f"  3. Full Pipeline  (match + prepare + align)  [debug={debug}]")
    print("=" * 60)

    # Give each detection a pickup point so alignment can transform it too
    for wp in workpieces:
        wp.pickupPoint = f"{wp.workpieceId * 10}.00,{wp.workpieceId * 10}.00"

    detections = [
        _perturb(_make_circle(),   tx=10, ty=-5,  angle_deg=15),
        _perturb(_make_rect(),     tx=-8, ty=12,  angle_deg=5),
        _perturb(_make_triangle(), tx=3,  ty=-10, angle_deg=20),
        _make_rect(cx=64, cy=64, w=15, h=10),   # unknown — should end up in noMatches
    ]

    final_matches, no_matches, _ = find_matching_workpieces(
        workpieces=workpieces,
        new_contours=detections,
        debug=debug,
    )

    print(f"\n  Matched   : {len(final_matches['workpieces'])}")
    print(f"  Unmatched : {len(no_matches)}")

    for i, wp in enumerate(final_matches["workpieces"]):
        orientation = final_matches["orientations"][i]
        print(f"\n  [{i}] {wp.name}  (id={wp.workpieceId})")
        print(f"      orientation after align : {orientation:.1f}°")
        print(f"      aligned centroid        : {Contour(wp.contour['contour']).getCentroid()}")
        if wp.pickupPoint:
            print(f"      transformed pickup      : {wp.pickupPoint}")


# ── Entry point ────────────────────────────────────────────────────────────────

def run() -> None:
    workpieces = [
        _StubWorkpiece(_make_circle(),   workpiece_id=1, name="Circle"),
        _StubWorkpiece(_make_rect(),     workpiece_id=2, name="Rectangle"),
        _StubWorkpiece(_make_triangle(), workpiece_id=3, name="Triangle"),
    ]
    strategy = GeometricMatchingStrategy(similarity_threshold=0.8,debug=True)

    _demo_matching(workpieces, strategy)
    _demo_difference_calculator()
    _demo_full_pipeline(copy.deepcopy(workpieces))   # deep-copy — pipeline mutates workpieces

    print("\n" + "=" * 60)
    print("  Done.")
    print("=" * 60)


if __name__ == "__main__":
    run()
