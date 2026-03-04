from ..adapters.workpiece_adapter import WorkpieceAdapter


def load_workpiece(workpiece):
    editor_data = WorkpieceAdapter.from_workpiece(workpiece)

    WorkpieceAdapter.print_summary(editor_data)

    contours_by_layer = editor_data.to_legacy_format()

    return workpiece, contours_by_layer

