# DynamicStreaming main grids and area records

Part of [`../game_data_recovery.md`](../game_data_recovery.md). See
[`README.md`](README.md) for the level and lane map.

**Level 3, world lane.** The main `fb_main_*.bytes`, area `FBStreamArea.bytes`
and version `fb_version.bytes` roots have selected-build generated FlatBuffer
accessors; the auxiliary `fb_init`/`fb_streaming` roots have none. Envelopes
and root framing belong to
[`dynamic_streaming.py`](../../scripts/game_data/dynamic_streaming.py). Field
names come from the reviewed [`contracts/`](../../scripts/game_data/contracts/)
and the modules below, whose docstrings hold layouts and proof detail.

## Shared proof pattern

Each native audit gates on the explicit installed `GameAssembly.dll` and
`global-metadata.dat` (plus `UnityPlayer.dll` for UnityPlayer routes),
matches pinned code windows or named body claims, and fails closed on a
missing or mismatched build. Each corpus gate rejoins every dumped file to
the authenticated VFS ledger by path, length and FileDataMd5 before naming a
field. Changing counts, value distributions, scene sets and receipts live in
the generated reports under `reports/animestudio/` (portal join:
`reports/game_data/`). A **direct conditional** route below is a selected
unpatched body: cache hits, failed lookups, other branches and iFix
`IsPatched` wrappers may take other paths, and no route records what ran in
play.

| Module | Owns |
| --- | --- |
| [`dynamic_main_native`](../../scripts/game_data/dynamic_main_native.py) | main `SingleGrid` vector widths; DataMask presence test |
| [`dynamic_data_index_native`](../../scripts/game_data/dynamic_data_index_native.py) | DataIndex layout; grid-local Type/Index partitions |
| [`dynamic_scalar_components_native`](../../scripts/game_data/dynamic_scalar_components_native.py) | scalar and spatial inline component getters, builder field parameters, MissionCondition string-index consumer and current-corpus value census |
| [`dynamic_system_routing_native`](../../scripts/game_data/dynamic_system_routing_native.py) | `EDynamicSceneData` to system route |
| [`dynamic_root_comp_native`](../../scripts/game_data/dynamic_root_comp_native.py) | RootComp layout and partition, authenticated directory-to-instance owner decoder, visible groups and controller, template lookup and match, lifecycle, IdComp branch |
| [`dynamic_resource_comp_native`](../../scripts/game_data/dynamic_resource_comp_native.py) | ResourceComp, ResourceGroupWithStateDesc, cross-grid payloads |
| [`dynamic_resource_state_native`](../../scripts/game_data/dynamic_resource_state_native.py) | selected ResourceGroup LogicState query mask and zero-overlap skip |
| [`dynamic_model_runtime_native`](../../scripts/game_data/dynamic_model_runtime_native.py) | named body claims for stored-transform/grid-matrix calls, instantiated-model parenting and child-collider enable control |
| [`dynamic_model_native`](../../scripts/game_data/dynamic_model_native.py) | complete inline Model fields, current main-file bytes and manifest prefab-path joins; optional declared prefab-root/collider joins |
| [`collision_runtime_mesh`](../../scripts/game_data/collision_runtime_mesh.py), [`collision_runtime_mesh_native`](../../scripts/game_data/collision_runtime_mesh_native.py) | admitted saved-window decoder and native Unity Mesh held-cache/type/count/index-width proof; one source-bound runtime geometry comparison per sample |
| [`collision_runtime_shape`](../../scripts/game_data/collision_runtime_shape.py) | admitted Collider current-shape member, concrete PxShape and same-call source-bound triangle-cache attachment; independent actor/flag fields and missing-window diagnostics |
| [`dynamic_sludge_surf_tile_native`](../../scripts/game_data/dynamic_sludge_surf_tile_native.py) | `SludgeComp.SurfTileIDs`; `PrimitiveIntList` closure; conditional navmesh consumer |
| [`dynamic_visibility_area_join`](../../scripts/game_data/dynamic_visibility_area_join.py), [`dynamic_visibility_state_join`](../../scripts/game_data/dynamic_visibility_state_join.py) | visible-group values to area IDs and MapConfig states |
| [`dynamic_visibility_runtime_native`](../../scripts/game_data/dynamic_visibility_runtime_native.py) | body claims: scene state, conditions, MapConfig and streaming-config load, loader file selection, area dealer and centers, portal assignment, spawn and AOI |
| [`dynamic_streaming_config_join`](../../scripts/game_data/dynamic_streaming_config_join.py) | MapConfig to `StreamingMapConfig` asset and scene roots |
| [`dynamic_main_path_join`](../../scripts/game_data/dynamic_main_path_join.py) | `fb_main` filename to root `UniqueId` |
| [`dynamic_version_native`](../../scripts/game_data/dynamic_version_native.py), [`dynamic_version_id_domain`](../../scripts/game_data/dynamic_version_id_domain.py) | version root and entries; same-scene IdComp join |
| [`dynamic_active_version_native`](../../scripts/game_data/dynamic_active_version_native.py), [`dynamic_version_ban_native`](../../scripts/game_data/dynamic_version_ban_native.py) | branch-version source and parser; ban-set consumer |
| [`dynamic_aux_pair_corpus`](../../scripts/game_data/dynamic_aux_pair_corpus.py), [`dynamic_aux_bridge_native`](../../scripts/game_data/dynamic_aux_bridge_native.py) | auxiliary pair relations and descriptor 21; native path-to-copy route |
| [`dynamic_stream_area_corpus`](../../scripts/game_data/dynamic_stream_area_corpus.py), [`dynamic_stream_area_native`](../../scripts/game_data/dynamic_stream_area_native.py) | area framing; area records, relations, `CheckInArea` |
| [`portal_center_join`](../../scripts/game_data/portal_center_join.py) | portal template and override destination vectors |

## Model instantiation and collider control

[`dynamic_model_native.json`](../../scripts/game_data/contracts/dynamic_model_native.json)
records the selected generated Model layout, nested getter carriers and builder
declarations. Its validator authenticates the explicit installed native pair
and the independent main-vector contract before decoding. The inline record
contains Guid words, Trans position/rotation/scale, LodGridChain, PathHash and
VisibilityInfo. Each transform member carries three float32 axes; do not read
stored Rot as a four-component quaternion. Full nested fields tile the record.
Nonfinite visibility values are stored float32 representations, not a framing
failure: retain their exact bit pattern and special-value class, without
assigning sentinel semantics.

