"""Authenticate Mastering's series of native second-order IIR filters."""
from __future__ import annotations

import hashlib
import json
import struct
from functools import lru_cache
from pathlib import Path

from scripts.game_data.contracts import CONTRACTS_DIR
from scripts.webui.audio.semantics.wwise_effect_updates import EffectUpdateError


@lru_cache(maxsize=1)
def load_mastering_filter_contract():
    return json.loads((CONTRACTS_DIR / "wwise_mastering_filter_native.json").read_text(encoding="utf-8"))


def validate_mastering_filter(contract, native_inputs, consumer, small_fill, read):
    def equal(check, expected, actual, offset=0):
        if expected != actual:
            raise EffectUpdateError("masteringFilter", check, offset, expected, actual)

    equal("schema", "endfield.wwise-mastering-filter-native-contract.v2", contract["schema"])
    equal("reviewStatus", "reviewed", contract["status"])
    equal("inputs", native_inputs, contract["nativeInputs"])
    equal("consumerProof", "validated", consumer["status"])
    equal("fillProof", "validated", small_fill["status"])
    equal("fillRange", [0, 144], small_fill["lengthRange"])
    equal("fillMeaning", True, small_fill["byteFill"])
    equal("paddingClaim", ([4, 12], 144, "inputAfterLogicalFrames", True), tuple(contract["padding"][k]
          for k in ("strideRange", "maximumBytes", "destination", "historyTraversesPaddedFrames")))
    equal("boundary", "conditional", contract["evidenceBoundary"])
    equal("section", 0, contract["sectionIndex"])
    methods = contract["methods"]
    equal("methodSet", {"process", "entry", "kernel"}, set(methods))
    bodies = {}
    for name, row in methods.items():
        size = row["bodyLength"]
        equal("methodExtent:" + name, True, type(size) is int and 0 < size <= 4096)
        body = read(int(row["rva"], 16), size)
        equal("methodLength:" + name, size, len(body))
        equal("methodHash:" + name, row["bodySha256"], hashlib.sha256(body).hexdigest())
        bodies[name] = body

    def block(name, offset, encoded):
        raw = bytes.fromhex(encoded)
        equal("program:" + name, raw, bodies[name][offset:offset + len(raw)], offset)

    def relative(name, at, prefix_hex, target):
        prefix = bytes.fromhex(prefix_hex); raw = bodies[name][at:at + len(prefix) + 4]
        equal("relativeOpcode:" + name, prefix, raw[:len(prefix)], at)
        equal("relativeExtent:" + name, len(prefix) + 4, len(raw), at)
        destination = int(methods[name]["rva"], 16) + at + len(raw) + struct.unpack_from("<i", raw, len(prefix))[0]
        equal("relativeTarget:" + name, target, destination, at)

    pointers = consumer["callbackBinding"]["callbackPointers"][0]["pointersByRecordOffset"]
    equal("callbackJoin", int(methods["process"]["rva"], 16), pointers.get(32, pointers.get("32")))
    layout = contract["layout"]
    equal("layout", (72, 76, 216, [12, 16, 20], [4, 8], [24, 72], [120, 168], 12),
          tuple(layout[k] for k in ("sectionFilterCountOffset", "filterRecordOffset", "filterRecordStride",
              "forwardCoefficientOffsets", "feedbackCoefficientOffsets", "inputHistoryOffsets", "outputHistoryOffsets", "historyCapacity")))
    equal("groups", (4, 4, True, True), tuple(contract["processing"][k] for k in
          ("channelGroupWidth", "frameGroupWidth", "coefficientZeroOffsetUnusedByKernel", "identitySkipUsesUnorderedTolerantComparison")))
    unity = contract["unityConstant"]
    equal("unityValue", struct.pack("<f", 1.0), read(int(unity["rva"], 16), 4))
    equal("unityRecorded", "0000803f", unity["wordHex"])

    # Section count, identity comparison, complete coefficient/state address,
    # call arguments and series backedge. UCOMISS/JNE accepts unordered pairs.
    block("process", 0x64, "8b4948f6c1018b4344")
    block("process", 0x4d, "448bbc24d0000000418d47ff3dff0000000f87ae010000")
    block("process", 0xb5, "a802740683e0fd894344")
    block("process", 0xc7, "458be185c90f84060100000f297424600f57f60f297c2450")
    relative("process", 0xdf, "f30f103d", int(unity["rva"], 16))
    block("process", 0xe7,
          "660f1f8400000000004963c44869c8d80000000f2e7c1958752c"
          "0f2e74195c75250f2e741960751e0f2e7c194c75170f2e74195075100f2e7419547509"
          "488d7b04e980000000")
    block("process", 0x150,
          "4d8b4a10488d7b04418bc44d8bc64869c8d80000008b07488bd64883c14c"
          "44897c2430894424284803cb8b0389442420")
    relative("process", 0x180, "e8", int(methods["entry"]["rva"], 16))
    block("process", 0x1a5, "483bf27503498bf541ffc4443b63480f8236ffffff")
    # Complete checked tail entry. Its jump leaves all Win64 arguments intact.
    block("entry", 0, "4885c9740e4885d274094d85c0")
    relative("entry", 0xd, "0f85", int(methods["kernel"]["rva"], 16))
    block("entry", 0x13, "b801022680c3")
    equal("entryLength", 25, len(bodies["entry"]))

    # Complete kernel grammar split only at the independently proved fill call.
    # Coefficients are broadcast; history vectors cover four channels. Four
    # consecutive samples update the two-input/two-output recurrence in order.
    block("kernel", 0,
          "4c89442418488954241053555657415541564881ecc80000008bac2430010000"
          "498bc08bb42428010000448bf5440f295c24604c8bca440f29642450488bf9"
          "440f296c2440440f29742430440f297c24204183e60374388bc6bb04000000"
          "448bc30fafc5452bc6440fafc641c1e002488d0c8233d2")
    relative("kernel", 0x75, "e8", int(small_fill["methodRva"], 16))
    block("kernel", 0x7a,
          "4c8b8c2408010000412bde488b84241001000003ebf3440f105f0c33d2"
          "f3440f106710f3440f106f14f3440f107704f3440f107f08448bac2420010000"
          "450fc6db00450fc6e400450fc6ed00450fc6f600450fc6ff004585ed0f84e8010000"
          "4c89a424000100004c89bc24c00000000f29b424b00000000f29bc24a0000000"
          "440f29842490000000440f298c2480000000440f29542470"
          "4d8d04914c8d3c90440f104c9718440f105497480f107c9778440f108497a8000000"
          "85ed0f84280100008d1cb5000000004d8bf7448d65ff48c1e3024d2bf0"
          "41c1ec0241ffc4448d1436448d1c7690"
          "410f10084b8d0406410f101cb0430f102c90450f59c70f28f1410f59f3"
          "410f28c1410f59c40f28d3410f59d3450f59d50f58f0450f59cd0f28c7"
          "410f59ff410f59c6410f58f2440f28d50f58f00f28c1410f59c4410f59cd"
          "410f58f0440f28c50f58d0450f59c30f28c6410f59c6410f58d1470f100c98"
          "0f58d00f28c3410f59c4410f59dd0f58d7430f103c984c03c3440f58c0"
          "410f59fb0f1130440f58c10f28c2410f59c60f28ce410f59cf410f1114b7"
          "4c03fb440f58c00f28c5410f59c4440f58c10f28ca410f59cf0f58f8"
          "410f28c0410f59c60f58fb460f1104900f58f80f58f9420f113c98"
          "4983ec010f850dffffff4c8b8c2408010000488b842410010000"
          "440f114c9718440f115497480f117c9778440f118497a800000083c204"
          "413bd50f8288feffff440f28542470440f288c2480000000440f28842490000000"
          "0f28bc24a00000000f28b424b00000004c8bbc24c00000004c8ba42400010000"
          "440f285c246033c0440f28642450440f286c2440440f28742430440f287c2420"
          "4881c4c8000000415e415d5f5e5d5bc3")
    equal("kernelLength", 753, len(bodies["kernel"]))
    return dict(status="validated", evidenceBoundary="conditional", sectionIndex=0,
                role="seriesSecondOrderIirFilters", layout=layout,
                arithmetic="five float32 products summed left to right, without fused multiply-add",
                feedbackCoefficientsUsedWithStoredSigns=True,
                historiesPersistPerChannel=True, coefficientZeroOffsetUnusedByKernel=True,
                identitySkipUnorderedTolerant=True, channelWidthRoundedToFour=True,
                arithmeticCondition="admitted state, frames one through 256 and stride at most twelve",
                nonmultipleFramePaddingHelperProven=True, inputTrailingFramesZeroed=True,
                historiesAdvanceThroughRoundedFrames=True, coefficientGenerationProven=False,
                publicControlNamesProven=False, runtimeInvocationObserved=False,
                meaningBoundary=contract["meaningBoundary"])


