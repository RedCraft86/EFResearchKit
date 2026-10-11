"""Project source-bound timelines from saved, complete Mission entry captures.

Publishes offline reports only. Authored dependencies, same-thread entry order,
restoration flags and unowned playback remain separate evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any

from scripts.common import check_installed_native_inputs
from scripts.game_data import mission_trace_inspect as trace
from scripts.game_data.mission_trace_replay import Replay, ReplayError, fingerprint, load_inspection, require_bound

SCHEMA = "endfield.mission-capture-timeline.v1"
BOUNDARY = (
    "Entry observations joined through explicit mission/quest identities and archived questDic membership. "
    "Configured predecessors and same-thread observed order do not establish server policy, successful "
    "returns, nesting, asynchronous causality, playback ownership or a universal mission/Story order."
)


def _text(value: Any) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 160


def archived_quests(replay: Replay, limits: trace.Limits) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    sources, assignments = trace.source_bindings(replay.session, replay.artifacts, limits, True)
    quests: dict[str, list[dict[str, Any]]] = defaultdict(list)
    documents: dict[str, Any] = {}
    for quest_id, owners in assignments.items():
        for owner in owners:
            name = owner["source"]
            if name not in documents:
                documents[name] = trace.bound_object(replay.artifacts, name, limits)
            quest = documents[name]["questDic"][quest_id]

            def source_check(condition: bool, check: str, expected: str, actual: Any) -> None:
                pin = {"path": str(replay.artifacts[name]["path"]), "sha256": owner["sourceSha256"]}
                require_bound(condition, check, f"Mission timeline: {check}: {owner['missionId']}/{quest_id}, {name}",
                              pin, expected, actual, missionId=owner["missionId"], questId=quest_id)

            predecessors = quest.get("prevQuestIdList", [])
            valid_predecessors = (isinstance(predecessors, list) and len(predecessors) <= 1024 and
                                  all(_text(value) for value in predecessors))
            source_check(valid_predecessors and len(set(predecessors)) == len(predecessors), "archived_predecessor_list",
                         "At most 1024 distinct nonempty string quest IDs",
                         {"type": type(predecessors).__name__,
                          "count": len(predecessors) if isinstance(predecessors, (dict, list)) else None})
            main_path = documents[name].get("mainPathQuests", [])
            source_check(isinstance(main_path, list) and len(main_path) <= 4096 and
                         all(_text(value) and value in documents[name]["questDic"] for value in main_path) and
                         len(set(main_path)) == len(main_path), "archived_main_path",
                         "At most 4096 distinct quest IDs explicitly present in this mission",
                         {"type": type(main_path).__name__, "count": len(main_path) if isinstance(main_path, list) else None})
            objectives = quest.get("objectiveList", [])
            source_check(isinstance(objectives, list) and len(objectives) <= 1024, "archived_objective_list",
                         "At most 1024 objective rows", {"type": type(objectives).__name__})
            conditions = []

            def visit(condition: Any, path: str, depth: int = 0) -> None:
                trace.require(depth <= 32 and len(conditions) < 4096,
                              f"Mission timeline: condition budget: {quest_id}, {name}")
                if condition is None:
                    return
                trace.require(isinstance(condition, dict), f"Mission timeline: invalid condition: {quest_id}, {path}")
                identity, kind = condition.get("uniqueId"), condition.get("$type")
                trace.require(_text(identity) and isinstance(kind, str) and 0 < len(kind) <= 512,
                              f"Mission timeline: missing condition identity/type: {quest_id}, {path}")
                conditions.append({"conditionId": identity, "storedType": kind, "sourcePath": path,
                                   "constantOperands": {key: value["constValue"] for key, value in condition.items()
                                                        if isinstance(value, dict) and "constValue" in value}})
                if kind.split(",", 1)[0] == "Beyond.Gameplay.CombineCondition":
                    children = condition.get("subConditions")
                    trace.require(isinstance(children, list) and len(children) <= 1024,
                                  f"Mission timeline: invalid combined children: {quest_id}, {path}")
                    for index, child in enumerate(children):
                        visit(child, f"{path}.subConditions[{index}]", depth + 1)

            for index, objective in enumerate(objectives):
                trace.require(isinstance(objective, dict), f"Mission timeline: invalid objective: {quest_id}, {index}")
                visit(objective.get("condition"), f"questDic[{quest_id}].objectiveList[{index}].condition")
            quests[quest_id].append({**owner, "questId": quest_id, "prevQuestIdList": predecessors,
                                    "mainPathQuests": main_path, "conditions": conditions})
    return dict(quests), sources


def project(entries: list[dict[str, Any]], quests: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Pure bounded projection; no ID prefixes, nearby entries or receiver guesses."""
    condition_candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for owners in quests.values():
        for owner in owners:
            for condition in owner["conditions"]:
                condition_candidates[condition["conditionId"]].append({
                    "missionId": owner["missionId"], "questId": owner["questId"],
                    "source": owner["source"], "sourceSha256": owner["sourceSha256"], **condition})
    timelines: dict[str, list[dict[str, Any]]] = defaultdict(list)
    observations, unassigned, conflicts = [], [], []
    by_sequence: dict[int, dict[str, Any]] = {}
    calls, flags = Counter(), Counter()
    for row in sorted(entries, key=lambda item: item["sequence"]):
        if row.get('phase', 'entry') not in ('entry', 'enter'):
            continue  # Returned field snapshots are distinct from a lifecycle entry.
        values, enums = {}, {}
        for field in row["fields"]:
            trace.require(field.get("state") in (1, 4) and field["label"] not in values,
                          f"Mission timeline: sequence {row['sequence']}, invalid/duplicate field {field.get('label')}")
            values[field["label"]] = field.get("value")
            if "enumNames" in field:
                enums[field["label"]] = field["enumNames"]
        entry = {"sequence": row["sequence"], "threadId": row["threadId"], "qpc": row["qpc"],
                 "secondsFromStart": row["secondsFromStart"], "hook": row["hook"], "entryFields": values,
                 "enumNames": enums, "missionId": None, "questId": None, "association": "unresolved"}
        if 'invocationId' in row:
            entry.update({k: row[k] for k in ('invocationId', 'parentInvocationId', 'depth', 'phase')})
        calls[row["hook"]] += 1
        quest_ids = {values[key] for key in ("questId", "parentQuestId") if _text(values.get(key))}
        direct = values.get("missionId") if _text(values.get("missionId")) else None
        owners = quests.get(next(iter(quest_ids)), []) if len(quest_ids) == 1 else []
        if len(quest_ids) == 1:
            entry["questId"] = next(iter(quest_ids))
        if len(quest_ids) > 1:
            entry["association"] = "conflicting_quest_carriers"
            conflicts.append({"sequence": row["sequence"], "hook": row["hook"], "questIds": sorted(quest_ids)})
        elif len(owners) > 1:
            entry["association"] = "ambiguous_archived_quest_membership"
            entry["candidateMemberships"] = owners
        elif owners and direct is not None and direct != owners[0]["missionId"]:
            entry["association"] = "conflicting_mission_and_quest_carriers"
            conflicts.append({"sequence": row["sequence"], "hook": row["hook"], "missionId": direct,
                              "questId": entry["questId"], "archivedMissionId": owners[0]["missionId"]})
        elif direct is not None:
            entry.update(missionId=direct, association="explicit_entry_mission_id")
        elif owners:
            entry.update(missionId=owners[0]["missionId"], association="explicit_entry_quest_and_archived_membership")
        elif quest_ids:
            entry["association"] = "quest_missing_from_archive"
        if owners and len(owners) == 1:
            entry["archivedMembership"] = {key: owners[0][key] for key in ("missionId", "source", "sourceSha256", "prevQuestIdList")}
        identity = values.get("conditionId", values.get("incomingConditionId"))
        if _text(identity):
            entry["storedConditionCandidates"] = condition_candidates.get(identity, [])
            entry["conditionBoundary"] = "Stored ID candidates only; a condition ID does not supply a live quest owner or an incoming numeric-map value."
        if row["hook"] == "mission.StartQuest":
            field = next((field for field in row["fields"] if field["label"] == "isNewQuest"), {})
            if field.get("type") == "bool" and field.get("canonicalBool") is True and type(values.get("isNewQuest")) is bool:
                entry["startKind"] = "new_quest_entry" if values["isNewQuest"] else "restoration_entry"
            else:
                entry["startKind"] = "unresolved_start_flag"
            flags[entry["startKind"]] += 1
        elif row["hook"] == "mission.StartMission":
            # stateChanged=false is a recorded flag, not an inferred accept event.
            entry["startKind"] = "mission_start_entry"
            flags["mission_start_entry"] += 1
        observations.append(entry)
        by_sequence[entry["sequence"]] = entry
        if entry["missionId"] is None:
            unassigned.append(entry["sequence"])
        else:
            timelines[entry["missionId"]].append(entry["sequence"])
    thread_last: dict[int, dict[str, Any]] = {}
    clock_conflicts = []
    for entry in observations:
        previous = thread_last.get(entry["threadId"])
        if previous and entry["qpc"] < previous["qpc"]:
            clock_conflicts.append({"threadId": entry["threadId"], "beforeSequence": previous["sequence"],
                                    "afterSequence": entry["sequence"]})
        thread_last[entry["threadId"]] = entry
    unsafe_threads = {item["threadId"] for item in clock_conflicts}
    successes: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for entry in observations:
        if entry["hook"] == "mission.SucceedQuest" and entry["missionId"] and entry["questId"]:
            successes[entry["missionId"], entry["questId"]].append(entry)
    dependencies = []
    for entry in observations:
        if entry.get("startKind") != "new_quest_entry" or not entry["missionId"] or not entry["questId"]:
            continue
        membership = entry.get("archivedMembership")
        if not membership:
            continue
        for predecessor in membership["prevQuestIdList"]:
            candidates = successes.get((entry["missionId"], predecessor), [])
            same_thread = [candidate for candidate in candidates if candidate["threadId"] == entry["threadId"] and
                           candidate["sequence"] < entry["sequence"] and candidate["qpc"] <= entry["qpc"]]
            selected = same_thread[-1] if same_thread and entry["threadId"] not in unsafe_threads else None
            dependencies.append({"missionId": entry["missionId"], "predecessorQuestId": predecessor,
                                 "questId": entry["questId"], "startSequence": entry["sequence"],
                                 "successSequence": selected["sequence"] if selected else None,
                                 "source": membership["source"], "sourceSha256": membership["sourceSha256"],
                                 "configuredDependency": True, "sameThreadObservedOrder": selected is not None,
                                 "status": "configured_dependency_with_observed_entries" if selected else "configured_dependency_only",
                                 "boundary": "Stored predecessor plus success/start entries; no prerequisite evaluation, successful return or server causal rule inferred."})
    definitions = {}
    for owners in quests.values():
        for owner in owners:
            if owner["missionId"] in timelines:
                definitions.setdefault((owner["missionId"], owner["source"]),
                                       {**{key: owner[key] for key in ("missionId", "source", "sourceSha256")},
                                        "mainPathQuests": owner.get("mainPathQuests", []),
                                        "evidenceBoundary": "structuralOnly: explicit stored main-path list, not observed execution or server selection."})
    return {"observations": observations, "missions": [{"missionId": identity, "entrySequences": sequences}
                                                        for identity, sequences in sorted(timelines.items())],
            "archivedMissionDefinitions": [definitions[key] for key in sorted(definitions)],
            "unassignedEntrySequences": unassigned, "identityConflicts": conflicts,
            "threadClockConflicts": clock_conflicts, "questDependencies": dependencies,
            "hookCalls": dict(sorted(calls.items())),
            "summary": {"entries": len(observations), "missionAssociatedEntries": len(observations) - len(unassigned),
                        "unassignedEntries": len(unassigned), "missions": len(timelines), "startKinds": dict(flags),
                        "configuredPredecessorsAtNewStarts": len(dependencies),
                        "predecessorsWithObservedSameThreadEntries": sum(item["sameThreadObservedOrder"] for item in dependencies),
                        "identityConflicts": len(conflicts), "threadClockConflicts": len(clock_conflicts),
                        "acceptedStoryOrderEdges": 0}}