The current-corpus gate rejoins every main file and the manifest by VFS length
and MD5, then resolves unsigned PathHash against native-validated AssetInfo
rows. Repeated identical manifest rows add no association; distinct path/Bundle
rows with one hash remain ambiguous. `--scene-receipt` revalidates an existing
selected scene export, then requires asset path, active logical Bundle and the
AssetBundle container's actual GameObject root before linking its colliders.
The result stores the authored Model transform beside the prefab-local matrix;
it deliberately does not synthesize a live world matrix. Per-build counts and
object rows live in `reports/animestudio/dynamic_model_current_latest.json`.

[`dynamic_model_runtime_claims.json`](../../scripts/game_data/contracts/dynamic_model_runtime_claims.json)
reproves selected method bodies by name on explicit native/metadata inputs.
`DynamicSceneModelSystem._GetModelTransform` contains the named stored
`Pos`/`Rot`/`Scl` getter calls, `DynamicStreamingScene.GetMat`, matrix point
and vector multiplication, and quaternion look-rotation calls. The instantiated
model path calls that transform routine, obtains a root Transform and calls
`Transform.SetParent`. A prefab's stored root-to-collider TRS is therefore only
one part of the placement investigation; a selected grid matrix, parent and
instantiated-prefab identity need their own joins.

`_SetColliderEnable` reads the named collider cache and contains child-component
collection and `Collider.set_enabled` calls. Saved prefab enabled/active flags
are authored state, not a proof of live collider activation. These claims prove
named reads/calls, including the evaluator's bounded owned fragments and
one-helper boundary. They do not prove complete argument dataflow, the branch
that ran, a live grid/parent value, subsequent animation or an IFix patch's
effect. A failed source gate produces no method rows; a failed claim remains
`pendingReview` in a separate report. Current method bodies, hashes and outcomes
are in `reports/animestudio/dynamic_model_runtime_claims_latest.json`.

The named claims also check Model.PathHash reads and
`ResourceManager.InstantiatePrefabAsync` calls in `_DoInitModel`.
`DynamicStreamingScene.GetMat` reads `m_runtimeMapData` and calls its sparse-array
element accessor; `OnAddUniqueId` allocates an id, accesses that array and calls
`Matrix4x4.TRS`. The registration API takes a scene unique-id string, direction,
position and bounds. Its selected runtime matrix and id mapping are not fields
in the stored Model record. These claims establish the source of the remaining
runtime boundary, while preserving their named-call/field-read scope.

### Offline boundary and next capture

Supported cooked geometry, stored prefab hierarchy and authored Model resource
paths can be recovered offline. Static coverage can still be widened to more
prefabs, but it cannot identify which loading/hold/IFix branch ran, which
GameObject was instantiated, the selected registration matrix and parent, or
the enabled/active state after animation and gameplay changes. Those questions
now warrant a bounded live capture.

Capture one source-identified Model in a known scene, carrying its source-file
hash, grid ordinal/UniqueId, element ordinal, Guid words and PathHash. Keep the
following events in one ordered, call-correlated session:

- `OnAddUniqueId` and `GetMat`: registration name, direction, position/bounds,
  runtime id, selected matrix and return status.
- `_DoInitModel` and `_DoInitInstantiateModel`: Model identity, requested prefab
  hash, resource handle/result, instantiated GameObject instance id, selected
  root/parent and resulting transform.
- `_GetModelTransform` and the collider-control route: input stored transform,
  selected scene matrix, returned transform, collider/mesh instance ids and
  enabled/active transitions. Snapshot collider world matrices after parenting
  and after the next physics update, so later changes remain distinguishable.

Use the checked serialized prefab root and Mesh CAB/PathID/raw/cooked hashes as
the offline side of the join. A runtime pointer, display name or reused
instance id alone is insufficient: record the resource/object lifetime and a
loader-to-instance identity bridge. Validate the selected-build ABI and hidden
return carriers before installing hooks, especially Matrix4x4 and
FAssetProxyHandle returns; named-call claims do not validate these carriers.
Do not infer active colliders from the prefab's saved flags or report a failed
load as an instantiated object. The generated current target shortlist belongs
in `reports/assets/collision_live_capture_plan.json`.

The first observer is prepared through
`scripts.game_data.collision_capture_prepare` and the standalone collision
target in `tools/EndfieldCapture/providers/collision/`. It uses EndfieldCapture's existing
prelaunch host and strict MinHook transaction implementation. The reviewed
`collision_capture_native.json` contract proves selected metadata signatures,
by-reference parameters, carrier/field layouts and bounded native bodies.
Preparation preserves the explicit output pointers of `_GetModelTransform`,
the hidden Matrix4x4 and FAssetProxyHandle return carriers, and the public
IL2CPP getter slots in provider order. Callback scopes unwind on either
exception kind, restore the thread-local parent and mark missing returns as
incomplete. The shared host retains process identity and the acknowledged stop
protocol; the collision host requests stop after an attempted attachment even
when it exits through an exception.

The recorder now consumes prepared declarations without comparing installed
file fingerprints or native body windows. Its file inventory is not an evidence
admission report. Keep the selected-build contract and independent recovery
inspector as the source/native admission boundary; existing admitted sessions
retain their earlier evidence and do not need to be recaptured for this refactor.

Start `tools/EndfieldCapture/Capture.ps1 -Preset collision` with the game closed.
Launch manually after `COLLISION WAITING`, then log in or enter **OMV Dijiang /
O.M.V.帝江号 (`base01_lv001`)** only after `COLLISION ARMED`. The target scene
name is checked against LevelDescTable and SpaceshipConst; the selected light
prefab has exact authored Model rows in this hub. Let it load and walk until
every retained live object reaches the final displayed checkpoint and pending
is zero, then type `stop` and keep the game open until saved. The launcher
uses the already built recorder and archives the selected source reports and
raw Model files with the session; it does not seal or verify them.

`scripts.game_data.collision_capture_inspect` authenticates the saved native
inputs, staged runtime, source archives, completion/loss counters and paired
same-thread calls before admitting observations. Exact Model bytes can join a
runtime call to a frozen authored row. Post-setter Unity reads occur on the
original caller and are skipped explicitly off the main thread. Runtime scene
names, matrices, prefab handles, parent pointers and collider/mesh identities
remain separately timed observations. This first pass still does not prove
loader-to-CAB/PathID identity, destruction/reuse, IFix branch selection or the
state at the next physics step; watched element IDs are selection candidates,
not lifetime receipts. Unobserved hooks stay visible in the inspection.

