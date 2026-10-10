"""Selected native byte-fill lane construction and REP STOSB instructions.

These facts describe register bits and instruction spans. Destination validity,
dispatch-table bounds, complete payload coverage and visibility belong to the
consumer proof. Memory forms and unsupported prefixes remain outside this lane.
"""
from __future__ import annotations
from .integer_addressing import _required, _reg
from .memory_moves import decode_memory_move_instructions
from .rep_string_moves import decode_rip_byte_test


def _row(data, offset, stop, start_va, text, **facts):
    return {'offset':offset, 'va':hex(start_va+offset),
            'bytes':data[offset:stop].hex(' '), 'text':text, 'write':None, **facts}, stop


def decode_fill_lanes(data, offset, start_va):
    if not 0 <= offset < len(data): return None
    at = offset
    if data[at:at+1] == b'\x66':
        at += 1; rex = 0
        if at < len(data) and 0x40 <= data[at] <= 0x4f:
            rex = data[at]; at += 1
        opcode = data[at:at+2]
        if opcode not in (b'\x0f\x6e', b'\x0f\x6c'): return None
        at += 2; modrm = _required(data, at, 1, offset, 'fill-lanes')[0]; at += 1
        if modrm >> 6 != 3: return None
        destination = ((modrm >> 3) & 7) | ((rex & 4) << 1)
        source = (modrm & 7) | ((rex & 1) << 3)
        if opcode == b'\x0f\x6e':
            bits = 64 if rex & 8 else 32; register = _reg(source, bits)
            return _row(data, offset, at, start_va,
                f"{'movq' if bits == 64 else 'movd'} xmm{destination}, {register}",
                fillLaneOperation={'operation':'gp-to-xmm', 'destination':destination,
                    'sourceRegister':register, 'sourceBits':bits,
                    'zeroBitsThrough127From':bits, 'preservesBitsAbove127':True,
                    'writesMemory':False, 'writesFlags':False})
        return _row(data, offset, at, start_va,
            f'punpcklqdq xmm{destination}, xmm{source}',
            fillLaneOperation={'operation':'unpack-low-qwords', 'destination':destination,
                'sourceVector':source, 'resultLow64':'previous destination low64',
                'resultHigh64':'previous source low64', 'preservesBitsAbove127':True,
                'writesMemory':False, 'writesFlags':False})
    if data[at:at+1] != b'\xc4': return None
    first, second = _required(data, at+1, 2, offset, 'fill-insert-vex')
    if first & 31 != 3 or second & 3 != 1 or second & 0x80 or data[at+3:at+4] != b'\x18': return None
    if not second & 4:
        raise ValueError(f'x64.fill-insert-vex.requires-256-bit: offset={offset}')
    modrm, immediate = _required(data, at+4, 2, offset, 'fill-insert-vex')
    if modrm >> 6 != 3: return None
    destination = ((modrm >> 3) & 7) | (((~first >> 7) & 1) << 3)
    base = (~second >> 3) & 15
    source = (modrm & 7) | (((~first >> 5) & 1) << 3)
    return _row(data, offset, at+6, start_va,
        f'vinsertf128 ymm{destination}, ymm{base}, xmm{source}, {hex(immediate)}',
        fillLaneOperation={'operation':'insert-128-lane', 'destination':destination,
            'baseVector':base, 'sourceVector':source, 'insertLane':immediate & 1,
            'encodedImmediate':immediate, 'ignoredImmediateBits':immediate & 0xfe,
            'zeroBitsAbove255':True, 'writesMemory':False, 'writesFlags':False})


def decode_rep_stosb(data, offset, start_va):
    if not 0 <= offset < len(data) or data[offset] != 0xf3: return None
    if offset+1 == len(data):
        raise ValueError(f'x64.rep-stosb.truncated: offset={offset}')
    if data[offset:offset+2] != b'\xf3\xaa': return None
    return _row(data, offset, offset+2, start_va, 'rep stosb',
        fillStringOperation={'operation':'rep-stosb', 'elementBytes':1,
            'addressBits':64, 'valueRegister':'al', 'destinationRegister':'rdi',
            'countRegister':'rcx', 'directionFlagControlsStep':True,
            'terminatesOnCountZero':True, 'zeroFlagControlsTermination':False,
            'modifiesRegisters':['rcx','rdi'], 'preservesValueRegister':True,
            'writesArithmeticFlags':False, 'changesDirectionFlag':False})


def decode_fill_jump(data, offset, start_va):
    if not 0 <= offset < len(data): return None
    at=offset; rex=0
    if 0x40 <= data[at] <= 0x4f: rex=data[at]; at+=1
    if rex & 4 or data[at:at+1] != b'\xff': return None
    modrm=_required(data,at+1,1,offset,'fill-jump')[0]
    if modrm >> 6 != 3 or (modrm >> 3) & 7 != 4: return None
    register=_reg((modrm & 7) | ((rex & 1) << 3),64)
    return _row(data,offset,at+2,start_va,f'jmp {register}',
                fillJumpOperation={'register':register,'bits':64,'writesMemory':False})


def decode_fill_instructions(mapper, data, start_va):
    class Fallback:
        def decode_one_x64(self, raw, offset, at):
            if raw[offset:offset+1] == b'\x90':
                return _row(raw,offset,offset+1,at,'nop',
                            paddingOperation={'readsMemory':False,'writesFlags':False})
            for decoder in (decode_fill_lanes,decode_rep_stosb,decode_fill_jump,decode_rip_byte_test):
                result=decoder(raw,offset,at)
                if result is not None:return result
            if raw[offset:offset+3] == b'\x0f\xae\xf8':
                return _row(raw,offset,offset+3,at,'sfence',
                            fillFenceOperation={'operation':'sfence','ordersStoresAgainstStores':True,
                                'ordersLoads':False,'allStoresVisibleAtReturnProved':False})
            return mapper.decode_one_x64(raw,offset,at)
    return decode_memory_move_instructions(Fallback(),data,start_va)
