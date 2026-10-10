"""Owned anonymous context bodies, physical array flow and address handoffs.

The first complete program has a byte counter, a QWORD array and flag writes.
The second complete CFG has an explicit-store inventory and selected incoming
address handoffs. Normal ABI returns, valid/disjoint storage and a stable
saved address are conditions. No runtime class, allocator/copy effect, slot
contents, formatter selection or root admission is inferred.
"""
from __future__ import annotations
from collections import deque
from scripts.game_data.il2cpp.integer_byte_operations import decode_byte_operation_instructions
from scripts.game_data.il2cpp.memory_moves import decode_memory_move
from scripts.game_data.il2cpp.owned_partition import (
    BranchGrammar, check_byte_partition, checked_rows, owned_windows, rip_load)
from scripts.game_data.il2cpp.relation_control import explicit_memory_effect, transfer
from scripts.game_data.il2cpp.relation_import_control import _memory

LABEL = 'contextSetupControl'
_ALIASES = {name: parent for parent, names in {
    'rbx': ('rbx', 'ebx', 'bx', 'bl', 'bh'),
    'rdx': ('rdx', 'edx', 'dx', 'dl', 'dh')}.items() for name in names}
_READ_ONLY = {'cmp', 'test', 'push', 'nop', 'ret'}
_WRITERS = {'mov', 'movzx', 'movsxd', 'lea', 'xor', 'add', 'sub',
            'and', 'or', 'inc', 'shr', 'shl', 'pop'}


def _rows(index, function):
    owned, pieces, windows = owned_windows(index, function, LABEL)
    if function['paddingWindows']:
        raise ValueError(LABEL + '.unreviewed-padding')
    rows = []
    for category, _, start, raw in windows:
        if category != 'codeWindows':
            raise ValueError(LABEL + '.unreviewed-piece-kind')
        rows.extend(checked_rows(decode_byte_operation_instructions(index.mapper, raw, start), raw, LABEL))
    check_byte_partition(owned, pieces, LABEL)
    rows.sort(key=lambda r: int(r['va'], 16))
    if len(rows) != function['checkedInstructionCount']:
        raise ValueError(LABEL + '.instruction-count')
    return rows


def _graph(rows, base, function, selected_ranges, entries):
    starts = {int(r['va'], 16) for r in rows}
    if len(starts) != len(rows):
        raise ValueError(LABEL + '.duplicate-instruction-start')
    edges, calls, branches, returns, stores = {}, [], [], [], []
    for row in rows:
        at = int(row['va'], 16); end = at + len(bytes.fromhex(row['bytes']))
        f = transfer(row); kind = f['kind']; targets = []
        if kind in ('jump', 'conditional'):
            targets.append(f['target'])
            branches.append({'siteRva': at-base, 'kind': kind, 'targetRva': f['target']-base,
                             **({'conditionCode': f['conditionCode']} if kind == 'conditional' else {})})
        if kind in ('next', 'conditional', 'call'):
            targets.append(end)
        if kind == 'call':
            target = f['target']-base
            if target not in entries and any(a <= target < b for a, b in selected_ranges):
                raise ValueError(LABEL + '.call-into-owned-interior')
            calls.append({'siteRva': at-base, 'targetRva': target})
        elif kind == 'return':
            returns.append(at-base)
        elif kind not in ('next', 'conditional', 'jump'):
            raise ValueError(LABEL + '.unreviewed-transfer-kind')
        if any(target not in starts for target in targets):
            raise ValueError(LABEL + '.local-target-or-continuation-boundary')
        edges[at] = set(targets)
        effect = explicit_memory_effect(row)
        if effect is not None:
            stores.append({'siteRva': at-base, **effect})
    for key, actual in (('directCalls', calls), ('localBranches', branches),
                        ('returnRvas', returns), ('explicitStores', stores)):
        if actual != function[key]:
            raise ValueError(f'{LABEL}.{key}: expected={str(function[key])[:200]} actual={str(actual)[:300]}')
    reached = set(); pending = [base+function['entryRva']]
    while pending:
        at = pending.pop()
        if at in reached:
            continue
        reached.add(at); pending.extend(edges[at]-reached)
    if reached != starts:
        raise ValueError(LABEL + '.uncovered-owned-instructions')
    return edges, {'role': function['role'], 'checkedInstructions': len(rows),
                   'checkedLocalBranches': len(branches), 'directCallSites': calls,
                   'explicitStoreSites': len(stores), 'returnSites': returns,
                   'staticPossibleReachableInstructions': len(reached)}


