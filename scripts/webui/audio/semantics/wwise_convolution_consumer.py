"""Selected Convolution parameter-copy and media-admission consumer facts.

The registered effect factory installs the reviewed vtable. Its initialization
callback retains the parameter object and copies a contiguous parameter state;
the processing callback calls a preparation routine which repeats that copy.
This closes a conditional native consumer route, not observed playback.

Initialization asks the retained context for media index zero, checks for a
non-null buffer, compares one media-header word with the incoming format word,
then selects between two implementations using a stored 16-bit discriminator.
Both child initializers copy the same header before the size guard, retain the
following prefix, and derive planar pointers from a padded prefix and a stored
stride count. Their payload element strides differ. This is a partial anonymous
layout: neither initializer proves complete payload bounds or sample encoding.
For the second variant, one conditional processing route joins the media
pointer table to the default kernel. That kernel expands packed words by
shifting/masking their float32 bits before SIMD multiplication. This establishes
upper-half float32 storage on that route, not all alternative kernels or a
complete impulse-response decoder.
Two words copied from the bank parameter block are subsequently read as float32.
The instruction witnesses preserve the scale/multiply/truncate sequence without
assigning public control names, milliseconds, buffer bounds or DSP meaning.
"""
from __future__ import annotations

import hashlib
import json
import struct
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from scripts.game_data.contracts import CONTRACTS_DIR
from scripts.webui.audio.semantics.wwise_effect_updates import EffectUpdateError


@lru_cache(maxsize=1)
def load_convolution_consumer_contract():
    return json.loads((CONTRACTS_DIR / "wwise_convolution_consumer_native.json").read_text(encoding="utf-8"))


