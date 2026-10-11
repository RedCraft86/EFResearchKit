"""Authenticate the initializer's stored defaults and bounded profile selection."""
from __future__ import annotations

import hashlib
import json
import struct
from functools import lru_cache
from pathlib import Path

from scripts.game_data.contracts import CONTRACTS_DIR
from scripts.webui.audio.semantics.wwise_effect_updates import EffectUpdateError


@lru_cache(maxsize=1)
def load_mastering_profiles_contract():
    return json.loads((CONTRACTS_DIR / "wwise_mastering_profiles_native.json").read_text(encoding="utf-8"))


def validate_mastering_profiles(contract, native_inputs, dynamics_contract, dynamics, image_base, read):
    def equal(check, expected, actual, offset=0):
        if expected != actual:raise EffectUpdateError("masteringProfiles", check, offset, expected, actual)
    equal("schema", "endfield.wwise-mastering-profiles-native-contract.v1", contract["schema"])
    equal("reviewStatus", "reviewed", contract["status"]); equal("boundary", "conditional", contract["evidenceBoundary"])
    equal("inputs", native_inputs, contract["nativeInputs"]); equal("parentInputs", native_inputs, dynamics_contract["nativeInputs"])
    equal("parentProof", "validated", dynamics["status"])
    comparison = contract["comparison"]; equal("comparisonEntry", "profileCompare", comparison["dynamicsExternal"])
    rva = int(dynamics_contract["externals"][comparison["dynamicsExternal"]]["rva"], 16)
    length = comparison["bodyLength"]; equal("comparisonExtent", True, type(length) is int and 0 < length <= 4096)
    digest = hashlib.sha256(read(rva, length)).hexdigest(); equal("comparisonBody", comparison["bodySha256"], digest)
    witness = comparison["symbolWitness"]
    equal("comparisonSymbol", "strcmp", witness["symbol"]); equal("comparisonWholeMatch", True, witness["exactNativeMatch"])
    equal("comparisonNamedBody", (length, digest), (witness["bodyLength"], witness["bodySha256"]))
    selection = contract["peakSelection"]
    equal("selectionShape", dict(pointerData="defaultProfilePointer", keyData="profileKeyPrefix", entries=1, recordStride=36, selectorPrefixBytes=4),
          {k:selection[k] for k in ("pointerData", "keyData", "entries", "recordStride", "selectorPrefixBytes")})
    key = bytes.fromhex(selection["keyHex"])
    equal("keyFraming", True, 1 <= len(key) <= 256 and key[-1:] == b"\0" and b"\0" not in key[:-1])
    data = dynamics_contract["data"]; key_rva = int(data[selection["keyData"]]["rva"], 16)
    equal("selectionKey", key, read(key_rva, len(key)))
    pointer_rva = int(data[selection["pointerData"]]["rva"], 16)
    equal("fileDefaultPointer", image_base+key_rva, struct.unpack("<Q", read(pointer_rva, 8))[0])
    bodies = {}; methods = dynamics_contract["methods"]
    for name in ("initPeak", "initBands"):
        row = methods[name]; raw = read(int(row["rva"], 16), row["bodyLength"])
        equal("methodHash:"+name, row["bodySha256"], hashlib.sha256(raw).hexdigest()); bodies[name] = raw
    grammar = dict(peakLoopLoad="488b17", peakCompareResult="85c0742a", peakLoopCount="ffc34883c70883fb0172e2",
        peakNoMatch="b806008080", peakRecordArguments="8bc34c8bcd488bce4c8d04c0",
        peakApplyResult="85c078be", peakSuccessFlag="c7464403000000",
        bandDefaultArguments="4c8bce0f2874244041b8ffff00004c8b742470488bcb488b7c2468488b6c2460",
        bandApplyResult="85c07817c7434403000000")
    equal("controlRoles", set(grammar), set(contract["controlOffsets"]))
    for name, expected in grammar.items():
        row = contract["controlOffsets"][name]; at = row["offset"]; raw = bytes.fromhex(expected)
        equal("control:"+name, raw, bodies[row["method"]][at:at+len(raw)], at)
    # Parent byte coverage supplies the methods, but these role joins independently
    # establish which key, record and application each initializer actually uses.
    for method, offset, kind, target in (("initPeak", 0x41, "data", selection["pointerData"]),
        ("initPeak", 0x83, "data", selection["keyData"]), ("initPeak", 0x8a, "external", comparison["dynamicsExternal"]),
        ("initPeak", 0xc9, "data", contract["defaultRows"]["peak"]["sourceData"]), ("initPeak", 0xdc, "method", "applyPeak"),
        ("initBands", 0x3ab, "data", contract["defaultRows"]["bands"]["sourceData"]), ("initBands", 0x3d7, "method", "applyBands")):
        matches = [p for p in methods[method]["program"] if p["offset"] == offset]
        equal("initializerRoleCount:"+method, 1, len(matches), offset); step = matches[0]
        equal("initializerRoleJoin:"+method, (kind, target), (step["targetKind"], step["target"]), offset)
    equal("recordSet", {"bands", "peak"}, set(contract["defaultRows"]))
    rows = {}
    for name, row in contract["defaultRows"].items():
        equal("recordDataRole", "bandDefaultProfilePrefix" if name == "bands" else "defaultProfilePrefix", row["sourceData"])
        words = row["rawWords"]; size = row["byteLength"]
        equal("recordExtent", True, type(size) is int and 0 < size <= 4096 and len(words)*4 == size and all(type(w) is int and 0 <= w <= 0xffffffff for w in words))
        raw = struct.pack("<"+"I"*len(words), *words); equal("recordBytes:"+name, raw, read(int(data[row["sourceData"]]["rva"], 16), size))
        prefix = 4 if name == "peak" else 0
        equal("legacyHeader:"+name, (0x01010003 if name == "peak" else 0x01010001, size-prefix), struct.unpack_from("<II", raw, prefix))
        if name == "peak":equal("storedSelector", 0xffff, words[0])
        rows[name] = dict(legacyPayloadBytes=size-prefix, payloadByteOffset=prefix, selector=0xffff)
    # The selected section-three record starts with a selector, then a payload.
    peak = bodies["initPeak"]; arguments = contract["controlOffsets"]["peakRecordArguments"]["offset"]
    record = arguments+12+7
    raw = bytes.fromhex("488d50044a8d1482468b0480")
    equal("peakPayloadAndSelector", raw, peak[record:record+len(raw)], record)
    return dict(status="validated", evidenceBoundary="conditional", exactNamedStringComparisonBodyProven=True,
        fileDefaultPeakKeyMatches=True, peakProfileCount=1, defaultInitializationRows=rows,
        legacyDefaultApplicationArgumentsProven=True, fullLegacyApplicationArithmeticProven=False,
        mutablePointerLifetimeProven=False, runtimeSelectionObserved=False, publicControlNamesProven=False,
        meaningBoundary=contract["meaningBoundary"])


def check_mastering_profiles_native_inputs(game_root: Path):
    from scripts.webui.audio.semantics.wwise_effect_native import check_effect_native_extension
    from scripts.webui.audio.semantics.wwise_mastering_dynamics import load_mastering_dynamics_contract, validate_mastering_dynamics_effect_context
    def validate(parent, base, read):
        dynamics = validate_mastering_dynamics_effect_context(parent, base, read)
        return validate_mastering_profiles(load_mastering_profiles_contract(), parent["nativeInputs"], load_mastering_dynamics_contract(), dynamics, base, read)
    return check_effect_native_extension(game_root, evidence_key="profiles", validate=validate)