The first admitted Dijiang light-prefab capture establishes a live source join:
selected Model records matched their frozen bytes, the prefab requests used the
same PathHash, and the transform output bits matched authored Pos/Rot/Scl. The
captured component snapshots had a zero root-grid index; no `GetMat` call was
nested under these selected transforms, although that hook was entered elsewhere.
After `SetParent(null, true)` returned, the selected root objects were active and
their queried world matrices were retained as separately timed observations.
The matrix translation differed slightly from the returned position, so keep
both samples rather than replacing one with the other or inventing a cause.
These observations constrain this loading episode; they do not prove every
transform/IFix branch or a serialized collider's live mesh identity.

No `_SetColliderEnable` entry occurred in that capture, and the observed
`Collider.set_enabled` entries were outside selected scopes. An active prefab
root and a stored `enableState` are therefore insufficient to classify its child
colliders. The saved-session inspector now retains component/context fields,
registration bounds, source UniqueId, exact transform comparisons and a named
hook census that distinguishes filtered calls from hooks with no entries.
Numeric load status remains numeric; component snapshots taken inside one
method are not a complete lifecycle receipt. The observer now takes a bounded
child-collider snapshot after selected instantiation. A separately timed
physics-step/lifetime observation and a loader-to-CAB/PathID bridge remain open.
Repeating the same scene walk cannot guarantee that an enable setter will run. Per-session
counts and joined rows belong in the collected inspection and generated
`reports/runtime_capture/collision/` findings.

The child snapshot uses the unique direct `SetParent` root recorded within the
selected instantiation. Its non-generic child-component query includes inactive
descendants and filters components through the native Collider ancestry. The
selected client signatures and entry/return witnesses authenticate that query,
managed Array length/index reads and the public class/type/GC-handle APIs.
Array access uses the checked managed methods, without an assumed array header.
Transient GC handles pin the root, reflected query type, result array and sampled
colliders; they are released on normal or observer-exception exits. No handle
is retained as a cross-frame lifetime claim.

A saved original-return timestamp precedes the child sample interval. The
inspection distinguishes these observer samples from original game calls,
binds summaries/child rows to the same source Model and root, and requires the
reported sample counts and component indices to agree. A completed empty
enumeration is distinct from an off-main-thread skip. Missing/ambiguous roots,
read/query failures and exceeded bounds invalidate capture admission and retain
a bounded `runtime-child-failure.json` diagnostic with the stage and source
record. Synthetic cases prove ordering, inactive/disabled state retention,
original error preservation, stop during instantiation, bounds and transient-pin
cleanup. The admitted retail child-query capture now exercises this path for the
selected Dijiang light models, with completed enumeration and no observer loss
or read failures.

The sampled descendants were active, enabled non-convex MeshColliders. Distinct
collider instances shared one observed runtime mesh, and each child's world
matrix matched its sampled root bit-for-bit after instantiation. The mesh name,
convex state and identity prefab-local matrix agree with the frozen serialized
candidate, whose empty render stream has a recovered cooked triangle payload.
That earlier session established conditional runtime state and candidate
consistency. The later admitted provenance session closes the selected Mesh's
CAB/PathID join. Those provenance-only sessions did not measure the runtime
cache; the admitted memory decoder below now compares it. Preserve the
post-parent and post-instantiation matrices separately: some basis entries
changed between those samples, while the small authored-position versus queried
translation difference remained. Neither difference establishes its cause.
The selected enable setter was still unobserved, so setter coverage is not a
prerequisite for this sampled state. The admitted provenance session reads the
shared runtime Mesh's serialized filename and PathID from the native identity
map. They agree exactly with the authenticated frozen selected Mesh source,
closing that identity gap for the observed instances. The runtime-created
Collider instances have no serialized map entry; do not assign their prefab
Collider's PathID to them. The raw/cooked hashes alone select the stored source.
The separately proved cache path and complete array comparison below establish
observed geometry; physical contact participation remains unobserved.

The reviewed native contract records the PersistentManager instance-ID map,
its concrete vtable, filename vector and identity consumer. The map yields a
serialized-file index and the raw 64-bit PathID; the concrete filename consumer
uses that same index to select a native string. The observer copies both in one
manager critical-section scope. Import-table ownership establishes that the
client uses Windows `EnterCriticalSection`/`LeaveCriticalSection`; it does not
use an SRW lock. The observer uses nonblocking `TryEnterCriticalSection`,
retains a busy-lock gap and retries during later snapshots. Native operand
witnesses authenticate the singleton, vtable and field declarations, while
runtime gates also check the concrete vtable and actual Windows lock bindings.
Bounds, string representation and reader failures retain stage diagnostics.
The observer calls the read-only identity lookup directly: it excludes the
consumer's subsequent file-opening path. No map entry is a valid observation
for a runtime-created collider and cannot be replaced with a name-based join.
Only an observed mesh CAB/PathID may match a unique frozen selected mesh source;
the raw serialized filename and signed/unsigned PathID interpretation remain
available separately. The client’s custom AssetBundle file-ID interface returns
PathIDs without the serialized-file index, so that interface alone cannot prove
a CAB join.

Later snapshots retain pinned managed Collider/root GameObject references,
which keep the wrappers available without proving native Unity object lifetime.
The observer checks cached native pointers, instance IDs and the original
GameObject/Transform identity before admitting another object read. Destruction
or replacement produces a lifetime gap and retires that retained record. It
samples after the first, sixtieth and six-hundredth later completed native
simulation-core calls. The reviewed native manager pointer, scene handle and
float step are forwarded unchanged in their own machine argument slots, and a
native completion function must return from the authenticated simulation-core
call site exactly once before the outer original core returns normally.
Rejected, skipped, reentrant or unwitnessed routes do not
advance the retained object's sample ordinals. A simulation whose entry precedes
enrollment is excluded. These are separately timed reads after the witnessed
completion path. The state reads alone do not measure contact pairs or native
geometry; the independently timed memory windows require their own decoder.
Missing sample epochs remain visible coverage gaps; acknowledged quiescent stop
releases every remaining handle and records the pending count. The saved-session
reader authenticates provenance, completion, source, timing and handle accounting
while continuing to accept the earlier capture schemas.

