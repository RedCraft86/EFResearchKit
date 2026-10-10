# Gameplay production catalogs

Production is the table-backed item, recipe and building publication displayed
inside Gameplay. Its builder keeps its own publication and does not rebuild or
depend on Gameplay, Assets or Data. Gameplay adds optional use effects and
rewards to item details from the publication in the same displayed language.
Its source links reuse the Data page's file viewer; the catalog and details
remain usable in a static package without that viewer's local server API.

## Inputs and publication

`scripts/webui/production/build_production.py` reads exported tables through
`ExportLayout`. Its `TABLE_NAMES` declaration is the exact table inventory;
the page registry declares the `table` structured input for extraction and
freshness checks. It reads no installed binary or other page's publication.
Existing Sprite crop documents and Texture2D images are optional reused inputs,
declared with the registry's `uses`; a Production refresh does not extract them.
The compact icon lookup uses authored `iconId` values and shared exact image-stem
resolution. Within exact-name candidates it shares Gameplay's item-icon shape
preference, then selects the highest resolution; Sprite wins an equal-size tie.
Same-name variants can include full art, small art and a solid silhouette, so a
Sprite-first filename sort is unsuitable for item thumbnails. This is a display
preference, not proof of the runtime asset selection. Missing icons stay
absent, with their identifiers recorded in `iconStatus`; no prefix match is used.

The builder publishes `webui/data/production/manifest.json`, the available
languages and default language, plus `webui/data/lang/<LANG>/production/index.json`
and item/recipe/building detail shards. Every source table has a SHA256 receipt
in the index. Missing or malformed required tables fail before publication.
An untranslated page uses the declared default language and displays that
fallback. The direct command is:

```bat
python -m scripts.webui.production.build_production --languages CN --default-language CN
```

`export.bat production` performs the page registry's normal freshness check and
build. Refreshing from the installed game remains an explicit separate choice.

## Recovered relationships

Item detail shards also carry `wikiDescriptions` from exact
`WikiEntryDataTable.refItemId` joins, with entry IDs and localized `desc` text.
Gameplay displays this explanation after primary and decorative descriptions,
including in the shared building/item detail. It uses the existing rich-text
renderer and deduplicates identical wiki explanations. This reads Production's
own exported tables, without a Story publication dependency.
The publication's `labels` resolves `ui_wiki_building_usable_formula` and
`ui_wiki_building_usable_func` through `TextTable` into the selected language's
I18n table. Gameplay uses their translated text for building recipe and wiki
explanation headings; keys are not displayed or translated via UI locale.
The same label map supplies item participating-recipe and activity-limited
recipe text from their corresponding wiki keys.
Recipe index summaries retain activity and gas-environment metadata and compact
original variants. Item recipe references select the variant by original ID,
never render a grouped union as one craft, and preserve condition badges in both
participating-recipe and production-source lists.
Item and building identity tags share the header row with the Story Wiki link.
Recipe rows keep formula, processing time and detail navigation in separate grid
columns; the building link lives inside the formula column so it cannot push the
detail link onto another row.

Item and building descriptions are separate authored fields:
`ItemTable.desc` and `FactoryBuildingTable.desc`. Their wording can differ even
for an exact building-item join (the multi-port underground pipe uses cargo
wording in the building record and liquids/gases in the item record). This does
not prove which field a runtime screen selects or that either field is obsolete.
`ItemTable.decoDesc` is item decorative text, not a second building description;
decorative buildings can repeat it in `FactoryBuildingTable.desc`. Details label
record/field sources only when linked descriptions differ (and decorative sources
only when linked decorative texts differ), group identical text into one display,
and retain distinct text separately. Descriptions have no headings; differing
sources use inline labels. Decorative text appears last, one font size smaller. This also covers
items whose own `desc` and `decoDesc` match. Per-publication inventories belong
under `reports/production/`, not in the durable recovery state.

- `ItemTable` supplies the complete catalog, localized item types, descriptions,
  rarity and stack fields; `FactoryItemTable` marks production-specific entries.
- Machine, hub and manual craft tables supply ingredients and outcomes. The
  item detail exposes reverse produced-by and used-in-recipe links. Machine
  recipe groups retain their stored nesting, including groups with multiple
  outputs. An explicit `machineId` matches a building by exact table key;
  `FactoryBuildingItemTable` maps building items to building identifiers.
- Recipe filters retain machine / infrastructure equipment / manual methods.
  Output categories collect every positive outcome's item type, showing type
  and exact building encyclopedia category, merging identical localized labels.
  The hub-craft method is displayed as 基建设备.
