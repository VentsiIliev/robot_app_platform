from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from src.robot_systems.paint.domain.dxf_path_form_behavior import (
    PaintDxfPathFormBehavior,
)


class TestPaintDxfPathFormBehavior(unittest.TestCase):
    def test_apply_installs_click_action_for_dxf_field(self) -> None:
        form = MagicMock()
        editor_frame = MagicMock()
        behavior = PaintDxfPathFormBehavior(
            prepare_dxf_raw_for_image=MagicMock(),
            dxf_importer=MagicMock(),
        )

        with patch(
            "src.robot_systems.paint.domain.dxf_path_form_behavior.install_line_edit_click_action"
        ) as install:
            behavior.apply(form, editor_frame)

        install.assert_called_once()
        args = install.call_args.args
        self.assertEqual(args[:2], (form, "dxfPath"))
        self.assertTrue(callable(args[2]))
        self.assertEqual(install.call_args.kwargs["placeholder"], "Click to choose DXF")
        self.assertTrue(install.call_args.kwargs["read_only"])

    def test_pick_and_preview_returns_when_dialog_is_cancelled(self) -> None:
        form = MagicMock()
        form.get_data.return_value = {"dxfPath": "/tmp/old.dxf"}
        editor_frame = MagicMock()
        behavior = PaintDxfPathFormBehavior(
            prepare_dxf_raw_for_image=MagicMock(),
            dxf_importer=MagicMock(),
        )

        with patch(
            "src.robot_systems.paint.domain.dxf_path_form_behavior.QFileDialog.getOpenFileName",
            return_value=("", ""),
        ), patch(
            "src.robot_systems.paint.domain.dxf_path_form_behavior.set_form_field_value"
        ) as set_value:
            behavior._pick_and_preview(form, editor_frame)

        behavior._dxf_importer.assert_not_called()
        editor_frame.set_verification_contours.assert_not_called()
        set_value.assert_not_called()

    def test_pick_and_preview_imports_places_aligns_and_updates_form(self) -> None:
        form = MagicMock()
        form.get_data.return_value = {"dxfPath": "/tmp/old.dxf"}
        editor_frame = MagicMock()
        prepared = {"contour": [[[5.0, 6.0]], [[7.0, 8.0]]]}
        aligned = {"contour": [[[15.0, 16.0]], [[17.0, 18.0]]]}
        prepare = MagicMock(return_value=prepared)
        importer = MagicMock(return_value={"raw": True})
        behavior = PaintDxfPathFormBehavior(
            prepare_dxf_raw_for_image=prepare,
            dxf_importer=importer,
        )

        with (
            patch(
                "src.robot_systems.paint.domain.dxf_path_form_behavior.QFileDialog.getOpenFileName",
                return_value=("/tmp/new.dxf", "DXF"),
            ),
            patch.object(behavior, "_resolve_image_size", return_value=(640.0, 480.0)),
            patch.object(behavior, "_get_current_editor_contour", return_value=np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])),
            patch.object(behavior, "_align_raw_workpiece_to_contour", return_value=aligned) as align,
            patch(
                "src.robot_systems.paint.domain.dxf_path_form_behavior.set_form_field_value"
            ) as set_value,
        ):
            behavior._pick_and_preview(form, editor_frame)

        importer.assert_called_once_with("/tmp/new.dxf")
        prepare.assert_called_once_with({"raw": True}, 640.0, 480.0)
        align.assert_called_once()
        np.testing.assert_allclose(
            editor_frame.set_verification_contours.call_args.args[0][0],
            np.array([[15.0, 16.0], [17.0, 18.0]]),
        )
        set_value.assert_called_once_with(form, "dxfPath", "/tmp/new.dxf")

    def test_pick_and_preview_uses_empty_overlay_for_short_contour(self) -> None:
        form = MagicMock()
        form.get_data.side_effect = RuntimeError("bad form")
        editor_frame = MagicMock()
        behavior = PaintDxfPathFormBehavior(
            prepare_dxf_raw_for_image=MagicMock(return_value={"contour": [[[1.0, 2.0]]]}),
            dxf_importer=MagicMock(return_value={"raw": True}),
        )

        with (
            patch(
                "src.robot_systems.paint.domain.dxf_path_form_behavior.QFileDialog.getOpenFileName",
                return_value=("/tmp/new.dxf", "DXF"),
            ),
            patch.object(behavior, "_resolve_image_size", return_value=(100.0, 50.0)),
            patch.object(behavior, "_get_current_editor_contour", return_value=np.empty((0, 2), dtype=np.float64)),
            patch(
                "src.robot_systems.paint.domain.dxf_path_form_behavior.set_form_field_value"
            ),
        ):
            behavior._pick_and_preview(form, editor_frame)

        self.assertEqual(editor_frame.set_verification_contours.call_args.args[0], [])

    def test_resolve_image_size_prefers_editor_image_dimensions(self) -> None:
        image = MagicMock()
        image.width.return_value = 320
        image.height.return_value = 240
        editor_frame = SimpleNamespace(
            contourEditor=SimpleNamespace(
                editor_with_rulers=SimpleNamespace(
                    editor=SimpleNamespace(image=image)
                )
            )
        )

        self.assertEqual(
            PaintDxfPathFormBehavior._resolve_image_size(editor_frame),
            (320.0, 240.0),
        )

    def test_resolve_image_size_falls_back_to_default_on_failure(self) -> None:
        self.assertEqual(
            PaintDxfPathFormBehavior._resolve_image_size(object()),
            (1280.0, 720.0),
        )

    def test_extract_raw_contour_points_handles_empty_and_valid_contours(self) -> None:
        self.assertEqual(
            PaintDxfPathFormBehavior._extract_raw_contour_points({"contour": []}).shape,
            (0, 2),
        )
        points = PaintDxfPathFormBehavior._extract_raw_contour_points(
            {"contour": [[[1, 2]], [[3, 4]]]}
        )
        np.testing.assert_allclose(points, np.array([[1.0, 2.0], [3.0, 4.0]]))

    def test_get_current_editor_contour_handles_main_workpiece_dict_and_invalid_shapes(self) -> None:
        editor_frame = SimpleNamespace(
            contourEditor=SimpleNamespace(
                editor_with_rulers=SimpleNamespace(
                    editor=SimpleNamespace(
                        workpiece_manager=SimpleNamespace(
                            get_contours=lambda: {"Main": [np.array([[[1.0, 2.0]], [[3.0, 4.0]]])]}
                        )
                    )
                )
            )
        )
        contour = PaintDxfPathFormBehavior._get_current_editor_contour(editor_frame)
        np.testing.assert_allclose(contour, np.array([[1.0, 2.0], [3.0, 4.0]]))

        dict_frame = SimpleNamespace(
            contourEditor=SimpleNamespace(
                editor_with_rulers=SimpleNamespace(
                    editor=SimpleNamespace(
                        workpiece_manager=SimpleNamespace(
                            get_contours=lambda: {"Workpiece": {"contours": [np.array([[1.0]])]}}
                        )
                    )
                )
            )
        )
        self.assertEqual(
            PaintDxfPathFormBehavior._get_current_editor_contour(dict_frame).shape,
            (0, 2),
        )

    def test_align_raw_workpiece_to_contour_delegates_to_alignment_module(self) -> None:
        behavior = PaintDxfPathFormBehavior(
            prepare_dxf_raw_for_image=MagicMock(),
            dxf_importer=MagicMock(),
            dxf_alignment_strategy="smooth",
            dxf_max_scale_deviation=0.2,
        )
        raw = {"contour": []}
        contour = np.array([[0.0, 0.0], [1.0, 0.0]])

        with patch(
            "src.robot_systems.paint.processes.paint.align.align_raw_workpiece_to_contour",
            return_value="aligned",
        ) as align:
            result = behavior._align_raw_workpiece_to_contour(raw, contour)

        self.assertEqual(result, "aligned")
        align.assert_called_once_with(
            raw,
            contour,
            strategy="smooth",
            max_scale_deviation=0.2,
        )

    def test_resample_rotate_transform_and_overlap_helpers(self) -> None:
        points = np.array([[0.0, 0.0], [2.0, 0.0], [2.0, 2.0]], dtype=np.float64)
        resampled = PaintDxfPathFormBehavior._resample_closed_path(points, 4)
        self.assertEqual(resampled.shape, (4, 2))

        angle = PaintDxfPathFormBehavior._principal_axis_angle(
            np.array([[0.0, 0.0], [2.0, 0.0], [4.0, 0.0]])
        )
        self.assertAlmostEqual(angle, 0.0, places=6)

        rotated = PaintDxfPathFormBehavior._rotate_points(
            np.array([[1.0, 0.0]], dtype=np.float64),
            np.array([0.0, 0.0], dtype=np.float64),
            np.pi / 2,
        )
        np.testing.assert_allclose(rotated, np.array([[0.0, 1.0]]), atol=1e-6)

        scaled = PaintDxfPathFormBehavior._rotate_and_scale_points(
            np.array([[1.0, 0.0]], dtype=np.float64),
            np.array([0.0, 0.0], dtype=np.float64),
            0.0,
            2.0,
        )
        np.testing.assert_allclose(scaled, np.array([[2.0, 0.0]]))

        transformed = PaintDxfPathFormBehavior._transform_points(
            np.array([[1.0, 0.0]], dtype=np.float64),
            np.array([0.0, 0.0], dtype=np.float64),
            0.0,
            2.0,
            np.array([3.0, 4.0], dtype=np.float64),
        )
        np.testing.assert_allclose(transformed, np.array([[5.0, 4.0]]))

        scale = PaintDxfPathFormBehavior._estimate_uniform_scale(
            np.array([[1.0, 0.0], [0.0, 1.0]]),
            np.array([[2.0, 0.0], [0.0, 2.0]]),
        )
        self.assertAlmostEqual(scale, 2.0, places=6)

        self.assertEqual(
            PaintDxfPathFormBehavior._alignment_error(
                np.array([[0.0, 0.0]]),
                np.array([[3.0, 4.0]]),
            ),
            5.0,
        )

        overlap = PaintDxfPathFormBehavior._mask_overlap_for_pose(
            np.array([[1.0, 0.0]], dtype=np.float64),
            np.array([[0.0, 0.0]], dtype=np.float64),
            np.array([0.0, 0.0], dtype=np.float64),
            0.0,
            1.0,
            np.array([0.0, 0.0], dtype=np.float64),
            overlap_fn=lambda source, target: float(source[0][0] + target[0][0]),
        )
        self.assertEqual(overlap, 1.0)

    def test_refine_alignment_with_mask_overlap_improves_pose(self) -> None:
        source_points = np.array([[0.0, 0.0], [1.0, 0.0]], dtype=np.float64)
        target_points = np.array([[2.0, 0.0], [3.0, 0.0]], dtype=np.float64)
        source_centroid = np.array([0.5, 0.0], dtype=np.float64)

        def overlap_fn(transformed: np.ndarray, _target: np.ndarray) -> float:
            return -abs(np.mean(transformed[:, 0]) - 2.5)

        theta, scale, translation = PaintDxfPathFormBehavior._refine_alignment_with_mask_overlap(
            source_points,
            target_points,
            source_centroid,
            initial_theta=0.0,
            initial_scale=1.0,
            initial_translation=np.array([0.0, 0.0], dtype=np.float64),
            overlap_fn=overlap_fn,
        )

        self.assertAlmostEqual(theta, 0.0, places=6)
        self.assertGreater(scale, 0.0)
        self.assertGreater(translation[0], 0.0)


if __name__ == "__main__":
    unittest.main()
