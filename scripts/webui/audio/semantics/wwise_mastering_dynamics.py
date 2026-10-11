"""Authenticate Mastering band dynamics and all three peak/clip modes.

Program declarations and native addresses live in the reviewed contract. The
validator checks complete program coverage, relative joins, vector initializer
semantics and independent arithmetic obligations. SIMD constants are conditional
on initialization and no later overwrite; no running client is observed here.
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
def load_mastering_dynamics_contract():
    return json.loads((CONTRACTS_DIR / "wwise_mastering_dynamics_native.json").read_text(encoding="utf-8"))


def _pair_target_indices(index, mapped_value, pair_option=1):
    """Logical target cells selected by the native unsigned pair arithmetic.

    The map determines parity; the code never searches for the mapped partner.
    A predecessor of logical cell zero is zero-extended before addressing.
    """
    if pair_option != 1 or mapped_value in (2, 3):
        return [index]
    if mapped_value & 1:
        return [(index - 1) & 0xffffffff, index]
    return [index, index + 1]


def _peak_storage_plan(delay_present, telemetry_present, optional_flag, channels, failed_mask):
    """Requests and partial returns of the shared admitted peak-application tail."""
    requests = []; clear_delay = False
    if not delay_present:
        requests.append("delay")
        if failed_mask & 1:
            return dict(requests=requests, clearDelay=False, result=0x8080000a)
        clear_delay = True
    if optional_flag == 1 and channels and not telemetry_present:
        requests.append("telemetry")
        if failed_mask & 2:
            return dict(requests=requests, clearDelay=clear_delay, result=0x8080000a)
    return dict(requests=requests, clearDelay=clear_delay, result=0)


def _band_storage_plan(present, optional_flag, bands, channels, failed_mask):
    """One shared side-output request per enabled active band, in band order."""
    requests = []
    if optional_flag == 1 and channels:
        for band in range(bands):
            if not present[band]:
                requests.append(band)
                if failed_mask & (1 << band):
                    return dict(requests=requests, result=0x8080000a)
    return dict(requests=requests, result=0)


def validate_mastering_dynamics(contract, native_inputs, updates, consumer, filtering, filter_contract, scalar, small_fill, read,
                                descriptor_contract, consumer_contract):
    def equal(check, expected, actual, offset=0):
        if expected != actual:
            raise EffectUpdateError("masteringDynamics", check, offset, expected, actual)

    equal("schema", "endfield.wwise-mastering-dynamics-native-contract.v8", contract["schema"])
    equal("reviewStatus", "reviewed", contract["status"])
    equal("inputs", native_inputs, contract["nativeInputs"])
    equal("consumerProof", "validated", consumer["status"])
    equal("updateProof", "validated", updates["status"])
    equal("filterProof", "validated", filtering["status"])
    equal("scalarProof", "validated", scalar["status"])
    equal("fillProof", "validated", small_fill["status"])
    equal("filterInputs", native_inputs, filter_contract["nativeInputs"])
    equal("descriptorOwnerSchema", "endfield.wwise-mastering-gain-native-contract.v3", descriptor_contract["schema"])
    equal("descriptorOwnerStatus", "reviewed", descriptor_contract["status"])
    equal("descriptorOwnerInputs", native_inputs, descriptor_contract["nativeInputs"])
    equal("descriptorConsumerInputs", native_inputs, consumer_contract["nativeInputs"])
    from scripts.webui.audio.semantics.wwise_mastering_gain import _descriptor_admission
    admission = _descriptor_admission(descriptor_contract["descriptorAdmission"], consumer_contract, read, equal)
    equal("boundary", "conditional", contract["evidenceBoundary"])
    methods = contract["methods"]
    equal("methodSet", {"processBands", "processModes", "bandEntry", "bandKernel", "telemetry",
                        "clipEntry", "peakEntry", "clipKernel", "peakKernel", "sum", "delayedKernel",
                        "convertPeak", "clamp", "applyPeak", "initPeak", "convertBands", "applyBands", "initBands",
                        "filterConversion", "filterCoefficients"}, set(methods))
    bodies = {}
    for name, row in methods.items():
        size = row["bodyLength"]
        equal("extent:" + name, True, type(size) is int and 0 < size <= 8192)
        body = read(int(row["rva"], 16), size)
        equal("length:" + name, size, len(body))
        equal("hash:" + name, row["bodySha256"], hashlib.sha256(body).hexdigest())
        bodies[name] = body
    for section, name in ((1, "processBands"), (3, "processModes")):
        pointers = consumer["callbackBinding"]["callbackPointers"][section]["pointersByRecordOffset"]
        equal("callback:" + name, int(methods[name]["rva"], 16), pointers.get(32, pointers.get("32")))
    for section, suffix in ((1, "Bands"), (3, "Peak")):
        pointers = consumer["callbackBinding"]["callbackPointers"][section]["pointersByRecordOffset"]
        for slot, prefix in ((56, "convert"), (16, "init"), (40, "apply")):
            name = prefix + suffix
            equal("callback:" + name, int(methods[name]["rva"], 16), pointers.get(slot, pointers.get(str(slot))))
    equal("externalSet", {"filterEntry", "copyPrimitive", "powerHelper", "coefficientHelper", "fillPrimitive", "profileCompare",
                          "packedTrigonometricHelper", "imageBase"}, set(contract["externals"]))
    equal("imageBase", 0, int(contract["externals"]["imageBase"]["rva"], 16))
    equal("filterEntryJoin", int(filter_contract["methods"]["entry"]["rva"], 16),
          int(contract["externals"]["filterEntry"]["rva"], 16))
    equal("powerHelperJoin", int(scalar["methodRva"], 16), int(contract["externals"]["powerHelper"]["rva"], 16))
    equal("powerHelperBoundary", False, scalar["wholeFunctionEquivalent"])
    equal("fillHelperJoin", int(small_fill["methodRva"], 16), int(contract["externals"]["fillPrimitive"]["rva"], 16))

    # These are mathematical values and masks, not a second native catalog.
    float_vectors = dict(logBaseScale=0.3010300099849701, powerBaseScale=3.321928024291992,
                         logPolynomialA=-1/3, logPolynomialB=2., logPolynomialC=-5/3,
                         expPolynomialA=.25, expPolynomialB=.75, expPolynomialC=1.,
                         bandZero=0., gainDbScale=.05, kneeHalf=.5, powerDbScale=10.,
                         bandUnity=1., negativePowerFallback=-100., mantissaOne=1.,
                         clipZero=0., clipUnity=1., clipNegativeUnity=-1.)
    integer_vectors = dict(exponentBias=127, exponentMask=255, mantissaMask=0x7fffff)
    vectors = contract["initializedVectors"]
    equal("vectorSet", set(float_vectors) | set(integer_vectors), set(vectors))
    for name, row in vectors.items():
        expected = (struct.pack("<f", float_vectors[name]) if name in float_vectors
                    else struct.pack("<I", integer_vectors[name])) * 4
        equal("vectorValue:" + name, expected.hex(), row["vectorHex"])
        size = row["bodyLength"]
        equal("initializerExtent:" + name, True, size in (11, 16, 17))
        body = read(int(row["rva"], 16), size)
        source = row["sourceRva"]
        if source is None:
            equal("initializerZero:" + name, bytes(16), expected)
            equal("initializerLoad:" + name, bytes.fromhex("0f57c0"), body[:3])
            store_at = 3
        else:
            equal("initializerLoad:" + name, bytes.fromhex("660f6f05"), body[:4])
            address = int(row["rva"], 16) + 8 + struct.unpack_from("<i", body, 4)[0]
            equal("initializerSourceJoin:" + name, int(source, 16), address)
            equal("initializerSourceValue:" + name, expected, read(address, 16))
            store_at = 8
        prefix = bytes.fromhex("660f7f05" if size == 17 else "0f2905")
        equal("initializerStore:" + name, prefix, body[store_at:store_at + len(prefix)], store_at)
        end = store_at + len(prefix) + 4
        equal("initializerReturn:" + name, end + 1, size)
        equal("initializerReturnByte:" + name, b"\xc3", body[end:])
        address = int(row["rva"], 16) + end + struct.unpack_from("<i", body, end - 4)[0]
        equal("initializerDestinationJoin:" + name, int(row["destinationRva"], 16), address)

    data = contract["data"]
    expected_data = dict(absoluteMask=struct.pack("<4I", *([0x7fffffff] * 4)),
                         scalarUnity=struct.pack("<f", 1.), delayedGainBias=struct.pack("<4f", *([.0026] * 4)),
                         signMask=struct.pack("<4I", *([0x80000000] * 4)), laneBits=struct.pack("<4I", 1, 2, 4, 8),
                         peakLower=struct.pack("<f", -30.), peakFirstTimeUpper=struct.pack("<f", 2.6),
                         peakSecondTimeUpper=struct.pack("<f", 5.), controlScale=struct.pack("<f", .05),
                         controlBase=struct.pack("<f", 10.), timeFactor=struct.pack("<f", -2.2))
    expected_data.update({k: struct.pack("<f", v) for k, v in dict(percentageUpper=100., crossoverUpper=24000.,
        bandThresholdLower=-60., ratioUpper=30., scalarHalf=.5, minimumTime=.01, bandOutputUpper=18., bandOutputLower=-18.,
        kneeUpper=20., powerTimeFactor=-440.0000305175781, inactiveReleaseFactor=-22., qLower=.1, qUpper=12.,
        angleScale=6.2831854820251465, negativeAngleScale=-6.2831854820251465, approximateEulerBase=2.718280076980591,
        negativeHalf=-.5, negativeTwo=-2., quarterControlScale=.025, sqrtTwo=1.4142135381698608,
        coefficientThreshold=.7).items()})
    equal("dataSet", set(expected_data) | {"allocationContext", "defaultProfilePointer", "profileKeyPrefix", "defaultProfilePrefix",
                                          "bandAllocationContext", "bandDefaultProfilePrefix", "coefficientTable"}, set(data))
    for name, row in data.items():
        size = row["byteLength"]
        equal("dataExtent:" + name, True, size == (52 if name == "coefficientTable" else len(bytes.fromhex(row["bytesHex"]))) and size in (4, 8, 16, 52))
        if name in expected_data:
            equal("dataMeaning:" + name, expected_data[name].hex(), row["bytesHex"])
        equal("dataValue:" + name, bytes.fromhex(row["bytesHex"]), read(int(row["rva"], 16), size))
    for name, row in methods.items():
        cursor = 0
        for step in row["program"]:
            equal("programCoverage:" + name, cursor, step["offset"], cursor)
            if "bytesHex" in step:
                raw = bytes.fromhex(step["bytesHex"])
                equal("programNonempty:" + name, True, bool(raw), cursor)
                equal("program:" + name, raw, bodies[name][cursor:cursor + len(raw)], cursor)
                cursor += len(raw)
                continue
            prefix = bytes.fromhex(step["prefixHex"]); suffix = bytes.fromhex(step["suffixHex"])
            end = cursor + len(prefix) + 4 + len(suffix)
            raw = bodies[name][cursor:end]
            equal("relativeExtent:" + name, end - cursor, len(raw), cursor)
            equal("relativeOpcode:" + name, prefix, raw[:len(prefix)], cursor)
            equal("relativeSuffix:" + name, suffix, raw[len(prefix) + 4:], cursor)
            kind = step["targetKind"]; target_name = step["target"]
            groups = {"method": methods, "external": contract["externals"], "data": data,
                      "initializedVector": vectors}
            equal("relativeKind:" + name, True, kind in groups, cursor)
            target_row = groups[kind][target_name]
            target = int(target_row["destinationRva" if kind == "initializedVector" else "rva"], 16)
            encoding = step.get("encoding", "relative32")
            equal("relativeEncoding:" + name, True, encoding in ("relative32", "absoluteImageRva"), cursor)
            if encoding == "absoluteImageRva":
                equal("absoluteTableRead", ("filterCoefficients", 0x8f, "data", "coefficientTable", "8b8cba", ""),
                      (name, cursor, kind, target_name, step["prefixHex"], step["suffixHex"]), cursor)
                actual = struct.unpack_from("<I", raw, len(prefix))[0]
            else:
                actual = int(row["rva"], 16) + end + struct.unpack_from("<i", raw, len(prefix))[0]
            equal("relativeTarget:" + name, target, actual, cursor)
            cursor = end
        equal("programEnd:" + name, len(bodies[name]), cursor, cursor)

    def block(name, offset, encoded):
        expected = bytes.fromhex(encoded)
        equal("arithmetic:" + name, expected, bodies[name][offset:offset + len(expected)], offset)

    block("clamp", 0, "0f2fc277050f2fc1730c0f2fc173040f28c1c30f28c2c3")
    equal("clampExtent", 23, len(bodies["clamp"]))
    block("convertBands", 0x5c8, "81f9010002010f85e20200003bc10f85da020000418b4e088d41ff83f8030f87ca020000")
    block("convertBands", 0x5ef,
          "418b461883f80f0f87ba020000894618418b460c83f8020f87aa0200004183f8017509413bc00f859b020000")
    block("convertBands", 0x61e, "418b461483f8010f878b020000")
    block("convertBands", 0x649, "418b461c85c00f8561020000413946200f8557020000")
    block("convertBands", 0x6aa, "85ff740e8d47ff0f2f4486240f86fa010000")
    block("convertBands", 0x7cd, "f30f104cfe30f30f58c9f30f1144de440f54cf0f2fc17606f30f114cde44")
    block("convertBands", 0x820, "c740fc0000a0c148c7000000004089680848c7400c0000803f488d4018")
    block("initBands", 0x95, "8b0289414048c741480400000048c741500000c84244897158")
    block("applyBands", 0xb82, "3d010002010f85500c00008b4a084533f6")
    block("applyBands", 0xbc3, "c744244000100101c744244418000000c7442450f4fd343f")
    block("applyBands", 0xd80, "f3460f1054e3304e8d3c2af3460f1194bfe80d0000428b44f334428984bf180e0000")
    block("applyBands", 0xdb4, "8b47400f57c9f3480f2ac8f30f59c8410f28c0f30f5ec1")
    block("applyBands", 0xe2e, "f3420f104cf340f3410f59cc")
    block("applyBands", 0xe49,
          "0f28cff3420f1074f3440f28c7f3420f11b4bfd80e0000f3420f5e4cf334f30f5cc10f57c9f3420f1184bf080f0000")
    block("applyBands", 0xe78, "410f28c38b4740f3480f2ac8f30f5ec1")
    block("applyBands", 0xe98, "f3410f59f6f30f5cc8f3440f5cd6f3420f118cbf380f0000f3460f1194bfc80f0000")
    block("applyBands", 0x178e, "498b064c8d05")
    block("applyBands", 0x1798, "41b96a000000ba00040000498bceff5008")
    block("applyBands", 0x174c, "448b3f488db7e80d0000440fb66f0c33c04c8bb588000000448be0"
          "4180fd017551443b6748734b8bd84585ff7444660f1f44000085db7531"
          "4883be10020000007527498b06")
    block("applyBands", 0x1798, "41b96a000000ba00040000498bceff5008488986100200004885c0741e"
          "ffc3413bdf72c433c041ffc44881c6700200004183fc047299e962faffff"
          "b80a008080e958faffff")
    band_storage = contract["sectionOne"]["storage"]
    equal("bandStorage", ("conditional", 12, 1, 72, 3560, 624, 528, 4, 106, 1024, "0x8080000a",
          "at most one request per active band when logical channels are nonzero",
          "nonnull first pointer retains the band storage", "failure stops later bands without rolling back prior writes"),
          tuple(band_storage[k] for k in ("evidenceBoundary", "optionalFlagOffset", "optionalFlagValue", "activeBandCountOffset",
              "bandStateOffset", "bandStateStride", "firstTelemetryPointerOffset", "maximumBands", "allocationTag",
              "requestBytes", "allocationFailure", "requests", "reuse", "partialFailure")))
    block("filterConversion", 0x34, "8b51080f57c985d20f84ae000000f30f10510c0f57c0418bc1f3480f2ac0f30f5ed0")
    block("filterConversion", 0xa8, "f30f10442430f30f5ed0f30f11030f28da0f28ca")
    block("filterCoefficients", 0x75, "f3440f5ed9f3440f59df83ff0c0f874b040000")
    block("filterCoefficients", 0xbd, "440f28c6f3450f5cc2410f28f8f3410f59fc440f28cf")
    block("filterCoefficients", 0x125, "410f28faf30f58fe450f28c2f3440f58c6f3410f59fc")
    block("filterCoefficients", 0x4af,
          "f30f111333c0f3440f115304f30f117308f3440f114b0cf3440f114310f30f117b14")
    table = struct.unpack("<13I", bytes.fromhex(data["coefficientTable"]["bytesHex"]))
    generator_rva = int(methods["filterCoefficients"]["rva"], 16)
    equal("coefficientTypeOneRoute", generator_rva + 0xb5, table[1])
    equal("coefficientTypeTwoRoute", generator_rva + 0x11d, table[2])
    block("convertPeak", 0x1b4,
          "81f9030002010f85d00000003bc10f85c80000008b4b0883f9020f87bc000000"
          "8b431c83f8010f87b000000083fe0175083bc60f85a3000000")
    block("convertPeak", 0x20d, "837b0802740a")
    block("convertPeak", 0x21d, "0f57d2f30f1043100f57c9")
    block("convertPeak", 0x24c, "837b0802751cf30f10570c0f57c9")
    block("convertPeak", 0x26b, "0f28f0f30f1177188b431c89471c33c0")
    block("initPeak", 0x6e, "8b028941404489714c")
    block("applyPeak", 0x2a0, "f30f104e0c410f28c2f3410f59c9418bfe")
    block("applyPeak", 0x2b6, "f30f1144bb50410f28c2f30f104e18f3410f59c9")
    block("applyPeak", 0x2cf, "f30f1184bbe00000008b4b4885c90f84a500000083e9010f848100000083f9010f8529010000")
    block("applyPeak", 0x2f5, "c784bb80000000d0913b3df30f1046140f2ec775050f28ceeb23")
    block("applyPeak", 0x30f, "8b43400f57c9f3480f2ac8f30f59c8410f28c0f30f5ec1")
    block("applyPeak", 0x32b,
          "0f28ce f30f5cc8488bcf488bc3f30f118c8bb0000000f30f118cbb90020000"
          "c784bb60020000c0988b3c8b4610f30f118cbbc00200008984bb30020000")
    block("applyPeak", 0x36d, "c784bb800000000000803fc784bbb00000000000803f")
    block("applyPeak", 0x397, "8b43400f57c9f3480f2ac8f30f59c8410f28c0f30f5ec1")
    block("applyPeak", 0x205, "4c89bc24e8000000440fb67b3c0f8561020000c1e009")
    block("applyPeak", 0x1e9,
          "41ffc64183fe0c0f829afeffff4883bb80030000008bf58b3b8b4304"
          "4c89bc24e8000000440fb67b3c0f8561020000c1e009")
    block("applyPeak", 0x222, "448bf041b970000000498b0424418bd6498bccff5008"
          "488983800300004885c00f8524020000be0a008080e927020000")
    block("applyPeak", 0x40c, "41ffc64183fe0c0f8287feffffe9d8fdffff")
    block("applyPeak", 0x46c, "4d8bc633d2488bc8")
    block("applyPeak", 0x479, "4180ff014c8bbc24e8000000755185f6754d85ff74499085ed7532"
          "4883bb88030000007528498b0424")
    block("applyPeak", 0x4a9, "41b97d000000ba00040000498bccff5008488983880300004885c0740d"
          "ffc53bef72c48bc6e950ffffffbe0a0080808bc6e944ffffff")
    block("initPeak", 0xe1, "85c078be488d8e40010000ba0c000000448971d0c7010000803f"
          "c781b00100000000803f4489b1e00100004489b1100200004489713044897160"
          "4489b1f00000004489b1200100004489b1900000004489b1c0000000488d4904"
          "4883ea0175b0c7464403000000e956ffffff")
    peak_storage = contract["sectionThree"]["storage"]
    equal("peakStorage", ("conditional", [0, 1, 2], 896, 904, 4, 9, 32, 112, 125, 1024, 60, 1,
          "0x8080000a", "only newly allocated successful delay storage", "nonnull pointers retained without capacity checks",
          "earlier control and pointer writes retained", [272, 320, 752, 800, 848, 368, 416, 560, 608, 464, 512],
          [0, 1065353216, 1065353216, 0, 0, 0, 0, 0, 0, 0, 0], 12, 3),
          tuple(peak_storage[k] for k in ("evidenceBoundary", "admittedModes", "delayPointerOffset", "telemetryPointerOffset",
              "strideOffset", "requestShift", "requestArithmeticBits", "delayAllocationTag", "telemetryAllocationTag",
              "telemetryRequestBytes", "optionalFlagOffset", "optionalFlagValue", "allocationFailure", "delayClear",
              "reuse", "partialFailure", "initialHistoryOffsets", "initialHistoryWords", "initialChannelCopies", "initialFlags")))
    application = contract["sectionThree"]["application"]
    equal("application", (64, 0, struct.unpack("<f", struct.pack("<f", .05))[0], 10.,
                          struct.unpack("<f", struct.pack("<f", -2.2))[0], 9, 1024, "d0913b3d", "c0988b3c"),
          tuple(application[k] for k in ("frequencyOffset", "frequencyDescriptorOffset", "controlScale", "controlBase",
              "timeFactor", "delayRequestShift", "optionalTelemetryRequestBytes", "delayedAttackBits", "delayedAuxiliaryBits")))
    conversion = contract["sectionThree"]["conversion"]
    equal("conversion", ("0x01020003", 32, [0, 2], [0, 1], 1, 1, [8, 12, 16, 20, 24, 28],
                         -30., struct.unpack("<f", struct.pack("<f", 2.6))[0], 5., True, True,
                         "negativeConvertedFirstFloat", "lowerBound"),
          tuple(conversion[k] for k in ("currentHeader", "byteLength", "modeRange", "linkRange", "specialMode",
              "requiredSpecialLink", "wordOffsets", "finiteLower", "firstTimeUpper", "secondTimeUpper",
              "delayedFirstTimeForcedZero", "otherModesPostWordForcedZero", "delayedPostUpper", "clampNaN")))
    section = consumer["sectionPointers"][3]
    equal("sectionHeaderJoin", int(conversion["currentHeader"], 16), section["header"])
    equal("sectionLengthJoin", conversion["byteLength"], section["byteLength"])
    word_rows = {r["receiverOffset"]: r for r in updates["bulkWordJoins"]["updateJoins"]}
    byte_rows = {r["receiverOffset"]: r for r in updates["bulkByteJoins"]["rows"] if r["kind"] == "nonzeroBooleanWord"}
    source_joins = []
    for offset in conversion["wordOffsets"]:
        receiver_offset = 8 + section["sourceOffset"] + offset
        row = (byte_rows if offset == 28 else word_rows).get(receiver_offset)
        equal("serializedControlJoin", True, row is not None, offset)
        source_joins.append(dict(sectionWordOffset=offset, **row))

    def f32(value):
        return struct.unpack("<f", struct.pack("<f", value))[0]

    band_conversion = contract["sectionOne"]["conversion"]
    equal("bandConversion", ("0x01020001", 144, [1, 4], [0, 2], 1, 1, [0., 100.], [0, 1], [0, 15],
          [28, 32], 36, [10., 24000.], True, 48, 24,
          [[-60., 0.], [1., 30.], [f32(.01), .5], [f32(.01), 5.], [-18., 18.], [0., 20.]],
          "twiceAbsoluteConvertedThreshold", [-20., 2., 0., 0., 1., 0.], "retainOutputBytes", "lowerBound"),
          tuple(band_conversion[k] for k in ("currentHeader", "byteLength", "bandRange", "linkRange", "specialMode",
              "requiredSpecialLink", "percentageRange", "pairRange", "bypassRange", "zeroWordOffsets", "crossoverOffset",
              "crossoverRange", "strictCrossoverOrder", "bandRecordOffset", "bandRecordStride", "bandFieldRanges", "kneeUpper",
              "inactiveRecord", "unreadCrossovers", "clampNaN")))
    band_application = contract["sectionOne"]["application"]
    equal("bandApplication", (64, 0, f32(.01), [0, 48, 96, 144, 192, 240, 288, 336, 480], 12,
          f32(-2.2), -440.0000305175781, -22., f32(.05), 10., "retained", 0., 1., "retainedUnused", "retained", 1024, 1, 2, 4, 2),
          tuple(band_application[k] for k in ("frequencyOffset", "frequencyDescriptorOffset", "percentageScale", "fieldArrayOffsets",
              "channelCapacity", "timeFactor", "powerTimeFactor", "inactiveReleaseFactor", "controlScale", "controlBase", "activeHistories",
              "inactivePowerHistory", "inactiveGainHistory", "singleBandFilterCounts", "filterHistories", "optionalTelemetryRequestBytes",
              "optionalTelemetryPointersPerBand", "cutoffStagesPerBoundary", "interiorFilterCount", "outerFilterCount")))
    coefficients = contract["sectionOne"]["coefficients"]
    equal("bandCoefficients", ("0x01011000", "0x02011000", 24, [1, 2], "f4fd343f", [0., .5], [f32(.1), 12.],
          6.2831854820251465, "float32(float32(0.5/Q)*packedHelperLane0)",
          ["1+alpha", "-2*packedHelperLane1", "1-alpha"],
          ["0.5*(1-packedHelperLane1)", "1-packedHelperLane1", "0.5*(1-packedHelperLane1)"],
          ["0.5*(1+packedHelperLane1)", "-(1+packedHelperLane1)", "0.5*(1+packedHelperLane1)"],
          ["a0", "-a1/a0", "-a2/a0", "b0/a0", "b1/a0", "b2/a0"], "unresolved"),
          tuple(coefficients[k] for k in ("currentHeader", "rawHeader", "byteLength", "generatedTypes", "qualityBits",
              "normalizedFrequencyRange", "qualityRange", "angleScale", "alpha", "denominator", "typeOneNumerator",
              "typeTwoNumerator", "storage", "helperNumericalMeaning")))
    section = consumer["sectionPointers"][1]
    equal("bandSectionHeaderJoin", int(band_conversion["currentHeader"], 16), section["header"])
    equal("bandSectionLengthJoin", band_conversion["byteLength"], section["byteLength"])
    band_joins = []
    for offset in [8, 12, 16, 20, 24, 36, 40, 44] + list(range(48, 144, 4)):
        receiver_offset = 8 + section["sourceOffset"] + offset
        if offset == 24:
            rows = [r for r in updates["bulkByteJoins"]["rows"] if r["receiverOffset"] == receiver_offset]
            equal("bandMaskSourceJoin", [0, 1, 2, 3], sorted(r.get("maskBit", -1) for r in rows), offset)
            equal("bandMaskSourceKind", True, all(r["kind"] == "inverseZeroMask" for r in rows), offset)
        else:
            row = (byte_rows if offset == 20 else word_rows).get(receiver_offset)
            equal("bandSerializedControlJoin", True, row is not None, offset)
            rows = [row]
        band_joins.extend(dict(sectionWordOffset=offset, **r) for r in rows)

    # Independent arithmetic obligations remain even if a declaration and its
    # body hash are edited together. These instructions express sign-aware clip,
    # squared envelope, asymmetric smoothing and gain-history selection.
    block("clipKernel", 0x100,
          "0f28e5410f59d80fc2e6010f28c40f55c50f54dc0f56d8")
    block("clipKernel", 0x120,
          "0f28c80fc2cb010f28d10f55cb0f54d00f56d10f28ca410f59c80f54cc0f55e20f56cc0f53d50f59d1")
    block("peakKernel", 0x146,
          "0f28c10fc2c3010f5cd90f594cc5400f54d80f55c60f56d80f1044c570"
          "0f595cc5100f28d00f58d90f115cc4500fc2d3010f53cb0f59c80f54ca0f55d40f56ca")
    block("bandKernel", 0x2c2, "0f59db0f595cd5200f58d8660f6fc30f115cd430")
    block("bandKernel", 0x5c6,
          "0f28c20f5984c5700100000f28dc0f28cc0f59a4c5a00100000f598cc540010000"
          "0fc2da010f5994c5d00100000f28eb0f58c80f58e20f55e90f54e30f56ec"
          "0f116cc5f00f59acc5000200000f28d50f5954c5c0")
    block("bandKernel", 0x250, "410fb7c7450fb7c36683e01f4585d2")
    # Complete map handoff and minimum/pair region, including local branch
    # destinations and all register widths. The selected map word's low bit
    # chooses adjacent logical cells; neither partner lookup nor bounds occurs.
    block("initBands", 0x5c, "8b4208")
    block("initBands", 0x68,
          "89018b42108941048b42148941080fb6424888410c"
          "0f1042180f1141100f104a280f1149200f1042380f114130")
    block("processBands", 0x1f3,
          "488d5310410fb7c6448bce4869c8700200008b43544c8bc5894424484881c1e80d0000"
          "8b434c4803cbf30f11442440894424388b074889542430498bd4894424288b0389442420")
    block("bandKernel", 0x1b7, "488b9d40030000")
    block("bandKernel", 0x472,
          "410f28cc458bc3418bcb4585d2743c0f1f40006666660f1f840000000000"
          "0fb7c10f28d1f30f1004840f2fc173030f28c80f2fd00fb7d166410f46d066ffc1"
          "0fb7c1440fb7c2413bc272d38b854803000083e8010f84af00000083f8010f85c8000000"
          "410f2fcc0f83be0000000f28d1488d0424f3410f59d6b9030000000fc6d200"
          "0f1f40000f1f8400000000000f1110488d40104883e90175f3"
          "83bd5803000001755a410fb7c0448b0c83418d41fe83f8017649"
          "410fb7c8410fbae1008d41010f42c1448bc08bd08d41ff0f42c8418bc0"
          "48c1e020480bc848c1ea028bc183e10348c1e8024183e003488d0481"
          "f30f110c84498d0490f30f110c84eb2d410fb7c0f30f110c84eb22")
    pair = contract["sectionOne"]["pairLinking"]
    equal("pairDeclaration", ("conditional", 2, 1, [2, 3], 12, 16, 32, "unsigned32To64",
          "firstStrictlyLowerFiniteTarget", ["index", "index+1"], ["uint32(index-1)", "index"], False, False),
          tuple(pair[k] for k in ("evidenceBoundary", "linkMode", "pairOption", "excludedMappedValues",
              "targetScratchCells", "minimumIndexBits", "indexArithmeticBits", "addressExtension",
              "minimumSelection", "evenTargets", "oddTargets", "partnerLookup", "partnerBoundsCheck")))
    equal("pairProgramWindows", dict(sectionDescriptorMapCopy=[104, 149],
          sectionMapAndControlForwarding=[499, 570], kernelMapRead=[439, 446], minimumAndPairSelection=[1138, 1403]),
          pair["programWindows"])
    pair_cases = []; mapping = admission["maskMapping"]
    for subset in range(1, 1 << len(mapping)):
        rows = [row for j, row in enumerate(mapping) if subset & (1 << j)]
        values = [row["valueIndex"] for row in rows]
        count = len(values); stride = (count + 3) & ~3
        for index, value in enumerate(values):
            indices = _pair_target_indices(index, value)
            if any(cell >= count for cell in indices) or (len(indices) == 2 and
                    values[indices[0]] != values[indices[1]] - 1):
                pair_cases.append(dict(mask=sum(1 << row["maskBit"] for row in rows),
                    minimumIndex=index, mappedValue=value, targetIndices=indices,
                    outsideScratch=any(cell >= pair["targetScratchCells"] for cell in indices),
                    outsideLogical=any(cell >= count for cell in indices),
                    outsideRounded=any(cell >= stride for cell in indices),
                    mappedPartnerMatches=not any(cell >= count for cell in indices) and
                        (len(indices) == 1 or values[indices[0]] == values[indices[1]] - 1)))
    block("processBands", 0x26d, "664585f67412448bc6488bd5440faf07498bcf")
    block("delayedKernel", 0x161,
          "8b951003000041b9800000008bca4489542420c1ea0783e17f85c9448bc1"
          "458bda450f44c18d420144894424240f45d0899510030000")
    block("delayedKernel", 0x4e2,
          "410f28c30f5994c5b0000000410f5cd40fc2c2010f28c8410f54c30f55ca0f56c80f114cdd80")
    block("delayedKernel", 0x688,
          "420f1054cde00f28cc0fc2ca010f28d90f28c1420f5484cde0000000"
          "420f555ccc500f56d80f28c20f5ceb0f59dc0fc2c4010f56c1"
          "420f108ccd700100000f59ea0f58eb0f28d90f54e80f55c40f56e8")
    equal("delayLayout", (128, 896, 320, 656, True, struct.unpack("<f", struct.pack("<f", .0026))[0]),
          tuple(contract["sectionThree"][k] for k in ("delayFrames", "delayPointerOffset", "gainHistoryOffset",
              "releaseHistoryOffset", "rescanSharesFourLanes", "targetGainBias")))
    equal("bandLayout", (1, 72, 92, 100, 216, 4, 3560, 624, 88, 32, 384, 432, 4),
          tuple(contract["sectionOne"][k] for k in ("sectionIndex", "bandCountOffset", "filterCountOffset",
              "filterRecordOffset", "filterRecordStride", "filterRecordsPerBand", "bandStateOffset", "bandStateStride",
              "bypassMaskOffset", "gainTargetFramePeriod", "powerHistoryOffset", "gainHistoryOffset", "maximumBands")))
    equal("modeLayout", (3, 72, 76, 80, 128, 176, 272, 4, False),
          tuple(contract["sectionThree"][k] for k in ("sectionIndex", "modeOffset", "linkOffset", "thresholdOffset",
              "attackOffset", "releaseOffset", "envelopeOffset", "channelGroupWidth", "frameRounding")))
    equal("modeRoles", {"0": "asymmetricPeakEnvelopeThenUnityClip", "1": "thresholdClip", "2": "delayedWindowPeakAndGainSmoothing"},
          contract["sectionThree"]["modes"])
    return dict(status="validated", evidenceBoundary="conditional",
                sectionOneRole="parallelFilteredBandDynamicsThenSum", sectionThreeModes=contract["sectionThree"]["modes"],
                squaredEnvelopeRecurrence="powerAlpha*x*x + (1-powerAlpha)*previousPower; each operation float32",
                peakEnvelopeRecurrence="(1-release)*previousPeak + attack*max(abs(x)-previousPeak,0); each operation float32",
                gainTargetFramePeriod=32, targetPeriodRestartsAtEachCall=True, nonlinearGainUsesBitPolynomials=True,
                gainHistoryUsesAttackWhenTargetIsLower=True, firstProcessSeedsPowerFromUnfilteredInput=True,
                pairIndexArithmeticProven=True, pairMapDescriptorJoined=True,
                pairPartnerLookup=False, pairPartnerBoundsCheck=False,
                pairBoundsForAllAdmittedMasksProven=False, conditionalPairAdmissionCases=pair_cases,
                pairLiveReachabilityProven=False,
                singleBandSkipsFilterLoop=True, roundedChannelWidth=4, frameRounding=False,
                optionalTelemetryOutput=True, reciprocalInstruction="RCPPS", exactReciprocalClaim=False,
                simdInitializerWritesProven=True, simdInitializerInvocationProven=False,
                simdConstantImmutabilityProven=False, sectionThreeModeTwoProven=True,
                delayFrames=128, peakRescanSharesFourLanes=True, delayRotationOnPartialBlocks=True,
                peakStorageTailJoinedForEveryAdmittedMode=True, peakStorageAllocationAndFailureRoutesProven=True,
                peakExistingDelayStorageRetainedWithoutCapacityCheck=True, peakOnlyNewDelayStorageCleared=True,
                peakInitialHistoriesResetAfterNonnegativeApplication=True,
                peakStorageCapacityOrRetryRecoveryProven=False,
                currentPeakConversionProven=True, peakSerializedControlJoins=source_joins,
                peakConversionNaN="lowerBound", conversionAndApplicationProven=True,
                currentBandConversionProven=True, bandApplicationProven=True, bandSerializedControlJoins=band_joins,
                bandSharedTelemetryStorageTailProven=True,bandTelemetryRequestsStopOnFirstFailure=True,
                bandTelemetryCapacityOrRetryRecoveryProven=False,
                crossoverCoefficientArithmeticProven=True, crossoverHelperNumericalMeaningProven=False,
                activeBandHistoriesRetained=True, inactiveBandHistoriesReset=True, filterHistoriesRetained=True,
                bandTimeCoefficient="1-coefficientHelper(float32(-2.2/float32(frequency*time))); zero/unordered time selects one",
                bandPowerCoefficient="1-coefficientHelper(float32(-440.0000305175781/frequency))",
                crossoverStagesPerBoundary=2, defaultOrLegacyControlSemanticsProven=False,
                peakApplicationProven=True, peakApplicationBoundary="direct fields and helper arguments; scalar results retain their existing boundaries",
                peakPowerArguments="10 and float32(convertedFloat*0.05)",
                peakTimeCoefficient="1-coefficientHelper(float32(-2.2/float32(frequency*time))); zero/unordered time selects one",
                delayAllocationRequest="32-bit frameStride shifted left nine", allocationBoundsOrLifetimeProven=False,
                coefficientHelperMeaning="unresolved", defaultProfileResolutionProven=False,
                conversionRequiresReadableStruct=True,
                publicControlNamesProven=False, runtimeInvocationObserved=False,
                meaningBoundary=contract["meaningBoundary"])


def validate_mastering_dynamics_effect_context(parent, base, read):
    """Reuse one selected image for dynamics and dependent focused audits."""
    from scripts.webui.audio.semantics.wwise_effect_small_fill import load_small_fill_contract, validate_small_fill
    from scripts.webui.audio.semantics.wwise_effect_scalar import load_scalar_contract, validate_scalar_correspondence
    from scripts.webui.audio.semantics.wwise_mastering_consumer import load_mastering_consumer_contract, validate_mastering_consumer
    from scripts.webui.audio.semantics.wwise_mastering_filter import load_mastering_filter_contract, validate_mastering_filter
    from scripts.webui.audio.semantics.wwise_mastering_updates import load_mastering_contract, validate_mastering_updates

    c = load_mastering_consumer_contract(); class_id = c["classId"]
    updates = validate_mastering_updates(load_mastering_contract(), parent["nativeInputs"],
                                         parent["registrationWitnesses"][class_id], base, read,
                                         structural=parent["structuralSchemas"][class_id])
    consumer = validate_mastering_consumer(c, parent, updates, base, read)
    fill = validate_small_fill(load_small_fill_contract(), parent["nativeInputs"], read)
    fc = load_mastering_filter_contract()
    filtering = validate_mastering_filter(fc, parent["nativeInputs"], consumer, fill, read)
    dc = load_mastering_dynamics_contract()
    scalar = validate_scalar_correspondence(load_scalar_contract(), parent["nativeInputs"], read)
    if dc["classId"] != class_id:
        raise EffectUpdateError("masteringDynamics", "classJoin", 0, class_id, dc["classId"])
    from scripts.webui.audio.semantics.wwise_mastering_gain import load_mastering_gain_contract
    return validate_mastering_dynamics(dc, parent["nativeInputs"], updates, consumer, filtering, fc, scalar, fill, read,
                                      load_mastering_gain_contract(), c)


def check_mastering_dynamics_native_inputs(game_root: Path):
    from scripts.webui.audio.semantics.wwise_effect_native import check_effect_native_extension

    return check_effect_native_extension(game_root, evidence_key="dynamics", validate=validate_mastering_dynamics_effect_context)
