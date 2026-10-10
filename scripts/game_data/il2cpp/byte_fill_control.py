"""Complete selected native fill control, value lanes, table and range proof.

Anonymous globals choose SSE/AVX/REP and temporal/non-temporal paths. Their
runtime values, destination validity, CPU state and store visibility are not
inferred. A normal return preserves the incoming destination pointer.
"""
from __future__ import annotations
from .fill_instructions import decode_fill_instructions
from .fill_geometry import prove_fill_geometry,prove_byte_replication
from .integer_addressing import decode_lea_address
from .owned_partition import BranchGrammar,owned_windows,checked_rows,check_byte_partition,window_bytes
from .relation_control import transfer

LABEL='byteFillControl'


def _nop(g):
    row=g.take('nop')
    if row.get('paddingOperation',{}).get('readsMemory') is not False:g.fail('padding','typed no-memory NOP',row)


def _lane(g,operation,**expected):
    row=g.row();facts=row.get('fillLaneOperation',{})
    if facts.get('operation')!=operation or any(facts.get(k)!=v for k,v in expected.items()):
        g.fail('lane-value',(operation,expected),facts)


def _store(g,*,width,base,index=None,displacement=0,non_temporal=False,alignment=1,register=None):
    row=g.row();f=row.get('memoryOperation',{});a=f.get('address',{})
    expected=('store',width,base,index,1,displacement,non_temporal,alignment,register or ('ymm0' if width==32 else 'xmm0'))
    actual=(f.get('direction'),f.get('memoryBytes'),a.get('base'),a.get('index'),a.get('scale'),a.get('displacement'),
            f.get('nonTemporalHint'),f.get('requiredAlignmentBytes'),f.get('register'))
    if actual!=expected or a.get('ripRelative') is not False or a.get('addressBits')!=64:
        g.fail('payload-store',expected,f)
    return int(row['va'],16)


def _global_compare(g,base,target):
    row=g.row();raw=bytes.fromhex(row['bytes']);at=int(row['va'],16)
    if len(raw)!=7 or raw[:3]!=b'\x4c\x3b\x05' or at+7+int.from_bytes(raw[3:],'little',signed=True)!=base+target:
        g.fail('global-unsigned-count-compare',target,row)


def _byte_test(g,base,target):
    row=g.row();f=row.get('byteTestOperation',{})
    if (f.get('address'),f.get('mask'),f.get('bits'))!=(base+target,2,8):g.fail('mode-byte-test',target,row)


def _table(g,base,t,*,register,index):
    row=g.row();f=row.get('memoryOperation',{});a=f.get('address',{})
    if (int(row['va'],16)-base,f.get('direction'),f.get('register'),f.get('registerBits'),f.get('memoryBytes'),
        a.get('base'),a.get('index'),a.get('scale'),a.get('displacement'),a.get('ripRelative'))!=(
        t['siteRva'],'load',register+'d',32,4,'r10',index,4,t['startRva'],False):
        g.fail('table-load',t,row)
    g.take(f'add {register}, r10');row=g.row()
    if row.get('fillJumpOperation',{}).get('register')!=register:g.fail('table-jump',register,row)
    if int(row['va'],16)-base!=t['jumpSiteRva']:g.fail('table-jump-site',t['jumpSiteRva'],row)


def _short_paths(rows,table,base):
    starts={int(r['va'],16):i for i,r in enumerate(rows)};used=set()
    if len(table['targetRvas'])!=16:raise ValueError(LABEL+'.short-table-size')
    for size,target in enumerate(table['targetRvas']):
        at=base+target;covered=set()
        for _ in range(8):
            if at not in starts:raise ValueError(LABEL+'.short-target-boundary')
            row=rows[starts[at]];used.add(at)
            if row['text']=='ret':break
            f=row.get('memoryOperation',{});a=f.get('address',{})
            width=f.get('memoryBytes');register={1:'r11b',2:'r11w',4:'r11d',8:'r11'}.get(width)
            if (not register or f.get('direction')!='store' or f.get('register')!=register
                or a.get('base')!='rcx' or a.get('index') is not None or a.get('ripRelative') is not False
                or a.get('addressBits')!=64 or f.get('requiredAlignmentBytes')!=1):
                raise ValueError(LABEL+'.short-store-operand')
            start=size+a['displacement'];end=start+width
            if not 0<=start<=end<=size:raise ValueError(LABEL+'.short-store-range')
            covered.update(range(start,end));at+=len(bytes.fromhex(row['bytes']))
        else:raise ValueError(LABEL+'.short-return')
        if covered!=set(range(size)):raise ValueError(LABEL+'.short-coverage')
    return used


