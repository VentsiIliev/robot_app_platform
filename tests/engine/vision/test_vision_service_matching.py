# """Tests for VisionService.run_matching
#
# Covered scenarios:
#   - returns a 4-tuple (dict, int, list, list) on any input
#   - empty contours list: all counts are zero
#   - empty workpieces list: all contours go to unmatched
#   - fully empty inputs produce empty results
#   - same-shape contour matches its workpiece template
#   - matched contours are np.ndarray items
#   - result dict contains expected keys when a match occurs
#   - result dict is populated on a match
#   - clearly-different shape is not matched
#   - unmatched contours are np.ndarray items
#   - no_match_count always equals len(unmatched_contours)
#   - mixed input: matched + unmatched sum equals total input contours
#   - correct contour routes to matched, wrong contour routes to unmatched
#   - multiple workpieces each match their own detected contour
# """
# import unittest
# from unittest.mock import MagicMock, patch
#
# import numpy as np
#
# from src.engine.vision.vision_service import VisionService
# from src.engine.vision.implementation.VisionSystem.features.shape_matching_training.core.dataset.shape_factory import (
#     ShapeFactory,
#     ShapeType,
# )
# from src.engine.vision.implementation.VisionSystem.features.shape_matching_training.core.dataset.data_augmentation import (
#     NoiseAugmentation,
#     RotationAugmentation,
#     ElasticDeformationAugmentation,
#     create_noisy_variants,
# )
#
# # Patch site: _refine_alignment_with_mask is imported directly into contour_aligner.
# # Patching there avoids the slow 3-stage iterative mask-overlap search during unit tests.
# _PATCH_REFINE = (
#     "src.engine.vision.implementation.VisionSystem"
#     ".features.contour_matching.alignment.contour_aligner._refine_alignment_with_mask"
# )
#
# # Patch site: get_settings is imported at module level in contour_matcher.
# # Used by camera-noise tests so they run against a known threshold (80%)
# # instead of whatever value is stored in the on-disk production settings file.
# _PATCH_SETTINGS = (
#     "src.engine.vision.implementation.VisionSystem"
#     ".features.contour_matching.contour_matcher.get_settings"
# )
#
#
# def _default_settings_mock() -> MagicMock:
#     """
#     Settings stub with default values (similarity_threshold=80, all debug=False).
#     Keeps camera-noise tests independent of the on-disk production settings file.
#     """
#     m = MagicMock()
#     m.get_similarity_threshold.return_value = 80.0
#     m.get_use_comparison_model.return_value = False
#     m.get_debug_similarity.return_value = False
#     m.get_debug_calculate_differences.return_value = False
#     m.get_debug_align_contours.return_value = False
#     return m
#
#
# # ---------------------------------------------------------------------------
# # Helpers
# # ---------------------------------------------------------------------------
#
# def _make_service() -> VisionService:
#     """VisionService whose vision_service is a mock — run_matching never touches it."""
#     return VisionService(MagicMock())
#
#
# class _StubWorkpiece:
#     """
#     Minimal workpiece stub satisfying the full interface consumed by
#     find_matching_workpieces (matching + alignment + update pipeline).
#     """
#
#     def __init__(self, contour: np.ndarray, workpiece_id: int = 1):
#         self._contour = contour
#         self.workpieceId = workpiece_id
#         # Mutable attributes written by update_workpiece_data
#         self.contour = {"contour": contour, "settings": {}}
#         self.sprayPattern = {"Contour": [], "Fill": []}
#         self.pickupPoint = None
#
#     def get_main_contour(self) -> np.ndarray:
#         return self._contour
#
#     def get_spray_pattern_contours(self) -> list:
#         return []
#
#     def get_spray_pattern_fills(self) -> list:
#         return []
#
#
# # ---------------------------------------------------------------------------
# # Return structure
# # ---------------------------------------------------------------------------
#
# class TestRunMatchingReturnStructure(unittest.TestCase):
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_returns_four_tuple(self, _):
#         result = _make_service().run_matching([], [])
#         self.assertEqual(len(result), 4)
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_types_are_dict_int_list_list(self, _):
#         result, no_match_count, matched, unmatched = _make_service().run_matching([], [])
#         self.assertIsInstance(result, dict)
#         self.assertIsInstance(no_match_count, int)
#         self.assertIsInstance(matched, list)
#         self.assertIsInstance(unmatched, list)
#
#
# # ---------------------------------------------------------------------------
# # Empty inputs
# # ---------------------------------------------------------------------------
#
# class TestRunMatchingEmptyInputs(unittest.TestCase):
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_fully_empty_inputs_return_empty_results(self, _):
#         result, no_match_count, matched, unmatched = _make_service().run_matching([], [])
#         self.assertEqual(no_match_count, 0)
#         self.assertEqual(matched, [])
#         self.assertEqual(unmatched, [])
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_empty_contours_zero_counts(self, _):
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         _, no_match_count, matched, unmatched = _make_service().run_matching([wp], [])
#         self.assertEqual(no_match_count, 0)
#         self.assertEqual(len(matched), 0)
#         self.assertEqual(len(unmatched), 0)
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_empty_workpieces_all_contours_unmatched(self, _):
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         _, no_match_count, matched, unmatched = _make_service().run_matching([], [circle])
#         self.assertEqual(no_match_count, 1)
#         self.assertEqual(len(unmatched), 1)
#         self.assertEqual(len(matched), 0)
#
#
# # ---------------------------------------------------------------------------
# # Successful match
# # ---------------------------------------------------------------------------
#
# class TestRunMatchingSuccessfulMatch(unittest.TestCase):
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_same_shape_contour_is_matched(self, _):
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         _, no_match_count, matched, unmatched = _make_service().run_matching([wp], [circle])
#         self.assertEqual(no_match_count, 0)
#         self.assertEqual(len(matched), 1)
#         self.assertEqual(len(unmatched), 0)
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_matched_contours_are_numpy_arrays(self, _):
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         _, _, matched, _ = _make_service().run_matching([wp], [circle])
#         for c in matched:
#             self.assertIsInstance(c, np.ndarray)
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_result_dict_is_populated_on_match(self, _):
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         result, _, _, _ = _make_service().run_matching([wp], [circle])
#         self.assertGreater(len(result), 0)
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_result_dict_has_expected_keys(self, _):
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         result, _, _, _ = _make_service().run_matching([wp], [circle])
#         for key in ("workpieces", "orientations", "mlConfidences", "mlResults"):
#             self.assertIn(key, result)
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_result_workpieces_list_has_one_entry(self, _):
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         result, _, _, _ = _make_service().run_matching([wp], [circle])
#         self.assertEqual(len(result["workpieces"]), 1)
#
#
# # ---------------------------------------------------------------------------
# # No match
# # ---------------------------------------------------------------------------
#
# class TestRunMatchingNoMatch(unittest.TestCase):
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_clearly_different_shape_is_unmatched(self, _):
#         # circle (many approxPolyDP vertices) vs rectangle (4 vertices) —
#         # vertex count delta > 5 → _getSimilarity returns 0.0
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         rectangle = ShapeFactory.generate_shape(ShapeType.RECTANGLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         _, no_match_count, matched, unmatched = _make_service().run_matching([wp], [rectangle])
#         self.assertEqual(no_match_count, 1)
#         self.assertEqual(len(matched), 0)
#         self.assertEqual(len(unmatched), 1)
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_unmatched_contours_are_numpy_arrays(self, _):
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         rectangle = ShapeFactory.generate_shape(ShapeType.RECTANGLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         _, _, _, unmatched = _make_service().run_matching([wp], [rectangle])
#         for c in unmatched:
#             self.assertIsInstance(c, np.ndarray)
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_no_match_count_equals_unmatched_list_length(self, _):
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         rectangle = ShapeFactory.generate_shape(ShapeType.RECTANGLE, scale=1.0)
#         triangle = ShapeFactory.generate_shape(ShapeType.TRIANGLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         _, no_match_count, _, unmatched = _make_service().run_matching(
#             [wp], [rectangle, triangle]
#         )
#         self.assertEqual(no_match_count, len(unmatched))
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_result_dict_is_empty_when_nothing_matched(self, _):
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         rectangle = ShapeFactory.generate_shape(ShapeType.RECTANGLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         result, _, _, _ = _make_service().run_matching([wp], [rectangle])
#         self.assertEqual(result.get("workpieces", []), [])
#
#
# # ---------------------------------------------------------------------------
# # Mixed inputs
# # ---------------------------------------------------------------------------
#
# class TestRunMatchingMixed(unittest.TestCase):
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_matched_plus_unmatched_equals_total_input(self, _):
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         rectangle = ShapeFactory.generate_shape(ShapeType.RECTANGLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         _, no_match_count, matched, unmatched = _make_service().run_matching(
#             [wp], [circle, rectangle]
#         )
#         self.assertEqual(len(matched) + no_match_count, 2)
#         self.assertEqual(len(matched) + len(unmatched), 2)
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_correct_contour_routes_to_matched_wrong_to_unmatched(self, _):
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         rectangle = ShapeFactory.generate_shape(ShapeType.RECTANGLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         _, _, matched, unmatched = _make_service().run_matching(
#             [wp], [circle, rectangle]
#         )
#         self.assertEqual(len(matched), 1)
#         self.assertEqual(len(unmatched), 1)
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_multiple_workpieces_each_match_own_contour(self, _):
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         hexagon = ShapeFactory.generate_shape(ShapeType.HEXAGON, scale=1.0)
#         wp1 = _StubWorkpiece(circle, workpiece_id=1)
#         wp2 = _StubWorkpiece(hexagon, workpiece_id=2)
#         _, no_match_count, matched, unmatched = _make_service().run_matching(
#             [wp1, wp2], [circle, hexagon]
#         )
#         self.assertEqual(no_match_count, 0)
#         self.assertEqual(len(matched), 2)
#         self.assertEqual(len(unmatched), 0)
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_three_contours_one_workpiece_only_matching_shape_is_matched(self, _):
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         rectangle = ShapeFactory.generate_shape(ShapeType.RECTANGLE, scale=1.0)
#         triangle = ShapeFactory.generate_shape(ShapeType.TRIANGLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         _, no_match_count, matched, unmatched = _make_service().run_matching(
#             [wp], [circle, rectangle, triangle]
#         )
#         self.assertEqual(len(matched), 1)
#         self.assertEqual(no_match_count, 2)
#         self.assertEqual(len(matched) + len(unmatched), 3)
#
#
# # ---------------------------------------------------------------------------
# # Camera noise simulation
# # ---------------------------------------------------------------------------
#
# class TestRunMatchingWithCameraNoise(unittest.TestCase):
#     """
#     Simulates real camera capture: the same physical workpiece photographed under
#     different conditions (sensor noise, lighting, slight tilt, lens distortion)
#     must still match its template stored in the workpiece library.
#
#     setUp patches get_settings in contour_matcher with default values
#     (similarity_threshold=80%, all debug=False) so these tests are independent
#     of the on-disk production settings file and produce no debug plot output.
#     """
#
#     def setUp(self):
#         patcher = patch(_PATCH_SETTINGS, return_value=_default_settings_mock())
#         patcher.start()
#         self.addCleanup(patcher.stop)
#
#     # ------------------------------------------------------------------
#     # Per-test augmentation helpers — seed before every random call
#     # ------------------------------------------------------------------
#
#     def _noisy(self, contour: np.ndarray, noise_level: float) -> np.ndarray:
#         """Gaussian pixel noise — models sensor/lighting variation."""
#         np.random.seed(42)
#         return NoiseAugmentation({'noise_level': noise_level, 'noise_type': 'gaussian'}).apply(contour.copy())
#
#     def _rotated(self, contour: np.ndarray, angle: float) -> np.ndarray:
#         """Fixed rotation — models camera not perfectly level."""
#         return RotationAugmentation({'fixed_angle': angle}).apply(contour.copy())
#
#     def _elastic(self, contour: np.ndarray, alpha: float = 0.5, sigma: float = 0.05) -> np.ndarray:
#         """Smooth elastic deformation — models lens distortion / thermal expansion."""
#         np.random.seed(42)
#         return ElasticDeformationAugmentation({'alpha': alpha, 'sigma': sigma}).apply(contour.copy())
#
#     # ------------------------------------------------------------------
#     # Gaussian noise — varying severity
#     # ------------------------------------------------------------------
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_light_gaussian_noise_still_matches(self, _):
#         """noise_level=0.5 px — good lighting, minor sensor noise."""
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         _, no_match_count, matched, _ = _make_service().run_matching([wp], [self._noisy(circle, 0.5)])
#         self.assertEqual(no_match_count, 0)
#         self.assertEqual(len(matched), 1)
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_medium_gaussian_noise_still_matches(self, _):
#         """noise_level=1.5 px — moderate lighting variation."""
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         _, no_match_count, matched, _ = _make_service().run_matching([wp], [self._noisy(circle, 1.5)])
#         self.assertEqual(no_match_count, 0)
#         self.assertEqual(len(matched), 1)
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_multiple_noise_levels_all_match(self, _):
#         """Parameterised: light → moderate noise levels all match the template."""
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         for noise_level in (0.3, 0.5, 1.0, 1.5):
#             with self.subTest(noise_level=noise_level):
#                 noisy = self._noisy(circle, noise_level)
#                 _, no_match_count, matched, _ = _make_service().run_matching([wp], [noisy])
#                 self.assertEqual(no_match_count, 0, msg=f"noise_level={noise_level} caused no match")
#                 self.assertEqual(len(matched), 1)
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_multiple_noisy_captures_in_single_call_all_match(self, _):
#         """
#         n simultaneous noisy captures of the same workpiece (e.g. burst mode)
#         all match in one run_matching call — no cross-contamination.
#         """
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         np.random.seed(0)
#         variants = create_noisy_variants(circle, n_variants=3, noise_levels=[0.3, 0.5, 1.0])
#         _, no_match_count, matched, unmatched = _make_service().run_matching([wp], variants)
#         self.assertEqual(no_match_count, 0)
#         self.assertEqual(len(matched), 3)
#         self.assertEqual(len(unmatched), 0)
#
#     # ------------------------------------------------------------------
#     # Rotation — camera angle variation
#     # ------------------------------------------------------------------
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_slight_rotation_still_matches(self, _):
#         """10° rotation — camera bracket not perfectly aligned."""
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         _, no_match_count, matched, _ = _make_service().run_matching([wp], [self._rotated(circle, 10.0)])
#         self.assertEqual(no_match_count, 0)
#         self.assertEqual(len(matched), 1)
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_multiple_rotation_angles_all_match(self, _):
#         """Circle is rotation-invariant — any angle must still match."""
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         for angle in (5.0, 15.0, 30.0, 45.0, 90.0):
#             with self.subTest(angle=angle):
#                 rotated = self._rotated(circle, angle)
#                 _, no_match_count, matched, _ = _make_service().run_matching([wp], [rotated])
#                 self.assertEqual(no_match_count, 0, msg=f"rotation={angle}° caused no match")
#                 self.assertEqual(len(matched), 1)
#
#     # ------------------------------------------------------------------
#     # Elastic deformation — lens distortion / thermal expansion
#     # ------------------------------------------------------------------
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_mild_elastic_deformation_still_matches(self, _):
#         """alpha=0.5, sigma=0.05 — mild lens or thermal distortion."""
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         _, no_match_count, matched, _ = _make_service().run_matching(
#             [wp], [self._elastic(circle, alpha=0.5, sigma=0.05)]
#         )
#         self.assertEqual(no_match_count, 0)
#         self.assertEqual(len(matched), 1)
#
#     # ------------------------------------------------------------------
#     # Combined conditions
#     # ------------------------------------------------------------------
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_combined_noise_and_rotation_still_matches(self, _):
#         """Slight tilt + sensor noise — the most common real capture condition."""
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         rotated = self._rotated(circle, 15.0)
#         augmented = self._noisy(rotated, 0.5)
#         _, no_match_count, matched, _ = _make_service().run_matching([wp], [augmented])
#         self.assertEqual(no_match_count, 0)
#         self.assertEqual(len(matched), 1)
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_noise_and_elastic_deformation_combined_still_matches(self, _):
#         """Sensor noise + lens distortion combined."""
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         deformed = self._elastic(circle, alpha=0.5, sigma=0.05)
#         augmented = self._noisy(deformed, 0.5)
#         _, no_match_count, matched, _ = _make_service().run_matching([wp], [augmented])
#         self.assertEqual(no_match_count, 0)
#         self.assertEqual(len(matched), 1)
#
#     # ------------------------------------------------------------------
#     # Noise must not confuse shape identity
#     # ------------------------------------------------------------------
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_noisy_contour_does_not_match_different_workpiece(self, _):
#         """Noisy circle must NOT match a rectangle template — noise cannot blur shape identity."""
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         rectangle = ShapeFactory.generate_shape(ShapeType.RECTANGLE, scale=1.0)
#         wp = _StubWorkpiece(rectangle)
#         _, no_match_count, matched, _ = _make_service().run_matching(
#             [wp], [self._noisy(circle, 1.0)]
#         )
#         self.assertEqual(no_match_count, 1)
#         self.assertEqual(len(matched), 0)
#
#     @patch(_PATCH_REFINE, return_value=(0.0, 1.0))
#     def test_noisy_variants_mixed_with_different_shape_routes_correctly(self, _):
#         """2 noisy circles + 1 rectangle against a circle workpiece: 2 match, 1 does not."""
#         circle = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
#         rectangle = ShapeFactory.generate_shape(ShapeType.RECTANGLE, scale=1.0)
#         wp = _StubWorkpiece(circle)
#         contours = [
#             self._noisy(circle, 0.5),
#             self._noisy(circle, 1.0),
#             rectangle,
#         ]
#         _, no_match_count, matched, unmatched = _make_service().run_matching([wp], contours)
#         self.assertEqual(len(matched), 2)
#         self.assertEqual(no_match_count, 1)
#         self.assertEqual(len(unmatched), 1)
#
#
# if __name__ == "__main__":
#     unittest.main()
#
