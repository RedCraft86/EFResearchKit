"""Activity navigation from authored dungeon references and mode destinations."""
from __future__ import annotations

import json


TABLES = (
    "ActivityCharTrial", "ActivityConditionalMultiStageTable",
    "ActivityConditionalMultiStageCompleteConditionTable", "SystemJumpTable",
    "SeasonTowerTable", "SeasonTowerGameGroupTable",
)


def activity_links(tables: dict, localized) -> dict[str, list[dict]]:
    activities = tables.get("ActivityTable", {})
    dungeons = tables.get("DungeonTable", {})
    links: dict[str, list[dict]] = {}

    def add(activity_id, dungeon_id, relation, source, **fields):
        if activity_id not in activities or dungeon_id not in dungeons:
            return
        rows = links.setdefault(dungeon_id, [])
        if any(row["id"] == activity_id for row in rows):
            return
        rows.append({"id": activity_id, "name": localized(activities[activity_id].get("name")) or activity_id,
                     "relation": relation, "source": source, **fields})

    for activity_id, activity in tables.get("ActivityDungeonTable", {}).items():
        for key, config in (activity.get("gameMap") or {}).items():
            add(activity_id, config.get("gameId"), "activityDungeon",
                {"table": "ActivityDungeonTable", "row": activity_id, "field": f"gameMap.{key}.gameId"},
                unlockStage=config.get("gameUnlockStage") or "", closeStage=config.get("gameCloseStage") or "",
                closeOnActivityEnd=config.get("gameCloseOnActivityEnd"))

    for key, row in tables.get("ActivityCharTrial", {}).items():
        add(row.get("activityId"), row.get("dungeonId"), "characterTrial",
            {"table": "ActivityCharTrial", "row": key, "field": "dungeonId"})

    conditions = tables.get("ActivityConditionalMultiStageCompleteConditionTable", {})
    for key, row in tables.get("ActivityConditionalMultiStageTable", {}).items():
        activity_id = row.get("activityId")
        if activity_id != key:
            continue
        for stage_id, stage in (row.get("stageList") or {}).items():
            if stage.get("stageId") != stage_id:
                continue
            for index, condition in enumerate(conditions.get(stage_id, {}).get("conditionList") or []):
                if condition.get("stageId") != stage_id:
                    continue
                # This is a literal condition reference, not inferred activity
                # ownership or a claim about the anonymous condition's execution.
                for param in condition.get("parameters") or []:
                    for dungeon_id in param.get("valueStringList") or []:
                        add(activity_id, dungeon_id, "completionReference",
                            {"table": "ActivityConditionalMultiStageCompleteConditionTable", "row": stage_id,
                             "field": f"conditionList.{index}.parameters"},
                            activityStage=stage_id, conditionType=condition.get("conditionType"))

    jumps = tables.get("SystemJumpTable", {})
    groups = tables.get("SeasonTowerGameGroupTable", {})
    for activity_id, activity in activities.items():
        jump_id = activity.get("detailJumpId")
        jump = jumps.get(jump_id, {})
        if jump.get("phaseId") != "SeasonTowerMainHud":
            continue
        try:
            args = json.loads(jump.get("phaseArgs") or "{}")
        except (TypeError, ValueError):
            continue
        if args != {}:
            continue
        # An unselected mode destination exposes stored season configurations;
        # it does not select the current live season, week, or star difficulty.
        for season_id, season in tables.get("SeasonTowerTable", {}).items():
            for week_id, week in (season.get("weeks") or {}).items():
                for group_id in week.get("includeGameIdList") or []:
                    group = groups.get(group_id)
                    if not group:
                        continue
                    for star, config in (group.get("stars") or {}).items():
                        add(activity_id, config.get("gameId"), "modeDestination",
                            {"table": "SeasonTowerGameGroupTable", "row": group_id, "field": f"stars.{star}.gameId"},
                            destination={"jumpId": jump_id, "season": season_id, "week": week_id})
    return links
