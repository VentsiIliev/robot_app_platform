import unittest
from unittest.mock import MagicMock

import numpy as np

from src.applications.workpiece_editor.editor_core.config.workpiece_form_schema import (
    WorkpieceFormSchema, WorkpieceFormFieldSpec,
)
from src.applications.workpiece_editor.editor_core.handlers.SaveWorkpieceHandler import SaveWorkpieceHandler
from src.applications.workpiece_editor.service.workpiece_editor_service import (
    WorkpieceEditorService, _has_valid_contour,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _schema(*required_keys):
    keys = required_keys or ("workpieceId",)
    fields = [WorkpieceFormFieldSpec(key=k, label=k, field_type="text", mandatory=True) for k in keys]
    return WorkpieceFormSchema(fields=fields)


def _make_svc(vision=None, save_fn=None, update_fn=None, schema=None, id_exists_fn=None):
    return WorkpieceEditorService(
        vision_service=vision,
        capture_snapshot_service=None,
        save_fn=save_fn   or (lambda d: (True, "saved")),
        update_fn=update_fn or (lambda sid, d: (True, "updated")),
        form_schema=schema if schema is not None else _schema(),
        segment_config=MagicMock(),
        id_exists_fn=id_exists_fn,
    )


# form_data that always passes validation in the default schema
_VALID = {"form_data": {"workpieceId": "wp001", "contour": [1, 2, 3]}}


# ── _has_valid_contour ────────────────────────────────────────────────────────

class TestHasValidContour(unittest.TestCase):

    def test_none_returns_false(self):
        self.assertFalse(_has_valid_contour(None))

    def test_numpy_one_point_returns_false(self):
        self.assertFalse(_has_valid_contour(np.array([[1, 2]])))  # size == 2

    def test_numpy_three_points_returns_true(self):
        self.assertTrue(_has_valid_contour(np.array([[1, 2], [3, 4], [5, 6]])))  # size == 6

    def test_list_two_elements_returns_false(self):
        self.assertFalse(_has_valid_contour([1, 2]))

    def test_list_three_elements_returns_true(self):
        self.assertTrue(_has_valid_contour([1, 2, 3]))

    def test_other_type_returns_false(self):
        self.assertFalse(_has_valid_contour("a contour string"))
        self.assertFalse(_has_valid_contour(42))


# ── SaveWorkpieceHandler ──────────────────────────────────────────────────────

class TestSaveWorkpieceHandlerValidate(unittest.TestCase):

    def test_all_keys_present_returns_true(self):
        ok, errs = SaveWorkpieceHandler.validate_form_data({"a": "x", "b": "y"}, ["a", "b"])
        self.assertTrue(ok)
        self.assertEqual(errs, [])

    def test_missing_key_returns_false(self):
        ok, errs = SaveWorkpieceHandler.validate_form_data({"a": "x"}, ["a", "b"])
        self.assertFalse(ok)
        self.assertEqual(len(errs), 1)
        self.assertIn("'b'", errs[0])

    def test_empty_value_treated_as_missing(self):
        ok, errs = SaveWorkpieceHandler.validate_form_data({"a": ""}, ["a"])
        self.assertFalse(ok)

    def test_no_required_keys_always_valid(self):
        ok, errs = SaveWorkpieceHandler.validate_form_data({}, [])
        self.assertTrue(ok)
        self.assertEqual(errs, [])

    def test_multiple_missing_keys_reported(self):
        ok, errs = SaveWorkpieceHandler.validate_form_data({}, ["x", "y"])
        self.assertFalse(ok)
        self.assertEqual(len(errs), 2)


# ── WorkpieceEditorService getters ────────────────────────────────────────────

class TestWorkpieceEditorServiceGetters(unittest.TestCase):

    def test_get_form_schema_direct_instance(self):
        s = _schema()
        self.assertIs(_make_svc(schema=s).get_form_schema(), s)

    def test_get_form_schema_callable_is_called(self):
        s = _schema()
        self.assertIs(_make_svc(schema=lambda: s).get_form_schema(), s)

    def test_get_segment_config_returns_stored_config(self):
        cfg = MagicMock()
        svc = WorkpieceEditorService(
            vision_service=None,
            capture_snapshot_service=None,
            save_fn=lambda d: (True, ""),
            update_fn=lambda s, d: (True, ""),
            form_schema=_schema(),
            segment_config=cfg,
        )
        self.assertIs(svc.get_segment_config(), cfg)

    def test_set_editing_stores_id(self):
        svc = _make_svc()
        svc.set_editing("store-xyz")
        self.assertEqual(svc._editing_storage_id, "store-xyz")

    def test_set_editing_none_clears_id(self):
        svc = _make_svc()
        svc.set_editing("abc")
        svc.set_editing(None)
        self.assertIsNone(svc._editing_storage_id)


# ── WorkpieceEditorService.get_contours ───────────────────────────────────────

class TestWorkpieceEditorServiceGetContours(unittest.TestCase):

    def test_no_vision_returns_empty_list(self):
        self.assertEqual(_make_svc(vision=None).get_contours(), [])

    def test_with_vision_delegates_and_returns(self):
        vision = MagicMock()
        vision.get_latest_contours.return_value = [[1, 2, 3], [4, 5, 6]]
        result = _make_svc(vision=vision).get_contours()
        vision.get_latest_contours.assert_called_once()
        self.assertEqual(len(result), 2)

    def test_vision_exception_returns_empty_list(self):
        vision = MagicMock()
        vision.get_latest_contours.side_effect = RuntimeError("disconnected")
        self.assertEqual(_make_svc(vision=vision).get_contours(), [])


# ── WorkpieceEditorService.save_workpiece ─────────────────────────────────────

class TestWorkpieceEditorServiceSave(unittest.TestCase):

    def test_missing_required_field_returns_false(self):
        svc = _make_svc(schema=_schema("workpieceId"))
        # workpieceId absent from form_data
        ok, msg = svc.save_workpiece({"form_data": {"contour": [1, 2, 3]}})
        self.assertFalse(ok)
        self.assertIn("Validation", msg)

    def test_missing_contour_returns_false(self):
        ok, msg = _make_svc().save_workpiece({"form_data": {"workpieceId": "wp1"}})
        self.assertFalse(ok)
        self.assertIn("contour", msg.lower())

    def test_valid_data_calls_save_fn(self):
        calls = []
        svc = _make_svc(save_fn=lambda d: (calls.append(d), (True, "ok"))[1])
        ok, _ = svc.save_workpiece(_VALID)
        self.assertTrue(ok)
        self.assertEqual(len(calls), 1)

    def test_save_fn_result_is_returned(self):
        svc = _make_svc(save_fn=lambda d: (False, "dup"))
        ok, msg = svc.save_workpiece(_VALID)
        self.assertFalse(ok)
        self.assertEqual(msg, "dup")

    def test_editing_id_set_calls_update_fn(self):
        update_ids = []
        svc = _make_svc(update_fn=lambda sid, d: (update_ids.append(sid), (True, "upd"))[1])
        svc.set_editing("store-99")
        svc.save_workpiece(_VALID)
        self.assertEqual(update_ids, ["store-99"])

    def test_editing_id_cleared_after_successful_update(self):
        svc = _make_svc()
        svc.set_editing("store-abc")
        svc.save_workpiece(_VALID)
        self.assertIsNone(svc._editing_storage_id)

    def test_duplicate_workpiece_id_returns_false(self):
        svc = _make_svc(id_exists_fn=lambda wp_id: wp_id == "wp001")
        ok, msg = svc.save_workpiece(_VALID)
        self.assertFalse(ok)
        self.assertIn("already exists", msg)

    def test_id_check_skipped_when_form_has_no_id(self):
        svc = _make_svc(
            schema=WorkpieceFormSchema(fields=[]),   # no required fields
            id_exists_fn=lambda _: True,             # blocks any named ID
        )
        # no workpieceId → id key is "" (falsy) → id_exists_fn not called
        ok, _ = svc.save_workpiece({"form_data": {"contour": [1, 2, 3]}})
        self.assertTrue(ok)

    def test_save_fn_exception_returns_false(self):
        def _boom(d): raise RuntimeError("disk full")
        svc = _make_svc(save_fn=_boom)
        ok, msg = svc.save_workpiece(_VALID)
        self.assertFalse(ok)
        self.assertIn("disk full", msg)

    def test_non_contour_editor_data_falls_back_to_form_data(self):
        calls = []
        svc = _make_svc(save_fn=lambda d: (calls.append(d), (True, "ok"))[1])
        data = {
            "form_data": {"workpieceId": "wp1", "contour": [1, 2, 3]},
            "editor_data": {"raw": "some data"},   # dict, not ContourEditorData
        }
        svc.save_workpiece(data)
        self.assertEqual(calls[0].get("workpieceId"), "wp1")


# ── WorkpieceEditorService.execute_workpiece ──────────────────────────────────

class TestWorkpieceEditorServiceExecute(unittest.TestCase):

    def test_returns_true_with_success_message(self):
        data = {"form_data": {"sprayPattern": {"Contour": [
            {"contour": [[0, 0], [100, 0], [100, 100]], "settings": {}}
        ]}}}
        ok, msg = _make_svc().execute_workpiece(data)
        self.assertTrue(ok)
        self.assertIsNotNone(msg)


if __name__ == "__main__":
    unittest.main()

