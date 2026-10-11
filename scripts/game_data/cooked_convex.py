"""Decode PhysX CVXM v13/CLHL v9 cooked convex hulls with exact consumption.

Framing and meanings: NVIDIA PhysX 4.1 GuConvexMesh.cpp, GuConvexMeshData.h,
ConvexMeshBuilder.cpp, ConvexHullBuilder.cpp and BigConvexDataBuilder.cpp.
Includes optional GPU edge endpoints and SUPM/GAUS v0, VALE v2 support maps.
No scene ownership, transforms, render attributes or WebUI publication inferred.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import argparse
from dataclasses import dataclass
import math
import hashlib
import json
import struct
from pathlib import Path

from scripts.game_data.cooked_stream import CookedReader, check_bounds, stream_header


@dataclass(frozen=True)
class CookedConvexMesh:
    vertices: tuple[tuple[float, float, float], ...]
    polygons: tuple[tuple[int, ...], ...]
    metadata: dict
    spans: tuple[dict, ...]


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _read_gauss(reader: CookedReader, vertices: tuple, edges: dict, polygons: list) -> dict:
    """Decode and independently check support extrema and hull valency lists."""
    outer_endian = reader.endian
    for chunk in (b"SUPM", b"GAUS"):
        version = stream_header(reader, b"ICE", chunk, "gauss."+chunk.decode())
        if version != 0:
            raise ValueError(f"unsupported {chunk.decode()} version {version}; expected 0")
    subdiv, count = reader.unpack("2I", "gauss.counts")
    if subdiv < 2 or count != 6*subdiv*subdiv or count > 65535:
        raise ValueError(f"Gauss invalid subdivision/sample counts {subdiv}/{count}")
    samples = reader.take(count*2, "gauss.samples")
    nv = len(vertices)
    if max(samples) >= nv:
        raise ValueError("Gauss support sample references a missing hull vertex")
    version = stream_header(reader, b"ICE", b"VALE", "gauss.VALE")
    if version != 2:
        raise ValueError(f"unsupported VALE version {version}; expected 2")
    stored_nv, adjacent_count = reader.unpack("2I", "gauss.valencyCounts")
    if stored_nv != nv or adjacent_count != 2*len(edges):
        raise ValueError(f"Gauss valency counts disagree with hull: {stored_nv}/{adjacent_count}")
    maximum = reader.u32("gauss.maxValency")
    if maximum > 65535:
        raise ValueError(f"Gauss max valency exceeds UInt16: {maximum}")
    valencies = reader.unpack(f"{nv}"+("B" if maximum <= 255 else "H"), "gauss.valencies")
    if max(valencies) != maximum or sum(valencies) != adjacent_count:
        raise ValueError("Gauss valencies disagree with recorded maximum/adjacency count")
    adjacent = reader.take(adjacent_count, "gauss.adjacentVertices")
    offset, lists = 0, []
    neighbors = [set() for _ in vertices]
    wedges = [Counter() for _ in vertices]
    for a, b in edges:
        neighbors[a].add(b); neighbors[b].add(a)
    for polygon in polygons:
        for i,v in enumerate(polygon):
            wedges[v][tuple(sorted((polygon[i-1],polygon[(i+1)%len(polygon)])))] += 1
    for v, size in enumerate(valencies):
        values = tuple(adjacent[offset:offset+size]); offset += size
        if len(set(values)) != size or set(values) != neighbors[v]:
            raise ValueError(f"Gauss adjacency for vertex {v} disagrees with hull edges")
        ordered_wedges = Counter(tuple(sorted((a,values[(i+1)%size]))) for i,a in enumerate(values))
        if ordered_wedges != wedges[v]:
            raise ValueError(f"Gauss adjacency order for vertex {v} disagrees with incident polygon wedges")
        lists.append(values)
    # Writer face order and lattice directions from precompute(). Normalizing
    # directions does not change extrema. Accept ties, including float rounding.
    for j in range(subdiv):
        for i in range(j, subdiv):
            u, v = 1-2*i/(subdiv-1), 1-2*j/(subdiv-1)
            directions = ((-1,u,v),(1,u,v),(v,-1,u),(v,1,u),(u,v,-1),(u,v,1),
                          (-1,v,u),(1,v,u),(u,-1,v),(u,1,v),(v,u,-1),(v,u,1))
            for k, direction in enumerate(directions):
                offset = (k%6)*subdiv*subdiv+(j+i*subdiv if k<6 else i+j*subdiv)
                projections = [dot(direction, p) for p in vertices]
                tolerance = 2e-5*max(1.0, *(abs(x) for x in projections))
                if (projections[samples[offset]] > min(projections)+tolerance
                        or projections[samples[offset+count]] < max(projections)-tolerance):
                    raise ValueError(f"Gauss sample {offset} disagrees with minimum/maximum hull projection")
    reader.endian = outer_endian
    return dict(subdivision=subdiv, sampleCount=count, minimumVertices=list(samples[:count]),
                maximumVertices=list(samples[count:]), valencies=valencies, adjacentVertices=lists)


def _internal_objects(planes: list, center: tuple, bounds: tuple) -> tuple:
    """Recompute the writer's internal sphere and axis-aligned box heuristic."""
    # Preserve float32 operation boundaries. Near-axis planes can make the
    # ray/plane numerator cancel; float64 produces a different limiting box.
    def f(value):
        try:
            result = struct.unpack("<f",struct.pack("<f",value))[0]
        except (OverflowError, struct.error) as error:
            raise ValueError("convex internal object computation overflows float32") from error
        if not math.isfinite(result):
            raise ValueError("convex internal object computation is not finite")
        return result
    def dot32(normal):
        return f(f(f(normal[0]*center[0])+f(normal[1]*center[1]))+f(normal[2]*center[2]))
    radius = min(abs(f(dot32(p[:3])+p[3])) for p in planes)
    r = f(radius/f(math.sqrt(3)))
    lengths = [f(bounds[a+3]-bounds[a]) for a in range(3)]
    largest = max(range(3), key=lambda a: lengths[a])
    e0, e1 = (largest+1)%3, (largest+2)%3
    if lengths[e0] < lengths[e1]:
        e0, e1 = e1, e0
    extent = math.inf
    for plane in planes:
        normal, base = plane[:3], f(-plane[3]-dot32(plane[:3]))
        if abs(normal[largest]) < 1e-7:
            continue
        n0,n1,inverse = f(r*normal[e0]),f(r*normal[e1]),f(1/normal[largest])
        for a in (-1,1):
            for b in (-1,1):
                extent = min(extent,max(abs(f(f(f(base+a*n0)+b*n1)*inverse)),r))
    side = math.inf
    for plane in planes:
        normal, base = plane[:3], f(-plane[3]-dot32(plane[:3]))
        n0 = f(extent*normal[largest])
        for denominator in (f(normal[e0]+normal[e1]),f(normal[e0]-normal[e1])):
            if abs(denominator) < 1e-7:
                continue
            for sign in (-1,1):
                side = min(side,max(abs(f(f(base+sign*n0)/denominator)),r))
    extents = [side]*3; extents[largest] = extent
    return radius,*extents


