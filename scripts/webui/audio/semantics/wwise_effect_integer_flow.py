"""Bounded symbolic integer flow for reviewed straight-line effect loaders.

The admitted x64 subset is intentionally small: integer moves/bit operations,
byte zero comparisons, conditional moves, setcc, pointer LEA and raw movss
transfers. Unsupported instructions or addressing fail closed. A canonical
Boolean decision graph keeps input byte zero-tests and every copied word bit
symbolic; no sampled value, floating interpretation or public control name is
introduced. Callers authenticate the selected method bytes and field contract.
"""
from __future__ import annotations

from dataclasses import dataclass


class IntegerFlowError(ValueError):
    def __init__(self, offset, detail):
        self.offset = offset
        super().__init__(f"effect integer flow at +{offset:#x}: {detail}")


class BooleanGraph:
    """Reduced ordered Boolean decision graph with deterministic variable order."""
    def __init__(self):
        self.nodes = [None, None]
        self.unique = {}
        self.variables = {}
        self.inverse_cache = {}
        self.operation_cache = {}

    def node(self, variable, low, high):
        if low == high:
            return low
        key = (variable, low, high)
        if key not in self.unique:
            self.unique[key] = len(self.nodes)
            self.nodes.append(key)
        return self.unique[key]

    def variable(self, name):
        if name not in self.variables:
            self.variables[name] = len(self.variables)
        return self.node(self.variables[name], 0, 1)

    def invert(self, value):
        if value < 2:
            return 1 - value
        if value not in self.inverse_cache:
            variable, low, high = self.nodes[value]
            self.inverse_cache[value] = self.node(variable, self.invert(low), self.invert(high))
        return self.inverse_cache[value]

    def combine(self, operation, left, right):
        if left > right:
            left, right = right, left
        if left < 2 and right < 2:
            return {"and": left & right, "or": left | right, "xor": left ^ right}[operation]
        key = (operation, left, right)
        if key in self.operation_cache:
            return self.operation_cache[key]
        lv = self.nodes[left][0] if left > 1 else len(self.variables)
        rv = self.nodes[right][0] if right > 1 else len(self.variables)
        variable = min(lv, rv)
        ll, lh = self.nodes[left][1:] if lv == variable else (left, left)
        rl, rh = self.nodes[right][1:] if rv == variable else (right, right)
        result = self.node(variable, self.combine(operation, ll, rl), self.combine(operation, lh, rh))
        self.operation_cache[key] = result
        return result

    def choose(self, condition, yes, no):
        return self.combine("or", self.combine("and", condition, yes),
                            self.combine("and", self.invert(condition), no))

    def zero(self, bits):
        any_bit = 0
        for bit in bits:
            any_bit = self.combine("or", any_bit, bit)
        return self.invert(any_bit)

    def describe(self, value, budget=12):
        names = {index: name for name, index in self.variables.items()}
        remaining = [budget]
        def visit(node):
            if node < 2:
                return bool(node)
            if remaining[0] <= 0:
                return "additional symbolic branches"
            remaining[0] -= 1
            variable, low, high = self.nodes[node]
            return {"variable": names[variable], "whenFalse": visit(low), "whenTrue": visit(high)}
        return visit(value)


@dataclass(frozen=True)
class Pointer:
    domain: str
    offset: int = 0


@dataclass(frozen=True)
class Register:
    number: int


@dataclass(frozen=True)
class Memory:
    base: int
    displacement: int


