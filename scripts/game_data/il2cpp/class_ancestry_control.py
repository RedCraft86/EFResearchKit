"""Selected named class getters and the complete has-parent byte program.

Export names anchor physical fields and a direct ancestry-array consumer.
Normal ABI returns, valid storage and coherent class state are conditions;
no live receiver identity, class initialization or Buff root is inferred.
"""
from __future__ import annotations
from collections import deque
from scripts.game_data.il2cpp.integer_addressing import decode_lea_address
from scripts.game_data.il2cpp.integer_context_memory import decode_context_memory_instructions
from scripts.game_data.il2cpp.memory_moves import decode_memory_move
from scripts.game_data.il2cpp.owned_partition import (
    BranchGrammar, check_byte_partition, checked_rows, owned_windows, window_bytes)
from scripts.game_data.il2cpp.relation_control import transfer, explicit_memory_effect
from scripts.game_data.il2cpp.relation_import_control import (
    _graph, _memory, _lea, _branch, _import, _exchange, _step, _address)

LABEL = 'classAncestryControl'
GETTERS = {
    'il2cpp_class_get_name': ('name', 'load'),
    'il2cpp_class_get_namespace': ('namespace', 'load'),
    'il2cpp_class_get_parent': ('parent', 'load'),
    'il2cpp_class_get_element_class': ('elementClass', 'load'),
    'il2cpp_class_get_type': ('type', 'address'),
}


def _getters(index, c, exports):
    selected = {r['symbolName']: r for r in exports['selectedExports']}
    if set(selected) != set(GETTERS) | {'il2cpp_class_has_parent'}:
        raise ValueError(LABEL + '.selected-export-set')
    rows = []
    if len(c['getters']) != len(GETTERS):
        raise ValueError(LABEL + '.getter-count')
    seen = set()
    for f in c['getters']:
        name = f['symbolName']; role, operation = GETTERS.get(name, (None, None))
        if role is None or name in seen or f['fieldRole'] != role or f['operation'] != operation:
            raise ValueError(LABEL + '.getter-role')
        seen.add(name); e = selected[name]
        if e['isForwarder'] or f['entryRva'] != e['targetRva']:
            raise ValueError(LABEL + '.getter-export-entry')
        w = f['closedEntryWindow']; start = index.pe.image_base+f['entryRva']
        if w['startRva'] != f['entryRva'] or not 2 <= w['endRva']-w['startRva'] <= 16:
            raise ValueError(LABEL + '.getter-window')
        raw = window_bytes(index,start,index.pe.image_base+w['endRva'],w['sha256'],LABEL)
        offset = c['physicalFields'][role]
        decoder = decode_memory_move if operation == 'load' else decode_lea_address
        decoded = decoder(raw,0,start)
        if decoded is None or raw[decoded[1]:] != b'\xc3':
            raise ValueError(LABEL + '.getter-closed-load-or-address-return')
        fact = decoded[0]['memoryOperation' if operation == 'load' else 'addressOperation']
        address = fact['address'] if operation == 'load' else fact
        if operation == 'load':
            if (fact['direction'],fact['register'],fact['memoryBytes'],fact['registerBits']) != ('load','rax',8,64):
                raise ValueError(LABEL + '.getter-qword-result')
        elif (fact['destination'],fact['destinationBits'],fact['readsMemory']) != ('rax',64,False):
            raise ValueError(LABEL + '.getter-address-result')
        if (address['base'],address['index'],address['displacement'],address['ripRelative']) != ('rcx',None,offset,False):
            raise ValueError(LABEL + '.getter-receiver-field')
        rows.append({'symbolName':name,'fieldRole':role,'offset':offset,'operation':operation,
                     'closedEntryBytes':len(raw),'checkedInstructions':2,
                     'entryExecutionHasNoBranchCallOrMemoryWrite':True,
                     'physicalFunctionExtentOrPaddingProved':False})
    return rows


def _load_byte(g, register, base, displacement):
    row = g.row(); f = row.get('byteMemoryZeroExtensionOperation', {}); a = f.get('sourceAddress', {})
    if (f.get('destinationRegister'),f.get('sourceBits'),f.get('memoryReadBytes'),
        f.get('zeroExtendsTo64'),a.get('base'),a.get('index'),a.get('displacement')) != (
            register,8,1,True,base,None,displacement):
        g.fail('unsigned-byte-field',(register,base,displacement),row)