def read_convex_mesh(payload: bytes) -> CookedConvexMesh:
    reader = CookedReader(payload, "<")
    version = stream_header(reader, b"NXS", b"CVXM", "convex")
    if version != 13:
        raise ValueError(f"unsupported convex version {version}; expected 13")
    flags = reader.u32("convex.flags")
    if flags:
        raise ValueError(f"unsupported convex flags 0x{flags:X}")
    outer_endian = reader.endian
    hull_version = stream_header(reader, b"ICE", b"CLHL", "hull")
    if hull_version != 9:
        raise ValueError(f"unsupported convex hull version {hull_version}; expected 9")
    nv, edge_bits, np, nr = reader.unpack("4I", "hull.counts")
    if not 4 <= nv <= 255 or not 4 <= np <= 255 or edge_bits > 65535:
        raise ValueError(f"invalid convex counts: vertices={nv}, edgeBits={edge_bits}, polygons={np}")
    ne, gpu = edge_bits & 32767, bool(edge_bits & 32768)
    flat = reader.floats(nv*3, "hull.vertices")
    vertices = tuple(tuple(flat[i:i+3]) for i in range(0, len(flat), 3))
    records = [reader.unpack("4fHBB", f"hull.polygon[{i}]") for i in range(np)]
    refs = reader.take(nr, "hull.vertexRefs")
    faces_by_edges = reader.take(ne*2, "hull.facesByEdges")
    faces_by_vertices = reader.take(nv*3, "hull.facesByVertices")
    endpoints = reader.unpack(f"{ne*2}H", "hull.gpuEdges") if gpu else ()
    polygons, planes, residuals, edge_faces, used_refs = [], [], [], defaultdict(list), set()
    tolerance = 2e-5 * max(1.0, *(abs(v) for vertex in vertices for v in vertex))
    # PhysX's hull checker uses a scale-dependent cooking tolerance, not exact
    # coplanarity. Preserve residuals: stored planes and polygon vertices can differ.
    plane_tolerance = 0.02 * max(1.0, sum(max(abs(v[a]) for v in vertices) for a in range(3)))
    for i, record in enumerate(records):
        plane, start, count, minimum = record[:4], *record[4:]
        if not all(math.isfinite(v) for v in plane) or abs(dot(plane[:3], plane[:3])-1) > 2e-4:
            raise ValueError(f"convex polygon {i}: invalid plane normal")
        if count < 3 or start+count > nr or minimum >= nv:
            raise ValueError(f"convex polygon {i}: invalid reference range/minIndex")
        occupied = set(range(start, start+count))
        if used_refs & occupied:
            raise ValueError(f"convex polygon {i}: overlapping reference range")
        used_refs.update(occupied)
        polygon = tuple(refs[start:start+count])
        if max(polygon) >= nv or len(set(polygon)) != count:
            raise ValueError(f"convex polygon {i}: invalid/repeated vertex reference")
        projections = [dot(plane[:3], v) for v in vertices]
        if abs(projections[minimum]-min(projections)) > tolerance:
            raise ValueError(f"convex polygon {i}: minIndex is not the minimum projection")
        residuals.append(max(abs(projections[v]+plane[3]) for v in polygon))
        if any(v+plane[3] > plane_tolerance for v in projections):
            raise ValueError(f"convex polygon {i}: hull vertex outside its plane")
        normal = (0.0, 0.0, 0.0)
        for j, a in enumerate(polygon):
            b = polygon[(j+1)%count]
            edge_faces[tuple(sorted((a,b)))].append((i,a,b))
            product = cross(vertices[a], vertices[b])
            normal = tuple(normal[k]+product[k] for k in range(3))
        if dot(normal, plane[:3]) <= 0:
            raise ValueError(f"convex polygon {i}: winding disagrees with plane")
        polygons.append(polygon); planes.append(plane)
    if len(used_refs) != nr or len(edge_faces) != ne:
        raise ValueError("convex topology does not match reference/edge counts")
    if nv-ne+np != 2:
        raise ValueError("convex topology fails the closed hull Euler relation")
    for edge, faces in edge_faces.items():
        if len(faces) != 2 or faces[0][1:] != faces[1][1:][::-1]:
            raise ValueError(f"convex edge {edge}: not a closed oriented manifold")
    stored_pairs = Counter(tuple(sorted(faces_by_edges[i:i+2])) for i in range(0,len(faces_by_edges),2))
    expected_pairs = Counter(tuple(sorted(f[0] for f in faces)) for faces in edge_faces.values())
    if stored_pairs != expected_pairs:
        raise ValueError("convex facesByEdges disagrees with polygon topology")
    for v in range(nv):
        faces = faces_by_vertices[v*3:v*3+3]
        if faces == b"\xff\xff\xff":
            continue  # Explicit PhysX fallback when three incident faces are unavailable.
        if len(set(faces)) != 3 or any(f >= np or v not in polygons[f] for f in faces):
            raise ValueError(f"convex vertex {v}: facesByVertices disagrees with topology")
    if gpu:
        pairs = Counter(tuple(sorted(endpoints[i:i+2])) for i in range(0,len(endpoints),2))
        if pairs != Counter(edge_faces.keys()):
            raise ValueError("convex GPU edge endpoints disagree with topology")
        for i in range(ne):
            edge = tuple(sorted(endpoints[2*i:2*i+2]))
            if sorted(faces_by_edges[2*i:2*i+2]) != sorted(f[0] for f in edge_faces[edge]):
                raise ValueError(f"convex GPU edge {i}: face map disagrees with endpoints")
    reader.endian = outer_endian
    epsilon = reader.floats(1, "convex.unusedEpsilon")[0]
    bounds = reader.floats(6, "convex.bounds")
    check_bounds(bounds, vertices, "convex bounds")
    mass = reader.floats(1, "convex.mass")[0]
    inertia = reader.floats(9, "convex.inertia") if mass != -1 else ()
    center = reader.floats(3, "convex.centerOfMass") if mass != -1 else ()
    gauss = reader.floats(1, "convex.gaussMapFlag")[0]
    if gauss not in (-1, 1):
        raise ValueError(f"unsupported convex Gauss-map branch {gauss}")
    gauss_data = _read_gauss(reader, vertices, edge_faces, polygons) if gauss == 1 else None
    internal = reader.floats(4, "convex.internalObjects")
    if internal[0] < 0 or any(e <= 0 for e in internal[1:]):
        raise ValueError("invalid convex internal radius/extents")
    computed_internal = _internal_objects(planes, center, bounds) if center else ()
    if computed_internal and any(abs(a-b) > 2e-5*max(1,abs(b),*(abs(x) for x in center)) for a,b in zip(internal,computed_internal)):
        raise ValueError("convex internal radius/extents differ from plane/center writer heuristic")
    reader.finish()
    volume, centroid, second = 0.0, [0.0]*3, [[0.0]*3 for _ in range(3)]
    anchor = tuple(sum(v[a] for v in vertices)/nv for a in range(3))
    for polygon in polygons:
        a = vertices[polygon[0]]
        for j in range(1, len(polygon)-1):
            b, c = vertices[polygon[j]], vertices[polygon[j+1]]
            points = [tuple(p[k]-anchor[k] for k in range(3)) for p in (a,b,c)]
            v = dot(points[0], cross(points[1],points[2]))/6
            volume += v
            for axis in range(3):centroid[axis] += v*sum(p[axis] for p in points)/4
            for x in range(3):
                for y in range(3):
                    second[x][y] += v*(sum(p[x]*p[y] for p in points)+sum(p[x] for p in points)*sum(p[y] for p in points))/20
    if volume <= 0:
        raise ValueError("convex hull has non-positive oriented volume")
    center_relative = tuple(v/volume for v in centroid)
    centroid = tuple(center_relative[a]+anchor[a] for a in range(3))
    covariance = [[second[x][y]-volume*center_relative[x]*center_relative[y] for y in range(3)] for x in range(3)]
    computed_inertia = tuple((sum(covariance[a][a] for a in range(3)) if x == y else 0)-covariance[x][y] for y in range(3) for x in range(3))
    # ConvexMeshBuilder::computeMassInfo serializes getOriginInertia, not the
    # center-of-mass tensor. Apply the parallel-axis term for local origin.
    origin_inertia = tuple(computed_inertia[y*3+x] + volume*((dot(centroid,centroid) if x == y else 0)-centroid[x]*centroid[y]) for y in range(3) for x in range(3))
    if mass != -1:
        if mass <= 0 or abs(mass-volume) > 2e-4*max(volume,1e-6):
            raise ValueError("convex stored mass differs from unit-density hull volume")
        if any(abs(center[i]-centroid[i]) > tolerance for i in range(3)):
            raise ValueError("convex stored center of mass differs from hull geometry")
        inertia_tolerance = 3e-4 * max(max(abs(x) for x in origin_inertia), 1e-8)
        if any(abs(a-b) > inertia_tolerance for a,b in zip(inertia,origin_inertia)):
            raise ValueError("convex stored inertia differs from integrated hull geometry")
    metadata = dict(version=version, hullVersion=hull_version, planes=planes,
                    minIndices=[r[-1] for r in records], edgeCount=ne,
                    facesByEdges=list(faces_by_edges), facesByVertices=list(faces_by_vertices),
                    gpuEdges=list(endpoints), bounds=bounds, unusedEpsilon=epsilon, mass=mass,
                    inertia=inertia, centerOfMass=center, internalObjects=internal,
                    gaussMap=gauss_data,
                    computedInternalObjects=computed_internal,
                    volume=volume, computedCenterOfMass=centroid, computedOriginInertia=origin_inertia,
                    computedCenterInertia=computed_inertia,
                    planeVertexResiduals=residuals, cookingPlaneTolerance=plane_tolerance, bytesConsumed=reader.offset)
    return CookedConvexMesh(vertices, tuple(polygons), metadata, tuple(reader.spans))


def write_convex_obj(path: Path, mesh: CookedConvexMesh) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as output:
        output.write("# Cooked convex collision hull; original polygon winding and local coordinates\ng cooked_convex_collision\n")
        for v in mesh.vertices:output.write("v " + " ".join(format(x, ".9g") for x in v) + "\n")
        for p in mesh.polygons:output.write("f " + " ".join(str(v+1) for v in p) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("--obj", type=Path, help="optional collision hull OBJ under reports/ or tmp/")
    args = parser.parse_args()
    payload = args.payload.read_bytes()
    mesh = read_convex_mesh(payload)
    if args.obj:
        write_convex_obj(args.obj, mesh)
    print(json.dumps(dict(source=str(args.payload), sha256=hashlib.sha256(payload).hexdigest(),
                          boundary="completeConvexPayload", vertexCount=len(mesh.vertices), polygonCount=len(mesh.polygons),
                          bytesConsumed=mesh.metadata["bytesConsumed"], gaussMap=mesh.metadata["gaussMap"] is not None,
                          fieldSpans=mesh.spans), indent=2))


if __name__ == "__main__":
    main()