The admitted provenance session exposed a coverage failure in the earlier
manual-physics selection: the managed `Physics.Simulate_Internal` entry was
unhit while native completion entered outside an admitted outer context. No
later checkpoint was recorded. Additional walking cannot repair that hook
selection. The current observer instead hooks the reviewed UnityPlayer
simulation core itself; stored native caller and managed-icall transfers prove
the manager/scene/step ABI into that shared core. This covers those callers
when they execute that core, without asserting the earlier session's actual
caller addresses or universal physics-route coverage. Its offline ABI,
forwarding, completion and trampoline gates pass. The admitted native-core
session now observes every requested checkpoint for the retained selected
objects, with no lifetime gap, unfinished epoch, loss or handle-accounting gap.

The expanded observer also retains opaque native memory windows rooted at each
sampled Collider and shared Mesh cached pointer, at instantiation and every
requested later checkpoint. It follows plausible aligned pointer values only
through committed private or mapped nonexecutable regions. Window size, scanned
pointer prefix, traversal depth, node count, session bytes and session block
count are bounded by the reviewed contract. A soft time budget is checked
between operations; it cannot bound an individual page fault or thread
preemption. Every recorded child edge must agree with bytes captured in its
parent window. Reads, limits and queue loss stay explicit coverage gaps, while
archive framing, counts, timestamps and receipt hashes are admission gates.
The worker writes the archive outside the game thread. This preserves more
bytes for later offline PhysX investigation without calling cooking functions
or guessing their ABI. These windows can contain neighboring allocations, and
the reads are separately timed: they do not prove allocation extents, a native
type, PhysX ownership, geometry equivalence or contact participation. A missing
or corrupt archive rejects the expanded session; a correctly recorded traversal
limit preserves the separately authenticated state and source observations.
The capture console reports retained-object and checkpoint coverage while the
session is active, so a scene walk can reach the last checkpoint before stop.

The earlier header-only memory session retained native Collider/Mesh headers and a managed
wrapper edge, but every traversal reached the soft time limit before a useful
physics-cache graph was collected. The saved Mesh windows contain the stored
submesh bounds byte sequence; no complete selected cooked payload, decoded
vertex array or triangle-index array occurs contiguously in those windows.
This is a bounded byte comparison, not proof that the client discarded,
recooked or replaced that geometry. The improved traversal filters plausible
pointer values while scanning the parent, then queries page protection only
when processing each distinct candidate immediately before reading it. Limits
and rejected candidates remain explicit. The subsequent native-core session
collected the required cache path and complete arrays despite recorded time
and node limits. A traversal limit does not erase an independently complete,
authenticated range; it leaves uncollected ranges unknown.

### Admitted runtime cache decoding

The reviewed
[`collision_runtime_mesh_native.json`](../../scripts/game_data/contracts/collision_runtime_mesh_native.json)
binds Unity Mesh's held physics-cache member to its native cleanup/release
consumer. The captured pointee has the concrete `PxBVH34TriangleMesh` vtable;
its type-name and vertex/triangle/count/remap getters, index-width selector and
selected word/DWORD readers are authenticated against the selected native
inputs. This is a pointer-bound type and array proof, beyond a name match or
the occurrence of vertex bytes in a neighboring allocation.

[`collision_runtime_mesh.py`](../../scripts/game_data/collision_runtime_mesh.py)
reuses an admitted session only while the frozen profile/runtime/sources,
journal and archive still authenticate. It rechecks archive framing and pointer
edges, reconciles selected cached observations with journal bytes, gates the
new native layout, and requires the raw Mesh and embedded cooked payload hashes
to select one frozen CAB/PathID identity. Each read uses one complete captured
window from the same invocation and Mesh root; partial windows are never
stitched, and contradicting overlaps withhold the affected comparison. Read
addresses, hashes and independent timestamps remain available.

For the selected Dijiang light Mesh, every admitted instantiation and later
checkpoint sample has identical complete vertex float bits and triangle index
values/order to the stored cooked payload. The runtime uses word indices where
the stored stream uses byte indices, and DWORD face remaps where the stored
stream uses byte remaps. These are distinct representations of the same
decoded values. Pointer-bound edge bytes and BV4 slab bytes also agree over
their complete stored extents; the runtime node count matches the stored
slot count. This auxiliary comparison does not decode a complete runtime BV4
traversal or optional material/adjacency layouts.

The source identity-map lock was busy at an intermediate checkpoint. Those
samples explicitly reuse the initial mapped Mesh identity conditionally,
through the admitted retained object, unchanged Mesh pointer/instance ID and
root/lifetime identity. They do not claim a fresh CAB/PathID read. Later direct
mapped reads agree. The shared cache and decoded geometry remain unchanged
across sampled epochs while the final child world matrices change in their
horizontal basis entries; translations remain unchanged. Preserve geometry
and placement separately, without assigning the matrix change a cause.