def _vector_body(g,base,t,*,role,width,non_temporal):
    chunk=8*width;loop=role+'Loop';tail=role+'Tail'
    g.mark(loop)
    for offset in range(0,chunk,width):
        _store(g,width=width,base='rcx',displacement=offset,non_temporal=non_temporal,alignment=width)
    g.take(f'add rcx, {hex(chunk)}',f'sub r8, {hex(chunk)}',f'cmp r8, {hex(chunk)}')
    g.branch('jae',loop);g.mark(tail)
    g.take(f'lea r9, [r8+{hex(width-1)}]',f'and r9, -{hex(width)}','mov r11, r9',f'shr r11, {hex(width.bit_length()-1)}')
    _table(g,base,t,register='r11',index='r11');prefix=[]
    for displacement in range(-chunk,-width,width):
        prefix.append(_store(g,width=width,base='rcx',index='r9',displacement=displacement,
            non_temporal=non_temporal,alignment=width if non_temporal else 1))
    endpoint=_store(g,width=width,base='rcx',index='r8',displacement=-width)
    head=_store(g,width=width,base='rax')
    expected=[head,endpoint,*reversed(prefix)]
    if [base+r for r in t['targetRvas']]!=expected:g.fail('tail-table-semantics',expected,t['targetRvas'])
    if non_temporal:
        row=g.take('sfence')
        if row.get('fillFenceOperation',{}).get('ordersStoresAgainstStores') is not True:g.fail('store-fence','typed SFENCE',row)
    if width==32:g.take('vzeroupper')
    g.take('ret')


def _main_program(rows,base,c):
    tables={t['role']:t for t in c['tables']};g=BranchGrammar(rows,label=LABEL+'.main')
    g.take('mov rax, rcx','mov r9, rcx');row=g.row();raw=bytes.fromhex(row['bytes'])
    decoded=decode_lea_address(raw,0,int(row['va'],16))
    if decoded is None or decoded[1]!=len(raw):g.fail('image-base','complete LEA',row)
    f=decoded[0]['addressOperation']
    if (f.get('destination'),f.get('destinationBits'),f.get('absoluteAddress'))!=('r10',64,base):g.fail('image-base',base,f)
    row=g.take('movzx edx, dl')
    if bytes.fromhex(row['bytes'])!=b'\x0f\xb6\xd2':g.fail('fill-byte-extension','MOVZX EDX, DL',row)
    g.take('mov r11, 0x101010101010101','imul r11, rdx')
    _lane(g,'gp-to-xmm',destination=0,sourceRegister='r11',sourceBits=64,zeroBitsThrough127From=64)
    g.take('cmp r8, 0xf');wide=g.branch('ja','wide')['target'];_nop(g)
    g.take('add rcx, r8');_table(g,base,tables['short'],register='r9',index='r8')
    used=_short_paths(rows,tables['short'],base)
    while int(g.rows[g.cursor]['va'],16)<wide:
        row=g.rows[g.cursor]
        if row['text']=='nop':_nop(g)
        elif int(row['va'],16) in used:g.row()
        else:g.fail('short-area-coverage','proved short payload or NOP',row)
    g.mark('wide');_lane(g,'unpack-low-qwords',destination=0,sourceVector=0)
    g.take('cmp r8, 0x20');g.branch('ja','large')
    _store(g,width=16,base='rcx');_store(g,width=16,base='rcx',index='r8',displacement=-16);g.take('ret')
    g.mark('large');row=g.row();raw=bytes.fromhex(row['bytes']);at=int(row['va'],16)
    if (len(raw)!=7 or raw[:2]!=b'\x83\x3d' or raw[-1]!=3
        or at+7+int.from_bytes(raw[2:6],'little',signed=True)!=base+c['globals']['vectorModeRva']):
        g.fail('vector-mode-compare',c['globals'],row)
    g.branch('jb','fallback');_global_compare(g,base,c['globals']['lowerThresholdRva']);g.branch('jbe','avx')
    _global_compare(g,base,c['globals']['upperThresholdRva']);g.branch('ja','avx')
    _byte_test(g,base,c['globals']['repModeRva']);rep=g.branch('jne')['target']
    if rep!=base+c['repEntryRva']:g.fail('rep-tail',c['repEntryRva'],rep)
    g.mark('avx');_lane(g,'insert-128-lane',destination=0,baseVector=0,sourceVector=0,insertLane=1)
    _rebase(g,32);g.take('cmp r8, 0x100');g.branch('jbe','temporal32Tail')
    _global_compare(g,base,c['globals']['upperThresholdRva']);g.branch('ja','nonTemporal32Loop');_nop(g)
    _vector_body(g,base,tables['temporal32'],role='temporal32',width=32,non_temporal=False);_nop(g)
    _vector_body(g,base,tables['nonTemporal32'],role='nonTemporal32',width=32,non_temporal=True);_nop(g)
    g.mark('fallback');_global_compare(g,base,c['globals']['lowerThresholdRva']);g.branch('jbe','sse')
    _byte_test(g,base,c['globals']['repModeRva']);rep=g.branch('jne')['target']
    if rep!=base+c['repEntryRva']:g.fail('rep-tail',c['repEntryRva'],rep)
    g.mark('sse');_rebase(g,16);g.take('cmp r8, 0x80');g.branch('jbe','fallback16Tail');_nop(g)
    _vector_body(g,base,tables['fallback16'],role='fallback16',width=16,non_temporal=False)
    g.finish()


