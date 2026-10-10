"""Authenticate the selected Baselib exports, imports and complete owned control.

All four native files are selected and checked before and after the proof.
On-disk declarations and conditional ABI flow never establish live bindings,
valid semaphore initialization, wait/retry termination or Buff root admission.
"""
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
from scripts.game_data.il2cpp.baselib_semaphore_control import validate_baselib_semaphore_control
from scripts.game_data.memorypack import buff_formatter_relation_import_control as parent_owner
from scripts.game_data.memorypack.corpus_gate import _fingerprint
from scripts.game_data.memorypack.native_owner import fail, proof_sources, validate_owner

LABEL = 'buffFormatterBaselib'
SCOPE = 'selected-baselib-export-import-and-complete-semaphore-thread-control-only'
PATH = CONTRACTS_DIR / 'buff_formatter_baselib_native.json'


def _fail(check, expected, actual, *, native_inputs=None):
    fail(LABEL, SCOPE, PATH, check, expected, actual, native_inputs=native_inputs)


def _contract():
    c, _ = read_reviewed_contract(PATH,
        schema='endfield.buff-formatter-baselib-native-contract.v1',
        status='exact-current-build', label=LABEL)
    if (c.get('scope'), c.get('parentContract'), c.get('libraryName')) != (
            SCOPE, 'buff_formatter_relation_import_control_native.json', 'baselib.dll'):
        _fail('contract-shape', 'reviewed scope, parent and library',
              (c.get('scope'), c.get('parentContract'), c.get('libraryName')), native_inputs=c.get('nativeInputs'))
    return c


def _proof_sources():
    return proof_sources(__file__, PATH, parent_owner._proof_sources(), NATIVE_MAPPER_PATH)


def _validate_selected(gameassembly, c, *, selected_inputs=None):
    parent = parent_owner._contract()
    parent_pins = {name: c['nativeInputs'].get(name) for name in parent['nativeInputs']}
    if parent['nativeInputs'] != parent_pins or parent['entryRva'] != c['callerEntryRva']:
        _fail('parent-build-entry', (parent['nativeInputs'], parent['entryRva']),
              (parent_pins, c['callerEntryRva']), native_inputs=c['nativeInputs'])
    parent_summary = parent_owner._validate_selected(gameassembly, parent)
    caller_imports = parent_summary['exactSelectedImportDeclarations']['selectedImports']
    by_slot = {r['slotRva']: r for r in caller_imports}
    roles = {r['role']: r['slotRva'] for r in parent['imports']}
    if (set(roles) != {'Acquire', 'Release', 'ThreadId'} or len(parent['imports']) != 3 or
            len(by_slot) != 3 or set(by_slot) != set(roles.values()) or
            any(r['libraryName'].casefold() != c['libraryName'].casefold() for r in caller_imports)):
        _fail('caller-import-role-ownership', 'three selected named Baselib declarations',
              caller_imports, native_inputs=c['nativeInputs'])
    library = (Path(gameassembly).parent / c['libraryName'] if selected_inputs is None
               else Path(selected_inputs[c['libraryName']]))
    mapper = load_native_mapper(NATIVE_MAPPER_PATH); pe = mapper.PeImage(library)
    exports = resolve_named_exports(pe, [r['symbolName'] for r in caller_imports])
    if exports != c['exportDeclarations'] or exports['libraryName'].casefold() != c['libraryName'].casefold():
        _fail('pe-export-declarations', c['exportDeclarations'], exports, native_inputs=c['nativeInputs'])
    by_name = {r['symbolName']: r for r in exports['selectedExports']}
    functions = {f['role']: f for f in c['functions']}
    if set(functions) != set(roles) or len(c['functions']) != 3:
        _fail('export-function-roles', sorted(roles), sorted(functions), native_inputs=c['nativeInputs'])
    for role, slot in roles.items():
        name = by_slot[slot]['symbolName']; row = by_name[name]; f = functions[role]
        if row['isForwarder'] or (f['symbolName'], f['entryRva']) != (name, row['targetRva']):
            _fail('named-export-function-join', (role, name, row['targetRva'], False),
                  (role, f['symbolName'], f['entryRva'], row['isForwarder']), native_inputs=c['nativeInputs'])
    if len({f['entryRva'] for f in functions.values()}) != 3:
        _fail('distinct-function-entries', 'three distinct selected entries',
              [f['entryRva'] for f in functions.values()], native_inputs=c['nativeInputs'])
    imports = resolve_named_import_slots(pe, [r['slotRva'] for r in c['kernelImports']])
    if imports != c['importDeclarations']:
        _fail('pe-kernel-import-declarations', c['importDeclarations'], imports, native_inputs=c['nativeInputs'])
    kernel = {r['slotRva']: r for r in imports['selectedImports']}
    for r in c['kernelImports']:
        row = kernel[r['slotRva']]
        if row['libraryName'].casefold() != 'kernel32.dll' or row['symbolName'] != r['role']:
            _fail('kernel-role-ownership', ('KERNEL32.dll', r['role']),
                  (row['libraryName'], row['symbolName']), native_inputs=c['nativeInputs'])
    index = BodyIndex(SimpleNamespace(mapper=mapper, pe=pe, metadata=None))
    summary = validate_baselib_semaphore_control(index, c)
    return {**summary, 'exactSelectedExportDeclarations': exports,
            'exactSelectedKernelImportDeclarations': imports,
            'actualCallerAndParentProofsRechecked': True,
            'selectedLibraryPath': library.as_posix(),
            'checkedCallerInstructions': parent_summary['constantFlowCfgInstructions'],
            'conditions': c['conditions']}


def validate_current_native_contract(*, gameassembly=None, metadata=None, baselib=None):
    return validate_owner(
        sys.modules[__name__], gameassembly=gameassembly, metadata=metadata,
        additional_inputs={'baselib.dll': baselib},
        open_claims={'completeTypedRelationMeaningProved': False,
                     'actualLoadedLibraryOrIatBindingProved': False,
                     'validSemaphoreInitializationOrObservedEffectsProved': False,
                     'finiteWaitOrRetryProved': False,
                     'callbackCursorEqualityProved': False,
                     'positiveListAdmitted': False, 'wholeRootAdmitted': False},
        check='native-baselib-control',
        expected='actual selected name/ordinal/function and kernel import joins plus complete owned programs',
        phase='Baselib export/import/control')