def _frame(rows, edges, base, function):
    """Exact RSP deltas on every possible local edge; callees return normally."""
    by_at = {int(r['va'], 16): r for r in rows}
    before = {base+function['entryRva']: 0}; pending = deque(before)
    while pending:
        at = pending.popleft(); row = by_at[at]; text = row['text']
        head, _, rest = text.partition(' '); delta = before[at]
        if head in ('push', 'pop'):
            if rest == 'rsp':
                raise ValueError(LABEL + '.dynamic-stack-pointer')
            delta += -8 if head == 'push' else 8
        elif rest.split(',')[0] == 'rsp':
            if head not in ('add', 'sub') or not rest.startswith('rsp, 0x'):
                raise ValueError(LABEL + '.unreviewed-stack-write')
            amount = int(rest.split(', ')[1], 16)
            delta += amount if head == 'add' else -amount
        kind = transfer(row)['kind']
        if kind == 'call' and ((8+delta) % 16 or -delta < 32):
            raise ValueError(LABEL + '.call-shadow-or-alignment')
        if kind == 'return' and delta != 0:
            raise ValueError(LABEL + '.unrestored-stack-return')
        for target in edges[at]:
            if target in before and before[target] != delta:
                raise ValueError(LABEL + '.inconsistent-stack-join')
            if target not in before:
                before[target] = delta; pending.append(target)
    if set(before) != set(by_at):
        raise ValueError(LABEL + '.unvisited-stack-state')
    return before


def _load_byte(g, register, base, offset):
    row = g.row(); f = row.get('byteMemoryZeroExtensionOperation', {}); a = f.get('sourceAddress', {})
    if (f.get('destinationRegister'), f.get('memoryReadBytes'), f.get('sourceBits'),
        f.get('zeroExtendsTo64'), a.get('base'), a.get('index'), a.get('displacement')) != (
            register, 1, 8, True, base, None, offset):
        g.fail('unsigned-byte-load', (register, base, offset), row)


def _cmp_zero(g, base, offset):
    row = g.row(); f = row.get('memoryImmediateComparisonOperation', {}); a = f.get('sourceAddress', {})
    if (f.get('bits'), f.get('memoryReadBytes'), f.get('immediateWord'),
        a.get('base'), a.get('index'), a.get('displacement')) != (64, 8, 0, base, None, offset):
        g.fail('qword-zero-comparison', (base, offset), row)


def _point(g, image_base, function, label):
    if int(g.rows[g.cursor]['va'], 16) != image_base+function['labels'][label]:
        g.fail('label:'+label, function['labels'][label], g.rows[g.cursor])


def _mark(g, image_base, function, label):
    _point(g, image_base, function, label); g.mark(label)


