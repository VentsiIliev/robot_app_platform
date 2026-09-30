from __future__ import annotations

from copy import deepcopy


APPLY_PAINT_SELECTION_ACTION = "paint.apply_rectangle_selection"
OPEN_PATH_SETTING = "closed_path"
SELECTION_SOURCE_SETTING = "paint_selection_source"


def apply_selected_paint_segments(editor) -> tuple[bool, str]:
    """Append open Paint sections selected from the canonical Workpiece outline."""
    manager = editor.manager
    segments = list(manager.get_segments())
    paint_layer_name = manager.layer_config.name_for_role("contour")
    workpiece_layer_name = manager.layer_config.name_for_role("workpiece")
    selected_workpiece: dict[int, set[int]] = {}
    selected_initial_paint: dict[int, set[int]] = {}

    for selected in editor.selection_manager.selected_points_list:
        if selected.get("role") != "anchor":
            continue
        segment_index = int(selected.get("seg_index", -1))
        point_index = int(selected.get("point_index", -1))
        if not 0 <= segment_index < len(segments):
            continue
        segment = segments[segment_index]
        layer_name = getattr(getattr(segment, "layer", None), "name", "")
        settings = getattr(segment, "settings", {}) or {}
        is_matching_source = layer_name == workpiece_layer_name
        is_initial_paint_source = (
            layer_name == paint_layer_name
            and bool(settings.get(SELECTION_SOURCE_SETTING))
        )
        if not (is_matching_source or is_initial_paint_source):
            continue
        if 0 <= point_index < len(segment.points):
            target = selected_initial_paint if is_initial_paint_source else selected_workpiece
            target.setdefault(segment_index, set()).add(point_index)

    # The two initial contours overlap. Prefer the cyan Paint source when the
    # rectangle hits both; after it is consumed, later selections use Workpiece.
    selected_by_segment = selected_initial_paint or selected_workpiece

    replacements = []
    for segment_index, selected_indices in selected_by_segment.items():
        source = segments[segment_index]
        point_count = len(source.points)
        crosses_closed_seam = (
            point_count > 2
            and 0 in selected_indices
            and point_count - 1 in selected_indices
            and len(selected_indices) < point_count
        )
        runs = _contiguous_runs(selected_indices)
        if crosses_closed_seam and len(runs) > 1:
            seam_run = runs[-1] + runs[0]
            runs = [seam_run, *runs[1:-1]]
        for run in runs:
            if len(run) < 2:
                continue
            replacement = manager.create_segment(
                [source.points[index] for index in run],
                layer_name=paint_layer_name,
            )
            replacement.settings = deepcopy(getattr(source, "settings", {}) or {})
            replacement.settings.pop(SELECTION_SOURCE_SETTING, None)
            replacement.settings[OPEN_PATH_SETTING] = False
            replacements.append(replacement)
    if not replacements:
        return False, "Select at least two neighboring Paint contour points."

    manager.save_state()
    manager.segments[:] = [
        segment
        for segment in segments
        if not (
            getattr(getattr(segment, "layer", None), "name", "") == paint_layer_name
            and bool((getattr(segment, "settings", {}) or {}).get(SELECTION_SOURCE_SETTING))
        )
    ]
    manager.segments.extend(replacements)
    manager.active_segment_index = len(manager.segments) - 1
    editor.selection_manager.clear_all_selections()
    editor.pointsUpdated.emit()
    editor.update()
    return True, "Paint segments created from the rectangle selection."


def _contiguous_runs(indices: set[int]) -> list[list[int]]:
    """Return ascending neighboring index runs; isolated points remain runs."""
    ordered = sorted(indices)
    if not ordered:
        return []
    runs = [[ordered[0]]]
    for index in ordered[1:]:
        if index == runs[-1][-1] + 1:
            runs[-1].append(index)
        else:
            runs.append([index])
    return runs

