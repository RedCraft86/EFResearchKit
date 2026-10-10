"""Gate context body/control proofs and recheck their actual caller joins."""
from __future__ import annotations
import sys
from pathlib import Path
from types import SimpleNamespace
from scripts.common import check_installed_native_inputs
from scripts.game_data.contracts import CONTRACTS_DIR
from scripts.game_data.il2cpp.body_claims import BodyIndex
from scripts.game_data.il2cpp.native_image import NATIVE_MAPPER_PATH, read_reviewed_contract
from scripts.game_data.il2cpp.protocol import load_native_mapper
from scripts.game_data.il2cpp.context_setup_control import validate_context_setup_control
from scripts.game_data.memorypack import buff_formatter_relation_import_control as parent_owner
from scripts.game_data.memorypack.corpus_gate import _fingerprint
from scripts.game_data.memorypack.native_owner import fail, proof_sources, validate_owner

LABEL = 'buffFormatterContextSetup'
SCOPE = 'selected-context-complete-owned-cfg-first-field-program-and-address-handoffs-only'
PATH = CONTRACTS_DIR / 'buff_formatter_context_setup_native.json'


def _fail(check, expected, actual, *, native_inputs=None):
    fail(LABEL, SCOPE, PATH, check, expected, actual, native_inputs=native_inputs)


def _contract():
    c, _ = read_reviewed_contract(PATH, schema='endfield.buff-formatter-context-setup-native-contract.v1',
                                  status='exact-current-build', label=LABEL)
    if (c.get('scope'), c.get('parentContract')) != (SCOPE, 'buff_formatter_relation_import_control_native.json'):
        _fail('contract-shape', 'reviewed scope and parent', c.get('scope'), native_inputs=c.get('nativeInputs'))
    return c


def _proof_sources():
    return proof_sources(__file__, PATH, parent_owner._proof_sources(), NATIVE_MAPPER_PATH)


def _validate_selected(gameassembly, c):
    parent = parent_owner._contract()
    if parent['nativeInputs'] != c['nativeInputs'] or parent['entryRva'] != c['callerEntryRva']:
        _fail('parent-build-entry', (parent['nativeInputs'], parent['entryRva']),
              (c['nativeInputs'], c['callerEntryRva']), native_inputs=c['nativeInputs'])
    parent_summary = parent_owner._validate_selected(gameassembly, parent)
    selected = [{'callerRole': b['role'], 'childRva': b['childRva']} for b in parent['blocks']]
    functions = {f['role']: f['entryRva'] for f in c['functions']}
    if (selected != c['callerContextTargets'] or functions != c['selectedFunctionEntries'] or
            set(functions.values()) != {r['childRva'] for r in selected}):
        _fail('actual-caller-child-joins', selected, c['callerContextTargets'], native_inputs=c['nativeInputs'])
    mapper = load_native_mapper(NATIVE_MAPPER_PATH); pe = mapper.PeImage(Path(gameassembly))
    index = BodyIndex(SimpleNamespace(mapper=mapper, pe=pe, metadata=None))
    summary = validate_context_setup_control(index, c)
    return {**summary, 'actualCallerAndParentProofsRechecked': True,
            'checkedCallerInstructions': parent_summary['constantFlowCfgInstructions']}


def validate_current_native_contract(*, gameassembly=None, metadata=None):
    return validate_owner(sys.modules[__name__], gameassembly=gameassembly, metadata=metadata,
        open_claims={'secondCompleteTypedFieldProgramProved': False,
                     'incomingSlotContentsUnchangedProved': False,
                     'allocationOrCopyCalleeEffectsProved': False,
                     'actualRuntimeClassOrFormatterSelected': False,
                     'callbackCursorEqualityProved': False,
                     'positiveListAdmitted': False, 'wholeRootAdmitted': False},
        check='native-context-control',
        expected='actual caller joins, complete owned CFGs, first field program and conditional incoming address handoffs',
        phase='context control')
