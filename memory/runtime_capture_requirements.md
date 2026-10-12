# Required runtime captures

This is the shared backlog of game-data evidence that still requires runtime
capture. Append future requirements here under their owning topic. Extend an
existing matching entry rather than duplicate it. Keep accepted entries with
their evidence boundary and owning-topic link so later work can reuse them.

For each requirement, record the unresolved question, required fields and
ordered phases, representative cases, acceptance criteria, and links to the
owning memory topic and reviewed contracts. Native sites and build-specific
layouts belong in contracts; changing counts, hashes, inventories and raw
sessions belong in ignored reports or capture directories. The owning topic
continues to hold durable conclusions. Collection policy and authorization
remain governed by [AGENTS.md](../AGENTS.md).

## Shared capture requirements

Every observation must carry enough identity to join it to its own invocation
and selected native program:

- Selected binary identities, including GameAssembly, metadata and UnityPlayer
  where required by the owning native contract; loaded module base and image
  bounds for any address rebasing.
- Session and process incarnation, thread ID, invocation ID, sequence and
  monotonic timestamp; explicit linkage between entry, intermediate phases,
  nested calls and return or failure endpoints.
- Exact native instruction/phase and the applicable observer schema, ABI and
  source recipe identity.
- Raw register/value bits and memory bytes with their declared widths,
  addresses, read extents and per-read success status. Preserve interpretation
  separately from the raw observations.
- Complete final receipt, consistent attempted/admitted/written accounting,
  drained and stable final counters, and no losses or required-field read/write
  errors. Incomplete or contradictory evidence withholds the affected claim.

An entry snapshot cannot establish a later read, completed helper, result or
storage write. Pointer equality needs same-invocation address/range evidence;
address reuse alone does not establish object lifetime. A caller address needs
an authenticated same-session map for its actual module.

## Cooked collision and live Mesh state

**Status:** accepted for the selected Dijiang light Mesh's CAB/PathID identity,
later completed-physics checkpoints, complete vertex/index cache equivalence,
and the observed Collider-to-PxShape-to-cache attachment.
The native-core session reaches every requested epoch without loss or lifetime
gaps. Its held `PxBVH34TriangleMesh` path and native getters authenticate the
pointer-bound arrays; the decoded values agree with the stored cooked payload
throughout the sampled epochs. Remap/edge/slab bytes also agree over their
stored extents. The intermediate busy identity-map lock remains explicit and
uses conditional retained-identity reuse; later direct mapped reads agree.
The saved Collider windows also establish concrete current-shape attachments
after instantiation and at the first completed-physics checkpoint, with partial
intermediate coverage. Their triangle geometry points to the same typed cache.
Later held shape pointers remain unchanged where sampled, but missing final
shape headers withhold fresh final geometry/flag claims. Another capture is
unnecessary for this selected geometry and attachment case. Distinct sources,
fresh uncaptured later shape fields and contact participation remain separate
requirements; the present observer does not measure collision pairs or contacts.

