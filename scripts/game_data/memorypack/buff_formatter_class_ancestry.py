"""Join selected named class API programs to the formatter context proof."""
from __future__ import annotations
import sys
from pathlib import Path
from types import SimpleNamespace
from scripts.common import check_installed_native_inputs
from scripts.game_data.contracts import CONTRACTS_DIR
from scripts.game_data.il2cpp.body_claims import BodyIndex
from scripts.game_data.il2cpp.native_image import NATIVE_MAPPER_PATH, read_reviewed_contract
from scripts.game_data.il2cpp.protocol import load_native_mapper
from scripts.game_data.il2cpp.pe_exports import resolve_named_exports
from scripts.game_data.il2cpp.pe_imports import resolve_named_import_slots
from scripts.game_data.il2cpp.class_ancestry_control import GETTERS, validate_class_ancestry_control
from scripts.game_data.memorypack import buff_formatter_context_setup as parent_owner
from scripts.game_data.memorypack import buff_formatter_relation_import_control as import_owner
from scripts.game_data.memorypack.corpus_gate import _fingerprint
from scripts.game_data.memorypack.native_owner import fail, proof_sources, validate_owner

LABEL='buffFormatterClassAncestry'
SCOPE='selected-named-class-fields-and-complete-ancestry-consumer-join-only'
PATH=CONTRACTS_DIR/'buff_formatter_class_ancestry_native.json'


def _fail(check,expected,actual,*,native_inputs=None):
    fail(LABEL,SCOPE,PATH,check,expected,actual,native_inputs=native_inputs)


def _contract():
    c,_=read_reviewed_contract(PATH,schema='endfield.buff-formatter-class-ancestry-native-contract.v1',
                               status='exact-current-build',label=LABEL)
    if (c.get('scope'),c.get('parentContract'))!=(SCOPE,'buff_formatter_context_setup_native.json'):
        _fail('contract-shape','reviewed scope and parent',c.get('scope'),native_inputs=c.get('nativeInputs'))
    return c


def _proof_sources():
    return proof_sources(__file__,PATH,parent_owner._proof_sources(),NATIVE_MAPPER_PATH)


def _validate_selected(gameassembly,c):
    parent=parent_owner._contract(); imported=import_owner._contract()
    first=next(f for f in parent['functions'] if f['role']=='first');fields=first['physicalFields']
    actual={'parent':fields['linkedReceiver'],'ancestryArray':fields['array'],
            'ancestryDepth':fields['countByte'],'readyFlags':fields['flagByte']}
    selected={k:c['physicalFields'].get(k) for k in actual}
    if (parent['nativeInputs']!=c['nativeInputs'] or imported['nativeInputs']!=c['nativeInputs'] or
        c['selectedFirstContextEntryRva']!=first['entryRva'] or
        c['hasParent']['setupTargetRva']!=first['entryRva'] or actual!=selected or
        c['hasParent']['readyMask']!=first['readyMask']):
        _fail('first-context-field-and-call-joins',(first['entryRva'],actual,first['readyMask']),
              (c['selectedFirstContextEntryRva'],selected,c['hasParent']['readyMask']),native_inputs=c['nativeInputs'])
    expected_protocol={'globalContextRva':imported['globalContextRva'],'offsets':imported['contextOffsets']}
    if c['protocol']!=expected_protocol or c['imports']!=imported['imports']:
        _fail('context-protocol-declarations',(expected_protocol,imported['imports']),
              (c['protocol'],c['imports']),native_inputs=c['nativeInputs'])
    parent_summary=parent_owner._validate_selected(gameassembly,parent)
    mapper=load_native_mapper(NATIVE_MAPPER_PATH);pe=mapper.PeImage(Path(gameassembly))
    exports=resolve_named_exports(pe,list(GETTERS)+['il2cpp_class_has_parent'])
    if exports!=c['exportDeclarations'] or exports['libraryName'].casefold()!='gameassembly.dll':
        _fail('selected-pe-exports',c['exportDeclarations'],exports,native_inputs=c['nativeInputs'])
    imports=resolve_named_import_slots(pe,[r['slotRva'] for r in c['imports']])
    if imports!=c['importDeclarations'] or imports!=imported['importDeclarations']:
        _fail('selected-pe-imports',c['importDeclarations'],imports,native_inputs=c['nativeInputs'])
    index=BodyIndex(SimpleNamespace(mapper=mapper,pe=pe,metadata=None))
    summary=validate_class_ancestry_control(index,c,exports)
    return {**summary,'actualFirstContextProofAndNamedConsumerRechecked':True,
            'checkedParentContextInstructions':parent_summary['checkedInstructions'],
            'actualFirstContextStoredArrayHasNamedAncestryConsumer':True,
            'exactSelectedExportDeclarations':exports,'exactSelectedImportDeclarations':imports,
            'physicalFields':c['physicalFields'],'conditions':c['conditions']}


def validate_current_native_contract(*,gameassembly=None,metadata=None):
    return validate_owner(sys.modules[__name__],gameassembly=gameassembly,metadata=metadata,
        open_claims={'liveClassReceiverOrFormatterIdentityProved':False,
                     'incomingSlotContentsUnchangedProved':False,
                     'initializationOrSynchronizationOutcomeProved':False,
                     'validAncestryArrayCapacityProved':False,'recursiveTerminationProved':False,
                     'callbackCursorEqualityProved':False,'positiveListAdmitted':False,'wholeRootAdmitted':False},
        check='native-class-ancestry-control',
        expected='selected named field getter programs, complete has-parent control and actual first-context field/call joins',
        phase='class ancestry control')
