"""Authenticate legacy guards, band state/routing and peak correspondence.

Revision framing has its own owner. This layer compares the complete old/current
peak loops after accounting for their explicit mode/link and amplitude steps.
Band scalar expressions and crossover arguments have independent bounded decoders.
Helper results, disjoint storage and unchanged controls retain their conditions.
"""
from __future__ import annotations

import hashlib
import json
import struct
from functools import lru_cache
from pathlib import Path

from scripts.game_data.contracts import CONTRACTS_DIR
from scripts.webui.audio.semantics.wwise_effect_updates import EffectUpdateError
from scripts.webui.audio.semantics.wwise_effect_integer_flow import Pointer


@lru_cache(maxsize=1)
def load_mastering_legacy_contract():
    return json.loads((CONTRACTS_DIR/'wwise_mastering_legacy_native.json').read_text(encoding='utf-8'))


def _loop_tokens(body, method, path):
    entries=path['instructions'];removed=path['removed'];start=path['start'];end=path['end']
    cursor=start;all_rows=sorted(entries+removed,key=lambda row:row['offset'])
    for row in all_rows:
        if row['offset']!=cursor or not 1<=row['byteLength']<=15:raise ValueError('loop instruction coverage is incomplete')
        cursor+=row['byteLength']
    if cursor!=end or end>len(body):raise ValueError('loop extent is not covered')
    positions={row['offset']:sum(item['offset']<row['offset'] for item in entries) for row in all_rows}
    result=[]
    for row in entries:
        at=row['offset'];size=row['byteLength'];raw=body[at:at+size];kind=row['kind']
        if kind=='branch':
            if size==2 and raw[0] in (0xeb,*range(0x70,0x80)):width=1;prefix=raw[:1]
            elif size==5 and raw[0]==0xe9:width=4;prefix=raw[:1]
            elif size==6 and raw[0]==0x0f and 0x80<=raw[1]<=0x8f:width=4;prefix=raw[:2]
            else:raise ValueError('unadmitted loop branch encoding')
            if row['displacementBytes']!=width:raise ValueError('loop branch width differs')
            target=at+size+int.from_bytes(raw[-width:],'little',signed=True)
            if target!=row['targetOffset']:raise ValueError('loop branch target differs')
            result.append((prefix.hex(),('local',positions[target]) if target in positions else ('shared',target)))
        elif kind=='relative':
            matches=[p for p in method['program'] if p['offset']==at and 'targetKind' in p]
            if len(matches)!=1:raise ValueError('loop relative role is missing or ambiguous')
            step=matches[0]
            if (row['targetKind'],row['target'])!=(step['targetKind'],step['target']):raise ValueError('loop helper/data role differs')
            prefix=bytes.fromhex(step['prefixHex']);suffix=bytes.fromhex(step['suffixHex'])
            if size!=len(prefix)+4+len(suffix) or raw[:len(prefix)]!=prefix or raw[len(prefix)+4:]!=suffix:raise ValueError('loop relative instruction framing differs')
            result.append((step['prefixHex'],step['suffixHex'],step['targetKind'],step['target']))
        elif kind=='bytes':
            if raw[0] in (0xe8,0xe9,0xeb,*range(0x70,0x80)) or (raw[:1]==b'\x0f' and len(raw)>1 and 0x80<=raw[1]<=0x8f):raise ValueError('unjoined loop control transfer')
            result.append(raw.hex())
        else:raise ValueError('unadmitted loop token kind')
    return result