def current_sources(replay: Replay, result: dict[str, Any], export_root: Path) -> dict[str, Any]:
    """Optionally match only observed missions; archived observations stay historical."""
    expected = replay.profile["files"]
    gate = check_installed_native_inputs(expected["gameAssembly"]["sha256"], expected["metadata"]["sha256"])
    joined: dict[str, Any] = {"nativeGate": {"status": gate.status, "detail": gate.detail},
                             "missions": [], "boundary": "Byte equality with selected existing exports, not whole-export freshness or new runtime observation."}
    if gate.status != "validated":
        joined["status"] = "unavailable"
        return joined
    export_root = export_root.resolve(strict=True)
    by_mission: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for definition in result.get("archivedMissionDefinitions", []):
        by_mission[definition["missionId"]].add((definition["source"], definition["sourceSha256"]))
    for entry in result["observations"]:
        membership = entry.get("archivedMembership")
        if membership and entry["missionId"]:
            by_mission[entry["missionId"]].add((membership["source"], membership["sourceSha256"]))
    for mission in result["missions"]:
        identity = mission["missionId"]
        sources = by_mission.get(identity, set())
        row: dict[str, Any] = {"missionId": identity, "status": "missing_archived_definition", "sources": []}
        for name, expected_hash in sorted(sources):
            relative = name.removeprefix("static-sources/files/")
            path = trace.safe_path(export_root, relative, existing=False)
            value: dict[str, Any] = {"path": str(path), "expectedSha256": expected_hash}
            if not path.is_file():
                value["status"] = "missing"
            else:
                value.update(fingerprint(path, trace.Limits().json_bytes))
                value["status"] = "matched" if value["sha256"] == expected_hash else "mismatched"
            row["sources"].append(value)
        if sources:
            row["status"] = "matched" if all(item["status"] == "matched" for item in row["sources"]) else "unavailable"
        joined["missions"].append(row)
    joined["status"] = "checked"
    return joined