- `medals.py` groups achievement medals by matching authored name and completion
  text handles to each item's name and decorative description. Ambiguous pairs
  also require the achievement/level item identifier; plated variants require
  `canBePlated`. Conflicting owners remain separate. Every tier keeps its full
  item row, conditions and source references. `AchievementTypeTable` supplies
  category/group labels. Original item identifiers remain searchable aliases
  to the achievement group; localized names alone never create a group.
- `limited_items.py` groups duplicate limited-item records through the exact
  `LTItemTable.itemId` mapping, using its target as the display identity. Rows
  must match apart from their identifier and internal type. Missing targets,
  differing configuration and cyclic links stay separate; chains are not
  followed. Original records and types remain in `itemVariants`, source receipts
  and relationship lists are combined, and both identifiers remain searchable
  and navigable. This does not equate their runtime item types or expiration rules.
- Building categories follow the encyclopedia's `WikiGroupTable` building groups
  through exact `WikiEntryDataTable.refItemId` and building-item joins. Multiple
  categories are retained; buildings without a matching entry remain uncategorized.
  Visible depth, height and width come directly from `FactoryBuildingTable.range`,
  also attached to the corresponding building items, without inventing a unit.
- `ShopGoodsTable.rewardId` joins `RewardTable.itemBundles` by exact identifier.
  Listings retain their authored currency, price, limits and unlock conditions
  from the goods, shop and shop group. Probabilistic reward bundles are never
  promoted to fixed item sources. Shop rows without a reward identifier remain
  explicit coverage gaps.
- Weapon breakthrough materials follow `WeaponBasicTable`'s explicit template
  reference into `WeaponBreakThroughTemplateTable`. Zero costs do not create
  material-use links. Weapon experience items, equipment enhancement costs,
  manual-upgrade mappings, recipe formula items and shop currencies form the
  remaining supported reverse uses. Their original source rows remain attached.

## Evidence boundary and remaining work

These joins prove stored configuration and identifier references, not current
availability, runtime unlocks, complete acquisition coverage or actual production
rates. Configured machine duration follows the exported UI's
`FactoryUtils.getCraftNeedTime` in `Common/Utils/FactoryUtils.lua`:
`progressRound * msPerRound / 1000` seconds. `totalProgress` remains a raw progress
field. Missing rounds or craft-group milliseconds leave duration unspecified;
hub and manual recipes do not acquire an invented duration. Recipe groups do not
imply alternatives. A missing source link means
the supported tables do not supply one; it does not mean an item is unobtainable.
Manual-upgrade rows are shown as mappings, without inventing an unstated consumed
quantity. There is no guessed join by label, naming convention or address order.

Character upgrade costs, gathering locations, task rewards, live shop state and
resolved unlock-condition explanations remain outside this publication. Building
renderer-template metadata is retained without inferring additional recipe
ownership. The page does not calculate production chains or effective rates.
The catalog index retains building wiki category order for device list grouping.
Group headers use the exact published category joins, with uncategorized devices
last; filtering and pagination still count device records, not group headings.
Items and recipes group by their first domain filter, with combined crafting
methods kept together. Recipe source/use references retain each original method's
gas environment rather than borrowing one requirement from a grouped recipe.
Building detail recipe lists group rows by the exact gas-environment ID and
display the requirement once per group. Recipes without a requirement remain
in a separate group; activity restrictions and formulas stay on each recipe.
Activity-only formula tags use exact craft-ID membership in
`LimitedFormulaCraftIdReverseTable`; matching activity `timeLimitFormula` lists
provide the forward join. The exported `FactoryUtils.isTimeLimitedFormula`
consumer checks this reverse table, and `FormulaCtrl` uses it for the limited-time
marker. This establishes stored classification and a direct Lua UI consumer,
not native-body validation or current runtime availability. Activity membership
is retained per method; a combined recipe's tag means it contains an activity
method, not that every method is activity-limited.
Recipes and machine recipe rows display nominal quantities per minute as
`count * 60 / durationSeconds`, preserving stored groups and method boundaries;
unknown or nonpositive durations do not produce rates. Required `gasEnv` values
join `FactoryEnvDisplayTable` exactly, retaining the numeric requirement and its
environment icon token. The frontend names those authored display tokens and
shows the corresponding exported `icon_gas_env_*` presentation icon; known
requirements display only the icon and name, while unknown requirements stay
visible by ID. This icon selection does not claim runtime asset ownership.

## Frontend contract

