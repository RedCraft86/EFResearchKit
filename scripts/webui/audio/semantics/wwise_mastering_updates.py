"""Authenticate Mastering Suite's numeric dispatcher and masked value helper.

The selector is a signed low 16-bit value. Two byte-index/dword-target tables
and explicit cases route it to anonymous parameter handlers. Every ordinary
handler has a reviewed full extent and a final branch to a common exit; that
exit writes a byte even on the invalid-selector path. No-op cases reach it
without reading the value pointer. Every payload is independently recognized:
raw word copies, zero-test Boolean words, inverse mask updates and cached-word
refresh. Indexed records use proved integer selector arithmetic, not a fitted
stride. No payload handler validates the supplied size or adds float clamps.
The bulk-loader join follows every word/scalar read through an unchanged
register into its first receiver store. Numeric update destinations join those
stores, including cache destinations before mask application. Whole-loader
symbolic integer flow proves the remaining byte-to-mask/Boolean joins and
selected cached-word stores for all admitted input bits and byte zero-tests.
Every numeric update selector now joins a serialized source. Raw copied words
and zero tests do not establish public control types or live activation.

The separate leaf helper proves a precise mask-controlled write: a selected
bit chooses zero or a cached word, which is written into an indexed record.
Its bit, cache and destination layouts are in the contract. No EQ/bypass label
or live effect activation follows from this anonymous representation.
"""
from __future__ import annotations

import hashlib
import json
import struct
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from scripts.game_data.contracts import CONTRACTS_DIR
from scripts.webui.audio.semantics.wwise_effect_integer_flow import IntegerFlow, IntegerFlowError
from scripts.webui.audio.semantics.wwise_effect_updates import EffectUpdateError


@lru_cache(maxsize=1)
def load_mastering_contract() -> dict[str, Any]:
    return json.loads((CONTRACTS_DIR / "wwise_mastering_updates_native.json").read_text(encoding="utf-8"))


def _payload_bytes(row, helper, start, finish):
    """Recognize complete handler bodies, leaving only the checked exit branch.

    The signed division-by-ten sequence is admitted only for nonnegative
    selector differences in the authenticated dispatch group. Control names
    and serialized offsets are deliberately absent from this representation.
    """
    p = row["payload"]
    kind = p["kind"]
    word = lambda n: struct.pack("<I", n & 0xffffffff).hex()
    byte = lambda n: bytes([n & 255]).hex()
    bias = p.get("selectorBias", 0)
    diffs = [ident - bias for ident in row["parameterIds"]]
    if not 0 <= bias <= 32767 or min(diffs) < 0:
        raise ValueError("Mastering payload selector difference is negative")
    lea = "418d48" + byte(-bias) if -128 <= -bias <= 127 else "418d88" + word(-bias)
    dest = p.get("receiverOffset", 0)
    if not 0 <= dest <= 0x7fffffff or not 0 <= p.get("recordBias", 0) <= 127:
        raise ValueError("Mastering payload displacement is outside its instruction domain")
    kind_prefix = ""
    def store(register, offset):
        small, large = {"rcx": ("8941", "8981"), "rbx": ("8943", "8983")}[register]
        return small + byte(offset) if offset < 128 else large + word(offset)
    if kind == "copyWord":
        kind_prefix = "418b01" + store(p["receiverRegister"], dest)
    elif kind == "booleanWord":
        kind_prefix = "33d24138110f95c28993" + word(dest)
    elif kind == "arrayWord":
        kind_prefix = "418b01" + lea + "89848b" + word(dest)
    elif kind in ("recordWord", "biasedRecordWord"):
        head = lea + "b867666666f7e9"
        if p["recordStride"] == 16 and kind == "recordWord":
            kind_prefix = head + "418b01c1fa028bcac1e91f03ca4803c98944cb" + byte(dest)
        elif p["recordStride"] == 24 and kind == "recordWord":
            kind_prefix = head + "c1fa028bc2c1e81f03d0418b01488d0c528984cb" + word(dest)
        elif p["recordStride"] == 24 and kind == "biasedRecordWord" and dest == p["recordBias"] * 24:
            kind_prefix = head + "c1fa028bc2c1e81f03c24883c0" + byte(p["recordBias"]) + "488d0c40418b018904cb"
    elif kind == "inverseMask":
        if max(diffs) >= 32:
            raise ValueError("Mastering mask index exceeds word")
        head = ("418bc8" if bias == 0 else lea) + "8bc7d3e041803900"
        load = "8b4b" + byte(dest) if dest < 128 else "8b8b" + word(dest)
        write = "894b" + byte(dest) if dest < 128 else "898b" + word(dest)
        left = "0bc8" + write
        # Both arms join completion. The earlier jump is inside the handler.
        next_at = row["bodyOffset"] + len(bytes.fromhex(head + load)) + 2 + len(bytes.fromhex(left))
        jump = "e9" + word(finish - (next_at + 5))
        kind_prefix = head + load + "75" + byte(len(bytes.fromhex(left + jump))) + left + jump + "f7d023c8" + write
    elif kind in ("maskAndRefresh", "cacheAndRefresh"):
        layout = helper["layout"]
        if kind == "maskAndRefresh":
            if max(diffs) >= 32:
                raise ValueError("Mastering mask index exceeds word")
            kind_prefix = ("33d2" + lea + "413811b8ffffffff448b83" + word(layout["maskOffset"])
                           + "0f44d08bc74133d0d3e023d04133d08993" + word(layout["maskOffset"])
                           + "8bd1488bcb")
        else:
            kind_prefix = (lea + "b867666666f7e9488bcbc1fa028bc2c1e81f03d0418b01898493"
                           + word(layout["cachedWordsOffset"]))
        call_at = start + row["bodyOffset"] + len(bytes.fromhex(kind_prefix))
        kind_prefix += "e8" + word(int(helper["rva"], 16) - call_at - 5)
    if not kind_prefix:
        raise ValueError(f"unrecognized Mastering payload shape: {kind}")
    return bytes.fromhex(kind_prefix)


