"""Prove the packed crossover helper's tiny pair and finite fast sine path.

Both selector branches use the same rounded SSE arithmetic in this admitted
path. Large-argument reduction and exceptional-lane callbacks remain separate.
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
def load_mastering_trigonometry_contract():
    return json.loads((CONTRACTS_DIR/'wwise_mastering_trigonometry_native.json').read_text(encoding='utf-8'))


def _fast_program(body,row,rva,constants):
    at=row['start'];registers={index:('input',) for index in row['inputRegisters']};bound=None;mask=None
    skips={p['offset']:bytes.fromhex(p['bytesHex']) for p in row['nonNumeric']}
    def take(n):
        nonlocal at
        if at+n>len(body):raise ValueError('truncated fast-vector instruction')
        raw=body[at:at+n];at+=n;return raw
    def value(index):
        if index not in registers:raise ValueError('uninitialized fast-vector register')
        return registers[index]
    for _ in range(96):
        if at==row['end']:return value(10),bound,mask
        if at>row['end']:raise ValueError('fast-vector path overruns its extent')
        if at in skips:
            raw=skips[at]
            if take(len(raw))!=raw:raise ValueError('non-numeric fast-path instruction differs')
            continue
        begin=at;prefix=0;rex=0
        if body[at]==0x66:prefix=take(1)[0]
        if 0x40<=body[at]<=0x4f:rex=take(1)[0]&15
        if rex&8:raise ValueError('unexpected vector REX.W')
        if take(1)!=b'\x0f':raise ValueError(f'unadmitted vector opcode +{begin:#x}')
        opcode=take(1)[0];modrm=take(1)[0];mode=modrm>>6;reg=((modrm>>3)&7)|((rex&4)<<1);rm=(modrm&7)|((rex&1)<<3)
        if opcode==0x72 and prefix==0x66:
            if mode!=3 or reg!=6 or take(1)!=b'\x1f':raise ValueError('unadmitted quadrant-sign shift')
            registers[rm]=('shiftBitsLeft',value(rm),31);continue
        if mode==3:source=value(rm)
        elif mode==0 and modrm&7==5 and not rex&1:
            displacement=int.from_bytes(take(4),'little',signed=True)
            extra=1 if opcode==0xc2 else 0;target=rva+at+extra+displacement
            if target not in constants:raise ValueError('unjoined fast-vector constant')
            source=('constant',constants[target])
        else:raise ValueError('unadmitted fast-vector address')
        if opcode in (0x10,0x28) and not prefix:registers[reg]=source;continue
        if opcode==0x50 and not prefix:
            if mode!=3 or reg!=0 or source!=bound:raise ValueError('range mask is not read into EAX')
            mask=source;continue
        if opcode==0xc2 and not prefix:
            if take(1)!=b'\x06':raise ValueError('unadmitted packed range predicate')
            bound=('greaterOrUnordered',value(reg),source);registers[reg]=bound;continue
        operations={0x54:'bitAnd',0x55:'bitAndNot',0x57:'bitXor',0x58:'addFloat32',0x59:'multiplyFloat32',0x5c:'subtractFloat32'}
        if opcode==0xef and prefix==0x66:operation='bitXor'
        elif not prefix and opcode in operations:operation=operations[opcode]
        else:raise ValueError(f'unadmitted fast-vector operation +{begin:#x}')
        registers[reg]=(operation,value(reg),source)
    raise ValueError('fast-vector instruction bound exceeded')


def _expected_fast():
    def const(role):return ('constant',role)
    def op(name,a,b):return (name,a,b)
    x=('input',);absolute=op('bitAnd',x,const('absoluteMask'));sign=op('bitAndNot',const('absoluteMask'),x)
    h=op('addFloat32',op('multiplyFloat32',const('inversePi'),absolute),const('roundBias'))
    n=op('subtractFloat32',h,const('roundBias'));r=absolute
    for role in ('piFirst','piSecond','piThird','piFourth'):r=op('subtractFloat32',r,op('multiplyFloat32',const(role),n))
    z=op('multiplyFloat32',r,r);signed_r=op('bitXor',r,('shiftBitsLeft',h,31))
    p=op('addFloat32',op('multiplyFloat32',const('polynomialNinth'),z),const('polynomialSeventh'))
    for role in ('polynomialFifth','polynomialThird'):p=op('addFloat32',op('multiplyFloat32',p,z),const(role))
    output=op('bitXor',op('addFloat32',signed_r,op('multiplyFloat32',op('multiplyFloat32',z,p),signed_r)),sign)
    return output,('greaterOrUnordered',absolute,const('fastMaximumAbsolute'))


def validate_mastering_trigonometry(contract,native_inputs,dynamics_contract,dynamics,read):
    def equal(check,expected,actual,offset=0):
        if expected!=actual:raise EffectUpdateError('masteringTrigonometry',check,offset,expected,actual)
    equal('schema','endfield.wwise-mastering-trigonometry-native-contract.v2',contract['schema'])
    equal('reviewStatus','reviewed',contract['status']);equal('boundary','conditional',contract['evidenceBoundary'])
    equal('inputs',native_inputs,contract['nativeInputs']);equal('parentInputs',native_inputs,dynamics_contract['nativeInputs']);equal('parentProof','validated',dynamics['status'])
    methods=contract['methods'];equal('methodSet',{'pair','dispatch','lowerSelector','higherSelector'},set(methods))
    equal('pairHelperJoin',dynamics_contract['externals']['packedTrigonometricHelper']['rva'],methods['pair']['rva'])
    bodies={}
    for name,row in methods.items():
        equal('methodExtent:'+name,True,type(row['bodyLength'])is int and 0<row['bodyLength']<=4096)
        raw=read(int(row['rva'],16),row['bodyLength']);equal('methodHash:'+name,row['bodySha256'],hashlib.sha256(raw).hexdigest());bodies[name]=raw
    values=dict(inversePi=.31830987334251404,roundBias=12582912.,piFirst=3.140625,piSecond=.0009675025939941406,
        piThird=1.5099067240953445e-7,piFourth=5.126688136514179e-12,polynomialNinth=2.605780537123792e-6,
        polynomialSeventh=-.00019809602235909551,polynomialFifth=.008333062753081322,polynomialThird=-.16666659712791443,
        fastMaximumAbsolute=10000.,tinyMaximumAbsolute=2**-13,halfPi=1.5707963705062866,pairUnity=1.)
    expected={role:struct.pack('<f',v)*(4 if role not in ('tinyMaximumAbsolute','halfPi','pairUnity') else 1) for role,v in values.items()}
    expected.update(absoluteMask=struct.pack('<4I',*([0x7fffffff]*4)),pairAbsoluteMask=struct.pack('<4I',0x7fffffff,0,0,0),pairHalf=struct.pack('<4f',.5,0,0,0))
    equal('constantSet',set(expected),set(contract['data']));constants={}
    for role,row in contract['data'].items():
        rva=int(row['rva'],16);raw=expected[role];equal('constantBytes:'+role,raw.hex(),row['bytesHex']);equal('constantRead:'+role,raw,read(rva,len(raw)));constants[rva]=role
    pair=bodies['pair'];dispatch=bodies['dispatch']
    pair_grammar=dict(readLow='f30f10d0',absolute='660fdb15',tinyCompare='0f2f15',tinyBranch='7215',
        prepareCosine='660fefc9f30f10ca',largePack='0f14c1',tinySquare='0f59d2',tinyHalf='0f5915',tinyUnity='f30f100d',tinySubtractAndPack='0f5cca0f14c1c3')
    equal('pairControlSet',set(pair_grammar),set(contract['pairControls']))
    for role,encoded in pair_grammar.items():
        at=contract['pairControls'][role];raw=bytes.fromhex(encoded);equal('pairControl:'+role,raw,pair[at:at+len(raw)],at)
    for role,row in contract['pairConstants'].items():
        at=row['offset'];prefix=bytes.fromhex(row['prefixHex']);end=at+len(prefix)+4
        equal('pairDataOpcode:'+role,prefix,pair[at:at+len(prefix)],at)
        equal('pairDataJoin:'+role,int(contract['data'][role]['rva'],16),int(methods['pair']['rva'],16)+end+struct.unpack_from('<i',pair,at+len(prefix))[0],at)
    equal('pairDataRoles',{'pairAbsoluteMask','tinyMaximumAbsolute','halfPi','pairHalf','pairUnity'},set(contract['pairConstants']))
    equal('largeCosineAdd',bytes.fromhex('f30f580d'),pair[0x1d:0x21],0x1d)
    equal('pairDispatchJump',b'\xeb',pair[0x28:0x29],0x28)
    equal('pairDispatchTarget',int(methods['dispatch']['rva'],16),int(methods['pair']['rva'],16)+0x2a+int.from_bytes(pair[0x29:0x2a],'little',signed=True),0x28)
    equal('selectorCompare',bytes.fromhex('833d'),dispatch[:2]);equal('selectorThreshold',2,dispatch[6])
    equal('selectorCellJoin',int(contract['selectorRva'],16),int(methods['dispatch']['rva'],16)+7+struct.unpack_from('<i',dispatch,2)[0])
    equal('selectorSignedGreaterOrEqual',bytes.fromhex('0f8d'),dispatch[7:9],7)
    equal('higherSelectorTarget',int(methods['higherSelector']['rva'],16),int(methods['dispatch']['rva'],16)+13+struct.unpack_from('<i',dispatch,9)[0],7)
    equal('lowerSelectorJump',b'\xe9',dispatch[13:14],13)
    equal('lowerSelectorTarget',int(methods['lowerSelector']['rva'],16),int(methods['dispatch']['rva'],16)+18+struct.unpack_from('<i',dispatch,14)[0],13)
    equal('fastRoles',{'lowerSelector','higherSelector'},set(contract['fastPrograms']))
    expression,bound=_expected_fast()
    for name,row in contract['fastPrograms'].items():
        nonnumeric=dict(alignedScratchPointer='4983e5c0',savedScratchPointer='4c89ac24',rangeMaskTest='85c0')
        equal('nonNumericRoles:'+name,{'alignedScratchPointer','savedScratchPointer'}|({'rangeMaskTest'} if name=='higherSelector' else set()),set(p['role'] for p in row['nonNumeric']))
        for item in row['nonNumeric']:
            role=item['role'];raw=bytes.fromhex(item['bytesHex']);prefix=bytes.fromhex(nonnumeric[role]);equal('nonNumericGrammar:'+role,prefix,raw[:len(prefix)],item['offset'])
            if role=='savedScratchPointer':equal('savedPointerExtent',8,len(raw),item['offset'])
            else:equal('nonNumericExtent:'+role,len(prefix),len(raw),item['offset'])
        try:actual,actual_bound,mask=_fast_program(bodies[name],row,int(methods[name]['rva'],16),constants)
        except (ValueError,IndexError,KeyError,struct.error) as error:raise EffectUpdateError('masteringTrigonometry','fastProgram:'+name,row['start'],'admitted vector expression and range mask',str(error)) from error
        equal('fastExpression:'+name,expression,actual,row['start']);equal('fastRange:'+name,bound,actual_bound,row['start']);equal('fastMask:'+name,bound,mask,row['start'])
        controls=contract['fastControls'][name]
        for role,item in controls.items():
            at=item['offset'];raw=bytes.fromhex(item['bytesHex']);equal('fastControl:'+name+':'+role,raw,bodies[name][at:at+len(raw)],at)
        equal('fastControlRoles:'+name,{'inputCapture','inputSeed','zeroExceptionalMask','rangeBranch','exceptionalMaskTest','exceptionalBranch','outputMove','return'},set(controls))
        literal=dict(inputCapture='440f28c0' if name=='lowerSelector' else '0f28d0',inputSeed='440f28c0' if name=='lowerSelector' else '440f28ca',
            zeroExceptionalMask='4533d2',exceptionalMaskTest='4585d2',outputMove='410f28c2')
        for role,encoded in literal.items():
            item=controls[role];raw=bytes.fromhex(encoded);equal('fastGrammar:'+name+':'+role,raw,bodies[name][item['offset']:item['offset']+len(raw)],item['offset'])
        item=controls['rangeBranch'];at=item['offset'];prefix=bytes.fromhex('85c00f85' if name=='lowerSelector' else '0f85');size=len(prefix)+4
        equal('rangeBranchGrammar:'+name,prefix,bodies[name][at:at+len(prefix)],at)
        equal('slowReductionJoin:'+name,row['slowEntry'],at+size+struct.unpack_from('<i',bodies[name],at+len(prefix))[0],at)
        item=controls['exceptionalBranch'];at=item['offset'];equal('exceptionalBranchGrammar:'+name,b'\x75',bodies[name][at:at+1],at)
        equal('exceptionalLaneJoin:'+name,row['exceptionalEntry'],at+2+int.from_bytes(bodies[name][at+1:at+2],'little',signed=True),at)
        item=controls['return'];at=item['offset'];equal('fastReturnGrammar:'+name,b'\x48\x81\xc4',bodies[name][at:at+3],at)
        equal('fastStackRestore:'+name,bodies[name][3:7],bodies[name][at+3:at+7],at)
        equal('fastReturn:'+name,b'\xc3',bodies[name][at+7:at+8],at)
    caller=contract['crossoverCaller'];equal('callerMethods',('filterConversion','filterCoefficients'),(caller['wrapperMethod'],caller['generatorMethod']))
    caller_bodies={}
    for name in (caller['wrapperMethod'],caller['generatorMethod']):
        row=dynamics_contract['methods'][name];body=read(int(row['rva'],16),row['bodyLength'])
        equal('callerMethodHash:'+name,row['bodySha256'],hashlib.sha256(body).hexdigest());caller_bodies[name]=body
    caller_grammar=dict(normalizedCutoff=('filterConversion','f30f10510c0f57c0418bc1f3480f2ac0f30f5ed00f2fd10f8691000000'),
        upperCutoffCompare=('filterConversion','0f2f15'),upperCutoffBranch=('filterConversion','0f8384000000'),
        generatorArgument=('filterCoefficients','0f28ca'),generatorZeroAndRetain=('filterCoefficients','0f57c08bfa488bd90f2978d80f28f3440f2940c8440f28c2440f2948b8'),
        generatorScalarCopy=('filterCoefficients','f30f10c1'))
    equal('callerControls',set(caller_grammar),set(caller['controls']))
    for name,(method,hex_value) in caller_grammar.items():
        at=caller['controls'][name];raw=bytes.fromhex(hex_value);equal('callerGrammar:'+name,raw,caller_bodies[method][at:at+len(raw)],at)
    for name,method,offset,kind,target in (('upperCutoff','filterConversion',caller['controls']['upperCutoffCompare'],'data','scalarHalf'),
        ('angleMultiply','filterCoefficients',caller['angleMultiply'],'data','angleScale'),
        ('helperCall','filterCoefficients',caller['helperCall'],'external','packedTrigonometricHelper'),
        ('generatorCall','filterConversion',caller['generatorCall'],'method','filterCoefficients')):
        steps=[p for p in dynamics_contract['methods'][method]['program'] if p['offset']==offset and 'targetKind' in p]
        equal('callerRelativeRoleCount:'+name,1,len(steps),offset);equal('callerRelativeRole:'+name,(kind,target),(steps[0]['targetKind'],steps[0]['target']),offset)
    for role,value in (('scalarHalf',.5),('angleScale',6.2831854820251465)):
        equal('callerConstant:'+role,struct.pack('<f',value),read(int(dynamics_contract['data'][role]['rva'],16),4))
    maximum_ratio=struct.unpack('<f',struct.pack('<I',struct.unpack('<I',struct.pack('<f',.5))[0]-1))[0]
    maximum_angle=struct.unpack('<f',struct.pack('<f',maximum_ratio*6.2831854820251465))[0]
    maximum_shifted=struct.unpack('<f',struct.pack('<f',maximum_angle+values['halfPi']))[0]
    equal('callerFastDomain',True,0<maximum_angle<maximum_shifted<values['fastMaximumAbsolute'])
    return dict(status='validated',evidenceBoundary='conditional',tinyPairArithmeticProven=True,tinyAbsoluteThreshold=2**-13,
        pairRoles=['inputSineApproximation','absoluteInputShiftedSineApproximation'],largeCosineArgument='float32(abs(input)+storedHalfPi)',
        selectorComparison='signed word >= 2 chooses higher selector path',actualCpuSelectorInitializationProven=False,
        bothFastVectorExpressionsProven=True,fastMaximumAbsolute=10000.,allPackedLanesMustBeAdmitted=True,
        quadrantSignUsesRoundedFloatBits=True,piSplitTerms=4,polynomialHighestPower=9,allArithmeticRoundsFloat32=True,
        authenticatedCrossoverCallerFastDomainProven=True,crossoverNormalizedCutoffRange='strictly between zero and one half',
        crossoverUnusedArgumentLanesZero=True,crossoverMaximumPackedAbsolute=maximum_shifted,
        largeArgumentReductionProven=False,exceptionalLaneHandlingProven=False,wholeSineCosineParityProven=False,
        namedHelperIdentityProven=False,runtimeInvocationObserved=False,meaningBoundary=contract['meaningBoundary'])


def check_mastering_trigonometry_native_inputs(game_root:Path):
    from scripts.webui.audio.semantics.wwise_effect_native import check_effect_native_extension
    from scripts.webui.audio.semantics.wwise_mastering_dynamics import load_mastering_dynamics_contract,validate_mastering_dynamics_effect_context
    def validate(parent,base,read):
        dynamics=validate_mastering_dynamics_effect_context(parent,base,read)
        return validate_mastering_trigonometry(load_mastering_trigonometry_contract(),parent['nativeInputs'],load_mastering_dynamics_contract(),dynamics,read)
    return check_effect_native_extension(game_root,evidence_key='trigonometry',validate=validate)
