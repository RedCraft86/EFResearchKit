"""Authenticate the selected image's static Mastering SIMD startup route.

The process-attach path and initializer pointer loop are direct native facts.
Its prerequisite gates, loader dispatch and other initializers remain conditions;
the audit does not observe a loaded client or prove constant immutability.
"""
from __future__ import annotations

import hashlib
import json
import struct
from functools import lru_cache
from pathlib import Path

from scripts.game_data.contracts import CONTRACTS_DIR
from scripts.webui.audio.semantics.wwise_effect_updates import EffectUpdateError


@lru_cache(maxsize=1)
def load_mastering_startup_contract():
    return json.loads((CONTRACTS_DIR / "wwise_mastering_startup_native.json").read_text(encoding="utf-8"))


def validate_mastering_startup(contract, native_inputs, dynamics_contract, dynamics, scalar_contract, image_base, read):
    def equal(check, expected, actual, offset=0):
        if expected != actual:
            raise EffectUpdateError("masteringStartup", check, offset, expected, actual)

    equal("schema", "endfield.wwise-mastering-startup-native-contract.v2", contract["schema"])
    equal("reviewStatus", "reviewed", contract["status"])
    equal("inputs", native_inputs, contract["nativeInputs"])
    equal("dynamicsInputs", native_inputs, dynamics_contract["nativeInputs"])
    equal("scalarInputs", native_inputs, scalar_contract["nativeInputs"])
    equal("dynamicsProof", ("validated", True), (dynamics["status"], dynamics["simdInitializerWritesProven"]))
    equal("boundary", "conditional", contract["evidenceBoundary"])
    methods = contract["methods"]; references = contract["references"]
    equal("methodSet", {"entry", "dllStart", "reasonRoute", "processAttach", "initializerWalk", "guardThunk", "guardTarget", "errorInitializerWalk", "fmaInitialize"}, set(methods))
    pe_offset = struct.unpack("<I", read(60, 4))[0]
    equal("peSignature", b"PE\0\0", read(pe_offset, 4))
    optional = pe_offset + 24
    equal("optionalHeaderJoin", optional, int(contract["pe"]["optionalHeaderRva"], 16))
    equal("optionalHeaderMagic", 0x20b, struct.unpack("<H", read(optional, 2))[0])
    equal("entryFieldOffset", 16, contract["pe"]["entryPointFieldOffset"])
    equal("peEntryPointJoin", int(methods["entry"]["rva"], 16), struct.unpack("<I", read(optional + 16, 4))[0])
    bodies = {}
    for name, row in methods.items():
        size = row["bodyLength"]
        equal("extent:" + name, True, type(size) is int and 0 < size <= 512)
        body = read(int(row["rva"], 16), size); bodies[name] = body
        equal("length:" + name, size, len(body))
        equal("hash:" + name, row["bodySha256"], hashlib.sha256(body).hexdigest())
        cursor = 0
        for step in row["program"]:
            equal("coverage:" + name, cursor, step["offset"], cursor)
            if "bytesHex" in step:
                raw = bytes.fromhex(step["bytesHex"])
                equal("nonempty:" + name, True, bool(raw), cursor)
                equal("program:" + name, raw, body[cursor:cursor + len(raw)], cursor)
                cursor += len(raw)
                continue
            prefix = bytes.fromhex(step["prefixHex"]); suffix = bytes.fromhex(step["suffixHex"])
            end = cursor + len(prefix) + 4 + len(suffix); raw = body[cursor:end]
            equal("relativeLength:" + name, end - cursor, len(raw), cursor)
            equal("relativeOpcode:" + name, prefix, raw[:len(prefix)], cursor)
            equal("relativeSuffix:" + name, suffix, raw[len(prefix) + 4:], cursor)
            groups = dict(method=methods, reference=references, external=contract["externals"],
                          scalarSelector=dict(runtimeSelector=dict(rva=scalar_contract["runtimeSelector"]["cellRva"])))
            kind = step["targetKind"]
            equal("relativeKind:" + name, True, kind in groups, cursor)
            target = int(groups[kind][step["target"]]["rva"], 16)
            actual = int(row["rva"], 16) + end + struct.unpack_from("<i", raw, len(prefix))[0]
            equal("relativeTarget:" + name, target, actual, cursor)
            cursor = end
        equal("programEnd:" + name, size, cursor, cursor)

    def block(name, offset, encoded):
        raw = bytes.fromhex(encoded)
        equal("controlFlow:" + name, raw, bodies[name][offset:offset + len(raw)], offset)

    block("entry", 0x17, "83fa017505")
    block("dllStart", 0x35, "8d42ff83f8017740")
    block("reasonRoute", 4, "85d2743983ea01742883ea01741683fa01740a")
    block("processAttach", 0x7a, "85c07529")
    block("processAttach", 0x83, "84c07420")
    block("initializerWalk", 0, "483bca743b48895c2408574883ec20488bfa488bd9488b034885c07410")
    block("initializerWalk", 0x2d, "4883c308483bdf75df488b5c24304883c4205fc3")
    block("guardTarget", 0, "ffe0")
    block("errorInitializerWalk", 0, "48895c2408574883ec20488bfa488bd9483bca7425488b034885c07414")
    block("errorInitializerWalk", 0x2d, "85c0750b4883c308483bdfebd933c0488b5c24304883c4205fc3")
    # CPUID clobbers EAX/EBX/ECX/EDX; R8 remains the zero/one accumulator.
    block("fmaInitialize", 0, "40534883ec104533c033c9")
    block("fmaInitialize", 0x12, "458d4801418bc10fa2890424b800100018894c240823c8895c24048954240c3bc8752c33c90f01d048c1e220480bd04889542420488b442420")
    block("fmaInitialize", 0x52, "24063c06450f44c1")
    block("fmaInitialize", 0x68, "33c04883c4105bc3")
    equal("guardTargetExtent", 2, len(bodies["guardTarget"]))
    for name, offset, target in (("entry", 0x38, "dllStart"), ("dllStart", 0x6a, "reasonRoute"),
                                 ("reasonRoute", 0x3c, "processAttach")):
        step = next(s for s in methods[name]["program"] if s["offset"] == offset)
        equal("startupRouteJoin:" + name, ("method", target), (step["targetKind"], step["target"]), offset)
    equal("guardPointer", image_base + int(methods["guardThunk"]["rva"], 16),
          struct.unpack("<Q", read(int(references["guardDispatchPointer"]["rva"], 16), 8))[0])
    equal("guardTargetPointer", image_base + int(methods["guardTarget"]["rva"], 16),
          struct.unpack("<Q", read(int(references["guardTargetPointer"]["rva"], 16), 8))[0])
    equal("guardDispatchJoin", "guardDispatchPointer", methods["initializerWalk"]["program"][1]["target"])
    equal("guardThunkJoin", "guardTargetPointer", methods["guardThunk"]["program"][0]["target"])
    begin = int(references["initializerBegin"]["rva"], 16); end = int(references["initializerEnd"]["rva"], 16)
    table = contract["initializerTable"]
    equal("tableBounds", True, 0 < end - begin <= 16384 and (end - begin) % 8 == 0)
    equal("tableExtent", end - begin, table["byteLength"])
    equal("tableCount", table["byteLength"] // 8, len(table["entries"]))
    expected = [image_base + int(r, 16) if r is not None else 0 for r in table["entries"]]
    actual = struct.unpack("<" + "Q" * len(expected), read(begin, end - begin))
    equal("tableValues", expected, list(actual))
    joins = table["selectedInitializerJoins"]; vectors = dynamics_contract["initializedVectors"]
    equal("initializerNames", set(vectors), {r["name"] for r in joins})
    equal("initializerJoinCount", len(vectors), len(joins))
    for row in joins:
        offset = row["tableByteOffset"]
        equal("initializerOffset", True, type(offset) is int and 0 <= offset < end - begin and offset % 8 == 0)
        target = image_base + int(vectors[row["name"]]["rva"], 16)
        equal("initializerPointer:" + row["name"], target, actual[offset // 8], offset)
    for offset, target in ((0x87, "initializerEnd"), (0x8e, "initializerBegin")):
        step = next(s for s in methods["processAttach"]["program"] if s["offset"] == offset)
        equal("attachTableArgument", ("reference", target), (step["targetKind"], step["target"]), offset)
    step = next(s for s in methods["processAttach"]["program"] if s["offset"] == 0x95)
    equal("attachWalkJoin", ("method", "initializerWalk"), (step["targetKind"], step["target"]), 0x95)
    cpu = contract["cpuInitialization"]
    equal("cpuPredicate", dict(cpuidLeaf=1, requiredEcxMask="0x18001000", xgetbvIndex=0, requiredXcr0Mask=6,
          predicate="ECX contains every required CPUID bit and XCR0 contains both required bits", selectorValues=dict(unavailable=0, available=1)),
          {k:cpu[k] for k in ("cpuidLeaf", "requiredEcxMask", "xgetbvIndex", "requiredXcr0Mask", "predicate", "selectorValues")})
    for offset, target in ((0x67, cpu["tableEndReference"]), (0x6e, cpu["tableBeginReference"]), (0x75, "errorInitializerWalk")):
        step = next(p for p in methods["processAttach"]["program"] if p["offset"] == offset)
        equal("cpuTableRoute", ("method" if offset == 0x75 else "reference", target), (step["targetKind"], step["target"]), offset)
    begin = int(references[cpu["tableBeginReference"]]["rva"], 16); end = int(references[cpu["tableEndReference"]]["rva"], 16)
    equal("cpuTableBound", True, 0 < end-begin <= 16384 and (end-begin) % 8 == 0)
    equal("cpuTableExtent", end-begin, cpu["tableByteLength"]); equal("cpuTableCount", (end-begin)//8, len(cpu["entries"]))
    actual = struct.unpack("<"+"Q"*len(cpu["entries"]), read(begin, end-begin))
    equal("cpuTablePointers", [image_base+int(r,16) if r is not None else 0 for r in cpu["entries"]], list(actual))
    offset = cpu["selectedTableByteOffset"]; equal("cpuTableSelectedBound", True, type(offset) is int and 0 <= offset < end-begin and offset % 8 == 0)
    equal("cpuInitializerPointer", image_base+int(methods["fmaInitialize"]["rva"],16), actual[offset//8], offset)
    for offset, kind, target, prefix in ((0xb, "reference", "cpuAvailability", "448905"), (0x4b, "reference", "cpuAvailability", "448b05"),
        (0x5a, "reference", "cpuAvailability", "448905"), (0x61, "scalarSelector", "runtimeSelector", "448905")):
        step = next(p for p in methods["fmaInitialize"]["program"] if p["offset"] == offset)
        equal("cpuStateJoin", (kind, target, prefix, ""), (step["targetKind"], step["target"], step["prefixHex"], step["suffixHex"]), offset)
    step = next(p for p in methods["errorInitializerWalk"]["program"] if p["offset"] == 0x27)
    equal("cpuWalkerDispatch", ("reference", "guardDispatchPointer", "ff15"), (step["targetKind"], step["target"], step["prefixHex"]), 0x27)
    return dict(status="validated", evidenceBoundary="conditional", peEntryPointProven=True,
                processAttachInitializerRouteProven=True, selectedInitializerCount=len(joins),
                initializerRange="half-open, eight-byte pointers, skips null entries",
                fileDefaultDispatch="indirect thunk then jump to RAX", prerequisiteGateSuccessAssumed=True,
                loaderDispatchUnchangedAssumed=True, otherInitializerEffectsProven=False,
                simdConstantImmutabilityProven=False, runtimeInvocationObserved=False,
                cpuSelectorInitializerRouteProven=True, cpuSelectorPredicateProven=True,
                cpuSelectorPredicate="CPUID leaf 1 ECX mask; conditional XGETBV index 0 mask",
                earlierInitializerSuccessAssumed=True, laterSelectorImmutabilityProven=False, liveCpuSelectionObserved=False,
                meaningBoundary=contract["meaningBoundary"])


def check_mastering_startup_native_inputs(game_root: Path):
    from scripts.webui.audio.semantics.wwise_effect_native import check_effect_native_extension
    from scripts.webui.audio.semantics.wwise_mastering_dynamics import (
        load_mastering_dynamics_contract, validate_mastering_dynamics_effect_context)
    from scripts.webui.audio.semantics.wwise_effect_scalar import load_scalar_contract

    def validate(parent, base, read):
        dynamics = validate_mastering_dynamics_effect_context(parent, base, read)
        return validate_mastering_startup(load_mastering_startup_contract(), parent["nativeInputs"],
                                         load_mastering_dynamics_contract(), dynamics, load_scalar_contract(), base, read)

    return check_effect_native_extension(game_root, evidence_key="startup", validate=validate)