class IntegerFlow:
    def __init__(self, body):
        self.body = body
        self.position = 0
        self.at = 0
        self.graph = BooleanGraph()
        self.registers = {n: tuple(self.graph.variable(("register", n, b)) for b in range(64)) for n in range(16)}
        self.registers.update({1: Pointer("receiver"), 2: Pointer("input"), 4: Pointer("stack")})
        self.xmm = {}
        self.receiver = {}
        self.stack = {}
        self.zero_flag = self.graph.variable(("entry", "zeroFlag"))
        self.byte_comparisons = set()
        self.instruction_count = 0

    def fail(self, detail):
        raise IntegerFlowError(self.at, detail)

    def take(self, count):
        raw = self.body[self.position:self.position + count]
        if len(raw) != count:
            self.fail("truncated instruction")
        self.position += count
        return raw

    def byte(self):
        return self.take(1)[0]

    def literal(self, count, signed=False):
        return int.from_bytes(self.take(count), "little", signed=signed)

    def modrm(self, rex, width):
        value = self.byte()
        mode, reg, base = value >> 6, (value >> 3) & 7, value & 7
        reg |= (rex & 4) << 1
        extended = base | ((rex & 1) << 3)
        if mode == 3:
            if width == 8 and not rex and (4 <= base <= 7 or 4 <= reg <= 7):
                self.fail("legacy high-byte registers are outside this profile")
            return Register(reg), Register(extended)
        if base == 4:
            sib = self.byte()
            if (sib >> 3) & 7 != 4 or rex & 2 or sib & 7 == 5 and mode == 0:
                self.fail("indexed/SIB addressing is outside this profile")
            extended = (sib & 7) | ((rex & 1) << 3)
        elif base == 5 and mode == 0:
            self.fail("RIP-relative addressing is outside this profile")
        displacement = self.literal(1 if mode == 1 else 4, True) if mode else 0
        return Register(reg), Memory(extended, displacement)

    def address(self, memory):
        base = self.registers[memory.base]
        if not isinstance(base, Pointer):
            self.fail("memory base is not an authenticated symbolic pointer")
        return Pointer(base.domain, base.offset + memory.displacement)

    def constant(self, value, width):
        return tuple((value >> bit) & 1 for bit in range(width))

    def input_word(self, offset):
        return tuple(self.graph.variable(("inputBit", offset + bit // 8, bit % 8)) for bit in range(32))

    def initial_receiver(self, offset, width=32):
        return tuple(self.graph.variable(("receiverBit", offset + bit // 8, bit % 8)) for bit in range(width))

    def byte_zero(self, offset):
        return self.graph.variable(("inputByteIsZero", offset))

    def receiver_word(self, offset):
        return self.read_pointer(Pointer("receiver", offset), 32)

    def read_pointer(self, pointer, width):
        if pointer.domain == "stack":
            if width != 64 or pointer.offset not in self.stack:
                self.fail("unrecorded stack read")
            return self.stack[pointer.offset]
        if pointer.offset < 0:
            self.fail("negative input/receiver offset")
        if pointer.domain == "input":
            if width != 32:
                self.fail("only copied input words and explicit byte zero-tests are admitted")
            return self.input_word(pointer.offset)
        if pointer.domain != "receiver":
            self.fail("unknown memory domain")
        values = []
        for byte in range(width // 8):
            bits = self.receiver.get(pointer.offset + byte)
            values.extend(bits if bits is not None else self.initial_receiver(pointer.offset + byte, 8))
        return tuple(values)

    def read(self, operand, width):
        if isinstance(operand, Register):
            value = self.registers[operand.number]
            if isinstance(value, Pointer):
                if width != 64:
                    self.fail("partial pointer read")
                return value
            return value[:width]
        return self.read_pointer(self.address(operand), width)

    def write(self, operand, value, width):
        if isinstance(operand, Register):
            if isinstance(value, Pointer):
                if width != 64:
                    self.fail("partial pointer write")
                self.registers[operand.number] = value
            elif width == 32:
                self.registers[operand.number] = tuple(value) + (0,) * 32
            elif width == 64:
                self.registers[operand.number] = tuple(value)
            else:
                old = self.registers[operand.number]
                if isinstance(old, Pointer):
                    self.fail("byte write into pointer")
                self.registers[operand.number] = tuple(value) + old[width:]
            return
        pointer = self.address(operand)
        if pointer.domain == "stack":
            if width != 64:
                self.fail("partial stack write")
            self.stack[pointer.offset] = value
            return
        if pointer.domain != "receiver" or pointer.offset < 0 or isinstance(value, Pointer):
            self.fail("invalid receiver store")
        for byte in range(width // 8):
            self.receiver[pointer.offset + byte] = tuple(value[byte * 8:byte * 8 + 8])

    def bit_operation(self, operation, target, other, width):
        left, right = self.read(target, width), self.read(other, width) if not isinstance(other, tuple) else other
        if isinstance(left, Pointer) or isinstance(right, Pointer):
            self.fail("bit operation on pointer")
        result = tuple(self.graph.combine(operation, a, b) for a, b in zip(left, right))
        self.write(target, result, width)
        self.zero_flag = self.graph.zero(result)

    def execute(self):
        while self.position < len(self.body):
            self.at = self.position
            self.instruction_count += 1
            if self.instruction_count > 4096:
                self.fail("instruction budget exceeded")
            opcode = self.byte()
            floating = opcode == 0xf3
            if floating:
                opcode = self.byte()
            rex = 0
            if 0x40 <= opcode <= 0x4f:
                rex = opcode & 15
                opcode = self.byte()
            width = 64 if rex & 8 else 32
            if opcode == 0xc3 and not floating:
                if self.position != len(self.body):
                    self.fail("bytes after return")
                return self
            if opcode == 0x0f:
                second = self.byte()
                if floating and second in (0x10, 0x11):
                    reg, memory = self.modrm(rex, 32)
                    if not isinstance(memory, Memory):
                        self.fail("only memory movss transfers are admitted")
                    if second == 0x10:
                        self.xmm[reg.number] = self.read(memory, 32)
                    elif reg.number in self.xmm:
                        self.write(memory, self.xmm[reg.number], 32)
                    else:
                        self.fail("uninitialized scalar register")
                    continue
                if not floating and second in (0x44, 0x45, 0x94, 0x95):
                    byte_width = 8 if second >= 0x90 else width
                    reg, other = self.modrm(rex, byte_width)
                    condition = self.zero_flag if second in (0x44, 0x94) else self.graph.invert(self.zero_flag)
                    if second >= 0x90:
                        if reg.number != 0:
                            self.fail("nonzero setcc opcode extension")
                        self.write(other, (condition,) + (0,) * 7, 8)
                    else:
                        yes, no = self.read(other, width), self.read(reg, width)
                        if isinstance(yes, Pointer) or isinstance(no, Pointer):
                            self.fail("conditional pointer move")
                        self.write(reg, tuple(self.graph.choose(condition, y, n) for y, n in zip(yes, no)), width)
                    continue
                self.fail("unsupported extended opcode")
            if floating:
                self.fail("unsupported F3 instruction")
            if opcode in (0x89, 0x8b, 0x8d, 0x33, 0x0b, 0x23, 0x38, 0x84):
                operand_width = 8 if opcode in (0x38, 0x84) else width
                reg, other = self.modrm(rex, operand_width)
                if opcode in (0x89, 0x8b):
                    target, source = (other, reg) if opcode == 0x89 else (reg, other)
                    self.write(target, self.read(source, width), width)
                elif opcode == 0x8d:
                    if width != 64 or not isinstance(other, Memory):
                        self.fail("non-pointer LEA")
                    self.write(reg, self.address(other), 64)
                elif opcode in (0x33, 0x0b, 0x23):
                    self.bit_operation({0x33: "xor", 0x0b: "or", 0x23: "and"}[opcode], reg, other, width)
                elif opcode == 0x38:
                    if not isinstance(other, Memory) or self.read(reg, 8) != (0,) * 8:
                        self.fail("only input byte comparison with zero is admitted")
                    pointer = self.address(other)
                    if pointer.domain != "input" or pointer.offset < 0:
                        self.fail("comparison does not read the input")
                    self.byte_comparisons.add(pointer.offset)
                    self.zero_flag = self.byte_zero(pointer.offset)
                else:
                    bits = tuple(self.graph.combine("and", a, b) for a, b in zip(self.read(reg, 8), self.read(other, 8)))
                    self.zero_flag = self.graph.zero(bits)
                continue
            if 0xb8 <= opcode <= 0xbf:
                value = self.literal(8 if width == 64 else 4)
                self.write(Register((opcode - 0xb8) | ((rex & 1) << 3)), self.constant(value, width), width)
                continue
            if opcode in (0x83, 0xf6, 0xc6):
                operand_width = 8 if opcode in (0xf6, 0xc6) else width
                extension, other = self.modrm(rex, operand_width)
                immediate = self.literal(1, opcode == 0x83)
                if opcode == 0x83 and extension.number == 4:
                    self.bit_operation("and", other, self.constant(immediate, width), width)
                elif opcode == 0xf6 and extension.number == 0:
                    bits = tuple(self.graph.combine("and", a, b) for a, b in zip(self.read(other, 8), self.constant(immediate, 8)))
                    self.zero_flag = self.graph.zero(bits)
                elif opcode == 0xc6 and extension.number == 0:
                    self.write(other, self.constant(immediate, 8), 8)
                else:
                    self.fail("unsupported immediate opcode extension")
                continue
            self.fail(f"unsupported opcode {opcode:#x}")
        self.fail("missing return")
