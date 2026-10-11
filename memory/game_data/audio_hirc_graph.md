# The HIRC object graph, and the types that are closed

Part of [`../game_data_recovery.md`](../game_data_recovery.md). See
[`README.md`](README.md) for the level and lane map.

**Level 3, audio lane.** The first structure above byte layout: the relations, how
they are told apart, and the per-type layouts that are closed byte-exact.

## Current position

- **Every shipped type frames byte-exact from the SDK deserializer** (see
  [`audio_hirc_parser.md`](audio_hirc_parser.md)); the field order per type is the
  module docstring of
  [`hirc_v150.py`](../../scripts/webui/audio/semantics/hirc_v150.py).
- **Two readings of the same bytes coexist.** The typed v150 parse in `hirc_v150`
  names fields. The corpus censuses in the AnimeStudio reader, gated by
  [`hirc_action_corpus`](../../scripts/webui/audio/semantics/hirc_action_corpus.py)
  and [`hirc_named_reach`](../../scripts/webui/audio/semantics/hirc_named_reach.py),
  measure words at corpus offsets and predate the SDK read. They stay as regression
  guards on the bytes; field names belong to the lanes and the typed parse. Each gate
  function's docstring records its measurement, controls and non-claims.
- **What the SDK names in the censuses.** The `0x08`/`0x12` leading word is the
  `CAkBus` parent bus, and a null one is followed by `idDeviceShareset` -- the extra
  word the corpus found on null-reference bodies. The front-offset parent of `0x02`,
  `0x05`, `0x06`, `0x07` and `0x09`, and the music word at offset 9, are the node
  frame's `DirectParentID`. `0x0A`'s counted array is a segment's children list; the
  name hashes near the end of `0x0C` are decision-tree keys; `0x0B`'s closing word
  100 is `iLookAheadTime`; the 14-byte record `0x02` and `0x0B` share is
  `AkBankSourceData`.
- **Evidence boundary.** Everything here is authored serialized structure: relations,
  counts of references, authored values. None of it is runtime DSP, effective
  inheritance, live State/RTPC/modulator values, branch choice, or audibility.
  Changing counts live in the `reports/animestudio/hirc_*_current_latest` reports
  and the generated Audio summary.

## Three relation kinds, told apart by in-degree and symmetry

| relation | direction | what separates it | gates |
| --- | --- | --- | --- |
| main reference graph (`05`->`02`, `07`->`07`, `09`->`05`, `04`->`03`, ...) | owner -> owned | every target named by **exactly one** referrer; same-bank by closure | `reference_graph_is_closed` |
| bus parent (`0x08`/`0x12` leading word) | child -> parent | many children per parent; a forest per bank | `the_shared_hierarchy_is_a_forest`, `almost_every_bank_contributes_one_tree`, `numeric_type_12_is_a_leaf`, `the_hierarchy_runs_opposite_to_the_main_reference_graph` |
| music references (every word offered) | mostly mutual | the reverse edge is present for about three quarters of askable edges; almost all same-bank | `the_music_relation_is_symmetric`, `music_references_resolve_inside_their_own_bank`, `music_bodies_all_carry_references` |

- **Direction is visible in in-degree, not in shape.** Both hierarchies are forests;
  only how often a target is named tells owner->owned from child->parent. The bus
  relation is deliberately **not** in the main reference graph: adding it would break
  that graph's one-referrer-per-target closure.
- **The parent field is the exact inverse of the child lists.** `DirectParentID`
  names the object whose counted child list names the child back, with zero
  disagreements across every checkable case and more than five type pairs
  (`the_parent_field_inverts_the_reference_graph`). Two different byte sources
  agreeing exactly is the strongest cross-check the format allows. `0x04` at offset 1
  looked like a parent and is not: it names a `0x03` in the same direction as the
  graph edge. The music offset-9 word is not part of this test (the main graph
  carries no music type); it is censused separately and forms its own forest below.
- **The music relation cannot be read as parenthood in either direction**, and it is
  not cliques (neighbours of a node are almost never linked). Only edges whose target
  was itself scanned can be asked for a reverse edge; counting the others as one-way
  mixes "not mutual" with "not askable".
- **Scope decides what a relation is.** The bus forest is built per bank. On
  deduplicated ids it merges unconnected trees into a few and looks far tidier. An
  object with no parent is a root; one naming a parent outside its bank is a root only
  of that bank's fragment -- and those are all `0x12`, whose parent usually lives in
  another bank. Almost every bank contributes one tree.

## The bus forest

- `0x08` sits above and `0x12` below; every parentless object is a `0x08`. `0x12`
  mostly names a `0x08`, `0x08` also nests in itself, a few name the audio device
  (`0x15`), and neither names a music type.
- The typed `CAkBus` parse in `hirc_v150` consumes every published bus exactly and
  resolves each to a parent bus or an explicit root; its layout (the property bundle,
  positioning, aux, limits and ducks **before** InitialFX, then InitialRTPC **before**
  StateChunk) is why byte scanners mistook duck and state data for effect counts.
- The pre-SDK corpus framer for `0x08`/`0x12` (reference, bundle, sized second list,
  nine-byte field, counted runs, a tail block of units and 12-byte records) is
  superseded by that parse. Its gates remain: `type08_head_words_are_null_or_resolve`,
  `type08_tail_head_names_one_object_type`, the tail-record and partial-body gates,
  and the shared-constant rival gates.
- **`0x08`'s tail-head first word names a `0x12` object**, against a control word in
  the same head that resolves zero times. The same words in `0x12`'s tail resolve
  zero times, control included: sharing a layout does not make a field mean the same
  thing, so the finding is not carried across.