def _band_scalar_program(body,method,row,attack_zero=None,release_zero=None,state_base=6):
    """Decode one complete active or inactive legacy scalar group."""
    def literal(x):return ('constant',struct.pack('<f',x).hex())
    registers={int(k):literal(v) for k,v in row['constantRegisters'].items()};eax=None;output={};condition=None;at=row['start']
    parameters={44:'threshold',48:'ratio',52:'attackTime',56:'releaseTime',60:'outputDb',64:'knee'}
    def take(n):
        nonlocal at
        if at+n>len(body):raise ValueError('truncated legacy band instruction')
        raw=body[at:at+n];at+=n;return raw
    def memory(rex,modrm):
        mode=modrm>>6;base=(modrm&7)|((rex&1)<<3);index=None;scale=1
        if modrm&7==4:
            sib=take(1)[0];scale=1<<(sib>>6);index=((sib>>3)&7)|((rex&2)<<2);base=(sib&7)|((rex&1)<<3)
        if mode==0:displacement=0
        elif mode in (1,2):displacement=int.from_bytes(take(1 if mode==1 else 4),'little',signed=True)
        else:raise ValueError('legacy band memory is a register')
        if base==3 and index in (12,14) and scale==8 and displacement in parameters:return ('parameter',parameters[displacement])
        if base==15 and mode==0 and index is None:return ('frequencyWord',)
        if base==state_base and index is None:return ('state',displacement+row['statePointerOffsetWithinBand'])
        raise ValueError('unjoined legacy band field address')
    def reg(index):
        if index not in registers:raise ValueError('undefined legacy band scalar register')
        return registers[index]
    def store(location,value):
        if location[0]!='state' or location[1] in output:raise ValueError('duplicate/unjoined legacy band scalar store')
        output[location[1]]=value
    for _ in range(512):
        if at==row['end']:return output
        if at>row['end']:raise ValueError('legacy band path exceeds its extent')
        begin=at
        if body[at] in (0x75,0xeb):
            opcode=take(1)[0];displacement=int.from_bytes(take(1),'little',signed=True)
            if opcode==0x75 and condition is None:raise ValueError('legacy time branch lacks predicate')
            if opcode==0xeb or not condition:at+=displacement
            continue
        if body[at]==0xe8:
            take(5);steps=[p for p in method['program'] if p['offset']==begin and p.get('prefixHex')=='e8']
            if len(steps)!=1 or steps[0]['targetKind']!='external':raise ValueError('legacy band helper role missing')
            role=steps[0]['target']
            if role=='coefficientHelper':result=('timeHelper',reg(0))
            elif role=='powerHelper':result=('powerHelper',reg(0),reg(1))
            else:raise ValueError('unadmitted legacy band helper')
            for index in range(6):registers.pop(index,None)
            registers[0]=result;eax=None;continue
        prefix=0;rex=0
        if body[at]==0xf3:prefix=take(1)[0]
        if 0x40<=body[at]<=0x4f:rex=take(1)[0]&15
        opcode=take(1)[0]
        if opcode in (0x8b,0x89,0xc7) and not prefix:
            modrm=take(1)[0];index=((modrm>>3)&7)|((rex&4)<<1)
            if rex&8:raise ValueError('legacy band store/load is not a word')
            location=memory(rex,modrm)
            if opcode==0xc7:
                if index:raise ValueError('legacy band immediate store has an unadmitted extension')
                store(location,('constant',take(4).hex()))
            elif opcode==0x8b:
                if index!=0:raise ValueError('legacy band load is not EAX')
                eax=location
            else:
                if index==13 and state_base==3:value=literal(0.)
                elif index==0 and eax is not None:value=eax
                else:raise ValueError('unjoined legacy raw word store')
                store(location,value)
            continue
        if opcode!=0x0f:raise ValueError(f'unadmitted legacy band opcode +{begin:#x}')
        operation=take(1)[0];modrm=take(1)[0];mode=modrm>>6;destination=((modrm>>3)&7)|((rex&4)<<1);source=(modrm&7)|((rex&1)<<3)
        if operation==0x2a and prefix==0xf3:
            if not rex&8 or mode!=3 or source!=0 or eax!=('frequencyWord',):raise ValueError('legacy band frequency conversion is not unsigned-32 via RAX')
            registers[destination]=('uint32ToFloat32',eax);continue
        if operation==0x57 and not prefix and mode==3 and destination==source:registers[destination]=literal(0.);continue
        operand=reg(source) if mode==3 else memory(rex,modrm)
        if operation==0x11 and prefix==0xf3:
            store(operand,reg(destination));continue
        if operation in (0x10,0x28) and ((operation==0x10 and prefix==0xf3) or (operation==0x28 and not prefix)):
            registers[destination]=operand;continue
        if operation==0x2e and not prefix:
            current=reg(destination)
            if operand!=literal(0.) or current not in (('parameter','attackTime'),('parameter','releaseTime')):raise ValueError('legacy time comparison has unproved operands')
            condition=attack_zero if current[1]=='attackTime' else release_zero;continue
        operations={0x59:'multiplyFloat32',0x5c:'subtractFloat32',0x5e:'divideFloat32'}
        if prefix!=0xf3 or operation not in operations:raise ValueError(f'unadmitted legacy band arithmetic +{begin:#x}')
        registers[destination]=(operations[operation],reg(destination),operand)
    raise ValueError('legacy band scalar instruction bound exceeded')