Owner: [DynamicStreaming collision recovery](game_data/world_dynamic_streaming.md#offline-boundary-and-next-capture).
Reviewed ABI, source and observation rules:
[collision_capture_native.json](../scripts/game_data/contracts/collision_capture_native.json).
Reviewed cache ownership/layout and saved-data comparison:
[collision_runtime_mesh_native.json](../scripts/game_data/contracts/collision_runtime_mesh_native.json),
[collision_runtime_mesh.py](../scripts/game_data/collision_runtime_mesh.py).
Reviewed Collider current-shape consumers and saved attachment comparison:
[collision_runtime_shape_native.json](../scripts/game_data/contracts/collision_runtime_shape_native.json),
[collision_runtime_shape.py](../scripts/game_data/collision_runtime_shape.py).
Stored cooked-format reader:
[cooked_collision.py](../scripts/game_data/cooked_collision.py).

For a new distinct source case, retain a continuous session from before scene instantiation through later
completed physics steps. Begin with the selected Dijiang hub resource so its
accepted source identity can be reused. A distinct prefab or scene is a new
case; its missing source or checkpoint is not repaired by another object's
observation. Require the following ordered phases:

- Exact stored Model bytes and source-file identity, grid/UniqueId, element,
  Guid and resource hash; loader request/result and the chosen root/parent.
- After original instantiation returns, enumerate children including inactive
  components. Record Collider and root/Transform/GameObject identities, world
  matrices, active/enabled/convex state and shared Mesh identity. Keep the
  post-parent and post-instantiation matrices as separate observations.
- In one native identity-map scope, retain the runtime Mesh's raw serialized
  filename, file index and PathID, plus its unique frozen-source join. A cloned
  Collider's absent serialized entry is a valid result, not a prefab PathID.
- Preserve native-core manager, scene handle and raw float step, entry/normal
  return linkage, and the exact nested completion call and return. Sample the
  retained objects after the requested later completed-step ordinals, with
  original enrollment time, managed pins and cached native-pointer/instance/
  root identity checks. Record destruction, replacement, busy locks and missing
  epochs explicitly; account for every retained handle at quiescent stop.
- At instantiation and the later checkpoints, retain bounded native
  Collider/Mesh windows, read ranges, region/protection metadata, parent pointer
  edges, timestamps, traversal/read/queue limits and archive hashes. Preserve
  these as opaque bytes until authenticated native consumers establish cache
  ownership and layouts. The admitted selected case has that owning path and
  complete array comparison; a copied float sequence or nearby pointer alone
  cannot establish a PhysX object or a live triangle buffer.

Accept the selected stored-source identity separately from later state and
cache geometry. Later state requires the normal-return/completion and lifetime
joins. Runtime geometry requires an authenticated owning cache path, bounded
array counts and element widths, and a complete decoded comparison with the
selected stored payload; uncaptured representations remain unknown.
Shape attachment additionally needs the native Collider current-shape consumer,
the concrete PxShape type and that same invocation's geometry-to-cache join.
Preserve missing later shape fields independently from observed held pointers;
do not fill them from a different invocation or retained address alone. Contact
participation needs its own observed pair/shape ownership and result phases,
which this observer does not implement. Stop after coverage reaches the final
requested checkpoint for every still-live retained object, then require the
shared clean-receipt and stable-file gates. Carry forward each accepted phase
without requesting it again merely because another phase remains open.

## Mission timeline

**Status:** the next useful evidence for handoff chronology and live parameter/
combined-cache behavior requires capture. Additional ordinary callee review can
refine conditional transfers but cannot settle these runtime joins.

Owner: [Story carriers](game_data/story_carriers.md#shared-mission-state-and-condition-connections)
and [Story recovery](webui/story_recovery.md#remaining-gaps).
Reviewed native rules:
[mission_expression_native.json](../scripts/game_data/contracts/mission_expression_native.json),
[mission_shared_native.json](../scripts/game_data/contracts/mission_shared_native.json).
Existing entry observers:
[mission_trace_capture.json](../scripts/game_data/contracts/mission_trace_capture.json).
Entry-only support does not imply that the outcome/intermediate phases below
are implemented by that recipe.

The additional focused observer is prepared in
[mission_state_trace_capture.json](../scripts/game_data/contracts/mission_state_trace_capture.json).
Its versioned GP-only paired ABI records state activation/callback snapshots,
AST parse/evaluation recursion, result setters and selected owning callbacks
with explicit thread, invocation, parent and entry/return identity. Param cells
use the authenticated concrete setter witnesses; the closed EventData layout
and native indirect callback argument are separately proved. The maintained
preparer, native collector and inspector reject missing/crossing pairs,
exceptions, depth overflow, loss and Stop within a live invocation. Use the
internal `CaptureMissionStateAst.bat` launcher and its `-CheckOnly` branch.
This is offline preparation, not a completed live capture. Params are sampled
at activation entry/return, not at every resolver instruction. Constructor/
subscription selection, all supplied child snapshots, effective IFix selection
and atomic cache coherence remain additional joins.

### Continuous quest handoff

Start before the last action of a currently available multi-quest route, and
retain one continuous interval through predecessor success, successor new
start and successor activation or its explicit absence. Preserve incoming
quest/mission state packet identity and state, supplied quest-action identity,
restoration flags, objective/condition identity, and any dialogue identities.
Include the screen recording and a clean final receipt. Runtime IDs select the
definition: reused display text and labels do not select daily variants.

Accept only the observed, explicitly owned route and its same-invocation or
same-thread local order. Do not infer server policy, successful returns,
playback ownership or a total mission order from entries. A later restoration
of the successor cannot repair an older unrecorded transition; repairing that
historical interval needs its original evidence or a legitimately replayable
case, not another unrelated recording.

### Live state predicates and combined evaluation

Choose a currently accessible case whose authenticated definition contains a
quest/mission-state predicate, preferably nested in a combined condition. Such
a definition is a capture candidate only: the reviewed default Mission leaf
lane excludes these non-ClientOnly predicates, so their native activation is
not guaranteed. Preserve a consumer/owner join if they execute through another
lane; leave an unhit hook as unobserved.

For a selected invocation, require:

- Condition receiver/lifetime and owning mission/quest/objective/source path;
  effective native/patch choice and applicable context.
- The actual Param references, typed constant/raw value, source selector,
  reference ID and path at resolution, plus the returned ID, comparator and
  target cached in that same condition. To claim construction, additionally
  retain the selected source bytes, JSON/MemoryPack reader/creator, created or
  reused object identity and before/after fields. A value constructor or stored
  JSON constant by itself cannot identify this join.
- Event subscription identity and completion; initial state query/outcome and
  initial result update; later matching event key, ID and state with its own
  dispatch/invocation linkage. Quest activation binds before its initial result,
  while mission activation sets its initial result before binding. Keep initial
  matches separate from later event-driven matches.
- Child/root/parent identities and cached results, expression/AST association,
  entry/intermediate/return linkage, result writes and callback/parent-evaluation
  nesting. Include every supplied child's decided state, even when unused by
  the expression. Observe mutation/reentrancy or enough paired outcomes to
  establish the bounded interval's quiescence.

Accept live operands, a completed result update or a nested-cache consequence
only with these phase/identity joins and the shared clean-receipt requirements.
The existing entry recipe can establish chronological carriers but cannot
alone close construction, result returns or callback quiescence. Develop and
validate any additional observer offline before requesting a recording.

Authoritative server admission remains a separate question. A received state
sequence records the selected outcome; it does not reveal the selection rule.

## IFix

**Status:** required runtime observations remain unobserved. Retained unrelated
entry profiles do not close these questions.

Owner: [IFix patch and VM evidence](game_data/ifix_patch.md).
Reviewed requirements:
[ifix_runtime_evidence.json](../scripts/game_data/contracts/ifix_runtime_evidence.json).
Native programs and layouts:
[ifix_vm_operands_native.json](../scripts/game_data/contracts/ifix_vm_operands_native.json).

### Reference aliasing: negative instance fields

For each selected `Ldfld` or `Stfld` invocation, capture:

- The raw field operand, resolved field index, receiver, evaluation base and
  selected unmanaged-field address.
- Source and destination Value descriptor addresses and their complete
  12-byte contents before copying.
- Receiver, unmanaged-array/header and computed field-address observations
  across copy and rebase, to establish the stable-storage premises separately
  from managed-array identities.
- The source tag actually read after both copy stores, including the observed
  branch selection.
- On the managed branch, the destination `Value1` rebase write and, for
  `Stfld`, the source `Value1` subsequently reread after that rebase.
- Managed-array identities, lengths and the selected reference before
  assignment/store requests, followed by the destination state after the
  request and the correlated normal return or failure endpoint.

Cover distinct nonoverlapping descriptors, identical Value addresses, partial
overlap changing the post-copy tag guard, a `Stfld` rebase changing the later
source index, and distinct/shared managed arrays. Record only relations actually
observed; an unavailable case remains open.

Accept a sampled alias consequence only when its ordered phases, descriptor
bytes, address stability and array/reference prerequisites are independently
supported. A store request and a completed store are separate observations.

### Generic contexts and results

For each selected `GetAsType` or GenericDelegate bridge invocation, capture:

- The actual ordinary or adjustor entry, incoming arguments and hidden context
  carrier according to that entry's reviewed native ABI.
- The saved incoming context, whether preparation ran, and the effective
  context pointer and selected entry at the actual consuming query.
- For `GetAsType`, the context entry reloaded after optional preparation and
  `GetObject`; for Func bridges, the result-type entry reloaded after `Execute`
  and `GetObject`, selected according to generic input arity. Action bridges
  have preparation observations but no local typed result-entry query.
- Type-query input and returned Type carrier, correlated cast or unbox
  outcome, returned pointer/scalar bits, and readable result-storage provenance.
- The reference selected by `GetObject` before clearing and the physical slot
  after clearing as separate phases.
- For adjustors, the receiver/context before adjustment and the values forwarded
  to the ordinary target, linked to the same invocation.

Cover reference, bool and native-pointer results; prepared/unprepared contexts;
ordinary/adjustor entries; and the same generic code with different runtime
contexts.

Accept raw context bits independently of a type interpretation. Effective
contexts and results require the consuming phase and paired outcome; entry
addresses, stored candidates and printed names do not identify the live closed
type. Byref ambiguity, unsupported layouts, missing phases or failed reads
withhold the corresponding interpretation.

### Closed generic and delegate identity

To claim closed-type selection or delegate construction/dispatch, additionally
capture:

- An authenticated mapping from the actual native runtime context to its method
  definition and generic instantiation.
- Separate class and method generic arguments, including raw type carriers,
  their kinds, arities and byref flags.
- The constructed delegate type, target, managed reflection MethodInfo,
  selected registered wrapper and observed invocation linkage.
- An authenticated connection between managed reflection identity and the
  native hidden context wherever that connection is claimed. These are
  different representations and need their own bridge evidence.

An ordinary shared-code address or a stored MethodSpec alone does not establish
this join. Keep opaque contexts unresolved until their mapping is proved.

### Patch execution lineage

To attribute observed behavior to an installed patch, capture:

- Accepted patch bytes/hash at `LoadInternal`.
- The selected fix record and registered wrapper identity.
- Same-invocation `IsPatched`/`GetPatch` selection and `Execute` entry, with the
  selected VM method and instruction position.

Keep patch-file declarations, wrapper registration and observed execution as
separate facts until this lineage is joined. Alias/context observations alone
do not prove that a declared replacement ran.

## Endminf later portrait refraction and temporal composition

**Status:** later portrait inputs received and independently analysed; no repeat
is requested now. The native provider/collector verdict remains incomplete
because shutdown erased retained CPU scope before report publication. A separate
source-authenticated retained-input scope rechecks the complete original
native/module/loss/payload/chronology joins, and selected original draw/post
replays are exact. Strict readers never substitute this scope. The reporting
bug is corrected and the new runtime passes build and nonlaunching preflight.
The completed first-pre-portrait transaction still describes its own different
effect and post phase.
Local Unity DLSS loaded-module identity is repaired and verified. Lab stage
isolation identifies M28 refraction as the main settled head-edge loss boundary;
the fragment-helper and texture controls do not justify a renderer default fix.

Owner: [lab capture queue](../endfield_reconstruction_lab/docs/capture-queue.md).
Durable rendering interpretation:
[lab rendering boundary](../endfield_reconstruction_lab/docs/rendering-pipeline-and-shadows.md).
Internal observer schemas, preparation and operator steps remain in the
EndfieldCapture checkout. Build with `Build.ps1`, then select a recipe with
`Capture.ps1`. The recorder consumes the supplied native declarations without
producer-side fingerprint, code-window or receipt verification; collection only
inventories files. Required source/native admission remains an independent
recovery-consumer concern and is not established by a successful capture.

Required ordered phases in one own Present:

- Exact body Forward selection after own Character Info Play in the reviewed
  later portrait window, with actor/Animator/cohort identity and original
  geometry, programs, constants, resources and target/depth state.
- Own opaque outline and M28 refraction inputs and before/after outputs.
- Tagged DLAA colour, depth and motion inputs/output, selected token/viewport,
  options/constants, exposure and evaluation entry/return chronology.
- Original post-consumer programs, inputs/state/output and presented SDR bytes,
  with exact linkage to the same body/refraction/temporal Present.

Acceptance requires complete native provider and scoped publications, no losses,
selected-build/module/source identity, complete authenticated payloads and exact
chronology. Original replays must reproduce the retained outputs before visual
stage measurements support a source correction. Early or shifted frames and
missing M28 remain withheld. Internal DLAA history, movie cadence, source-pose
parity, particle birth and renderer ownership are separate claims; an unrelated
active-particle timing bracket is not required for this draw transaction.

The received evidence supports bounded original-input and stage-contribution
analysis. Native provider completion remains withheld. Later radial post is
inactive; DLAA brightens the own selected dark-edge mask on average. The own
M28 output and tagged DLAA input differ across intervening processing, whose
individual producers are not captured by this transaction. Matching lab inputs,
source pose and internal history remain offline recovery questions rather than
reasons to repeat this capture automatically.
