"""Model authored state operands and conditional Boolean objective structure.

Native receipt claims authenticate comparator/evaluator semantics separately.
This is an offline source model, conditional on parameter resolution and the
native parser yielding the modeled AST. It never emits accepted timeline edges.
Without the separate authenticated parser review, mixed unparenthesized binary
operators remain withheld. Neither parser mode emits timeline edges.
"""
from __future__ import annotations

from collections import Counter
from itertools import product
import re
from typing import Any

from scripts.game_data.il2cpp.protocol import field_defaults, native_enum_members
from scripts.game_data.mission_expression import parse_expression as native_parse_expression, lex_expression

TOKEN = re.compile(r"\s*(\{[0-9]+\}|and|or|not|\(|\))")
MAX_LEAVES = 14
MAX_DEPTH = 64


def parse_expression(text: str, children: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip() or len(text) > 8192:
        raise ValueError("mission_state.expression: empty or oversized expression")
    tokens, at = [], 0
    while at < len(text):
        if not text[at:].strip():
            break
        match = TOKEN.match(text, at)
        if match is None:
            raise ValueError(f"mission_state.expression: unrecognized token at={at} text={text[at:at+24]!r}")
        tokens.append(match[1])
        at = match.end()
    position = 0

    def term(depth: int) -> dict[str, Any]:
        nonlocal position
        if depth > MAX_DEPTH or position >= len(tokens):
            raise ValueError("mission_state.expression: missing term or depth exceeds budget")
        token = tokens[position]
        position += 1
        if token == "not":
            return {"op": "not", "child": term(depth+1)}
        if token == "(":
            result = group(depth+1)
            if position >= len(tokens) or tokens[position] != ")":
                raise ValueError("mission_state.expression: missing closing parenthesis")
            position += 1
            return result
        if token.startswith("{"):
            index = int(token[1:-1])
            if not 0 <= index < len(children):
                raise ValueError(f"mission_state.expression: child index expected <{len(children)} actual={index}")
            return children[index]
        raise ValueError(f"mission_state.expression: expected term actual={token}")

    def group(depth: int) -> dict[str, Any]:
        nonlocal position
        result = term(depth)
        operator = None
        while position < len(tokens) and tokens[position] != ")":
            token = tokens[position]
            if token not in ("and", "or"):
                raise ValueError(f"mission_state.expression: expected binary operator actual={token}")
            if operator is not None and token != operator:
                raise ValueError("mission_state.expression: mixed unparenthesized operators require native precedence proof")
            operator = token
            position += 1
            result = {"op": token, "left": result, "right": term(depth+1)}
        return result

    tree = group(0)
    if position != len(tokens):
        raise ValueError("mission_state.expression: unexpected closing parenthesis")
    return tree


def condition_tree(node: dict[str, Any], path: str, depth: int = 0, *, native_parser_model: bool = False,
                   decision_gates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if depth > MAX_DEPTH:
        raise ValueError("mission_state.condition_tree: nested condition budget exceeded")
    kind = node["$type"].split(",", 1)[0]
    if kind == "Beyond.Gameplay.CombineCondition":
        children = [condition_tree(child, f"{path}.subConditions[{n}]", depth+1, native_parser_model=native_parser_model,
                                   decision_gates=decision_gates)
                    for n, child in enumerate(node["subConditions"])]
        parser = native_parse_expression if native_parser_model else parse_expression
        result = parser(node["conditionEvalString"], children)
        if native_parser_model and decision_gates is not None:
            used = {value for kind, value in lex_expression(node["conditionEvalString"]) if kind == "index"}
            paths = [f"{path}.subConditions[{n}]" for n in range(len(children))]
            decision_gates.append({"sourcePath": path, "conditionId": node.get("uniqueId"),
                "decisionWaitChildSourcePaths": paths,
                "expressionChildSourcePaths": [p for n, p in enumerate(paths) if n in used],
                "unusedChildSourcePaths": [p for n, p in enumerate(paths) if n not in used],
                "boundary": "conditional normal outer Evaluate waits for each supplied child cache; expression alternatives cannot bypass this gate"})
        return result
    return {"op": "leaf", "sourcePath": path, "conditionId": node.get("uniqueId"), "type": kind}


def leaves(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if tree["op"] == "leaf":
        return {tree["sourcePath"]: tree}
    if tree["op"] == "not":
        return leaves(tree["child"])
    return {**leaves(tree["left"]), **leaves(tree["right"])}


def evaluate_boolean(tree: dict[str, Any], values: dict[str, bool]) -> bool:
    op = tree["op"]
    if op == "leaf":
        return values[tree["sourcePath"]]
    if op == "not":
        return not evaluate_boolean(tree["child"], values)
    if op == "and":
        return evaluate_boolean(tree["left"], values) and evaluate_boolean(tree["right"], values)
    if op == "or":
        return evaluate_boolean(tree["left"], values) or evaluate_boolean(tree["right"], values)
    raise ValueError(f"mission_state.boolean: unknown operator={op}")


def boolean_roles(tree: dict[str, Any]) -> dict[str, Any]:
    keys = sorted(leaves(tree))
    if len(keys) > MAX_LEAVES:
        return {"status": "withheld_budget", "leaves": len(keys), "roles": {}}
    satisfying = {key: set() for key in keys}
    count = 0
    for assignment in product((False, True), repeat=len(keys)):
        values = dict(zip(keys, assignment))
        if evaluate_boolean(tree, values):
            count += 1
            for key, value in values.items():
                satisfying[key].add(value)
    return {"status": "modeled", "leaves": len(keys), "satisfyingAssignments": count,
            "roles": {key: "unsatisfiable_objective" if not count else
                      "requires_condition_true" if values == {True} else
                      "requires_condition_false" if values == {False} else "alternative_or_optional"
                      for key, values in satisfying.items()}}


REQUIRED_CLAIMS = {
    "dialogHistoryAndServerConditions": {
        "Beyond.Gameplay.GameCondition.set_result": "propagatesConditionResultOnDefaultPath"},
    "questMissionStatePredicates": {
        "Beyond.TableUtils.DoCompare": "comparesSignedInt32OnDefaultPath",
        "Beyond.Gameplay.MissionSystem.GetQuestState": "looksUpQuestStateOnDefaultPath",
        "Beyond.Gameplay.CheckQuestState._OnQuestStateChange": "comparesStateEventOnDefaultPath",
        "Beyond.Gameplay.CheckMissionState._OnMissionStateChange": "comparesStateEventOnDefaultPath"},
    "combinedConditionAst": {
        "Beyond.Gameplay.CombineCondition._EvaluateNode": "evaluatesBooleanAstOnDefaultPath",
        "Beyond.Gameplay.CombineCondition.Evaluate": "gatesCombinedEvaluationOnDefaultPath"},
}


def build_constraints(source: dict[str, Any], receipt: dict[str, Any], image: Any,
                      expression_review: dict[str, Any] | None = None) -> dict[str, Any]:
    """Caller authenticates current contract/receipt and gates selected image."""
    for group, required in REQUIRED_CLAIMS.items():
        admitted = receipt.get("groups", {}).get(group, {})
        operators = {row["symbol"]: {key for claim in row["claims"] for key in claim}
                     for row in admitted.get("methods", [])}
        if admitted.get("status") != "validated" or any(operator not in operators.get(symbol, set()) for symbol, operator in required.items()):
            return {"status": "native_claims_not_admitted", "stateReferences": [], "objectiveModels": [],
                    "graphEffect": "none", "detail": f"required validated claim group={group}"}
    parser_reviewed = (expression_review or {}).get("status") == "validated"
    activation_orders = {row["symbol"].removesuffix(".OnActivate"): row["callOrder"]
                         for row in (expression_review or {}).get("activationOrderProofs", [])
                         if parser_reviewed and row.get("status") == "validated"}
    defaults = field_defaults(image.metadata)
    enum_names = ["Beyond.GEnums.CompareOperator", "Beyond.Gameplay.MissionSystem+QuestState",
                  "Beyond.Gameplay.MissionSystem+MissionState"]
    enums = {name: {row["id"]: row["name"] for row in native_enum_members(image.metadata, defaults, image.pe, image.registration, name)}
             for name in enum_names}
    models, roles, totals = [], {}, Counter()
    for objective in source.get("objectives", []):
        row = {key: objective[key] for key in ("missionId", "ownerQuestId", "sourcePath")}
        try:
            decision_gates: list[dict[str, Any]] = []
            tree = condition_tree(objective["condition"], objective["sourcePath"], native_parser_model=parser_reviewed,
                                  decision_gates=decision_gates)
            analysis = boolean_roles(tree)
            row.update(analysis, astModel=tree, nativeParserEquivalenceProved=False,
                       nativeParserCallerModelReviewed=parser_reviewed,
                       combineDecisionGates=decision_gates,
                       allChildrenDecidedGate="conditional native outer Evaluate, including children unused by AST",
                       nestedCachedResultCoherenceProved=False)
            roles.update({(row["missionId"], row["ownerQuestId"], path): role for path, role in analysis["roles"].items()})
        except (ValueError, KeyError, TypeError, RecursionError) as exc:
            row.update(status="withheld_expression", detail=str(exc)[:400], nativeParserEquivalenceProved=False)
        totals[row["status"]] += 1
        models.append(row)
    references = []
    quest_owners: dict[str, list[str]] = {}
    for mission, definition in source["missions"].items():
        for quest in definition.get("questIds", []):
            quest_owners.setdefault(quest, []).append(mission)
    for reference in source.get("stateReferences", []):
        row = dict(reference)
        row.update(status="unresolved_operands", booleanRole=roles.get((row["missionId"], row["ownerQuestId"], row["sourcePath"]), "unused_or_withheld"),
                   nativeParameterResolutionProved=False, nativeConstantParameterPathReviewed=parser_reviewed,
                   nativeTypedEventPublicationReviewed=parser_reviewed and bool(expression_review.get("eventPublication")),
                   nativeParamLoadingReviewed=parser_reviewed and bool(expression_review.get("parameterLoading")),
                   nativeActivationCallOrder=activation_orders.get(row["type"], []),
                   runtimeParamSourceZeroRequired=parser_reviewed, acceptedTimelineEdge=False)
        if row["constantOperands"]:
            comparator, state = row["storedComparator"]["constValue"], row["storedState"]["constValue"]
            state_enum = "Beyond.Gameplay.MissionSystem+"+("QuestState" if row["targetKind"] == "quest" else "MissionState")
            if type(comparator) is int and type(state) is int and comparator in enums[enum_names[0]] and state in enums[state_enum]:
                row.update(status="conditional_named_state_operand", comparatorName=enums[enum_names[0]][comparator],
                           stateName=enums[state_enum][state], stateEnum=state_enum)
                owners = quest_owners.get(row["targetId"], []) if row["targetKind"] == "quest" else [row["targetId"]] if row["targetId"] in source["missions"] else []
                row.update(targetMissionOwners=owners, targetResolvedInSelectedExport=len(owners) == 1,
                           selfReference=row["targetId"] == (row["ownerQuestId"] if row["targetKind"] == "quest" else row["missionId"]))
                if parser_reviewed and row["targetKind"] == "quest":
                    prefix = row["targetId"].split("_q#", 1)[0] if "_q#" in row["targetId"] else ""
                    row.update(nativeUncachedOwnerPrefix=prefix, nativeUncachedOwnerAgreesWithExport=owners == [prefix])
            else:
                row["detail"] = f"selected enum operands unresolved: comparator={str(comparator)[:60]} state={str(state)[:60]}"
        row["evidenceBoundary"] = ("conditional source constraint: reviewed ASCII native parser caller model and source-zero constant resolver; live Param initialization, default callee/context behavior and coherent nested caches assumed; no event, chronology or accepted handoff"
                                   if parser_reviewed else "conditional source constraint: authored constants and Boolean model; parameter resolution and native parser equivalence assumed; no event, chronology or accepted handoff")
        references.append(row)
    return {"status": "conditional_source_models", "graphEffect": "none", "stateReferences": references,
            "objectiveModels": models, "objectiveModelCounts": dict(totals),
            "operandCounts": dict(Counter(row["status"] for row in references)),
            "namedStateCounts": dict(Counter(f"{row['targetKind']}:{row['comparatorName']}:{row['stateName']}" for row in references if "stateName" in row)),
            "booleanRoleCounts": dict(Counter(row["booleanRole"] for row in references)),
            "enumMembers": enums,
            "nativeParserCallerModelReviewed": parser_reviewed,
            "evidenceBoundary": "Selected native comparator/evaluator claims and authored Boolean constraints. With a validated expression review, the model follows reviewed ASCII native parser caller algorithms and source-zero constant resolution. Full live initialization, successful default callee/context behavior, stable leaf results and coherent nested caches remain conditions. New state events are not proved. Multiple objectives are analyzed separately; no quest-level combination rule inferred."}
