"""Audit shared Mission selectors across a selected export and retained entries.

Reports applicability and observations separately. This is not an installed
VFS census, a new native evaluation, or a reconstruction of server decisions.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.common import check_installed_native_inputs
from scripts.game_data.il2cpp.native_image import open_native_image
from scripts.game_data.mission_shared_native import ConditionSelectors, DEFAULT_CONTRACT
from scripts.game_data.mission_expression_native import evaluate as evaluate_expression_native, DEFAULT_CONTRACT as EXPRESSION_CONTRACT
from scripts.game_data.schemas.mission_runtime_main import CONTRACT_PATH as SOURCE_SCHEMA_CONTRACT, decode_mission_runtime_main
from scripts.repo_paths import REPO_ROOT
from scripts.webui.story_recovery.mission_state_constraints import build_constraints

SCHEMA = "endfield.mission-mechanism-audit.v1"
MAX_JSON = 32*1024*1024


def read_bound(path: Path, expected: dict[str, Any] | None = None) -> tuple[Any, dict[str, Any]]:
    before = path.stat()
    if before.st_size > MAX_JSON:
        raise ValueError(f"mission_mechanism.input_budget: {path}: expected <= {MAX_JSON}; actual={before.st_size}")
    raw = path.read_bytes()
    after = path.stat()
    pin = {"path": str(path.resolve()), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f"mission_mechanism.input_mutation: {path}")
    if expected and (pin["bytes"] != expected.get("bytes", pin["bytes"]) or pin["sha256"].casefold() != expected["sha256"].casefold()):
        raise ValueError(f"mission_mechanism.input_hash: {path}: expected={expected['sha256']} actual={pin['sha256']}")
    return json.loads(raw.decode("utf-8-sig")), pin


def reviewed_selectors(contract: dict[str, Any], receipt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Use only evaluated claims present in a fully passing current receipt."""
    result = {}
    if receipt.get("status") != "validated":
        raise ValueError("mission_mechanism.native_receipt: requires validated status")
    for group_name, group in contract["groups"].items():
        evaluated = receipt["groups"][group_name]
        if evaluated["status"] != "validated":
            raise ValueError(f"mission_mechanism.native_group: {group_name}: {evaluated['status']}")
        methods = {row["symbol"]: row for row in evaluated["methods"]}
        for symbol, spec in group["methods"].items():
            row = methods.get(symbol)
            if row is None or row["claims"] != spec["claims"]:
                raise ValueError(f"mission_mechanism.native_claims: {group_name}/{symbol}: receipt differs from reviewed claims")
            if spec["method"] != "get_conditionType":
                continue
            claims = [claim[key] for claim in spec["claims"]
                      for key in ("returnsEnumMember", "returnsEnumAfterFalseCall") if key in claim]
            if len(claims) != 1:
                continue
            result[spec["type"]+"."+spec["method"]] = {"enumType": claims[0]["type"], "member": claims[0]["member"],
                "group": group_name, "symbol": symbol}
            if "call" in claims[0]:
                result[spec["type"]+"."+spec["method"]]["normalReturnGuard"] = {"call": claims[0]["call"], "result": False}
    return result


