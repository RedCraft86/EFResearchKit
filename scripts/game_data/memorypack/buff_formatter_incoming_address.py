"""Gate the complete incoming-address helper and its actual context caller."""
from __future__ import annotations
import sys
from pathlib import Path
from types import SimpleNamespace
from scripts.common import check_installed_native_inputs
from scripts.game_data.contracts import CONTRACTS_DIR
from scripts.game_data.il2cpp.body_claims import BodyIndex
from scripts.game_data.il2cpp.native_image import NATIVE_MAPPER_PATH,read_reviewed_contract
from scripts.game_data.il2cpp.protocol import load_native_mapper
from scripts.game_data.il2cpp.pe_imports import resolve_named_import_slots
from scripts.game_data.il2cpp.initializer_control import validate_initializer_control
from scripts.game_data.memorypack import buff_formatter_class_ancestry as parent_owner
from scripts.game_data.memorypack import buff_formatter_context_setup as context_owner
from scripts.game_data.memorypack.corpus_gate import _fingerprint
from scripts.game_data.memorypack.native_owner import fail,proof_sources,validate_owner

LABEL='buffFormatterIncomingAddress'
SCOPE='complete-owned-input-address-helper-control-writes-homes-and-handoffs-only'
PATH=CONTRACTS_DIR/'buff_formatter_incoming_address_native.json'


def _fail(check,expected,actual,*,native_inputs=None):
    fail(LABEL,SCOPE,PATH,check,expected,actual,native_inputs=native_inputs)


def _contract():
    c,_=read_reviewed_contract(PATH,schema='endfield.buff-formatter-incoming-address-native-contract.v1',
                               status='exact-current-build',label=LABEL)
    if (c.get('scope'),c.get('parentContract'),c.get('contextContract'))!=(SCOPE,'buff_formatter_class_ancestry_native.json','buff_formatter_context_setup_native.json'):
        _fail('contract-shape','reviewed scope and parent/context',c.get('scope'),native_inputs=c.get('nativeInputs'))
    return c


def _proof_sources():
    return proof_sources(__file__,PATH,parent_owner._proof_sources(),NATIVE_MAPPER_PATH)


def _validate_selected(gameassembly,c):
    parent=parent_owner._contract();context=context_owner._contract();second=next(f for f in context['functions'] if f['role']=='second')
    entry=c['function']['entryRva']
    actual={'entryRva':second['entryRva'],'callSites':[r for r in second['directCalls'] if r['targetRva']==entry],
            'inputAddressHelperCallRva':second['incomingAddressCallRvas'][-1],
            'handoffStartRva':second['addressHandoff']['helperHandoffStartRva']}
    if (parent['nativeInputs']!=c['nativeInputs'] or context['nativeInputs']!=c['nativeInputs'] or
        second['addressHandoff']['helperTargetRva']!=entry or c['callerJoin']!=actual or not actual['callSites']):
        _fail('actual-context-helper-join',actual,c['callerJoin'],native_inputs=c['nativeInputs'])
    if c['namedGetterPhysicalFields']!=parent['physicalFields']:
        _fail('named-getter-field-provenance',parent['physicalFields'],c['namedGetterPhysicalFields'],native_inputs=c['nativeInputs'])
    parent_summary=parent_owner._validate_selected(gameassembly,parent)
    mapper=load_native_mapper(NATIVE_MAPPER_PATH);pe=mapper.PeImage(Path(gameassembly));base=pe.image_base
    slots=sorted({r['cell']-base for r in c['function']['calls'] if r['kind']=='indirectCall'})
    imports=resolve_named_import_slots(pe,slots)
    if imports!=c['importDeclarations'] or imports!=parent['importDeclarations']:
        _fail('selected-helper-import-declarations',c['importDeclarations'],imports,native_inputs=c['nativeInputs'])
    index=BodyIndex(SimpleNamespace(mapper=mapper,pe=pe,metadata=None))
    summary=validate_initializer_control(index,c)
    return {**summary,'actualContextCallerAndNamedAncestryParentRechecked':True,
            'checkedNamedAncestryParentInstructions':parent_summary['checkedInstructions'],
            'checkedParentContextInstructions':parent_summary['checkedParentContextInstructions'],
            'exactSelectedHelperImportDeclarations':imports,'namedGetterPhysicalFields':c['namedGetterPhysicalFields'],
            'namedGetterOffsetsIdentifyLiveHelperReceiverProved':False,'conditions':c['conditions']}


def validate_current_native_contract(*,gameassembly=None,metadata=None):
    return validate_owner(sys.modules[__name__],gameassembly=gameassembly,metadata=metadata,
        open_claims={'incomingSlotContentsUnchangedProved':False,'completeTypedClassFieldMeaningProved':False,
                     'liveClassOrFormatterIdentityProved':False,'allocationCapacityAndInitializationOutcomeProved':False,
                     'recursiveTerminationProved':False,'callbackCursorEqualityProved':False,
                     'positiveListAdmitted':False,'wholeRootAdmitted':False},
        check='native-incoming-address-control',
        expected='actual context/helper join, complete owned control/write inventories, saved homes and address origins',
        phase='incoming address control')
