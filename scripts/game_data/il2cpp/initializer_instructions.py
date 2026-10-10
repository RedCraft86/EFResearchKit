"""Optional initializer memory writes with exact widths and default addresses.

Selected legacy packed moves, byte stores/logic and locked INC/DEC establish
instruction facts, without class-field, storage-validity or runtime meaning.
"""
from __future__ import annotations
from .integer_addressing import _address,_prefix,_required
from .integer_byte_operations import _destination
from .integer_context_memory import decode_context_memory_instructions
from .integer_tag_dispatch import _row,_memory_text
from .memory_moves import decode_memory_move,decode_copy_padding,_finish_address


def decode_initializer_move(data,offset,start_va):
    if not 0<=offset<len(data):return None
    at,rex=_prefix(data,offset);op=data[at:at+2]
    if op not in (b'\x0f\x10',b'\x0f\x11',b'\x0f\x28',b'\x0f\x29'):return None
    at+=2;modrm=_required(data,at,1,offset,'initializer-packed-move')[0];at+=1
    if modrm>>6==3:return None
    number=((modrm>>3)&7)|((rex&4)<<1);address,at=_address(data,at,modrm,rex,offset,'initializer-packed-move')
    term=_finish_address(address,at,start_va);load=op[1] in (0x10,0x28);aligned=op[1] in (0x28,0x29)
    mnemonic='movaps' if aligned else 'movups';register=f'xmm{number}'
    operands=f'{register}, [{term}]' if load else f'[{term}], {register}'
    return _row(data,offset,at,start_va,f'{mnemonic} {operands}',
        write={'register':register,'value':'loaded low 128 memory bits'} if load else None,
        memoryOperation={'direction':'load' if load else 'store','register':register,
            'backingRegister':f'vector{number}','registerBits':128,'registerBitOffset':0,
            'memoryBytes':16,'address':address,'valueExtension':None,
            'upperRegisterEffect':'preserved','requiredAlignmentBytes':16 if aligned else 1,
            'nonTemporalHint':False,'writesFlags':False})


def decode_initializer_byte_store(data,offset,start_va):
    if not 0<=offset<len(data):return None
    at,rex=_prefix(data,offset)
    if rex&4 or data[at:at+1]!=b'\xc6':return None
    at+=1;modrm=_required(data,at,1,offset,'initializer-byte-store')[0];at+=1
    if modrm>>6==3 or (modrm>>3)&7:return None
    address,at=_address(data,at,modrm,rex,offset,'initializer-byte-store')
    value=_required(data,at,1,offset,'initializer-byte-store')[0];at+=1
    operand=_memory_text(address,at,start_va,8)
    return _row(data,offset,at,start_va,f'mov {operand}, {hex(value)}',
        immediateMemoryStoreOperation={'bits':8,'destinationAddress':address,
            'memoryReadBytes':0,'memoryWriteBytes':1,'encodedImmediateBits':8,
            'immediateWord':value,'signExtendsImmediateTo64':False,
            'writesFlags':False,'preservesRegisters':True})


def decode_initializer_byte_logic(data,offset,start_va):
    if not 0<=offset<len(data):return None
    at,rex=_prefix(data,offset)
    if rex&4 or data[at:at+1]!=b'\x80':return None
    at+=1;modrm=_required(data,at,1,offset,'initializer-byte-logic')[0];at+=1
    group=(modrm>>3)&7
    if group not in (1,4):return None
    operation='or' if group==1 else 'and';address=None
    if modrm>>6==3:fact=_destination((modrm&7)|((rex&1)<<3),rex);operand=fact['destinationRegister']
    else:
        address,at=_address(data,at,modrm,rex,offset,'initializer-byte-logic')
        fact={'bits':8,'destinationAddress':address,'memoryReadBytes':1,'memoryWriteBytes':1,
              'preservesRegisters':True}
        operand=None
    value=_required(data,at,1,offset,'initializer-byte-logic')[0];at+=1
    if address is not None:operand=_memory_text(address,at,start_va,8)
    fact.update(operation=operation,immediateWord=value,encodedImmediateBits=8,
                signExtendsImmediateTo64=False,clearsFlags=['CF','OF'],undefinedFlags=['AF'],writesResultFlags=['SF','ZF','PF'])
    key='byteMemoryLogicalOperation' if address is not None else 'byteLogicalOperation'
    return _row(data,offset,at,start_va,f'{operation} {operand}, {hex(value)}',**{key:fact})


def decode_initializer_locked_step(data,offset,start_va):
    if not 0<=offset<len(data) or data[offset]!=0xf0:return None
    at,rex=_prefix(data,offset+1)
    if rex&4 or data[at:at+1]!=b'\xff':return None
    at+=1;modrm=_required(data,at,1,offset,'initializer-locked-step')[0];at+=1
    group=(modrm>>3)&7
    if modrm>>6==3 or group not in (0,1):return None
    address,at=_address(data,at,modrm,rex,offset,'initializer-locked-step');bits=64 if rex&8 else 32
    operand=_memory_text(address,at,start_va,bits);op='inc' if group==0 else 'dec'
    return _row(data,offset,at,start_va,f'lock {op} {operand}',
        memoryStepOperation={'operation':op,'bits':bits,'destinationAddress':address,
            'memoryReadBytes':bits//8,'memoryWriteBytes':bits//8,'locked':True,
            'preservesRegisters':True,'delta':1 if group==0 else -1,'wrapsModulo':1<<bits,
            'preservesCarryFlag':True,'writesFlags':['OF','SF','ZF','AF','PF']})


def decode_initializer_instructions(mapper,data,start_va):
    class Fallback:
        def decode_one_x64(self,raw,offset,at):
            for decoder in (decode_memory_move,decode_copy_padding,decode_initializer_move,
                            decode_initializer_byte_store,decode_initializer_byte_logic,decode_initializer_locked_step):
                result=decoder(raw,offset,at)
                if result is not None:return result
            if raw[offset:offset+1]==b'\x90':
                return _row(raw,offset,offset+1,at,'nop',paddingOperation={'readsMemory':False,'writesFlags':False})
            return mapper.decode_one_x64(raw,offset,at)
    return decode_context_memory_instructions(Fallback(),data,start_va)