def check_mastering_filter_native_inputs(game_root: Path):
    from scripts.webui.audio.semantics.wwise_effect_native import check_effect_native_extension
    from scripts.webui.audio.semantics.wwise_effect_small_fill import load_small_fill_contract, validate_small_fill
    from scripts.webui.audio.semantics.wwise_mastering_consumer import load_mastering_consumer_contract, validate_mastering_consumer
    from scripts.webui.audio.semantics.wwise_mastering_updates import load_mastering_contract, validate_mastering_updates

    def validate(parent, base, read):
        c = load_mastering_consumer_contract(); class_id = c["classId"]
        updates = validate_mastering_updates(load_mastering_contract(), parent["nativeInputs"],
                                             parent["registrationWitnesses"][class_id], base, read,
                                             structural=parent["structuralSchemas"][class_id])
        consumer = validate_mastering_consumer(c, parent, updates, base, read)
        small_fill = validate_small_fill(load_small_fill_contract(), parent["nativeInputs"], read)
        contract = load_mastering_filter_contract()
        if contract["classId"] != class_id:
            raise EffectUpdateError("masteringFilter", "classJoin", 0, class_id, contract["classId"])
        return validate_mastering_filter(contract, parent["nativeInputs"], consumer, small_fill, read)

    return check_effect_native_extension(game_root, evidence_key="filter", validate=validate)