The selected source, cache geometry and later-state requirements in the
[runtime-capture backlog](../runtime_capture_requirements.md#cooked-collision-and-live-mesh-state)
are accepted. Another capture is unnecessary for this case's mesh equivalence.
This result is conditional on this source and these separately timed samples;
it does not prove allocation extents, an atomic cache snapshot, a Collider's
`PxShape` attachment by itself, contact participation, other meshes or unobserved
physics routes. The separate attachment reader below supplies that additional
owning path. Generated comparison inventories and the validated source-local
collision OBJ belong under `reports/runtime_capture/collision/` or the saved
session's `collected/` directory.

### Collider current-shape attachment

The reviewed
[`collision_runtime_shape_native.json`](../../scripts/game_data/contracts/collision_runtime_shape_native.json)
establishes the Collider's current-shape member through both an actor getter
consumer and the MeshCollider vtable's physics cleanup path. The cleanup passes
the same receiver into the detach helper, consumes that member through the
bound `PxShape.getActor` slot, and clears it on the reviewed normal branch.
The concrete shape vtable, type-name getter, triangle geometry getter and
flag getter are authenticated against the selected native inputs. These are
native consumer relationships; the capture does not observe cleanup executing.

[`collision_runtime_shape.py`](../../scripts/game_data/collision_runtime_shape.py)
recomputes the admitted source-bound Mesh comparison, then reads the native
Collider root, its current-shape pointer, concrete shape type and triangle
geometry pointer from that invocation's Collider windows. The shape's triangle
Mesh equals the separately typed Mesh-held cache from the same invocation.
This proves a Collider-to-PxShape-to-cooked-source join for the selected samples;
it does not rely on nearby vertex bytes, an anonymous pointer or a name match.
The PhysX geometry/flag buffered-state branches are followed independently;
missing buffers never fall back to inline data. All interpreted field offsets,
state masks, virtual slots and code anchors live in the reviewed contract.

For the selected Dijiang light case, each instantiated Collider has its own
concrete shape and all shapes refer to the same decoded triangle cache. The
full join is captured after instantiation and at the first completed-physics
checkpoint. An intermediate checkpoint has only partial shape-window coverage;
the final checkpoint captures the Collider members but no shape headers. Each
held member is unchanged across its observed checkpoints. This preserves a
sampled pointer observation, without promoting it into a fresh later geometry
or flag read, or a continuous shape lifetime proof.

Captured shape flags configure simulation and scene query, with trigger clear;
the native actor getter also yields a non-null association. Neither establishes
actor scene membership, an actual collision pair, or a contact result. The
windows and roots are independently timed, so the same-call join remains
conditional rather than an atomic scene snapshot. Another capture is unnecessary
to establish this selected case's attachment. Fresh final shape fields, distinct
source cases and contact participation remain separate questions. Generated
per-call/epoch coverage belongs under `reports/runtime_capture/collision/` or
the session's `collected/` directory.

## Main grids

- **Vector extent (exact).** Selected accessor and builder widths bound every
  current grid vector count word and body without overlap. The shared reader
  now also bounds root/grid table objects, both root vectors, shared vtables
  and complete `TotalStr` UTF-8 strings including their count and NUL byte,
  rejecting partial overlap or an alias between different allocation kinds.
  Exact shared vtable/string extents are counted once. Every uncovered range,
  including the physical tail, stays explicitly recorded as a residual; the
  authenticated current main corpus has only zero-filled residuals. This is
  allocation extent, not a padding proof or nested-record field closure.
  Positive `Desc` table targets still need a reader; the current empty vector
  supplies no target evidence. `DataMask` stays a raw `UInt64`.
- **Filename (exact).** Every current `fb_main` filename decodes to its own
  root `UniqueId` under the selected `GetPath` packed-ID rule (low byte, next
  byte, one high nibble). Which ID the game requests is open.
- **DataIndex (structural).** Every valid `DataIndex.Grid` equals its
  containing `SingleGrid.UniqueId` (not always the file root's), and for each
  observed `Type` the `Index` values partition the same-named vector exactly.
  Where counts alone are ambiguous the native enum and accessor names decide;
  every observed Type has a nonzero named system route, distinct for the
  count-only rivals.
- **RootComp (structural, plus direct conditional consumer).** RootComp
  `Comps` groups tile each grid's DataIndex directory, and each entity type's
  ordered child Types equal its `comps` list in the exported
  `DynamicSceneTemplates` asset. Natively, `RootComp.Type` keys the typed
  template dictionary that `OnInit` fills from `TEMPLATE_PATH`; grid
  load, reload and enter reach `_ParseLoad`, which walks DataIndex entries
  (bounded by the template's `comps`, not stored `Comps.Num`), routes each
  Type to its system and can call `RegisterEntity`. The IdComp branch reads
  `UniqueId` and rejoins routing. The public
  `decode_authenticated_root_components` decoder authenticates current raw
  bytes before rechecking main framing, directory target bounds, group
  tiling and the fresh authored template signatures. It returns each
  checked directory reference with its source-local grid, component-vector
  and instance ordinals, and the owning RootComp ordinal and typed entity
  label. This closes the authored `RootComp.Comps` -> directory `DataIndex`
  -> component instance join. It does not assign indirectly grouped
  children or demonstrate that the authored entity exists in play.
- **ResourceComp (structural).** Its five groups partition their same-grid
  vectors; each resource descriptor's inner group partitions `Model`,
  `Effect` or `Ecs` targets across grids and files, resolved by scene path
  plus grid ID. The descriptor's state, level and factory scalars have exact
  offsets. A selected LogicState query consumer is authenticated below;
  the other scalars' runtime use remains open.
- **`PrimitiveIntList` closure (structural).** RootComp visibility,
  ResourceGroup visibility and Sludge `SurfTileIDs` spans are disjoint and
  tile each grid's `PrimitiveIntList` exactly. `SurfTileIDs` values are
  nonzero stored tile IDs. Their selected conditional navmesh consumer is
  authenticated separately from the stored partition.

## Scalar and spatial inline components

`dynamic_scalar_components_native` closes the stored layouts of
`MissionCondition`, `ActivityCondition`, `MapVarControlComp`, `PoiControlComp`,
`TreeRootComp`, `DecorationRootComp`, `ConveyorBeltComp` and
`ConveyorBeltBoxComp` (**exact selected layout**). Each generated getter's
metadata return type and native position read establishes its field type
and byte offset. The generated constructor's named field parameters,
record width and alignment agree with the main vector contract. Complete
main allocation framing and authenticated VFS path/length/MD5 joins run
before the corpus census; a different or missing native build produces no
layout.

The same contract also closes `Vector3`, `SeatComp`, `FactoryBlockComp`,
`SceneGridInfo`, `ExtraSceneComp`, `NavModifyArea`, `Bounds`, `ConveyorPath`,
`WaterPipeComp`, `InteractiveStateComp`, `GlobalVarControlComp` and
`SettlementControlComp`. Selected `Vector3` getter fast paths
read named `Single` fields `X`, `Y` and `Z` at byte offsets zero, four and
eight; the constructor names those same three fields and declares their
inline width. Typed nested getters pass the containing record's position
plus a proved offset to checked carrier initializers, which retain the
ByteBuffer and return a `Vector3` carrier. Their constructor's flattened
parameters independently match the named axes. This establishes stored
`SeatComp.Pos`/`Rot`, factory and scene-grid `Center`, and extra-scene
`MinPos`/`MaxPos`/`CurrentPos`; scalar `Radius`, `Len`, `Direction`, seat
keys and the byte Boolean `RaiseLevelEvent` retain their declared types.
The same carrier proof covers the additional named position, rotation,
scale and bounds fields. Conveyor paths retain the generated names
`WorldStartPoint`, `WorldEndPoint` and `WorldCenter`; a stored name alone
does not prove the live transform used by their consumer. Water-pipe
angles, delays, heights and interactive IDs, and interactive/global/settlement
control scalars retain their declared types. These are authored spatial
and control fields, without world-space, parent-transform, rotation-unit,
radius-unit, target-table, operator-enum or live occupancy claims.

Keep representation separate from meaning. `MissionCondition.IsQuest` and
`IsSame` are stored `Int32`, while `MapVarControlComp.ControlLoad` and the
conveyor entry/exit fields are byte-sized native Booleans. Map variable
`CompareValue` is signed `Int64`; `CompareType`, `MapKey`, `MapId` and the
four `Extra` fields stay signed integers with no inferred operator, target
or sentinel meaning. `TreeRootComp.NormalModel` is signed `Int64`, distinct
from the conveyors' unsigned group IDs. A getter name ending in `Id` or
`Tid` does not establish an external table key or rule out a string-vector
index. Consumers must prove those joins before labels are projected.

`MissionCondition.Id` now has that independent consumer proof (**direct
selected unpatched path**). `RegisterEntityCaredCondition` retains the
containing `FBDynamicSceneChunkData` carrier and passes the generated `Id`
getter's signed integer result to `DynamicSceneChunkStrExt.GetStrSpan`.
That method selects root field `TotalStr`, bounds the signed index, reads
its four-byte string uoffset and byte length, and returns the stored span.
Index zero is an ordinary string slot: it can contain a quest key, not an
absence sentinel. Negative and out-of-range indices return an empty span
on this selected path; the census reports that fallback separately from a
resolved authored empty string. All current authored condition indices
resolve within their own containing root. The returned span is passed to
`DynamicSceneRuntimeStringManager.GetStrKey`; an allocated runtime key is
not the stored index and is not established by this offline join.

The census keeps the original integer beside its resolved authored text.
Mission and quest keys may support a definition-level UI link after the
matching published definition is checked, but this does not establish that
the condition ran, passed or activated an entity. Other component IDs have
no equivalent target proof yet.

The current corpus has no authored `ActivityCondition`,
`DecorationRootComp` or `Bounds` examples, so their generated layouts do not establish
usage. Unassigned internal bytes in tree, conveyor and map-variable
records are zero in the authenticated current corpus; they remain reported
gaps, not a runtime padding or allocator proof. Counts, distributions,
bounded record samples and source MD5s belong in
`reports/animestudio/dynamic_scalar_components_native_latest.{json,md}`.
Enum meanings, control-ID targets, evaluated conditions and live activation
remain unresolved.

`decode_authenticated_main` lets a caller reuse existing exported raw
bytes after the explicit selected-native layout gate and current VFS
receipt gate. It checks the receipt's length and MD5 before complete main
framing and field decoding; the census also records each file's SHA256.
The public result retains source-relative grid and component ordinals,
original scalar values and separate proved string references, with nested
vectors represented by named axes. A component's entity or group owner is
not established by its position in a vector; direct directory references
can acquire an authored RootComp association only through the independent
root decoder and its current template gate. These associations retain
their directory ordinal, rather than treating vector order as entity order.
Raw `Vector3`, `NavModifyArea`, condition and path children have no owner
projection unless a specific checked DataGroup join establishes it.
Corpus and report receipts
must describe the current native inputs and current bytes before a Data
view projects them; bounded report samples are not a substitute for the
authenticated decoder.

The next runtime witness for this branch is a single selected scene/grid
load or reload: record the selected MapConfig and streaming configuration,
the requested `fb_main` path and accepted bytes, the grid UniqueId,
RootComp position and matched template component list, then the actual
DataIndex/system route and `RegisterEntity` call. Record whether the
selected iFix path is active. A condition-controlled example additionally
needs the stored TotalStr key, evaluated condition result and selected
state/area list at that call. This would test the conditional native path
and authored owner join against a live entity; offline directory or string
membership cannot supply that observation. Indirect DataGroup ownership
remains a separate static join rather than a reason to require a capture.

## ResourceGroup state query

`dynamic_resource_state_native` authenticates the registered
`DynamicSceneResourceGroupSystem._FillTargetStateGroupSet` unpatched body
(**direct conditional**). Its `FBDynamicSceneResourceGroupWithStateDesc`
`get_LogicState` call returns a checked `UInt32`, which the caller tests
against its named incoming `UInt32 mask` parameter. The native frame is
checked against entry RSP so this is the supplied mask rather than a
similarly shaped local. Zero bit intersection branches past the subsequent
`Group` getter to the loop advance: the selected query includes a group only
when `(LogicState & mask) != 0`. This is a bit-intersection filter, not numeric
equality; zero LogicState does not pass this particular query.

The reviewed contract pins the selected native inputs and complete caller
main-body window. The validator also authenticates the generated resource
layout, caller identity and full signature, both direct getter targets,
getter-return-to-test handoff, argument location and zero-overlap branch.
A missing or mismatched input or changed body produces no rule and preserves
an existing receipt. Focused tests cover wrong argument slots, comparison or
branch substitutions, getter targets, loop target and native gate failure.
The generated audit belongs under
`reports/dynamic_streaming/ifix_parallel/`; the reusable proof is the tracked
[`dynamic_resource_state_native.json`](../../scripts/game_data/contracts/dynamic_resource_state_native.json)
and its validator.

This selected query does not establish the loading or activation predicate
of every resource consumer. The anonymous descriptor-source helper's owner
join, live selected scene/grid/group, insertion ownership and iFix routes
remain outside this scalar gate. `SceneState`, `LevelNum` and `FactoryIndex`
need their own authenticated consumers before receiving runtime semantics.

## Sludge surface tile consumer

`dynamic_sludge_surf_tile_native` authenticates the selected unpatched
`DynamicSceneSludgeSystem._GetSludgeSurfTileIDs` path (**direct conditional**).
The original generated getter and inlined collector return the same
`SurfTileIDs` group position with the same ByteBuffer carrier. Checked group
`Index`/`Num` accessors select grid-local `PrimitiveIntList` entries. Each
iteration rejects a negative index, an index at or above the generated
vector length, and a zero or negative Int32 value. Positive Int32 values
are sign-extended to UInt64, so only the positive Int32 range is retained.
The indexed accessor clone shares the registered generated accessor's
vtable slot, vector helper, stride and selected little-endian Int32 read;
the length accessor is itself registered.

The output is the supplied `List<UInt64>`, cleared before the selected loop.
Its static `Add` companion is joined through the bounded MethodSpec and
class-instantiation tables, separately from the inline insertion helper.
That helper and the registered generic candidate agree on the list size
field, qword insertion stride and resize target. This closes the selected
insertion relationship without treating shared code or a static companion
as a live MethodInfo; the resize helper implementation remains open.

`_AreSurfTilesLoaded` passes each retained UInt64 ID to the registered
`NavMeshChunkManager.IsSurfaceLoaded` method. A false result returns false
immediately; a null, empty or exhausted selected list path returns true.
`_TryApplyNavMeshState` passes the same local collector output to this check
and reaches `_ApplyNavAndMaybeUnbind` on the selected empty-list or
load-check-true branch. This establishes **conditional navmesh use**, not
active Sludge state, an observed tile load, or a successful state mutation.
Live grid/component selection, patch routes, deferred callbacks and
physical/rendering effects remain unresolved.

A runtime receipt must correlate the caller's global ID/state, selected
scene/file identity and grid ID, Sludge wrapper/group `Index`/`Num`, produced
UInt64 IDs, each `IsSurfaceLoaded` result, the aggregate load-check result,
and the reached apply or deferred callback under one bounded thread/call
lineage. It must include the exact selected native build and loss/overflow
status. A graphics/audio-only session or a method-name hit cannot establish
that join; an observation profile needs these specific call/data receipts
before a capture is useful for Sludge recovery.

## Visibility and scene state

The nested `VisibleStateGroup`/`VisibleAreaGroup` spans address the grid's
`PrimitiveIntList`. `SceneVisibilityControllerBase.Register` reads each value
through that vector slot for the group chosen by the typed state or area
controller: a **direct conditional consumer**, not a name match. The stored
values join scene-locally (**stored cross-file relations**): every
`VisibleAreaGroup` value is in the same scene's `FBStreamArea.TotalAreas`
(including zero; spaceship-cabin main files have no area file), and every
`VisibleStateGroup` value is an index in the scene's `MapConfig.sceneStates`,
where index zero is a named state.

Those state indices have a named native source. `BaseGameScene` calculates a
mask and index list from the MapConfig conditions (or sets one state by
name) and hands the list through `DynamicStreamingScene.SyncSceneStates` to
the entity and resource systems' state controllers; area changes reach their
area controllers through `OnAreaChanged`. Conditions dispatch to quest,
mission, current-map variable and client-global variable leaves and to
`And`/`Or` trees; variable leaves compare as `Single` with an absolute
tolerance near `1e-5`, and a missing variable returns false. The MapConfig
comes from `DataManager.MapConfigTable` (`Data/Json/MapConfig/<id>.json`)
through normal and seamless loading. In the current export (observed; no
tracked gate rechecks it) every `LevelConfig.mapIdStr` names a MapConfig
whose own `mapIdStr` equals its file stem. Evaluated conditions, the active
state list, and whether a stored RootComp group is registered in play are open.

## Scene to DynamicStreaming files

Every `MapConfig.streamingMapConfigPath` resolves to one exported
`StreamingMapConfig` MonoBehaviour by container, source file and PathID, the
class coming from the original object index (many-to-one; unreferenced
assets stay as unselected candidates). Natively, `GameScene._ExtractSceneConfig`
loads that asset into the typed `BaseGameScene.streamingMapConfig`, and its
`mapSceneName` reaches `DynamicStreamingScene.InitScene`, which builds the
scene base path for `DynamicDataLoader.SetBasePath` (`fb_main`, `fb_init`,
`fb_streaming` templates) and `DynamicSceneVersionBanSet.LoadFromBasePath`
(`fb_version`). The typed chunk loader reads through
`VirtualFileSystem.ReadFileByLowIO` and checks chunk version fields. These
are **direct conditional file-selection and read routes**, not receipts that
a file was requested or accepted. The authored `streamingDataPathRoot`
(`Data/Streaming/...`) is a separate path family from the DynamicStreaming
`Scene` files; the link is `mapSceneName` plus the initializer. One-sided
scene sets stay in the join report and do not show a failed load.

## Version roots and the ban set

- **Layout (exact, direct).** `fb_version` is `Entries`, `Major`, `Minor`;
  each 16-byte entry is `UInt64 Id`, `Int32 Version` and alignment. The
  selected-width reader closes every current file through EOF.
- **Id domain (structural).** Every populated `Entry.Id` occurs as an indexed
  `IdComp.UniqueId` in the same scene's main grids; the entries are a subset,
  never a grid `UniqueId`, and the `map01` control has no overlap.
- **Active version source (direct, conditional).** The enter-game login
  response (`Proto.MSG_B1`, message ID `1`) reaches
  `PlayerInfoSystem.SyncBranchVersion`, which stores string field `f14_` as
  `m_branchVersion`; `_ResolveActiveVersion` parses it with
  `GlobalOptions._ParseVersion` (`v<major>d<minor>` with optional further
  `d<phase>` segments). Active phase defaults to a full-phase sentinel and
  changes only when a parsed output is nonzero, so a matched two-component
  value with a nonzero part sets phase zero while `v0d0` keeps the sentinel.
- **Ban consumer (direct, conditional).** `LoadFromBasePath` exits when the
  phase is at least the sentinel or a path, file, root or major/minor check
  fails; otherwise entries with `Version > activePhase` add their `Id` to
  `m_banned`, and `IsEntityVersionBanned(globalId)` returns
  `m_banned.Contains(globalId)` only when `m_needCheck` is set.

## Auxiliary `fb_init`/`fb_streaming` pairs

- **Stored pairing (exact).** Every current file has its counterpart. Root
  fields 0-1 and vector bodies 2-3 agree, field 4 agrees on its checked prefix
  only, field-5 tables agree in count and shape, and init field 7 and
  streaming field 6 are the complementary nonempty positions.
- **ID, descriptor and blob groups (exact).** Streaming field-6 rows carry
  four-byte IDs; init field-7 rows carry eight-byte descriptors (signed 16-bit
  ID and stride, zero reserved word) and a nested byte blob. Stride times the
  group ID count gives descriptor-major segments that tile the blob, and the
  grouped IDs partition the root field-3 IDs as a multiset.
- **Descriptor 21 (exact stored projection).** One stride-64 descriptor per
  group holds the root field-5 names clipped to 63 bytes: a stored name
  column, not a lossless copy, and not a named runtime component.
- **Native route (direct, conditional).** The ECS load transition passes both
  paths through `AllocateRuntimeChunk_Injected` to a native object that
  stores them separately, requests two streams in one indexed record,
  resolves both ready buffers to FlatBuffer roots, reads init field 7 and
  streaming field 6 at one ordinal, and hands IDs, descriptors and blob to a
  builder that copies stride-times-count bytes per descriptor into per-ID
  destinations. It shares the lookup and stream helpers checked by the IV
  path contract ([`world_irradiance.md`](world_irradiance.md)); the provider
  and VFS file a request chose are open.

## `FBStreamArea` records and area selection

- **Framing (exact).** With the corrected `Int32` widths the six vector count
  words and bodies tile the root tail through EOF; root bounds are inline.
- **Records and relations (direct, structural).** Area, trigger, point and
  bounds records have native offsets. In the populated file, area ranges
  partition `AreaVisibleGroups`, trigger ranges partition `Points`, every
  point lies in its trigger's XY bounds and those bounds are exactly the point
  extrema. The other current files are empty with an inverted-sentinel box.
- **Selection (direct, conditional).** `GameSceneAreaDealer.InitData` reads
  the scene's area file through VFS into a typed root, builds a trigger quad
  tree and seeds its active set from `RootVisible`. `FlushStreamingArea`
  enables areas against that set: nonzero areas go to
  `StreamingSceneV2.SetArea_Injected` and `DynamicStreamingScene.OnAreaChanged`;
  zero takes a default-area layer path. Refreshes query the tree around the
  stored streaming center (plus an optional extra-load sub-center) and apply
  the stored visibility slices.
- **Predicate (direct).** `CheckInArea` applies inclusive X/Z and height
  bounds, then an even-odd ray test over the trigger's closed point ring,
  comparing stored `Coord.Y` with query Z.
- **Centers (direct conditional, stored).** A regular load's center is the
  `pos` that `SquadManager.ServerTeleportSquad` passes to `LoadAtPos`; a
  seamless load's is the portal component's `tpPosition`. Placed portals
  store nondefault `tp_position` overrides, distinct from their world
  position, which the selected `ApplyProperties` route writes into
  `tpPosition`. The placed interactive reaches the allocator through a spawn
  pipeline entered from AOI interest (no dependency group; grid force-load
  and range-exit callers).

## Evidence boundary

Tiers are marked inline above. **Exact** covers VFS identity, vector and
tail framing, the filename-to-root ID and the auxiliary pair bytes;
**direct** covers selected accessors and the conditional native routes;
partitions, the template match and cross-file joins are **structural only**.
**Unresolved:** other nested main fields, positive table-reference targets and
allocator-backed proof for the zero-filled residual ranges; `DataMask`;
auxiliary descriptors other than 21 and whole-root closure; `Entry.Id`
meaning beyond the IdComp join; resource activation conditions and state,
level and factory consumers beyond the selected LogicState query; live Sludge tile
selection and navmesh effects; live login bytes, branch-version value,
registration execution
and repeated-segment captures; and every live selection: MapConfig,
streaming and template asset loads, grid and area activation, evaluated
conditions, version phase, ban results and ban-set reuse, auxiliary file and
provider, the squad teleport `pos` source, portal values and AOI/spawn
execution, polygon-edge equality, patch state. `RootVisible` is an authored
initial-set input, not a runtime receipt.

## Eliminated readings

Each was tested and refused; the module docstring has the reasoning.

| Refused reading | Module |
| --- | --- |
| a universal four-byte main vector width | `dynamic_main_native` |
| `DataMask` bits as present or nonempty vector flags, any base shift | `dynamic_main_native` |
| a DataIndex target chosen by counts alone | `dynamic_data_index_native` |
| `EDynamicSystem` defaults read as signed compressed `Int32` | `dynamic_system_routing_native` |
| `RootComp.Type` labels from numeric agreement alone | `dynamic_root_comp_native` |
| `SceneVisibleStateInts`/`SceneVisibleAreaInts` as visible-group targets | `dynamic_root_comp_native` |
| the IdComp branch skipping routing; stored `Comps.Num` as the loop bound | `dynamic_root_comp_native` |
| `MountViewModel` as a model record (it addresses `PrimitiveStringList`) | `dynamic_resource_comp_native` |
| `VisibleStateGroup` index zero as an invalid marker | `dynamic_visibility_state_join` |
| the MapConfig condition list as a complete state catalog | `schemas/map_config.py` |
| variable conditions as exact integer tests; a missing variable as zero | `dynamic_visibility_runtime_native` |
| a shared generic loader pointer as proof of the loaded class | `dynamic_visibility_runtime_native` |
| `streamingDataPathRoot` as the DynamicStreaming path | `dynamic_streaming_config_join` |
| an all-scalar `fb_version` root; an ungated 16-byte entry width | `dynamic_version_native` |
| auxiliary field-4 prefix equality as full-width equality | `dynamic_aux_pair_corpus` |
| descriptor 21 as a lossless root-name copy | `dynamic_aux_pair_corpus` |
| byte-sized `RootVisible`/`AreaVisibleGroups` from `Get*Bytes` helpers | `dynamic_stream_area_corpus` |
| `RootVisible` as the union of area slices; the empty inverted box as malformed | `dynamic_stream_area_native` |
| a portal's world position as its destination; `forceLoad` as the skip-AOI flag | `portal_center_join` |

## Recovery queue

1. A component-ownership witness for descriptor 21 or a source-backed meaning
   for another auxiliary descriptor, with a runtime path/provider receipt.
2. ResourceGroup consumers beyond the selected LogicState mask query,
   including the descriptor-source helper's owner join and the SceneState,
   LevelNum and FactoryIndex scalars. The Sludge
   `SurfTileIDs` group-to-primitive/list and load-check-to-apply joins are
   authenticated conditional native consumers; a live Sludge/grid/tile
   receipt and deferred callback behavior remain the next Sludge boundary.
3. Runtime receipts (exact build, caller, file identity) for MapConfig and
   streaming-config selection, grid and area activation, version phase and
   ban results, portal AOI and spawn, and the squad teleport `pos` source.
4. The remaining nested main fields and positive table targets, then an
   allocator-backed residual/padding proof and `DataMask`.