def _compare(g, bits, register, base, displacement, *, index=None, scale=1, memory_first=True):
    row = g.row(); f = row.get('memoryRegisterComparisonOperation', {}); a = f.get('memoryAddress', {})
    if (f.get('bits'),f.get('register'),f.get('memoryIsLeftOperand'),f.get('memoryReadBytes'),
        f.get('memoryWriteBytes'),a.get('base'),a.get('index'),a.get('scale'),a.get('displacement')) != (
            bits,register,memory_first,bits//8,0,base,index,scale,displacement):
        g.fail('physical-comparison',(bits,register,base,index,scale,displacement,memory_first),row)


def _byte_compare(g, base, displacement):
    row=g.row(); raw=bytes.fromhex(row['bytes'])
    # This selected form compares one receiver byte with AL; no REX or SIB.
    expected=b'\x38\x87'+displacement.to_bytes(4,'little',signed=True)
    if base!='rdi' or raw!=expected:
        g.fail('unsigned-depth-compare','CMP byte [RDI+disp32], AL',row)


def _frame(rows, edges, entry):
    by_at={int(r['va'],16):r for r in rows}; incoming={entry:0}; pending=deque([entry])
    while pending:
        at=pending.popleft(); row=by_at[at]; text=row['text']; delta=incoming[at]
        head,_,rest=text.partition(' ')
        if head in ('push','pop'):
            if rest=='rsp':raise ValueError(LABEL+'.dynamic-stack')
            delta+=-8 if head=='push' else 8
        elif rest.split(',')[0]=='rsp':
            if head not in ('add','sub') or not rest.startswith('rsp, 0x'):
                raise ValueError(LABEL+'.unreviewed-stack-write')
            amount=int(rest.split(', ')[1],16);delta+=amount if head=='add' else -amount
        kind=transfer(row)['kind']
        if kind in ('call','indirectCall') and ((8+delta)%16 or -delta<32):
            raise ValueError(LABEL+'.call-frame')
        if kind=='return' and delta!=0:raise ValueError(LABEL+'.return-frame')
        for target in edges[at]:
            if target in incoming and incoming[target]!=delta:raise ValueError(LABEL+'.stack-join')
            if target not in incoming:incoming[target]=delta;pending.append(target)
    if set(incoming)!=set(by_at):raise ValueError(LABEL+'.unreachable-owned-code')
    return incoming


def _program(rows, base, c):
    f=c['hasParent']; fields=c['physicalFields']; p=c['protocol']; offsets=p['offsets']
    slots={r['role']:base+r['slotRva'] for r in c['imports']}
    if set(slots)!={'ThreadId','Acquire','Release'} or len(c['imports'])!=3:
        raise ValueError(LABEL+'.import-role-set')
    g=BranchGrammar(rows,label=LABEL); labels=f['labels']
    def mark(label):
        g.mark(label)
        if g.labels[label]!=base+labels[label]:g.fail('label:'+label,labels[label],g.labels[label]-base)
    frame=f['frameBytes']; home=f['contextStackOffset']
    if frame<32 or frame%16 or not frame<=home<=frame+32:
        raise ValueError(LABEL+'.frame-declaration')
    for register,offset in [('rbx',16),('rbp',24),('rsi',32)]:_memory(g,'store',register,8,base='rsp',displacement=offset)
    g.take('push rdi',f'sub rsp, 0x{frame:x}','mov rbp, rdx','mov rdi, rcx')
    _load_byte(g,'eax','rcx',fields['readyFlags']);g.take('nop',f'test al, 0x{f["readyMask"]:x}')
    g.branch('jne','result')
    g.take(f'cmp qword [rcx+0x{fields["ancestryArray"]:x}], 0x0');g.branch('jne','result')
    context=base+p['globalContextRva'];owner=context+offsets['owner'];counter=context+offsets['reentry'];count=context+offsets['count']
    _lea(g,'rax',absolute=context);_memory(g,'store','rax',8,base='rsp',displacement=home)
    _import(g,slots['ThreadId']);g.take('mov rsi, rax')
    _memory(g,'load','rcx',8,absolute=owner);g.take('mov ebx, 0x1','cmp rax, rcx');g.branch('je','sameOwner')
    g.take('mov ecx, 0xffffffff');_exchange(g,'xadd','ecx',absolute=count);g.take('test ecx, ecx');g.branch('jg','ownerStore')
    _memory(g,'load','rcx',8,absolute=context);_import(g,slots['Acquire'])
    mark('ownerStore');_memory(g,'store','rsi',8,absolute=owner);_memory(g,'store','ebx',4,absolute=counter);g.branch('jmp','setup')
    mark('sameOwner');_step(g,'inc',absolute=counter)
    mark('setup');_lea(g,'rdx',displacement=home);g.take('mov rcx, rdi');call=g.call(base+f['setupTargetRva']);g.take('nop')
    # The child receives the slot address. The subsequent R8 load is fresh.
    _memory(g,'load','r8',8,base='rsp',displacement=home)
    g.take(f'cmp dword [r8+0x{offsets["reentry"]:x}], 0x0');_branch(g,'jle',base+labels['result'])
    g.take(f'cmp dword [r8+0x{offsets["reentry"]:x}], 0x1');g.branch('jne','decrementReentry')
    g.take('xor eax, eax');_memory(g,'store','rax',8,base='r8',displacement=offsets['owner']);_memory(g,'store','eax',4,base='r8',displacement=offsets['reentry'])
    _memory(g,'load','edx',4,base='r8',displacement=offsets['count'])
    mark('retry');_compare(g,32,'edx','r8',offsets['limit'],memory_first=False);g.branch('je','result')
    g.take('lea eax, [rdx+rbx*1]');_compare(g,32,'eax','r8',offsets['limit'],memory_first=False);_branch(g,'jle',base+labels['candidate'])
    _memory(g,'load','ebx',4,base='r8',displacement=offsets['limit']);g.take('sub ebx, edx')
    mark('candidate');g.take('lea ecx, [rdx+rbx*1]','mov eax, edx');_exchange(g,'cmpxchg','ecx',displacement=offsets['count']);g.branch('je','exchanged')
    g.take('mov edx, eax');g.branch('jmp','retry')
    mark('exchanged');g.take('test edx, edx');_branch(g,'jns',base+labels['result'])
    g.take('neg edx','cmp ebx, edx','cmovge ebx, edx','mov edx, ebx');_memory(g,'load','rcx',8,base='r8',displacement=offsets['handle']);_import(g,slots['Release']);g.branch('jmp','result')
    mark('decrementReentry');_step(g,'dec',displacement=offsets['reentry'])
    mark('result');g.take('mov rcx, rbp');g.call(base+f['parentPreparationTargetRva'])
    _load_byte(g,'eax','rbp',fields['ancestryDepth']);_byte_compare(g,'rdi',fields['ancestryDepth']);g.branch('jb','false')
    g.take('movzx ecx, al');_memory(g,'load','rax',8,base='rdi',displacement=fields['ancestryArray'])
    _compare(g,64,'rbp','rax',-8,index='rcx',scale=8);g.branch('jne','false')
    g.take('mov al, 0x1');g.branch('jmp','restore')
    mark('false');g.take('xor al, al')
    mark('restore')
    for register,offset in [('rbx',16),('rbp',24),('rsi',32)]:_memory(g,'load',register,8,base='rsp',displacement=offset+frame+8)
    g.take(f'add rsp, 0x{frame:x}','pop rdi','ret');g.finish()
    return {'setupCallRva':int(call['va'],16)-base,'setupReceivesOriginalFirstArgument':True,
            'setupReceivesAddressOfContextStackSlot':True,'releaseContextPointerTreatedAsFresh':True,
            'parentPreparationReceivesOriginalSecondArgument':True,
            'normalAlResult':'one iff unsigned first depth >= freshly loaded second depth and first ancestry array[second depth-1] equals original second argument',
            'indexBytes':8,'indexMinusOneOffset':-8,'zeroSecondDepthHasNoAdditionalGuard':True}


def validate_class_ancestry_control(index,c,exports):
    getters=_getters(index,c,exports);f=c['hasParent'];base=index.pe.image_base
    e=next(r for r in exports['selectedExports'] if r['symbolName']=='il2cpp_class_has_parent')
    if e['isForwarder'] or e['targetRva']!=f['entryRva']:raise ValueError(LABEL+'.has-parent-export-entry')
    owned,pieces,windows=owned_windows(index,f,LABEL)
    if f['paddingWindows']:raise ValueError(LABEL+'.unreviewed-padding')
    rows=[]
    for category,_,start,raw in windows:
        if category!='codeWindows':raise ValueError(LABEL+'.unreviewed-window')
        rows.extend(checked_rows(decode_context_memory_instructions(index.mapper,raw,start),raw,LABEL))
    rows.sort(key=lambda r:int(r['va'],16));check_byte_partition(owned,pieces,LABEL)
    if len(rows)!=f['checkedInstructionCount']:raise ValueError(LABEL+'.instruction-count')
    edges=_graph(rows,{'tables':[]},base);_frame(rows,edges,base+f['entryRva'])
    stores=[{'siteRva':int(r['va'],16)-base,**explicit_memory_effect(r)} for r in rows if explicit_memory_effect(r) is not None]
    calls=[{'siteRva':int(r['va'],16)-base,**transfer(r)} for r in rows if transfer(r)['kind'] in ('call','indirectCall')]
    returns=[int(r['va'],16)-base for r in rows if transfer(r)['kind']=='return']
    if (stores,calls,returns)!=(f['explicitStores'],f['calls'],f['returnRvas']):raise ValueError(LABEL+'.complete-effect-inventory')
    program=_program(rows,base,c)
    return {'selectedNamedGetters':getters,'completeHasParentOwnedControlChecked':True,
            'checkedInstructions':len(rows)+sum(r['checkedInstructions'] for r in getters),
            'ownedHasParentBytes':sum(b-a for a,b in owned),'closedGetterEntryBytes':sum(r['closedEntryBytes'] for r in getters),
            'explicitStoreSites':len(stores),'callSites':calls,'returnSites':returns,**program,
            'liveClassReceiverOrFormatterIdentityProved':False,'incomingSlotContentsUnchangedProved':False,
            'initializationOrSynchronizationOutcomeProved':False,'validAncestryArrayCapacityProved':False,
            'recursiveTerminationProved':False,'callbackCursorEqualityProved':False,
            'positiveListAdmitted':False,'wholeRootAdmitted':False}