def _expected_band_active(attack_zero,release_zero):
    def literal(x):return ('constant',struct.pack('<f',x).hex())
    def parameter(name):return ('parameter',name)
    def op(name,a,b):return (name,a,b)
    frequency=('uint32ToFloat32',('frequencyWord',));one=literal(1.)
    def time(name,zero):
        if zero:return one
        argument=op('divideFloat32',literal(-2.2),op('multiplyFloat32',frequency,parameter(name)))
        return op('subtractFloat32',one,('timeHelper',argument))
    fields={0:parameter('threshold'),48:parameter('ratio'),96:time('attackTime',attack_zero),144:time('releaseTime',release_zero),
        192:('powerHelper',literal(10.),op('multiplyFloat32',parameter('outputDb'),literal(.05))),240:parameter('knee'),
        288:op('subtractFloat32',one,op('divideFloat32',one,parameter('ratio'))),
        336:op('subtractFloat32',one,('timeHelper',op('divideFloat32',literal(-440.0000305175781),frequency))),
        480:op('subtractFloat32',parameter('threshold'),op('multiplyFloat32',parameter('knee'),literal(.5)))}
    return {offset+4*channel:value for offset,value in fields.items() for channel in range(4)}


def _expected_band_inactive():
    def literal(x):return ('constant',struct.pack('<f',x).hex())
    frequency=('uint32ToFloat32',('frequencyWord',));one=literal(1.)
    def alpha(factor):return ('subtractFloat32',one,('timeHelper',('divideFloat32',literal(factor),frequency)))
    fields={0:literal(-20.),48:literal(2.),96:alpha(-440.0000305175781),144:alpha(-22.),192:one,
        240:literal(0.),288:literal(.5),336:alpha(-440.0000305175781),384:literal(0.),432:one,480:literal(-20.)}
    return {offset+4*channel:value for offset,value in fields.items() for channel in range(6)}


