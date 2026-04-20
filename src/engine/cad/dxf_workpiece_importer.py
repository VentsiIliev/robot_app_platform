from __future__ import annotations

from .dxf_geometry_parser import (
    DxfGeometry,
    DxfGeometryParser,
    DxfImportOptions,
    normalize_path,
    parse_dxf_geometry,
    to_contour_array,
)


class DxfWorkpieceImporter:
    """DXF to workpiece adapter built on top of the reusable geometry parser."""

    def __init__(self, options: DxfImportOptions | None = None) -> None:
        self._options = options or DxfImportOptions()
        self._parser = DxfGeometryParser(self._options)

    def import_file(self, dxf_path: str) -> dict:
        geometry = self._parser.parse_file(dxf_path)
        contour = normalize_path(
            geometry.largest_closed_path(),
            self._options.normalize_to_origin,
        )
        return {
            "contour": to_contour_array(contour),
            "sprayPattern": {
                "Contour": [],
                "Fill": [],
            },
        }

    def import_file_to_editor_data(self, dxf_path: str):
        from src.applications.workpiece_editor.editor_core.adapters.workpiece_adapter import WorkpieceAdapter

        return WorkpieceAdapter.from_raw(self.import_file(dxf_path))


def import_dxf_to_workpiece_data(
    dxf_path: str,
    *,
    options: DxfImportOptions | None = None,
) -> dict:
    return DxfWorkpieceImporter(options=options).import_file(dxf_path)


def import_dxf_to_editor_data(
    dxf_path: str,
    *,
    options: DxfImportOptions | None = None,
):
    return DxfWorkpieceImporter(options=options).import_file_to_editor_data(dxf_path)


def parse_dxf_to_geometry(
    dxf_path: str,
    *,
    options: DxfImportOptions | None = None,
) -> DxfGeometry:
    return parse_dxf_geometry(dxf_path, options=options)
