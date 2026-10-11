"""Bounded PhysX stream primitives shared by the triangle and convex readers."""
from __future__ import annotations

import math
import struct


class CookedReader:
    def __init__(self, payload: bytes, endian: str, offset: int = 0):
        self.payload, self.endian, self.offset = payload, endian, offset
        self.spans: list[dict] = []

    def take(self, size: int, field: str) -> bytes:
        if size < 0 or size > len(self.payload) - self.offset:
            raise ValueError(f"{field} at 0x{self.offset:X}: need {size} bytes, have {len(self.payload)-self.offset}")
        start = self.offset
        self.offset += size
        self.spans.append(dict(field=field, start=start, end=self.offset))
        return self.payload[start:self.offset]

    def unpack(self, fmt: str, field: str) -> tuple:
        return struct.unpack(self.endian + fmt, self.take(struct.calcsize(self.endian + fmt), field))

    def u32(self, field: str) -> int:
        return self.unpack("I", field)[0]

    def floats(self, count: int, field: str) -> tuple[float, ...]:
        raw = self.take(count * 4, field)
        values = tuple(v[0] for v in struct.iter_unpack(self.endian + "f", raw))
        if not all(math.isfinite(v) for v in values):
            raise ValueError(f"{field}: non-finite float")
        return values

    def finish(self) -> None:
        if self.offset != len(self.payload):
            raise ValueError(f"cooked payload: {len(self.payload)-self.offset} trailing bytes at 0x{self.offset:X}")


def stream_header(reader: CookedReader, magic: bytes, chunk: bytes, field: str) -> int:
    raw = reader.take(8, field + ".header")
    if raw[:3] != magic or raw[3] not in (0, 1) or raw[4:] != chunk:
        raise ValueError(f"{field}: expected {magic!r}/{chunk!r} header")
    reader.endian = "<" if raw[3] else ">"
    return reader.u32(field + ".version")


def check_bounds(bounds: tuple, vertices: tuple, field: str, quantization_error: tuple = (0, 0, 0), *, lower_error: tuple = (0, 0, 0)) -> None:
    if len(bounds) != 6 or not all(math.isfinite(v) for v in bounds):
        raise ValueError(f"{field}: invalid bounds")
    if any(bounds[i] > bounds[i+3] for i in range(3)):
        raise ValueError(f"{field}: inverted bounds")
    for vertex in vertices:
        for axis in range(3):
            tolerance = quantization_error[axis] + 2e-6 * max(1.0, abs(bounds[axis]), abs(bounds[axis+3]))
            if not bounds[axis]-tolerance-lower_error[axis] <= vertex[axis] <= bounds[axis+3]+tolerance:
                raise ValueError(f"{field}: vertex outside stored bounds on axis {axis}; value={vertex[axis]:.9g}, bounds={bounds[axis]:.9g}..{bounds[axis+3]:.9g}, error={tolerance+lower_error[axis]:.9g}/{tolerance:.9g}")