- **Music segments reach buses in other packages.** `0x0A`'s word at offset 5 (where
  the SDK frame puts `OverrideBusId`) never resolves inside its own package; corpus-wide
  every value resolves, to `0x08` objects apart from one variant
  (`the_type0a_word_five_points_outside_its_package`).

## The music family

These are corpus measurements; the lanes frame the same bytes by name.

- **One authored bank shipped twice.** One bank appears byte-identical in
  `audit_banks.pck` and `hotfix_main_b75.pck` and holds nearly all music objects, so
  music totals are about double the distinct population. Closure rates are
  unaffected; sample sizes are not. `the_corpus_reports_its_duplication` publishes
  the distinct count beside every total.
- **`DirectParentID` forms a forest** chaining `0x0A` -> `0x0D` -> `0x0C` -> `0x0C`
  (with `0x0A` -> `0x0C` directly): acyclic per bank, deep, many children per parent
  -- the same shape as the bus relation in an unrelated family
  (`the_type0c_parent_relation_repeats_the_same_shape`). The typed parse reads it
  through the whole node base (`hirc_v150.hirc_object_parent_id`). The C# census's
  head word is `DirectParentID` only when body byte 2, the FX count, is zero
  (offset 9); in the nonzero branch its offset-5 word is the first FX slot's
  `fxID`, and the parent sits at `10 + 6 x uNumFx`. Those bodies' head words are FX
  references that happen to resolve in the same bank, not parents. Five `0x0C`
  bodies with first byte 6 follow neither branch and are counted, not dropped; a
  fourth byte-2 value must fail closed (`music_head_references_are_closed`).
- **Every `0x0B` is a child of exactly one `0x0A`** -- as many distinct targets as the
  type declares, none twice, none missed (`the_music_partition_edge_is_one_to_one`).
  The word before the first child is a count that is right in every body that carries
  one (`the_type0a_reference_is_a_counted_array`); the segments without a track are a
  whole population four bytes shorter, not anomalies.
- **`0x0A` and `0x0D` place their references in fields, `0x0C` in lists**: edges per
  distinct end distance separate them by an order of magnitude with an empty middle
  (`the_music_types_split_into_located_and_scattered_references`). A handful of
  `0x0C` bodies carry over half its references, so quote its median, not its mean.
  The `0x0A` -> `0x0B` edge alone is 4-byte aligned to the body end
  (`the_type0a_to_type0b_edge_is_aligned_to_the_body_end`). `0x0C`'s first counted
  array sits at `32 + 5 * body[14]` against rival bases that find nothing, and a flag
  inside the fixed region after it places the next block
  (`the_type0c_reference_array_is_located`, `..._region_flag_places_the_next_block`).
- **`0x0C` names**: the words 12 and 24 bytes from the end match FNV hashes of shipped
  literals far above chance (`High`, `Low`, `Loop`, `WIN`, `Start`, `NONE`, ...);
  they are decision-tree keys. `music_tail_words_are_named` skips rather than passes
  when no names were supplied.
- **Authored values in `0x0A`, recorded as observations**: a float that is whole in
  almost every body, 55-190 with modes 120, 130, 110, 90 (tempo-like; `AkMeterInfo`
  carries `f32 fTempo`); a 32-bit fixed-point fraction of one beside it; a bounded
  whole float with a -96 floor in the head; the constant `0x408F4000` shared by
  `0x0A`, `0x0C` and `0x0D` and almost absent from `0x0B`. What each measures is not
  claimed by the gates.
- **Nothing outside the family enters it.** The main graph and the parent field carry
  no music type; five action-target words land on `0x0C` roots with no outgoing edge
  and reach no source id (`the_music_family_is_not_entered_from_the_object_graph`);
  the non-HIRC sections name only buses. This says no resolved relation reaches
  music, not that music cannot play at runtime.

## Source records, media and names

The selected native queue companion now checks Action construction and new
Event Action-list creation as well as the stored Play Action target word's
setter and exact-key execution lookup. New Event lists follow authored order
only for distinct resolved registry objects with no later intrusive-link
mutation; existing Event IDs bypass the new list. This gives that authored target
edge a conditional consumer read, separate from the parser's same-bank object
join. It does not identify a live bank occurrence or make an unknown target
subtype into a Sound. Direct selected Event/Play/Sound paths also have complete
numeric package-row to offline FLAC PCM witnesses; the memory stream label does
not imply embedded bank media. The native and physical-media interpretation is
owned by [`audio_native_hooks.md`](audio_native_hooks.md), with changing cohorts
under `reports/audio/`.

- **`0x02` and `0x0B` share the 14-byte `AkBankSourceData` record**, and their
  plug-in ids are built-in codec ids: `0x00040001` Vorbis and `0x00140001` Opus in
  WEM, company 0, type Codec. No third-party or premium plug-in is referenced, so the
  base SDK is sufficient.
- **The source id names shipped media, across packages.** Essentially all declared
  media are named by some record (`0x02` for most, `0x0B` for the music media), and
  the words one byte either side name almost none (`media_attribution_is_discriminated`);
  the plug-in id alone decides whether a source id names shipped media
  (`media_join_is_decided_by_the_plugin_id`). A bank's media usually live in another
  package, so every join is a corpus union.
  For External Source records, the native bank loader places this stored source
  ID in the selector's descriptor match word. It is an external-slot cookie,
  with the actual path or memory supplied alongside the posted Event. The
  selector's first usable matching descriptor and prepared argument are checked
  by the queue companion; this conditional binding is detailed in
  [`audio_native_hooks.md`](audio_native_hooks.md). A coincident numeric media
  ID cannot turn that slot into ordinary codec media.
