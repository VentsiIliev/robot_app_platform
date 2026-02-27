from typing import Tuple


def split_into_16bit(value: int) -> Tuple[int, int]:
    """
    Split a signed integer into two 16-bit unsigned halves for Modbus register writes.
    Returns (high16, low16).
    """
    u32   = value & 0xFFFFFFFF
    high  = (u32 >> 16) & 0xFFFF
    low   = u32 & 0xFFFF
    return high, low


def int_to_hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08X}"