def _rebase(g,width):
    g.take('mov r9, rcx',f'and r9, {hex(width-1)}',f'sub r9, {hex(width)}',
           'sub rcx, r9','sub rdx, r9','add r8, r9')


def _rep_program(rows):
    g=BranchGrammar(rows,label=LABEL+'.rep')
    g.take('push rdi','mov eax, edx','mov rdi, rcx','mov rcx, r8');row=g.take('rep stosb')
    f=row.get('fillStringOperation',{})
    if (f.get('elementBytes'),f.get('addressBits'),f.get('valueRegister'),f.get('destinationRegister'),f.get('countRegister'),
        f.get('directionFlagControlsStep'),f.get('terminatesOnCountZero'))!=(1,64,'al','rdi','rcx',True,True):
        g.fail('rep-stores','complete REP STOSB facts',row)
    g.take('mov rax, r9','pop rdi','ret');g.finish()


def validate_byte_fill_control(index,c):
    base=index.pe.image_base;all_rows=[];programs={};owned_bytes=0
    if c['selectedCallerDomain']!={'unsignedCountBits':8,'strideBytes':8,'fillByte':0}:
        raise ValueError(LABEL+'.caller-domain')
    for function in c['functions']:
        owned,pieces,windows=owned_windows(index,function,LABEL);rows=[]
        if function['paddingWindows']:raise ValueError(LABEL+'.unreviewed-padding-partition')
        for category,_,start,raw in windows:
            if category!='codeWindows':raise ValueError(LABEL+'.unreviewed-piece')
            rows+=checked_rows(decode_fill_instructions(index.mapper,raw,start),raw,LABEL)
        check_byte_partition(owned,pieces,LABEL)
        if len(rows)!=function['checkedInstructionCount']:raise ValueError(LABEL+'.instruction-count')
        if function['role'] in programs:raise ValueError(LABEL+'.duplicate-function')
        programs[function['role']]=rows;all_rows+=rows;owned_bytes+=sum(b-a for a,b in owned)
    if set(programs)!={'main','rep'}:raise ValueError(LABEL+'.function-roles')
    entries={f['role']:f['entryRva'] for f in c['functions']}
    if entries!={'main':c['entryRva'],'rep':c['repEntryRva']}:raise ValueError(LABEL+'.entry-join')
    if [t['role'] for t in c['tables']]!=['short','temporal32','nonTemporal32','fallback16']:
        raise ValueError(LABEL+'.table-roles')
    table_bytes=0
    table_ranges=[]
    for t in c['tables']:
        raw=window_bytes(index,base+t['startRva'],base+t['endRva'],t['sha256'],LABEL)
        if raw!=b''.join(v.to_bytes(4,'little') for v in t['targetRvas']):raise ValueError(LABEL+'.table-values')
        if len(t['targetRvas'])!=(16 if t['role']=='short' else 9):raise ValueError(LABEL+'.table-size')
        table_bytes+=len(raw)
        table_ranges.append((t['startRva'],t['endRva']))
    if any(b>a2 for (_,b),(a2,_) in zip(sorted(table_ranges),sorted(table_ranges)[1:])):
        raise ValueError(LABEL+'.overlapping-tables')
    _main_program(programs['main'],base,c);_rep_program(programs['rep'])
    starts={int(r['va'],16):r for r in all_rows};edges={};returns=[];stores=[];branches=[]
    table_jumps={base+t['jumpSiteRva']:[base+r for r in t['targetRvas']] for t in c['tables']}
    if len(starts)!=len(all_rows) or len(table_jumps)!=4:raise ValueError(LABEL+'.duplicate-instruction-or-dispatch')
    for at,row in starts.items():
        if 'fillJumpOperation' in row:
            if at not in table_jumps:raise ValueError(LABEL+'.unreviewed-table-jump')
            successors=table_jumps[at]
        else:
            f=transfer(row);kind=f['kind'];successors=[]
            if kind=='return':returns.append(at-base)
            elif kind in ('jump','conditional'):
                successors.append(f['target']);branches.append({'siteRva':at-base,'kind':kind,'targetRva':f['target']-base,
                    **({'conditionCode':f['conditionCode']} if kind=='conditional' else {})})
            elif kind!='next':raise ValueError(LABEL+'.unreviewed-call-or-transfer')
            if kind in ('next','conditional'):successors.append(at+len(bytes.fromhex(row['bytes'])))
        if any(target not in starts for target in successors):raise ValueError(LABEL+'.outside-or-mid-instruction-edge')
        edges[at]=successors
        if row.get('memoryOperation',{}).get('direction')=='store' or 'fillStringOperation' in row:stores.append(at-base)
    pending=[base+c['entryRva']];reached=set()
    while pending:
        at=pending.pop()
        if at in reached:continue
        reached.add(at);pending+=edges[at]
    if any(starts[a]['text']!='nop' for a in set(starts)-reached):raise ValueError(LABEL+'.unreachable-nonpadding-instruction')
    if branches!=c['branches'] or sorted(returns)!=c['returnRvas'] or stores!=c['payloadStoreSiteRvas']:
        raise ValueError(LABEL+'.control-or-store-inventory')
    geometry=[prove_fill_geometry(width=w,chunk=8*w) for w in (16,32)]
    for size in range(16,33):
        if set(range(16)) | set(range(size-16,size)) != set(range(size)):
            raise ValueError(LABEL+'.bounded-vector-coverage')
    return {'completeOwnedFillAndRepProgramsChecked':True,'checkedInstructions':len(all_rows),
        'ownedBytes':owned_bytes,'authenticatedTableBytes':table_bytes,'checkedTables':4,
        'tableEntries':43,'possibleLocalReachableInstructions':len(reached),'unreachableTypedNopInstructions':len(starts)-len(reached),
        'directConditionalBranches':len(branches),'payloadStoreSites':len(stores),'normalReturnSites':len(returns),
        'shortSizes':list(range(16)),'boundedVectorSizes':list(range(16,33)),
        'byteReplication':prove_byte_replication(),'vectorGeometry':geometry,
        'normalReturnEqualsIncomingDestinationProved':True,'repPreservesRdiAndRestoresFrameProved':True,
        'allRequestedBytesEqualLowIncomingValueByteConditionallyProved':True,
        'selectedCallerCountMaximum':255,'selectedCallerByteLengthMaximum':2040,
        'selectedCallerZeroFillAndReturnedPointerConditionalJoinProved':True,
        'payloadReadsRequired':False,'repDirectionFlagZeroRequired':True,'validWritableMemoryAndCompatibleCpuStateRequired':True,
        'compatibleStackAndNormalReturnRequired':True,
        'nonWrappingEndpointAndControlStorageNoninterferenceRequired':True,
        'nonTemporalStoresHaveFollowingSfenceProved':True,'allStoresGloballyVisibleAtReturnProved':False,
        'allocationSuccessOrValidCapacityProved':False,'runtimeExecutionObserved':False,
        'initializedAllocatorProtocolOrLiveGlobalSelectionProved':False,'incomingSlotContentsUnchangedProved':False,
        'callbackCursorEqualityProved':False,'positiveListAdmitted':False,'wholeRootAdmitted':False}