- **Action targets cross banks** (`type03_targets_cross_bank_boundaries`); the gated
  reference vectors do not.
- **Type `0x04` is the object managed code addresses by name.** Every match between a
  metadata literal hashed with the shipped `AudioHashGenerator` (FNV-1 over UTF-16
  with ASCII case folding) and a HIRC id lands on a `0x04` and on no other type; the
  walk from it to media is in `hirc_named_reach`.
- **The 12-byte point `{f32, f32, u32 interpolation 0..9}`** is one record in RTPC
  curves, layer and clip-automation curves, attenuation curves and `ENVS`. Its code
  alphabet is dominated by 9 and 4 everywhere.

## The typed v150 parse

Detail lives in the owning modules; this is the boundary.

- **Effects.** NodeBase effect slots, output-bus ids and effect definitions (PCK and
  bank scope, class id, parameter hash) are exact. Typed built-in parameter values
  need the selected-build gate in
  [`wwise_effect_native.py`](../../scripts/webui/audio/semantics/wwise_effect_native.py)
  over [`wwise_effect_parameters_native.json`](../../scripts/game_data/contracts/wwise_effect_parameters_native.json).
  Convolution Reverb and Mastering Suite are joined to their methods structurally.
  Their reviewed contract partitions each contiguous input span into anonymous
  word copies, scalar loads and byte zero-tests/extensions, with an exact native
  instruction witness for each read. The gate checks those witnesses and refuses
  gaps, overlaps, incompatible widths and a partition that misses its declared
  end. The page shows serialized offset, width and raw bits; a scalar load may
  add a float32 representation view, not a named setting, unit or processed native
  value. A short block publishes no read rows; a longer block retains its unread
  suffix. These methods do not test the supplied length. RoomVerb keeps eleven
  unnamed floats. Slot flags and native input reads are authored, not runtime DSP.
  Convolution's update-to-bulk-field joins are checked by
  [`wwise_effect_updates.py`](../../scripts/webui/audio/semantics/wwise_effect_updates.py);
  its clamps are absent from bulk loading and must not constrain bank values.
  [`wwise_effect_scalar.py`](../../scripts/webui/audio/semantics/wwise_effect_scalar.py)
  authenticates partial named `powf` code/data correspondence, not whole-function
  parity or live CPU selection.
  [`wwise_mastering_updates.py`](../../scripts/webui/audio/semantics/wwise_mastering_updates.py)
  proves Mastering's complete anonymous update transformations, every serialized
  source join and the common flag write, including invalid selectors. Whole-loader
  symbolic integer flow proves byte zero-tests, preserved mask bits and masked
  cached-word selection without sampling input values.
  [`wwise_mastering_consumer.py`](../../scripts/webui/audio/semantics/wwise_mastering_consumer.py)
  joins parameter retention, dirty-flag consumption and versioned section routing
  to the effect-local engine. On the admitted version-four route, each of the
  first four bank bytes controls an anonymous section: zero suppresses its
  processing callback; nonzero makes it eligible. The complete callback binder
  and native order tables join section IDs to numeric callbacks and state objects;
  one order mode swaps the first two sections. An unused record ends the section
  loop. These direct consumers establish the conditional suppression role, not
  public EQ/bypass labels or observed playback. The later
  context-indexed routine has a separate unresolved DSP and ownership boundary.
  Refresh clears the dirty byte before conversion; conversion failure returns
  false after that clear. Bank input acceptance therefore does not prove that
  the processing-state conversion succeeds.
  [`wwise_mastering_gain.py`](../../scripts/webui/audio/semantics/wwise_mastering_gain.py)
  closes the current-revision route for section two: its serialized float words
  are clamped during conversion, selected by the channel map, scaled and passed
  to the partially identified base-ten power helper; the processing kernel
  multiplies each sample by its channel's gain. The complete descriptor dispatcher
  constructs bounded numeric control indices from the channel mask, appending
  one deferred bit after the ascending traversal. It checks the logical count
  and a stride large enough for that count and divisible by four; the section
  receives this logical count rather than capacity. This proves channel padding
  fits the admitted stride. The kernel rounds channels and frames to groups of
  four, so its input frame padding and actual caller allocation still require a
  separate proof. The converter sends NaNs to the lower clamp bound; its special-mode
  equality check permits unordered comparisons. Gain application, successful
  admission and padded storage remain explicit conditions; neither public
  speaker/control names nor complete power-helper equivalence are established.
  [`wwise_mastering_filter.py`](../../scripts/webui/audio/semantics/wwise_mastering_filter.py)
  joins section zero to its series of second-order IIR kernels. Each channel
  retains two previous inputs and outputs; three input products and two feedback
  products are summed in order with float32 rounding and the stored feedback
  signs. The section skips records that pass its identity comparison, leaving
  those histories untouched. This comparison is also unordered-tolerant.
  Coefficient generation and public filter names remain unresolved. The complete
  kernel grammar and the shared
  [`wwise_effect_small_fill.py`](../../scripts/webui/audio/semantics/wwise_effect_small_fill.py)
  proof also establish its trailing-frame zero fill for admitted strides at most
  twelve. The input padding is overwritten and filter history advances through
  the rounded frame count. The fill validator proves complete bounded writes on
  scalar, SSE, AVX and repeat-store routes without assuming live CPU selection;
  gain updates use the same helper to zero unused channel-gain slots. Actual
  caller allocation, wider strides and larger fill lengths remain separate gaps.
  Offline reference recurrence and series checks are supplemental
  evidence, not observed playback or a general stability guarantee.
  [`wwise_mastering_dynamics.py`](../../scripts/webui/audio/semantics/wwise_mastering_dynamics.py)
  joins section one's parallel band processing and all three section-three modes
  to those same callback records. A band runs its own series of IIR filters;
  later band outputs are added to the first output. A single-band configuration
  skips the filter loop. The per-band bypass mask skips dynamics, rather than
  removing the band from the sum. First processing seeds each logical channel's
  power history from the unfiltered first input sample squared. Each frame then
  updates power as `alpha*x*x + (1-alpha)*previousPower`; every multiplication
  and addition rounds separately to float32. A bit-polynomial logarithm,
  piecewise knee transform and bit-polynomial power approximation produce the
  target gain every thirty-two frames, with that period restarting on each call.
  Gain history updates every frame using one coefficient when the target is
  lower and another otherwise; the resulting gain and an output multiplier
  scale the sample. Optional link modes share the minimum logical-channel
  target, or distribute a scaled minimum with a selected-channel exception.
  The numeric-map pair exception is joined to the actual descriptor map copy.
  With the scaled-minimum link mode and pair option enabled, mapped values two
  and three retain a single-channel exception. Other even mapped values select
  the minimum's logical slot and its successor; odd mapped values select its
  predecessor and the minimum slot. This uses mapped parity rather than looking
  up the partner. Sparse masks can therefore select an unrelated channel or a
  slot beyond the logical/rounded channels. A leading odd mapped value produces
  an unsigned predecessor that zero-extends into a far positive scratch address.
  The validator proves the complete local selection region and enumerates every
  admitted supported mask and possible minimum. Original fragment execution
  checks that enumeration; complete finite-input kernel paths also reach its
  representative cases, stopping before the far store. Descriptor admission
  alone does not prove pair safety. Host mask/control selection, live reachability
  and public speaker names remain unresolved; this is not an observed fault.
  Section three's mode one clips each signed sample to its channel threshold.
  Mode zero updates a peak as
  `(1-release)*previousPeak + attack*max(abs(x)-previousPeak,0)`, derives a
  threshold-to-peak gain using the approximate reciprocal instruction, optionally
  shares the minimum gain across logical channels, and clips the scaled sample
  to unit magnitude. This is the observed recurrence; replacing it with a
  conventional attack/release formula changes its behavior.
  Mode two delays samples by a fixed window, tracks its peaks, smooths gain and
  clips the delayed output to threshold times the output multiplier. Its peak
  rescan is triggered by logical channels but recomputes a whole SIMD channel
  group, including padded lanes. Partial blocks rotate the delay storage; the
  original input enters the delay while the earlier sample is emitted. The
  validator authenticates the complete kernels, telemetry pointer selection,
  relative joins and constant initializer bodies through
  [`wwise_mastering_dynamics_native.json`](../../scripts/game_data/contracts/wwise_mastering_dynamics_native.json).
  Those initializers write the SIMD constants into mutable storage.
  [`wwise_mastering_startup.py`](../../scripts/webui/audio/semantics/wwise_mastering_startup.py)
  authenticates the selected PE entry point, process-attach route, initializer
  table and pointer walker through
  [`wwise_mastering_startup_native.json`](../../scripts/game_data/contracts/wwise_mastering_startup_native.json).
  Every needed initializer is inside that range. The file-default dispatch
  invokes each non-null pointer in order. Offline execution of the original
  entry/attach/walker and selected initializer bodies checks both the successful
  path and prerequisite failure paths, with other callbacks explicitly modeled.
  This closes the static startup-route join. Successful prerequisites, unchanged
  loader dispatch, effects of other initializers and no later constant overwrite
  remain conditions; execution in a live client and constant lifetime are not
  observed. An earlier error-returning initializer table now joins the writer of
  the power/time helper's CPU-selector cell. Its walker skips null pointers and
  aborts on the first nonzero return. The selected initializer resets an
  availability cell, checks a CPUID leaf-one mask and conditionally checks an
  XGETBV index-zero mask, then writes zero or one to both cells and returns zero.
  The shipped method has no leaf-seven augmentation. Original initializer and
  complete attach-route checks agree with modeled hardware responses across
  required-bit subsets, unrelated bits, stale values and earlier-table failure
  positions. Actual hardware responses, prerequisite success, other initializer
  effects and later selector writes remain conditions. Offline reference checks cover
  original kernels and complete callbacks with synthetic admitted states,
  including successive blocks, band bypass subsets, delay rotation, telemetry
  and in-place delayed processing. Copy is an assumed primitive, and reciprocal
  agreement has a tolerance. Section one's current converter now joins all its
  serialized control sources, including the inverse-zero bypass bits, to state
  application. It restricts band count and link/pair controls, clamps active band
  fields and requires increasing clamped crossovers. Unused crossover slots keep
  the output's previous bytes; inactive band records receive explicit defaults.
  The application maps threshold, ratio, time, output and knee fields to the
  dynamics arrays. Active histories survive a control update, inactive power and
  gain histories reset, and filter histories survive coefficient changes.
  Each crossover boundary uses two equal stages. Outer bands have one boundary;
  interior bands have two. The generated numeric filter types' coefficient
  arithmetic and normalization are directly proved through the packed helper's
  two returned lanes. The packed helper's admitted crossover arithmetic now has
  an independent proof below; complete arbitrary-input trigonometric equivalence
  remains unresolved. The final temporary descriptor word is not initialized by this
  producer and is unused by these two coefficient branches. A single-band update
  leaves filter counts unused and unchanged. Optional telemetry requests one
  allocation per active band; allocation ownership and lifetime remain open.
  Section three's current converter and application also join its serialized
  words to processing state. Conversion restricts the
  numeric mode and link flag and applies mode-dependent float clamps; delayed
  processing forces the first time word to zero, while the other modes force
  the extra amplitude word to zero. NaNs select the lower clamp bound. The two
  amplitude words feed the base-ten power helper after scaling. Timing uses
  the frequency copied from the descriptor and a second scalar helper; the
  exact arguments and returned-value arithmetic are proved. Its finite scalar
  and FMA paths now have a separate instruction-order proof. Delay storage is requested from
  the stride; optional gain side-output storage has a separate request.
  Offline application checks executed the original helpers and a selected fill
  route against synthetic allocator buffers, including fill bounds and canaries.
  Those sampled results do not prove general helper equivalence, fill paths,
  allocation admission or lifetime. Complete helper equivalence, legacy revision
  arithmetic, public names and live activation remain open.
  The complete peak-application storage tail is now joined for every admitted
  old/current mode. All valid modes reach the delay request after their coefficient
  writes, even when that mode does not use delayed processing. A nonnull delay
  pointer suppresses allocation and clearing without checking capacity. A new
  returned pointer is stored before its null check, and only a successful new
  allocation is cleared. The optional byte must equal one; nonzero logical count
  permits at most one side-output allocation, with existing storage retained.
  Either failure returns the allocation error while retaining earlier controls
  and pointers. Initialization resets the declared history arrays to zero or
  unity only after nonnegative default application, then publishes success flags.
  Original complete application checks cover both revisions, every valid mode,
  channel count, pointer-presence and allocation-failure combination. Complete
  initializer checks confirm all history resets and their failure boundaries.
  Math/fill helpers and allocator results in these storage checks are explicit
  ABI-conforming models; their earlier numerical receipts keep separate boundaries.
  Real capacity, helper side effects, retry recovery, ownership and live selection
  remain unresolved.
  [`wwise_mastering_profiles.py`](../../scripts/webui/audio/semantics/wwise_mastering_profiles.py)
  now joins the initializer's stored defaults through
  [`wwise_mastering_profiles_native.json`](../../scripts/game_data/contracts/wwise_mastering_profiles_native.json).
  Section one passes its legacy payload directly to application with the
  all-word selector. Section three compares a fixed key with a single stored
  pointer entry, then passes that record's selector and legacy payload.
  The string helper's whole body exactly matches a named CRT comparison body.
  File-default pointer and terminated-string equality establish the stored
  selection; mutated pointer contents can instead take the no-match exit.
  Nonnegative application results permit success flags, while negative results
  return before those flags. Original comparison and initializer checks exercise
  alignment/page-edge string paths, null arguments, no-match and application
  success/failure, with application callbacks explicitly modeled to capture
  arguments. This proves default selection and forwarding, not complete legacy
  application mathematics, mutable pointer lifetime or actual use by a client.
  [`wwise_mastering_revisions.py`](../../scripts/webui/audio/semantics/wwise_mastering_revisions.py)
  proves converter header negotiation and revision routing through
  [`wwise_mastering_revisions_native.json`](../../scripts/game_data/contracts/wwise_mastering_revisions_native.json).
  A source must have a recognized revision and its exact nominal size. A
  recognized destination revision retains its existing length word without
  validating it; an unrecognized destination instead receives the source header.
  Old-to-old, old-to-current and current-to-current routes exist, while
  current-to-old rejects before converting controls. These checks establish
  nominal framing, not readable or writable memory capacity. Original framing
  executions agree with the bounded header decoder and leave control bytes
  untouched until the selected control entry.
  [`wwise_mastering_legacy.py`](../../scripts/webui/audio/semantics/wwise_mastering_legacy.py)
  adds legacy control guards and peak application correspondence through
  [`wwise_mastering_legacy_native.json`](../../scripts/game_data/contracts/wwise_mastering_legacy_native.json).
  Legacy band records have one fewer available band and crossover slot. Their
  old-to-old route restricts bypass bits to that band count and enforces the
  special/link restriction; old-to-current conversion admits the wider bypass
  mask and omits that restriction. Both reject nonzero reserved words. Legacy
  peak conversion likewise requires its two reserved words to be zero; conversion
  to current supplies zero extra amplitude and derives the link flag from the
  special argument. Original converters match an independent model in bounded
  integer and floating corner cases, including quiet NaNs, retained unused
  fields, inactive defaults and partial output writes before error exits.
  The old and current peak application loops have identical normalized arithmetic
  and branch structure after accounting for explicit differences: old application
  repeatedly writes mode/link and forces link off, while current application
  initializes the extra amplitude array through the power helper. Old application
  retains that array's prior values. Delayed processing reads it; the authenticated
  stored old default uses mode zero, which does not. The normal control pipeline
  supplies current records. Original application/processing checks confirm that
  retained amplitude can change delayed output under synthetic admitted state,
  while modes zero and one ignore it. This is conditional state dependence, not
  proof of a running-client fault or legacy delayed-mode reachability. Immutable
  controls, disjoint storage and completing helpers remain required. Legacy
  active-band arithmetic now has a separate bounded scalar decoder: all field
  stores and helper arguments agree with independent expression trees across
  zero/unordered time selections. The original group loop repeats that mapping
  over the channel arrays. Frequency comes from an unsigned word converted
  through a zero-extended register. Original full application checks use nonzero
  prior histories and exercise unsigned high-frequency words; active histories
  survive and inactive power/gain histories reset in that corpus. The complete
  inactive group now has an independent expression proof for every field array
  and its repeated channel stores. Inactive attack and power smoothing use the
  same coefficient; release uses a distinct factor. Original execution confirms
  those stores from nonzero prior state, including unsigned frequency rounding
  boundaries and local underflow handling with the external error callback modeled.
  A separate bounded decoder keeps copied cutoff and argument words symbolic
  while proving legacy crossover routing: two stages for outer bands, four for
  interior bands, and retained unused counts for a single band. It joins each
  descriptor, destination and helper argument across all admitted band positions.
  Nonzero conversion results take the common application-error exit. Original
  success paths and individually forced failures confirm call order, retained
  earlier writes and unchanged filter histories. The temporary descriptor's last
  word remains unwritten and is unused by the admitted coefficient cases. These
  proofs require disjoint storage and completing helpers with preserved
  nonvolatile registers. Arbitrary-input helper equivalence, external error side
  effects, complete allocation admission/lifetime and live use remain open.
  The common band application's optional-storage tail now has a complete local
  proof in the dynamics owner. It visits active bands in order only when the
  optional byte equals one and logical channels are nonzero. Each band can request
  one shared first-channel side buffer; an existing first pointer suppresses that
  request. Other channel pointers and inactive bands are retained. Each return is
  stored before its null check; failure stops later bands and leaves earlier
  controls and allocations intact. Original tail execution covers the finite
  pointer/failure selections, and complete old/current application checks reach
  those exits after the control writes. Allocator/helper outputs in these storage
  checks are explicit ABI models. Capacity, cleanup, ownership and live use remain
  separate gaps.
  [`wwise_mastering_coefficients.py`](../../scripts/webui/audio/semantics/wwise_mastering_coefficients.py)
  now proves the complete numeric generator dispatch through
  [`wwise_mastering_coefficients_native.json`](../../scripts/game_data/contracts/wwise_mastering_coefficients_native.json).
  A bounded scalar instruction decoder walks each native case through all six
  stores and compares expression trees that preserve every float32 operation.
  This includes the gain-dependent cases, first-order cases, both sides of
  the quality-threshold branch and the root-zero/unordered skip-division paths.
  Helper arguments are exact; their returns remain
  opaque. The first-order cases use a stored approximate Euler base in the power
  helper, which must not be replaced by an exact exponential. The raw zero-type
  generator writes zero coefficients; its wrapper instead skips generation and
  publishes identity coefficients. Unsupported unsigned types return an error
  without coefficient stores. Original generator and wrapper executions match
  the operation model exactly in bounded ordinary-input checks using captured
  helper returns. Strictly positive finite power-helper returns, completing SSE
  comparisons and nonzero normalization remain conditional. The root comparison
  takes its equality branch for zero or unordered and retains the undivided
  numerator. Modeled opaque helper returns exercise positive/negative zero,
  negative finite values and quiet NaN through original generator/wrapper code;
  finite coefficients and NaN output positions agree. Full NaN payload and
  floating exception behavior, whole helper equivalence, public filter names
  and actual CPU selection remain outside this arithmetic proof.
  [`wwise_mastering_trigonometry.py`](../../scripts/webui/audio/semantics/wwise_mastering_trigonometry.py)
  proves the packed helper's tiny pair and both finite fast-vector paths through
  [`wwise_mastering_trigonometry_native.json`](../../scripts/game_data/contracts/wwise_mastering_trigonometry_native.json).
  Tiny inputs return the input and a rounded quadratic approximation in the low
  pair. Larger inputs pack the input and its absolute value plus a stored
  approximation of π/2; the second result is a shifted sine approximation,
  with its own argument rounding. Both signed selector branches have identical
  lane-wise arithmetic: rounded-float range reduction, a split pi subtraction,
  quadrant and original sign bits, and an odd polynomial. The fast admission
  applies to every packed lane, not only the two results the caller uses.
  The authenticated crossover wrapper admits only normalized cutoffs strictly
  between zero and one half. Its generator clears the remaining input lanes
  before scaling the cutoff, so those crossover calls remain inside the proved
  tiny or finite fast domain for either selector branch. Original wrapper,
  generator, packed helper and normalization executions match independently
  computed stored coefficients, including poisoned incoming upper registers and
  identity fallback at rejected cutoffs or quality values. Separate original
  vector executions cover signed zero, subnormals, threshold neighbors and a
  wider finite corpus. Sampled sine/cosine error is an observation; it does not
  replace the instruction-order result. Large-argument reduction for other
  callers, exceptional callbacks, complete numerical parity, selector lifetime,
  named whole-helper identity and live use remain open.
  [`wwise_mastering_time.py`](../../scripts/webui/audio/semantics/wwise_mastering_time.py)
  authenticates the time helper through
  [`wwise_mastering_time_native.json`](../../scripts/game_data/contracts/wwise_mastering_time_native.json).
  It reduces the input to an integer, a table index and a binary exponent, then
  evaluates a cubic residual polynomial in binary64 and converts the result to
  float32. A lower-lane decoder proves both expressions, preserving the scalar
  rounding boundaries and the FMA path's fused operations. Range predicates and
  special-value construction are separate obligations. Both paths share the
  already authenticated power helper's table and mutable CPU-selector cell.
  Selected native code regions correspond to named CRT exponential functions;
  the merged shipped method differs from that named implementation. Positive
  infinity returns unchanged and negative infinity returns positive zero. NaNs
  retain their sign/payload while setting the quiet bit and bypass the external
  error routine. Finite overflow and underflow select infinity or zero and call
  that routine; the local handler preserves the selected candidate under the
  callee-saved ABI. Original scalar execution and separately modeled AVX
  floating instructions match the instruction-order oracle on bounded inputs,
  including caller arguments and range/table boundary neighbors. The AVX model
  is used because the emulator does not reproduce that instruction set reliably;
  it is not execution evidence for the original floating instructions. Sampled
  agreement with mathematical exponential does not establish general numerical
  equivalence. Error side effects, nondefault floating environment, traps,
  successful startup, selector lifetime and live CPU choice remain open.
  [`wwise_mastering_shared.py`](../../scripts/webui/audio/semantics/wwise_mastering_shared.py)
  closes the later context-indexed routine's sample arithmetic under admitted
  storage through
  [`wwise_mastering_shared_native.json`](../../scripts/game_data/contracts/wwise_mastering_shared_native.json).
  This separate routine blends saved samples with current planar-buffer samples
  using a degree-six polynomial, rounding each operation to float32. It handles
  the primary channels, an optional auxiliary buffer and identity-matched streams
  in an optional list. Short valid buffers modify the blend position as well as
  limiting processed samples. The transition timer decreases by the lesser of
  remaining duration and primary buffer capacity, independently of valid frame
  counts. Saved histories stay fixed during the transition. Calls beginning with
  a zero timer capture last valid samples; the list packs eligible identities and
  samples, skipping empty or selected-status buffers. List transitions match
  opaque identity values against that prior capture. The caller's two enabling
  bytes and indexed record stride are joined to the existing consumer proof.
  Complete original-routine offline execution agrees exactly with the reference
  polynomial, timer and capture model in bounded synthetic storage. Primary and
  auxiliary capture require positive valid frame counts; general empty-buffer
  admission is not proved. The producer and transition joins are separately
  authenticated by
  [`wwise_mastering_context.py`](../../scripts/webui/audio/semantics/wwise_mastering_context.py)
  and its
  [`wwise_mastering_context_native.json`](../../scripts/game_data/contracts/wwise_mastering_context_native.json).
  Setup keys parallel vectors by the retained context pointer, creates or reuses
  a shared record, and derives transition duration by truncating a float32
  sample-rate product then rounding upward to a power of two. Reusing a key
  resets its timer and previous counter while captured storage/count can persist.
  The effect reset callback starts the timer only when the anonymous current
  counter minus its saved counter equals one modulo its word width. Refresh
  preserves histories for that unit difference; every other difference clears
  shared and local histories. The captured list count remains while its arrays
  are zeroed. Execute runs the shared routine, publishes the current counter,
  and brackets those operations with declared critical-section calls. Local
  effect termination frees its own buffers and leaves shared rows intact;
  the registered global callback frees the per-record arrays and parallel
  vectors. Original native setup, growth, reset, Execute and teardown paths
  agree with bounded offline checks, including counter wrap and same-key reuse.
  Initial value-allocation failure frees the new identity array. Reallocation
  writes its returned pointer before checking null and writes the new capacity
  before the call; a failed call can therefore discard the stored old pointer.
  Retention of that old allocation depends on the allocator and is not inferred
  from the caller alone. Global cleanup skips records with a null value pointer.
  Counter API meaning, callback scheduling, complete allocator recovery,
  concurrent ownership/lifetime, public identity meaning and live invocation
  remain open.
  The normal local-engine caller is now joined to the existing descriptor
  admission proof, without a second mask-mapping catalog. Successful setup uses
  a fixed local DSP sample rate and frame capacity; prepared logical channels
  are rounded upward to four for the stride and scratch allocation requests.
  This bounds the normal stride to the channel-array capacity. The shared
  transition duration still uses the separate supplied sample rate. Refresh
  rejects every changed bit in the prepared channel-format word before downstream
  calls. Composed original caller checks capture the section descriptors and
  allocation requests with construction/conversion/section callbacks modeled.
  Standalone descriptor admission still accepts wider aligned strides, and an
  allocator's actual supplied capacity remains conditional. Refresh requires the
  primary maximum to be divisible by four, but that guard supplies no upper bound.
  The original chunk loop advances a word-sized offset; very high aligned maxima
  still wrap it. Complete original refresh checks after supported channel setup
  reach those paths with downstream effects modeled and stop on the repeated
  offset. This records a primary-frame
  admission gap, not a live-client fault. The full local buffer-setup body also
  joins its request arithmetic and retry paths. A nonnull main pointer suppresses
  allocation without checking its capacity. The first main allocation can fail
  immediately; the remaining three are all attempted before a combined check,
  retaining successful prior pointers. The optional byte must equal one, and
  each enabled setup requests and overwrites that pointer without freeing the
  previous one in this body. Disabled setup retains it. A format-helper failure
  returns its result without clearing a previously set ready flag. Original full
  execution checks every pointer-nullness/failure combination and repeated setup
  with ABI-conforming helper clobbers. Requested sizes and returned-pointer stores
  do not establish real capacity, helper side effects, retry cleanup or ownership.
  The reviewed limits and joins live in
  [`wwise_mastering_context_native.json`](../../scripts/game_data/contracts/wwise_mastering_context_native.json).
  [`wwise_convolution_consumer.py`](../../scripts/webui/audio/semantics/wwise_convolution_consumer.py)
  joins parameter copies, float reads, media admission and variant pointer layout;
  a conditional packed kernel expands upper-half float32 words. Header copies
  precede size checks, and these partial reads do not prove payload bounds.
  Each extension has its own reviewed native contract behind the shared selected
  triplet gate. Control names, alternate kernels and audible behavior remain open.
