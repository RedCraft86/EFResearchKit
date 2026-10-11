"""Prove all numeric coefficient cases using their native scalar expressions.

Helpers are opaque return values. Expression trees retain every Single operation
and its rounding boundary; similarities to named response formulas are not used
as identification evidence. The parent owns complete generator byte coverage.
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
def load_mastering_coefficients_contract():
    return json.loads((CONTRACTS_DIR / "wwise_mastering_coefficients_native.json").read_text(encoding="utf-8"))


def _constant(value):
    return ("constant", struct.pack("<f", value).hex())


def _operation(kind, *args):
    if kind in ("add", "mul"):
        args = tuple(sorted(args, key=repr))
    return (kind, *args)


def _expected_raw(kind, quality_high=False, root_skip=False):
    """Native operation order; no algebraic reassociation or helper substitution."""
    F, Q, G, S, C = [("input", k) for k in ("F", "Q", "G", "S", "C")]
    zero, one, half, negative_half, negative_two = map(_constant, (0., 1., .5, -.5, -2.))
    add = lambda a, b: _operation("add", a, b)
    sub = lambda a, b: _operation("sub", a, b)
    mul = lambda a, b: _operation("mul", a, b)
    div = lambda a, b: _operation("div", a, b)
    sqrt = lambda a: _operation("sqrt", a)
    neg = lambda a: _operation("neg", a)
    helper = lambda a, b: _operation("helper", a, b)
    alpha = mul(div(half, Q), S); minus_two_c = mul(C, negative_two)
    denominator = [add(alpha, one), minus_two_c, sub(one, alpha)]
    if kind == 0:return [zero] * 6
    if kind in (1, 2, 12):
        value = sub(one, C) if kind != 2 else add(one, C)
        b0 = mul(value, half); b1 = value if kind != 2 else neg(value)
        if kind == 12:
            scale = sqrt(div(_constant(.7), Q)) if quality_high else one
            b0 = mul(b0, scale); b1 = mul(b1, scale)
        return denominator + [b0, b1, b0]
    if kind in (3, 8):
        H = helper(_constant(10.), mul(G, _constant(.05))); R = sqrt(H)
        v = alpha if kind == 3 else mul(S, half)
        a = v if root_skip else div(v, R)
        b0 = add(mul(R, alpha), one) if kind == 3 else mul(mul(S, half), R)
        b2 = sub(one, mul(R, alpha)) if kind == 3 else mul(mul(S, negative_half), R)
        return [add(a, one), minus_two_c, sub(one, a), b0, minus_two_c if kind == 3 else zero, b2]
    if kind in (4, 5):
        H = helper(_constant(10.), mul(G, _constant(.025))); U = add(H, one); D = sub(H, one)
        DC = mul(D, C); UC = mul(U, C); T = mul(mul(sqrt(H), S), _constant(2**.5))
        if kind == 4:
            left = add(DC, U); right = sub(U, DC)
            return [add(right, T), add(sub(D, UC), sub(D, UC)), sub(right, T),
                    mul(add(left, T), H), mul(mul(add(UC, D), H), negative_two), mul(sub(left, T), H)]
        left = sub(U, DC); right = add(U, DC)
        return [add(right, T), sub(mul(D, negative_two), add(UC, UC)), sub(right, T),
                mul(add(left, T), H), mul(add(H, H), sub(D, UC)), mul(sub(left, T), H)]
    if kind in (6, 7):
        H = helper(_constant(2.718280076980591), mul(F, _constant(-6.2831854820251465)))
        return [one, neg(H), zero, sub(one, H) if kind == 6 else add(mul(H, half), half),
                zero if kind == 6 else sub(negative_half, mul(H, half)), zero]
    if kind == 9:return denominator + [alpha, zero, neg(alpha)]
    if kind == 10:return denominator + [one, minus_two_c, one]
    if kind == 11:return denominator + [sub(one, alpha), minus_two_c, add(alpha, one)]
    raise ValueError("coefficient type outside admitted numeric cases")


def _scalar_program(body, start, rva, constants, helper_rva, *, quality_high=False, root_skip=False):
    """Decode the whole selected case through all six stores; unsupported bytes fail."""
    F, Q, G, S, C = [("input", k) for k in ("F", "Q", "G", "S", "C")]
    half = _constant(.5); unknown = ("unknown",)
    registers = {j: unknown for j in range(16)}
    registers.update({1: Q, 6: G, 7: S, 8: F, 10: C, 11: _operation("mul", _operation("div", half, Q), S), 12: half})
    output = {}; at = start; condition = None; visited = set(); helper_arguments = []
    for _ in range(256):
        if not 0 <= at < len(body):raise ValueError("coefficient arithmetic leaves the body")
        if at in visited:raise ValueError("coefficient arithmetic repeats a byte offset")
        visited.add(at)
        if len(output) == 6 and body[at:at+2] == b"\xeb\x05":
            return [output[j] for j in range(0, 24, 4)], helper_arguments, sorted(visited)
        if body[at:at+2] == b"\x33\xc0":at += 2; continue
        opcode = body[at]
        if opcode in (0xe9, 0xeb, 0x74, 0x76):
            width = 4 if opcode == 0xe9 else 1; end = at + 1 + width
            if end > len(body):raise ValueError("coefficient truncated branch")
            target = end + int.from_bytes(body[at+1:end], "little", signed=True)
            if opcode in (0xe9, 0xeb):at = target; continue
            if opcode == 0x74:
                if condition != "positive-helper-root-vs-zero":raise ValueError("coefficient unexpected equality branch")
                at = target if root_skip else end
            else:
                if condition != "quality-vs-threshold":raise ValueError("coefficient unexpected below/equal branch")
                at = end if quality_high else target
            continue
        if opcode == 0xe8:
            end = at + 5
            if end > len(body):raise ValueError("coefficient truncated call")
            target = rva + end + int.from_bytes(body[at+1:end], "little", signed=True)
            if target != helper_rva:raise ValueError("coefficient unexpected helper target")
            if unknown in (registers[0], registers[1]):raise ValueError("coefficient undefined helper argument")
            expression = _operation("helper", registers[0], registers[1]); helper_arguments.append(expression)
            for j in range(6):registers[j] = unknown
            registers[0] = expression; at = end; continue
        cursor = at; scalar = body[cursor] == 0xf3
        if scalar:cursor += 1
        if cursor >= len(body):raise ValueError("coefficient truncated prefix")
        rex = 0
        if 0x40 <= body[cursor] <= 0x4f:rex = body[cursor]; cursor += 1
        if cursor + 3 > len(body):raise ValueError("coefficient truncated SSE")
        if body[cursor] != 0x0f:raise ValueError(f"coefficient unsupported instruction at +{at:#x}")
        op = body[cursor+1]; modrm = body[cursor+2]; cursor += 3
        destination = ((modrm >> 3) & 7) | ((rex & 4) << 1)
        source = (modrm & 7) | ((rex & 1) << 3); mode = modrm >> 6
        if mode == 3:
            operand = registers[source]
        elif mode == 0 and source == 5:
            end = cursor + 4
            if end > len(body):raise ValueError("coefficient truncated RIP operand")
            address = rva + end + int.from_bytes(body[cursor:end], "little", signed=True)
            if address not in constants:raise ValueError("coefficient unjoined scalar constant")
            operand = constants[address]; cursor = end
        elif scalar and op == 0x11 and source == 3 and mode in (0, 1):
            displacement = 0
            if mode == 1:
                if cursor >= len(body):raise ValueError("coefficient truncated store operand")
                displacement = int.from_bytes(body[cursor:cursor+1], "little", signed=True); cursor += 1
            if displacement not in range(0, 24, 4) or displacement in output:raise ValueError("coefficient duplicate/out-of-range store")
            if registers[destination] == unknown:raise ValueError("coefficient undefined store")
            output[displacement] = registers[destination]; at = cursor; continue
        else:raise ValueError("coefficient unsupported memory operand")
        previous = registers[destination]
        if not scalar and op == 0x28 and mode == 3:registers[destination] = operand
        elif scalar and op == 0x10:registers[destination] = operand
        elif not scalar and op == 0x57:
            if mode == 3 and destination == source:registers[destination] = _constant(0.)
            elif operand == ("signMask",):registers[destination] = _operation("neg", previous)
            else:raise ValueError("coefficient unsupported XOR")
        elif scalar and op in (0x58, 0x5c, 0x59, 0x5e, 0x51):
            if operand == unknown or op != 0x51 and previous == unknown:raise ValueError("coefficient undefined arithmetic input")
            operation = {0x58: "add", 0x5c: "sub", 0x59: "mul", 0x5e: "div", 0x51: "sqrt"}[op]
            registers[destination] = _operation(operation, operand) if op == 0x51 else _operation(operation, previous, operand)
        elif not scalar and op in (0x2e, 0x2f):
            if op == 0x2f and previous == Q and operand == _constant(.7):condition = "quality-vs-threshold"
            elif op == 0x2e and previous[0] == "sqrt" and previous[1][0] == "helper" and operand == _constant(0.):condition = "positive-helper-root-vs-zero"
            else:raise ValueError("coefficient unproved comparison inputs")
        else:raise ValueError(f"coefficient unsupported SSE operation at +{at:#x}")
        at = cursor
    raise ValueError("coefficient arithmetic exceeds instruction bound")


def validate_mastering_coefficients(contract, native_inputs, dynamics_contract, dynamics, read):
    def equal(check, expected, actual, offset=0):
        if expected != actual:raise EffectUpdateError("masteringCoefficients", check, offset, expected, actual)

    equal("schema", "endfield.wwise-mastering-coefficients-native-contract.v3", contract["schema"])
    equal("reviewStatus", "reviewed", contract["status"]); equal("boundary", "conditional", contract["evidenceBoundary"])
    equal("inputs", native_inputs, contract["nativeInputs"]); equal("parentInputs", native_inputs, dynamics_contract["nativeInputs"])
    equal("parentProof", "validated", dynamics["status"])
    equal("generatorMethod", "filterCoefficients", contract["generatorMethod"]); equal("tableData", "coefficientTable", contract["tableData"])
    row = dynamics_contract["methods"][contract["generatorMethod"]]; rva = int(row["rva"], 16)
    equal("extent", True, type(row["bodyLength"]) is int and 0 < row["bodyLength"] <= 4096)
    body = read(rva, row["bodyLength"]); equal("hash", row["bodySha256"], hashlib.sha256(body).hexdigest())
    common = contract["commonOffsets"]
    windows = dict(frame="488bc448895808574881ec90000000", angleArgument="0f28ca", retainKindAndOutput="8bfa488bd9",
                   retainGain="0f28f3", retainFrequency="440f28c2", angleToCallArgument="f30f10c1",
                   helperSeedAndTypeGuard="0f28f8f30f108c24c0000000450f28dc440f28d0440fc6d001f3440f5ed9f3440f59df83ff0c0f874b040000",
                   invalidError="b802022680")
    equal("commonRoles", set(windows) | {"angleMultiply", "packedHelperCall", "halfLoad"}, set(common))
    def block(role, encoded):
        offset = common[role]
        equal("commonOffset", True, type(offset) is int and 0 <= offset < len(body))
        raw = bytes.fromhex(encoded); equal("commonArithmetic", raw, body[offset:offset+len(raw)], offset)
    for role, raw in windows.items():block(role, raw)
    data = dynamics_contract["data"]; table_row = data[contract["tableData"]]
    table = struct.unpack("<13I", read(int(table_row["rva"], 16), 52))
    offsets = contract["entryOffsets"]
    equal("entries", True, len(offsets) == 13 and all(type(v) is int and 0 <= v < len(body) for v in offsets))
    equal("tableRoutes", [rva+v for v in offsets], list(table))
    for role, prefix, target in (("angleMultiply", "f30f590d", int(data["angleScale"]["rva"], 16)),
                                ("halfLoad", "f3440f1025", int(data["scalarHalf"]["rva"], 16)),
                                ("packedHelperCall", "e8", int(dynamics_contract["externals"]["packedTrigonometricHelper"]["rva"], 16))):
        block(role, prefix); at = common[role]; size = len(bytes.fromhex(prefix)) + 4
        equal("commonRelativeJoin", target, rva + at + size + int.from_bytes(body[at+size-4:at+size], "little", signed=True), at)
    values = dict(scalarUnity=1., controlScale=.05, controlBase=10., scalarHalf=.5, angleScale=6.2831854820251465,
        negativeAngleScale=-6.2831854820251465, approximateEulerBase=2.718280076980591, negativeHalf=-.5,
        negativeTwo=-2., quarterControlScale=.025, sqrtTwo=2**.5, coefficientThreshold=.7)
    equal("dataRoles", set(values) | {"signMask"}, set(contract["dataRoles"]))
    constants = {}
    for name in contract["dataRoles"]:
        d = data[name]; address = int(d["rva"], 16)
        expected = bytes.fromhex("00000080"*4) if name == "signMask" else struct.pack("<f", values[name])
        equal("constant:" + name, expected, read(address, len(expected)))
        constants[address] = ("signMask",) if name == "signMask" else ("constant", expected.hex())
    helper_rva = int(dynamics_contract["externals"]["powerHelper"]["rva"], 16)
    paths = []
    for kind, start in enumerate(offsets):
        choices = [(False, False), (False, True)] if kind in (3, 8) else [(False, False), (True, False)] if kind == 12 else [(False, False)]
        for quality_high, root_skip in choices:
            try:actual, helpers, covered = _scalar_program(body, start, rva, constants, helper_rva, quality_high=quality_high, root_skip=root_skip)
            except ValueError as error:raise EffectUpdateError("masteringCoefficients", "scalarProgram", start, "complete admitted arithmetic", str(error)) from error
            expected = _expected_raw(kind, quality_high, root_skip)
            if expected != actual:
                def first_difference(a, b, path):
                    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)) and len(a) == len(b):
                        for j, (left, right) in enumerate(zip(a, b)):
                            if left != right:return first_difference(left, right, path + f"/{j}")
                    return path, a, b
                path, left, right = first_difference(expected, actual, f"type{kind}:qualityHigh={quality_high}:rootSkip={root_skip}")
                equal("coefficientExpressions:" + path, left, right, start)
            paths.append(dict(numericType=kind, qualityAboveThreshold=quality_high if kind == 12 else None,
                              helperRootZeroOrUnordered=root_skip if kind in (3, 8) else None,
                              helperArguments=helpers, instructionOffsets=covered, expressionOrder=["a0", "a1", "a2", "b0", "b1", "b2"]))
    equal("inputsDeclaration", dict(frequency="normalized cutoff", quality="Q", gain="raw gain argument",
        packedHelper="opaque lane 0 S and lane 1 C", alpha="float32(float32(0.5/Q)*S)"), contract["inputs"])
    equal("output", dict(rawOrder=["a0", "a1", "a2", "b0", "b1", "b2"], storedByWrapper=["a0", "-a1/a0", "-a2/a0", "b0/a0", "b1/a0", "b2/a0"],
        zeroType="six zero raw coefficients; the wrapper skips generation for type zero",
        invalidType="unsigned type >12 returns error without coefficient stores"), contract["output"])
    equal("arithmetic", dict(rounding="float32 after each scalar operation", helper="opaque power-helper call result with exact base/exponent arguments",
        firstOrderBase=2.718280076980591, firstOrderExponentScale=-6.2831854820251465, qualityThreshold=0.699999988079071,
        qualityUpperScale="sqrt(float32(qualityThreshold/Q))", qualityLowerScale=1.,
        admittedHelperResult="positive finite results have ordinary numerical arithmetic; zero/unordered roots have separate skip-division expression paths",
        helperRootSkipPredicate="UCOMISS square-root result,+0; ZF=1 skips division for zero or unordered if the comparison completes"), contract["arithmetic"])
    return dict(status="validated", evidenceBoundary="conditional", numericTypes=list(range(13)), arithmeticPaths=paths,
                allNumericGeneratorArithmeticProven=True, rawZeroTypeIsNotIdentity=True, unsignedInvalidTypesDoNotStoreCoefficients=True,
                firstOrderPowerBase=values["approximateEulerBase"], exactEulerSubstitutionValid=False,
                qualityThreshold=struct.unpack("<f", struct.pack("<f", .7))[0], helperReturnMeaningProven=False,
                helperRootZeroOrUnorderedBranchProven=True, helperExceptionalNumericBehaviorProven=False,
                publicFilterNamesProven=False, runtimeInvocationObserved=False,
                meaningBoundary=contract["meaningBoundary"])


def check_mastering_coefficients_native_inputs(game_root: Path):
    from scripts.webui.audio.semantics.wwise_effect_native import check_effect_native_extension
    from scripts.webui.audio.semantics.wwise_mastering_dynamics import load_mastering_dynamics_contract, validate_mastering_dynamics_effect_context

    def validate(parent, base, read):
        dynamics = validate_mastering_dynamics_effect_context(parent, base, read)
        return validate_mastering_coefficients(load_mastering_coefficients_contract(), parent["nativeInputs"], load_mastering_dynamics_contract(), dynamics, read)

    return check_effect_native_extension(game_root, evidence_key="coefficients", validate=validate)