def census(mission_root: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    families, missions, pins = {}, {}, []
    state_references, objectives = [], []
    counts = Counter()
    paths = sorted(path for path in mission_root.glob("*.json") if not path.name.endswith("_meta.json"))
    if not paths:
        raise ValueError(f"mission_mechanism.sources: no main mission definitions: {mission_root}")
    for path in paths:
        raw = path.read_bytes()
        if len(raw) > MAX_JSON:
            raise ValueError(f"mission_mechanism.source_budget: {path}")
        decode_mission_runtime_main(raw, source=f"MissionRuntimeAsset/{path.name}")
        document = json.loads(raw.decode("utf-8-sig"))
        pin = {"path": str(path.resolve()), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        pins.append(pin)
        identity = document["missionId"]
        if identity in missions:
            raise ValueError(f"mission_mechanism.mission_identity: {path}: expected one definition of {identity}; actual=duplicate")
        main_path = document["mainPathQuests"]
        if len(set(main_path)) != len(main_path) or any(quest not in document["questDic"] for quest in main_path):
            raise ValueError(f"mission_mechanism.main_path: {identity}: missing or duplicate owned quest")
        mission = {"source": pin, "questConditions": {}, "questIds": sorted(document["questDic"]), "missionType": document["missionType"]}
        missions[identity] = mission
        counts.update(missions=1, quests=len(document["questDic"]), questsOutsideMainPath=len(document["questDic"])-len(main_path),
                      clientActionPhaseEntries=len(document["clientActionMapKey"]))

        def condition(node: Any, quest: str, source_path: str) -> None:
            if node is None:
                return
            if not isinstance(node, dict) or not isinstance(node.get("$type"), str):
                raise ValueError(f"mission_mechanism.condition: {identity}/{quest}: {source_path}")
            kind = node["$type"].split(",", 1)[0]
            row = families.setdefault(kind, {"instances": 0, "missions": set(), "quests": set(), "roles": Counter(), "examples": []})
            row["instances"] += 1
            row["missions"].add(identity)
            row["quests"].add((identity, quest))
            row["roles"]["combined" if kind == "Beyond.Gameplay.CombineCondition" else "leaf"] += 1
            ref = {"type": kind, "conditionId": node.get("uniqueId"), "sourcePath": source_path}
            mission["questConditions"].setdefault(quest, []).append(ref)
            if len(row["examples"]) < 3:
                row["examples"].append({"missionId": identity, "questId": quest, **ref})
            state_kind = {"Beyond.Gameplay.CheckQuestState": ("quest", "_questId", "_targetQuestState"),
                          "Beyond.Gameplay.CheckMissionState": ("mission", "_missionId", "_targetMissionState")}.get(kind)
            if state_kind:
                target_kind, target_field, state_field = state_kind
                target = node[target_field]
                comparator, state = node["_comparer"], node[state_field]
                static = all(isinstance(parameter, dict) and set(parameter) == {"constValue"}
                             for parameter in (target, comparator, state))
                state_references.append({"missionId": identity, "ownerQuestId": quest, **ref,
                    "targetKind": target_kind, "storedTarget": target, "storedComparator": comparator, "storedState": state,
                    "constantOperands": static, "targetId": target["constValue"] if static else None,
                    "evidenceBoundary": "structuralOnly: operand reference, not an owning quest, prerequisite decision or accepted timeline edge"})
            if kind == "Beyond.Gameplay.CombineCondition":
                for position, child in enumerate(node["subConditions"]):
                    condition(child, quest, f"{source_path}.subConditions[{position}]")

        for quest_id, quest in document["questDic"].items():
            counts["dependencyEdges"] += len(quest["prevQuestIdList"])
            counts["questsWithMultiplePredecessors"] += len(quest["prevQuestIdList"]) > 1
            for position, objective in enumerate(quest["objectiveList"]):
                counts["objectives"] += 1
                counts["multipleCombinedObjectives"] += bool(objective["multiple"] and objective.get("condition") and
                    objective["condition"].get("$type", "").split(",", 1)[0] == "Beyond.Gameplay.CombineCondition")
                if objective["condition"] is not None:
                    objectives.append({"missionId": identity, "ownerQuestId": quest_id,
                        "sourcePath": f"questDic[{quest_id}].objectiveList[{position}].condition", "condition": objective["condition"]})
                condition(objective["condition"], quest_id, f"questDic[{quest_id}].objectiveList[{position}].condition")
    return families, {"missions": missions, "counts": dict(counts), "stateReferences": state_references,
                      "objectives": objectives,
                      "sourceNames": [path.name for path in paths]}, pins


def retained_coverage(bundle_path: Path, missions: dict[str, Any], expected_native: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    bundle, bundle_pin = read_bound(bundle_path)
    pins = [bundle_pin]
    coverage = defaultdict(lambda: {"questEntryAssociations": Counter(), "conditionEntryAssociations": Counter(), "sessions": set()})
    stats = Counter()
    for session in bundle["sessions"]:
        timeline, pin = read_bound(Path(session["report"]["path"]), session["report"])
        pins.append(pin)
        if timeline.get("status") != "validated" or not timeline.get("captureAdmitted"):
            raise ValueError(f"mission_mechanism.timeline_admission: {pin['path']}")
        inspection_pin = next(row for row in timeline["inputs"] if Path(row["path"]).name == "inspection.json")
        inspection, actual_inspection_pin = read_bound(Path(inspection_pin["path"]), inspection_pin)
        pins.append(actual_inspection_pin)
        profile_path = Path(inspection["session"])/"private/mission-trace-build-manifest.json"
        profile, profile_pin = read_bound(profile_path, {"sha256": inspection["profileSha256"]})
        pins.append(profile_pin)
        matched_native = all(profile["files"][key]["sha256"].casefold() == expected_native[key].casefold()
                             for key in ("gameAssembly", "metadata"))
        stats["sessions"] += 1
        stats["retainedEntries"] += len(timeline["observations"])
        for entry in timeline["observations"]:
            identity, quest = entry.get("missionId"), entry.get("questId")
            membership, mission = entry.get("archivedMembership"), missions.get(identity)
            if not matched_native or not mission or not membership or membership["sourceSha256"].casefold() != mission["source"]["sha256"].casefold():
                stats["entriesWithheldFromCurrentCohort"] += 1
                reason = ("nativeProfileMismatch" if not matched_native else "noExplicitOwnedQuest" if not membership else
                          "missingCurrentMission" if not mission else "sourceBytesMismatch")
                stats[reason] += 1
                continue
            conditions = mission["questConditions"].get(quest, [])
            for kind in {row["type"] for row in conditions}:
                coverage[kind]["questEntryAssociations"][entry["hook"]] += 1
                coverage[kind]["sessions"].add(str(timeline["session"]))
            condition_id = entry["entryFields"].get("conditionId")
            matched = [row for row in conditions if condition_id and row["conditionId"] == condition_id]
            if len(matched) == 1:
                coverage[matched[0]["type"]]["conditionEntryAssociations"][entry["hook"]] += 1
            elif matched:
                stats["ambiguousOwnedConditionEntries"] += 1
    return {"families": coverage, "summary": dict(stats)}, pins


def build(mission_root: Path, native_report: Path, timeline_bundle: Path) -> dict[str, Any]:
    native, native_pin = read_bound(native_report)
    contract, contract_pin = read_bound(DEFAULT_CONTRACT, native["contract"])
    selectors = reviewed_selectors(contract, native)
    native_inputs = native["nativeGate"]
    assembly, metadata = Path(native_inputs["gameAssembly"]["path"]), Path(native_inputs["metadata"]["path"])
    expected = {"gameAssembly": native_inputs["gameAssembly"]["sha256"], "metadata": native_inputs["metadata"]["sha256"]}
    gate = check_installed_native_inputs(expected["gameAssembly"], expected["metadata"], gameassembly=assembly, metadata=metadata)
    result: dict[str, Any] = {"schema": SCHEMA, "status": gate.status, "nativeGate": {"status": gate.status, "detail": gate.detail},
        "evidenceBoundary": {"structuralOnly": "Named-schema closure of selected exported objective condition trees and authored dependencies; not whole-installed VFS freshness.",
            "conditional": "Unique stored class, concrete selected metadata inheritance and virtual slot join to a reviewed default getter; assumes matching live subtype/default IFix path.",
            "direct": "Reused admitted entry reports, matched native profile and source bytes, explicit quest plus unique owned condition ID where present.",
            "unresolved": "Specific Check bodies, live activation/results, objective map values, asynchronous ownership and server policy; quest entries beside a family are not leaf callback coverage."},
        "graphEffect": "none", "liveCaptureRequested": False, "families": [], "inputs": [native_pin, contract_pin]}
    if gate.status != "validated":
        return result
    _, schema_pin = read_bound(SOURCE_SCHEMA_CONTRACT)
    families, source, source_pins = census(mission_root)
    coverage, retained_pins = retained_coverage(timeline_bundle, source["missions"], expected)
    image = open_native_image(assembly, metadata)
    resolver = ConditionSelectors(image, selectors)
    _, expression_pin = read_bound(EXPRESSION_CONTRACT)
    expression_review = evaluate_expression_native(image=image)
    if expression_review["contract"]["sha256"].casefold() != expression_pin["sha256"].casefold():
        raise ValueError("mission_mechanism.expression_contract_mutation: native review and pinned source differ")
    state_constraints = build_constraints(source, native, image, expression_review)
    selector_totals = Counter()
    selector_family_totals = Counter()
    objective_routes = Counter()
    reviewed_missions: set[str] = set()
    for kind, family in sorted(families.items()):
        selection = resolver.resolve(kind)
        observed = coverage["families"].get(kind, {"questEntryAssociations": {}, "conditionEntryAssociations": {}, "sessions": set()})
        selector_totals[selection["status"]] += family["instances"]
        selector_family_totals[selection["status"]] += 1
        if selection["status"] == "conditional_reviewed_selector":
            reviewed_missions.update(family["missions"])
            route = ("combined_container" if kind == "Beyond.Gameplay.CombineCondition" and selection["conditionType"] == "Combined" else
                     "eligible_client_leaf" if selection["defaultClientLeafSelection"] else "excluded_client_leaf")
            objective_routes[route] += family["instances"]
        else:
            route = "unreviewed"
            objective_routes[route] += family["instances"]
        result["families"].append({"type": kind, "storedInstances": family["instances"], "missions": len(family["missions"]),
            "quests": len(family["quests"]), "roles": dict(family["roles"]), "examples": family["examples"], "selector": selection,
            "conditionalObjectiveRoute": route,
            "retained": {"questEntryAssociations": dict(observed["questEntryAssociations"]),
                "conditionEntryAssociations": dict(observed["conditionEntryAssociations"]), "sessions": len(observed["sessions"])}})
    pair_cases = []
    complete_copy_loops = False
    for row in native["groups"].get("missionLifecycle", {}).get("methods", []):
        row_loops = {"copiesObjectiveMapsOnDefaultPath": {}} in row["claims"]
        complete_copy_loops |= row_loops
        transfers = [claim["passesInterfaceCurrentStringIntPairFastPath"] for claim in row["claims"]
                     if "passesInterfaceCurrentStringIntPairFastPath" in claim]
        transferred = any(spec == {"call": "System.Collections.Generic.Dictionary`2.Add", "classArguments": ["string", "int"]}
                          for spec in transfers)
        for claim in row["claims"]:
            for pair in claim.get("callsInterfacePairCurrentFastPaths", {}).get("classArguments", []):
                pair_cases.append({"classArguments": pair, "conditionalCurrentReturnCopyProved": True,
                    "destinationTransferProved": transferred and pair == ["string", "int"],
                    "fieldLayoutProved": False, "completeLoopProved": row_loops})
    result.update(status="validated", sourceSummary=source["counts"], selectorInstanceCounts=dict(selector_totals),
                  selectorFamilyCounts=dict(selector_family_totals), missionsWithReviewedSelector=len(reviewed_missions),
                  retainedSummary=coverage["summary"], conditionFamilies=len(families),
                  nativePairCases=pair_cases,
                  completeNormalCopyLoopClaim=complete_copy_loops,
                  conditionalObjectiveRoutes=dict(objective_routes),
                  storedStateReferences=source.get("stateReferences", []),
                  stateConstraints=state_constraints,
                  expressionNative=expression_review,
                  inputs=[native_pin, contract_pin, schema_pin, expression_pin, *source_pins, *retained_pins])
    for pin in result["inputs"]:
        read_bound(Path(pin["path"]), pin)
    current_names = sorted(path.name for path in mission_root.glob("*.json") if not path.name.endswith("_meta.json"))
    if current_names != source["sourceNames"]:
        raise ValueError("mission_mechanism.source_set_mutation: mission input names changed")
    after = check_installed_native_inputs(expected["gameAssembly"], expected["metadata"], gameassembly=assembly, metadata=metadata)
    result["nativeGateAfter"] = {"status": after.status, "detail": after.detail}
    if after.status != "validated":
        result.update(status=after.status, families=[], selectorInstanceCounts={}, selectorFamilyCounts={},
                      missionsWithReviewedSelector=0, nativePairCases=[], conditionalObjectiveRoutes={}, completeNormalCopyLoopClaim=False)
        result["stateConstraints"] = {"status": after.status, "stateReferences": [], "objectiveModels": [], "graphEffect": "none"}
        result["expressionNative"] = {"status": after.status, "methods": [], "grammar": {}, "parameterResolution": {}, "ownerLookup": {}, "eventPublication": {}, "parameterLoading": {}, "activationOrderProofs": []}
    return result


def markdown(result: dict[str, Any]) -> str:
    if result["status"] != "validated":
        return f"# Mission generalization audit\n\nStatus: {result['status']}. No native classifications admitted.\n"
    source, retained = result["sourceSummary"], result["retainedSummary"]
    known = result["selectorFamilyCounts"].get("conditional_reviewed_selector", 0)
    observed = sum(bool(row["retained"]["conditionEntryAssociations"]) for row in result["families"])
    lines = ["# Shared Mission mechanism audit", "",
        f"The selected export contains **{source['missions']} mission definitions, {source['quests']} quests and {result['conditionFamilies']} objective-condition families**. Named schema validation covers the objective condition trees in these files; installed VFS completeness and whole-export freshness are not claimed.", "",
        f"Exact selected metadata inheritance and virtual-slot joins extend reviewed default selectors to **{known} families in {result['missionsWithReviewedSelector']} missions**, covering {result['selectorInstanceCounts'].get('conditional_reviewed_selector', 0)} stored condition nodes. Specific Check bodies, actual activation and live IFix choices remain separate.", "",
        f"The {retained['sessions']} admitted recording intervals retain {retained['retainedEntries']} entries. {observed} stored families have uniquely owned condition-entry associations after matching profile-native hashes and source bytes. Entries naming a quest beside a family are counted separately and do not prove that leaf executed.", "",
        "## General rules and limits", "",
        "- Quest/mission state, objective values, local conditions, UI presentation and playback remain separate carriers; explicit identity-bearing joins select observed paths.",
        "- A leaf inherits a reviewed selector only if no nearer override replaces it and its getter occupies the same virtual slot. Concrete and registered generic parent contexts are checked.",
        "- Source families without a reviewed getter remain unreviewed; their class names do not assign ClientOnly or server behavior.",
        f"- Authored structure includes {source['questsWithMultiplePredecessors']} quests with multiple predecessors and {source['questsOutsideMainPath']} quests outside their mission's main-path list. The list is not the whole dependency graph.",
        f"- {source['multipleCombinedObjectives']} stored objectives use multiple combined presentation. This is applicability evidence for the shared presentation consumer, not observed progress for every objective.", "",
        f"- Reviewed selectors cover {result['conditionalObjectiveRoutes'].get('eligible_client_leaf', 0)} eligible client leaf nodes, {result['conditionalObjectiveRoutes'].get('excluded_client_leaf', 0)} leaf nodes excluded from that default lane, and {result['conditionalObjectiveRoutes'].get('combined_container', 0)} combined containers. These are stored instances with conditional default applicability, not executed checks or server decisions.", "",
        "## Native current-pair cases", "",
        "| Selected pair | Matching-interface current return copy | Destination caller flow |", "| --- | --- | --- |"]
    for pair in result["nativePairCases"]:
        label = "/".join(pair["classArguments"])
        transfer = 'Checked string/int Add window' if pair['destinationTransferProved'] else 'Separate obligation'
        if pair['completeLoopProved']:
            transfer = {('string','int'): 'Checked values-loop Add argument program',
                        ('string','Proto.QUEST_OBJECTIVE_DETAIL'): 'Checked nested-map / new-detail / outer-Add caller program',
                        ('ulong','bool'): 'Checked signed-context Add argument program; low64 preserved'}[tuple(pair['classArguments'])]
        lines.append(f"| {label} | Checked complete helper variant | {transfer} |")
    lines += ["", "All current-pair cases require normal TypeInfo resolution, valid receiver/interface tables and a valid getter return. The helpers copy a 16-byte return window; type binding alone does not establish closed field layout. Initializer/fallback helper semantics, enumerator implementation, runtime map contents and quest ownership remain open; normal caller loop flow is assessed separately below.", "",
              "## Copy loops and timeline constraints", "",
              ("The complete normal Copy caller grammar is checked through all three loops: it clears the values destination and enumerates incoming values, copies the root completion flag, clears the details destination, then allocates a new detail for each incoming detail and fills its nested hash dictionary before adding it to the outer destination. Current-return lanes reach the selected Add contexts and every loop backedge/false exit is bound. The nested hash transfer preserves the low 64-bit argument into a signed destination context; this caller contains no arithmetic or range check on that transfer."
               if result['completeNormalCopyLoopClaim'] else "A complete normal Copy-loop claim is not admitted by this receipt."), "",
              "This closes caller control/argument flow under valid objects, unpatched dispatch, normal Win64 ABI and successful collection/allocation/cleanup calls. Enumerator/collection/helper bodies, closed pair field layout, external heap aliases, exceptional paths and actual map values remain separate. Copying a completed flag or count is not a new quest-state message.", "",
              f"The selected source retains {len(result['storedStateReferences'])} quest/mission-state operand references. Their owning objective and referenced target remain distinct. These are structural constraints, not accepted progression edges or proof that the referenced state was reached.", "",
              "## State predicates and Boolean AST", ""]
    constraints = result.get("stateConstraints", {})
    if constraints.get("status") == "conditional_source_models":
        lines += ["The selected default Int32 comparator cases, matching-ID state callbacks, valid-node Boolean AST evaluator and outer all-children-decided gate are checked. Activation reads existing client state; callback delivery is a separate lane. No new state event is required for a predicate to match restored state.", "",
                  "The inner AST uses exact True leaf tests, Boolean NOT, and short-circuit AND/OR. The outer evaluator waits on every Undecided child (and on null children) before calling the AST; an OR alternative cannot bypass that gate. Own Undecided forces a result write; unchanged decided Boolean results skip the setter.", "",
                  f"Named authored state operands: {constraints['namedStateCounts']}. Boolean source roles: {constraints['booleanRoleCounts']}.", "",
                  ("The authenticated native expression review supplies an ASCII parser model: space/tab skipping, case folding, immediate NOT reduction, equal left-associative AND/OR precedence, parenthesis pruning and contiguous distinct index checks. Source-zero Param resolvers copy constants before blackboard/getter dispatch. Live Param initialization, successful default helper/context behavior and stable nested caches remain conditions."
                   if constraints.get("nativeParserCallerModelReviewed") else "Native expression review is withheld; source roles use only the earlier unambiguous model, with parameter resolution and native parser equivalence assumed."), "",
                  "Conditions requiring True/False differ from alternatives; none is an accepted handoff, an observed completion, or chronological ordering of state numbers. Each objective is modeled separately.", ""]
        if result.get("expressionNative", {}).get("eventPublication"):
            lines += ["Normal quest updates publish their record state before the StartQuest/SucceedQuest state-case calls and global state-change send; normal mission updates publish a new MissionData before their lifecycle branch. Earlier show-data/property helpers can run before these publication points. Producers and subscribers select matching event keys and closed string/state-enum contexts. The compiled sender passes reference/Int32 packet lanes into a synchronous dispatcher/binding/delegate path. These are conditional native caller relationships, with runtime subscriptions, helper/context semantics, exceptions, patches and callback reentrancy still separate.", "",
                      "The active result setter caches a changed decided result, calls its callback helper, then evaluates its parent. Callback mutation/reentrancy prevents treating this as an atomic refresh of all nested caches. Source models also retain every supplied child in a decision-wait gate, separately from the children used by the expression.", ""]
        if result.get("expressionNative", {}).get("parameterLoading"):
            lines += ["The selected ordinary value constructors explicitly set the constant source. Concrete MemoryPack wrappers require a full four-property object and read/store constant, reference ID, source selector and path; they do not use omission to default the source. Mission resource loading has JSON and MemoryPack paths and a JSON fallback. The selected export's JSON members alone cannot identify which reader, creator or field-setting outcome produced a live Param.", "",
                      "A bounded walk of the actual default activation control graphs verifies the critical call order on every completing path: QuestState binds before its initial result, while MissionState sets its initial result before binding. Calls are opaque returning boundaries. Neither subscriptions nor callback nesting are observed, and an activation result cannot be assigned to a later state event from timestamps alone.", ""]
    else:
        lines += ["State/AST claims are not admitted by this receipt; no native constraint models published.", ""]
    lines += ["## Remaining review priorities", ""]
    pending = [row for row in result["families"] if row["selector"]["status"] != "conditional_reviewed_selector"]
    if pending:
        lines += ["| Unreviewed stored selector | Condition nodes | Missions |", "| --- | ---: | ---: |"]
        for row in sorted(pending, key=lambda row: (-row["storedInstances"], row["type"]))[:10]:
            lines.append(f"| {row['type']} | {row['storedInstances']} | {row['missions']} |")
    else:
        lines += ["Every stored objective family in this selected export has a reviewed default selector join. This closes this census's selector gap, not predicate or execution parity.", "",
            "- Native parser, constant resolver, typed publication/subscription contexts and compiled packet lanes are reviewed. Live Param initialization, registration, context/helper behavior, patches and delivery remain separate from these caller rules. Correlate explicit runtime state changes with candidate handoffs.",
            "- Prove closed pair field layout and enumerator/collection/helper bodies, then relate actual delivered values to display counts and completion flags.",
            "- Preserve the unrecorded handoff, live IFix/receiver choices, asynchronous playback ownership and authoritative server-decision gaps."]
    lines += ["", "These are offline review priorities, not requests to replay completed missions. No Story order or page data is published.", "",
              "Durable interpretation: [Story carriers](../../memory/game_data/story_carriers.md). The JSON beside this report pins source files, native receipt, schema contracts and retained-entry inputs.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mission-root", type=Path, required=True)
    parser.add_argument("--native-report", type=Path, required=True)
    parser.add_argument("--timeline-bundle", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=REPO_ROOT/"reports/runtime_capture/mission-mechanism-audit.json")
    args = parser.parse_args(argv)
    output = args.report.resolve()
    if not any(output.is_relative_to(REPO_ROOT/root) for root in ("reports", "scratch", "tmp")):
        parser.error("generated audit must be within reports/, scratch/ or tmp/")
    try:
        result = build(args.mission_root, args.native_report, args.timeline_bundle)
    except (ValueError, KeyError, TypeError, OSError, AttributeError) as exc:
        result = {"schema": SCHEMA, "status": "validation_failed", "families": [],
                  "diagnostics": [{"validator": "mission_mechanism_audit", "failedCheck": "source_or_receipt_binding",
                    "sourcePath": str(args.mission_root), "expected": "Named sources and unchanged authenticated receipts",
                    "actual": str(exc)[:2048]}]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    output.with_suffix(".md").write_text(markdown(result), encoding="utf-8")
    print(f"Mission mechanism audit: {result['status']}: {output}")
    if result["status"] == "validated":
        print(json.dumps({"sources": result["sourceSummary"], "families": result["conditionFamilies"],
                          "selectors": result["selectorInstanceCounts"], "retained": result["retainedSummary"]}, sort_keys=True))
        return 0
    print(json.dumps(result.get("diagnostics", result.get("nativeGateAfter", result.get("nativeGate"))), ensure_ascii=True))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
