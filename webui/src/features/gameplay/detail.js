// Shared presentation for all Gameplay datasets; data and interaction stay with their owners.
(() => {
  const W = window.WebUI;
  const esc = W.escapeHtml;
  function knownQuantity(value, unavailable = false) {
    return !unavailable && (typeof value === 'number' || typeof value === 'string')
      && String(value).trim() !== '' && Number.isFinite(Number(value)) && Number(value) >= 0;
  }
  function metadata(fields) {
    return (fields || []).filter((field) => field != null && field !== "").map((field) =>
      typeof field === "string" ? field : `${field.label}=${field.value}`).join(" | ");
  }
  function image(asset, href = W.exportFullHref) {
    return asset?.rel ? `<img class="gameplay-heading-image" src="${esc(href(asset.rel))}" alt="" loading="lazy" decoding="async">` : "";
  }
  function identity({ imageHtml = "", titleHtml = "", subtitleHtml = "", metadataHtml = "" }) {
    return `<div class="gameplay-heading-identity">${imageHtml ? `<div class="gameplay-heading-picture">${imageHtml}</div>` : ""}<div class="gameplay-heading-content">${subtitleHtml}<h2 class="gameplay-heading-title">${titleHtml}</h2>${metadataHtml}</div></div>`;
  }
  // Preserve existing nodes/IDs and their event bindings when applying the shared shell.
  function mount(header, main, title, meta, imageHtml = "") {
    header.classList.add("gameplay-detail-heading");
    header.querySelector("button")?.classList.add("locate-current-button");
    main.querySelector("#gameplay-detail-wiki")?.classList.add("gameplay-heading-links");
    main.classList.add("gameplay-heading-identity");
    title.classList.add("gameplay-heading-title");
    meta.classList.add("gameplay-heading-meta");
    let content = main.querySelector(":scope > .gameplay-heading-content");
    if (!content) {
      content = document.createElement("div");
      content.className = "gameplay-heading-content";
      content.append(...main.childNodes);
      main.append(content);
    }
    main.querySelector(":scope > .gameplay-heading-picture")?.remove();
    if (imageHtml) {
      const picture = document.createElement("div");
      picture.className = "gameplay-heading-picture";
      picture.innerHTML = imageHtml;
      main.prepend(picture);
    }
  }
  function sidebarHeader({ statsHtml, toggleId, panelId, resetId, resetLabel = "Reset filters" }) {
    return `<div class="gameplay-sidebar-stats">${statsHtml}</div><div class="sidebar-header-actions"><button id="${esc(toggleId)}" class="panel-toggle" type="button" aria-controls="${esc(panelId)}" aria-expanded="true"></button><button id="${esc(resetId)}" type="button">${esc(resetLabel)}</button></div>`;
  }
  function propertyCard({ title, bodyHtml, metaHtml = "", className = "" }) {
    return `<article class="gameplay-skill-card ${esc(className)}"><header><div class="gameplay-skill-title">${esc(title)}</div>${metaHtml}</header>${bodyHtml}</article>`;
  }
  function propertyGrid(cards) {
    return cards.length ? `<div class="gameplay-equipment-property-grid">${cards.join("")}</div>` : "";
  }
  function section(title, bodyHtml, { id = "", anchorLabel = "", className = "", count = null, focusable = false } = {}) {
    if (!bodyHtml || count === 0) return "";
    const anchor = id ? ` id="${esc(id)}" data-gameplay-section="${esc(anchorLabel || title)}"${focusable ? ' tabindex="-1"' : ""}` : "";
    return `<section class="gameplay-section ${esc(className)}"${anchor}><h3 class="gameplay-section-title">${esc(title)}${count != null ? ` <span>(${esc(W.formatNumber(count))})</span>` : ""}</h3><div class="gameplay-section-body">${bodyHtml}</div></section>`;
  }
  function storyWikiLink(href, label) {
    return `<a class="gameplay-detail-tag gameplay-detail-wiki-link gameplay-wiki-link" href="${esc(href)}"><span>${esc(label)}</span></a>`;
  }
  function datasetLink(kind, id, label) {
    return `<a class="gameplay-detail-tag gameplay-detail-wiki-link gameplay-wiki-link" href="${esc(W.gameplayTabs.pageUrl(kind, id))}" data-gameplay-dataset="${esc(kind)}" data-gameplay-record="${esc(id)}"><span>${esc(label)}</span></a>`;
  }
  function relatedLink(label, { href = '', iconHtml = '', kind = '', id = '', relatedKey = '' } = {}) {
    const content = `${iconHtml}<span>${esc(label)}</span>`;
    const classes = 'gameplay-value-chip gameplay-item-chip gameplay-related-link';
    if (relatedKey) return `<button type="button" class="${classes}" data-gameplay-related-key="${esc(relatedKey)}">${content}</button>`;
    const dataset = kind ? ` data-gameplay-dataset="${esc(kind)}" data-gameplay-record="${esc(id)}"` : '';
    return `<a class="${classes}" href="${esc(kind ? W.gameplayTabs.pageUrl(kind, id) : href)}"${dataset}>${content}</a>`;
  }
  function bindDatasetLinks(root) {
    root.querySelectorAll("[data-gameplay-dataset]").forEach((link) => link.addEventListener("click", (event) => {
      if (!W.isPlainClick(event)) return;
      event.preventDefault();
      W.gameplayTabs.open(link.dataset.gameplayDataset, link.dataset.gameplayRecord);
    }));
  }
  W.gameplayDetail = { knownQuantity, metadata, image, identity, mount, sidebarHeader, propertyCard, propertyGrid, section, storyWikiLink, datasetLink, relatedLink, bindDatasetLinks };
})();