def _first(rows, base, function):
    c = function['physicalFields']; link, array, count, flags = [c[k] for k in ('linkedReceiver', 'array', 'countByte', 'flagByte')]
    mask = function['readyMask']; frame = function['frameBytes']
    if (any(type(n) != int or n < 0 for n in (link, array, count, flags, frame)) or
            type(mask) != int or not 0 < mask < 256 or mask & (mask-1) or
            frame < 32 or frame % 16 or len({link, array, count, flags}) != 4):
        raise ValueError(LABEL + '.first-declarations')
    g = BranchGrammar(rows, label=LABEL+'.first')
    g.take('push rbx', f'sub rsp, 0x{frame:x}'); _load_byte(g, 'eax', 'rcx', flags)
    g.take('mov rbx, rcx', f'test al, 0x{mask:x}'); g.branch('jne', 'restore')
    _cmp_zero(g, 'rcx', array); g.branch('jne', 'restore')
    _cmp_zero(g, 'rcx', link); g.branch('je', 'afterRecursive')
    _memory(g, 'load', 'rax', 8, base='rcx', displacement=link)
    _cmp_zero(g, 'rax', array); g.branch('jne', 'afterRecursive')
    g.take('mov rcx, rax'); recursive = g.call(base+function['entryRva'])
    if function['incomingAddressCallRvas'] != [int(recursive['va'], 16)-base]:
        g.fail('recursive-address-call-inventory', 'actual complete first recursive call', function['incomingAddressCallRvas'])
    _mark(g, base, function, 'afterRecursive'); _cmp_zero(g, 'rbx', link); g.branch('je', 'rootCount')
    _memory(g, 'load', 'rax', 8, base='rbx', displacement=link); _load_byte(g, 'ecx', 'rax', count)
    row = g.row(); f = row.get('byteRegisterStepOperation', {})
    if (f.get('operation'), f.get('destinationRegister'), f.get('parentRegister'), f.get('bitOffset'),
        f.get('bits'), f.get('delta'), f.get('wrapsModulo'), f.get('preservesOtherParentBits'),
        f.get('preservesCarryFlag')) != ('inc', 'cl', 'rcx', 0, 8, 1, 256, True, True):
        g.fail('byte-count-increment', 'INC CL modulo 256 with partial write', row)
    g.branch('jmp', 'countStore'); _mark(g, base, function, 'rootCount'); g.take('mov cl, 0x1')
    _mark(g, base, function, 'countStore'); _memory(g, 'store', 'cl', 1, base='rbx', displacement=count)
    g.take('mov r8d, 0x8', 'movzx edx, cl'); rip_load(g, 'rcx', base+function['allocationContextGlobalRva'])
    g.call(base+function['allocationLikeTargetRva'])
    _cmp_zero(g, 'rbx', link); _memory(g, 'store', 'rax', 8, base='rbx', displacement=array)
    g.branch('je', 'rootStore'); _load_byte(g, 'ecx', 'rbx', count)
    row = g.row(); raw = bytes.fromhex(row['bytes']); decoded = decode_memory_move(raw, 0, int(row['va'], 16))
    f = decoded[0]['memoryOperation'] if decoded is not None and decoded[1] == len(raw) else {}
    a = f.get('address', {})
    if (f.get('direction'), f.get('register'), f.get('memoryBytes'), a.get('base'),
        a.get('index'), a.get('scale'), a.get('displacement')) != ('store', 'rbx', 8, 'rax', 'rcx', 8, -8):
        g.fail('indexed-self-store', 'QWORD receiver at array+(fresh count-1)*8', row)
    _memory(g, 'load', 'rax', 8, base='rbx', displacement=link)
    _memory(g, 'load', 'rcx', 8, base='rbx', displacement=array); _load_byte(g, 'r8d', 'rax', count)
    _memory(g, 'load', 'rdx', 8, base='rax', displacement=array)
    g.take('shl r8, 0x3'); g.call(base+function['copyLikeTargetRva']); g.branch('jmp', 'flagUpdate')
    _mark(g, base, function, 'rootStore'); _memory(g, 'store', 'rbx', 8, base='rax')
    _mark(g, base, function, 'flagUpdate'); _load_byte(g, 'eax', 'rbx', flags); g.take('nop')
    row = g.row(); f = row.get('byteLogicalOperation', {})
    if (f.get('operation'), f.get('destinationRegister'), f.get('immediateWord'), f.get('parentRegister'),
        f.get('bitOffset'), f.get('bits'), f.get('preservesOtherParentBits')) != ('or', 'al', mask, 'rax', 0, 8, True):
        g.fail('fresh-byte-flag-or', ('AL', mask), row)
    _memory(g, 'store', 'al', 1, base='rbx', displacement=flags)
    _mark(g, base, function, 'restore'); g.take(f'add rsp, 0x{frame:x}', 'pop rbx', 'ret'); g.finish()


