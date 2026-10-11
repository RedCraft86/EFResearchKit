"""Link combat stages to the Map page and to the missions that gate them.

Map links are identity joins only: a stage's ``DungeonTable.sceneId`` and
``levelId`` are shown when the Map page published that exact map or map
variant id. Mission links come from typed authored rows, never from a shared
scene or name match:

- ``GameMechanicConditionTable`` conditionType 19 (``MissionStateEqual``)
  names a mission that gates the stage's availability; conditionType 18
  (``QuestStateEqual``) names a quest whose ``<mission>_q#<n>`` id carries its
  mission. Both are unlock prerequisites, not owners or triggers.
- ``SubGameInstanceDataTable.dungeonMissionId`` co-carries the mission shell
  the stage runs in.

Names and Story targets are read from other pages' publications (Map index,
``missions.json`` and the Story index), so a link appears once that page is
built and is omitted otherwise.
"""
from __future__ import annotations

import json
from pathlib import Path

MISSION_CONDITIONS = {19: "unlock", 18: "unlockQuest"}


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else None


def map_targets(data_root: Path) -> dict[str, dict]:
    """Published Map ids, including variants that open through their parent."""
    index = _read(data_root / "map_recovery" / "index.json") or {}
    targets = {}
    for row in index.get("maps") or []:
        targets[row["id"]] = {"id": row["id"], "name": row.get("name") or row.get("label") or ""}
        for variant in row.get("variants") or []:
            if variant.get("id") and variant["id"] not in targets:
                targets[variant["id"]] = {"id": row["id"], "variant": variant["id"],
                                          "name": variant.get("name") or row.get("name") or ""}
    return targets


def story_targets(root: Path) -> dict[str, str]:
    """First published Story conversation for each mission id."""
    index = _read(root / "index.json") or {}
    first: dict[str, str] = {}
    for entry in index.get("entries") or []:
        if entry.get("m") and entry.get("k"):
            first.setdefault(entry["m"], entry["k"])
    return first


def mission_rows(conditions: dict | None, subgames: dict | None) -> dict[str, list[dict]]:
    """Typed stage→mission rows keyed by stage id."""
    rows: dict[str, list[dict]] = {}
    for condition in (conditions or {}).values():
        if not isinstance(condition, dict):
            continue
        relation = MISSION_CONDITIONS.get(condition.get("conditionType"))
        if relation is None:
            continue
        values = [value for parameter in condition.get("parameter") or [] if isinstance(parameter, dict)
                  for value in parameter.get("valueStringList") or [] if value]
        if not values:
            continue
        target = str(values[0])
        mission = target.split("_q#", 1)[0] if relation == "unlockQuest" else target
        row = {"id": mission, "relation": relation}
        if mission != target:
            row["quest"] = target
        rows.setdefault(str(condition.get("gameMechanicsId") or ""), []).append(row)
    for stage, raw in (subgames or {}).items():
        mission = raw.get("dungeonMissionId") if isinstance(raw, dict) else None
        if isinstance(mission, str) and mission:
            rows.setdefault(stage, []).append({"id": mission, "relation": "missionShell"})
    return rows


def link_stages(entries: list[dict], *, data_root: Path, root: Path,
                conditions: dict | None, subgames: dict | None) -> None:
    maps = map_targets(data_root)
    names = (_read(root / "missions.json") or {}).get("missionNames") or {}
    stories = story_targets(root)
    missions = mission_rows(conditions, subgames)
    for row in entries:
        links = []
        for role in ("sceneId", "levelId"):
            target = maps.get(row.get(role) or "")
            if target and all(link.get("variant", link["id"]) != target.get("variant", target["id"]) for link in links):
                links.append({**target, "role": "scene" if role == "sceneId" else "level"})
        seen = set()
        mission_links = []
        for mission in missions.get(row["id"], []):
            key = (mission["id"], mission["relation"])
            if key in seen:
                continue
            seen.add(key)
            mission_links.append({**mission, "name": names.get(mission["id"], ""),
                                  **({"story": stories[mission["id"]]} if mission["id"] in stories else {})})
        row["links"] = {"maps": links, "missions": mission_links}
