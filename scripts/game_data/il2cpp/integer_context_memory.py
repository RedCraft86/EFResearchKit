"""Optional physical memory SUB/byte INC/XOR and accumulator AND forms.

Operand sizes, partial writes, immediate sign extension and original instruction
ends are proved here. These instructions establish no allocator/class meaning.
"""
from __future__ import annotations
from scripts.game_data.il2cpp.integer_addressing import _address, _prefix, _reg, _required
from scripts.game_data.il2cpp.integer_tag_dispatch import _memory_text, _row
from scripts.game_data.il2cpp.integer_byte_operations import _destination, decode_byte_operation_instructions


def decode_memory_destination_subtract(data, offset, start_va):
    if not 0 <= offset < len(data): return None
    at, rex = _prefix(data, offset)
    if data[at:at+1] != b'\x29': return None
    at += 1; modrm = _required(data, at, 1, offset, 'memory-destination-subtract')[0]; at += 1
    if modrm >> 6 == 3: return None
    bits = 64 if rex & 8 else 32; register = _reg(((modrm >> 3) & 7) | ((rex & 4) << 1), bits)
    address, at = _address(data, at, modrm, rex, offset, 'memory-destination-subtract')
    text = _memory_text(address, at, start_va, bits)
    return _row(data, offset, at, start_va, f'sub {text}, {register}',
        memoryDestinationSubtractOperation={'bits':bits,'sourceRegister':register,'destinationAddress':address,
            'memoryReadBytes':bits//8,'memoryWriteBytes':bits//8,'preservesRegisters':True,
            'wrapsModulo':1 << bits,'result':'previous destination memory minus source modulo operand width',
            'writesFlags':['CF','OF','SF','ZF','AF','PF']})


def decode_accumulator_and(data, offset, start_va):
    if not 0 <= offset < len(data): return None
    at, rex = _prefix(data, offset)
    if data[at:at+1] != b'\x25': return None
    at += 1; raw = _required(data, at, 4, offset, 'accumulator-and'); at += 4
    bits = 64 if rex & 8 else 32
    value = int.from_bytes(raw, 'little', signed=bits == 64)
    register = 'rax' if bits == 64 else 'eax'
    return _row(data, offset, at, start_va, f'and {register}, {hex(value)}',
        write={'register':register,'value':'previous accumulator AND extended immediate'},
        accumulatorAndOperation={'destinationRegister':register,'bits':bits,'encodedImmediateBits':32,
            'immediateValue':value,'immediateWord':value & ((1 << bits)-1),
            'signExtendsImmediateTo64':bits==64,'zeroExtendsTo64':bits==32,'writesMemory':False,
            'clearsFlags':['CF','OF'],'undefinedFlags':['AF'],'writesResultFlags':['SF','ZF','PF']})


def decode_byte_memory_step(data, offset, start_va):
    if not 0 <= offset < len(data): return None
    at, rex = _prefix(data, offset)
    if rex & 4 or data[at:at+1] != b'\xfe': return None
    at += 1; modrm = _required(data, at, 1, offset, 'byte-memory-step')[0]; at += 1
    group = (modrm >> 3) & 7
    if modrm >> 6 == 3 or group not in (0,1): return None
    address, at = _address(data, at, modrm, rex, offset, 'byte-memory-step')
    text = _memory_text(address, at, start_va, 8); operation = 'inc' if group == 0 else 'dec'
    return _row(data, offset, at, start_va, f'{operation} {text}',
        memoryStepOperation={'operation':operation,'bits':8,'destinationAddress':address,
            'memoryReadBytes':1,'memoryWriteBytes':1,'locked':False,'preservesRegisters':True,
            'delta':1 if group==0 else -1,'wrapsModulo':256,'preservesCarryFlag':True,
            'writesFlags':['OF','SF','ZF','AF','PF']})


def decode_byte_memory_xor(data, offset, start_va):
    if not 0 <= offset < len(data): return None
    at, rex = _prefix(data, offset)
    if data[at:at+1] != b'\x32': return None
    at += 1; modrm = _required(data, at, 1, offset, 'byte-memory-xor')[0]; at += 1
    if modrm >> 6 == 3: return None
    number = ((modrm >> 3) & 7) | ((rex & 4) << 1)
    address, at = _address(data, at, modrm, rex, offset, 'byte-memory-xor')
    text = _memory_text(address, at, start_va, 8); fact = _destination(number, rex)
    fact.update(operation='xor',sourceAddress=address,memoryReadBytes=1,memoryWriteBytes=0,
                clearsFlags=['CF','OF'],undefinedFlags=['AF'],writesResultFlags=['SF','ZF','PF'])
    return _row(data, offset, at, start_va, f'xor {fact["destinationRegister"]}, {text}',
                write={'register':fact['destinationRegister'],'value':'previous byte XOR memory byte'},
                byteMemoryXorOperation=fact)


def decode_memory_register_compare(data, offset, start_va):
    if not 0 <= offset < len(data): return None
    at, rex = _prefix(data, offset); opcode = data[at:at+1]
    if opcode not in (b'\x39',b'\x3b'): return None
    at += 1; modrm = _required(data, at, 1, offset, 'memory-register-compare')[0]; at += 1
    if modrm >> 6 == 3: return None
    bits = 64 if rex & 8 else 32; register = _reg(((modrm >> 3) & 7) | ((rex & 4) << 1), bits)
    address, at = _address(data, at, modrm, rex, offset, 'memory-register-compare')
    text = _memory_text(address, at, start_va, bits); memory_first = opcode == b'\x39'
    return _row(data, offset, at, start_va, f'cmp {text}, {register}' if memory_first else f'cmp {register}, {text}',
        memoryRegisterComparisonOperation={'bits':bits,'register':register,'memoryAddress':address,
            'memoryReadBytes':bits//8,'memoryWriteBytes':0,'memoryIsLeftOperand':memory_first,
            'preservesRegisters':True,'writesFlags':['CF','OF','SF','ZF','AF','PF']})


def decode_context_memory_instructions(mapper, data, start_va):
    class Fallback:
        def decode_one_x64(self, raw, offset, at):
            for decoder in (decode_memory_destination_subtract,decode_accumulator_and,
                            decode_byte_memory_step,decode_byte_memory_xor,decode_memory_register_compare):
                result = decoder(raw, offset, at)
                if result is not None: return result
            return mapper.decode_one_x64(raw, offset, at)
    return decode_byte_operation_instructions(Fallback(),data,start_va)
