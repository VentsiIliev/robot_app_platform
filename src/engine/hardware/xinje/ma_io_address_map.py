from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class XinjeMAIOAddressMap:
    """Modbus address map for Xinje MA digital I/O modules."""

    model: str
    input_addresses: Mapping[str, int]
    output_addresses: Mapping[str, int]

    def resolve_input(self, point: int | str) -> int:
        return self._resolve(point, self.input_addresses, "input")

    def resolve_output(self, point: int | str) -> int:
        return self._resolve(point, self.output_addresses, "output")

    def _resolve(self, point: int | str, mapping: Mapping[str, int], kind: str) -> int:
        if isinstance(point, int):
            return point

        key = point.strip().upper()
        if key in mapping:
            return mapping[key]

        try:
            return int(key, 0)
        except ValueError as exc:
            valid = ", ".join(mapping)
            raise ValueError(
                f"Unknown Xinje {self.model} {kind} point {point!r}; expected one of: {valid}"
            ) from exc


XinjeMA8X8YR = XinjeMAIOAddressMap(
    model="MA-8X8YR",
    input_addresses={f"X{index}": index for index in range(8)},
    output_addresses={f"Y{index}": 128 + index for index in range(8)},
)
