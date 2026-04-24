from ..adapters.i_workpiece_data_adapter import IWorkpieceDataAdapter


def load_workpiece(workpiece, adapter: IWorkpieceDataAdapter):
    editor_data = adapter.from_workpiece(workpiece)

    adapter.print_summary(editor_data)

    contours_by_layer = editor_data.to_legacy_format()

    return workpiece, contours_by_layer
