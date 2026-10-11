"""Authenticate both instruction-order paths of Mastering's time helper.

The helper has partial named CRT expf correspondence. Its normal scalar and
FMA expressions are proved separately; neither that correspondence nor sampled
numerics establishes whole-library equivalence or a live CPU choice.
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
def load_mastering_time_contract():
    return json.loads((CONTRACTS_DIR / "wwise_mastering_time_native.json").read_text(encoding="utf-8"))


def _node(operation, *args):
    # Commutation preserves an operation; reassociation would erase rounding.
    if operation in {"add64", "mul64"}:args = tuple(sorted(args, key=repr))
    return (operation, *args)


def _expected_expression(fused):
    x = ("input32",); d = lambda name: ("data", name)
    s = _node("mul64", _node("to64", x), d("scale"))
    n = _node("roundInteger", s); j = _node("and", ("integer", 63), n)
    q = _node("sar", _node("subInteger", n, j), ("integer", 6))
    scale = _node("doubleBits", _node("shl", _node("addInteger", q, ("integer", 1023)), ("integer", 52)))
    r = (_node("fnmadd64", _node("to64Integer", n), d("step"), _node("to64", x)) if fused
         else _node("sub64", _node("to64", x), _node("mul64", d("step"), _node("to64Integer", n))))
    square = _node("mul64", r, r)
    if fused:
        polynomial = _node("fma64", square, _node("fma64", d("sixth"), r, d("half")), r)
        unscaled = _node("fma64", polynomial, _node("table", j), _node("table", j))
    else:
        polynomial = _node("add64", _node("mul64", square, _node("add64", _node("mul64", d("sixth"), r), d("half"))), r)
        unscaled = _node("add64", _node("mul64", polynomial, _node("table", j)), _node("table", j))
    return _node("to32", _node("mul64", unscaled, scale))


def _numeric_path(body, start, end, rva, data_addresses, table_address):
    """Bounded lower-lane decoder, with explicit SSE versus FMA rounding nodes."""
    xmm = {0: ("input32",)}; integer = {}; comparisons = []; table_register = False
    at = start
    def register(values, index):
        if index not in values:raise ValueError("undefined arithmetic register")
        return values[index]
    def raw(width):
        nonlocal at
        if at + width > end:raise ValueError("truncated arithmetic instruction")
        value = body[at:at+width]; at += width; return value
    for _ in range(128):
        if at == end:return register(xmm, 0), comparisons
        begin = at
        # The integer index/exponent operations are part of the numeric result.
        if body[at:at+3] == b"\x4c\x8d\x15":
            raw(3); target = rva + at + 4 + int.from_bytes(raw(4), "little", signed=True)
            if target != table_address:raise ValueError("unjoined lookup table")
            table_register = True; continue
        if body[at:at+3] == b"\x48\xc7\xc0":
            raw(3); integer[0] = ("integer", int.from_bytes(raw(4), "little", signed=True)); continue
        if body[at:at+2] in (b"\x23\xc1", b"\x2b\xc8"):
            opcode = raw(2)
            if opcode == b"\x23\xc1":integer[0] = _node("and", register(integer, 0), register(integer, 1))
            else:integer[1] = _node("subInteger", register(integer, 1), register(integer, 0))
            continue
        if body[at:at+2] == b"\xc1\xf9":
            raw(2); integer[1] = _node("sar", register(integer, 1), ("integer", raw(1)[0])); continue
        if body[at:at+3] == b"\x48\x81\xc1":
            raw(3); integer[1] = _node("addInteger", register(integer, 1), ("integer", int.from_bytes(raw(4), "little", signed=True))); continue
        if body[at:at+3] == b"\x48\xc1\xe1":
            raw(3); integer[1] = _node("shl", register(integer, 1), ("integer", raw(1)[0])); continue
        if body[at:at+2] == b"\x0f\x83" or body[at] == 0x72 or body[at:at+2] == b"\x0f\x82":
            long = body[at] == 0x0f; opcode = raw(2 if long else 1); width = 4 if long else 1
            target = at + width + int.from_bytes(raw(width), "little", signed=True)
            if not comparisons or len(comparisons[-1]) != 3:raise ValueError("unpaired range branch")
            comparisons[-1] += ("jae" if opcode == b"\x0f\x83" else "jb", target)
            continue
        pp = 0; rex = 0; mapping = 1; source1 = None; vex = False
        if body[at] in (0xc4, 0xc5):
            vex = True; prefix = raw(1)[0]
            if prefix == 0xc5:
                v = raw(1)[0]; rex = ((~v >> 7) & 1) << 2
            else:
                v1, v = raw(2); mapping = v1 & 31
                rex = (((~v1 >> 7) & 1) << 2) | ((~v1 >> 5) & 1) | ((v >> 4) & 8)
            pp = v & 3; source1 = (~v >> 3) & 15
            if v & 4:raise ValueError("unproved vector width")
        else:
            if body[at] in (0x66, 0xf3, 0xf2):pp = {0x66: 1, 0xf3: 2, 0xf2: 3}[raw(1)[0]]
            if 0x40 <= body[at] <= 0x4f:rex = raw(1)[0] & 15
            if raw(1) != b"\x0f":raise ValueError(f"unsupported arithmetic instruction +{begin:#x}")
        opcode, modrm = raw(2); destination = ((modrm >> 3) & 7) | ((rex & 4) << 1)
        source = (modrm & 7) | ((rex & 1) << 3); mode = modrm >> 6
        if mode == 3:
            # MOVD/MOVQ into XMM reads the integer register, not an XMM source.
            operand = register(integer if opcode == 0x6e else xmm, source)
        elif mode == 0 and source == 5:
            target = rva + at + 4 + int.from_bytes(raw(4), "little", signed=True)
            if target not in data_addresses:raise ValueError("unjoined arithmetic constant")
            operand = ("data", data_addresses[target])
        elif mode == 0 and source & 7 == 4 and raw(1) == b"\xc2" and table_register:
            operand = _node("table", register(integer, 0))
        else:raise ValueError("unsupported arithmetic memory operand")
        previous = register(xmm, source1) if source1 is not None and opcode in (0x59, 0x58, 0x5c, 0xa9, 0xbd) else xmm.get(destination)
        if mapping == 2 and pp == 1 and opcode in (0xa9, 0xbd):
            if previous is None:raise ValueError("undefined fused destination")
            old = register(xmm, destination)
            xmm[destination] = (_node("fma64", old, previous, operand) if opcode == 0xa9
                                else _node("fnmadd64", previous, operand, old))
        elif mapping != 1:raise ValueError("unsupported opcode map")
        elif opcode == 0x5a and pp in (2, 3):xmm[destination] = _node("to64" if pp == 2 else "to32", operand)
        elif opcode == 0xe6 and pp in (2, 3):xmm[destination] = _node("to64Integer" if pp == 2 else "roundInteger", operand)
        elif opcode in (0x28, 0x10) and pp in (1, 3):xmm[destination] = operand
        elif opcode == 0x7e and pp == 1 and mode == 3:integer[source] = register(xmm, destination)
        elif opcode == 0x6e and pp == 1 and mode == 3 and rex & 8:xmm[destination] = _node("doubleBits", operand)
        elif opcode in (0x59, 0x58, 0x5c) and pp in (1, 3):
            if previous is None:raise ValueError("undefined scalar destination")
            xmm[destination] = _node({0x59: "mul64", 0x58: "add64", 0x5c: "sub64"}[opcode], previous, operand)
        elif opcode in (0x2e, 0x2f) and pp == 1:comparisons.append(("ucomisd" if opcode == 0x2e else "comisd", register(xmm, destination), operand))
        else:raise ValueError(f"unsupported scalar opcode +{begin:#x}")
    raise ValueError("arithmetic instruction bound exceeded")


def validate_mastering_time(contract, native_inputs, dynamics_contract, dynamics, scalar_contract, scalar, read):
    def equal(check, expected, actual, offset=0):
        if expected != actual:raise EffectUpdateError("masteringTime", check, offset, expected, actual)
    equal("schema", "endfield.wwise-mastering-time-native-contract.v1", contract["schema"])
    equal("reviewStatus", "reviewed", contract["status"]); equal("boundary", "conditional", contract["evidenceBoundary"])
    for name, source in (("self", contract), ("dynamics", dynamics_contract), ("scalar", scalar_contract)):
        equal("inputs:"+name, native_inputs, source["nativeInputs"])
    for name, proof in (("dynamics", dynamics), ("scalar", scalar)):equal("parentProof:"+name, "validated", proof["status"])
    equal("parentHelper", "coefficientHelper", contract["dynamicsHelper"])
    rva = int(dynamics_contract["externals"][contract["dynamicsHelper"]]["rva"], 16)
    rows = dict(helper=contract["method"], special=contract["specialHandler"]); bodies = {}; rvas = dict(helper=rva, special=int(rows["special"]["rva"], 16))
    for name, row in rows.items():
        size = row["bodyLength"]; equal("extent:"+name, True, type(size) is int and 0 < size <= 4096)
        bodies[name] = read(rvas[name], size); equal("length:"+name, size, len(bodies[name]))
        equal("hash:"+name, row["bodySha256"], hashlib.sha256(bodies[name]).hexdigest())
    body = bodies["helper"]
    equal("tableSymbol", "__two_to_jby64_table", contract["scalarTableSymbol"])
    table_matches = [row for row in scalar_contract["dataCorrespondences"] if row["symbol"] == contract["scalarTableSymbol"]]
    equal("tableJoinCount", 1, len(table_matches)); scalar_table = table_matches[0]
    equal("tableExtent", 512, scalar_table["byteLength"]); table = int(scalar_table["rva"], 16)
    values = dict(infinity=struct.pack("<I", 0x7f800000)+bytes(12), scale=struct.pack("<d", 64 / 0.6931471805599453)+bytes(8),
        upper=struct.pack("<d", 8192.)+bytes(8), lower=struct.pack("<d", -9600.)+bytes(8),
        step=struct.pack("<d", 0.6931471805599453/64)+bytes(8), sixth=struct.pack("<d", 1/6)+bytes(8), half=struct.pack("<d", .5)+bytes(8),
        negativeInfinity=struct.pack("<I", 0xff800000), quietBit=struct.pack("<I", 0x400000), nanFlag=struct.pack("<I", 1),
        zeroFlag=struct.pack("<I", 2), infinityFlag=struct.pack("<I", 3), name=b"expf\0")
    equal("dataRoles", set(values), set(contract["data"]))
    addresses = {name: int(row["rva"], 16) for name, row in contract["data"].items()}
    for name, expected in values.items():
        equal("dataExtent:"+name, len(expected), contract["data"][name]["byteLength"])
        equal("dataValue:"+name, expected, read(addresses[name], len(expected)))
    selector = int(scalar_contract["runtimeSelector"]["cellRva"], 16)
    targets = dict(data=addresses, method=rvas, runtime=dict(selector=selector), table=dict(table=table),
                   external={name: int(value, 16) for name, value in contract["externals"].items()})
    for name, row in rows.items():
        for reference in row["references"]:
            at = reference["offset"]; prefix = bytes.fromhex(reference["prefixHex"]); suffix = bytes.fromhex(reference["suffixHex"])
            end = at + len(prefix) + 4 + len(suffix); raw = bodies[name][at:end]
            equal("referenceOpcode:"+name, prefix, raw[:len(prefix)], at); equal("referenceSuffix:"+name, suffix, raw[len(prefix)+4:], at)
            equal("referenceJoin:"+name, targets[reference["targetKind"]][reference["target"]],
                  rvas[name]+end+int.from_bytes(raw[len(prefix):len(prefix)+4], "little", signed=True), at)
    paths = contract["paths"]; equal("paths", {"scalar", "fma"}, set(paths))
    for name, path in paths.items():
        try:expression, comparisons = _numeric_path(body, path["start"], path["end"], rva, {v:k for k,v in addresses.items()}, table)
        except (ValueError, IndexError) as error:raise EffectUpdateError("masteringTime", "numericPath:"+name, path["start"], "complete admitted numeric path", str(error)) from error
        expected_expression = _expected_expression(name == "fma")
        if expected_expression != expression:
            def difference(left, right, path):
                if isinstance(left, tuple) and isinstance(right, tuple) and len(left) == len(right):
                    for j, (a, b) in enumerate(zip(left, right)):
                        if a != b:return difference(a, b, path+f"/{j}")
                return path, left, right
            detail, expected, actual = difference(expected_expression, expression, name)
            equal("expression:"+detail, expected, actual, path["start"])
        scaled = _node("mul64", _node("to64", ("input32",)), ("data", "scale"))
        expected = [("comisd", scaled, ("data", "upper"), "jae", path["overflow"]),
                    ("ucomisd" if name == "fma" else "comisd", scaled, ("data", "lower"), "jb", path["underflow"])]
        equal("rangePredicates:"+name, expected, comparisons, path["start"])
    # Independent control/ABI obligations use declarations only for locations.
    grammar = dict(frame="4883ec38", selector="833d", scalarAbsolute="660f7ec20fbaf21f", fmaAbsolute="c5f97ec20fbaf21f",
        scalarUnderflowSeed="0f57c9660f6ec2", fmaUnderflowSeed="c5f057c9c5f96ec2", scalarOverflowArgument="660f6ec2",
        fmaOverflowArgument="c5f96ec2", scalarQuietCandidate="660f6eca", fmaQuietCandidate="c5f96eca",
        zeroReturn="0f57c04883c438c3", unchangedReturn="4883c438c3",
        scalarSpecialInput="660f7ec2", fmaSpecialInput="c5f97ec2",
        specialSave="0f2970e80f28f10f28d04183e802", specialFlags="742b4183f801757d", specialReturn="0f28c60f287424504883c468c3")
    equal("controlRoles", set(grammar), set(contract["controlOffsets"]))
    for name, expected in grammar.items():
        row = contract["controlOffsets"][name]; raw = bytes.fromhex(expected)
        equal("control:"+name, raw, bodies[row["method"]][row["offset"]:row["offset"]+len(raw)], row["offset"])
    for branch in contract["branches"]:
        at = branch["offset"]; opcode = bytes.fromhex(branch["opcodeHex"]); width = branch["width"]
        equal("branchWidth", True, width in (1, 4)); equal("branchOpcode", opcode, body[at:at+len(opcode)], at)
        end = at+len(opcode)+width; target = end+int.from_bytes(body[at+len(opcode):end], "little", signed=True)
        equal("branchTarget", branch["targetOffset"], target, at)
    edges = contract["classificationEdges"]
    equal("classificationRoles", {"selector", "scalarSpecial", "fmaSpecial", "scalarPositiveInfinity", "scalarNegativeInfinity", "fmaPositiveInfinity", "fmaNegativeInfinity"}, set(edges))
    edge_targets = dict(selector="fmaAbsolute", scalarSpecial="scalarSpecialInput", fmaSpecial="fmaSpecialInput",
                        scalarPositiveInfinity="unchangedReturn", scalarNegativeInfinity="zeroReturn",
                        fmaPositiveInfinity="unchangedReturn", fmaNegativeInfinity="zeroReturn")
    for name, row in edges.items():
        equal("classificationRole:"+name, edge_targets[name], row["targetRole"])
        at = row["offset"]; long = body[at] == 0x0f; width = 4 if long else 1
        opcode = body[at:at+(2 if long else 1)]
        expected = b"\x0f\x85" if name == "selector" else b"\x0f\x8d" if name.endswith("Special") else b"\x0f\x84" if long else b"\x74"
        equal("classificationPredicate:"+name, expected, opcode, at)
        end = at+len(opcode)+width
        equal("classificationTarget:"+name, contract["controlOffsets"][row["targetRole"]]["offset"],
              end+int.from_bytes(body[at+len(opcode):end], "little", signed=True), at)
    # Outside the numeric decoder, these independent opcodes establish candidate
    # construction and comparison. The declarations cannot rename an arithmetic
    # load into a NaN quieting operation or omit the classifier's data operands.
    candidate_references = []
    for row in contract["method"]["references"]:
        if row["targetKind"] == "runtime":
            equal("selectorCompare", ("selector", "833d", "00"), (row["target"], row["prefixHex"], row["suffixHex"]), row["offset"])
        if row["targetKind"] != "data":continue
        role = row["target"]; prefix = bytes.fromhex(row["prefixHex"])
        if role in {"zeroFlag", "infinityFlag", "nanFlag"}:equal("candidateFlagLoad", b"\x44\x8b\x05", prefix, row["offset"])
        elif role == "negativeInfinity":equal("negativeInfinityCompare", b"\x3b\x15", prefix, row["offset"])
        elif role == "quietBit":equal("nanQuietOperation", b"\x0b\x15", prefix, row["offset"])
        elif role == "infinity":equal("infinityOpcode", True, prefix in (b"\x3b\x15", b"\x0f\x28\x0d", b"\xc5\xf8\x28\x0d"), row["offset"])
        else:continue
        candidate_references.append(role)
    equal("candidateReferenceSet", sorted(["infinity"]*6+["negativeInfinity", "quietBit", "zeroFlag", "infinityFlag", "nanFlag"]*2), sorted(candidate_references))
    witness = contract["symbolWitness"]
    equal("symbol", "expf", witness["symbol"]); equal("wholeFunctionClaim", False, contract["wholeFunctionEquivalent"])
    equal("namedSymbols", {"expf", "expf_sse2"}, {row["symbol"] for row in witness["symbols"]})
    equal("namedRegions", True, 0 < len(witness["regions"]) <= 128)
    symbol_sizes = {row["symbol"]:row["bodyLength"] for row in witness["symbols"]}; matched = 0; previous_end = 0
    for row in witness["regions"]:
        start, size, source = row["nativeOffset"], row["byteLength"], row["symbolOffset"]
        equal("namedRegionBounds", True, all(type(v) is int for v in (start,size,source)) and size > 0 and previous_end <= start <= len(body)-size
              and row["symbol"] in symbol_sizes and 0 <= source <= symbol_sizes[row["symbol"]]-size)
        raw = bytearray(body[row["nativeOffset"]:row["nativeOffset"]+row["byteLength"]])
        equal("namedExtent", row["byteLength"], len(raw))
        for operand in row["relativeOperands"]:
            at, width = operand; equal("namedOperand", True, width in (1, 4) and 0 <= at <= len(raw)-width)
            raw[at:at+width] = bytes(width)
        equal("namedRegion", row["normalizedSha256"], hashlib.sha256(raw).hexdigest(), row["nativeOffset"]); matched += len(raw)
        previous_end = start+size
    equal("arithmeticDeclaration", dict(index="round-MXCSR(x*scale)", tableIndex="n & 63", exponent="(n-tableIndex)>>6", polynomial="r + r*r*(half+sixth*r)",
        ordinaryDomain="finite input; lower <= x*scale < upper", output="float32((table[index]*(1+polynomial))*2**exponent)",
        rounding="per-instruction binary64, then binary32; FMA has one rounding per fused operation"), contract["arithmetic"])
    return dict(status="validated", evidenceBoundary="conditional", methodRva=hex(rva), numericPaths=["scalar", "fma"],
        numericExpressionsProven=True, partialNamedExpfCorrespondence=True, wholeFunctionEquivalent=False, matchedNamedCodeBytes=matched,
        sharedPowerHelperSelectorProven=True, sharedPowerHelperTableProven=True, specialCandidatePreserved=True,
        nanCandidateBypassesExternalError=True,
        specialErrorSideEffectsProven=False, runtimeCpuPathObserved=False, arbitraryInputMathEquivalenceProven=False, meaningBoundary=contract["meaningBoundary"])


def check_mastering_time_native_inputs(game_root: Path):
    from scripts.webui.audio.semantics.wwise_effect_native import check_effect_native_extension
    from scripts.webui.audio.semantics.wwise_mastering_dynamics import load_mastering_dynamics_contract, validate_mastering_dynamics_effect_context
    from scripts.webui.audio.semantics.wwise_effect_scalar import load_scalar_contract, validate_scalar_correspondence
    def validate(parent, base, read):
        dynamics = validate_mastering_dynamics_effect_context(parent, base, read)
        scalar_contract = load_scalar_contract(); scalar = validate_scalar_correspondence(scalar_contract, parent["nativeInputs"], read)
        return validate_mastering_time(load_mastering_time_contract(), parent["nativeInputs"], load_mastering_dynamics_contract(), dynamics, scalar_contract, scalar, read)
    return check_effect_native_extension(game_root, evidence_key="time", validate=validate)
