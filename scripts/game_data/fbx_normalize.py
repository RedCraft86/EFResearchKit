"""Make an exported binary FBX deterministic, so equal content means equal bytes.

AnimeStudio writes Animator FBX through the Autodesk FBX SDK, which stamps
every file with its wall-clock creation time, a random ``FileId`` and footer
id, the output file name, and object ids taken from live SDK pointers. Two
exports of the same Unity object graph -- the same prefab instantiated by
several cutscenes, or one export run and the next -- therefore never share a
byte, which defeats hash-based dedup in the store and the asset list.

:func:`normalize_fbx` rewrites only those fields, in place and at their
original lengths, so node offsets stay valid and the file size is unchanged
(store freshness stamps compare sizes against the loose file):

- ``FBXHeaderExtension/CreationTimeStamp`` fields, ``CreationTime`` and
  ``FileId`` get fixed values, as does the footer id;
- the ``_p<16 hex>`` pathId suffix in ``DocumentUrl``/``SrcDocumentUrl`` is
  zeroed (the name otherwise stays, so same-name copies agree);
- every object id (the first ``L`` of each ``Objects`` child and of
  ``Documents/Document``) is renumbered by order of appearance, and every
  ``L`` property holding one of those ids -- connections, pose nodes,
  document roots -- is rewritten to match.

Geometry, materials, skins and transforms are untouched. Content that is
genuinely different (other meshes, materials or nodes) stays different. A
buffer that is not a binary FBX this reader understands is returned as is.
"""

from __future__ import annotations

import re
import struct

FBX_MAGIC = b"Kaydara FBX Binary  \x00"
# Blender's fixed export values; any constant works, these are recognisable.
FIXED_FILE_ID = bytes.fromhex("28b32aebb624ccc2bfc8b02aa92bfcf1")
FIXED_FOOTER_ID = bytes.fromhex("fabcab09d0c8d466b176fb831cf7267e")
FIXED_CREATION_TIME = b"1970-01-01 10:00:00:000"
FIXED_TIMESTAMP = {
    b"Year": 1970, b"Month": 1, b"Day": 1, b"Hour": 10,
    b"Minute": 0, b"Second": 0, b"Millisecond": 0,
}
# Renumbered ids start far from small integers such as the root id 0.
OBJECT_ID_BASE = 0x1000_0000_0000
_PATH_ID_SUFFIX = re.compile(rb"_p[0-9A-Fa-f]{16}(?=\.fbx$|$)")
_SCALAR_SIZES = {ord("Y"): 2, ord("C"): 1, ord("I"): 4, ord("F"): 4, ord("D"): 8, ord("L"): 8}


class _Node:
    __slots__ = ("name", "props", "children")

    def __init__(self, name: bytes, props: list[tuple[int, int, int]], children: list["_Node"]):
        self.name = name
        # (type code, value offset, value length) per property
        self.props = props
        self.children = children

    def child(self, name: bytes) -> "_Node | None":
        return next((node for node in self.children if node.name == name), None)


def _parse_props(buf: bytes, offset: int, count: int, end: int) -> list[tuple[int, int, int]]:
    props = []
    for _ in range(count):
        if offset >= end:
            raise ValueError("FBX property exceeds its declared block")
        code = buf[offset]
        offset += 1
        size = _SCALAR_SIZES.get(code)
        if size is not None:
            props.append((code, offset, size))
            offset += size
        elif code in (ord("S"), ord("R")):
            if offset + 4 > end:
                raise ValueError("short FBX string length")
            (size,) = struct.unpack_from("<I", buf, offset)
            props.append((code, offset + 4, size))
            offset += 4 + size
        elif code in b"fdlib":
            if offset + 12 > end:
                raise ValueError("short FBX array header")
            _length, _encoding, size = struct.unpack_from("<III", buf, offset)
            props.append((code, offset + 12, size))
            offset += 12 + size
        else:
            raise ValueError(f"unknown FBX property type {code!r}")
        if offset > end:
            raise ValueError("FBX property exceeds its declared block")
    if offset != end:
        raise ValueError("FBX property block size mismatch")
    return props


