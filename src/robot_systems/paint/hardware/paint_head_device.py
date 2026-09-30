from __future__ import annotations

from src.engine.hardware.communication.i_register_transport import IRegisterTransport


class PaintHeadDevice:
    """Apply paint-head presets or relative degree moves and verify writes."""

    def __init__(
        self,
        transport: IRegisterTransport,
        register: int,
        *,
        min_value: int,
        max_value: int,
        preset_spacing: int,
        preset_count: int,
        degree_units_numerator: int,
        degree_units_denominator: int,
    ) -> None:
        if not 0 <= register <= 65535:
            raise ValueError("Paint-head register address is invalid")
        if not 0 <= min_value <= max_value <= 65535:
            raise ValueError("Paint-head register range is invalid")
        if preset_spacing < 1 or preset_count < 1:
            raise ValueError("Paint-head preset calibration is invalid")
        if min_value + preset_spacing * (preset_count - 1) != max_value:
            raise ValueError("Paint-head preset range does not match its calibration")
        if degree_units_numerator < 1 or degree_units_denominator < 1:
            raise ValueError("Paint-head degree calibration is invalid")
        self._transport = transport
        self._register = register
        self._min_value = min_value
        self._max_value = max_value
        self._preset_spacing = preset_spacing
        self._preset_count = preset_count
        self._degree_units_numerator = degree_units_numerator
        self._degree_units_denominator = degree_units_denominator

    def go_to_setting(self, setting: int) -> int:
        """Write the script's absolute preset: min + spacing × (count − setting)."""
        return self.go_to_position(self.register_for_setting(setting))

    def go_to_position(self, position: int) -> int:
        """Write a calibrated register position and verify the readback."""
        return self._write_and_verify(self.validate_position(position))

    def validate_position(self, position: int) -> int:
        """Validate an absolute target without device I/O for dry runs."""
        if isinstance(position, bool) or not isinstance(position, int):
            raise ValueError("Paint-head target must be a whole register value")
        if not self._min_value <= position <= self._max_value:
            raise ValueError(f"Paint-head target {position} is outside the configured range")
        return position

    def register_for_setting(self, setting: int) -> int:
        """Calculate an absolute preset without accessing hardware."""
        if isinstance(setting, bool) or not isinstance(setting, int):
            raise ValueError("Paint-head setting must be a whole number")
        if not 1 <= setting <= self._preset_count:
            raise ValueError(f"Paint-head setting must be 1..{self._preset_count}")
        return self._min_value + self._preset_spacing * (self._preset_count - setting)

    def move_degrees(self, delta_degrees: int) -> int:
        """Move signed whole degrees from the current register position."""
        return self.move_register_delta(self.register_delta_for_degrees(delta_degrees))

    def move_register_delta(self, delta_register: int) -> int:
        """Move a signed register distance after reading the current position."""
        if isinstance(delta_register, bool) or not isinstance(delta_register, int) or delta_register == 0:
            raise ValueError("Paint-head register move must be a nonzero whole number")
        current = self.read_position()
        return self.go_to_position(current + delta_register)

    def register_delta_for_setting_tenths(self, tenths: int) -> int:
        """Convert a positive tenth-of-setting step to register units."""
        if isinstance(tenths, bool) or not isinstance(tenths, int) or tenths < 1:
            raise ValueError("Paint-head setting step must be a positive whole number of tenths")
        delta = round(self._preset_spacing * tenths / 10)
        if delta == 0:
            raise ValueError("Paint-head setting step is smaller than one register unit")
        return delta

    def move_setting_tenths(self, signed_tenths: int) -> int:
        """Advance the displayed setting by exact tenths in register direction."""
        if isinstance(signed_tenths, bool) or not isinstance(signed_tenths, int) or signed_tenths == 0:
            raise ValueError("Paint-head setting step must be a nonzero whole number of tenths")
        current = self.read_position()
        displayed_tenths = round(10 + (self._max_value - current) * 10 / self._preset_spacing)
        target_tenths = displayed_tenths - signed_tenths
        if not 10 <= target_tenths <= self._preset_count * 10:
            raise ValueError("Paint-head setting step exceeds the configured range")
        target = round(
            self._max_value - (target_tenths - 10) * self._preset_spacing / 10
        )
        if target == current:
            raise ValueError("Paint-head setting step is smaller than one register unit")
        return self.go_to_position(target)

    def read_position(self) -> int:
        """Read and validate the current register position."""
        current = self._transport.read_register(self._register)
        if not self._min_value <= current <= self._max_value:
            raise ValueError(f"Paint-head position {current} is outside the configured range")
        return current

    def register_delta_for_degrees(self, delta_degrees: int) -> int:
        """Calculate a signed relative delta without accessing hardware."""
        if isinstance(delta_degrees, bool) or not isinstance(delta_degrees, int) or delta_degrees == 0:
            raise ValueError("Paint-head movement must be a nonzero integer number of degrees")

        # Match the script's round(degrees * 94 / 90) conversion.
        delta_register = round(
            delta_degrees * self._degree_units_numerator / self._degree_units_denominator
        )
        if delta_register == 0:
            raise ValueError("Paint-head degree move rounds to zero register units")
        return delta_register

    def _write_and_verify(self, target: int) -> int:
        self._transport.write_register(self._register, target)
        actual = self._transport.read_register(self._register)
        if actual != target:
            raise RuntimeError(f"Paint-head readback mismatch: wrote {target}, read {actual}")
        return actual
