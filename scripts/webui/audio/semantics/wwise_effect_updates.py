"""Prove bounded anonymous effect update routes on an already gated image.

This is a byte-pattern validator, not an x64 emulator. It accepts only the
reviewed signed-selector/two-table dispatcher and three complete handler
shapes. Constants and addresses come from the contract and selected PE.
No control names or mathematical identity are assigned to the scalar helper.
"""
from __future__ import annotations

import hashlib
import struct
from typing import Any, Callable


class EffectUpdateError(ValueError):
    def __init__(self, class_id: str, check: str, offset: int, expected: Any, actual: Any):
        self.diagnostic = {
            "validator": "wwise-effect-updates", "failedClassId": class_id,
            "failedCheck": check, "failedBodyOffset": offset,
            "expected": str(expected)[:160], "actual": str(actual)[:160],
        }
        super().__init__(f"{class_id} {check} at +{offset:#x}: expected {str(expected)[:160]}; actual {str(actual)[:160]}")


def validate_effect_update(
    class_id: str, schema: dict[str, Any], structural: dict[str, Any],
    registration: dict[str, Any], image_base: int,
    read: Callable[[int, int], bytes],
) -> dict[str, Any]:
    """Return derived routes only after all bytes, joins and paths agree."""
    method = schema["method"]
    start = int(method["rva"], 16)
    body = read(start, method["bodyLength"])

    def equal(check: str, offset: int, expected: Any, actual: Any) -> None:
        if expected != actual:
            raise EffectUpdateError(class_id, check, offset, expected, actual)

    equal("updateBodyHash", 0, method["bodySha256"], hashlib.sha256(body).hexdigest())
    equal("updateBoundary", 0, "direct", schema["evidenceBoundary"])
    equal("updateShape", 0, "signed16TwoTableScalarUpdatesV1", schema["shape"])
    slot = schema["vtableSlot"]
    equal("updateSlot", 0, 8, slot)
    equal("updateSlotTarget", 0, image_base + start,
          struct.unpack("<Q", read(int(registration["vtableRva"], 16) + slot, 8))[0])
    pos = 0

    def take(size: int) -> bytes:
        nonlocal pos
        value = body[pos:pos + size]
        equal("updateInstructionExtent", pos, size, len(value))
        pos += size
        return value

    def expect(encoded: str) -> None:
        at = pos
        raw = bytes.fromhex(encoded)
        equal("updateInstruction", at, raw.hex(), take(len(raw)).hex())

    def u32() -> int:
        return struct.unpack("<I", take(4))[0]

    def relative(width: int = 4) -> int:
        delta = int.from_bytes(take(width), "little", signed=True)
        return pos + delta

    def constant(opcode: str) -> dict[str, Any]:
        expect(opcode)
        rva = start + relative()
        raw = read(rva, 4)
        key = f"0x{rva:08x}"
        equal("updateConstant", pos - 4, schema["constants"].get(key), raw.hex())
        used_constants.add(key)
        return {"rawHex": raw.hex(), "float32": struct.unpack("<f", raw)[0]}

    def success() -> None:
        expect("b8")
        equal("updateSuccess", pos, schema["successReturnCode"], u32())
        expect("4883c4205bc3")

    used_constants: set[str] = set()
    expect("40534883ec20488bd94d85c075")
    nonnull = relative(1)
    expect("b8")
    null_result = u32()
    equal("updateNullResult", pos - 4, schema["nullReturnCode"], null_result)
    expect("4883c4205bc3")
    equal("updateNonnullBranch", pos, pos, nonnull)
    expect("480fbfc283f8")
    count = take(1)[0] + 1
    equal("updateSelectorCount", pos - 1, schema["selectorCount"], count)
    expect("0f87")
    default = relative()
    equal("updateDefaultTarget", pos - 4, schema["defaultHandlerOffset"], default)
    expect("488d15")
    equal("updateImageBase", pos, 0, start + relative())
    expect("0fb68402")
    selector_at = u32() - start
    equal("updateSelectorTable", pos - 4, schema["selectorTableBodyOffset"], selector_at)
    expect("8b8c82")
    target_at = u32() - start
    equal("updateTargetTable", pos - 4, schema["targetTableBodyOffset"], target_at)
    expect("4803caffe1")
    code_start = pos
    equal("updateTableBoundary", target_at, schema["codeByteLength"], target_at)
    equal("updateTargetTableEnd", target_at, selector_at, target_at + schema["targetCount"] * 4)
    equal("updateSelectorTableEnd", selector_at, len(body), selector_at + count)
    targets = [value - start for (value,) in struct.iter_unpack("<I", body[target_at:selector_at])]
    dispatch = []
    for selector in body[selector_at:]:
        if selector >= len(targets):
            raise EffectUpdateError(class_id, "updateTableIndex", selector_at, f"< {len(targets)}", selector)
        dispatch.append(targets[selector])
    cases = schema["cases"]
    expected_dispatch = [default] * count
    seen_ids: set[int] = set()
    for case in cases:
        selector = case["parameterId"]
        if type(selector) is not int or not 0 <= selector < count or selector in seen_ids:
            raise EffectUpdateError(class_id, "updateCaseId", 0, "unique in-range integer", selector)
        seen_ids.add(selector)
        expected_dispatch[selector] = case["handlerOffset"]
    equal("updateDispatch", selector_at, expected_dispatch, dispatch)
    equal("updateTargetSet", target_at, set(expected_dispatch), set(targets))

    bulk = structural["setParamsBlock"]
    bulk_body = read(int(bulk["rva"], 16), bulk["bodyLength"])
    equal("updateBulkBodyHash", 0, bulk["bodySha256"], hashlib.sha256(bulk_body).hexdigest())
    source_reads = {row["serializedOffset"]: row for row in structural["inputReads"]}
    routes = []
    end = code_start
    for case in sorted(cases, key=lambda row: row["handlerOffset"]):
        pos = case["handlerOffset"]
        equal("updateHandlerPartition", pos, end, pos)
        receiver = case["receiverOffset"]
        if type(receiver) is not int or not 0 <= receiver < 128:
            raise EffectUpdateError(class_id, "updateReceiverOffset", pos, "nonnegative disp8", receiver)
        disp = bytes([receiver]).hex()
        kind = case["kind"]
        row = {"parameterId": case["parameterId"], "serializedOffset": case["serializedOffset"],
               "receiverOffset": receiver, "kind": kind}
        if kind == "word32Copy":
            expect("418b008943" + disp)
        elif kind == "clampFloat32":
            expect("f3410f10000f57c90f2fc172")
            branch = relative(1)
            upper = constant("f30f5d05")
            expect("0f28c8")
            equal("updateClampBranch", pos, pos, branch)
            expect("f30f114b" + disp)
            row.update(lower={"rawHex": "00000000", "float32": 0.0}, upper=upper)
        elif kind == "clampThenScalarHelper":
            expect("f3410f1000")
            lower = constant("f30f100d")
            expect("0f2fc172")
            branch = relative(1)
            expect("0f28c8")
            if case["upperIsZero"]:
                expect("0f57c0f30f5dc8")
                upper = {"rawHex": "00000000", "float32": 0.0}
            else:
                upper = constant("f30f5d0d")
            equal("updateClampBranch", pos, pos, branch)
            scale = constant("f30f590d")
            first_arg = constant("f30f1005")
            expect("e8")
            helper = start + relative()
            equal("updateScalarHelper", pos - 4, int(schema["scalarHelperRva"], 16), helper)
            expect("f30f1143" + disp)
            row.update(lower=lower, upper=upper, scale=scale, helperFirstArgument=first_arg)
        else:
            raise EffectUpdateError(class_id, "updateHandlerKind", pos, "reviewed handler", kind)
        success()
        end = pos

        # The complete bulk body is independently hashed and its read partition
        # validated by the caller. Check the reviewed destination inside that
        # source read's bounded interval, not an offset coincidence elsewhere.
        source = source_reads[case["serializedOffset"]]
        equal("updateBulkReadWidth", source["bodyOffset"], 4, source["byteWidth"])
        store_at = case["bulkStoreBodyOffset"]
        store = bytes.fromhex(case["bulkStoreInstructionHex"])
        equal("updateBulkStoreBytes", store_at, store, bulk_body[store_at:store_at + len(store)])
        prefixes = {"word32Copy": ("8941", "8947"),
                    "clampFloat32": ("f30f1141", "f30f114f"),
                    "clampThenScalarHelper": ("f30f1147",)}[kind]
        expected_stores = [prefix + disp for prefix in prefixes]
        if store.hex() not in expected_stores:
            raise EffectUpdateError(class_id, "updateBulkDestination", store_at, expected_stores, store.hex())
        next_read = min((r["bodyOffset"] for r in source_reads.values() if r["bodyOffset"] > source["bodyOffset"]), default=len(bulk_body))
        if not source["bodyOffset"] < store_at < next_read:
            raise EffectUpdateError(class_id, "updateBulkStoreInterval", store_at,
                                    f"{source['bodyOffset']} < store < {next_read}", store_at)
        routes.append(row)
    # The final handler shares its successful epilogue with the default arm.
    pos = default
    success()
    equal("updateCodeEnd", pos, schema["codeByteLength"], pos)
    equal("updateHandlerEnd", end, pos, end)
    equal("updateConstantSet", 0, set(schema["constants"]), used_constants)
    return {"evidenceBoundary": "direct", "routes": sorted(routes, key=lambda row: row["parameterId"]),
            "nullReturnCode": null_result, "successReturnCode": schema["successReturnCode"],
            "unhandledSelectorBehavior": "successWithoutWrite", "selectorInterpretation": "signedLow16",
            "suppliedSizeChecked": False, "scalarHelperMeaning": "unresolved",
            "clampBoundary": "finite float32 inputs; no mathematical NaN or DSP claim"}