def _band_crossover_program(body,method,row,count,band,fail_call=None,error_code=1):
    """Decode routing while keeping every copied input word symbolic."""
    registers={0:0,2:count,3:Pointer('controls'),4:Pointer('stack'),5:Pointer('stack',256),
        7:Pointer('state'),8:('word','selector'),9:2,10:Pointer('state',64),12:Pointer('allocator'),13:band}
    memory={('state',0,32):('word','format'),('state',64,32):('word','frequency'),('state',72,32):count,
        ('stack',0x180,32):('word','selector'),('stack',0x170,64):Pointer('state',64),
        ('stack',0x40,32):0x01011000,('stack',0x44,32):24,('stack',0x50,32):0x3f34fdf4,
        ('stack',0x54,32):('word','untouchedDescriptorTail')}
    for index in range(2):memory['controls',36+4*index,32]=('cutoffWord',36+4*index)
    at=row['start'];xmm={};calls=[];counts={};zero=None;carry=None
    def take(n):
        nonlocal at
        if not 0<=at<=len(body)-n:raise ValueError('truncated legacy crossover instruction')
        raw=body[at:at+n];at+=n;return raw
    def add(a,b):
        if isinstance(a,Pointer) and type(b) is int:return Pointer(a.domain,a.offset+b)
        if isinstance(b,Pointer) and type(a) is int:return Pointer(b.domain,b.offset+a)
        if type(a) is int and type(b) is int:return a+b
        raise ValueError('arithmetic on an opaque crossover word')
    def reg(n,width=64):
        if n not in registers:raise ValueError('undefined crossover register after helper')
        v=registers[n]
        if isinstance(v,Pointer) and width!=64:raise ValueError('partial crossover pointer read')
        if type(v) is int:return v&((1<<width)-1)
        if isinstance(v,tuple) and width!=32:raise ValueError('partial/extended opaque crossover word')
        return v
    def operands(rex):
        modrm=take(1)[0];mode=modrm>>6;index=((modrm>>3)&7)|((rex&4)<<1);base=(modrm&7)|((rex&1)<<3)
        if mode==3:return index,('register',base)
        scaled=None;scale=1
        if modrm&7==4:
            sib=take(1)[0];scale=1<<(sib>>6);scaled=((sib>>3)&7)|((rex&2)<<2);base=(sib&7)|((rex&1)<<3)
            if scaled==4:scaled=None
            if sib&7==5 and mode==0:base=None
        elif modrm&7==5 and mode==0:raise ValueError('unjoined crossover RIP operand')
        displacement=int.from_bytes(take(1 if mode==1 else 4),'little',signed=True) if mode else int.from_bytes(take(4),'little',signed=True) if base is None else 0
        return index,('memory',base,scaled,scale,displacement)
    def address(operand):
        if operand[0]!='memory':raise ValueError('crossover LEA/memory is a register')
        _,base,index,scale,displacement=operand;v=displacement
        if base is not None:v=add(v,reg(base))
        if index is not None:
            value=reg(index)
            if type(value) is not int:raise ValueError('crossover scaled index is not an integer')
            v=add(v,value*scale)
        return v
    def read(operand,width):
        if operand[0]=='register':return reg(operand[1],width)
        p=address(operand)
        if not isinstance(p,Pointer) or (p.domain,p.offset,width) not in memory:raise ValueError('unjoined crossover memory read')
        return memory[p.domain,p.offset,width]
    def write(operand,v,width):
        if operand[0]=='register':
            if isinstance(v,Pointer) and width!=64:raise ValueError('partial crossover pointer write')
            if isinstance(v,tuple) and width!=32:raise ValueError('partial crossover word write')
            registers[operand[1]]=v&((1<<width)-1) if type(v) is int else v;return
        p=address(operand)
        if not isinstance(p,Pointer) or p.domain not in ('stack','state'):raise ValueError('unjoined crossover memory write')
        if p.domain=='state':
            if width!=16 or p.offset!=92+2*band:raise ValueError('crossover writes outside its filter-count cell')
            counts[p.offset]=v
        memory[p.domain,p.offset,width]=v
    def compare(a,b,width,testing=False):
        nonlocal zero,carry
        if type(a) is not int or type(b) is not int:raise ValueError('branch depends on an opaque crossover word')
        mask=(1<<width)-1;a&=mask;b&=mask;zero=(a&b)==0 if testing else a==b;carry=False if testing else a<b
    def branch(opcode,target):
        nonlocal at
        if opcode==0xeb:at=target;return
        if zero is None or carry is None:raise ValueError('crossover branch lacks flags')
        if opcode not in (0x72,0x74,0x75):raise ValueError('unadmitted crossover condition')
        if {0x72:carry,0x74:zero,0x75:not zero}[opcode]:at=target
    for _ in range(1024):
        if at in (row['end'],row['errorExit']):return dict(calls=calls,filterCountWrites=counts,exit=at)
        if not row['start']<=at<row['end']:raise ValueError('crossover path leaves its extent')
        begin=at;prefix=0;rex=0
        if body[at] in (0x66,0xf3):prefix=take(1)[0]
        if 0x40<=body[at]<=0x4f:rex=take(1)[0]&15
        opcode=take(1)[0];width=16 if prefix==0x66 else 64 if rex&8 else 32
        if opcode in (0x72,0x74,0x75,0xeb):
            target=at+1+int.from_bytes(take(1),'little',signed=True);branch(opcode,target);continue
        if opcode==0xe8:
            take(4);steps=[p for p in method['program'] if p['offset']==begin and p.get('prefixHex')=='e8']
            if len(steps)!=1 or (steps[0]['targetKind'],steps[0]['target'])!=('method','filterConversion'):raise ValueError('unjoined crossover helper')
            if reg(1)!=Pointer('stack',0x40):raise ValueError('crossover descriptor pointer differs')
            p=reg(2)
            if not isinstance(p,Pointer) or p.domain!='state':raise ValueError('crossover target is not state')
            fields=tuple(memory['stack',offset,32] for offset in (0x40,0x44,0x48,0x4c,0x50,0x54))
            calls.append((p.offset,reg(8,32),reg(9,32),memory['stack',0x20,32],memory['stack',0x28,64],fields))
            result=error_code if len(calls)-1==fail_call else 0
            for n in (0,1,2,8,9,10,11):registers.pop(n,None)
            for n in range(6):xmm.pop(n,None)
            registers[0]=result;zero=carry=None;continue
        if opcode==0x0f:
            operation=take(1)[0]
            if operation in (0x82,0x84,0x85):
                target=at+4+int.from_bytes(take(4),'little',signed=True);branch(operation-0x10,target);continue
            index,other=operands(rex)
            if operation==0x1f and prefix in (0,0x66):continue
            if prefix!=0xf3 or operation not in (0x10,0x11):raise ValueError('unadmitted crossover extended opcode')
            if operation==0x10:xmm[index]=read(other,32)
            elif index in xmm:write(other,xmm[index],32)
            else:raise ValueError('undefined crossover scalar word')
            continue
        if opcode==0x90 and prefix==0x66:continue
        if 0xb8<=opcode<=0xbf:
            write(('register',(opcode-0xb8)|((rex&1)<<3)),int.from_bytes(take(8 if width==64 else width//8),'little'),width);continue
        index,other=operands(rex);register=('register',index)
        if opcode==0x8b:write(register,read(other,width),width)
        elif opcode==0x89:write(other,read(register,width),width)
        elif opcode==0x8d:write(register,address(other),width)
        elif opcode==0x03:write(register,add(read(register,width),read(other,width)),width);zero=carry=None
        elif opcode in (0x3b,0x85):compare(read(register,width),read(other,width),width,opcode==0x85)
        elif opcode==0xff and index in (0,1):
            v=read(other,width)
            if type(v) is not int:raise ValueError('crossover increment/decrement of opaque word')
            write(other,v+(1 if index==0 else -1),width);zero=carry=None
        elif opcode==0x69:
            factor=int.from_bytes(take(4),'little',signed=True);v=read(other,width)
            if type(v) is not int:raise ValueError('crossover multiplication of opaque word')
            write(register,v*factor,width);zero=carry=None
        elif opcode==0xc7 and index==0:write(other,int.from_bytes(take(2 if width==16 else 4),'little',signed=width==64),width)
        elif opcode==0x83 and index in (0,7):
            immediate=int.from_bytes(take(1),'little',signed=True)
            if index==0:write(other,add(read(other,width),immediate),width);zero=carry=None
            else:compare(read(other,width),immediate,width)
        else:raise ValueError(f'unadmitted crossover opcode +{begin:#x}')
    raise ValueError('crossover instruction bound exceeded')


def _expected_band_crossover(row,count,band,fail_call=None):
    calls=[];counts={}
    def emit(stage,kind,cutoff):
        fields=(0x01011000,24,kind,('cutoffWord',36+4*cutoff),0x3f34fdf4,('word','untouchedDescriptorTail'))
        calls.append((100+216*(4*band+stage),('word','format'),('word','frequency'),('word','selector'),Pointer('allocator'),fields))
        return len(calls)-1==fail_call
    if count>1:
        kind=2 if band==count-1 else 1;cutoff=band-1 if band==count-1 else band
        for stage in range(2):
            if emit(stage,kind,cutoff):return dict(calls=calls,filterCountWrites=counts,exit=row['errorExit'])
        if 0<band<count-1:
            counts[92+2*band]=4
            for stage in range(2,4):
                if emit(stage,2,band-1):return dict(calls=calls,filterCountWrites=counts,exit=row['errorExit'])
        else:counts[92+2*band]=2
    return dict(calls=calls,filterCountWrites=counts,exit=row['end'])


def validate_mastering_legacy(contract,native_inputs,dynamics_contract,dynamics,revisions,profiles_contract,profiles,read):
    def equal(check,expected,actual,offset=0):
        if expected!=actual:raise EffectUpdateError('masteringLegacy',check,offset,expected,actual)
    equal('schema','endfield.wwise-mastering-legacy-native-contract.v4',contract['schema'])
    equal('reviewStatus','reviewed',contract['status']);equal('boundary','conditional',contract['evidenceBoundary'])
    for name,value in (('inputs',contract['nativeInputs']),('dynamicsInputs',dynamics_contract['nativeInputs']),('profilesInputs',profiles_contract['nativeInputs'])):equal(name,native_inputs,value)
    for name,value in (('dynamics',dynamics),('revisions',revisions),('profiles',profiles)):equal('parentProof:'+name,'validated',value['status'])
    bodies={}
    for name in ('convertBands','convertPeak','applyPeak','applyBands','processModes','delayedKernel'):
        row=dynamics_contract['methods'][name];body=read(int(row['rva'],16),row['bodyLength'])
        equal('methodHash:'+name,row['bodySha256'],hashlib.sha256(body).hexdigest());bodies[name]=body
    # Opcodes encode independent integer guards; branch targets must all reach
    # the actual shared invalid-control result, rather than a nearby address.
    guard_grammar=dict(bandLegacyCount='418b460883f801',bandLegacyCountUpper='83f803',bandLegacyBypassUpper='83f80f',
        bandLegacyBypassThreeBits='83f807',bandLegacyLink='418b460c83f802',bandLegacySpecial='4183f8017509413bc0',
        bandLegacyPair='418b461483f801',bandCurrentCount='418b4e088d41ff83f802',bandCurrentBypass='418b461883f80f',
        bandCurrentLink='418b460c83f802',bandCurrentPair='418b461483f801',peakLegacyMode='8b430883f802',
        bandLegacyReservedFirst='418b461c85c0',bandLegacyReservedSecond='41394620',
        bandCurrentReservedFirst='418b461c85c0',bandCurrentReservedSecond='41394620',
        peakLegacyReservedFirst='837b1800',peakLegacyReservedSecond='837b1c00',peakCurrentMode='8b430883f802',
        peakCurrentReservedFirst='837b1800',peakCurrentReservedSecond='837b1c00')
    equal('guardSet',set(guard_grammar),set(contract['guards']))
    for name,hex_value in guard_grammar.items():
        row=contract['guards'][name];at=row['offset'];raw=bytes.fromhex(hex_value);body=bodies[row['method']]
        equal('guard:'+name,raw,body[at:at+len(raw)],at)
        branch_at=at+len(raw);branch=body[branch_at:branch_at+6]
        equal('guardBranch:'+name,bytes.fromhex(row['branchOpcode']),branch[:2],branch_at)
        equal('guardErrorTarget:'+name,row['errorOffset'],branch_at+6+struct.unpack_from('<i',branch,2)[0],branch_at)
        error=body[row['errorOffset']:row['errorOffset']+5]
        equal('invalidControlResult:'+name,b'\xb8'+struct.pack('<I',0x80800008),error,row['errorOffset'])
    equal('conversionLayouts',dict(bands=dict(legacyBandLimit=3,legacyBandOffset=44,currentBandOffset=48,bandStride=24,
        legacyCutSlots=2,currentCutSlots=3,legacyBypassMaximum=7,currentBypassMaximum=15,crossRevisionRequiresSpecialLink=False),
        peak=dict(legacyReservedOffsets=[24,28],currentExtraAmplitudeOffset=24,currentLinkOffset=28,crossRevisionLink='special equals one')),
        contract['conversionLayouts'])
    # This cross-revision path proceeds directly from link admission to pair
    # admission; unlike the old-to-old route it has no special/link comparison.
    row=contract['bandCrossRevisionLinkStore'];at=row['offset']
    raw=bytes.fromhex('89460c418b461483f801')
    equal('bandCrossRevisionNoSpecialLink',raw,bodies['convertBands'][at:at+len(raw)],at)
    row=contract['peakCrossRevisionFields'];at=row['offset'];raw=bytes.fromhex('33c0f30f11471483fe018947180f94c0')
    equal('peakCrossRevisionExtraAndLink',raw,bodies['convertPeak'][at:at+len(raw)],at)
    paths=contract['peakLoops'];equal('loopRoles',{'legacy','current'},set(paths));tokens={}
    removed_grammar=dict(legacyModeRead='8b4608',legacyPowerBase='410f28c2',legacyModeStore='894348',legacyLinkZero='896b4c',
        currentPowerBase='410f28c2',currentAmplitudeBase='410f28c2',currentAmplitudeRead='f30f104e18',
        currentAmplitudeScale='f3410f59c9',currentAmplitudeStore='f30f1184bbe0000000')
    equal('removedRoles',set(removed_grammar)|{'currentAmplitudePower'},set(row['role'] for path in paths.values() for row in path['removed']))
    for name,path in paths.items():
        try:tokens[name]=_loop_tokens(bodies['applyPeak'],dynamics_contract['methods']['applyPeak'],path)
        except (ValueError,IndexError,KeyError,struct.error) as error:raise EffectUpdateError('masteringLegacy','loopProgram:'+name,path['start'],'complete normalized loop framing and joins',str(error)) from error
        for row in path['removed']:
            at=row['offset'];role=row['role'];raw=bodies['applyPeak'][at:at+row['byteLength']]
            if role=='currentAmplitudePower':
                matches=[p for p in dynamics_contract['methods']['applyPeak']['program'] if p['offset']==at]
                equal('extraPowerRoleCount',1,len(matches),at)
                equal('extraPowerRole',('e8','external','powerHelper'),tuple(matches[0][k] for k in ('prefixHex','targetKind','target')),at)
            else:equal('removed:'+role,bytes.fromhex(removed_grammar[role]),raw,at)
    equal('peakLoopCorrespondence',tokens['current'],tokens['legacy'])
    controls=contract['controlOffsets']
    grammar=dict(legacyLinkSeed=('applyPeak','33ed'),currentModeAndLink=('applyPeak','8941488b421c89414c'),
        legacyBandThresholdRead=('convertBands','f3430f1044fe2c'),legacyBandThresholdStore=('convertBands','f3420f1144fe2c'),
        crossBandThresholdRead=('convertBands','f3430f1044fe2c'),crossBandThresholdStore=('convertBands','f30f1144de30'),
        legacyBandIndex=('convertBands','4c8d3c5b'),crossBandIndex=('convertBands','4c8d3c40'),
        currentToSharedAllocation=('applyPeak','e9d8fdffff'),modeDispatch=('processModes','418b4a4885c9746c83e901743f83f901740a'),
        delayedStateBase=('processModes','498d4a50'),delayedSavedBase=('delayedKernel','488bd9'),
        delayedAmplitudeRead=('delayedKernel','0f108c8390000000'),delayedAmplitudeCapture=('delayedKernel','0f118cd510010000'),
        delayedAmplitudeMultiply=('delayedKernel','420f59accd10010000'))
    equal('controlRoles',set(grammar),set(controls))
    for name,(method,hex_value) in grammar.items():
        row=controls[name];at=row['offset'];raw=bytes.fromhex(hex_value)
        equal('controlMethod:'+name,method,row['method'],at);equal('control:'+name,raw,bodies[method][at:at+len(raw)],at)
    equal('currentFormats',True,dynamics['currentBandConversionProven'] and dynamics['currentPeakConversionProven'])
    default=profiles_contract['defaultRows']['peak'];words=default['rawWords']
    equal('storedDefaultMode',0,words[3]);equal('defaultModeDeclaration',0,contract['defaultPeakMode'])
    equal('defaultArguments',True,profiles['legacyDefaultApplicationArgumentsProven'])
    active=contract['bandActiveProgram'];equal('activeBandPointer',100,active['statePointerOffsetWithinBand'])
    equal('activeBandConstants',{'7':1.,'8':-2.2,'9':0.,'11':-440.0000305175781,'12':.05,'13':10.,'14':.5},active['constantRegisters'])
    band=bodies['applyBands'];method=dynamics_contract['methods']['applyBands']
    setup_grammar=dict(stateAlias='488bf9',parameterAlias='488bda',frequencyPointer='4c8d5140',frequencyRetain='4d8bfa',
        groupSetup='418bc54869f0700200004c8d34404c897d704881c64c0e000048c7442430030000004803f74c8d2440',
        groupLoop='4883c61048836c2430010f85ddfbffff',zeroTime='450f57c9')
    equal('activeBandSetupRoles',set(setup_grammar),set(active['setupControls']))
    for role,encoded in setup_grammar.items():
        at=active['setupControls'][role];raw=bytes.fromhex(encoded);equal('bandActiveSetup:'+role,raw,band[at:at+len(raw)],at)
    expected_roles={'7':'scalarUnity','8':'timeFactor','11':'powerTimeFactor','12':'controlScale','13':'controlBase','14':'scalarHalf'}
    equal('activeBandConstantRoles',set(expected_roles),set(active['constantLoads']))
    for index,role in expected_roles.items():
        at=active['constantLoads'][index];steps=[p for p in method['program'] if p['offset']==at and 'targetKind' in p]
        equal('bandActiveConstantCount:'+role,1,len(steps),at);equal('bandActiveConstantRole:'+role,('data',role),(steps[0]['targetKind'],steps[0]['target']),at)
        prefix=bytes.fromhex('f3'+('44' if int(index)>=8 else '')+'0f10'+format(0x05+8*(int(index)&7),'02x'))
        equal('bandActiveConstantRegister:'+role,prefix,band[at:at+len(prefix)],at)
    for attack_zero in (False,True):
        for release_zero in (False,True):
            try:actual=_band_scalar_program(band,method,active,attack_zero,release_zero)
            except (ValueError,IndexError,KeyError,struct.error) as error:raise EffectUpdateError('masteringLegacy','bandActiveProgram',active['start'],'complete four-channel arithmetic and state stores',str(error)) from error
            equal('bandActiveExpressions',_expected_band_active(attack_zero,release_zero),actual,active['start'])
    inactive=contract['bandInactiveProgram'];equal('inactiveBandPointer',436,inactive['statePointerOffsetWithinBand'])
    equal('inactiveBandConstants',{'6':-22.,'7':1.,'11':-440.0000305175781},inactive['constantRegisters'])
    inactive_setup=dict(admittedEntry='83fa040f836710000041b90200000041ba04000000eb04',
        emptyCountFrequency='4c8d7940',groupSetup='442bd28bc24869f070020000458bf24881c69c0f00004803f74533ed',
        bandSetup='488bde4d8be1',groupLoop='4883c3184983ec010f85cafbffff',
        bandLoop='4881c67002000041b9020000004983ee010f85a3fbffff',sharedTail='e9ca0b0000')
    equal('inactiveBandSetupRoles',set(inactive_setup),set(inactive['setupControls']))
    for role,encoded in inactive_setup.items():
        at=inactive['setupControls'][role];raw=bytes.fromhex(encoded);equal('bandInactiveSetup:'+role,raw,band[at:at+len(raw)],at)
    at=inactive['releaseConstantLoad'];steps=[p for p in method['program'] if p['offset']==at and 'targetKind' in p]
    equal('bandInactiveReleaseRoleCount',1,len(steps),at)
    equal('bandInactiveReleaseRole',('data','inactiveReleaseFactor'),(steps[0]['targetKind'],steps[0]['target']),at)
    equal('bandInactiveReleaseRegister',bytes.fromhex('f30f1035'),band[at:at+4],at)
    try:actual=_band_scalar_program(band,method,inactive,state_base=3)
    except (ValueError,IndexError,KeyError,struct.error) as error:raise EffectUpdateError('masteringLegacy','bandInactiveProgram',inactive['start'],'complete six-channel arithmetic and state stores',str(error)) from error
    equal('bandInactiveExpressions',_expected_band_inactive(),actual,inactive['start'])
    crossover=contract['bandCrossoverProgram']
    crossover_setup=dict(frame='488bc44c894820448940185553574154488d68984881ec480100004d8be1488bda488bf9',
        countRead='8b520841b902000000',bandIndexZero='33c0448be885d20f84fa050000',
        descriptorHeader='c744244000100101c744244418000000c7442450f4fd343f',
        frequencySave='4c895570',outerLoop='8b574841ffc5443bea731e4c8ba58800000041b902000000448b85800000004d8bd733c0e954faffff',
        conversionError='b805008080')
    equal('bandCrossoverSetupRoles',set(crossover_setup),set(crossover['setupControls']))
    for role,encoded in crossover_setup.items():
        at=crossover['setupControls'][role];raw=bytes.fromhex(encoded);equal('bandCrossoverSetup:'+role,raw,band[at:at+len(raw)],at)
    equal('bandCrossoverErrorJoin',crossover['setupControls']['conversionError'],crossover['errorExit'])
    paths=0
    for count in range(1,4):
        for index in range(count):
            expected=_expected_band_crossover(crossover,count,index)
            selections=[(None,0)]+[(n,code) for n in range(len(expected['calls'])) for code in (1,0x80004005)]
            for fail_call,error_code in selections:
                try:actual=_band_crossover_program(band,method,crossover,count,index,fail_call,error_code)
                except (ValueError,IndexError,KeyError,struct.error) as error:raise EffectUpdateError('masteringLegacy','bandCrossoverProgram',crossover['start'],'complete symbolic cutoff/argument/destination joins and error paths',str(error)) from error
                equal('bandCrossoverPaths',_expected_band_crossover(crossover,count,index,fail_call),actual,crossover['start']);paths+=1
    return dict(status='validated',evidenceBoundary='conditional',legacyControlGuardsAndLayoutsProven=True,
        legacyToCurrentBandSpecialLinkEnforced=False,peakApplicationLoopCorrespondenceProven=True,
        matchedPeakLoopInstructions=len(tokens['legacy']),legacyPeakLinkForcedZero=True,
        legacyPeakExtraAmplitudeRetained=True,currentPeakExtraAmplitudeWritten=True,
        extraAmplitudeUsedByMode=2,storedPeakDefaultMode=0,storedPeakDefaultDoesNotUseExtraAmplitude=True,
        normalUpdateUsesCurrentRecords=True,legacyActiveBandStateArithmeticProven=True,legacyActiveBandMappedFields=9,
        legacyActiveBandChannelCopies=12,legacyActiveBandTimeZeroOrUnorderedPathsProven=True,
        legacyInactiveBandStateArithmeticProven=True,legacyInactiveBandMappedFields=11,legacyInactiveBandChannelCopies=12,
        legacyInactiveBandAttackEqualsPowerCoefficient=True,completeLegacyBandArithmeticProven=False,
        legacyBandCrossoverRoutingProven=True,legacyBandCrossoverPaths=paths,legacySingleBandFilterCountRetainedUnused=True,
        legacyFilterConversionFailureStopsApplication=True,legacyFilterConversionFailureResult=0x80800005,
        wholeHelperParityProven=False,runtimeLegacyModeTwoReachabilityProven=False,runtimeInvocationObserved=False,
        meaningBoundary=contract['meaningBoundary'])


def check_mastering_legacy_native_inputs(game_root:Path):
    from scripts.webui.audio.semantics.wwise_effect_native import check_effect_native_extension
    from scripts.webui.audio.semantics.wwise_mastering_dynamics import load_mastering_dynamics_contract,validate_mastering_dynamics_effect_context
    from scripts.webui.audio.semantics.wwise_mastering_profiles import load_mastering_profiles_contract,validate_mastering_profiles
    from scripts.webui.audio.semantics.wwise_mastering_revisions import load_mastering_revisions_contract,validate_mastering_revisions
    def validate(parent,base,read):
        d=load_mastering_dynamics_contract();dynamics=validate_mastering_dynamics_effect_context(parent,base,read)
        revisions=validate_mastering_revisions(load_mastering_revisions_contract(),parent['nativeInputs'],d,dynamics,read)
        p=load_mastering_profiles_contract();profiles=validate_mastering_profiles(p,parent['nativeInputs'],d,dynamics,base,read)
        return validate_mastering_legacy(load_mastering_legacy_contract(),parent['nativeInputs'],d,dynamics,revisions,p,profiles,read)
    return check_effect_native_extension(game_root,evidence_key='legacy',validate=validate)
