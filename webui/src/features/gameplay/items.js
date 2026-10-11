// Gameplay's combined item catalog includes buildings; recipes render within their related items. Publication paths and exact ID
// joins remain owned by the Gameplay items builder; gameplay/tabs.js owns navigation.
(() => {
  const W = window.WebUI;
  const esc = W.escapeHtml;
  const $ = (selector) => document.querySelector(selector);
  const ui = (en, cn) => String(window.WEBUI_UI_LOCALE || document.documentElement.lang || "zh").startsWith("zh") ? cn : en;
  const kinds = ["recipes", "items", "machines"];
  const storyIndexes = new Map();
  async function itemStoryLink(id, language) {
    if (!storyIndexes.has(language)) storyIndexes.set(language,
      getJson(`data/lang/${encodeURIComponent(language)}/index.json`).then((index) =>
        new Set((index.entries || []).filter((entry) => entry.d === "wiki").map((entry) => entry.k)))
        .catch((error) => { storyIndexes.delete(language); throw error; }));
    const key = `wiki_${id}`;
    if (!(await storyIndexes.get(language)).has(key)) return "";
    const params = new URLSearchParams({ lang: language,
      ui: window.WEBUI_UI_LOCALE || document.documentElement.lang || "zh", story: key });
    return W.gameplayDetail.storyWikiLink(`?${params.toString()}#story`, ui("Story wiki", "剧情 Wiki"));
  }
  const state = {
    root: null, data: null, itemImages: {}, requestedLanguage: "", language: "", selectedId: "",
    query: "", sort: "title", facets: null, rows: [], catalogRows: [], filtered: [], shards: new Map(),
    loadToken: 0, detailToken: 0, detail: null, loading: null, splitter: null, records: {},
  };
  const currentLanguage = () => String($("#language")?.value || "CN").toUpperCase();
  const active = () => document.body.dataset.activeView === "gameplay" && W.gameplayTabs?.kind === "item";
  const entryKey = (row) => `${row.kind}:${row.id}`;
  const wikiLabel = (key) => state.data?.labels?.[key] || "";
  const tagLabel = (tag) => ({
    factory_item: ui("Production material", "生产物料"), craftable: ui("Recipe output", "配方产物"),
    ingredient: ui("Recipe ingredient", "配方原料"), shop_reward: ui("Shop listing", "商店配置"),
    other_uses: ui("Other linked uses", "其他用途引用"), building_item: ui("Building item", "建筑物品"),
    no_source_link: ui("No linked recipe or shop", "未关联配方或商店"),
    machine: ui("Machine crafting", "由设备制造"), hub: ui("Infrastructure equipment", "制作设备的配方"),
    manual: ui("Manual crafting", "简易制造"), has_recipes: ui("Has recipes", "含配方"),
    needs_power: ui("Requires power", "需要供电"),
    activity_only: ui("Activity-only formula", "活动限定配方"),
  })[tag] || tag;
  const useLabel = (type) => ({
    weapon_breakthrough: ui("Weapon breakthrough", "武器突破"), weapon_experience: ui("Weapon experience", "武器经验"),
    equipment_enhance: ui("Equipment enhancement", "装备强化"),
    manual_upgrade_mapping: ui("Manual upgrade mapping", "手动制作升级映射"),
    recipe_formula: ui("Recipe formula reference", "配方物品引用"),
    shop_currency: ui("Shop currency", "商店货币"),
  })[type] || type;
  const number = (value) => W.formatNumber(value);
  const badge = (value) => `<span class="gameplay-items-badge">${esc(value)}</span>`;
  const empty = (message) => `<p class="gameplay-items-empty">${esc(message)}</p>`;
  const path = (file) => `data/lang/${encodeURIComponent(state.language)}/gameplay/items/${file}`;
  const richText = (text) => window.renderDisplayedTextHtml ? window.renderDisplayedTextHtml(text, "") : esc(text);
  const iconUrl = (id) => {
    const icon = state.data?.icons?.[String(id || "").toLowerCase()];
    return icon ? W.exportFullHref(icon.r) : "";
  };
  const iconHtml = (id, className = "") => {
    const url = iconUrl(id);
    return url ? `<img class="gameplay-items-icon ${className}" src="${esc(url)}" alt="" loading="lazy" decoding="async">` : "";
  };
  const rowIcon = (row, className = "") => {
    if (row.kind === "items" && String(row.type) === "13") {
      const images = state.itemImages[row.id] || [];
      const asset = row.iconId ? images.find((image) => image.role === "icon") : images[0];
      return asset?.rel ? `<img class="gameplay-items-icon ${className}" src="${esc(W.exportFullHref(asset.rel))}" alt="" loading="lazy" decoding="async">` : "";
    }
    const tiers = row.medalIcons || row.medalLevels?.map((tier) => ({
      iconId: tier.item?.medalIconId, level: tier.level, plated: tier.plated,
    }));
    if (tiers?.length) {
      return `<span class="gameplay-items-medal-icons">${tiers.map((tier) => {
        const label = `${ui("Level", "等级")} ${tier.level}${tier.plated ? ` · ${ui("Plated", "镀层")}` : ""}`;
        const image = iconHtml(tier.iconId, className);
        return image ? `<span title="${esc(label)}" aria-label="${esc(label)}">${image}</span>` : "";
      }).join("")}</span>`;
    }
    if (row.kind === "items" && String(row.type) === "100") return iconHtml(row.medalIconId, className);
    const refs = row.kind === "recipes" ? (row.outcomes || []).flat() : [row];
    const ref = refs.find((value) => iconUrl(value.iconId));
    if (!ref) return "";
    const base = iconHtml(ref.iconId, className);
    return iconUrl(ref.contentIconId)
      ? `<span class="gameplay-items-composite-icon ${className}">${base}${iconHtml(ref.contentIconId, "gameplay-items-content-icon")}</span>` : base;
  };
  const categoryLabel = (id) => id === "(none)" ? ui("Uncategorized", "未分类")
    : state.rows.flatMap((row) => row.categories || []).find((category) => category.id === id)?.title || id;
  const categoryIcon = (id) => iconUrl(state.rows.flatMap((row) => row.categories || []).find((category) => category.id === id)?.iconId);
  const rawTypeValue = (row) => row.kind === "machines" ? "building" : row.typeGroup || row.type || "(none)";
  const singletonTypes = new Set();
  const typeValue = (row) => singletonTypes.has(rawTypeValue(row)) ? "other" : rawTypeValue(row);
  const buildingLabel = (id) => id === "(none)" ? ui("Uncategorized", "未分类")
    : state.data.machineCategories.find((category) => category.id === id)?.title || id;
  const buildingIcon = (id) => iconUrl(state.data.machineCategories.find((category) => category.id === id)?.iconId);
  const buildingValues = (row) => row.buildingCategories.length ? row.buildingCategories.map((category) => category.id)
    : row.buildings.length ? ["(none)"] : [];

  function combinedItems(data) {
    const machines = new Map(data.machines.map((row) => [row.id, row]));
    const represented = new Set();
    const items = data.items.map((row) => {
      const buildings = row.buildingIds.map((id) => machines.get(id)).filter(Boolean);
      buildings.forEach((building) => represented.add(building.id));
      return { ...row, buildings,
        buildingCategories: [...new Map(buildings.flatMap((building) => building.categories).map((category) => [category.id, category])).values()],
        tags: [...new Set([...row.tags, ...buildings.flatMap((building) => building.tags)])],
      };
    });
    // Keep authored buildings without a published item, without duplicating exact item joins.
    return [...items, ...data.machines.filter((row) => !represented.has(row.id)).map((row) => ({
      ...row, buildings: [row], buildingCategories: row.categories,
      tags: [...new Set([...row.tags, "building_item"])],
    }))];
  }

  function itemSelection(kind, id) {
    if (!["items", "machines"].includes(kind)) return "";
    if (kind === "machines") {
      const item = state.data.items.find((row) => row.buildingIds.includes(id));
      if (item) return `items:${item.id}`;
    }
    return `${kind}:${id}`;
  }
  function pageUrl(kind, id) {
    const url = new URL(W.gameplayTabs.pageUrl("item", itemSelection(kind, id)));
    return url.href;
  }

  function recordLink(kind, id, title, resolved = true) {
    if (!id) return "";
    if (!resolved) return `<span class="gameplay-items-unresolved" title="${esc(ui("Unresolved identifier", "未解析标识符"))}">${esc(title || id)}</span>`;
    const row = state.records[kind]?.get(id);
    return `<a class="gameplay-items-record-link" href="${esc(pageUrl(kind, id))}" data-gameplay-items-kind="${esc(kind)}" data-gameplay-items-id="${esc(id)}" title="${esc(id)}">${row ? rowIcon(row) : ""}<span>${esc(title || id)}</span></a>`;
  }

  const itemLink = (ref) => recordLink("items", ref.catalogId, ref.title, ref.resolved);
  const itemBundle = (ref) => `<a class="gameplay-value-chip gameplay-item-chip gameplay-item-chip-link" href="${esc(pageUrl('items', ref.catalogId))}" data-gameplay-items-kind="items" data-gameplay-items-id="${esc(ref.catalogId)}">${iconHtml(ref.iconId, 'gameplay-item-chip-icon')}<b>${esc(ref.title || ref.name || ref.id)}</b>${W.gameplayDetail.knownQuantity(ref.count, ref.quantityDataUnavailable) ? ` ×${esc(number(ref.count))}` : ''}</a>`;

  function discountText(price, discount) {
    const rate = Number(discount);
    if (!Number.isFinite(rate) || rate <= 0 || rate > 1) return '';
    if (rate === 1) return badge(ui('Configured price: no discount', '配置折扣：无折扣（原价）'));
    // CashShopUtils.GetDisplayPrice rounds the rate before flooring the price.
    const percent = Math.floor(rate * 100 + 0.5);
    const amount = Math.floor(Number(price) * percent / 100);
    return `<span class="gameplay-items-badge">${esc(ui(`Configured ${percent}% price: ${number(amount)}`, `配置${percent / 10}折：${number(amount)}`))}</span>`;
  }

  function sourceLinks(rows = []) {
    const unique = [...new Map(rows.map((row) => [`${row.table}:${row.row}:${row.field || ""}`, row])).values()];
    if (!unique.length) return "";
    return `<details class="gameplay-items-sources gameplay-items-technical"><summary>${esc(ui("Source tables", "源数据表"))} (${unique.length})</summary><ul>${unique.map((row) => {
      const href = W.dataPageUrl({ store: "loose", group: "Table", name: `${row.table}.json` });
      return `<li><a href="${esc(href)}">${esc(row.table)}.json</a> · <code>${esc(row.row)}${row.field ? `.${esc(row.field)}` : ""}</code></li>`;
    }).join("")}</ul></details>`;
  }

  function properties(values, label = ui("Stored configuration", "存储配置"), expanded = false) {
    const rows = Object.entries(values).filter(([, value]) => value != null && value !== "");
    if (!rows.length && !expanded) return "";
    const content = rows.length ? `<dl>${rows.map(([key, value]) => `<dt>${esc(key)}</dt><dd>${esc(typeof value === "object" ? JSON.stringify(value) : String(value))}</dd>`).join("")}</dl>` : empty(ui("No values stored.", "未存储配置值。"));
    return expanded ? `<section class="gameplay-items-properties"><h4>${esc(label)}</h4>${content}</section>`
      : `<details class="gameplay-items-properties"><summary>${esc(label)}</summary>${content}</details>`;
  }

  function section(title, contents, count) {
    return W.gameplayDetail.section(title, contents, { className: "gameplay-items-section", count });
  }

  function dimensions(range) {
    const axes = ["depth", "width", "height"];
    if (!axes.some((key) => Number.isFinite(range?.[key]))) return "";
    const size = axes.map((key) => Number.isFinite(range?.[key]) ? number(range[key]) : "—").join(" × ");
    return `<dl class="gameplay-items-dimensions"><div><dt>${esc(ui("Dimensions (depth × width × height)", "尺寸（深度 × 宽度 × 高度）"))}</dt><dd>${esc(size)}</dd></div></dl>`;
  }

  const durationText = (row) => row.durationSeconds != null
    ? `${esc(number(row.durationSeconds))} ${esc(ui("s", "秒"))}` : esc(ui("Not specified", "未指定"));

  function gasRequirement(row) {
    const env = row.gasEnvironment;
    const id = env?.id;
    if (!id) return "";
    const gas = {
      T_fx_icon_gas_stable_UI: { name: ui("Stable", "稳定"), icon: "icon_gas_env_stable" },
      T_fx_icon_gas_wet_UI: { name: ui("Wet", "潮湿"), icon: "icon_gas_env_humidity" },
      T_fx_icon_gas_acidic_UI: { name: ui("Acidic", "酸性"), icon: "icon_gas_env_acid" },
      T_fx_icon_gas_xiranite_UI: { name: ui("Xiranite", "息壤"), icon: "icon_gas_env_xiranite" },
    }[env?.iconId];
    return `<div class="gameplay-items-gas-requirement"><strong>${esc(ui("Required gas environment", "所需气体环境"))}</strong>: ${iconHtml(gas?.icon)} ${esc(gas?.name || String(id))}</div>`;
  }

  function activityTag(row) {
    return row.activityId ? `<div class="gameplay-items-activity-tag">${badge(ui("Activity-only", "活动限定"))}</div>` : "";
  }

  function rateText(ref, seconds) {
    return Number.isFinite(seconds) && seconds > 0 && Number.isFinite(ref.count) && ref.count >= 0
      ? `<span class="gameplay-items-rate">${esc(number(ref.count * 60 / seconds))} ${esc(ui("/ min", "/ 分钟"))}</span>` : "";
  }

  function inlineRecipeGroups(groups, seconds, renderItem = itemBundle) {
    if (!(groups || []).some((group) => group.length)) return esc(ui("No items recorded", "未记录物品"));
    return `<span class="gameplay-items-machine-group">${groups.flat().map((ref) => `<span class="gameplay-items-reaction-item">${renderItem(ref)} ${rateText(ref, seconds)}</span>`).join(' <span class="gameplay-items-plus">+</span> ')}</span>`;
  }

  function renderMachineRecipe(recipe, showEnvironment = true, { renderItem = itemBundle, formulaOnly = false, catalogLayout = false } = {}) {
    if (!recipe.activityId && (!showEnvironment || (!recipe.machineId && !recipe.gasEnvironment))) formulaOnly = true;
    const formula = `${inlineRecipeGroups(recipe.ingredients, recipe.durationSeconds, renderItem)}<span class="gameplay-items-machine-arrow" aria-hidden="true">→</span>${inlineRecipeGroups(recipe.outcomes, recipe.durationSeconds, renderItem)}`;
    const time = Number.isFinite(recipe.durationSeconds) ? `<span class="gameplay-items-machine-time">${esc(ui("Processing time", "处理时间"))}: ${durationText(recipe)}</span>` : "";
    const device = catalogLayout && showEnvironment && recipe.machineId ? recordLink("machines", recipe.machineId, recipe.machineName) : "";
    const contentClass = catalogLayout ? " gameplay-items-machine-content-catalog" : formulaOnly ? " gameplay-items-machine-content-formula-only" : showEnvironment ? "" : " gameplay-items-machine-content-compact";
    return `<article class="gameplay-skill-card gameplay-items-machine-recipe${catalogLayout ? " gameplay-items-catalog-recipe" : ""}" data-gameplay-items-recipe="${esc(recipe.id)}"><div class="gameplay-items-machine-content${contentClass}"><div class="gameplay-items-machine-activity">${activityTag(recipe)}</div>${catalogLayout ? "" : `<div class="gameplay-items-machine-device">${showEnvironment && recipe.machineId ? recordLink("machines", recipe.machineId, recipe.machineName) : ""}</div><div class="gameplay-items-machine-environment">${showEnvironment ? gasRequirement(recipe) : ""}</div>`}<div class="gameplay-items-machine-formula">${catalogLayout && showEnvironment ? gasRequirement(recipe) : ""}${formula}${catalogLayout && (device || time) ? `<div class="gameplay-items-reaction-details">${device}${time}</div>` : ""}</div></div>${catalogLayout ? "" : time}</article>`;
  }

  function renderMachineRecipes(recipes) {
    if (!recipes.some((recipe) => recipe.gasEnvironment)) return `<div class="gameplay-items-references">${recipes.map((recipe) => renderMachineRecipe(recipe, true, { catalogLayout: true })).join("")}</div>`;
    const groups = new Map();
    for (const recipe of recipes) {
      const key = recipe.gasEnvironment?.id ?? null;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(recipe);
    }
    return [...groups].map(([environment, rows]) => `<section class="gameplay-items-environment-group" data-gameplay-items-environment="${esc(environment ?? "none")}">
      ${environment == null ? `<h4>${esc(ui("No gas environment requirement", "无气体环境要求"))}</h4>` : gasRequirement(rows[0])}
      <div class="gameplay-items-references">${rows.map((recipe) => renderMachineRecipe(recipe, false, { catalogLayout: true })).join("")}</div></section>`).join("");
  }

  function recipeRefs(rows, produced) {
    if (!rows.length) return empty(ui("No recipe links recovered in these tables.", "这些表中未恢复到配方关联。"));
    return `<div class="gameplay-items-references">${rows.map((row) => {
      const entry = state.records.recipes.get(row.groupId);
      const recipe = entry?.recipeVariants ? entry.recipeVariants.find((variant) => variant.id === row.id) : entry;
      if (!recipe) throw new Error(`${ui("Missing published recipe", "缺少已发布配方")}: ${row.id}`);
      return renderMachineRecipe({ ...row, ...recipe }, true, { catalogLayout: true })
        + (produced ? recipeConfiguration(recipe) : "");
    }).join("")}</div>`;
  }

  function groupShopListings(rows) {
    // Record IDs and discounts vary within one otherwise matching purchase.
    const stable = (value) => Array.isArray(value) ? value.map(stable)
      : value && typeof value === "object" ? Object.fromEntries(Object.keys(value).sort().map((key) => [key, stable(value[key])])) : value;
    const groups = new Map();
    for (const row of rows) {
      const { id, goodsId, rewardId, sources, cnDiscount, ...configuration } = row;
      const key = JSON.stringify(stable(configuration));
      if (!groups.has(key)) groups.set(key, { ...row, goodsIds: [], discountVariants: [], sources: [] });
      const group = groups.get(key);
      const recordId = goodsId || id;
      if (recordId && !group.goodsIds.includes(recordId)) group.goodsIds.push(recordId);
      if (!group.discountVariants.includes(cnDiscount)) group.discountVariants.push(cnDiscount);
      group.sources.push(...(sources || []));
    }
    return [...groups.values()];
  }

  function shopDiscounts(row, price) {
    return row.discountVariants.slice()
      .sort((a, b) => Number(b) - Number(a))
      .map((discount) => discountText(price, discount)).join(" ");
  }

  function renderShop(row) {
    const conditions = Object.values(row.conditions || {}).some((value) => Array.isArray(value) ? value.length : !!value);
    return `<article class="gameplay-items-reference"><strong>${esc(row.shopGroupName)}${row.shopName !== row.shopGroupName ? ` · ${esc(row.shopName)}` : ""}</strong>
      <div>${W.gameplayDetail.knownQuantity(row.count, row.quantityDataUnavailable) ? `${esc(ui("Configured quantity", "配置数量"))}: ${number(row.count)} · ` : ''}${esc(ui("Price", "价格"))}: ${number(row.price)} ${itemLink(row.currency)}</div>
      ${shopDiscounts(row, row.price)}
      ${row.currency?.id === 'item_spaceship_credit' ? `<small>${esc(ui('Actual price uses the server-provided discount.', '实际价格采用服务器下发的折扣。'))}</small>` : ''}
      ${row.goodsIds?.length > 1 ? `<div>${esc(ui("Grouped shop records", "合并商店记录"))}: ${number(row.goodsIds.length)}</div>` : ""}
      ${conditions ? badge(ui("Has unlock conditions", "有解锁条件")) : ""}${row.hasRandomRewards ? badge(ui("Also contains random rewards", "还含随机奖励")) : ""}
      ${row.lockDescription ? `<p>${richText(row.lockDescription)}</p>` : ""}
      ${properties({ goodsId: row.goodsIds?.length > 1 ? row.goodsIds : row.id, limitCount: row.limitCount, limitCountRefreshType: row.limitCountRefreshType,
        cnDiscount: row.discountVariants || row.cnDiscount, shopRefreshType: row.shopRefreshType, shopRefreshCycleType: row.shopRefreshCycleType,
        unlockConditions: row.conditions }, ui("Limits and conditions", "限购与条件"))}${sourceLinks(row.sources)}</article>`;
  }

  function renderUses(rows) {
    const groups = new Map();
    for (const row of rows) {
      if (!groups.has(row.type)) groups.set(row.type, []);
      groups.get(row.type).push(row);
    }
    return [...groups].map(([type, rows]) => {
      const group = type === 'shop_currency' ? groupShopListings(rows) : rows;
      return `<details class="gameplay-items-use-group"${group.length <= 5 ? " open" : ""}><summary>${esc(useLabel(type))} (${number(group.length)})</summary>${type === 'shop_currency' ? `<p>${esc(ui('Configured discounts and prices are shown for each purchase. Actual discounts are supplied by the server.', '每条购买记录展示配置折扣与折后价，实际折扣以服务器下发为准。'))}</p>` : ''}<div class="gameplay-items-references">${group.map((row) => {
      const resolved = row.targetKind && state.records[row.targetKind]?.has(row.targetCatalogId);
      const title = row.targetId ? recordLink(row.targetKind, row.targetCatalogId, row.title, resolved) : esc(row.title);
      return `<article class="gameplay-items-reference">${gasRequirement(row)}${title}${W.gameplayDetail.knownQuantity(row.count, row.quantityDataUnavailable) ? ` ${badge(type === 'shop_currency' ? `${ui('Base price', '原价')}: ${number(row.count)}` : `× ${number(row.count)}`)}` : ""}
        ${row.level != null ? `<div>${esc(ui("Breakthrough level", "突破等级"))}: ${esc(row.level)}${row.displayLevel != null ? ` · ${esc(ui("Displayed level", "显示等级"))}: ${esc(row.displayLevel)}` : ""}</div>` : ""}
        ${type === 'shop_currency' ? shopDiscounts(row, row.count) : ''}
        ${row.items?.length ? `<div class="item-reward-tags">${row.items.map(itemBundle).join('')}</div>` : ""}
        ${row.hasRandomRewards ? badge(ui("Also contains random rewards", "还含随机奖励")) : ""}
        ${type === "weapon_experience" ? properties({ itemExp: row.itemExp, weaponExp: row.weaponExp, weaponExpConvertRatio: row.weaponExpConvertRatio }) : ""}
        ${sourceLinks(row.sources)}</article>`;
    }).join("")}</div></details>`;
    }).join("") || empty(ui("No other uses linked in the supported tables.", "支持的数据表中未关联其他用途。"));
  }

  function itemTags(row) {
    return `${badge(row.typeName)}${row.showingTypeName && row.showingTypeName !== row.typeName ? badge(row.showingTypeName) : ""}${badge(`${ui("Rarity", "稀有度")} ${row.rarity}`)}`;
  }

  function itemStorageMetadata(row) {
    const stack = Number.isFinite(row.stackLimit) && row.stackLimit > 1 ? row.stackLimit : null;
    const backpack = Number.isFinite(row.backpackStackLimit) && row.backpackStackLimit > 1 ? row.backpackStackLimit : null;
    const buffer = row.factory?.buildingBufferStackLimit;
    return [
      stack && stack === backpack ? { label: ui("Stack limit", "堆叠上限"), value: number(stack) } : null,
      stack && stack !== backpack ? { label: ui("Stack limit", "堆叠上限"), value: number(stack) } : null,
      backpack && stack !== backpack ? { label: ui("Backpack stack limit", "背包堆叠上限"), value: number(backpack) } : null,
      Number.isFinite(buffer) && buffer > 1 ? { label: ui("Building buffer stack limit", "设备缓存堆叠上限"), value: number(buffer) } : null,
    ].filter(Boolean);
  }

  function itemProperties(row) {
    const raw = properties({ maxStackCount: row.stackLimit, maxBackpackStackCount: row.backpackStackLimit, obtainWayIds: row.obtainWayIds, ...row.factory }, ui("Raw item configuration", "原始物品配置"));
    return raw ? `<div class="gameplay-items-technical">${raw}</div>` : "";
  }

  function renderItem(row, includeLore = true, includeMeta = true) {
    let html = row.sharedBuilding || !includeMeta ? "" : `<div class="gameplay-items-meta">${itemTags(row)}</div>`;
    if (row.medalLevels?.length) {
      html += `<div class="gameplay-items-meta">${(row.categories || []).map((category) => badge(category.title)).join("")}</div>`;
      return html + section(ui("Medal tiers", "蚀刻章等级"), `<div class="gameplay-items-references">${row.medalLevels.map((tier) => `<article class="gameplay-items-reference gameplay-items-medal-tier">
        <h4>${rowIcon(tier.item)}${esc(`${ui("Level", "等级")} ${tier.level}${tier.plated ? ` · ${ui("Plated", "镀层")}` : ""}`)}</h4><code>${esc(tier.item.id)}</code>
        ${tier.item.description && tier.item.description !== row.description ? `<div class="gameplay-items-description">${richText(tier.item.description)}</div>` : ""}
        ${tier.conditions.length ? `<ul>${tier.conditions.map((condition) => `<li>${richText(condition.description || condition.conditionId)}${condition.progressToCompare != null ? ` · ${esc(ui("Target", "目标"))} ${number(condition.progressToCompare)}` : ""}</li>`).join("")}</ul>` : ""}
        ${renderItem(tier.item)}${sourceLinks(tier.item.sources)}</article>`).join("")}</div>`, row.medalLevels.length);
    }
    if (includeLore && row.lore && row.lore !== row.description) html += sourceDescription(row, true);
    for (const building of row.sharedBuilding ? [] : row.buildingDimensions || []) {
      html += `${row.buildingDimensions.length > 1 ? `<p>${esc(building.title)}</p>` : ""}${dimensions(building)}`;
    }
    html += renderItemConnections(row);
    if (row.outputReferences.length) html += section(ui("Configured output references", "配置产物引用"), row.outputReferences.map(itemLink).join(" · "));
    if (!row.sharedBuilding) html += itemProperties(row);
    return html;
  }

  function renderItemConnections(row) {
    const shops = groupShopListings(row.shops);
    let html = section(ui("Produced by", "制作来源"), recipeRefs(row.producedBy, true), row.producedBy.length);
    html += section(wikiLabel("ui_wiki_item_part_formula"), recipeRefs(row.usedBy, false), row.usedBy.length);
    if (shops.length) html += `<details class="gameplay-items-section gameplay-items-shop-section"><summary>${esc(ui("Configured shop listings", "商店配置"))} <span>(${number(shops.length)})</span></summary>${shops.map(renderShop).join("")}</details>`;
    html += section(ui("Upgrades and other uses", "升级与其他用途"), renderUses(row.upgrades), row.upgrades.length);
    return html;
  }

  function recipeConfiguration(row) {
    return `${row.formulaItem ? section(ui("Formula item", "配方物品"), itemLink(row.formulaItem)) : ""}<div class="gameplay-items-recipe-config">${properties(row.conditions || {}, ui("Unlock and operating conditions", "解锁与运行条件"))}<div class="gameplay-items-technical">${properties({ ...(row.configuration || {}), ...(row.timing || {}) }, ui("Raw recipe configuration", "原始配方配置"))}</div></div>`;
  }

  function machineTags(row) {
    return `${(row.categories || []).map((category) => `<span class="gameplay-items-badge gameplay-items-category">${iconHtml(category.iconId)}${esc(category.title)}</span>`).join("")}${row.needPower ? badge(ui("Requires power", "需要供电")) : ""}${badge(`${ui("Electricity consumption", "电力消耗")}: ${row.powerConsume ?? "—"}`)}`;
  }

  function machineProperties(row) {
    const raw = properties({ type: row.type, inputPorts: row.inputPorts, outputPorts: row.outputPorts, range: row.range,
      placeDomains: row.placeDomains, recommendDomains: row.recommendDomains, rendererTemplateMap: row.rendererTemplateMap }, ui("Raw building configuration", "原始建筑配置"));
    return raw ? `<div class="gameplay-items-technical">${raw}</div>` : "";
  }
  function machineAttributes(row) {
    const axes = ["depth", "width", "height"];
    const fields = [
      axes.some((key) => Number.isFinite(row.range?.[key])) ? { label: ui("Dimensions (depth × width × height)", "尺寸（深度 × 宽度 × 高度）"), value: axes.map((key) => Number.isFinite(row.range?.[key]) ? number(row.range[key]) : "—").join(" × "), numeric: true } : null,
      row.needPower != null ? { label: ui("Requires power", "需要供电"), value: row.needPower ? ui("Yes", "是") : ui("No", "否") } : null,
      row.powerConsume != null ? { label: ui("Electricity consumption", "电力消耗"), value: number(row.powerConsume), numeric: true } : null,
    ].filter(Boolean);
    return section(ui("Basic attributes", "基础属性"), W.gameplayDetail.propertyGrid(fields.map((field) => W.gameplayDetail.propertyCard({ title: field.label, bodyHtml: `<p class="gameplay-description">${field.numeric ? `<span class="gameplay-desc-value">${esc(field.value)}</span>` : esc(field.value)}</p>` }))));
  }

  function renderMachine(row, includeItemConnections = true, compact = false, includeMeta = true, includeAttributes = true) {
    let html = compact || !includeMeta ? "" : `<div class="gameplay-items-meta">${machineTags(row)}</div>`;
    if (includeAttributes) html += machineAttributes(row);
    if (!compact && row.items.length) html += section(ui("Building items", "建筑物品"), row.items.map(itemLink).join(" · "));
    if (includeItemConnections) for (const item of row.linkedItems || []) html += renderItemConnections(item);
    html += section(wikiLabel("ui_wiki_building_usable_formula"), row.recipes.length ? renderMachineRecipes(row.recipes) : empty(ui("No recipe names this building ID.", "没有配方直接引用此建筑标识符。")), row.recipes.length);
    if (!compact) html += machineProperties(row);
    return html;
  }

  function sharedBuildingDetail(row) {
    const item = row.kind === "items" ? row : row.linkedItems?.length === 1 ? row.linkedItems[0] : null;
    const building = row.kind === "machines" ? row : row.linkedMachines?.length === 1 ? row.linkedMachines[0] : null;
    if (!item || !building || item.buildingIds?.length !== 1 || building.items?.length !== 1
      || item.buildingIds[0] !== building.id || building.items[0].id !== item.id) return row;
    const sources = [...new Map([...item.sources, ...building.sources].map((source) => [JSON.stringify(source), source])).values()];
    const { linkedItems: _items, linkedMachines: _machines, itemLore: _lore, ...buildingRecord } = building;
    return { ...item, linkedItems: [], linkedMachines: [buildingRecord], sharedBuilding: buildingRecord, sources };
  }

  // These fields belong to different table records; neither proves which
  // description a particular runtime screen selects.
  function sourceDescription(row, deco = false, showSource = false) {
    const value = deco ? row.lore : row.description;
    if (!value) return "";
    const machine = row.kind === "machines";
    const label = deco ? ui("Item decorative description", "物品装饰描述")
      : machine ? ui("Building description", "设备描述") : ui("Item description", "物品描述");
    const source = `${machine ? "FactoryBuildingTable" : "ItemTable"}[${row.id}].${deco ? "decoDesc" : "desc"}`;
    return `<div class="gameplay-items-description${deco ? " gameplay-items-deco" : ""}">${showSource ? `<small>${esc(label)} · <code>${esc(source)}</code></small>` : ""}<div>${richText(value)}</div></div>`;
  }

  function detailDescriptions(row) {
    if (!["items", "machines"].includes(row.kind)) return row.description ? `<div class="gameplay-items-description">${richText(row.description)}</div>` : "";
    const groups = new Map();
    const related = [row, ...(row.linkedItems || []), ...(row.linkedMachines || [])];
    const descriptionsDiffer = new Set(related.map((record) => record.description).filter(Boolean)).size > 1;
    const decoDiffer = new Set(related.map((record) => record.lore).filter(Boolean)).size > 1;
    for (const deco of [false, true]) {
      for (const record of related) {
        const value = deco ? record.lore : record.description;
        if (!value) continue;
        const group = groups.get(value) || [];
        group.push({ record, deco });
        groups.set(value, group);
      }
    }
    const rendered = [...groups.values()].map((records) => {
      const showSource = records.some(({deco}) => deco ? decoDiffer : descriptionsDiffer);
      if (records.length === 1 || !showSource) {
        return sourceDescription(records[0].record, records[0].deco, showSource);
      }
      if (records.every(({deco}) => deco)) {
        const sources = records.map(({record}) => `<div><small><code>${esc(`ItemTable[${record.id}].decoDesc`)}</code></small></div>`).join("");
        return `<div class="gameplay-items-description gameplay-items-deco">${sources}<div>${richText(records[0].record.lore)}</div></div>`;
      }
      const labels = [...new Set(records.map(({record, deco}) => deco ? ui("Item decorative description", "物品装饰描述") : record.kind === "machines" ? ui("Building description", "设备描述") : ui("Item description", "物品描述")))];
      return `<div class="gameplay-items-description">${showSource ? `<small>${esc(labels.join(" / "))}</small>` + records.map(({record, deco}) => `<div><small><code>${esc(`${record.kind === "machines" ? "FactoryBuildingTable" : "ItemTable"}[${record.id}].${deco ? "decoDesc" : "desc"}`)}</code></small></div>`).join("") : ""}<div>${richText(records[0].deco ? records[0].record.lore : records[0].record.description)}</div></div>`;
    });
    // Decorative text follows all primary descriptions without a heading.
    const decorative = [];
    const primary = [];
    [...groups.values()].forEach((records, index) => {
      (records.every(({deco}) => deco) ? decorative : primary).push(rendered[index]);
    });
    return [...primary, ...decorative].join("");
  }

  function renderRecordAudio(row, payload) {
    if (payload?.schema !== "endfield.audio-record-media.v1") return "";
    return (row.musicLinks || []).map((link) => {
      const media = payload.events?.[link.eventId]?.media || [];
      const label = link.role === "sample" ? ui("Sample", "试听片段") : ui("Full track", "完整曲目");
      return media.filter((candidate) => candidate.src).map((candidate) => {
        const filename = (candidate.rel || candidate.src).split(/[\\/]/).pop();
        return `<figure class="gameplay-items-audio-asset"><figcaption>${esc(label)}${media.length > 1 ? ` · ${esc(ui("Candidate audio", "候选音频"))}` : ""}</figcaption><audio controls preload="none" src="${esc(candidate.src)}" aria-label="${esc(label + ': ' + filename)}"></audio><div class="gameplay-items-audio-filename">${esc(filename)}</div></figure>`;
      }).join("");
    }).join("");
  }

  function renderDetail(row) {
    const panel = $("#gameplay-items-detail");
    if (!panel) return;
    if (!row) { panel.innerHTML = empty(ui("Select an item to explore its connections.", "选择物品以查看关联。")); return; }
    const machineView = row.kind === "machines";
    panel.classList.add("gameplay-catalog-reading-view");
    row = sharedBuildingDetail(row);
    const hasBuilding = machineView || Boolean(row.sharedBuilding);
    panel.classList.toggle("gameplay-items-machine-reading-view", hasBuilding);
    const updateId = `${row.kind}:${row.id}`;
    const machine = row.sharedBuilding || row;
    const detailMeta = W.gameplayDetail.metadata([
      { label: ui("Type", "类型"), value: machineView ? ui("Building", "建筑") : ui("Item", "物品") },
      { label: "ID", value: row.id },
      row.sharedBuilding ? { label: ui("Building ID", "建筑标识符"), value: row.sharedBuilding.id } : null,
      row.typeName ? { label: ui("Item type", "物品类型"), value: row.typeName } : null,
      row.showingTypeName && row.showingTypeName !== row.typeName ? { label: ui("Display type", "显示类型"), value: row.showingTypeName } : null,
      row.rarity != null ? { label: ui("Rarity", "稀有度"), value: row.rarity } : null,
      ...itemStorageMetadata(row),
      (machine.categories || []).length ? { label: ui("Category", "分类"), value: machine.categories.map((category) => category.title).join(" / ") } : null,
      hasBuilding && ["depth", "width", "height"].some((key) => Number.isFinite(machine.range?.[key]))
        ? { label: ui("Dimensions", "尺寸"), value: ["depth", "width", "height"].map((key) => Number.isFinite(machine.range?.[key]) ? number(machine.range[key]) : "—").join("×") } : null,
      hasBuilding && machine.needPower != null ? { label: ui("Requires power", "需要供电"), value: machine.needPower ? ui("Yes", "是") : ui("No", "否") } : null,
      hasBuilding && machine.powerConsume != null ? { label: ui("Electricity consumption", "电力消耗"), value: number(machine.powerConsume) } : null,
    ]);
    const entityLinks = row.kind === "items" ? [
      ["weapon", ui("Weapon details", "武器详情")],
      ["equipment", ui("Equipment details", "装备详情")],
    ].filter(([kind]) => W.gameplay.hasEntry(kind, row.id, state.language))
      .map(([kind, label]) => W.gameplayDetail.datasetLink(kind, row.id, label)).join("") : "";
    const musicLinks = (row.musicLinks || []).map((link) => {
      const url = new URL(window.location.href);
      for (const key of [...url.searchParams.keys()]) if (key.startsWith("audio")) url.searchParams.delete(key);
      url.searchParams.set("audio", link.eventId);
      url.searchParams.set("audioKind", "events");
      url.hash = "audio";
      return W.gameplayDetail.storyWikiLink(url.toString(), link.role === "sample"
        ? ui("Audio: sample", "音频：试听片段") : ui("Audio: full track", "音频：完整曲目"));
    }).join("");
    const detailLinks = entityLinks + musicLinks;
    panel.innerHTML = `<header class="gameplay-items-detail-header gameplay-detail-heading">${W.gameplayDetail.identity({
      imageHtml: rowIcon(row, "gameplay-items-icon-large"),
      titleHtml: `${esc(row.title)} ${W.updateBadges.html("gameplay", updateId)}`,
      metadataHtml: `<div class="gameplay-heading-meta gameplay-items-detail-meta">${esc(detailMeta)}</div><div class="gameplay-heading-links" data-gameplay-items-story-link${detailLinks ? "" : " hidden"}>${detailLinks}</div>`,
    })}<button id="gameplay-items-reveal-current" class="locate-current-button" type="button">${esc(ui("Locate current file", "定位当前文件"))}</button></header><div class="gameplay-catalog-detail-body">
      ${W.updateBadges.panel("gameplay", updateId)}
      ${detailDescriptions(row)}
      ${renderWikiDescriptions(row)}
      ${row.kind === "items" ? renderItem(row, false, false) : renderMachine(row, true, false, false, !hasBuilding)}
      ${row.sharedBuilding ? `${renderMachine(row.sharedBuilding, false, true, true, !hasBuilding)}<div class="gameplay-items-shared-config">${itemProperties(row)}${machineProperties(row.sharedBuilding)}</div>` : (row.linkedMachines || []).map((machine) => section(machine.title, renderMachine(machine, false) + sourceLinks(machine.sources))).join("")}
      ${row.kind === "items" ? '<div class="gameplay-items-gameplay-item" data-gameplay-item-content></div>' : ""}${sourceLinks(row.sources)}<div data-gameplay-item-assets></div></div>`;
    W.gameplayDetail.bindDatasetLinks(panel);
    const gallery = panel.querySelector("[data-gameplay-item-assets]");
    const displayedIcons = new Set([...panel.querySelectorAll("img.gameplay-items-icon")].map((image) => image.getAttribute("src")));
    if (machineView) for (const id of [row.iconId, row.contentIconId, machine.iconId]) {
      const url = iconUrl(id);
      if (url) displayedIcons.add(url);
    }
    const seenAssets = new Set();
    const images = row.kind === "items" && String(row.type) === "13" ? state.itemImages[row.id] || [] : Object.entries(state.data.icons || {}).flatMap(([id, icon]) => {
      if (!displayedIcons.has(W.exportFullHref(icon.r)) || seenAssets.has(icon.r)) return [];
      seenAssets.add(icon.r);
      return [{ rel: icon.r, category: id }];
    });
    const galleryEntry = { id: row.id, kind: machineView ? "machines" : row.kind, title: row.title };
    gallery.innerHTML = W.gameplay.assetGallery(galleryEntry, { entries: { [`${galleryEntry.kind}:${row.id}`]: { images } } });
    if (["items", "machines"].includes(row.kind)) {
      const token = state.detailToken;
      const storyLink = panel.querySelector("[data-gameplay-items-story-link]");
      const ids = row.kind === "items" ? [row.id] : (row.items || []).map((item) => item.id);
      Promise.all(ids.map((id) => itemStoryLink(id, state.language))).then((links) => {
        if (token === state.detailToken && storyLink.isConnected) {
          storyLink.innerHTML = [...new Set(links)].join("") + detailLinks;
          storyLink.hidden = !storyLink.innerHTML;
          W.gameplayDetail.bindDatasetLinks(storyLink);
        }
      }).catch(() => {});
    }
    if (row.kind === "items") {
      const contents = panel.querySelector("[data-gameplay-item-content]");
      const token = state.detailToken;
      W.gameplay.itemContent(row.id, state.language).then((html) => {
        if (token === state.detailToken && contents.isConnected) contents.innerHTML = html;
      }).catch(() => {
        if (token === state.detailToken && contents.isConnected) contents.innerHTML = `${empty(ui("Gameplay item effects are unavailable in this publication.", "当前数据暂不可读取物品使用效果。"))}<button type="button" data-gameplay-item-retry>${esc(ui("Retry item effects", "重试使用效果"))}</button>`;
      });
    }
    const galleryToken = state.detailToken;
    const musicMedia = row.musicLinks?.length
      ? getJson(`data/lang/${encodeURIComponent(state.language)}/audio/record_media.json`).catch(() => null)
      : Promise.resolve(null);
    Promise.all([
      W.gameplay.itemGallery(row.id, state.language, { entry: row, images, assetKind: machineView ? "machines" : row.kind }).catch(() => ""),
      musicMedia,
    ]).then(([html, payload]) => {
      if (galleryToken !== state.detailToken || !gallery.isConnected) return;
      if (html) gallery.innerHTML = html;
      const players = renderRecordAudio(row, payload);
      if (!players) return;
      const assetsBody = gallery.querySelector(".gameplay-section-body");
      if (assetsBody) assetsBody.insertAdjacentHTML("beforeend", `<div class="gameplay-items-audio-assets">${players}</div>`);
      else gallery.innerHTML = section(ui("Assets", "素材"), `<div class="gameplay-items-audio-assets">${players}</div>`);
    }).catch(() => {});
    $("#gameplay-items-reveal-current").addEventListener("click", revealSelectedInList);

  }

  function renderWikiDescriptions(row) {
    const items = row.kind === "items" ? [row] : row.linkedItems || [];
    const seen = new Set();
    const contents = items.flatMap((item) => item.wikiDescriptions || []).filter((entry) => {
      if (!entry.text || seen.has(entry.text)) return false;
      seen.add(entry.text);
      return true;
    }).map((entry) => `<div class="gameplay-items-description gameplay-items-wiki">${richText(entry.text)}</div>`).join("");
    return section(wikiLabel("ui_wiki_building_usable_func"), contents);
  }

  async function select(id, { write = true } = {}) {
    state.selectedId = id;
    state.detail = null;
    if (write) syncUrl();
    renderList();
    const token = ++state.detailToken;
    const row = state.rows.find((entry) => entryKey(entry) === id);
    if (!row) { $("#gameplay-items-detail").innerHTML = empty(id ? ui("This record is not in the published catalog.", "此记录不在已发布目录中。") : ui("Select a record to explore its connections.", "选择记录以查看关联。")); return; }
    $("#gameplay-items-detail").innerHTML = empty(ui("Loading details…", "正在加载详情…"));
    try {
      const file = path(row.detail);
      if (!state.shards.has(file)) state.shards.set(file, getJson(file).catch((error) => { state.shards.delete(file); throw error; }));
      const shard = await state.shards.get(file);
      if (token !== state.detailToken) return;
      const detail = shard.records?.[row.id];
      if (!detail) throw new Error(ui("The detail shard does not contain this record.", "详情分片不含此记录。"));
      if (["items", "machines"].includes(detail.kind)) {
        const relatedKind = detail.kind === "machines" ? "items" : "machines";
        const relatedIds = detail.kind === "machines" ? (detail.items || []).map((item) => item.catalogId) : detail.buildingIds || [];
        const related = (await Promise.all(relatedIds.map(async (id) => {
          const relatedId = id;
          const summary = state.records[relatedKind]?.get(relatedId);
          if (!summary?.detail) return null;
          const relatedFile = path(summary.detail);
          if (!state.shards.has(relatedFile)) state.shards.set(relatedFile, getJson(relatedFile).catch((error) => { state.shards.delete(relatedFile); throw error; }));
          const relatedShard = await state.shards.get(relatedFile);
          return relatedShard.records?.[relatedId] || null;
        }))).filter(Boolean);
        if (detail.kind === "machines") {
          detail.linkedItems = related;
          detail.itemLore = related.map((item) => item.lore);
        } else detail.linkedMachines = related;
        if (token !== state.detailToken) return;
      }
      // Item pages own complete recipe details, including variants and operating conditions.
      const recipeIds = [...new Set([...(detail.producedBy || []), ...(detail.usedBy || [])].map((ref) => ref.groupId))];
      await Promise.all(recipeIds.map(async (recipeId) => {
        const summary = state.records.recipes.get(recipeId);
        if (!summary?.detail) return;
        const file = path(summary.detail);
        if (!state.shards.has(file)) state.shards.set(file, getJson(file).catch((error) => { state.shards.delete(file); throw error; }));
        const shard = await state.shards.get(file);
        const recipe = shard.records?.[recipeId];
        if (recipe) state.records.recipes.set(recipeId, { ...summary, ...recipe });
      }));
      if (token !== state.detailToken) return;
      state.detail = detail;
      renderDetail(detail);
    } catch (error) {
      if (token === state.detailToken) $("#gameplay-items-detail").innerHTML = `${empty(ui("Details could not be loaded.", "无法加载详情。"))}<p>${esc(error.message)}</p><button type="button" data-gameplay-items-retry-detail>${esc(ui("Retry", "重试"))}</button>`;
    }
  }

  function searchText(row) {
    return [row.id, row.title, row.description, row.typeName, row.showingTypeName,
      ...row.buildings.flatMap((building) => [building.id, building.title, building.description]),
      ...row.buildingCategories.map((category) => `${category.id} ${category.title}`),
      ...(row.aliases || []),
      ...(row.categories || []).map((category) => `${category.id} ${category.title}`),
      ...row.tags.map(tagLabel), ...row.sources.map((source) => `${source.table}.json ${source.row}`),
    ].filter(Boolean).join("\n");
  }

  function itemListGroup(row) {
    const values = typeValue(row);
    const id = Array.isArray(values) ? [...values].sort().join("|") : values;
    return { id, title: id === "other" ? ui("Other", "其它") : row.kind === "machines" ? ui("Buildings", "建筑") : row.typeName || ui("Uncategorized", "未分类") };
  }

  const listGroups = W.listGroups.create();

  function renderList() {
    const host = $("#gameplay-items-list");
    if (!host) return;
    listGroups.render(host, state.filtered, {
      keyOf: (row) => itemListGroup(row).id,
      title: (row) => itemListGroup(row).title,
      icon: (row) => iconHtml(itemListGroup(row).iconId),
      renderRow: (row) => {
      const subtitle = row.kind === "items" ? (row.medalLevelCount ? `${row.typeName} · ${(row.categories || []).map((category) => category.title).join(" · ")} · ${row.medalLevelCount} ${ui("tiers", "个等级")}` : `${row.typeName} · ${ui("Recipe sources", "制作来源")} ${row.counts.producedBy} · ${ui("Uses", "用途")} ${row.counts.usedBy + row.counts.upgrades}`)
        : `${(row.categories || []).map((category) => category.title).join(" · ") || ui("Uncategorized", "未分类")}${row.recipeCount ? ` · ${ui("Recipes", "配方")} ${row.recipeCount}` : ""}`;
      const key = entryKey(row);
      return `<button type="button" class="gameplay-items-row${key === state.selectedId ? " selected" : ""}" data-gameplay-items-select="${esc(key)}" aria-pressed="${key === state.selectedId}">${rowIcon(row, "gameplay-items-icon-list")}<span class="gameplay-items-row-text"><strong>${esc(row.title)} ${W.updateBadges.html("gameplay", key)}</strong><span>${esc(subtitle)}</span><code>${esc(row.id)}</code></span></button>`;
      }, estimateHeight: 90,
    });
    $("#gameplay-items-count").textContent = `${number(state.filtered.length)} / ${number(state.rows.length)}`;
    const locate = $("#gameplay-items-reveal-current");
    if (locate) locate.disabled = !state.selectedId;
  }

  function revealSelectedInList() {
    if (!state.selectedId) return;
    const index = state.filtered.findIndex((row) => entryKey(row) === state.selectedId);
    if (index < 0) return;
    const row = listGroups.locate($("#gameplay-items-list"), state.filtered[index]);
    listGroups.reveal(row);
  }

  function applyFilters(reset = true, write = true) {
    const tokens = W.parseQuery(state.query);
    const scored = state.facets.filter(state.rows).map((row) => ({ row, score: W.queryScore(searchText(row), tokens) }))
      .filter((entry) => !tokens.length || entry.score > 0)
      .map((entry) => ({ ...entry, group: itemListGroup(entry.row) }));
    const compare = W.sorting.comparator("gameplay-items-sort", (a, b) => {
      const title = a.title.localeCompare(b.title, undefined, { numeric: true, sensitivity: "base" }) || a.id.localeCompare(b.id);
      if (state.sort === "title-desc") return -title;
      if (state.sort === "rarity-asc") return (a.rarity - b.rarity) || title;
      if (state.sort === "rarity-desc") return (b.rarity - a.rarity) || title;
      return title;
    });
    scored.sort((a, b) => {
      const categoryA = a.group.id;
      const categoryB = b.group.id;
      if (categoryA !== categoryB) return categoryA === "(none)" ? 1 : categoryB === "(none)" ? -1
        : a.group.title.localeCompare(b.group.title, undefined, { numeric: true });
      return compare(a.row, b.row);
    });
    state.filtered = scored.map((entry) => entry.row);
    if (reset) W.continuousList.reset($("#gameplay-items-list"));
    const nextId = state.filtered.some((row) => entryKey(row) === state.selectedId)
      ? state.selectedId : state.filtered.length ? entryKey(state.filtered[0]) : "";
    if (nextId !== state.selectedId || !state.detail) select(nextId, { write: false });
    else renderList();
    if (write) syncUrl();
  }

  function syncUrl() {
    if (!active()) return;
    const url = new URL(location.href);
    for (const key of [...url.searchParams.keys()]) if (key.startsWith("item")) url.searchParams.delete(key);
    url.searchParams.set("gameplayKind", "item");
    if (state.selectedId) url.searchParams.set("gameplay", state.selectedId); else url.searchParams.delete("gameplay");
    if (state.query) url.searchParams.set("itemQ", state.query);
    if (state.sort !== "title") url.searchParams.set("itemSort", state.sort);
    state.facets.toParams(url.searchParams);
    url.hash = "gameplay";
    history.replaceState(history.state, "", url);
  }

  function readUrl() {
    const params = new URLSearchParams(location.search);
    state.selectedId = params.get("gameplay") || "";
    state.query = params.get("itemQ") || "";
    state.sort = ["title", "title-desc", "rarity-asc", "rarity-desc"].includes(params.get("itemSort")) ? params.get("itemSort") : "title";
    return params;
  }

  function setupCatalogSplitters() {
    state.splitter?.destroy();
    state.splitter = W.setupListShellSplitters({
      shell: $("#gameplay-items-app .gameplay-items-layout"), sidebar: $("#gameplay-items-sidebar"),
      pane: $("#gameplay-items-splitter"), panel: $("#gameplay-items-filters"),
      filter: $("#gameplay-items-filter-splitter"), list: $("#gameplay-items-list"),
      paneStorageKey: "webui_gameplay_splitter_width",
      filterStorageKey: "webui_filter_splitter_height_gameplay", minSidebarWidth: 300,
    });
  }

  function renderShell({ params = null } = {}) {
    if (!state.root || !state.data) return;
    ++state.detailToken;
    state.detail = null;
    const facetState = state.facets?.snapshot();
    state.rows = state.catalogRows;
    singletonTypes.clear();
    const typeCounts = new Map();
    state.rows.forEach((row) => typeCounts.set(rawTypeValue(row), (typeCounts.get(rawTypeValue(row)) || 0) + 1));
    typeCounts.forEach((count, value) => { if (count === 1) singletonTypes.add(value); });
    state.root.innerHTML = `<div class="gameplay-items-layout">
      <aside id="gameplay-items-sidebar" class="gameplay-items-sidebar"><header class="gameplay-sidebar-header">${W.gameplayDetail.sidebarHeader({
        statsHtml: `<span>${number(state.rows.length)} ${esc(ui("entries", "条目"))}</span>`,
        toggleId: "gameplay-items-filter-toggle", panelId: "gameplay-items-filters", resetId: "gameplay-items-reset", resetLabel: ui("Reset filters", "重置筛选"),
      })}</header>
      <div id="gameplay-items-filters" class="filters">
      <section class="filter-section filter-section-basic" data-filter-section="gameplay-items-basic" data-fixed-open="1">
        <span class="filter-section-title">${esc(ui("Basic filters", "基础筛选"))}</span>
        <div class="filter-section-body filter-section-body-stack">
          <input id="gameplay-items-search" type="search" value="${esc(state.query)}" aria-label="${esc(ui("Search names, IDs, ingredients or files", "搜索名称、标识符、原料或文件"))}" placeholder="${esc(ui("Search names, IDs, ingredients or files", "搜索名称、标识符、原料或文件"))}">
          <div class="filter-control-row"><label for="gameplay-items-sort">${esc(ui("Sort", "排序"))}</label><select id="gameplay-items-sort"><option value="title">${esc(ui("Name (A-Z)", "名称 (A-Z)"))}</option><option value="title-desc">${esc(ui("Name descending", "名称降序"))}</option><option value="rarity-asc">${esc(ui("Rarity ascending", "稀有度升序"))}</option><option value="rarity-desc">${esc(ui("Rarity descending", "稀有度降序"))}</option></select></div>
        </div>
      </section>
      ${W.filters.sectionMarkup({ key: "gameplay-items-type", label: ui("Types", "类型"), container: "gameplay-items-type-filter" })}
      ${W.filters.sectionMarkup({ key: "gameplay-items-category", label: ui("Medal categories", "蚀刻章分类"), container: "gameplay-items-category-filter" })}
      ${W.filters.sectionMarkup({ key: "gameplay-items-building", label: ui("Building categories", "建筑分类"), container: "gameplay-items-building-filter" })}
      ${W.filters.sectionMarkup({ key: "gameplay-items-tag", label: ui("Relationships", "关联"), container: "gameplay-items-tag-filter" })}
      ${W.updateBadges.filterSection("gameplay-items")}
      </div>
      <div id="gameplay-items-filter-splitter" class="filter-splitter" role="separator" aria-label="${esc(ui("Resize filters", "调整筛选区高度"))}" aria-orientation="horizontal" tabindex="0"></div>
      <div class="gameplay-items-list-heading"><span id="gameplay-items-count" aria-live="polite"></span> ${esc(ui("entries", "条目"))}</div><div id="gameplay-items-list"></div></aside>
      <div id="gameplay-items-splitter" class="pane-splitter" role="separator" aria-label="${esc(ui("Resize gameplay sidebar", "调整玩法侧栏宽度"))}" aria-orientation="vertical" tabindex="0"></div>
      <main class="gameplay-items-main">
      ${state.language !== state.requestedLanguage ? `<p class="gameplay-items-note">${esc(ui(`This catalog has no ${state.requestedLanguage} publication; showing ${state.language}.`, `此目录没有 ${state.requestedLanguage} 数据，当前显示 ${state.language}。`))}</p>` : ""}
      <div id="gameplay-items-detail" aria-live="polite"></div><details class="gameplay-items-technical gameplay-items-audit"><summary>${esc(ui("Coverage and unresolved references", "覆盖范围与待解析引用"))}</summary><p>${esc(ui("Upgrade coverage: weapon breakthrough and experience, equipment enhancement, manual-upgrade mappings, formula items and shop currencies. Other item sources and uses may exist.", "升级用途覆盖武器突破与经验、装备强化、手动升级映射、配方物品及商店货币；物品还可能有其他来源和用途。"))}</p>
      <p>${esc(ui("Unresolved source references", "待解析来源引用"))}: ${number(state.data.unresolvedReferences.length)}</p><ul>${state.data.unresolvedReferences.map((row) => `<li>${esc(row.table)} · <code>${esc(row.row)}.${esc(row.field)} → ${esc(row.target || ui("empty", "空值"))}</code></li>`).join("")}</ul></details></main></div>`;
    $("#gameplay-items-sort").value = state.sort;
    W.sorting.refresh();
    state.facets = W.facets.create({
      countMode: "total", groups: [
        W.updateBadges.filterGroup("gameplay-items", (row) => W.updateBadges.status("gameplay", `${row.kind}:${row.id}`), { param: "itemUpdate" }),
        { id: "type", container: "#gameplay-items-type-filter", section: "gameplay-items-type", param: "itemType",
          values: typeValue, label: (value) => value === "other" ? ui("Other", "其它") : value === "building" ? ui("Buildings", "建筑") : state.rows.find((row) => typeValue(row) === value)?.typeName || value },
        { id: "category", container: "#gameplay-items-category-filter", section: "gameplay-items-category", param: "itemCategory",
          values: (row) => row.kind === "items" ? (row.categories || []).map((category) => category.id) : [], label: categoryLabel, icon: categoryIcon },
        { id: "building", container: "#gameplay-items-building-filter", section: "gameplay-items-building", param: "itemBuilding",
          values: buildingValues, label: buildingLabel, icon: buildingIcon },
        { id: "tag", container: "#gameplay-items-tag-filter", section: "gameplay-items-tag", param: "itemTag", values: (row) => row.tags, label: tagLabel },
      ], onChange: () => applyFilters(),
    });
    if (params) state.facets.fromParams(params, { silent: true });
    else if (facetState) state.facets.restore(facetState, { silent: true });
    W.updateBadges.syncFilter("gameplay-items", "gameplay", state.facets);
    W.filters.bindSections(state.root);
    state.facets.render(state.rows);
    setupCatalogSplitters();
    W.filters.createPanelToggle({ panel: "#gameplay-items-filters", toggle: "#gameplay-items-filter-toggle", left: ".gameplay-items-sidebar",
      storageKey: "webui_gameplay_items_filters_collapsed", labels: (collapsed) => collapsed ? ui("Show filters", "显示筛选") : ui("Hide filters", "隐藏筛选") });
    $("#gameplay-items-search").addEventListener("input", (event) => { state.query = event.target.value; applyFilters(); });
    $("#gameplay-items-sort").addEventListener("change", (event) => { state.sort = event.target.value; applyFilters(); });
    $("#gameplay-items-reset").addEventListener("click", () => {
      state.query = ""; state.sort = "title"; $("#gameplay-items-search").value = ""; $("#gameplay-items-sort").value = "title";
      state.facets.reset({ silent: true }); state.facets.render(state.rows); W.sorting.refresh(); applyFilters();
    });
    applyFilters(true, false);
    renderList();
    syncUrl();
    W.gameplayTabs?.render();
  }

  async function getJson(url) {
    const response = await W.fetchWithProgress(url, { cache: "no-cache" });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}: ${url}`);
    return response.json();
  }

  async function load(language = currentLanguage(), force = false, { render = true } = {}) {
    if (!state.root) init();
    if (!state.root) return null;
    const requested = String(language || "CN").toUpperCase();
    if (!force && state.loading && requested === state.requestedLanguage) return state.loading;
    if (!force && state.data && requested === state.requestedLanguage) {
      if (render) renderShell({ params: readUrl() });
      return state.data;
    }
    const token = ++state.loadToken;
    ++state.detailToken;
    state.requestedLanguage = requested;
    state.data = null;
    state.root.innerHTML = empty(ui("Loading catalog…", "正在加载目录…"));
    const pending = (async () => {
      try {
        const manifest = await getJson("data/gameplay/items/manifest.json");
        if (manifest.schema !== "endfield.gameplay-items.v1") throw new Error(ui("Unsupported item manifest; rebuild Gameplay data.", "物品清单格式不匹配，请重新构建玩法数据。"));
        const chosen = manifest.languages.includes(requested) ? requested : manifest.defaultLanguage;
        const [data, images] = await Promise.all([getJson(`data/lang/${encodeURIComponent(chosen)}/gameplay/items/index.json`), W.gameplay.itemImages(chosen), W.updateBadges.load("gameplay")]);
        if (token !== state.loadToken) return null;
        if (data.schema !== "endfield.gameplay-items.v1") throw new Error(ui("Unsupported item catalog; rebuild Gameplay data.", "物品目录格式不匹配，请重新构建玩法数据。"));
        state.data = data; state.itemImages = images; state.language = chosen; state.shards.clear(); state.detail = null;
        state.catalogRows = combinedItems(data);
        state.records = Object.fromEntries(kinds.map((kind) => [kind, new Map(data[kind].map((row) => [row.id, row]))]));
        if (render && active()) renderShell({ params: readUrl() });
        W.gameplayTabs?.render();
        return data;
      } catch (error) {
        if (token !== state.loadToken) return null;
        state.data = null;
        state.root.innerHTML = `${empty(ui("This catalog could not be loaded.", "无法加载此目录。"))}<p class="gameplay-items-error">${esc(error.message)}</p><button type="button" data-gameplay-items-retry>${esc(ui("Retry", "重试"))}</button>`;
        W.gameplayTabs?.render();
        return null;
      } finally { if (token === state.loadToken) state.loading = null; }
    })();
    state.loading = pending;
    return pending;
  }

  function open(kind, id = "") {
    if (!kinds.includes(kind)) return;
    const selection = itemSelection(kind, id);
    if (!selection) return;
    history.pushState(history.state, "", pageUrl(kind, id));
    if (!active()) W.setActiveView("gameplay");
    else window.dispatchEvent(new PopStateEvent("popstate"));
  }

  function init() {
    state.root = $("#gameplay-items-app");
    if (!state.root || state.root.dataset.gameplayItemsBound) return;
    state.root.dataset.gameplayItemsBound = "1";
    state.root.addEventListener("click", (event) => {
      const link = event.target.closest("[data-gameplay-items-kind]");
      if (link && W.isPlainClick(event)) { event.preventDefault(); open(link.dataset.gameplayItemsKind, link.dataset.gameplayItemsId); return; }
      const reward = event.target.closest("[data-gameplay-related-key]");
      if (reward) { const [kind, ...id] = reward.dataset.gameplayRelatedKey.split(":"); W.gameplayTabs.open(kind, id.join(":")); return; }
      const selection = event.target.closest("[data-gameplay-items-select]");
      if (selection) { select(selection.dataset.gameplayItemsSelect); return; }
      if (event.target.closest("[data-gameplay-items-retry]")) load(currentLanguage(), true);
      if (event.target.closest("[data-gameplay-items-retry-detail]")) select(state.selectedId);
      if (event.target.closest("[data-gameplay-item-retry]") && state.detail) renderDetail(state.detail);
    });
  }

  W.gameplayItems = { hasItem: (id, language) => !!state.data && state.language === language && !!state.records.items?.has(id), init, load, open, pageUrl, renderCraftingRecipe: (recipe, renderItem) => renderMachineRecipe(recipe, false, { renderItem, formulaOnly: true }), count: () => state.data && state.requestedLanguage === currentLanguage() ? state.catalogRows.length : null };
  window.addEventListener("webui:ui-locale-changed", () => { if (active() && state.data) renderShell(); });
  window.addEventListener("webui:inline-tag-mode-changed", () => { if (state.detail) renderDetail(state.detail); });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true }); else init();
})();
