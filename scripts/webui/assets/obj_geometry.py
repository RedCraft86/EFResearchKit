"""Check exported OBJ geometry without retaining a complete mesh in memory."""
from __future__ import annotations

import math
import re
from pathlib import Path


def obj_has_drawable_faces(path: Path) -> bool:
    """Match the preview's index validation and nondegenerate triangle fan.

    Group-only markers and point/line-only files are valid inventory entries,
    but cannot produce a surface preview. Stop at the first drawable face.
    Read errors propagate instead of classifying unavailable data as empty.
    """
    vertex_count = 0
    with path.open(encoding="utf-8-sig") as stream:
        for line in stream:
            # OBJ exports put UV and normal records before faces. Ignore those
            # large sections without splitting or converting their numbers.
            line = line.lstrip()
            if len(line) < 2 or line[0] not in {"v", "f"} or not line[1].isspace():
                continue
            parts = line.partition("#")[0].split()
            if not parts:
                continue
            if parts[0] == "v" and len(parts) >= 4:
                try:
                    if all(math.isfinite(float(value)) for value in parts[1:4]):
                        vertex_count += 1
                except ValueError:
                    pass
            elif parts[0] == "f" and len(parts) >= 4:
                face = []
                for token in parts[1:]:
                    value = token.split("/", 1)[0]
                    if not re.fullmatch(r"-?[0-9]+", value):
                        break
                    raw = int(value)
                    index = raw - 1 if raw > 0 else vertex_count + raw
                    if raw == 0 or not 0 <= index < vertex_count:
                        break
                    face.append(index)
                else:
                    if any(len({face[0], face[i], face[i + 1]}) == 3 for i in range(1, len(face) - 1)):
                        return True
    return False