def _bulk_word_joins(contract, structural, body, equal):
    method = structural["setParamsBlock"]
    equal("masteringBulkLength", 0, method["bodyLength"], len(body))
    equal("masteringBulkHash", 0, method["bodySha256"], hashlib.sha256(body).hexdigest())
    facts = contract["bulkWordJoins"]
    at = facts["receiverWitnessBodyOffset"]
    equal("masteringBulkReceiver", at, "488bf9", facts["receiverWitnessHex"])
    equal("masteringBulkReceiverBytes", at, bytes.fromhex(facts["receiverWitnessHex"]), body[at:at + 3])
    equal("masteringBulkInputBases", 0, 1, len(structural["inputBaseWitnesses"]))
    base = structural["inputBaseWitnesses"][0]
    equal("masteringBulkInputRegister", 0, "r9", base["register"])
    equal("masteringBulkInputBaseRange", 0, True, 0 <= base["inputBaseOffset"] < 128)
    encoded = bytes.fromhex("4c8d4a") + bytes([base["inputBaseOffset"]])
    equal("masteringBulkInputBase", base["bodyOffset"], encoded,
          body[base["bodyOffset"]:base["bodyOffset"] + len(encoded)])
    source_rows = {r["serializedOffset"]: r for r in structural["inputReads"]
                   if r["readKind"] in ("word32Copy", "scalar32Load")}
    equal("masteringBulkWordPartition", 0, sorted(source_rows), sorted(r["serializedOffset"] for r in facts["rows"]))
    destinations = {}
    for row in facts["rows"]:
        source = source_rows[row["serializedOffset"]]
        at = source["bodyOffset"]
        encoded = bytes.fromhex(source["instructionHex"])
        scalar = source["readKind"] == "scalar32Load"
        prefix = bytes.fromhex("f3410f10" if scalar else "418b")
        equal("masteringBulkReadOpcode", at, prefix, encoded[:len(prefix)])
        modrm = encoded[len(prefix)]
        equal("masteringBulkReadAddress", at, True, modrm in (0x41, 0x49, 0x81, 0x89))
        width = 1 if modrm < 0x80 else 4
        equal("masteringBulkReadExtent", at, len(prefix) + 1 + width, len(encoded))
        equal("masteringBulkReadOffset", at, source["serializedOffset"],
              base["inputBaseOffset"] + int.from_bytes(encoded[-width:], "little", signed=True))
        equal("masteringBulkReadBytes", at, encoded, body[at:at + len(encoded)])
        bridge = bytes.fromhex(row["bridgeInstructionHex"])
        # These complete instructions change flags or restore RSI, never the
        # loaded EAX/ECX/XMM0/XMM1, source R9 or receiver RDI.
        equal("masteringBulkBridgeKind", at, True, bridge.hex() in
              ("", "4184d2", "4184d0", "f6c210", "f6c220", "488b742410"))
        end = at + len(encoded)
        equal("masteringBulkBridgeBytes", at, bridge, body[end:row["storeBodyOffset"]])
        equal("masteringBulkStoreAdjacency", at, end + len(bridge), row["storeBodyOffset"])
        destination = row["receiverOffset"]
        equal("masteringBulkStoreRange", at, True, 0 <= destination <= 0x7fffffff)
        mode = 0x40 if destination < 128 else 0x80
        dest_modrm = mode | (modrm & 0x38) | 7
        store = (bytes.fromhex("f30f11" if scalar else "89") + bytes([dest_modrm])
                 + destination.to_bytes(1 if mode == 0x40 else 4, "little", signed=True))
        at = row["storeBodyOffset"]
        equal("masteringBulkStoreClaim", at, store.hex(), row["storeInstructionHex"])
        equal("masteringBulkStoreBytes", at, store, body[at:at + len(store)])
        equal("masteringBulkUniqueDestination", at, False, destination in destinations)
        destinations[destination] = source
    joins = []
    for handler in contract["handlers"]:
        p = handler["payload"]
        kind = p["kind"]
        if kind not in ("copyWord", "arrayWord", "recordWord", "biasedRecordWord", "cacheAndRefresh"):
            continue
        for ident in handler["parameterIds"]:
            index = ident - p.get("selectorBias", 0)
            if kind == "copyWord":
                dest = p["receiverOffset"]
            elif kind == "arrayWord":
                dest = p["receiverOffset"] + index * 4
            elif kind == "cacheAndRefresh":
                dest = contract["maskedWordHelper"]["layout"]["cachedWordsOffset"] + (index // 10) * 4
            else:
                dest = p["receiverOffset"] + (index // 10) * p["recordStride"]
            equal("masteringUpdateBulkJoin", handler["bodyOffset"], True, dest in destinations)
            source = destinations[dest]
            joins.append(dict(parameterId=ident, serializedOffset=source["serializedOffset"], receiverOffset=dest,
                              bulkReadKind=source["readKind"], cachedBeforeMask=kind == "cacheAndRefresh"))
    return dict(storedWordCount=len(destinations), updateJoins=sorted(joins, key=lambda r: r["parameterId"]),
                publicControlNamesProven=False)


def _bulk_byte_joins(contract, structural, body, word_joins, equal):
    """Prove Boolean joins using full straight-line native integer semantics."""
    try:
        flow = IntegerFlow(body).execute()
    except IntegerFlowError as exc:
        raise EffectUpdateError("masteringUpdates", "masteringBulkIntegerFlow", exc.offset,
                                "admitted complete straight-line loader", str(exc)) from exc
    byte_rows = {r["serializedOffset"]: r for r in structural["inputReads"] if r["readKind"] == "byteZeroTest"}
    facts = contract["bulkByteJoins"]
    equal("masteringByteBoundary", 0, "direct", facts["evidenceBoundary"])
    equal("masteringByteComparisonSet", 0, sorted(byte_rows), sorted(flow.byte_comparisons))
    equal("masteringByteSourcePartition", 0, sorted(byte_rows), sorted(r["serializedOffset"] for r in facts["rows"]))
    payloads = {ident: handler["payload"] for handler in contract["handlers"] for ident in handler["parameterIds"]}
    expected_ids = sorted(ident for ident, p in payloads.items()
                          if p["kind"] in ("inverseMask", "maskAndRefresh", "booleanWord"))
    equal("masteringByteSelectorSet", 0, expected_ids, [r["parameterId"] for r in facts["rows"]])
    graph = flow.graph
    for row in facts["rows"]:
        ident, source, dest = row["parameterId"], row["serializedOffset"], row["receiverOffset"]
        p = payloads[ident]
        if p["kind"] == "booleanWord":
            equal("masteringByteUpdateKind", byte_rows[source]["bodyOffset"], "nonzeroBooleanWord", row["kind"])
            equal("masteringByteUpdateDestination", 0, p["receiverOffset"], dest)
            expected = (graph.invert(flow.byte_zero(source)),) + (0,) * 31
            actual = flow.receiver_word(dest)
            differing = next((i for i, pair in enumerate(zip(expected, actual)) if pair[0] != pair[1]), None)
            if differing is not None:
                raise EffectUpdateError("masteringUpdates", "masteringByteBooleanValue", byte_rows[source]["bodyOffset"],
                                        {"source": source, "bit": differing, "value": graph.describe(expected[differing])},
                                        graph.describe(actual[differing]))
        else:
            equal("masteringByteUpdateKind", 0, "inverseZeroMask", row["kind"])
            expected_dest = p.get("receiverOffset", contract["maskedWordHelper"]["layout"]["maskOffset"])
            equal("masteringByteUpdateDestination", 0, expected_dest, dest)
            bit = row["maskBit"]
            equal("masteringByteMaskBit", 0, ident - p["selectorBias"], bit)
            equal("masteringByteMaskBitRange", 0, True, 0 <= bit < 32)
            expected, actual = flow.byte_zero(source), flow.receiver_word(dest)[bit]
            if expected != actual:
                raise EffectUpdateError("masteringUpdates", "masteringByteMaskValue", byte_rows[source]["bodyOffset"],
                                        {"source": source, "maskBit": bit, "value": graph.describe(expected)}, graph.describe(actual))
    for row in facts["maskRemainders"]:
        dest, first = row["receiverOffset"], row["firstBit"]
        covered = sorted(r["maskBit"] for r in facts["rows"] if r["kind"] == "inverseZeroMask" and r["receiverOffset"] == dest)
        equal("masteringMaskRemainderStart", 0, list(range(first)), covered)
        equal("masteringMaskRemainderKind", 0, True, row["kind"] in ("zero", "preserveInitial"))
        expected = (0,) * 32 if row["kind"] == "zero" else flow.initial_receiver(dest)
        equal("masteringMaskRemainderValue", 0, expected[first:], flow.receiver_word(dest)[first:])
    equal("masteringMaskRemainderSet", 0,
          sorted({r["receiverOffset"] for r in facts["rows"] if r["kind"] == "inverseZeroMask"}),
          sorted(r["receiverOffset"] for r in facts["maskRemainders"]))
    # Cross-check all word destinations through the independent symbolic model.
    for row in contract["bulkWordJoins"]["rows"]:
        equal("masteringSymbolicWordStore", row["storeBodyOffset"],
              flow.input_word(row["serializedOffset"]), flow.receiver_word(row["receiverOffset"]))
    cached = []
    mask_layout = contract["maskedWordHelper"]["layout"]
    inverse_sources = {(r["receiverOffset"], r.get("maskBit")): r["serializedOffset"] for r in facts["rows"]}
    for row in word_joins["updateJoins"]:
        if not row["cachedBeforeMask"]:
            continue
        index = (row["receiverOffset"] - mask_layout["cachedWordsOffset"]) // 4
        source = inverse_sources[(mask_layout["maskOffset"], index)]
        dest = (index + mask_layout["recordBias"]) * 16
        expected = tuple(graph.choose(flow.byte_zero(source), 0, bit) for bit in flow.input_word(row["serializedOffset"]))
        equal("masteringSymbolicMaskedRecord", 0, expected, flow.receiver_word(dest))
        cached.append(dict(parameterId=row["parameterId"], wordSerializedOffset=row["serializedOffset"],
                           zeroTestSerializedOffset=source, receiverOffset=dest, whenByteZero="writeZero"))
    return dict(evidenceBoundary="direct", rows=facts["rows"], maskRemainders=facts["maskRemainders"],
                cachedRecordJoins=cached, symbolicInputCoverage="all word bits and byte zero/nonzero combinations",
                runtimeInvocationObserved=False)


def validate_mastering_updates(
    contract: dict[str, Any], native_inputs: dict[str, Any],
    registration: dict[str, Any], image_base: int, read: Callable[[int, int], bytes],
    *, structural: dict[str, Any],
) -> dict[str, Any]:
    def equal(check, offset, expected, actual):
        if expected != actual:
            raise EffectUpdateError("masteringUpdates", check, offset, expected, actual)

    equal("masteringSchema", 0, "endfield.wwise-mastering-updates-native.v4", contract["schema"])
    equal("masteringReview", 0, "reviewedCurrentBuild", contract["status"])
    equal("masteringInputs", 0, native_inputs, contract["nativeInputs"])
    equal("masteringBoundary", 0, "direct", contract["evidenceBoundary"])
    method = contract["method"]
    start = int(method["rva"], 16)
    body = read(start, method["bodyLength"])
    equal("masteringBodyLength", 0, method["bodyLength"], len(body))
    equal("masteringBodyHash", 0, method["bodySha256"], hashlib.sha256(body).hexdigest())
    equal("masteringSlot", 0, 8, contract["vtableSlot"])
    equal("masteringSlotTarget", 0, start + image_base,
          struct.unpack("<Q", read(int(registration["vtableRva"], 16) + contract["vtableSlot"], 8))[0])
    pos = 0

    def take(size):
        nonlocal pos
        raw = body[pos:pos + size]
        equal("masteringInstructionExtent", pos, size, len(raw))
        pos += size
        return raw

    def expect(encoded):
        raw = bytes.fromhex(encoded)
        equal("masteringInstruction", pos, raw, take(len(raw)))

    def number():
        return struct.unpack("<I", take(4))[0]

    def relative(width=4):
        displacement = int.from_bytes(take(width), "little", signed=True)
        return pos + displacement

    def table(which, selector_prefix, target_prefix):
        expect(selector_prefix); selector = number() - start
        expect(target_prefix); target = number() - start
        declaration = contract["tables"][which]
        equal("masteringSelectorTable", pos, declaration["selectorOffset"], selector)
        equal("masteringTargetTable", pos, declaration["targetOffset"], target)
        count = declaration["targetCount"]
        equal("masteringTableAdjacency", target, selector, target + count * 4)
        targets = [rva - start for rva, in struct.iter_unpack("<I", body[target:selector])]
        indexes = body[selector:selector + declaration["selectorCount"]]
        equal("masteringSelectorExtent", selector, declaration["selectorCount"], len(indexes))
        routes = []
        for i in indexes:
            if i >= len(targets):
                raise EffectUpdateError("masteringUpdates", "masteringTableIndex", selector, f"< {len(targets)}", i)
            routes.append(targets[i])
        return routes

    expect("48895c2408574883ec204d8bc8488bd94c0fbfc2bf")
    success = number()
    expect("4181f8"); pivot = number()
    expect("0f8f"); higher = relative()
    expect("0f84"); pivot_handler = relative()
    expect("4181f8"); first_max = number()
    expect("0f87"); invalid = relative()
    expect("4c8d15"); equal("masteringImageBase", pos, 0, start + relative())
    first_routes = table(0, "430fb68402", "418b9482")
    equal("masteringFirstSelectorCount", pos, first_max + 1, len(first_routes))
    expect("4903d2ffe2")
    first_handler = pos
    equal("masteringHigherBlock", higher, contract["higherRangeOffset"], higher)
    pos = higher
    expect("4181f8"); upper_pivot = number()
    expect("0f8f"); upper_tail = relative()
    expect("0f84"); finish = relative()
    expect("418d80"); lower = -int.from_bytes(take(4), "little", signed=True)
    equal("masteringAdjacentRanges", pos, pivot + 1, lower)
    expect("3d"); second_max = number()
    expect("0f87"); equal("masteringInvalidJoin", pos, invalid, relative())
    expect("4c8d15"); equal("masteringImageBase", pos, 0, start + relative())
    expect("4898")
    second_routes = table(1, "410fb68402", "418b8c82")
    equal("masteringSecondSelectorCount", pos, second_max + 1, len(second_routes))
    expect("4903caffe1")
    second_handler = pos
    equal("masteringRangeOrder", pos, True, first_max < pivot < lower + second_max < upper_pivot)
    equal("masteringUpperTail", upper_tail, contract["upperTailOffset"], upper_tail)
    pos = upper_tail
    expect("4181f8"); sentinel = number()
    equal("masteringSentinelRange", pos, True, upper_pivot < sentinel <= 32767)
    expect("74"); equal("masteringNoopJoin", pos, finish, relative(1))
    equal("masteringInvalidEntry", pos, invalid, pos)
    expect("bf"); failure = number()
    equal("masteringFinishEntry", pos, finish, pos)
    expect("c683"); flag_offset = number(); flag_value = take(1)[0]
    expect("8bc7488b5c24304883c4205fc3")
    equal("masteringCodeEnd", pos, contract["codeByteLength"], pos)
    equal("masteringCompletion", finish, contract["completion"],
          dict(successReturnCode=success, invalidReturnCode=failure,
               flagReceiverOffset=flag_offset, flagValue=flag_value))
    equal("masteringTablePadding", pos, b"\x0f\x1f\x00", body[pos:contract["tables"][0]["targetOffset"]])
    equal("masteringMiddleTables", 0, contract["tables"][1]["targetOffset"],
          contract["tables"][0]["selectorOffset"] + len(first_routes))
    equal("masteringFinalTable", 0, len(body), contract["tables"][1]["selectorOffset"] + len(second_routes))

    groups: dict[int, list[int]] = {}
    for ident, target in [*enumerate(first_routes), *enumerate(second_routes, lower),
                          (pivot, pivot_handler), (upper_pivot, finish), (sentinel, finish)]:
        if target != invalid:
            groups.setdefault(target, []).append(ident)
    handlers = contract["handlers"]
    equal("masteringHandlerSet", 0, sorted(groups), sorted([row["bodyOffset"] for row in handlers] + [finish]))
    expected_start = first_handler
    for row in sorted(handlers, key=lambda r: r["bodyOffset"]):
        at, size = row["bodyOffset"], row["byteLength"]
        if expected_start == higher:
            expected_start = second_handler
        equal("masteringHandlerPartition", at, expected_start, at)
        equal("masteringHandlerIds", at, row["parameterIds"], groups[at])
        raw = body[at:at + size]
        equal("masteringHandlerHash", at, row["sha256"], hashlib.sha256(raw).hexdigest())
        tail_size = row["completionBranchBytes"]
        equal("masteringHandlerBranchSize", at, True, tail_size in (2, 5))
        equal("masteringPayload", at,
              _payload_bytes(row, contract["maskedWordHelper"], start, finish), raw[:-tail_size])
        pos = at + size - tail_size
        expect("eb" if tail_size == 2 else "e9")
        equal("masteringHandlerCompletion", at, finish, relative(tail_size - 1))
        expected_start = at + size
    equal("masteringLastHandler", expected_start, upper_tail, expected_start)
    helper = contract["maskedWordHelper"]
    raw = read(int(helper["rva"], 16), helper["bodyLength"])
    equal("masteringMaskHelperHash", 0, helper["bodySha256"], hashlib.sha256(raw).hexdigest())
    layout = helper["layout"]
    word = lambda n: struct.pack("<I", n).hex()
    # Complete leaf, including both returns and the exact conditional join.
    encoded = ("8b81" + word(layout["maskOffset"]) + "0fa3d0448bc2730d33d2498d40"
               + bytes([layout["recordBias"]]).hex() + "4803c08914c1c3428b9481"
               + word(layout["cachedWordsOffset"]) + "498d40" + bytes([layout["recordBias"]]).hex()
               + "4803c08914c1c3")
    equal("masteringMaskHelper", 0, bytes.fromhex(encoded), raw)
    for at in helper["directCallBodyOffsets"]:
        equal("masteringHelperCallOpcode", at, b"\xe8", body[at:at + 1])
        equal("masteringHelperCallTarget", at, int(helper["rva"], 16),
              start + at + 5 + struct.unpack_from("<i", body, at + 1)[0])
    bulk_method = structural["setParamsBlock"]
    bulk_body = read(int(bulk_method["rva"], 16), bulk_method["bodyLength"])
    bulk = _bulk_word_joins(contract, structural, bulk_body, equal)
    byte_joins = _bulk_byte_joins(contract, structural, bulk_body, bulk, equal)
    return {
        "status": "validated", "evidenceBoundary": "direct", "selectorInterpretation": "signedLow16",
        "handlerGroups": [{"parameterIds": row["parameterIds"], "bodyOffset": row["bodyOffset"]}
                          for row in handlers], "noValueReadSelectors": groups[finish],
        "payloads": [{"parameterIds": row["parameterIds"], **row["payload"]} for row in handlers],
        "recordSelectorDivisor": 10,
        "bulkWordJoins": bulk,
        "bulkByteJoins": byte_joins,
        "allUpdateSelectorsJoinedToSerializedSources": True,
        "completion": contract["completion"], "invalidSelectorWritesCompletionFlag": True,
        "maskedWordHelper": {**layout, "recordStrideBytes": 16,
                             "maskIndexInterpretation": "lowFiveBits", "addressIndexInterpretation": "unsigned32",
                             "whenMaskBitSet": "writeZero", "whenMaskBitClear": "copyCachedWord"},
        "meaningBoundary": contract["meaningBoundary"],
    }


def check_mastering_update_native_inputs(game_root: Path) -> dict[str, Any]:
    from scripts.webui.audio.semantics.wwise_effect_native import check_effect_native_extension

    def validate(parent, base, read):
        contract = load_mastering_contract()
        return validate_mastering_updates(contract, parent["nativeInputs"],
                                          parent["registrationWitnesses"][contract["classId"]], base, read,
                                          structural=parent["structuralSchemas"][contract["classId"]])

    return check_effect_native_extension(game_root, evidence_key="updates", validate=validate)