`webui/src/features/production/index.js` mounts inside `#production-app` under
`#gameplay-view`; `gameplay/tabs.js` owns shared dataset navigation. It uses
shared facets, regular-expression search,
category/direction sorting, pagination, filter collapsing and Data file links.
The three catalogs are Gameplay's Items, Recipes and Machines & buildings. Selection,
search and repeated type/output-category/relationship filters persist in `production*` URL
parameters. Links also set `gameplayKind=item|recipe|machine` and use `#gameplay`.
Legacy `#production` links normalize to the shared Gameplay page while retaining
their filters and selection. Legacy Gameplay item identifiers open Items.
Search determines membership; the chosen name/rarity order applies even with
multiple search terms. Catalog and relationship navigation resets filters and
sorting to match the destination URL; browser history restores the prior state.
Replacing the catalog clears its detail state and invalidates pending detail
requests, including failures. Display-setting events cannot revive an old
selection, and a pending copy action only updates its original button.
Source tables and the coverage audit follow the global Show debug info switch.
Normal views retain item relationships and meaningful availability limitations.
Item-type filters merge identical localized labels while retaining each original
type in the data. Building filters show encyclopedia groups and their available
icons. Item, recipe-output and building icons share the same compact lookup.
Character avatar items follow `UserAvatarTable.itemId` and its explicit icon
reference, selecting a square image for character heads. Filled bottle and gas
jar icons overlay the exact `FullBottleTable.liquidId` or `FullGasJarTable.gasId`
item icon at the center, matching the exported `UI/Widgets/ItemIcon.lua` layout
(content side length `80/180` of the container). Achievement tiers select
`<achievementId>_lvNN` art and `_plating` for the proved plated variant. A single
authored tier displays Level 1 while retaining its original `sourceLevel` for
the icon and evidence; multiple tiers keep their authored levels.
Recipes with the same complete set of positive output item IDs share an entry.
`recipeVariants` preserve each source recipe's nested groups, counts, machine,
conditions and configured duration; differing co-products stay separate.
`recipeAliases` retains old recipe URLs and reverse links. Recipe type filters
cover all methods in an entry, and search covers all machines and source IDs.
Every method shows production time and expanded conditions/configuration in two
columns, stacking on narrow screens. These display groups do not imply one
combined craft or establish that methods are interchangeable at runtime.
Machines display `powerConsume` as electricity consumption and dimensions as
depth × width × height. Their recipe rows include each source method's full
ingredient/output groups and quantities plus processing time, with a link to
the recipe detail. The builder embeds these method summaries before recipe
grouping, so a machine row never borrows another method's time or quantities.
Descriptions render expanded through Story's safe rich-text renderer, including
bold and named emphasis tags, and follow the shared raw-tag display setting.
Empty relationship sections are omitted.

The shared update badges read `updates/production.json`. The Updates builder
compares the same catalog joins over both exports' authored source rows and
common localized text. Item, recipe, machine and grouped medal identities use
`<kind>:<id>` keys. Limited-item groups retain both raw item rows and their
`LTItemTable` mapping in the same comparison identity. UI changes and icon
display preferences create no game update.

Fixture tests in the local `scripts/tests/test_build_production.py` cover exact
joins, nested groups, zero-cost rejection, probabilistic shop boundaries,
unresolved identifiers, input failures and shard/index publication consistency.
They also cover localized type merging, exact encyclopedia joins, dimensions,
full-size icon selection, Sprite-only fallback and rejection of similar names.
`test_production_categories.py` covers output categories, medal ownership and
plating, old identifiers, and the scope and field details of Production updates.
`test_production_limited_items.py` covers explicit mapping, divergent and missing
targets, relationship preservation, aliases and grouped update provenance.
`scripts/tests/production_navigation.cjs` uses bounded browser fixtures for
sorting, URL/history state, delayed detail responses and clipboard completion.

Item recipe references resolve the original source ID within `recipeVariants`
before rendering a grouped recipe. Each source retains its own machine, groups,
time and environment; a grouped catalog entry is not a combined formula.
Shop cards group identical published configuration fields, excluding goods ID
and source links, and label the number of matching configurations. All goods
IDs and source links remain available; this grouping does not prove runtime
availability or merge the underlying goods. Raw goods can differ in sorting
even when the published display fields match.

Item and recipe pages share the compact method row: activity tag, machine,
gas environment, formula and processing time. Item/machine rows link to the
recipe page; recipe rows omit that self-link and retain supplemental formula
items, conditions and stored configuration below the row. Empty metadata
columns retain their width so formulas align across source methods.
