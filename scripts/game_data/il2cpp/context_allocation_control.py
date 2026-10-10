"""Complete anonymous context allocation/reservation body and clear tail.

Prove physical size/cursor/remaining, refill and node writes, globals and
restored clear-helper arguments. Allocation success, pointed storage, live
global callees, clear-helper result/effects and allocator protocol remain
conditions or open joins. This owner admits no serialized child/list/root.
"""
from __future__ import annotations
from scripts.game_data.il2cpp.integer_context_memory import decode_context_memory_instructions
from scripts.game_data.il2cpp.owned_partition import BranchGrammar, owned_windows, checked_rows, check_byte_partition, rip_load
from scripts.game_data.il2cpp.relation_control import transfer, explicit_memory_effect
from scripts.game_data.il2cpp.relation_import_control import _memory
from scripts.game_data.il2cpp.integer_addressing import decode_lea_address

LABEL = 'contextAllocationControl'


def instruction_transfer(row):
    raw = bytes.fromhex(row['bytes'])
    if raw == b'\xff\xd0': return {'kind':'registerCall','register':'rax'}
    if raw == b'\xcc': return {'kind':'trap'}
    return transfer(row)


def memory_effect(row):
    if 'memoryDestinationSubtractOperation' in row:
        return {'kind':'memoryDestinationSubtractOperation','facts':row['memoryDestinationSubtractOperation']}
    return explicit_memory_effect(row)


def _rows(index, c):
    owned, pieces, windows = owned_windows(index, c, LABEL)
    if c['paddingWindows']:
        raise ValueError(LABEL+'.unreviewed-padding')
    rows = []
    for category, _, start, raw in windows:
        if category != 'codeWindows': raise ValueError(LABEL+'.unreviewed-piece')
        rows.extend(checked_rows(decode_context_memory_instructions(index.mapper,raw,start),raw,LABEL))
    check_byte_partition(owned,pieces,LABEL); rows.sort(key=lambda r:int(r['va'],16))
    if len(rows) != c['checkedInstructionCount']: raise ValueError(LABEL+'.instruction-count')
    return rows


def _graph(rows, base, c):
    starts = {int(r['va'],16) for r in rows}; edges = {}; calls = []; branches = []; tails = []; stores = []; traps = []
    if len(starts) != len(rows): raise ValueError(LABEL+'.duplicate-start')
    for row in rows:
        at = int(row['va'],16); f = instruction_transfer(row); kind = f['kind']; targets = []
        if kind in ('jump','conditional'):
            if f['target'] not in starts:
                if kind != 'jump' or f['target'] != base+c['clearTailTargetRva']:
                    raise ValueError(LABEL+'.unreviewed-external-transfer')
                tails.append({'siteRva':at-base,'targetRva':f['target']-base})
            else:
                targets.append(f['target'])
                branches.append({'siteRva':at-base,'kind':kind,'targetRva':f['target']-base,
                    **({'conditionCode':f['conditionCode']} if kind=='conditional' else {})})
        if kind in ('next','call','registerCall','conditional'):
            targets.append(at+len(bytes.fromhex(row['bytes'])))
        if kind in ('call','registerCall'):
            if kind=='call' and any(base+w['startRva']<=f['target']<base+w['endRva'] for w in c['ownedWindows']):
                raise ValueError(LABEL+'.call-into-owned-program')
            calls.append({'siteRva':at-base,'kind':kind,
                **({'targetRva':f['target']-base} if kind=='call' else {'register':f['register']})})
        elif kind == 'trap': traps.append(at-base)
        elif kind not in ('next','jump','conditional'):
            raise ValueError(LABEL+'.unreviewed-transfer-kind')
        if any(t not in starts for t in targets): raise ValueError(LABEL+'.continuation-boundary')
        edges[at] = set(targets)
        effect = memory_effect(row)
        if effect: stores.append({'siteRva':at-base,**effect})
    for key, actual in (('calls',calls),('localBranches',branches),('tailCalls',tails),('trapRvas',traps),('explicitStores',stores)):
        if c[key] != actual: raise ValueError(f'{LABEL}.{key}: expected={str(c[key])[:160]} actual={str(actual)[:240]}')
    reached = set(); pending = [base+c['entryRva']]
    while pending:
        at = pending.pop()
        if at in reached: continue
        reached.add(at); pending.extend(edges[at]-reached)
    if reached != starts: raise ValueError(LABEL+'.uncovered-owned-instructions')
    before = {base+c['entryRva']:0}; pending = [base+c['entryRva']]; by_at = {int(r['va'],16):r for r in rows}
    while pending:
        at = pending.pop(); row = by_at[at]; text = row['text']; head,_,rest = text.partition(' '); depth = before[at]
        if head in ('push','pop'):
            if rest == 'rsp': raise ValueError(LABEL+'.dynamic-rsp')
            depth += -8 if head=='push' else 8
        elif rest.split(',')[0] == 'rsp':
            if head not in ('add','sub') or not rest.startswith('rsp, 0x'): raise ValueError(LABEL+'.unreviewed-rsp-write')
            amount = int(rest.split(', ')[1],16); depth += amount if head=='add' else -amount
        f = instruction_transfer(row)
        if f['kind'] in ('call','registerCall') and ((8+depth)%16 or -depth < 32):
            raise ValueError(LABEL+'.call-shadow-or-alignment')
        if f['kind']=='jump' and f['target']==base+c['clearTailTargetRva'] and depth != 0:
            raise ValueError(LABEL+'.unrestored-tail-frame')
        for t in edges[at]:
            if t in before and before[t] != depth: raise ValueError(LABEL+'.inconsistent-stack-join')
            if t not in before: before[t] = depth; pending.append(t)
    return {'checkedInstructions':len(rows),'checkedLocalBranches':len(branches),'calls':calls,
            'tailCalls':tails,'explicitStoreSites':len(stores),'trapSites':traps,
            'staticPossibleReachableInstructions':len(reached)}


