"""Decode PhysX version-15 cooked triangle geometry and CPU BV4 v3 metadata.

Format references (NVIDIA's original writer, not an inferred Unity render schema):
https://github.com/NVIDIAGameWorks/PhysX/blob/4.1/physx/source/physxcooking/src/mesh/TriangleMeshBuilder.cpp
https://github.com/NVIDIAGameWorks/PhysX/blob/4.1/physx/source/geomutils/src/mesh/GuMeshData.h
https://github.com/NVIDIAGameWorks/PhysX/blob/4.1/physx/source/geomutils/src/GuSerialize.cpp

The complete reader checks remap/material/adjacency framing, quantized or float
BV4 slabs, leaf coverage, bounds and edge masks through EOF. RTree and GPU tails
are refused. The prefix reader remains available for explicit partial probes.
Convex framing has its own reader. No WebUI publication or render fallback.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import struct

from scripts.game_data.cooked_stream import CookedReader, check_bounds


@dataclass(frozen=True)
class TriangleGeometry:
    version: int
    midphase: int
    flags: int
    index_width: int
    vertices: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]
    geometry_end: int
    opaque_tail_bytes: int


def read_triangle_geometry(payload: bytes) -> TriangleGeometry:
    """Fail closed on unsupported framing and invalid geometry prefix values."""
    if len(payload) < 28:
        raise ValueError(f"cooked header: need 28 bytes, got {len(payload)}")
    if payload[:3] != b"NXS" or payload[3] not in (0, 1) or payload[4:8] != b"MESH":
        raise ValueError("expected NXS endian byte followed by MESH triangle chunk")
    endian = "<" if payload[3] else ">"
    version, midphase, flags, vertex_count, triangle_count = struct.unpack_from(endian + "5I", payload, 8)
    if version != 15:
        raise ValueError(f"unsupported cooked triangle version {version}; expected 15")
    if midphase not in (0, 1):
        raise ValueError(f"unsupported triangle midphase {midphase}")
    if flags & ~0x3F or flags & 0x0C == 0x0C:
        raise ValueError(f"unsupported/conflicting triangle flags 0x{flags:X}")
    if not vertex_count or not triangle_count:
        raise ValueError("cooked triangle geometry has zero vertices or triangles")
    width = 1 if flags & 4 else 2 if flags & 8 else 4
    vertex_end = 28 + vertex_count * 12
    geometry_end = vertex_end + triangle_count * 3 * width
    if geometry_end > len(payload):
        raise ValueError(f"geometry prefix: need {geometry_end} bytes for {vertex_count} vertices/{triangle_count} triangles, got {len(payload)}")
    vertices = tuple(struct.iter_unpack(endian + "3f", memoryview(payload)[28:vertex_end]))
    for i, vertex in enumerate(vertices):
        if not all(math.isfinite(v) for v in vertex):
            raise ValueError(f"vertex {i}: non-finite coordinate")
    code = {1: "B", 2: "H", 4: "I"}[width]
    triangles = tuple(struct.iter_unpack(endian + "3" + code, memoryview(payload)[vertex_end:geometry_end]))
    for i, triangle in enumerate(triangles):
        if max(triangle) >= vertex_count:
            raise ValueError(f"triangle {i}: index {max(triangle)} outside vertex count {vertex_count}")
    return TriangleGeometry(version, midphase, flags, width, vertices, triangles,
                            geometry_end, len(payload) - geometry_end)


@dataclass(frozen=True)
class CookedTriangleMesh:
    geometry: TriangleGeometry
    metadata: dict
    spans: tuple[dict, ...]


def read_triangle_mesh(payload: bytes) -> CookedTriangleMesh:
    """Decode the complete observed BV4 v3 slab branch; reject unsupported tails.

    Layout and traversal: GuMeshFactory.cpp, GuBV4.cpp, GuBV4_Common.h,
    GuBV4Build.cpp in NVIDIA PhysX 4.1. No heuristic choice of a node layout.
    """
    geometry = read_triangle_geometry(payload)
    if payload[3] != 1:
        raise ValueError("complete BV4 reader requires little endian raw slabs")
    if geometry.midphase != 1 or geometry.flags & 32:
        raise ValueError("complete triangle reader supports BV4 CPU data only (no RTree/GPU tail)")
    reader = CookedReader(payload, "<" if payload[3] else ">", geometry.geometry_end)
    vertex_end = 28+12*len(geometry.vertices)
    reader.spans.extend((dict(field="mesh.header", start=0, end=28),
                         dict(field="mesh.vertices", start=28, end=vertex_end),
                         dict(field="mesh.triangles", start=vertex_end, end=geometry.geometry_end)))
    n = len(geometry.triangles)
    metadata = {"materials": [], "faceRemap": [], "adjacency": []}
    if geometry.flags & 1:
        metadata["materials"] = list(reader.unpack(f"{n}H", "materials"))
    if geometry.flags & 2:
        maximum = reader.u32("faceRemap.maxIndex")
        code = "B" if maximum <= 255 else "H" if maximum <= 65535 else "I"
        remap = reader.unpack(f"{n}{code}", "faceRemap.indices")
        if max(remap) != maximum:
            raise ValueError("faceRemap: recorded maximum differs from decoded indices")
        metadata["faceRemap"] = list(remap)
    if geometry.flags & 16:
        metadata["adjacency"] = list(reader.unpack(f"{3*n}I", "adjacency"))
    if reader.take(4, "bvh.magic") != b"BV4 ":
        raise ValueError("expected BV4 tree chunk")
    version = reader.u32("bvh.version")
    if version != 3:
        raise ValueError(f"unsupported BV4 version {version}; expected 3")
    local = reader.floats(4, "bvh.localSphere")
    init = reader.u32("bvh.initData")
    min_coeff = reader.floats(3, "bvh.minCoeff")
    max_coeff = reader.floats(3, "bvh.maxCoeff")
    quantized = reader.u32("bvh.quantized")
    if quantized not in (0, 1):
        raise ValueError(f"invalid BV4 quantized flag {quantized}")
    count = reader.u32("bvh.slotCount")
    if count % 4:
        raise ValueError("BV4 slab slot count must be a multiple of four")
    raw = reader.take(count * (16 if quantized else 28), "bvh.slabs")
    slots = []
    slab_size = 64 if quantized else 112
    for offset in range(0, len(raw), slab_size):
        if quantized:
            coords = struct.unpack_from(reader.endian + "24h4I", raw, offset)
        else:
            coords = struct.unpack_from(reader.endian + "24f4I", raw, offset)
        for slot in range(4):
            if quantized:
                lo = tuple(coords[axis*8+slot*2] * min_coeff[axis] for axis in range(3))
                hi = tuple(coords[axis*8+slot*2+1] * max_coeff[axis] for axis in range(3))
            else:
                lo = tuple(coords[axis*4+slot] for axis in range(3))
                hi = tuple(coords[(axis+3)*4+slot] for axis in range(3))
            slots.append(dict(bounds=lo+hi, data=coords[24+slot],
                              minimumZeroClamp=tuple(bool(quantized and coords[a*8+slot*2] == 0) for a in range(3))))
    visited, covered, leaves, zero_clamps = set(), set(), [], []
    if count:
        if init not in (0, 2, 4):
            raise ValueError(f"unsupported BV4 root initData {init}")
        pending = list(range((init >> 1)+2))
        while pending:
            index = pending.pop()
            if index >= count or index in visited:
                raise ValueError(f"BV4 invalid/repeated child slot {index}")
            visited.add(index)
            slot = slots[index]; data = slot["data"]
            if data == 0xFFFFFFFF:
                raise ValueError(f"BV4 active slot {index} is padding")
            if data & 1:
                first, size = data >> 5, (data >> 1) & 15
                if not size or first+size > n:
                    raise ValueError(f"BV4 leaf {index}: invalid triangle span {first}+{size}")
                indices = range(first, first+size)
                if any(i in covered for i in indices):
                    raise ValueError(f"BV4 leaf {index}: overlapping triangle span")
                covered.update(indices)
                vertices = tuple(geometry.vertices[v] for i in indices for v in geometry.triangles[i])
                # _FlattenQ truncates signed minima toward zero and refuses to
                # decrement when qmin==0. A small negative minimum can therefore
                # become zero. Only that exact writer branch gets one unit.
                error = tuple(abs(min_coeff[a]) if slot["minimumZeroClamp"][a] else 0 for a in range(3))
                check_bounds(slot["bounds"], vertices, f"BV4 leaf {index}", lower_error=error)
                for a in range(3):
                    residual = slot["bounds"][a]-min(v[a] for v in vertices)
                    if error[a] and residual > 0:
                        zero_clamps.append(dict(slot=index, axis=a, residual=residual, quantizationUnit=error[a]))
                leaves.append(dict(slot=index, firstTriangle=first, triangleCount=size))
            else:
                child, size = data >> 11, ((data >> 1) & 3)+2
                slot["precomputedSortMask"] = (data >> 3) & 255
                if size > 4 or child % 4 or child <= index or child+size > count:
                    raise ValueError(f"BV4 slot {index}: invalid child {child}+{size}")
                for i in range(child, child+size):
                    # Parent and child bounds are rounded independently. Two
                    # dequantization units bound their possible relative error.
                    error = tuple(2*max(abs(min_coeff[a]), abs(max_coeff[a])) for a in range(3)) if quantized else (0, 0, 0)
                    check_bounds(slot["bounds"], (slots[i]["bounds"][:3], slots[i]["bounds"][3:]), f"BV4 parent {index}", error)
                    pending.append(i)
        if covered != set(range(n)):
            raise ValueError("BV4 leaves do not cover every cooked triangle exactly once")
        if any(i not in visited and slot["data"] != 0xFFFFFFFF for i, slot in enumerate(slots)):
            raise ValueError("BV4 contains unreachable active slots")
    elif n > 4:
        raise ValueError("BV4 implicit tree requires at most four triangles")
    epsilon = reader.floats(1, "geomEpsilon")[0]
    bounds = reader.floats(6, "bounds")
    check_bounds(bounds, geometry.vertices, "collision bounds")
    if epsilon < 0 or local[3] < 0:
        raise ValueError("negative collision epsilon/sphere radius")
    extra_count = reader.u32("edgeFlags.count")
    if extra_count not in (0, n):
        raise ValueError(f"edge flag count {extra_count} differs from triangle count {n}")
    edge_flags = reader.take(extra_count, "edgeFlags.bytes")
    if any(v & ~0x3F for v in edge_flags):
        raise ValueError("triangle edge mask contains reserved bits outside silhouette/convex flags")
    reader.finish()
    metadata.update(bvh=dict(version=version, localSphere=local, initData=init,
                             minCoeff=min_coeff, maxCoeff=max_coeff, quantized=bool(quantized),
                             slots=slots, leaves=leaves, minimumZeroClamps=zero_clamps), bounds=bounds, geomEpsilon=epsilon,
                    edgeFlags=list(edge_flags), bytesConsumed=reader.offset)
    return CookedTriangleMesh(geometry, metadata, tuple(reader.spans))


def write_obj(path: Path, geometry: TriangleGeometry, *, complete: CookedTriangleMesh | None = None) -> None:
    """Write original collision coordinates/winding, with an explicit provenance tag."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as output:
        output.write("# Cooked collision surface; not Unity render geometry\n")
        output.write(f"# PhysX MESH version {geometry.version}; " + ("complete CPU BV4 payload validated\n" if complete else f"geometry prefix only; opaque tail bytes {geometry.opaque_tail_bytes}\n"))
        output.write("g cooked_collision\n")
        for vertex in geometry.vertices:
            output.write("v " + " ".join(format(value, ".9g") for value in vertex) + "\n")
        for triangle in geometry.triangles:
            output.write("f " + " ".join(str(value + 1) for value in triangle) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path, help="extracted cooked triangle buffer, not a whole Unity object")
    parser.add_argument("--obj", type=Path, help="optional collision surface OBJ under reports/ or tmp/")
    parser.add_argument("--prefix-only", action="store_true", help="validate geometry prefix only; leave the tail explicitly opaque")
    args = parser.parse_args()
    payload = args.payload.read_bytes()
    geometry = read_triangle_geometry(payload)
    complete = None if args.prefix_only else read_triangle_mesh(payload)
    if args.obj:
        write_obj(args.obj, geometry, complete=complete)
    print(json.dumps({"source": str(args.payload), "sha256": hashlib.sha256(payload).hexdigest(),
                      "boundary": "geometryPrefixOnly" if complete is None else "completeCpuBv4Payload", "version": geometry.version,
                      "midphase": geometry.midphase, "flags": geometry.flags,
                      "indexWidth": geometry.index_width, "vertexCount": len(geometry.vertices),
                      "triangleCount": len(geometry.triangles), "geometryEnd": geometry.geometry_end,
                      "opaqueTailBytes": geometry.opaque_tail_bytes if complete is None else 0,
                      "bytesConsumed": geometry.geometry_end if complete is None else complete.metadata["bytesConsumed"],
                      "fieldSpans": None if complete is None else complete.spans,
                      "bvhQuantized": None if complete is None else complete.metadata["bvh"]["quantized"]}, indent=2))


if __name__ == "__main__":
    main()