def _parse_nodes(buf: bytes, offset: int, end: int, wide: bool) -> tuple[list[_Node], int]:
    header = "<QQQ" if wide else "<III"
    header_size = 24 if wide else 12
    null_record = header_size + 1
    nodes = []
    while offset + null_record <= end:
        node_end, count, props_size = struct.unpack_from(header, buf, offset)
        if node_end == 0:
            if count or props_size or buf[offset + header_size]:
                raise ValueError("invalid FBX null record")
            return nodes, offset + null_record
        name_size = buf[offset + header_size]
        name_at = offset + header_size + 1
        name = bytes(buf[name_at:name_at + name_size])
        props_at = name_at + name_size
        if not offset + null_record <= props_at <= props_at + props_size <= node_end <= end:
            raise ValueError("FBX node bounds do not advance within the parent")
        props = _parse_props(buf, props_at, count, props_at + props_size)
        children, _ = _parse_nodes(buf, props_at + props_size, node_end, wide)
        nodes.append(_Node(name, props, children))
        offset = node_end
    return nodes, offset


def _walk(nodes: list[_Node]):
    for node in nodes:
        yield node
        yield from _walk(node.children)


def normalize_fbx(data: bytes) -> bytes:
    """Return ``data`` with its per-export noise replaced by fixed values."""
    if not data.startswith(FBX_MAGIC) or len(data) < 27:
        return data
    (version,) = struct.unpack_from("<I", data, 23)
    try:
        top, top_end = _parse_nodes(data, 27, len(data), version >= 7500)
    except (ValueError, struct.error, IndexError, RecursionError):
        return data
    buf = bytearray(data)
    by_name = {node.name: node for node in top}

    stamp = by_name.get(b"FBXHeaderExtension")
    stamp = stamp.child(b"CreationTimeStamp") if stamp else None
    for field in stamp.children if stamp else ():
        value = FIXED_TIMESTAMP.get(field.name)
        if value is not None and field.props and field.props[0][0] == ord("I"):
            struct.pack_into("<i", buf, field.props[0][1], value)
    file_id = by_name.get(b"FileId")
    if file_id and file_id.props and file_id.props[0][2] == len(FIXED_FILE_ID):
        buf[file_id.props[0][1]:file_id.props[0][1] + 16] = FIXED_FILE_ID
    created = by_name.get(b"CreationTime")
    if created and created.props and created.props[0][2] == len(FIXED_CREATION_TIME):
        at = created.props[0][1]
        buf[at:at + len(FIXED_CREATION_TIME)] = FIXED_CREATION_TIME
    header = by_name.get(b"FBXHeaderExtension")
    scene_info = header.child(b"SceneInfo") if header else None
    properties = scene_info.child(b"Properties70") if scene_info else None
    for prop in properties.children if properties else ():
        if len(prop.props) < 5:
            continue
        _, key_at, key_size = prop.props[0]
        if bytes(buf[key_at:key_at + key_size]) not in (b"DocumentUrl", b"SrcDocumentUrl"):
            continue
        _, at, size = prop.props[-1]
        value = bytes(buf[at:at + size])
        buf[at:at + size] = _PATH_ID_SUFFIX.sub(lambda m: b"_p" + b"0" * 16, value)

    ids: dict[bytes, bytes] = {}

    def own_id(node: _Node) -> None:
        if node.props and node.props[0][0] == ord("L"):
            _, at, _ = node.props[0]
            key = bytes(buf[at:at + 8])
            ids.setdefault(key, struct.pack("<q", OBJECT_ID_BASE + len(ids)))

    documents = by_name.get(b"Documents")
    for node in documents.children if documents else ():
        if node.name == b"Document":
            own_id(node)
    objects = by_name.get(b"Objects")
    for node in objects.children if objects else ():
        own_id(node)
    for node in _walk(top):
        for code, at, _ in node.props:
            if code == ord("L"):
                replacement = ids.get(bytes(buf[at:at + 8]))
                if replacement is not None:
                    buf[at:at + 8] = replacement

    if top_end + 16 <= len(buf):
        buf[top_end:top_end + 16] = FIXED_FOOTER_ID
    return bytes(buf)
