"""Prove Mastering's admitted section-two gain route in the selected image.

This audit closes current-revision conversion, channel mapping, gain application
and sample multiplication. It does not name public controls or establish caller
buffer bounds, live activation or complete power-helper equivalence.
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
def load_mastering_gain_contract():
    return json.loads((CONTRACTS_DIR / "wwise_mastering_gain_native.json").read_text(encoding="utf-8"))


def validate_mastering_gain(contract, parent, updates, consumer, consumer_contract, scalar, small_fill, read):
    def equal(check, expected, actual, offset=0):
        if expected != actual:
            raise EffectUpdateError("masteringGain", check, offset, expected, actual)

    equal("schema", "endfield.wwise-mastering-gain-native-contract.v3", contract["schema"])
    equal("reviewStatus", "reviewed", contract["status"])
    equal("nativeInputs", parent["nativeInputs"], contract["nativeInputs"])
    equal("consumerProof", "validated", consumer["status"])
    equal("updateProof", "validated", updates["status"])
    equal("scalarProof", "validated", scalar["status"])
    equal("fillProof", "validated", small_fill["status"])
    equal("fillRange", [0, 144], small_fill["lengthRange"])
    equal("fillMeaning", True, small_fill["byteFill"])
    equal("fillClaim", ("unusedChannelGains", 48, "conditional"), tuple(contract["smallFill"][k]
          for k in ("purpose", "maximumBytes", "evidenceBoundary")))
    equal("boundary", "conditional", contract["evidenceBoundary"])
    equal("class", parent["classId"], contract["classId"])
    equal("consumerInputs", contract["nativeInputs"], consumer_contract["nativeInputs"])
    equal("section", 2, contract["sectionIndex"])
    methods = contract["methods"]
    equal("methodSet", {"convert", "clamp", "init", "apply", "process", "kernel"}, set(methods))
    bodies = {}
    for name, row in methods.items():
        size = row["bodyLength"]
        equal("methodExtent:" + name, True, type(size) is int and 0 < size <= 4096)
        body = read(int(row["rva"], 16), size)
        equal("methodLength:" + name, size, len(body))
        equal("methodHash:" + name, row["bodySha256"], hashlib.sha256(body).hexdigest())
        bodies[name] = body

    def block(name, offset, encoded):
        expected = bytes.fromhex(encoded)
        equal("program:" + name, expected, bodies[name][offset:offset + len(expected)], offset)

    def relative(name, offset, opcode, target):
        prefix = bytes.fromhex(opcode)
        raw = bodies[name][offset:offset + len(prefix) + 4]
        equal("relativeOpcode:" + name, prefix, raw[:len(prefix)], offset)
        equal("relativeExtent:" + name, len(prefix) + 4, len(raw), offset)
        address = int(methods[name]["rva"], 16) + offset + len(raw) + struct.unpack_from("<i", raw, len(prefix))[0]
        equal("relativeTarget:" + name, target, address, offset)

    def call(name, offset, target):
        relative(name, offset, "e8", int(methods[target]["rva"], 16))

    section = consumer["sectionPointers"][2]
    equal("sectionHeader", "0x01030002", contract["sectionHeader"])
    equal("sectionHeaderJoin", int(contract["sectionHeader"], 16), section["header"])
    equal("sectionLength", 64, contract["sectionByteLength"])
    equal("sectionLengthJoin", contract["sectionByteLength"], section["byteLength"])
    pointers = consumer["callbackBinding"]["callbackPointers"][2]["pointersByRecordOffset"]
    for slot, name in ((16, "init"), (32, "process"), (40, "apply"), (56, "convert")):
        equal("callbackJoin:" + name, int(methods[name]["rva"], 16), pointers.get(slot, pointers.get(str(slot))))
    equal("scalarBoundary", False, scalar["wholeFunctionEquivalent"])
    scalar_rva = int(scalar["methodRva"], 16)

    # Complete scalar clamp: unordered comparisons select the lower bound.
    block("clamp", 0, "0f2fc277050f2fc1730c0f2fc173040f28c1c30f28c2c3")
    equal("clampLength", 23, len(bodies["clamp"]))
    constants = contract["constants"]
    equal("constantSet", {"lower", "upper", "scale", "base"}, set(constants))
    for name, value in (("lower", -100.0), ("upper", 12.0), ("scale", 0.05), ("base", 10.0)):
        raw = read(int(constants[name]["rva"], 16), 4)
        equal("constant:" + name, struct.pack("<f", value), raw)
        equal("recordedConstant:" + name, raw.hex(), constants[name]["wordHex"])

    conversion = contract["conversion"]
    equal("conversionLayout", (4, 12, 8, [56, 60], 1, [8, 12], "lowerBound"),
          tuple(conversion[k] for k in ("version", "valueCount", "valuesOffset", "reservedOffsets",
                                        "specialMode", "specialModeEqualOffsets", "clampNaN")))
    # Exact dispatch to revision three, its size check and output header choice.
    block("convert", 0, "48895c2418564883ec40488bf2488bd94885c90f84730200004885d20f846a020000")
    block("convert", 0x22,
          "8b1181fa02000101751683790410742cb802022680488b5c24604883c4405ec3"
          "81fa02000201750683790430ebe081fa0200030175da8379044075d4"
          "8b0e8bc181f902000101741a81f902000201741281f902000301740a89168b43048946048bc28b0b")
    block("convert", 0x86, "0f297424300f297c242081f902000101753c")
    block("convert", 0xd4, "81f9020002010f85f4000000")
    block("convert", 0x1d4,
          "81f9020003010f85a50000003bc10f859d000000837b38000f8593000000"
          "837b3c000f85890000004183f801750bf30f10430c0f2e43087578")
    relative("convert", 0x20d, "f30f1035", int(constants["upper"]["rva"], 16))
    block("convert", 0x215, "482bde")
    relative("convert", 0x218, "f30f103d", int(constants["lower"]["rva"], 16))
    block("convert", 0x220, "48896c2450bd0c00000048897c2458488d7e080f1f4000660f1f840000000000f30f10041f0f28d60f28cf")
    call("convert", 0x24b, "clamp")
    block("convert", 0x250,
          "f30f1107488d7f044883ed0175e2488b7c245833c0488b6c245048894638"
          "33c00f287424300f287c2420488b5c24604883c4405ec3b808008080ebe4"
          "488b5c2460b8010226804883c4405ec3")
    equal("convertLength", 668, len(bodies["convert"]))

    state = contract["state"]
    equal("stateLayout", (0, 4, 12, 72, 68, 1, 2, 24, 8, 16),
          tuple(state[k] for k in ("channelCountOffset", "frameStrideOffset", "mappingOffset", "gainOffset",
                                  "flagsOffset", "initializedMask", "firstProcessMask", "descriptorMappingOffset",
                                  "descriptorChannelCountOffset", "descriptorStrideOffset")))
    # Native init copies the channel map; its default gain helper is outside
    # this claim. Successful init sets both initialized and first-process bits.
    block("init", 0,
          "40534883ec20488bd94885c974574885d274528b420889018b4210894104"
          "8b42148941080f1042180f11410c0f104a280f11491c0f1042380f11412c"
          "0fb6424888413c8b02")
    block("init", 0x4c, "894140")
    block("init", 0x54, "85c07812c74344030000004883c4205bc3b8010226804883c4205bc3")
    equal("initLength", 112, len(bodies["init"]))

    # Complete current-revision apply path. Older layouts are authenticated
    # but their data mapping is deliberately outside this proof.
    block("apply", 0,
          "488bc4564883ec70488bf14885c90f84580100004885d20f844f010000"
          "48895808488978100f2970e80f2978d88b023d020001010f84a8000000"
          "3d020002010f84960000003d02000301756a"
          "0f10420833ff0f104a180f114424200f1042280f114c24300f11442440"
          "3939763e")
    relative("apply", 0x6d, "f30f1035", int(constants["scale"]["rva"], 16))
    relative("apply", 0x75, "f30f103d", int(constants["base"]["rva"], 16))
    block("apply", 0x7d, "0f1f008b44be0c0f28c7f30f104c8420f30f59ce")
    relative("apply", 0x91, "e8", scalar_rva)
    block("apply", 0x96, "f30f1144be48ffc73b3e72de83ff0c0f83ba00000041b80c000000e997000000")
    block("apply", 0xbb, "0f28742460488bbc2488000000488b9c24800000000f287c24504883c4705ec3")
    block("apply", 0x14d, "442bc78bcf4883c11249c1e00233d2488d0c8e")
    relative("apply", 0x160, "e8", int(small_fill["methodRva"], 16))
    block("apply", 0x165, "33c0e94fffffff")
    equal("applyLength", 375, len(bodies["apply"]))

    # Complete callback, except the independently joined relative call.
    block("process", 0,
          "4883ec384885c9744c4885d274474d85c07442448b4c2460418d41ff3dff000000"
          "77328b4144a801750ab8030226804883c438c3a802740683e0fd8941448b4104"
          "894424288b0189442420")
    call("process", 0x4b, "kernel")
    block("process", 0x50, "4883c438c3b8010226804883c438c3")
    equal("processLength", 95, len(bodies["process"]))
    # Complete leaf kernel: four channel lanes and four frames per iteration.
    # RBP=channel count; RSI=frame count; R11D=stride; R14=state, RDI=input,
    # RBX=output. MULPS is the only sample arithmetic, with no summation.
    block("kernel", 0,
          "48895c240848896c2410488974241848897c242041568b6c243033c0418bf1"
          "498bd8488bfa4c8bf185ed0f84ac000000448b5c24386666660f1f840000000000"
          "410f1064864885f60f848100000041ba02000000418d4afe410fafcb03c8"
          "4c8d0c8d00000000410f101c39418d4aff410fafcb0f59dc03c8"
          "4c8d048d00000000418bca410f101438410fafcb0f59d403c8488d148d00000000"
          "0f100c3a418d4a014183c204410fafcb0f59cc03c80f10048f410f111c19"
          "410f1114180f59c40f110c1a0f11048b418d4afe3bce728583c0043bc5"
          "0f8266ffffff33c0488b5c2410488b6c2418488b742420488b7c2428415ec3")
    equal("kernelLength", 243, len(bodies["kernel"]))
    equal("processingLayout", ([1, 256], 4, 4), tuple(contract["processing"][k]
          for k in ("frameCountRange", "channelGroupWidth", "frameGroupWidth")))

    # Join every control slot to the already proved bulk loader; no duplicate
    # build-specific selector/source catalog is stored here.
    joins = {r["receiverOffset"]: r for r in updates["bulkWordJoins"]["updateJoins"]}
    controls = []
    for index in range(conversion["valueCount"]):
        receiver = 8 + section["sourceOffset"] + conversion["valuesOffset"] + index * 4
        equal("serializedJoin:" + str(index), True, receiver in joins)
        controls.append(dict(valueIndex=index, parameterId=joins[receiver]["parameterId"],
                             serializedOffset=joins[receiver]["serializedOffset"]))
    descriptor = _descriptor_admission(contract["descriptorAdmission"], consumer_contract, read, equal)
    return dict(status="validated", evidenceBoundary="conditional", sectionIndex=2,
                role="mappedChannelGain", controls=controls,
                conversion=dict(lower=-100.0, upper=12.0, nan="lowerBound",
                                specialModeEquality="unorderedTolerant", reservedWordsMustBeZero=True),
                gain=dict(base=10.0, exponentScaleBits=constants["scale"]["wordHex"],
                          usesChannelMapping=True, unusedChannelGainSlotsZeroed=True,
                          wholePowerHelperEquivalent=False),
                sampleArithmetic="float32(input * gain[channel])", frameRange=[1, 256],
                channelsAndFramesRoundedToFour=True, descriptorAdmission=descriptor, bufferBoundsProven=False,
                publicControlNamesProven=False, runtimeInvocationObserved=False,
                meaningBoundary=contract["meaningBoundary"])


def _descriptor_admission(claim, consumer_contract, read, equal):
    """Recognize the full numeric mask dispatcher and its section descriptor."""
    equal("descriptorMethod", "engineInit", claim["consumerMethod"])
    equal("descriptorSectionMethod", "engineInitialize", claim["sectionDescriptorMethod"])
    equal("descriptorBoundary", "direct", claim["evidenceBoundary"])
    equal("descriptorLimits", ([64, 256], 64, 48000, 12, 4), tuple(claim[k] for k in
          ("blockCountRange", "blockCountQuantum", "fixedFrequency", "maximumChannels", "strideQuantum")))
    methods = consumer_contract["methods"]
    row = methods[claim["consumerMethod"]]
    body = read(int(row["rva"], 16), row["bodyLength"])
    equal("descriptorHash", row["bodySha256"], hashlib.sha256(body).hexdigest())
    equal("descriptorLength", 556, len(body))

    def block(offset, encoded):
        raw = bytes.fromhex(encoded)
        equal("descriptorProgram", raw, body[offset:offset + len(raw)], offset)

    # Count, frequency, capacity, logical count, stride and bit-mask retention.
    block(0,
          "4889742418574883ec20498bf9418bf04c8bd14885c90f84000200004885d2"
          "0f84f701000041f7c0feffffff7410b805022680488b7424404883c4205fc3"
          "4885ff7510b800022680488b7424404883c4205fc3"
          "8b0a48895c243048896c24388d41c03dc00000000f87a8010000f6c13f"
          "0f859f01000041890a817a0480bb00000f858f01000041c7420480bb0000"
          "8b420883f80c0f877b010000418942088b420c85c00f846c0100003b4208"
          "0f87630100004189420c8b42103b420c0f8253010000a8030f854b010000"
          "418942100f57c08b42144533db418942144533c08b5a14448bcb8b6a0c"
          "410f114218410f114228410f11423885db0f84df0000006690")
    # Dispatch excludes bit three until the final append. This includes every
    # branch destination, so the case values cannot be attributed by proximity.
    block(0x100,
          "4183f80c0f83c200000041f6c1010f84ac000000418bcb"
          "b801000000d3e083f8080f84990000003d000200007f46743d"
          "83e801743483e801742883e802741c83e80c741083f8100f85c8000000")
    mapping = claim["maskMapping"]
    equal("descriptorMappingBits", [0, 1, 2, 4, 5, 9, 10, 12, 14, 15, 17, 3], [r["maskBit"] for r in mapping])
    equal("descriptorMappingValues", list(range(12)), sorted(r["valueIndex"] for r in mapping))
    # The switch topology above selects these complete mov/xor-and-jump cases.
    cases = [(5, 0x14d, "eb64"), (4, 0x154, "eb5d"), (2, 0x15b, "eb56"),
             (1, 0x162, "eb4f"), (0, 0x169, "eb4b"), (9, 0x16d, "eb44"),
             (17, 0x197, "eb1a"), (15, 0x19e, "eb13"), (14, 0x1a5, "eb0c"),
             (12, 0x1ac, "eb05"), (10, 0x1b3, "")]
    by_bit = {r["maskBit"]: r for r in mapping}
    for bit, offset, branch in cases:
        value = by_bit[bit]
        equal("descriptorCaseOffset", offset, value["caseBodyOffset"], offset)
        instruction = "33c9" if bit == 0 else "b9" + struct.pack("<I", value["valueIndex"]).hex()
        if bit == 0:
            equal("descriptorZeroCase", 0, value["valueIndex"], offset)
        block(offset, instruction + branch)
    block(0x174, "3d0004000074383d00100000742a3d00400000741c3d00800000740e3d00000200757e")
    block(0x1b8, "43894c821841ffc041ffc341d1e90f8534fffffff6c308740c")
    equal("descriptorDeferredOffset", 0x1d1, by_bit[3]["caseBodyOffset"], 0x1d1)
    block(0x1d1, "43c7448218" + struct.pack("<I", by_bit[3]["valueIndex"]).hex()
          + "41ffc0443bc575330fb642184c8bc78bd641884250498bca")
    at = 0x1f2
    equal("descriptorInitializeOpcode", b"\xe8", body[at:at + 1], at)
    target = int(row["rva"], 16) + at + 5 + struct.unpack_from("<i", body, at + 1)[0]
    equal("descriptorInitializeTarget", int(methods[claim["sectionDescriptorMethod"]]["rva"], 16), target, at)
    block(0x1f7,
          "f7d81bc02505008080488b5c2430488b6c2438488b7424404883c4205fc3"
          "b802022680ebe4488b742440b8010226804883c4205fc3")
    # The initialized engine reorders its scalar fields into the descriptor
    # passed to each section. Its logical count, not capacity, is copied to +8.
    init = methods[claim["sectionDescriptorMethod"]]
    init_body = read(int(init["rva"], 16), init["bodyLength"])
    equal("descriptorSectionHash", init["bodySha256"], hashlib.sha256(init_body).hexdigest())
    raw = bytes.fromhex("8b010f104118894424248b41040f104928894424208b4108"
                        "8944242c8b410c894424288b4110894424308b4114")
    equal("descriptorSectionCopy", raw, init_body[0x2d:0x2d + len(raw)], 0x2d)
    raw = bytes.fromhex("89442434")
    equal("descriptorSectionMaskCopy", raw, init_body[0x66:0x6a], 0x66)
    raw = bytes.fromhex("488d542420ffd0")
    equal("descriptorSectionCall", raw, init_body[0x16f:0x16f + len(raw)], 0x16f)
    return dict(evidenceBoundary="direct", logicalChannels=[1, 12], strideMultiple=4,
                strideAtLeastRoundedChannels=True, channelMappingIndicesInRange=True,
                maskMapping=[dict(maskBit=r["maskBit"], valueIndex=r["valueIndex"]) for r in mapping],
                maskTraversal="ascendingExceptDeferredBitThree", callerBufferBoundsProven=False)


def check_mastering_gain_native_inputs(game_root: Path):
    from scripts.webui.audio.semantics.wwise_effect_native import check_effect_native_extension
    from scripts.webui.audio.semantics.wwise_effect_scalar import load_scalar_contract, validate_scalar_correspondence
    from scripts.webui.audio.semantics.wwise_effect_small_fill import load_small_fill_contract, validate_small_fill
    from scripts.webui.audio.semantics.wwise_mastering_consumer import load_mastering_consumer_contract, validate_mastering_consumer
    from scripts.webui.audio.semantics.wwise_mastering_updates import load_mastering_contract, validate_mastering_updates

    def validate(parent, base, read):
        consumer_contract = load_mastering_consumer_contract()
        class_id = consumer_contract["classId"]
        updates = validate_mastering_updates(load_mastering_contract(), parent["nativeInputs"],
                                             parent["registrationWitnesses"][class_id], base, read,
                                             structural=parent["structuralSchemas"][class_id])
        consumer = validate_mastering_consumer(consumer_contract, parent, updates, base, read)
        scalar = validate_scalar_correspondence(load_scalar_contract(), parent["nativeInputs"], read)
        small_fill = validate_small_fill(load_small_fill_contract(), parent["nativeInputs"], read)
        parent_identity = dict(nativeInputs=parent["nativeInputs"], classId=class_id)
        return validate_mastering_gain(load_mastering_gain_contract(), parent_identity, updates, consumer,
                                       consumer_contract, scalar, small_fill, read)

    return check_effect_native_extension(game_root, evidence_key="gain", validate=validate)