- **Buses and NodeBase tail.** The bus forest is typed and complete. The NodeBase
  tail yields AuxParams (user-defined aux slots reach aux buses; no populated
  early-reflections target), AdvSettings, State groups and RTPC curves, checked by an
  independent unique-payload audit. Game-defined aux ids, listeners and send levels
  are runtime inputs.
- **Properties.** Initial AkPropID bundles keep raw u32 and float forms; initial
  BypassFX/BypassAllFX ids do not occur; unnamed ids stay numeric.
- **Controls.** Non-playback Action tails are typed exactly or published as
  `failedClosed` with an offset and a reason. Six `AU_RTPC_*` GameParameter names are
  symbol-to-id evidence only
  ([`rtpc_alignment.py`](../../scripts/webui/audio/semantics/rtpc_alignment.py)).
  Type-6 selector packages join media only through exact same-bank evidence
  (`event_projection.selector_branch_projection`).
- **Media rows** project all of this per possible leaf; the contract, including
  `noExplicitOutputBusSerialized`, is the module docstring of
  [`media_rows.py`](../../scripts/webui/audio/semantics/media_rows.py).

## Rules this file taught

- Check a structural test against the degenerate input that passes it for free -- a
  run of zeros, a count of zero, a one-element list -- before reading its hit rate.
