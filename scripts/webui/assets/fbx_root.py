"""Read the root node names of an exported binary FBX hierarchy.

AnimeStudio exports each Unity Animator as an FBX of the whole transform tree
it belongs to, and names the file after the GameObject that carries the
Animator. Cutscene and timeline Animators sit on generic objects (``Actor``,
``GameObject``, ``offset``), so the file name alone does not say which scene a
file belongs to; the FBX root node does. This reader seeks through the node
records and reads only ``Objects/Model`` property lists and ``Connections``,
never the geometry arrays, so it stays cheap on multi-megabyte files.

It proves only the exported FBX tree: a root is a ``Model`` connected to the
scene root (id 0). It says nothing about how the game instantiates the scene.
"""

from __future__ import annotations

import io
import struct
from pathlib import Path
from typing import BinaryIO

FBX_MAGIC = b"Kaydara FBX Binary  \x00"
_PROP_SIZES = {b"Y": 2, b"C": 1, b"I": 4, b"F": 4, b"D": 8, b"L": 8}


def _read_header(handle: BinaryIO, wide: bool) -> tuple[int, int, int, bytes] | None:
    raw = handle.read(25 if wide else 13)
    if len(raw) < (25 if wide else 13):
        return None
    if wide:
        end, count, prop_len = struct.unpack("<QQQ", raw[:24])
    else:
        end, count, prop_len = struct.unpack("<III", raw[:12])
    name_len = raw[-1]
    if end == 0:
        return (0, 0, 0, b"")
    return end, count, prop_len, handle.read(name_len)


def _parse_props(data: bytes, count: int) -> list[object]:
    props: list[object] = []
    pos = 0
    for _ in range(count):
        code = data[pos : pos + 1]
        pos += 1
        if code in (b"S", b"R"):
            (length,) = struct.unpack_from("<I", data, pos)
            pos += 4
            value = data[pos : pos + length]
            pos += length
            props.append(value.decode("utf-8", "replace") if code == b"S" else value)
        elif code == b"L":
            props.append(struct.unpack_from("<q", data, pos)[0])
            pos += 8
        elif code in _PROP_SIZES:
            pos += _PROP_SIZES[code]
            props.append(None)
        else:
            # Arrays never appear on Model or C records; stop rather than guess.
            break
    return props


def _children(handle: BinaryIO, start: int, end: int, wide: bool):
    """Yield (name, props_offset, prop_count, prop_len, end) for direct children."""
    position = start
    while position < end:
        handle.seek(position)
        header = _read_header(handle, wide)
        if header is None or header[0] == 0:
            return
        node_end, count, prop_len, name = header
        yield name, handle.tell(), count, prop_len, node_end
        position = node_end


def read_fbx_root_names(path: Path) -> list[str]:
    """Return the names of the top-level FBX models, in file order."""
    with path.open("rb") as handle:
        return _root_names(handle, path.stat().st_size)


def read_fbx_root_names_from_bytes(data: bytes) -> list[str]:
    """:func:`read_fbx_root_names` for an FBX already in memory (a Unity store row)."""
    return _root_names(io.BytesIO(data), len(data))


def _root_names(handle: BinaryIO, file_end: int) -> list[str]:
    if handle.read(len(FBX_MAGIC)) != FBX_MAGIC:
        return []
    handle.seek(23)
    (version,) = struct.unpack("<I", handle.read(4))
    wide = version >= 7500
    models: dict[int, str] = {}
    parents: dict[int, int] = {}
    for name, props_at, count, prop_len, node_end in _children(handle, 27, file_end, wide):
        if name not in (b"Objects", b"Connections"):
            continue
        child_start = props_at + prop_len
        wanted = b"Model" if name == b"Objects" else b"C"
        for child, child_props_at, child_count, child_len, _ in _children(
            handle, child_start, node_end, wide
        ):
            if child != wanted:
                continue
            handle.seek(child_props_at)
            props = _parse_props(handle.read(child_len), child_count)
            if wanted == b"Model" and len(props) >= 2 and isinstance(props[0], int):
                models[props[0]] = str(props[1]).split("\x00", 1)[0]
            elif (
                wanted == b"C"
                and len(props) >= 3
                and props[0] == "OO"
                and isinstance(props[1], int)
            ):
                parents[props[1]] = props[2]
    return [label for model_id, label in models.items() if parents.get(model_id, 0) not in models]