def build_timeline(inspection_dir: Path, output_dir: Path, *, export_root: Path | None = None,
                   limits: trace.Limits = trace.Limits()) -> dict[str, Any]:
    inspection_dir, output_dir = inspection_dir.resolve(), output_dir.resolve()
    trace.require(any(output_dir.is_relative_to((trace.REPO_ROOT / folder).resolve()) for folder in ("reports", "scratch", "tmp")),
                  "Mission timeline: output must be inside ignored reports/, scratch/ or tmp/")
    report = trace.read_object(inspection_dir / "inspection.json", limits.json_bytes)
    session = Path(report["session"]).resolve()
    trace.require(not any(output_dir.is_relative_to(root) or root.is_relative_to(output_dir)
                          for root in (inspection_dir, session)), "Mission timeline: output overlaps retained evidence")
    trace.require(not output_dir.exists() or (output_dir.is_dir() and not any(output_dir.iterdir())),
                  "Mission timeline: output directory must be new or empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {"schema": SCHEMA, "status": "failed", "captureAdmitted": False,
                              "session": str(session), "evidenceBoundary": BOUNDARY, "graphEffect": "none",
                              "nativeValidationReproved": False, "externalOriginAuthenticated": False}
    try:
        replay = load_inspection(inspection_dir, limits=limits)
        trace.require(any(hook["name"] == "mission.StartQuest" for hook in replay.profile["missionTraceHooks"]),
                      "Mission timeline: retained profile has no Mission quest lifecycle hook")
        quests, sources = archived_quests(replay, limits)
        projection = project(replay.entries, quests)
        names = {hook["name"] for hook in replay.profile["missionTraceHooks"]}
        projection["hookCoverage"] = {"selected": len(names), "observed": len(projection["hookCalls"]),
                                       "unobserved": sorted(names - projection["hookCalls"].keys()),
                                       "boundary": "Unhit entries do not prove absent gameplay, callbacks, alternative IFix paths or server progress."}
        if export_root is not None:
            projection["currentSourceJoin"] = current_sources(replay, projection, export_root)
        replay.unchanged(limits)
        reader_pin = fingerprint(Path(__file__), limits.json_bytes)
        result.update(projection, status="validated", captureAdmitted=True, inputs=[*replay.inputs, reader_pin],
                      sources=sources, inventory=replay.inventory, retainedGameBuild=replay.profile["gameBuild"])
    except (trace.InspectionError, OSError, KeyError, TypeError, ValueError, AttributeError, RecursionError) as exc:
        result["failure"] = str(exc)[:2048]
        result["diagnostics"] = [getattr(exc, "diagnostic", {
            "validator": "mission_capture_timeline", "failedCheck": "replay_or_archived_source_binding",
            "sourcePath": str(inspection_dir / "inspection.json"),
            "expected": "Complete raw-bound replay and explicit archived source identities",
            "actual": str(exc)[:2048]})]
        (output_dir / "mission-timeline.json").write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="ascii")
        raise ReplayError(result["failure"], result["diagnostics"][0]) from exc
    (output_dir / "mission-timeline.json").write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="ascii")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspection-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--current-export-root", type=Path, help="Optional selected-native and byte checks for observed mission definitions.")
    args = parser.parse_args(argv)
    try:
        result = build_timeline(args.inspection_dir, args.output_dir, export_root=args.current_export_root)
    except (trace.InspectionError, OSError, KeyError, ValueError) as exc:
        print(f"Mission timeline failed: {exc}")
        diagnostic = getattr(exc, "diagnostic", None)
        if diagnostic:
            print(json.dumps(diagnostic, ensure_ascii=True, sort_keys=True))
        return 1
    summary = result["summary"]
    print(f"Mission timeline validated: {summary['missions']} missions, {summary['entries']} entries; "
          f"{summary['predecessorsWithObservedSameThreadEntries']} stored predecessors corroborated by entries; "
          f"{summary['unassignedEntries']} entries have no resolved mission association.")
    current = result.get("currentSourceJoin")
    if current and current["status"] == "unavailable":
        print(f"Current-source join unavailable: {current['nativeGate']['status']}: {current['nativeGate']['detail']}")
    elif current:
        unavailable = [row for row in current["missions"] if row["status"] != "matched"]
        if unavailable:
            print("Current-source reuse withheld: " + json.dumps(unavailable[0], ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
