"""Prove bounded byte-fill writes on all dispatched native small-fill routes."""
from __future__ import annotations

import hashlib
import json
import struct
from functools import lru_cache
from pathlib import Path

from scripts.game_data.contracts import CONTRACTS_DIR
from scripts.webui.audio.semantics.wwise_effect_updates import EffectUpdateError


@lru_cache(maxsize=1)
def load_small_fill_contract():
    return json.loads((CONTRACTS_DIR / "wwise_effect_small_fill_native.json").read_text(encoding="utf-8"))


def validate_small_fill(contract, native_inputs, read):
    def equal(check, expected, actual, offset=0):
        if expected != actual:
            raise EffectUpdateError("effectSmallFill", check, offset, expected, actual)

    equal("schema", "endfield.wwise-effect-small-fill-native-contract.v1", contract["schema"])
    equal("reviewStatus", "reviewed", contract["status"])
    equal("nativeInputs", native_inputs, contract["nativeInputs"])
    equal("boundary", "conditional", contract["evidenceBoundary"])
    equal("maximumLength", 144, contract["maximumLength"])
    method = contract["method"]; start = int(method["rva"], 16)
    equal("recordedBodyLength", 904, method["bodyLength"])
    body = read(start, method["bodyLength"])
    equal("bodyLength", 904, len(body))
    equal("bodyHash", method["bodySha256"], hashlib.sha256(body).hexdigest())

    def block(at, encoded):
        raw = bytes.fromhex(encoded)
        equal("program", raw, body[at:at + len(raw)], at)

    def branch(at, prefix, target):
        p = bytes.fromhex(prefix); raw = body[at:at + len(p) + 4]
        equal("branchOpcode", p, raw[:len(p)], at)
        equal("branchTarget", target, start + at + len(raw) + struct.unpack_from("<i", raw, len(p))[0], at)

    # Replicate the low fill byte in both vector halves; preserve original
    # pointer in RAX/R9. R10 is the PE image base for relative-offset tables.
    block(0, "488bc14c8bc94c8d15")
    equal("imageBaseLea", 0, start + 13 + struct.unpack_from("<i", body, 9)[0], 6)
    block(0xd, "0fb6d249bb01010101010101014c0fafda66490f6ec34983f80f0f87830000000f1f004903c8")
    block(0x3b, "4d03ca41ffe1")
    block(0xb0, "660f6cc04983f820770cf30f7f01f3420f7f4401f0c3833d")
    # Global values only choose a route. Every reachable small route below
    # has the same bounded write coverage, so their live values are unnecessary.
    equal("cpuComparisonImmediate", 3, body[0xcc], 0xc6)
    branch(0xcd, "0f82", start + 0x2b0)
    block(0xd3, "4c3b05")
    block(0xda, "76164c3b05")
    block(0xe3, "770df605")
    equal("repeatFlag", 2, body[0xeb], 0xe5)
    repeat = contract["repeat"]; repeat_rva = int(repeat["rva"], 16)
    equal("recordedRepeatLength", 16, repeat["bodyLength"])
    branch(0xec, "0f85", repeat_rva)
    block(0xf2, "c4e37d18c0014c8bc94983e11f4983e920492bc9492bd14d03c14981f8000100007665")
    # Length <=144 cannot reach the >256 AVX loop or non-temporal path.
    block(0x17a, "4d8d481f4983e1e04d8bd949c1eb05")
    block(0x191, "4d03da41ffe3")
    block(0x2b0, "4c3b05")
    block(0x2b7, "760df605")
    equal("sseRepeatFlag", 2, body[0x2bf], 0x2b9)
    branch(0x2c0, "0f85", repeat_rva)
    block(0x2c6, "4c8bc94983e10f4983e910492bc9492bd14d03c14981f880000000764b66666666660f1f840000000000")
    block(0x2f0,
          "660f7f01660f7f4110660f7f4120660f7f4130660f7f4140660f7f4150660f7f4160660f7f4170"
          "4881c1800000004981e8800000004981f88000000073c2"
          "4d8d480f4983e1f04d8bd949c1eb04")
    block(0x345, "4d03da41ffe3")
    repeated = read(repeat_rva, repeat["bodyLength"])
    equal("repeatLength", 16, len(repeated))
    equal("repeatHash", repeat["bodySha256"], hashlib.sha256(repeated).hexdigest())
    equal("repeatProgram", bytes.fromhex("578bc2488bf9498bc8f3aa498bc15fc3"), repeated)

    tables = contract["tables"]
    equal("tableSet", {"small", "sse", "avx"}, set(tables))
    expected_refs = {"small": (0x33, "478b8c82"), "sse": (0x33d, "478b9c9a"), "avx": (0x189, "478b9c9a")}
    for name, table in tables.items():
        at, prefix = expected_refs[name]
        equal("tableReference:" + name, at, table["referenceBodyOffset"], at)
        block(at, prefix)
        equal("tableAddress:" + name, int(table["rva"], 16), struct.unpack_from("<I", body, at + 4)[0], at)
        count = 16 if name == "small" else 9
        equal("tableCount:" + name, count, len(table["entryOffsets"]))
        equal("tableRows:" + name, [start + v for v in table["entryOffsets"]],
              list(struct.unpack("<" + str(count) + "I", read(int(table["rva"], 16), count * 4))))

    # Interpret every small jump-table target as stores relative to end pointer.
    # Each supported opcode names R11's replicated byte, word, dword or qword.
    stores = [(bytes.fromhex(p), width) for p, width in
              (("4c8959", 8), ("448959", 4), ("66448959", 2), ("448859", 1))]
    for count, at in enumerate(tables["small"]["entryOffsets"]):
        covered = set(); position = at
        for _ in range(5):
            equal("smallPosition", True, 0 <= position < len(body), position)
            if body[position] == 0xc3:
                break
            selected = next(((p, width) for p, width in stores if body[position:position + len(p)] == p), None)
            equal("smallStoreOpcode", True, selected is not None, position)
            prefix, width = selected
            displacement = struct.unpack_from("<b", body, position + len(prefix))[0]
            begin = count + displacement
            equal("smallStoreBounds", True, 0 <= begin and begin + width <= count, position)
            covered.update(range(begin, begin + width)); position += len(prefix) + 1
        else:
            equal("smallReturn", True, False, position)
        equal("smallCoverage", set(range(count)), covered, at)

    # Recognize complete backward fallthrough tails, including their final
    # unaligned end store and original-pointer store. The table selects exactly
    # ceil(remainder/width) stores, rather than a proximity-derived entry count.
    for name, width, first, tail, end_prefix, base_prefix, terminal in (
        ("sse", 16, 0x34b, 0x37c, "f3420f7f4401f0", "f30f7f00", "c3"),
        ("avx", 32, 0x197, 0x1d4, "c4a17e7f4401e0", "c5fe7f00", "c5f877c3"),
    ):
        entries = tables[name]["entryOffsets"]
        position = first; expected = [tail + len(bytes.fromhex(end_prefix)), tail]
        for distance in range(8 * width, 2 * width - 1, -width):
            expected.append(position)
            if name == "sse":
                encoded = "f3420f7f4409" + struct.pack("<b", -distance).hex()
            elif distance >= 160:
                encoded = "c4a17e7f8409" + struct.pack("<i", -distance).hex()
            else:
                encoded = "c4a17e7f4409" + struct.pack("<b", -distance).hex()
            block(position, encoded); position += len(bytes.fromhex(encoded))
        equal("tailPartition:" + name, tail, position)
        equal("tailEntries:" + name, [expected[0], expected[1], *reversed(expected[2:])], entries)
        block(tail, end_prefix + base_prefix + terminal)

    # Exhaustive finite length/alignment geometry proves all allowed intervals
    # remain within the requested extent and cover it, including overlapping
    # first/end writes and the possible single SSE 128-byte loop.
    geometries = 0
    for width in (16, 32):
        for count in range(33, contract["maximumLength"] + 1):
            for alignment in range(width):
                position = width - alignment; remainder = count - position
                intervals = [(0, width)]
                if width == 16 and remainder > 128:
                    intervals.append((position, position + 128)); position += 128; remainder -= 128
                blocks = (remainder + width - 1) // width
                for n in range(blocks - 1):intervals.append((position + n * width, position + (n + 1) * width))
                intervals.append((count - width, count))
                covered = set()
                for begin, end in intervals:
                    equal("vectorStoreBounds", True, 0 <= begin <= end <= count)
                    covered.update(range(begin, end))
                equal("vectorCoverage", set(range(count)), covered); geometries += 1
    return dict(status="validated", evidenceBoundary="conditional", methodRva=method["rva"],
                byteFill=True, lengthRange=[0, 144], lowByteReplicated=True, originalPointerReturned=True,
                routes=["scalar", "sse", "avx", "repeat"], vectorLengthAlignmentCases=geometries,
                liveCpuSelectionObserved=False, largerLengthsProven=False, meaningBoundary=contract["meaningBoundary"])


def check_small_fill_native_inputs(game_root: Path):
    from scripts.webui.audio.semantics.wwise_effect_native import check_effect_native_extension

    def validate(parent, base, read):
        return validate_small_fill(load_small_fill_contract(), parent["nativeInputs"], read)

    return check_effect_native_extension(game_root, evidence_key="smallFill", validate=validate)
