"""Gate complete context allocation control and its actual caller argument join."""
from __future__ import annotations
import sys
from pathlib import Path
from types import SimpleNamespace
from scripts.common import check_installed_native_inputs
from scripts.game_data.contracts import CONTRACTS_DIR
from scripts.game_data.il2cpp.body_claims import BodyIndex
from scripts.game_data.il2cpp.native_image import NATIVE_MAPPER_PATH, read_reviewed_contract
from scripts.game_data.il2cpp.protocol import load_native_mapper
from scripts.game_data.il2cpp.context_allocation_control import validate_context_allocation_control
from scripts.game_data.memorypack import buff_formatter_context_setup as parent_owner
from scripts.game_data.memorypack.corpus_gate import _fingerprint
from scripts.game_data.memorypack.native_owner import fail, proof_sources, validate_owner

LABEL = 'buffFormatterContextAllocation'
SCOPE = 'selected-context-allocation-complete-reservation-refill-node-and-clear-tail-control-only'
PATH = CONTRACTS_DIR / 'buff_formatter_context_allocation_native.json'

def _fail(check, expected, actual, *, native_inputs=None):
    fail(LABEL,SCOPE,PATH,check,expected,actual,native_inputs=native_inputs)

def _contract():
    c,_ = read_reviewed_contract(PATH,schema='endfield.buff-formatter-context-allocation-native-contract.v1',status='exact-current-build',label=LABEL)
    if (c.get('scope'),c.get('parentContract'))!=(SCOPE,'buff_formatter_context_setup_native.json'):
        _fail('contract-shape','reviewed scope and parent',c.get('scope'),native_inputs=c.get('nativeInputs'))
    return c

def _proof_sources():
    return proof_sources(__file__,PATH,parent_owner._proof_sources(),NATIVE_MAPPER_PATH)

def _validate_selected(gameassembly,c):
    parent = parent_owner._contract(); first = next(f for f in parent['functions'] if f['role']=='first')
    if parent['nativeInputs']!=c['nativeInputs'] or first['entryRva']!=c['callerEntryRva']:
        _fail('parent-build-entry',(parent['nativeInputs'],first['entryRva']),(c['nativeInputs'],c['callerEntryRva']),native_inputs=c['nativeInputs'])
    parent_summary = parent_owner._validate_selected(gameassembly,parent)
    if (first['allocationLikeTargetRva']!=c['entryRva'] or
        not parent_summary['firstCompleteByteCounterArrayFlagProgramChecked'] or
        c['selectedCallerDomain']!={'unsignedCountBits':8,'strideBytes':8}):
        _fail('actual-caller-allocation-arguments','actual first call with unsigned byte count and stride eight',c['entryRva'],native_inputs=c['nativeInputs'])
    mapper = load_native_mapper(NATIVE_MAPPER_PATH); pe = mapper.PeImage(Path(gameassembly))
    index = BodyIndex(SimpleNamespace(mapper=mapper,pe=pe,metadata=None))
    return {**validate_context_allocation_control(index,c),'actualContextCallerAndParentProofsRechecked':True,
            'checkedContextCallerInstructions':parent_summary['checkedInstructions']}

def validate_current_native_contract(*,gameassembly=None,metadata=None):
    return validate_owner(sys.modules[__name__],gameassembly=gameassembly,metadata=metadata,
        open_claims={'allocationSuccessOrNonzeroReturnProved':False,'liveAllocationCalleeSelected':False,
            'initializedAllocatorProtocolOrValidCapacityProved':False,'clearHelperResultEqualsOldCursorProved':False,
            'clearHelperStoresOrVisibilityProved':False,'incomingSlotContentsUnchangedProved':False,
            'callbackCursorEqualityProved':False,'positiveListAdmitted':False,'wholeRootAdmitted':False},
        check='native-context-allocation-control',expected='actual caller argument join and complete owned reservation/refill/node/clear-tail program',
        phase='context allocation control')
