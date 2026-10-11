"""Authenticate reviewed partial correspondence with the CRT's named powf.

The shipped helper and the available named CRT implementation differ. Reviewed
regions agree after their explicit relative operands are masked, and selected
referenced constants and complete lookup tables agree byte for byte. The
contract records both native and COFF provenance. This identifies a powf-family
implementation, not whole-function equivalence or its live CPU branch.

An offline scalar-path comparison agrees with base-10 powers on its sampled
finite inputs. That generated receipt is separate from this static validator:
no sample count, output value or emulator success becomes a universal claim.
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
def load_scalar_contract() -> dict[str, Any]:
    return json.loads((CONTRACTS_DIR / "wwise_effect_scalar_native.json").read_text(encoding="utf-8"))


def validate_scalar_correspondence(
    contract: dict[str, Any], native_inputs: dict[str, Any],
    read: Callable[[int, int], bytes],
) -> dict[str, Any]:
    """Require the caller's selected triplet gate before accepting these rows."""
    def equal(check: str, offset: int, expected: Any, actual: Any) -> None:
        if expected != actual:
            raise EffectUpdateError("scalarHelper", check, offset, expected, actual)

    def digest(check: str, offset: int, raw: bytes, expected: str) -> None:
        equal(check, offset, expected, hashlib.sha256(raw).hexdigest())

    equal("scalarSchema", 0, "endfield.wwise-effect-scalar-native.v2", contract["schema"])
    equal("scalarReview", 0, "reviewedCurrentBuild", contract["status"])
    equal("scalarInputs", 0, native_inputs, contract["nativeInputs"])
    equal("scalarBoundary", 0, "conditional", contract["evidenceBoundary"])
    equal("scalarWholeFunctionClaim", 0, False, contract["wholeFunctionEquivalent"])
    method = contract["method"]
    start = int(method["rva"], 16)
    body = read(start, method["bodyLength"])
    equal("scalarBodyLength", 0, method["bodyLength"], len(body))
    digest("scalarBodyHash", 0, body, method["bodySha256"])
    regions = contract["codeCorrespondences"]
    if not isinstance(regions, list) or not regions:
        raise EffectUpdateError("scalarHelper", "scalarRegions", 0, "nonempty reviewed regions", regions)
    previous_end = 0
    previous_symbol_end = 0
    matched_bytes = 0
    rip_operands = set()
    for row in regions:
        at, size, source = row["nativeOffset"], row["byteLength"], row["symbolOffset"]
        if (any(type(v) is not int for v in (at, size, source)) or size <= 0
                or at < previous_end or at + size > len(body) or source < previous_symbol_end
                or source + size > contract["symbolWitness"]["symbolBodyLength"]):
            raise EffectUpdateError("scalarHelper", "scalarRegionExtent", at,
                                    "ordered nonoverlapping native and named-symbol spans", row)
        masked = bytearray(body[at:at + size])
        operand_end = 0
        for operand in row["relocatedOperands"]:
            offset, width, kind = operand["offset"], operand["width"], operand["kind"]
            if (type(offset) is not int or type(width) is not int or width not in (1, 4)
                    or offset < operand_end or offset + width > size
                    or kind not in ("ripRelative", "controlRelative")
                    or kind == "ripRelative" and width != 4):
                raise EffectUpdateError("scalarHelper", "scalarOperandExtent", at,
                                        "ordered bounded relative operands", operand)
            masked[offset:offset + width] = bytes(width)
            if kind == "ripRelative":
                rip_operands.add(at + offset)
            operand_end = offset + width
        digest("scalarNamedRegion", at, masked, row["normalizedSha256"])
        previous_end = at + size
        previous_symbol_end = source + size
        matched_bytes += size
    data = contract["dataCorrespondences"]
    if not isinstance(data, list) or not data:
        raise EffectUpdateError("scalarHelper", "scalarData", 0, "nonempty named data witnesses", data)
    for row in data:
        size = row["byteLength"]
        if type(size) is not int or not 0 < size <= 65536:
            raise EffectUpdateError("scalarHelper", "scalarDataExtent", 0, "bounded positive length", size)
        raw = read(int(row["rva"], 16), size)
        equal("scalarDataLength", 0, size, len(raw))
        digest("scalarNamedData", 0, raw, row["sha256"])
        reference = row["reference"]
        at, disp = reference["nativeBodyOffset"], reference["displacementOffset"]
        instruction = bytes.fromhex(reference["instructionHex"])
        equal("scalarReferenceExtent", at, True,
              0 <= at and 0 <= disp and disp + 4 <= len(instruction) <= 15 and at + len(instruction) <= len(body))
        equal("scalarReferenceInstruction", at, instruction, body[at:at + len(instruction)])
        equal("scalarReferenceOperand", at, True, at + disp in rip_operands)
        equal("scalarReferenceTarget", at, int(row["rva"], 16),
              start + at + len(instruction) + struct.unpack_from("<i", instruction, disp)[0])
    selector = contract["runtimeSelector"]
    at = selector["instructionBodyOffset"]
    instruction = bytes.fromhex(selector["instructionHex"])
    equal("scalarSelectorInstruction", at, instruction, body[at:at + len(instruction)])
    equal("scalarSelectorShape", at, b"\x83\x3d", instruction[:2])
    equal("scalarSelectorSize", at, 7, len(instruction))
    equal("scalarSelectorCell", at, int(selector["cellRva"], 16),
          start + at + len(instruction) + struct.unpack_from("<i", instruction, 2)[0])
    equal("scalarSelectorValue", at, selector["comparedValue"], instruction[-1])
    return {
        "status": "validated", "evidenceBoundary": "conditional",
        "symbol": contract["symbolWitness"]["symbol"], "methodRva": method["rva"],
        "scope": "partialNamedCodeAndDataCorrespondence", "wholeFunctionEquivalent": False,
        "matchedCodeBytes": matched_bytes, "dataWitnessCount": len(data),
        "runtimeBranchObserved": False, "meaningBoundary": contract["meaningBoundary"],
    }


def check_effect_scalar_native_inputs(game_root: Path) -> dict[str, Any]:
    """Focused audit using the same explicit selected-input gate as effect data."""
    from scripts.webui.audio.semantics.wwise_effect_native import check_effect_native_extension
    def validate(parent, base, read):
        contract = load_scalar_contract()
        target = int(contract["method"]["rva"], 16)
        callers = sorted(class_id for class_id, row in parent["parameterUpdates"].items()
                         if int(row["scalarHelperRva"], 16) == target)
        if not callers:
            raise EffectUpdateError("scalarHelper", "scalarCallerJoin", 0,
                                    "authenticated parameter-update caller", [])
        result = validate_scalar_correspondence(contract, parent["nativeInputs"], read)
        result["callingClassIds"] = callers
        return result

    return check_effect_native_extension(game_root, evidence_key="correspondence", validate=validate)