def _second(rows, base, function, stack):
    c = function['addressHandoff']; flags = c['flagByte']; frame = c['frameBytes']
    delta = frame+16; home = c['entryHomeOffset']; current = c['currentHomeOffset']
    if (any(type(n) != int or n < 0 for n in (flags, frame, home, current)) or
            frame < 32 or frame % 16 != 8 or not 8 <= home <= 32 or current != home+delta):
        raise ValueError(LABEL + '.second-home-geometry')
    g = BranchGrammar(rows[:12], label=LABEL+'.secondPrefix')
    _memory(g, 'store', 'rdx', 8, base='rsp', displacement=home)
    g.take('push rbx', 'push rdi', f'sub rsp, 0x{frame:x}'); _load_byte(g, 'eax', 'rcx', flags)
    g.take('mov rbx, rdx', 'mov rdi, rcx', f'test al, 0x{c["readyMask"]:x}')
    g.branch('jne', 'restore'); g.take(f'test byte [rcx+0x{c["blockedFlagByte"]:x}], 0x{c["blockedMask"]:x}')
    g.branch('jne', 'restore'); _cmp_zero(g, 'rcx', c['linkedReceiver'])
    g.labels['restore'] = base+c['restoreRva']; g.finish()
    positions = {int(r['va'], 16)-base: n for n, r in enumerate(rows)}
    n = positions[c['restoreRva']]; g = BranchGrammar(rows[n:n+4], label=LABEL+'.secondRestore')
    g.take(f'add rsp, 0x{frame:x}', 'pop rdi', 'pop rbx', 'ret'); g.finish()
    n = positions[c['rbxHomeReloadRva']]; g = BranchGrammar(rows[n:n+1], label=LABEL+'.rbxHome')
    _memory(g, 'load', 'rbx', 8, base='rsp', displacement=current); g.finish()
    n = positions[c['recursiveHandoffStartRva']]; g = BranchGrammar(rows[n:n+4], label=LABEL+'.recursiveHandoff')
    g.take('mov rdx, rbx'); _memory(g, 'store', 'rbp', 8, base='rsp', displacement=c['saveRbpOffset'])
    g.take('mov rcx, r14'); recursive = g.call(base+function['entryRva']); g.finish()
    n = positions[c['helperHandoffStartRva']]; g = BranchGrammar(rows[n:n+3], label=LABEL+'.helperHandoff')
    _memory(g, 'load', 'rdx', 8, base='rsp', displacement=current)
    g.take('mov rcx, rax'); helper = g.call(base+c['helperTargetRva']); g.finish()
    if function['incomingAddressCallRvas'] != [int(r['va'], 16)-base for r in (recursive, helper)]:
        g.fail('second-address-call-inventory', 'actual two checked handoff calls', function['incomingAddressCallRvas'])
    for rva in (c['rbxHomeReloadRva'], c['recursiveHandoffStartRva'], c['helperHandoffStartRva']):
        if stack[base+rva] != -delta:
            raise ValueError(LABEL + '.handoff-stack-depth')
    # Direct stack stores cannot overwrite the saved entry address. Other
    # indirect stores and callee effects still require disjoint/stable storage.
    for row in rows[1:]:
        effect = explicit_memory_effect(row)
        if effect is None:
            continue
        f = effect['facts']; a = f.get('address', f.get('destinationAddress', {}))
        if a.get('base') != 'rsp':
            continue
        if a.get('index') is not None:
            raise ValueError(LABEL + '.indexed-stack-store')
        width = f.get('memoryBytes', f.get('memoryWriteBytes'))
        if not isinstance(width, int) or width <= 0:
            raise ValueError(LABEL + '.unclassified-stack-store-width')
        begin = stack[int(row['va'], 16)]+a['displacement']
        if begin < home+8 and home < begin+width:
            raise ValueError(LABEL + '.direct-stack-store-overwrites-home')