- A constant fitted by closure is established only if rivals scored the same way lose;
  score only the bodies that exercise it and reduce on corpus totals.
- Count bodies, not entries: one body can carry a whole total, and a 100% rate over
  optional structure is an average of claims.
- A field that is 0 in almost every body and small elsewhere is a count; a
  single-element counted run is indistinguishable from a fixed head.
- Measure locality from both ends of a variable-length body. Resolve ids in the
  right scope: per bank for a forest, corpus-wide before calling a word "resolves
  nowhere".
- A one-to-one claim needs distinct targets equal to the population, no repeats, and
  the edge total equal to both; an edge total alone supplies none of them.
- A neighbouring offset is a control only if it is not itself part of the structure.
- Never re-implement a hash the repo already mirrors: a duplicate FNV without the
  case fold once lost every literal with capitals.
- When rules accumulate around a field, suspect the field's shape; when a walk
  desynchronises, look for the next occurrence of something already parsed; when
  words look misaligned, find where a known sentinel sits to recover the grid.
- When a type will not frame, offer every word: sparse 32-bit ids let the id space
  discriminate. When a small type resists, look for a structure another type closes.
- Before presenting a located field as new, grep the reader for its offset; print a
  sigil, not a count, for varying positions in a byte table.

## Eliminated readings

