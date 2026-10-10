"""Gate the actual context clear tail, full fill effects and result-field join."""
from __future__ import annotations
import sys
from pathlib import Path
from types import SimpleNamespace
from scripts.common import check_installed_native_inputs
from scripts.game_data.contracts import CONTRACTS_DIR
from scripts.game_data.il2cpp.body_claims import BodyIndex
from scripts.game_data.il2cpp.native_image import NATIVE_MAPPER_PATH,read_reviewed_contract
from scripts.game_data.il2cpp.protocol import load_native_mapper
from scripts.game_data.il2cpp.byte_fill_control import validate_byte_fill_control
from scripts.game_data.memorypack import buff_formatter_context_allocation as parent_owner
from scripts.game_data.memorypack import buff_formatter_context_setup as context_owner
from scripts.game_data.memorypack.corpus_gate import _fingerprint
from scripts.game_data.memorypack.native_owner import fail,proof_sources,validate_owner

LABEL='buffFormatterClearTail'
SCOPE='selected-clear-tail-complete-byte-fill-rep-and-actual-context-result-join-only'
PATH=CONTRACTS_DIR/'buff_formatter_clear_tail_native.json'

def _fail(check,expected,actual,*,native_inputs=None):
    fail(LABEL,SCOPE,PATH,check,expected,actual,native_inputs=native_inputs)

def _contract():
    c,_=read_reviewed_contract(PATH,schema='endfield.buff-formatter-clear-tail-native-contract.v1',status='exact-current-build',label=LABEL)
    if (c.get('scope'),c.get('parentContract'))!=(SCOPE,'buff_formatter_context_allocation_native.json'):
        _fail('contract-shape','reviewed scope and allocation parent',c.get('scope'),native_inputs=c.get('nativeInputs'))
    return c

def _proof_sources():
    return proof_sources(__file__,PATH,parent_owner._proof_sources(),NATIVE_MAPPER_PATH)

def _validate_selected(gameassembly,c):
    parent=parent_owner._contract();context=context_owner._contract()
    first=next(f for f in context['functions'] if f['role']=='first')
    if (parent['nativeInputs']!=c['nativeInputs'] or context['nativeInputs']!=c['nativeInputs']
        or parent['clearTailTargetRva']!=c['entryRva']
        or parent['callerEntryRva']!=c['callerEntryRva'] or first['entryRva']!=c['callerEntryRva']):
        _fail('actual-caller-build-and-tail','same selected build, actual allocation tail and first context entry',
              (parent['clearTailTargetRva'],c['entryRva']),native_inputs=c['nativeInputs'])
    summary=parent_owner._validate_selected(gameassembly,parent)
    if (not summary['clearTailRestoresFrameRegistersAndForwardsOldCursorZeroAndUnroundedProductProved']
        or parent['selectedCallerDomain']!={'unsignedCountBits':8,'strideBytes':8}
        or c['selectedCallerDomain']!={'unsignedCountBits':8,'strideBytes':8,'fillByte':0}):
        _fail('actual-clear-arguments','proved unsigned byte count times eight, zero fill and old cursor',
              c['selectedCallerDomain'],native_inputs=c['nativeInputs'])
    mapper=load_native_mapper(NATIVE_MAPPER_PATH);pe=mapper.PeImage(Path(gameassembly))
    index=BodyIndex(SimpleNamespace(mapper=mapper,pe=pe,metadata=None))
    return {**validate_byte_fill_control(index,c),'actualContextCallerAndParentProofsRechecked':True,
            'checkedAllocationInstructions':summary['checkedInstructions'],
            'checkedContextCallerInstructions':summary['checkedContextCallerInstructions'],
            'actualFirstContextArrayResultFieldOffset':first['physicalFields']['array'],
            'actualFirstContextStoredArrayPointerEqualsAllocatorOldCursorConditionallyProved':True}

def validate_current_native_contract(*,gameassembly=None,metadata=None):
    return validate_owner(sys.modules[__name__],gameassembly=gameassembly,metadata=metadata,
        open_claims={'allocationSuccessOrValidCapacityProved':False,'initializedAllocatorProtocolOrLiveGlobalSelectionProved':False,
            'allStoresGloballyVisibleAtReturnProved':False,'runtimeExecutionObserved':False,
            'incomingSlotContentsUnchangedProved':False,'callbackCursorEqualityProved':False,
            'positiveListAdmitted':False,'wholeRootAdmitted':False},check='native-byte-fill-control',
        expected='complete owned byte fill and REP control, tables, values, ranges, normal return and actual caller field join',
        phase='byte fill and actual context result join')