def _compare(g, register, receiver, offset):
    row = g.row(); f = row.get('memoryRegisterComparisonOperation',{}); a = f.get('memoryAddress',{})
    if (f.get('bits'),f.get('register'),f.get('memoryReadBytes'),f.get('memoryIsLeftOperand'),
        a.get('base'),a.get('index'),a.get('displacement')) != (64,register,8,True,receiver,None,offset):
        g.fail('qword-memory-comparison',(register,receiver,offset),row)


def _lea(g, register, *, receiver=None, index=None, scale=1, offset=0, absolute=None):
    row = g.row(); raw = bytes.fromhex(row['bytes']); decoded = decode_lea_address(raw,0,int(row['va'],16))
    f = decoded[0]['addressOperation'] if decoded is not None and decoded[1]==len(raw) else {}
    if (f.get('destination'),f.get('destinationBits'),f.get('readsMemory')) != (register,64,False):
        g.fail('lea-register',register,row)
    expected = (True,absolute) if absolute is not None else (False,receiver,index,scale,offset)
    actual = (f.get('ripRelative'),f.get('absoluteAddress')) if absolute is not None else (
        f.get('ripRelative'),f.get('base'),f.get('index'),f.get('scale'),f.get('displacement'))
    if actual != expected: g.fail('lea-address',expected,row)


def _indirect(g):
    row = g.take('call rax')
    if instruction_transfer(row) != {'kind':'registerCall','register':'rax'}:
        g.fail('global-register-call','original FF D0',row)


def _mark(g, base, c, name):
    if int(g.rows[g.cursor]['va'],16) != base+c['labels'][name]:
        g.fail('label:'+name,c['labels'][name],g.rows[g.cursor])
    g.mark(name)