def validate_convolution_consumer(contract, parent, image_base: int, read: Callable[[int, int], bytes]):
    def equal(check, role, expected, actual):
        if expected != actual:
            raise EffectUpdateError("convolutionConsumer", f"{check}:{role}", 0, expected, actual)

    equal("schema", "contract", "endfield.wwise-convolution-consumer-native.v3", contract["schema"])
    equal("status", "contract", "reviewedCurrentBuild", contract["status"])
    equal("inputs", "contract", parent["nativeInputs"], contract["nativeInputs"])
    equal("boundary", "contract", "direct", contract["evidenceBoundary"])
    registration = parent["registrationWitnesses"][contract["classId"]]
    methods = contract["methods"]
    bodies = {}
    for name, row in methods.items():
        raw = read(int(row["rva"], 16), row["bodyLength"])
        equal("methodLength", name, row["bodyLength"], len(raw))
        equal("methodHash", name, row["bodySha256"], hashlib.sha256(raw).hexdigest())
        bodies[name] = raw
    equal("factory", "registration", registration["factoryRva"], methods["factory"]["rva"])
    witnesses = contract["witnesses"]

    def witness(role, expected=None):
        row = witnesses[role]
        raw = bytes.fromhex(row["instructionHex"])
        at = row["bodyOffset"]
        equal("instruction", role, raw, bodies[row["method"]][at:at + len(raw)])
        if expected is not None:
            equal("operation", role, bytes.fromhex(expected), raw)
        return row, raw

    # Read every witness, including branch destinations and data constants.
    for role in witnesses:
        witness(role)
    u32 = lambda value: struct.pack("<I", value).hex()
    u8 = lambda value: bytes([value]).hex()
    layout = contract["layout"]
    parameter = layout["parameterPointer"]
    state = layout["currentState"]
    context = layout["contextPointer"]
    witness("factoryVtableStore", "488908")
    lea, raw = witness("factoryVtableLea")
    equal("vtableOpcode", "factory", b"\x48\x8d\x0d", raw[:3])
    vtable = int(methods["factory"]["rva"], 16) + lea["bodyOffset"] + 7 + struct.unpack_from("<i", raw, 3)[0]
    equal("vtable", "factory", int(contract["effectVtableRva"], 16), vtable)
    for role, slot in contract["callbackSlots"].items():
        equal("callbackSlot", role, image_base + int(methods[role]["rva"], 16),
              struct.unpack("<Q", read(vtable + slot, 8))[0])

    source = layout["parameterCopySource"]
    copied = ("0f1041" + u8(source) + "0f11020f1049" + u8(source + 16)
              + "0f114a100f1041" + u8(source + 32) + "0f114220f20f1049" + u8(source + 48)
              + "f20f114a308b41" + u8(source + 56) + "894238c3")
    equal("copyLeaf", "parameterState", bytes.fromhex(copied), bodies["copy"])
    equal("copyExtent", "parameterState", 60, layout["parameterCopyBytes"])
    witness("initRetainAllocator", "488991" + u32(layout["allocatorPointer"]) + "4c8bfa")
    witness("initCopyArguments", "488d51" + u8(state) + "4c8989" + u32(parameter)
            + "488bf14c8941" + u8(context) + "498bc94d8bf0")
    witness("prepareCopyArguments", "488d79" + u8(state) + "488bd9488b89" + u32(parameter) + "488bd7")
    for role, target in (("initCopyCall", "copy"), ("prepareCopyCall", "copy"), ("executePrepareCall", "prepare")):
        row, raw = witness(role)
        equal("callOpcode", role, b"\xe8", raw[:1])
        equal("callTarget", role, int(methods[target]["rva"], 16),
              int(methods[row["method"]]["rva"], 16) + row["bodyOffset"] + 5 + struct.unpack_from("<i", raw, 1)[0])
    witness("executeReceiver", "488b41" + u8(layout["processingPointer"]) + "488bfa488bf14885c0")
    media = contract["mediaAdmission"]
    witness("initFormatPointer", "4c8ba424" + u32(media["formatArgumentStackOffset"]))
    witness("mediaSizeOutput", "4c8d8c24" + u32(media["sizeOutputStackOffset"]))
    witness("mediaPointerOutput", "4c8d4424" + u8(media["pointerOutputStackOffset"]))
    witness("mediaContextAndIndex", "488b4e" + u8(context) + "33d2")
    equal("mediaIndex", "request", 0, media["requestedIndex"])
    witness("mediaOutputZeros", "48894424" + u8(media["pointerOutputStackOffset"])
            + "898424" + u32(media["sizeOutputStackOffset"]))
    witness("mediaOutputZeroSource", "33c0")
    witness("mediaContextCall", "488b01ff50" + u8(media["contextSlot"]))
    witness("mediaResult", "4c8b6c24" + u8(media["pointerOutputStackOffset"])
            + "498bce4d8b0e4d85ed")
    witness("formatWordStore", "418b04248986" + u32(layout["formatWord"]))
    witness("mediaFormatComparison", "418b0424413945" + u8(media["headerComparisonOffset"]))
    witness("mediaDiscriminator", "410fb745" + u8(media["discriminatorOffset"]) + "0f44df6685c0")
    witness("mediaSecondDiscriminator", "6683f8" + u8(media["acceptedDiscriminators"][1]))
    equal("firstDiscriminator", "zeroTest", 0, media["acceptedDiscriminators"][0])
    for row in contract["branches"]:
        w, raw = witness(row["role"])
        equal("branchOpcode", row["role"], bytes.fromhex(row["opcodeHex"]), raw[:-1])
        equal("branchTarget", row["role"], row["targetBodyOffset"],
              w["bodyOffset"] + len(raw) + int.from_bytes(raw[-1:], "little", signed=True))
    numeric = contract["numericConsumer"]
    witness("firstStoredWordAsFloat", "f30f104e" + u8(state))
    witness("secondStoredWordAsFloat", "f30f104e" + u8(state + 4) + "f30f584e" + u8(state))
    for role in ("firstScale", "sumScale"):
        w, raw = witness(role)
        equal("scaleOpcode", role, b"\xf3\x0f\x59\x0d", raw[:4])
        rva = int(methods[w["method"]]["rva"], 16) + w["bodyOffset"] + 8 + struct.unpack_from("<i", raw, 4)[0]
        equal("scaleAddress", role, int(numeric["scaleRva"], 16), rva)
    scale = read(int(numeric["scaleRva"], 16), 4)
    equal("scaleBits", "constant", numeric["scaleHex"], scale.hex())
    witness("firstFormatToFloat", "f3480f2ac0")
    witness("firstMultiplyTruncate", "f30f59c8f3480f2cc189442470")
    witness("sumFormatToFloatAndTruncate", "f3480f2ac0f30f59c8f3480f2cc1")
    # Bind the numerical field reads to the prior exact bulk-loader source join.
    update = parent["parameterUpdates"][contract["classId"]]
    joins = {r["parameterId"]: r for r in update["cases"]}
    for ident, serialized in ((0, 0), (1, 4)):
        equal("storedSource", str(ident), serialized, joins[ident]["serializedOffset"])
        equal("copiedDestination", str(ident), state + serialized,
              state + joins[ident]["receiverOffset"] - source)
    witness("childStore", "48894e" + u8(layout["processingPointer"]) + "4885c9")
    witness("childInitArguments", "488b01498bd7448b8c24" + u32(media["sizeOutputStackOffset"])
            + "4c8b4424" + u8(media["pointerOutputStackOffset"]) + "895c2420")
    witness("childInitCall", "ff5008")
    child = contract["childMedia"]
    equal("childVariants", "set", media["acceptedDiscriminators"],
          [row["discriminator"] for row in child["variants"]])
    for variant in child["variants"]:
        role = str(variant["discriminator"])
        ctor = bodies[variant["constructor"]]
        ctor_rva = int(methods[variant["constructor"]]["rva"], 16)
        equal("childConstructor", role, b"\x48\x8d\x05", ctor[:3])
        equal("childVtableStore", role, bytes.fromhex("48890133c0"), ctor[7:12])
        equal("childConstructorReturn", role, bytes.fromhex("488bc1c3"), ctor[-4:])
        table = ctor_rva + 7 + struct.unpack_from("<i", ctor, 3)[0]
        equal("childVtable", role, int(variant["vtableRva"], 16), table)
        equal("childInitSlot", role, image_base + int(methods[variant["initializer"]]["rva"], 16),
              struct.unpack("<Q", read(table + 8, 8))[0])
        at = variant["constructorCallBodyOffset"]
        equal("childConstructorCall", role, bytes.fromhex("488bc8e8"), bodies["init"][at - 3:at + 1])
        equal("childConstructorTarget", role, ctor_rva,
              int(methods["init"]["rva"], 16) + at + 5 + struct.unpack_from("<i", bodies["init"], at + 1)[0])
        allocation = variant["allocationBodyOffset"]
        equal("childAllocation", role, bytes.fromhex("ba" + u32(variant["allocationBytes"]) + "498bcfff50084885c0"),
              bodies["init"][allocation:allocation + 14])
        branch_role = "zeroDiscriminatorBranch" if variant["discriminator"] == 0 else "secondDiscriminatorBranch"
        target = next(row["targetBodyOffset"] for row in contract["branches"] if row["role"] == branch_role)
        equal("childSelection", role, variant["selectionTargetBodyOffset"], target)
        equal("childAllocationPath", role, 16, allocation - target)
        # The bounded prefix recognizer names only reads and pointer arithmetic.
        raw = bodies[variant["initializer"]]
        def chunk(at, encoded):
            expected = bytes.fromhex(encoded)
            equal("childHeaderOperation", f"{role}+{at}", expected, raw[at:at + len(expected)])
        dest = child["headerDestinationOffset"]
        chunk(0x1a, "410f2800488bf2488bd90f1141" + u8(dest)
              + "410f2848100f1149" + u8(dest + 16) + "410f2840200f1141" + u8(dest + 32))
        equal("childHeaderBytes", role, 48, child["headerBytes"])
        chunk(0x3a, "4183f9" + u8(child["headerBytes"]) + "0f86")
        chunk(0x44, "8b69" + u8(dest + child["prefixCountHeaderOffset"]) + "85ed0f84")
        for at in (0x3e, 0x49):
            equal("childInvalidBranch", f"{role}+{at}", variant["invalidBodyOffset"],
                  at + 6 + struct.unpack_from("<i", raw, at + 2)[0])
        chunk(variant["invalidBodyOffset"], "b8" + u32(child["invalidReturnCode"]))
        chunk(0x4f, "8b41" + u8(dest + child["pointerCountHeaderOffset"])
              + "4d8d70" + u8(child["headerBytes"]) + "0fb6c0")
        equal("childCountMask", role, 255, child["pointerCountMask"])
        chunk(0x60, "8bd04c8971" + u8(variant["prefixPointerOffset"]) + "8bf848c1e203")
        chunk(0x7b, "488943" + u8(child["pointerTableOffset"]) + "4885c0")
        equal("childPrefixElement", role, 2, child["prefixElementBytes"])
        equal("childPrefixAlignment", role, 16, child["prefixAlignment"])
        chunk(0x88, "488d0c6d0f0000004883e1f04903ce48890883ff017634")
        stride_sib = {4: "88", 8: "c8"}.get(variant["payloadElementStride"])
        equal("childStride", role, True, stride_sib is not None)
        chunk(0x9f, "41b808000000448d57ff4533c90f1f4000488b53" + u8(child["pointerTableOffset"])
              + "4d8d40088b4b" + u8(dest + child["payloadStrideCountHeaderOffset"])
              + "4d8d4908498b4411f8488d0c" + stride_sib + "49894c10f84983ea0175dd")
    packed = contract["packedKernel"]
    equal("packedBoundary", "kernel", "conditional", packed["evidenceBoundary"])
    equal("packedDiscriminator", "kernel", True, packed["discriminator"] in media["acceptedDiscriminators"])
    variant = next(row for row in child["variants"] if row["discriminator"] == packed["discriminator"])
    equal("packedInputStride", "media", 4, variant["payloadElementStride"])
    equal("packedExecuteSlot", "child", image_base + int(methods[packed["executeMethod"]]["rva"], 16),
          struct.unpack("<Q", read(int(variant["vtableRva"], 16) + packed["executeVtableSlot"], 8))[0])
    witness("parentChildExecute", "488b4e" + u8(layout["processingPointer"])
            + "458bcdf30f10464c458bc6498bd7488b014c8b50" + u8(packed["executeVtableSlot"])
            + "488b86c00000004889442428f30f1144242041ffd2")
    row, raw = witness("kernelDefaultLea")
    equal("packedDefaultOpcode", "kernel", bytes.fromhex("488d05"), raw[:3])
    equal("packedDefaultTarget", "kernel", int(methods[packed["kernelMethod"]]["rva"], 16),
          int(methods[row["method"]]["rva"], 16) + row["bodyOffset"] + 7 + struct.unpack_from("<i", raw, 3)[0])
    witness("kernelDefaultStore", "488983" + u32(packed["kernelPointerOffset"]))
    witness("kernelReceiver", "488bf9")
    witness("kernelMediaPointer", "488b47" + u8(child["pointerTableOffset"])
            + "448b6f6c4c8b7f" + u8(variant["prefixPointerOffset"]) + "4c8b34c8")
    witness("kernelCallArguments", "450fb70f4d8bc6488b87" + u32(packed["kernelPointerOffset"])
            + "453bcc488b542440488bcd450f43ccffd0")
    witness("kernelSourceRegister", "498bf80f2978d8482bfa")
    witness("kernelSourceRebase", "488d1c17")
    row, raw = witness("kernelMaskRead")
    equal("packedMaskOpcode", "kernel", bytes.fromhex("66440f6f2d"), raw[:5])
    equal("packedMaskTarget", "kernel", int(packed["maskRva"], 16),
          int(methods[row["method"]]["rva"], 16) + row["bodyOffset"] + 9 + struct.unpack_from("<i", raw, 5)[0])
    mask = read(int(packed["maskRva"], 16), 16)
    equal("packedMaskBytes", "kernel", packed["maskHex"], mask.hex())
    equal("packedMaskValue", "kernel", struct.pack("<4I", *([0xffff0000] * 4)), mask)
    witness("kernelExpansion", "f30f6f2c83f30f6f7c831066440f6fd5410f54ed66410f72f210"
            + "66440f6fc766410f72f010410f28da440f59d4410f28d0440f59c60f28cd0f59cc"
            + "410f54fd410f59d9410f59d3410f59e9")
    return {
        "status": "validated", "evidenceBoundary": "direct", "parameterCopyBytes": layout["parameterCopyBytes"],
        "copyIncludesUnnamedPadding": True, "refreshAtPreparation": True,
        "mediaRequestIndex": media["requestedIndex"], "mediaHeaderComparedOffset": media["headerComparisonOffset"],
        "mediaDiscriminatorOffset": media["discriminatorOffset"], "acceptedDiscriminators": media["acceptedDiscriminators"],
        "floatReadSerializedOffsets": [0, 4], "floatScale": struct.unpack("<f", scale)[0],
        "runtimeInvocationObserved": False, "meaningBoundary": contract["meaningBoundary"],
        "childMedia": {**child, "headerCopiedBeforeSizeGuard": True,
                       "nativeMinimumSizeExclusive": child["headerBytes"],
                       "completePayloadBoundsProven": False, "sampleEncodingProven": False},
        "conditionalPackedKernel": packed,
    }


def check_convolution_consumer_native_inputs(game_root: Path):
    from scripts.webui.audio.semantics.wwise_effect_native import check_effect_native_extension
    return check_effect_native_extension(game_root, evidence_key="consumer", validate=lambda parent, base, read:
                                        validate_convolution_consumer(load_convolution_consumer_contract(), parent, base, read))
