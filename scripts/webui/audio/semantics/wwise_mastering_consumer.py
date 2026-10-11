"""Authenticate Mastering's parameter retention and conditional engine route.

The selected parameter constructor fixes a version-four section layout. The
effect retains that object, consumes its dirty byte and passes its section
pointers through a conversion dispatcher into an effect-local engine. A mask
bit is joined to that engine's per-record callback suppression test. This is
direct consumer evidence for anonymous sections, not public control names or
observed playback. The later context-indexed routine remains a separate gap.
"""
from __future__ import annotations

import hashlib
import json
import struct
from functools import lru_cache
from pathlib import Path

from scripts.game_data.contracts import CONTRACTS_DIR
from scripts.webui.audio.semantics.wwise_effect_integer_flow import IntegerFlow, IntegerFlowError
from scripts.webui.audio.semantics.wwise_effect_updates import EffectUpdateError


@lru_cache(maxsize=1)
def load_mastering_consumer_contract():
    return json.loads((CONTRACTS_DIR / "wwise_mastering_consumer_native.json").read_text(encoding="utf-8"))


def _callback_binding(contract, bodies, methods, image_base, read, equal, witness, call):
    """Recognize the complete callback binder and its two order-table joins."""
    binding = contract["callbackBinding"]
    equal("bindingBoundary", "contract", "direct", binding["evidenceBoundary"])
    offsets = [16, 24, 32, 40, 48, 56]
    equal("bindingSlots", "contract", offsets, binding["recordPointerOffsets"])
    body = bodies["bindCallbacks"]
    prefix = bytes.fromhex(
        "48895c240833c08bd84885c9750bb805008080488b5c2408c38b1183faff742685d2"
        "0f84d400000083fa010f849c00000083fa02746f83fa03743ec701ffffffffbb01022680"
        "4c8bd8488941084c8bd04c8bc84c8bc0488bd0488941108bc34c8959184c895128"
        "4c8949304c89412048895138488b5c2408c3")
    equal("bindingDispatcher", "body", prefix, body[:len(prefix)])
    paths = binding["paths"]
    equal("bindingSectionSet", "contract", list(range(4)), [p["sectionIndex"] for p in paths])
    # These registers are the six complete stores in the shared exit above.
    registers = {"488d05": 16, "4c8d1d": 24, "4c8d05": 32,
                 "4c8d15": 40, "4c8d0d": 48, "488d15": 56}
    expected_entry = len(prefix)
    rows = []
    start = int(methods["bindCallbacks"]["rva"], 16)
    common = body.index(bytes.fromhex("488941108bc34c895918"))
    for path in sorted(paths, key=lambda p: p["bodyOffset"]):
        position = path["bodyOffset"]
        equal("bindingPartition", str(path["sectionIndex"]), expected_entry, position)
        pointers = {}
        for operation in path["sequence"]:
            equal("bindingInstructionOffset", str(path["sectionIndex"]), position, operation["bodyOffset"])
            if operation["kind"] == "zeroAlias":
                equal("bindingZeroAlias", "operation", "4c8bc8", operation["instructionHex"])
                equal("bindingZeroBytes", "operation", b"\x4c\x8b\xc8", body[position:position + 3])
                equal("bindingZeroOrder", "operation", False, 16 in pointers)
                pointers[48] = None
                position += 3
            else:
                equal("bindingOperation", "operation", "lea", operation["kind"])
                prefix_hex = operation["prefixHex"]
                equal("bindingRegister", "operation", True, prefix_hex in registers)
                raw = body[position:position + 7]
                equal("bindingLea", "operation", bytes.fromhex(prefix_hex), raw[:3])
                destination = start + position + 7 + struct.unpack_from("<i", raw, 3)[0]
                equal("bindingPointer", "operation", int(operation["targetRva"], 16), destination)
                slot = registers[prefix_hex]
                equal("bindingUniqueRegister", "operation", False, slot in pointers)
                pointers[slot] = destination
                position += 7
        equal("bindingPointerSet", "operation", offsets, sorted(pointers))
        equal("bindingBranchOffset", "operation", position, path["branchOffset"])
        raw = bytes.fromhex(path["branchHex"])
        equal("bindingBranchBytes", "operation", raw, body[position:position + len(raw)])
        equal("bindingBranchOpcode", "operation", True, raw[0] in (0xeb, 0xe9))
        width = 1 if raw[0] == 0xeb else 4
        equal("bindingBranchExtent", "operation", width + 1, len(raw))
        equal("bindingCommonJoin", "operation", common,
              position + len(raw) + int.from_bytes(raw[1:], "little", signed=True))
        expected_entry = position + len(raw)
        rows.append(dict(sectionIndex=path["sectionIndex"], pointersByRecordOffset=pointers))
    equal("bindingEnd", "body", len(body), expected_entry)
    # Prove that each dispatcher case reaches the path with that section ID.
    for ident, condition, width in ((0, "85d20f84", 4), (1, "83fa010f84", 4),
                                    (2, "83fa0274", 1), (3, "83fa0374", 1)):
        encoded = bytes.fromhex(condition)
        extent = 2 + width if width == 4 else 2
        at = prefix.index(encoded) + len(encoded) - (extent - width)
        equal("bindingDispatchJoin", str(ident), paths[ident]["bodyOffset"],
              at + extent + int.from_bytes(body[at + extent - width:at + extent], "little", signed=True))

    call("controlEngineInitCall", "engineInit")
    call("engineInitInitializeCall", "engineInitialize")
    witness("engineInitializeOrderMode", "418bc54889b424b000000083e0014803c0")
    row, raw = witness("engineInitializeOrderTable")
    equal("orderTableOpcode", "engineInitialize", bytes.fromhex("488d0d"), raw[:3])
    table = int(methods["engineInitialize"]["rva"], 16) + row["bodyOffset"] + 7 + struct.unpack_from("<i", raw, 3)[0]
    equal("orderTable", "engineInitialize", int(binding["orderTableRva"], 16), table)
    witness("engineInitializeOrderPointers", "488d2cc14c8d3cc1")
    witness("engineInitializeLookup", "3b7500730a498b4708418b0c06eb05b9ffffffff890b")
    witness("engineInitializeBindArgs", "890b4885db0f84d1000000488bcb48c7434001000000")
    call("engineInitializeBindCall", "bindCallbacks")
    witness("engineInitializeStateBranch", "8b0383f8ff744f85c0743d83f801742a83f802741783f8030f858c000000")
    state_rows = binding["stateOffsets"]
    equal("engineStateSet", "contract", list(range(4)), [s["sectionIndex"] for s in state_rows])
    witnesses = contract["witnesses"]
    choice = witnesses["engineInitializeStateBranch"]["bodyOffset"]
    for state in state_rows:
        at = state["bodyOffset"]
        ident = state["sectionIndex"]
        if ident < 3:
            condition = bytes.fromhex(("85c074", "83f80174", "83f80274")[ident])
            branch = bodies["engineInitialize"].index(condition, choice, choice + 30) + len(condition) - 1
            destination = branch + 2 + int.from_bytes(bodies["engineInitialize"][branch + 1:branch + 2], "little", signed=True)
        else:
            destination = choice + len(bytes.fromhex(witnesses["engineInitializeStateBranch"]["instructionHex"]))
        equal("engineStateDispatchJoin", str(ident), at, destination)
        raw = bytes.fromhex("488d8f") + struct.pack("<I", state["receiverOffset"]) + bytes.fromhex("33c0488bd1")
        equal("engineStatePointer", str(ident), raw, bodies["engineInitialize"][at:at + len(raw)])
        branch = at + len(raw)
        equal("engineStateBranchOpcode", str(ident), 0xeb, bodies["engineInitialize"][branch])
        equal("engineStateStoreJoin", str(ident), witnesses["engineInitializeStateStore"]["bodyOffset"],
              branch + 2 + int.from_bytes(bodies["engineInitialize"][branch + 1:branch + 2], "little", signed=True))
    witness("engineInitializeStateStore", "48895308")
    witness("engineInitializeCallbackArguments", "498b47084d8bc4418b540604488b4310895340488d542420")
    witness("engineInitializeCallbackCall", "ffd0")
    witness("engineInitializeLoop", "ffc64883c3484983c61083fe040f822cffffffc747480100000044896f4c")
    orders = []
    equal("orderModes", "contract", [0, 1], [o["mode"] for o in binding["orders"]])
    for order in binding["orders"]:
        count, pointer = struct.unpack("<QQ", read(table + order["mode"] * 16, 16))
        equal("orderCount", str(order["mode"]), 4, count)
        equal("orderRowsPointer", str(order["mode"]), image_base + int(order["rowsRva"], 16), pointer)
        raw = read(pointer - image_base, count * 16)
        ids = [struct.unpack_from("<I", raw, at)[0] for at in range(0, len(raw), 16)]
        equal("orderRows", str(order["mode"]), order["sectionIds"], ids)
        equal("orderSectionSet", str(order["mode"]), list(range(4)), sorted(ids))
        orders.append(dict(mode=order["mode"], sectionIds=ids))
    return dict(evidenceBoundary="direct", callbackPointers=sorted(rows, key=lambda r: r["sectionIndex"]),
                nativeOrders=orders, publicSectionNamesProven=False, callbackMathematicsProven=False)