def _origins(rows, edges, base, function):
    """Finite address provenance; all other complete/partial writes lose origin."""
    by_at = {int(r['va'], 16): r for r in rows}
    before = {base+function['entryRva']: (frozenset({None}), frozenset({'entryRdxAddress'}))}
    pending = deque(before); home = function.get('addressHandoff', {})
    reloads = {base+home[k]: register for k, register in
               (('rbxHomeReloadRva', 'rbx'), ('helperHandoffStartRva', 'rdx')) if k in home}
    while pending:
        at = pending.popleft(); row = by_at[at]; values = list(before[at])
        head, _, rest = row['text'].partition(' '); kind = transfer(row)['kind']
        if kind == 'call':
            values[1] = frozenset({None})  # normal Win64 calls preserve RBX
        elif kind in ('jump', 'conditional', 'return') or head in _READ_ONLY:
            pass
        elif head in _WRITERS:
            destination = rest.split(',')[0]; parent = _ALIASES.get(destination)
            if parent is not None:
                n = 0 if parent == 'rbx' else 1
                if at in reloads:
                    if destination != reloads[at]:
                        raise ValueError(LABEL + '.home-reload-destination')
                    values[n] = frozenset({'savedEntryRdxAddress'})
                elif row['text'] == 'mov rbx, rdx':
                    values[0] = values[1]
                elif row['text'] == 'mov rdx, rbx':
                    values[1] = values[0]
                else:
                    values[n] = frozenset({None})
        else:
            raise ValueError(LABEL + '.unreviewed-origin-instruction:'+head)
        for target in edges[at]:
            old = before.get(target); new = tuple(values) if old is None else tuple(a | b for a, b in zip(old, values))
            if old != new:
                before[target] = new; pending.append(target)
    result = []
    for rva in function['incomingAddressCallRvas']:
        origins = before[base+rva][1]
        if not origins or None in origins or transfer(by_at[base+rva])['kind'] != 'call':
            raise ValueError(LABEL + '.incoming-address-not-proved:'+hex(rva))
        result.append({'siteRva': rva, 'rdxOrigins': sorted(origins)})
    return result


def validate_context_setup_control(index, contract):
    functions = {f['role']: f for f in contract['functions']}
    if set(functions) != {'first', 'second'} or len(contract['functions']) != 2:
        raise ValueError(LABEL + '.distinct-function-roles')
    entries = {f['entryRva'] for f in functions.values()}
    ranges = sorted((w['startRva'], w['endRva']) for f in functions.values() for w in f['ownedWindows'])
    if len(entries) != 2 or any(a >= b for a, b in ranges) or any(b > c for (a, b), (c, d) in zip(ranges, ranges[1:])):
        raise ValueError(LABEL + '.overlapping-or-empty-ownership')
    base = index.pe.image_base; programs, graphs, stacks, summaries = {}, {}, {}, []
    for role, function in functions.items():
        rows = _rows(index, function); edges, summary = _graph(rows, base, function, ranges, entries)
        programs[role] = rows; graphs[role] = edges; stacks[role] = _frame(rows, edges, base, function)
        summaries.append({**summary, 'ownedBytes': sum(w['endRva']-w['startRva'] for w in function['ownedWindows'])})
    _first(programs['first'], base, functions['first'])
    _second(programs['second'], base, functions['second'], stacks['second'])
    handoffs = [dict(role=role, **r) for role, function in functions.items()
                for r in _origins(programs[role], graphs[role], base, function)]
    return {'completeOwnedPrimaryChainedCfgsChecked': True, 'programs': summaries,
            'checkedInstructions': sum(s['checkedInstructions'] for s in summaries),
            'ownedBytes': sum(s['ownedBytes'] for s in summaries),
            'explicitStoreSites': sum(s['explicitStoreSites'] for s in summaries),
            'firstCompleteByteCounterArrayFlagProgramChecked': True,
            'firstLinkedCountExpression': '(fresh unsigned linked count byte + 1) modulo 256; otherwise 1',
            'firstCountWrapsAt255WithoutAdditionalGuard': True,
            'firstQwordArrayStoreAndCopyLikeArgumentsChecked': True,
            'firstFreshFlagByteOrAndFullRestorationChecked': True,
            'possibleLocalCallsHaveAlignedShadowSpaceAndRestoredRspChecked': True,
            'selectedIncomingAddressHandoffsChecked': handoffs,
            'secondDirectStackStoresDoNotOverwriteSavedAddressChecked': True,
            'secondCompleteTypedFieldProgramProved': False,
            'incomingSlotContentsUnchangedProved': False,
            'allocationOrCopyCalleeEffectsProved': False,
            'validArrayCapacityOrNonzeroAllocationProved': False,
            'recursiveTerminationProved': False,
            'actualRuntimeClassOrFormatterSelected': False,
            'callbackCursorEqualityProved': False, 'positiveListAdmitted': False, 'wholeRootAdmitted': False,
            'conditions': contract['conditions']}
