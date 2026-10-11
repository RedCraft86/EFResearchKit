"""Authenticate Mastering's later context-indexed polynomial sample transition.

This routine is separate from the local four-section engine. Its history capture,
timer arithmetic and opaque stream-identity comparisons do not prove the context
producer, a public control meaning, allocation lifetime or live activation.
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
def load_mastering_shared_contract():
    return json.loads((CONTRACTS_DIR / "wwise_mastering_shared_native.json").read_text(encoding="utf-8"))


def validate_mastering_shared(contract, native_inputs, consumer_contract, consumer, read):
    def equal(check, expected, actual, offset=0):
        if expected != actual:
            raise EffectUpdateError("masteringShared", check, offset, expected, actual)

    equal("schema", "endfield.wwise-mastering-shared-native-contract.v1", contract["schema"])
    equal("reviewStatus", "reviewed", contract["status"])
    equal("inputs", native_inputs, contract["nativeInputs"])
    equal("consumerInputs", native_inputs, consumer_contract["nativeInputs"])
    equal("consumerProof", "validated", consumer["status"])
    equal("boundary", "conditional", contract["evidenceBoundary"])
    method = contract["method"]; layout = contract["layout"]; data = contract["data"]
    equal("routineJoin", int(consumer["contextRoutine"]["rva"], 16), int(method["rva"], 16))
    equal("recordStrideJoin", consumer["contextRoutine"]["recordStrideBytes"], layout["recordStrideBytes"])
    size = method["bodyLength"]
    equal("extent", True, type(size) is int and 0 < size <= 16384)
    body = read(int(method["rva"], 16), size)
    equal("length", size, len(body)); equal("hash", method["bodySha256"], hashlib.sha256(body).hexdigest())
    # Independent mathematical coefficients; addresses live only in the contract.
    coefficients = [-11.209857940673828, 37.939247131347656, -50.80830001831055, 34.48499298095703,
                    -12.930046081542969, 3.4470739364624023, 0.07175690680742264]
    roles = ["Leading", "Second", "Third", "Fourth", "Fifth", "Sixth", "Constant"]
    expected_data = {}
    for role, value in zip(roles, coefficients):
        raw = struct.pack("<f", abs(value))
        expected_data["polynomial" + role + "Scalar"] = raw
        expected_data["polynomial" + role + "Vector"] = raw * 4
    expected_data.update(laneOffsets=struct.pack("<4I", 0, 1, 2, 3), scalarUnity=struct.pack("<f", 1.),
                         vectorUnity=struct.pack("<4f", 1., 1., 1., 1.), unsignedLowByteMask=struct.pack("<4I", *([255] * 4)),
                         unsignedHighByteScale=struct.pack("<4f", *([256.] * 4)))
    equal("dataSet", set(expected_data), set(data))
    for name, raw in expected_data.items():
        row = data[name]
        equal("dataExtent:" + name, len(raw), row["byteLength"])
        equal("dataDeclaration:" + name, raw.hex(), row["bytesHex"])
        equal("dataValue:" + name, raw, read(int(row["rva"], 16), len(raw)))
    cursor = 0
    for step in method["program"]:
        equal("coverage", cursor, step["offset"], cursor)
        if "bytesHex" in step:
            raw = bytes.fromhex(step["bytesHex"])
            equal("nonempty", True, bool(raw), cursor); equal("program", raw, body[cursor:cursor + len(raw)], cursor)
            cursor += len(raw)
            continue
        prefix = bytes.fromhex(step["prefixHex"]); suffix = bytes.fromhex(step["suffixHex"])
        end = cursor + len(prefix) + 4 + len(suffix); raw = body[cursor:end]
        equal("relativeLength", end - cursor, len(raw), cursor)
        equal("relativeOpcode", prefix, raw[:len(prefix)], cursor)
        equal("relativeSuffix", suffix, raw[len(prefix) + 4:], cursor)
        actual = int(method["rva"], 16) + end + struct.unpack_from("<i", raw, len(prefix))[0]
        equal("relativeDataJoin", int(data[step["target"]]["rva"], 16), actual, cursor); cursor = end
    equal("programEnd", size, cursor, cursor)

    def block(offset, encoded):
        raw = bytes.fromhex(encoded)
        equal("arithmetic", raw, body[offset:offset + len(raw)], offset)

    block(0x1c, "8b72084c8d513c4d8be1400fb6f6458b0a4d8bf8488bfa4c8bd94585c90f847b2a0000")
    block(0xc2, "0fb74210443bc8")
    block(0x10c, "488b07450f28fe0fb77712490fafcc450fc6ff00")
    block(0x132, "418b4338450f28ec0f57c0f3480f2ac0f3440f5ee8")
    block(0x154, "413bf10f8325070000")
    block(0x7c7, "418b02412bc041ffc0f3410f59c7f30f5cd80f57c0f3480f2ac0f3410f59c5f30f59d8f30f5ccb")
    block(0x7ee, "0f28c1f30f59c5f30f5cd00f28c3f30f59c5f30f59d1f30f5cd7f30f59d1f3410f58d0f30f59d1")
    block(0x833, "f30f59cbf30f5911f30f5ccff30f59cbf3410f58c8f30f59cbf3410f5cc9f30f59cbf3410f58caf30f59cbf3410f58cbf3410f59cef30f58d1f30f1111")
    block(0x1ca1, "413b5340899c2430010000410f43534089142485d2")
    block(0x1ce0, "4d8b00498b7b508bc84c3904cf740bffc03bc272f2")
    block(0x2a5b, "45290a")
    block(0x2b99, "480fafca4803c8488b078b4c88fc41890c93")
    block(0x2c19, "418b3424448bd3413b736041895b40410f437360")
    block(0x2c59, "4183790c11743c6641837912007434")
    block(0x2c75, "488b04d8488b00488904d1")
    block(0x2c90, "428b4480fc89049141ff4340")
    expected_layout = (104, 0, 12, 48, 2, 56, 60, 64, 80, 88, 96, 0, 8, 255, 12, 16, 18, 0, 8, 16, 1, 17, 1004, 1005)
    layout_keys = ("recordStrideBytes", "primaryHistoryOffset", "primaryChannelLimit", "auxiliaryHistoryOffset", "auxiliaryChannelLimit",
                   "durationOffset", "remainingOffset", "capturedCountOffset", "capturedIdPointerOffset", "capturedValuePointerOffset",
                   "capturedCapacityOffset", "bufferDataPointerOffset", "bufferChannelWordOffset", "bufferChannelMask", "bufferStatusOffset",
                   "bufferMaximumFramesOffset", "bufferValidFramesOffset", "listCountOffset", "listBuffersPointerOffset", "listIdentitiesPointerOffset",
                   "listIdentityIndirection", "listSkippedCaptureStatus", "auxiliaryFlagEffectOffset", "listFlagEffectOffset")
    equal("layout", dict(zip(layout_keys, expected_layout)), layout)
    # Join the two caller flag bytes through the already authenticated Execute body.
    execute = consumer_contract["methods"]["execute"]
    caller = read(int(execute["rva"], 16), execute["bodyLength"])
    equal("callerHash", execute["bodySha256"], hashlib.sha256(caller).hexdigest())
    equal("callerFlags", bytes.fromhex("0fb687ed0300004c8bc588442428498bd60fb687ec030000486bcb6888442420"), caller[0x71:0x91])
    equal("polynomial", (coefficients, "float32 Horner, separate rounding at each multiply/add",
          "P(q)*savedSample + P(1-q)*currentSample, separately rounded",
          "float32((remaining-frameIndex)*float32(1/duration))",
          "float32(float32(1-float32(frameIndex*float32(1/validFrames)))*ordinaryQ)"),
          tuple(contract["polynomial"][k] for k in ("coefficientsDescending", "evaluation", "blend", "ordinaryQ", "shortBufferQ")))
    equal("transition", ("min(remaining,primaryMaximumFrames)", "min(bufferValidFrames,frameLimit)",
          "bufferValidFrames < frameLimit", "frameLimit independent of valid frame counts", "retained", True,
          "last valid sample per admitted planar channel; primary/auxiliary need positive valid frame counts",
          "min(currentListCount,previousCapturedCount)", "opaque identity value equality",
          "min(currentListCount,capturedCapacity)", "pack identities and last samples for status !=17 and validFrames !=0",
          "nonzero byte; auxiliary also requires nonnull pointer"),
          tuple(contract["transition"][k] for k in ("frameLimit", "processedFrames", "shortBufferCondition", "counterDecrement",
              "historiesDuringTransition", "captureWhenCounterZero", "capture", "listTransitionCount", "listTransitionMatching",
              "listCaptureCount", "listCapture", "enabledFlags")))
    return dict(status="validated", evidenceBoundary="conditional", contextRoutineJoined=True,
                recordStrideBytes=104, primaryPlanarChannelLimit=12, auxiliaryPlanarChannelLimit=2,
                transition="degree-six polynomial blend of saved and current samples",
                polynomialCoefficientsDescending=coefficients, floatingOperationRounding="float32 per operation",
                timerDecrement="min(remaining,primaryMaximumFrames), independent of valid frames",
                transitionHistoriesRetained=True, zeroTimerCapturesLastValidSamples=True,
                listMatchesOpaqueIdentityValues=True, listCaptureSkipsStatus=17,
                emptyPrimaryOrAuxiliaryCaptureAdmissionProven=False, contextProducerProven=False,
                allocationOrLifetimeProven=False, runtimeInvocationObserved=False, meaningBoundary=contract["meaningBoundary"])


def check_mastering_shared_native_inputs(game_root: Path):
    from scripts.webui.audio.semantics.wwise_effect_native import check_effect_native_extension
    from scripts.webui.audio.semantics.wwise_mastering_consumer import load_mastering_consumer_contract, validate_mastering_consumer
    from scripts.webui.audio.semantics.wwise_mastering_updates import load_mastering_contract, validate_mastering_updates

    def validate(parent, base, read):
        c = load_mastering_consumer_contract(); class_id = c["classId"]
        updates = validate_mastering_updates(load_mastering_contract(), parent["nativeInputs"],
                                             parent["registrationWitnesses"][class_id], base, read,
                                             structural=parent["structuralSchemas"][class_id])
        consumer = validate_mastering_consumer(c, parent, updates, base, read)
        return validate_mastering_shared(load_mastering_shared_contract(), parent["nativeInputs"], c, consumer, read)

    return check_effect_native_extension(game_root, evidence_key="shared", validate=validate)