def validate_mastering_consumer(contract, parent, updates, image_base, read):
    def equal(check, role, expected, actual):
        if expected != actual:
            offset = contract.get("witnesses", {}).get(role, {}).get("bodyOffset", 0)
            raise EffectUpdateError("masteringConsumer", f"{check}:{role}", offset, expected, actual)

    equal("schema", "contract", "endfield.wwise-mastering-consumer-native.v2", contract["schema"])
    equal("status", "contract", "reviewedCurrentBuild", contract["status"])
    equal("inputs", "contract", parent["nativeInputs"], contract["nativeInputs"])
    equal("boundary", "contract", "direct", contract["evidenceBoundary"])
    equal("updateProof", "contract", "validated", updates["status"])
    equal("updateSources", "contract", True, updates["allUpdateSelectorsJoinedToSerializedSources"])
    methods = contract["methods"]
    bodies = {}
    for name, row in methods.items():
        raw = read(int(row["rva"], 16), row["bodyLength"])
        equal("methodLength", name, row["bodyLength"], len(raw))
        equal("methodHash", name, row["bodySha256"], hashlib.sha256(raw).hexdigest())
        bodies[name] = raw
    registration = parent["registrationWitnesses"][contract["classId"]]
    equal("factory", "registration", int(registration["factoryRva"], 16), int(methods["factory"]["rva"], 16))
    constructor = methods["parameterConstructor"]
    for key, parent_key in (("rva", "parameterConstructorRva"),
                            ("bodyLength", "parameterConstructorBodyLength"),
                            ("bodySha256", "parameterConstructorBodySha256")):
        expected, actual = registration[parent_key], constructor[key]
        equal("constructor", key, int(expected, 16) if key == "rva" else expected,
              int(actual, 16) if key == "rva" else actual)
    witnesses = contract["witnesses"]

    def witness(role, expected=None):
        row = witnesses[role]
        raw = bytes.fromhex(row["instructionHex"])
        at = row["bodyOffset"]
        equal("instruction", role, raw, bodies[row["method"]][at:at + len(raw)])
        if expected is not None:
            equal("operation", role, bytes.fromhex(expected), raw)
        return row, raw

    def target(role, opcode, target_rva=None, target_offset=None):
        row, raw = witness(role)
        prefix = bytes.fromhex(opcode)
        equal("relativeOpcode", role, prefix, raw[:len(prefix)])
        width = len(raw) - len(prefix)
        equal("relativeWidth", role, True, width in (1, 4))
        destination = row["bodyOffset"] + len(raw) + int.from_bytes(raw[-width:], "little", signed=True)
        expected = target_offset
        if target_rva is not None:
            destination += int(methods[row["method"]]["rva"], 16)
            expected = target_rva
        equal("relativeTarget", role, expected, destination)

    def call(role, name):
        target(role, "e8", target_rva=int(methods[name]["rva"], 16))

    def at(name, offset, encoded, role):
        raw = bytes.fromhex(encoded)
        equal("operation", role, raw, bodies[name][offset:offset + len(raw)])

    for role in witnesses:
        witness(role)
    u32 = lambda n: struct.pack("<I", n).hex()
    u8 = lambda n: bytes([n]).hex()
    layout = contract["layout"]
    param, state, engine = layout["parameterPointer"], layout["localState"], layout["enginePointer"]
    version, mask = layout["version"], layout["sectionMaskOffset"]
    source, dirty = layout["parameterSource"], layout["dirtyByte"]
    active, refresh = layout["activeByte"], layout["refreshByte"]
    witness("factoryVtableStore", "488908")
    row, raw = witness("factoryVtableLea")
    equal("vtableOpcode", "factory", b"\x48\x8d\x0d", raw[:3])
    vtable = int(methods["factory"]["rva"], 16) + row["bodyOffset"] + 7 + struct.unpack_from("<i", raw, 3)[0]
    equal("vtable", "factory", int(contract["effectVtableRva"], 16), vtable)
    equal("callbackSet", "factory", {"init": 48, "execute": 56}, contract["callbackSlots"])
    for name, slot in contract["callbackSlots"].items():
        equal("callback", name, image_base + int(methods[name]["rva"], 16), struct.unpack("<Q", read(vtable + slot, 8))[0])
    witness("factoryVersion", "c780" + u32(state) + u32(version))
    witness("parameterVersion", "c741" + u8(source) + u32(version))
    witness("initRetain", "4c8949" + u8(param) + "4d8bd04c8b4c2450488951"
            + u8(layout["allocatorPointer"]) + "4c8941" + u8(layout["contextPointer"])
            + "4c8981" + u32(layout["contextKey"]))
    witness("initAdmission", "80b9" + u32(active) + "00")
    target("initAdmissionBranch", "74", target_offset=witnesses["initPrepareJump"]["bodyOffset"] + 5)
    witness("initPrepareArgs", "498bd14883c428")
    target("initPrepareJump", "e9", target_rva=int(methods["prepare"]["rva"], 16))
    witness("executeAdmission", "80b9" + u32(active) + "00498bf1498be84c8bf2488bf9")
    target("executeAdmissionBranch", "0f84", target_offset=witnesses["executeExit"]["bodyOffset"])
    call("executeRefreshCall", "refresh")

    # The complete entry decision computes force ? 3 : (dirty ? 2 : 0).
    # A zero result returns before either flag is cleared or any callee runs.
    witness("syncFlags", "f6da488bd9488b49" + u8(param) + "1bc083e0038bf883cf0280b9"
            + u32(dirty) + "000f44f885ff750db001488b5c24784883c4605fc3")
    witness("syncClearFlags", "c683" + u32(refresh) + "00c681" + u32(dirty) + "00")
    witness("syncConvertArgs", "488b4b" + u8(param) + "488d93" + u32(state)
            + "4883c1" + u8(source) + "4533c94533c0")
    call("syncConvertCall", "convert")
    witness("syncConvertResult", "85c00f8588000000")
    # R8 is the converted state, R9 the engine object; zero frames apply state
    # without processing samples. The low flag bits carry init/update modes.
    witness("syncControlArgs", "8b83e00300004c8d83" + u32(state)
            + "4883bb18040000008bd0440fb6c8488b43180f95c148894424588b83e8030000"
              "897c2450884c244833c9c1ea0c8954244033d28944243844894c24304c8b4b"
            + u8(engine) + "c74424280000000048c744242000000000")
    call("syncControlCall", "engineControl")
    witness("syncControlResult", "85c07521")
    witness("syncFailureExit", "488b74247032c0488b5c24784883c4605fc3")
    witness("syncSuccessFlag", "488bcbc683" + u32(refresh) + "01")
    for role, width in (("syncConvertResult", 4), ("syncControlResult", 1)):
        row, raw = witness(role)
        equal("failureExitJoin", role, witnesses["syncFailureExit"]["bodyOffset"],
              row["bodyOffset"] + len(raw) + int.from_bytes(raw[-width:], "little", signed=True))
    row, raw = witness("prepareForceSync")
    equal("operation", "prepareForceArguments", bytes.fromhex("410fb6d7488bcb48897b" + u8(engine)), raw[:11])
    equal("operation", "prepareForceCallOpcode", b"\xe8", raw[11:12])
    # The immediately preceding R15d definition is one; no reassignment occurs
    # along the successful preparation path before its byte is passed in DL.
    witness("prepareForceOne", "41bf01000000")
    equal("prepareForceCall", "sync", int(methods["sync"]["rva"], 16),
          int(methods["prepare"]["rva"], 16) + row["bodyOffset"] + 16 + struct.unpack_from("<i", raw, 12)[0])
    witness("refreshSyncArgs", "33d2498bcc")
    call("refreshSyncCall", "sync")
    witness("refreshSyncResult", "84c07553")
    witness("refreshDirtyCheck", "4138bc24" + u32(refresh) + "7512498b4424" + u8(param)
            + "4038b8" + u32(dirty))
    target("refreshDirtyBranch", "0f84", target_offset=witnesses["refreshCleanExit"]["bodyOffset"])
    witness("refreshControlArgs", "498b4424184d8d8424" + u32(state)
            + "4939bc24180400004d8b4c24" + u8(engine)
            + "498b9424000400000f95c148894424588b8424f8000000897c2450884c2448"
              "498b8c24f803000089442440418b8424e8030000894424388b44246089442430"
              "498d44243044897424284889442420")
    call("refreshControlCall", "engineControl")

    # Version four selects these four section pointers on both sides. Header
    # words record anonymous type/revision tags and lengths, not public names.
    sections = contract["sections"]
    equal("sectionIndexes", "contract", list(range(4)), [s["index"] for s in sections])
    equal("layoutVersion", "sections", 4, version)
    witness("convertSourceVersion", "4183fa" + u8(version) + "0f851f020000")
    witness("convertDestinationVersion", "8b0a83f9010f84800100008bc183f902")
    witness("convertDestinationFour", "83f8" + u8(version) + "0f85d1000000")
    witness("convertMaskRead", "448b41" + u8(mask))
    witness("convertMaskWrite", "448942" + u8(mask))
    witness("convertDescriptorCount", "c7454704000000")
    witness("convertSourceDescriptorTable", "488d45f748899c24d000000033db4889454f")
    witness("convertDestinationDescriptorTable", "488d45b74889453fc7453704000000")
    for section in sections:
        ident, offset = section["index"], section["sourceOffset"]
        absolute = source + offset
        displacement = u8(absolute) if absolute < 128 else u32(absolute)
        prefix = "c741" if absolute < 128 else "c781"
        encoded = prefix + displacement + u32(section["header"])
        encoded += prefix + (u8(absolute + 4) if absolute < 128 else u32(absolute + 4)) + u32(section["byteLength"])
        at("parameterConstructor", section["constructorBodyOffset"], encoded, f"sectionHeader{ident}")
        equal("sectionId", str(ident), ident, section["header"] & 0xffff)
        lea_source = ("488d41" + u8(offset)) if offset < 128 else ("488d81" + u32(offset))
        at("convert", section["convertSourceBodyOffset"], lea_source + "488945" + u8((ident * 16 - 1) & 255), f"sectionSource{ident}")
        if offset < 128:
            lea_dest = ("488d4a" if ident == 0 else "488d42") + u8(offset)
        else:
            lea_dest = "488d82" + u32(offset)
        store_dest = ("48894d" if ident == 0 else "488945") + u8((ident * 16 - 65) & 255)
        at("convert", section["convertDestinationBodyOffset"], lea_dest + store_dest, f"sectionDestination{ident}")
        at("engineControl", section["engineDescriptorBodyOffset"], "b8" + u32(offset), f"engineSectionPointer{ident}")
        witness(f"sectionConversionArgs{ident}", "488b54d7084c8bce488b4908448bc5")
        target(f"sectionConversionCall{ident}", "e8", target_rva=int(section["conversionTargetRva"], 16))
    witness("convertSectionsArgs", "458bc3488d5537488d4d47")
    call("convertSectionsCall", "convertSections")
    witness("convertSectionSourceLoads", "488b7a084c897c24504c8b7908")
    witness("convertSectionLoop", "8bd34803d2418b04d7498d0cd785c0745183e801743683e801741b83f801757f")
    witness("convertSectionResultLoop", "85c07525ffc3413b1e0f827bffffff33c0")

    # Reuse the loader's symbolic model to prove it preserves the constructor
    # version and section headers. The update proof supplies all byte joins.
    bulk = parent["structuralSchemas"][contract["classId"]]["setParamsBlock"]
    bulk_body = read(int(bulk["rva"], 16), bulk["bodyLength"])
    equal("bulkLength", "headers", bulk["bodyLength"], len(bulk_body))
    equal("bulkHash", "headers", bulk["bodySha256"], hashlib.sha256(bulk_body).hexdigest())
    try:
        flow = IntegerFlow(bulk_body).execute()
    except IntegerFlowError as exc:
        raise EffectUpdateError("masteringConsumer", "bulkIntegerFlow", exc.offset,
                                "supported authenticated loader", str(exc)) from exc
    for offset in [source, *(source + s["sourceOffset"] + delta for s in sections for delta in (0, 4))]:
        equal("preservedHeader", str(offset), flow.initial_receiver(offset), flow.receiver_word(offset))
    joins = {r["parameterId"]: r for r in updates["bulkByteJoins"]["rows"]}
    control_rows = []
    for ident in range(4):
        row = joins[ident]
        equal("sectionByteKind", str(ident), "inverseZeroMask", row["kind"])
        equal("sectionByteMask", str(ident), source + mask, row["receiverOffset"])
        equal("sectionByteBit", str(ident), ident, row["maskBit"])
        control_rows.append(dict(sectionIndex=ident, serializedOffset=row["serializedOffset"],
                                 whenByteZero="skipProcessingCallback", whenByteNonzero="callbackEligible"))
    witness("controlStateRetain", "448b6d784d8bf14533c9498bd8418bc1")
    witness("controlModeGate", "41f6c4020f84220400004885db0f8448040000")
    witness("controlVersionDispatch", "8b0383f8010f841003000083f8020f841702000083f8030f840e01000083f804740ab807008080e921040000")
    witness("controlEnginePointer", "413b7e34498d76" + u8(layout["engineSubobject"]) + "0f85620400004c8bbda8000000")
    witness("controlSectionDispatch", "400fb6cf41b80100000041d3e0418bc883e901745883e901743c83e902742083f9040f8549030000")
    witness("controlSectionDescriptorPointer", "4803c34889440c38")
    witness("controlMaskTest", "488bce448543" + u8(mask) + "458bc1410f95c0")
    call("controlToggleCall", "sectionToggle")
    witness("controlFourSections", "66ffc76683ff040f83c40200004533c9e947ffffff")
    record = contract["engineRecord"]
    stride, key = record["strideBytes"], record["baseOffset"]
    equal("recordStride", "engine", 72, stride)
    toggle = "4885c9745383fa047f4e4183f8017748f64148017506b803022680c3"
    for ident in range(4):
        key_offset, disabled = key + ident * stride, record["disabledWordOffset"] + ident * stride
        compare = ("3951" + u8(key_offset)) if key_offset < 128 else ("3991" + u32(key_offset))
        store = "448981" + u32(disabled)
        toggle += compare + "7507" + store
    toggle += "33c0c3b801022680c3"
    equal("toggleBody", "engine", bytes.fromhex(toggle), bodies["sectionToggle"])
    witness("controlProcessArguments", "4c8b45584d8bce488b5550488bce44896c2420")
    call("controlProcessCall", "engineProcess")
    witness("engineRecordLoad", "480fbfc7488d0cc041837ccf" + u8(key) + "ff")
    equal("unusedId", "engine", 0xffffffff, record["unusedSectionId"])
    loop = witnesses["engineLoop"]
    target("engineUnusedBranch", "74", target_offset=loop["bodyOffset"] + len(bytes.fromhex(loop["instructionHex"])))
    witness("engineDisabledTest", "4183bccf" + u32(record["disabledWordOffset"]) + u8(record["disabledValue"]))
    equal("disabledValue", "engine", 1, record["disabledValue"])
    target("engineDisabledBranch", "74", target_offset=loop["bodyOffset"])
    witness("engineCallbackArguments", "498b44cf" + u8(record["processingCallbackOffset"])
            + "4d8bce498b4ccf" + u8(record["statePointerOffset"]) + "4c8bc3498bd4896c2420")
    witness("engineCallbackCall", "ffd0")
    witness("engineLoop", "66ffc76683ff047cb0")

    # Authenticate the later call and its key/stride, without attaching the
    # local engine's section meanings to this separate shared-state routine.
    witness("contextKeyRead", "4c8b87" + u32(layout["contextKey"]))
    for role, prefix in (("contextLookupCount", "8b15"), ("contextLookupTable", "4c8b0d"),
                         ("contextRecordBase", "48030d")):
        _, raw = witness(role)
        equal("ripOpcode", role, bytes.fromhex(prefix), raw[:-4])
    witness("contextLookup", "4d3904c17406ffc03bc272f48bd8")
    witness("contextRecordStride", "486bcb" + u8(contract["contextRoutine"]["recordStrideBytes"]))
    target("contextRoutineCall", "e8", target_rva=int(contract["contextRoutine"]["rva"], 16))
    equal("executionOrder", "callback", True, witnesses["executeRefreshCall"]["bodyOffset"] < witnesses["contextRoutineCall"]["bodyOffset"])
    binding = _callback_binding(contract, bodies, methods, image_base, read, equal, witness, call)
    return dict(status="validated", evidenceBoundary="direct", parameterObjectRetained=True,
                parameterLayoutVersion=version, bankLoaderPreservesSectionHeaders=True,
                syncFlags={"forced": 3, "dirty": 2, "unchanged": 0}, dirtyClearedBeforeConversion=True,
                conversionFailureReturnsFalseAfterClearingDirty=True,
                sectionPointers=[dict(index=s["index"], sourceOffset=s["sourceOffset"], byteLength=s["byteLength"],
                                      header=s["header"]) for s in sections],
                sectionControls=dict(evidenceBoundary="conditional", rows=control_rows,
                                     condition="version-four effect state, successful parameter conversion and an admitted initialized engine record",
                                     publicControlNamesProven=False),
                unusedRecordEndsSectionLoop=True,
                callbackBinding=binding,
                contextRoutine=contract["contextRoutine"], runtimeInvocationObserved=False,
                meaningBoundary=contract["meaningBoundary"])


def check_mastering_consumer_native_inputs(game_root: Path):
    from scripts.webui.audio.semantics.wwise_effect_native import check_effect_native_extension
    from scripts.webui.audio.semantics.wwise_mastering_updates import load_mastering_contract, validate_mastering_updates

    def validate(parent, base, read):
        contract = load_mastering_consumer_contract()
        class_id = contract["classId"]
        updates = validate_mastering_updates(load_mastering_contract(), parent["nativeInputs"],
                                             parent["registrationWitnesses"][class_id], base, read,
                                             structural=parent["structuralSchemas"][class_id])
        return validate_mastering_consumer(contract, parent, updates, base, read)

    return check_effect_native_extension(game_root, evidence_key="consumer", validate=validate)