- **Corpus-only framing of the music types** (head rules, end anchors, region grids,
  the `0x0D` `165 + 34a + 5b` length rule, the `0x0B` fixed 88-byte entries): fits
  retired by the SDK read. The length rule is a regularity of lengths only; the
  length groups do not align to one repeated block.
- **A second counted array in `0x0C`**: every "count" before it was 1, which any word
  holding 1 satisfies.
- **The music heads as a fixed skeleton**: only a few front positions are constant;
  the node frame parses at many offsets, so "it parsed" carries no information there.
- **The `0x08`/`0x12` tail in the music types**: the tail block fits almost nothing,
  and the apparent entry-run matches were all count-zero bodies.
- **The 12-byte curve record in `0x0A`/`0x0C`/`0x0D`**: chance fits; the unconstrained
  scan's near-total hits on `0x0D` were runs of zero bytes.
- **Curve propagation along bus edges**: untestable here -- too few edges with curves
  at both ends, and a shared-code statistic that scores the same on shuffled pairs.
- **`0x08` tail-head words as names**: none matches an FNV hash of any metadata string
  literal; the head's word at offset 10 is not a reference.
- **A head byte that sizes `0x0A`'s tail, or a byte inside the tail that counts its
  extension**: neither exists; the four-byte insertion sits right after the child
  reference.
- **The "fixed 9-byte signature" in `0x08`/`0x12`**: a field that varies in one 32-bit
  slot, not a magic.
- **A hand-read "zero-unit" tail layout**: invented from two samples, closed 1 of 10.
- **A misplaced entry run as the cause of the remaining fenced tails**: no run length
  from 0 to 63 frames them.
- **A `0x11` classification of the two edges into it**: too few references to place
  them on either side of an empty-middle discriminator.

## Open

- Convolution Reverb and Mastering Suite still need public control/section names,
  remaining conversion and processing mathematics, and live selection. Preserve
  the admitted-route conditions on recovered native consumers; do not fit names
  or additional runtime roles from corpus correlations.
- The AnimeStudio music head census should read `DirectParentID` after the FX and
  metadata groups instead of taking offset 5 when the FX count is nonzero; until
  then its nonzero-branch rows are FX references.
- Several lane residual strings still describe SDK-named fields as opaque (the
  `0x05` policy block, the `0x06` group head, the `0x0E` head); the names are in
  `hirc_v150`, the lanes do not publish them yet.
- Runtime: game-defined aux sends, live RTPC and State values, selector and decision
  tree choice, duck activation, effective inheritance, and audibility.