def validate_context_allocation_control(index, c):
    base = index.pe.image_base; rows = _rows(index,c); summary = _graph(rows,base,c)
    frame = c['frame']; fields = c['fields']; constants = c['constants']; labels = c['labels']
    alignment = constants['reservationAlignment']; refill_alignment = constants['refillAlignment']
    if (alignment != 8 or refill_alignment <= 0 or refill_alignment & (refill_alignment-1) or
        set(frame)!={'bytes','restoreDelta','savedEntryOffsets','nodeOwnerArgumentOffset','nodeZeroArgumentOffset'} or
        any(type(v)!=int or v<0 for k,v in frame.items() if k!='savedEntryOffsets') or frame['bytes']<48 or frame['bytes']%16 or
        frame['restoreDelta']!=frame['bytes']+24 or frame['savedEntryOffsets']!=[8,16,24]):
        raise ValueError(LABEL+'.alignment-or-frame-declarations')
    primary = [r for r in rows if base+c['entryRva']<=int(r['va'],16)<base+c['primaryEndRva']]
    cold = [r for r in rows if int(r['va'],16)>=base+c['coldEntryRva']]
    if len(primary)+len(cold)!=len(rows): raise ValueError(LABEL+'.program-partition')
    g = BranchGrammar(primary,label=LABEL+'.primary')
    for register,offset in zip(('rbx','rbp','rsi'),frame['savedEntryOffsets']):
        _memory(g,'store',register,8,base='rsp',displacement=offset)
    g.take('push rdi','push r14','push r15',f'sub rsp, 0x{frame["bytes"]:x}',
           'mov r14, r8','mov rbp, rdx','mov r15, rcx','mov rbx, rdx','imul rbx, r8',
           f'add rbx, 0x{alignment-1:x}',f'and rbx, {hex(-alignment)}')
    _memory(g,'load','rax',8,base='rcx'); _memory(g,'load','r9',8,base='rax',displacement=fields['rootOwner'])
    _memory(g,'load','rsi',8,base='r9',displacement=fields['ownerBlock'])
    _compare(g,'rbx','rsi',fields['remaining']); g.branch('jb','refill')
    _mark(g,base,c,'reserve'); _memory(g,'load','rcx',8,base='rsi',displacement=fields['cursor'])
    _lea(g,'rdx',receiver='rbx',index='rcx'); _memory(g,'store','rdx',8,base='rsi',displacement=fields['cursor'])
    row = g.row(); f = row.get('memoryDestinationSubtractOperation',{}); a = f.get('destinationAddress',{})
    if (f.get('bits'),f.get('sourceRegister'),f.get('memoryReadBytes'),f.get('memoryWriteBytes'),
        a.get('base'),a.get('index'),a.get('displacement')) != (64,'rbx',8,8,'rsi',None,fields['remaining']):
        g.fail('remaining-qword-subtraction','remaining -= rounded reservation',row)
    g.take('imul rbp, r14','mov r8, rbp','xor edx, edx')
    for register,offset in zip(('rbx','rbp','rsi'),frame['savedEntryOffsets']):
        _memory(g,'load',register,8,base='rsp',displacement=offset+frame['restoreDelta'])
    g.take(f'add rsp, 0x{frame["bytes"]:x}','pop r15','pop r14','pop rdi')
    tail = g.branch('jmp')
    if tail['target']!=base+c['clearTailTargetRva']: g.fail('clear-tail',c['clearTailTargetRva'],tail)
    _mark(g,base,c,'refill'); row = g.row(); raw = bytes.fromhex(row['bytes'])
    if (len(raw)!=7 or raw[:2]!=b'\x80\x3d' or raw[-1]!=0 or
        int(row['va'],16)+7+int.from_bytes(raw[2:6],'little',signed=True)!=base+c['refillModeGlobalRva']):
        g.fail('global-byte-zero-test',c['refillModeGlobalRva'],row)
    g.branch('jne','alternateRefill')
    _mark(g,base,c,'newBlock'); rip_load(g,'rax',base+c['allocationFunctionGlobalRva'])
    g.take(f'mov ecx, 0x{constants["blockMetadataBytes"]:x}'); _indirect(g); g.take('mov rsi, rax')
    _lea(g,'rax',receiver='rbx',offset=refill_alignment-1); row = g.row(); f = row.get('accumulatorAndOperation',{})
    if (f.get('destinationRegister'),f.get('bits'),f.get('encodedImmediateBits'),f.get('signExtendsImmediateTo64'),
        f.get('immediateValue')) != ('rax',64,32,True,-refill_alignment):
        g.fail('refill-unsigned-rounding-mask',-refill_alignment,row)
    g.take(f'mov edi, 0x{constants["minimumBlockBytes"]:x}','cmp rax, rdi'); row = g.row()
    if row.get('conditionalMove')!={'condition':'a','destination':'rdi','source':'rax','width':64}:
        g.fail('unsigned-refill-size-selection','CMOVA RDI,RAX',row)
    rip_load(g,'rax',base+c['allocationFunctionGlobalRva']); g.take('mov rcx, rdi'); _indirect(g)
    for offset,register in ((fields['cursor'],'rax'),(fields['buffer'],'rax'),
                            (fields['remaining'],'rdi'),(fields['total'],'rdi')):
        _memory(g,'store',register,8,base='rsi',displacement=offset)
    g.take('xor ecx, ecx'); _memory(g,'store','rcx',8,base='rsi')
    _memory(g,'load','rdi',8,base='r15'); g.take(f'mov rax, 0x{constants["nodeCountLimit"]:x}')
    _compare(g,'rax','r15',fields['nodeCount']); g.branch('je','nodeFailure')
    _memory(g,'store','r15',8,base='rsp',displacement=frame['nodeOwnerArgumentOffset'])
    _memory(g,'store','rcx',8,base='rsp',displacement=frame['nodeZeroArgumentOffset'])
    g.take(f'mov ecx, 0x{constants["nodeBytes"]:x}'); g.call(base+c['nodeAllocationTargetRva'])
    _memory(g,'store','rsi',8,base='rax',displacement=fields['nodePayload']); row = g.row()
    f = row.get('memoryStepOperation',{}); a = f.get('destinationAddress',{})
    if (f.get('operation'),f.get('bits'),f.get('memoryWriteBytes'),a.get('base'),a.get('displacement'))!=('inc',64,8,'r15',fields['nodeCount']):
        g.fail('node-count-qword-increment','INC receiver node count',row)
    _memory(g,'load','rcx',8,base='rdi',displacement=fields['nodePrevious'])
    _memory(g,'store','rdi',8,base='rax'); _memory(g,'store','rcx',8,base='rax',displacement=fields['nodePrevious'])
    _memory(g,'store','rax',8,base='rdi',displacement=fields['nodePrevious']); _memory(g,'store','rax',8,base='rcx')
    g.branch('jmp','reserve'); g.labels.update(alternateRefill=base+labels['alternateRefill'],nodeFailure=base+labels['nodeFailure']); g.finish()
    h = BranchGrammar(cold,label=LABEL+'.cold'); _mark(h,base,c,'alternateRefill')
    h.call(base+c['alternateRefillTargetRva']); h.take('mov rsi, rax','test rax, rax'); h.branch('jne','reserve')
    h.branch('jmp','newBlock'); _mark(h,base,c,'nodeFailure')
    _lea(h,'rcx',absolute=base+c['nodeFailureArgumentGlobalRva']); h.call(base+c['nodeFailureTargetRva'])
    h.take('int3'); h.labels.update(reserve=base+labels['reserve'],newBlock=base+labels['newBlock']); h.finish()
    domain = c['selectedCallerDomain']
    if domain!={'unsignedCountBits':8,'strideBytes':8}: raise ValueError(LABEL+'.caller-domain')
    maximum = ((1 << domain['unsignedCountBits'])-1)*domain['strideBytes']
    if maximum+alignment-1 >= 1 << 64 or domain['strideBytes']%alignment:
        raise ValueError(LABEL+'.caller-product-or-alignment')
    return {**summary,'completeOwnedReservationRefillNodeAndClearTailProgramChecked':True,
        'ownedBytes':sum(w['endRva']-w['startRva'] for w in c['ownedWindows']),
        'reservationExpression':f'uint64(uint64(count * stride) + {alignment-1}) AND uint64({-alignment})',
        'clearLengthExpression':'uint64(original count * original stride)',
        'selectedCallerProductMaximum':maximum,'selectedCallerProductAndReservationEqualWithoutArithmeticOverflow':True,
        'existingRemainingUnsignedGuardAndCursorRemainingWritesProved':True,
        'refillGlobalCalleeSizeAndBlockMetadataWritesProved':True,'nodeLinksCounterGuardAndColdTrapProved':True,
        'clearTailRestoresFrameRegistersAndForwardsOldCursorZeroAndUnroundedProductProved':True,
        'sameLoadedAllocationCellHasTwoFreshReadsProved':True,
        'allocationSuccessOrNonzeroReturnProved':False,'liveAllocationCalleeSelected':False,
        'initializedAllocatorProtocolOrValidCapacityProved':False,
        'clearHelperResultEqualsOldCursorProved':False,'clearHelperStoresOrVisibilityProved':False,
        'incomingSlotContentsUnchangedProved':False,'recursiveTerminationProved':False,
        'callbackCursorEqualityProved':False,'positiveListAdmitted':False,'wholeRootAdmitted':False,
        'conditions':c['conditions']}
