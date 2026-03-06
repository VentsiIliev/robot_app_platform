from __future__ import annotations

import numpy as np
from typing import Any, Dict, List, Optional

from src.robot_systems.glue.domain.workpieces.model.glue_workpiece_filed import GlueWorkpieceField

from src.applications.workpiece_editor.editor_core.models.base_workpiece import BaseWorkpiece


class GlueWorkpiece(BaseWorkpiece):

    def __init__(
        self,
        workpieceId: str,
        name: str,
        description: str,
        gripperID: int,
        glueType: str,
        contour,
        height: float,
        glueQty: float,
        pickupPoint: Optional[Any],
        sprayPattern: Optional[Dict] = None,
    ):
        super().__init__(workpieceId, name)
        self.workpieceId  = workpieceId
        self.description  = description
        self.gripperID    = gripperID
        self.glueType     = glueType
        self.contour      = contour
        self.height       = height
        self.glueQty      = glueQty
        self.pickupPoint  = pickupPoint
        self.sprayPattern = sprayPattern if sprayPattern is not None else {}

    def __str__(self) -> str:
        gripper = self.gripperID.value if hasattr(self.gripperID, "value") else self.gripperID
        return (
            f"GlueWorkpiece(id={self.workpieceId}, name={self.name}, "
            f"gripper={gripper}, height={self.height}, pickup={self.pickupPoint})"
        )

    # ── Contour accessors ────────────────────────────────────────────

    def get_main_contour(self) -> np.ndarray:
        raw = self.contour["contour"] if isinstance(self.contour, dict) else self.contour
        return _to_n12(raw)

    def get_main_contour_settings(self) -> dict:
        if isinstance(self.contour, dict):
            return self.contour.get("settings", {})
        return {}

    def set_main_contour(self, contour) -> None:
        if isinstance(self.contour, dict):
            self.contour["contour"] = contour
        else:
            self.contour = contour

    # ── Spray pattern accessors ───────────────────────────────────────

    def get_spray_pattern_contours(self) -> List[dict]:
        return self._spray_entries("Contour")

    def get_spray_pattern_fills(self) -> List[dict]:
        return self._spray_entries("Fill")

    def _spray_entries(self, key: str) -> List[dict]:
        result = []
        for entry in self.sprayPattern.get(key, []):
            pts = np.array(entry.get("contour", []), dtype=np.float32).reshape(-1, 2)
            result.append({"contour": pts, "settings": entry.get("settings", {})})
        return result

    # ── Serialization ────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            GlueWorkpieceField.WORKPIECE_ID.value:  self.workpieceId,
            GlueWorkpieceField.NAME.value:          self.name,
            GlueWorkpieceField.DESCRIPTION.value:   self.description,
            GlueWorkpieceField.GRIPPER_ID.value:    self.gripperID,
            GlueWorkpieceField.GLUE_TYPE.value:     self.glueType,
            GlueWorkpieceField.CONTOUR.value:       self.contour,
            GlueWorkpieceField.HEIGHT.value:        self.height,
            GlueWorkpieceField.GLUE_QTY.value:      self.glueQty,
            GlueWorkpieceField.PICKUP_POINT.value:  self.pickupPoint,
            GlueWorkpieceField.SPRAY_PATTERN.value: self.sprayPattern,
        }

    @staticmethod
    def from_dict(data: dict) -> GlueWorkpiece:
        F = GlueWorkpieceField
        wp = GlueWorkpiece(
            workpieceId  = data[F.WORKPIECE_ID.value],
            name         = data[F.NAME.value],
            description  = data[F.DESCRIPTION.value],
            height       = data.get(F.HEIGHT.value, 4),
            glueQty      = data[F.GLUE_QTY.value],
            gripperID    = int(data[F.GRIPPER_ID.value]),
            glueType     = data[F.GLUE_TYPE.value],
            contour      = data[F.CONTOUR.value],
            pickupPoint  = data.get(F.PICKUP_POINT.value),
            sprayPattern = data.get(F.SPRAY_PATTERN.value, {}),
        )
        print(f"GlueWorkpiece.from_dict: {wp}")
        return wp

    @staticmethod
    def serialize(workpiece: GlueWorkpiece) -> dict:
        import copy
        wp = copy.copy(workpiece)
        wp.contour      = _contour_to_list(wp.contour)
        wp.sprayPattern = _spray_to_list(wp.sprayPattern)
        return wp.to_dict()

    @staticmethod
    def deserialize(data: dict) -> GlueWorkpiece:
        F = GlueWorkpieceField
        raw_contour = data.get(F.CONTOUR.value, [])
        contour = (
            _contour_from_list(raw_contour)
            if isinstance(raw_contour, dict)
            else [_contour_from_list(s) for s in raw_contour]
        )

        raw_spray = data.get(F.SPRAY_PATTERN.value, {})
        spray = (
            {k: [_contour_from_list(s) for s in v] for k, v in raw_spray.items()}
            if isinstance(raw_spray, dict) else raw_spray
        )

        wp = GlueWorkpiece.from_dict(data)
        wp.contour      = contour
        wp.sprayPattern = spray
        return wp




def _to_n12(data) -> np.ndarray:
    if isinstance(data, np.ndarray):
        if data.ndim == 3 and data.shape[1] == 1:
            return data
        if data.ndim == 2:
            return data.reshape(-1, 1, 2)
        return data.reshape(-1, 2).reshape(-1, 1, 2)

    flat = []
    for pt in data:
        while isinstance(pt, (list, tuple, np.ndarray)) and len(pt) == 1:
            pt = pt[0]
        if len(pt) >= 2:
            x, y = pt[0], pt[1]
            while isinstance(x, (list, tuple, np.ndarray)):
                x = x[0] if len(x) > 0 else 0
            while isinstance(y, (list, tuple, np.ndarray)):
                y = y[0] if len(y) > 0 else 0
            flat.append([float(x), float(y)])
    return np.array(flat, dtype=np.float32).reshape(-1, 1, 2) if flat else np.empty((0, 1, 2), np.float32)


def _contour_to_list(obj) -> Any:
    if isinstance(obj, np.ndarray):
        if obj.ndim == 2 and obj.shape[1] == 2:
            obj = obj.reshape(-1, 1, 2)
        return obj.tolist()
    if isinstance(obj, dict) and "contour" in obj:
        c = obj["contour"]
        if isinstance(c, np.ndarray) and c.ndim == 2 and c.shape[1] == 2:
            c = c.reshape(-1, 1, 2)
        return {"contour": _contour_to_list(c), "settings": dict(obj.get("settings", {}))}
    if isinstance(obj, list):
        return [_contour_to_list(i) for i in obj]
    return obj


def _spray_to_list(spray) -> dict:
    if not isinstance(spray, dict):
        return {}
    return {k: [_contour_to_list(seg) for seg in v] for k, v in spray.items()}


def _contour_from_list(obj) -> Any:
    if isinstance(obj, dict) and "contour" in obj:
        arr = np.array(obj["contour"], dtype=np.float32)
        if arr.ndim == 1 and arr.shape[0] == 2:
            arr = arr.reshape(1, 1, 2)
        elif arr.ndim == 2 and arr.shape[1] == 2:
            arr = arr.reshape(-1, 1, 2)
        return {"contour": arr, "settings": obj.get("settings", {})}
    if isinstance(obj, list):
        return [_contour_from_list(i) for i in obj]
    return obj