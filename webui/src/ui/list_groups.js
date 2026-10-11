// Collapsible list groups shared by the Gameplay lists.
// Each page keeps its own collapsed-group set (owned by the returned
// controller), renders groups as <details data-list-group>, and reopens a
// collapsed group before scrolling a selected row into view.
//
//   const groups = WebUI.listGroups.create();
//   host.innerHTML = groups.section({ id, title, count, icon, className, body });
//   groups.bind(host);           // remember user collapse/expand per group id
//   groups.reveal(row);          // open the row's group, then scroll to it
//   WebUI.listGroups.counts(rows, (row) => key)  // Map key -> row count, one pass
(() => {
  const WebUI = window.WebUI;
  const esc = (value) => WebUI.escapeHtml(value);

  function counts(rows, keyOf) {
    const result = new Map();
    for (const row of rows) {
      const key = keyOf(row);
      result.set(key, (result.get(key) || 0) + 1);
    }
    return result;
  }

  function create() {
    const collapsed = new Set();
    const views = new WeakMap();
    const headings = new Map();
    function render(host, entries, { keyOf, title, icon = () => '', renderRow, estimateHeight = 80 }) {
      const options = { keyOf, title, icon, renderRow, estimateHeight };
      views.set(host, { entries, options });
      const groups = new Map();
      for (const entry of entries) {
        const id = keyOf(entry);
        if (!groups.has(id)) groups.set(id, []);
        groups.get(id).push(entry);
      }
      const rows = [];
      for (const [id, items] of groups) {
        if (!headings.has(id)) headings.set(id, { heading: true, id });
        rows.push(headings.get(id));
        if (!collapsed.has(id)) rows.push(...items);
      }
      WebUI.continuousList.render(host, rows, (row) => {
        if (!row.heading) return renderRow(row);
        const items = groups.get(row.id);
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'list-group-summary continuous-list-group';
        button.setAttribute('aria-expanded', String(!collapsed.has(row.id)));
        button.innerHTML = `${icon(items[0])}<strong>${esc(title(items[0]))}</strong><span>${WebUI.formatNumber(items.length)}</span>`;
        button.addEventListener('click', () => {
          if (collapsed.has(row.id)) collapsed.delete(row.id); else collapsed.add(row.id);
          render(host, entries, options);
          WebUI.continuousList.reveal(host, row)?.querySelector('button')?.focus({ preventScroll: true });
        });
        return button;
      }, { estimateHeight: (row) => row.heading ? 40 : estimateHeight });
    }
    function locate(host, entry) {
      const view = views.get(host);
      if (!view || !view.entries.includes(entry)) return null;
      if (collapsed.delete(view.options.keyOf(entry))) render(host, view.entries, view.options);
      return WebUI.continuousList.reveal(host, entry)?.querySelector('button') || null;
    }
    // Opening markup only when `body` is omitted, so a caller that streams rows
    // can close the group itself with "</details>".
    function section({ id, title, count, icon = "", className = "", body }) {
      const open = `<details class="list-group-section${className ? ` ${className}` : ""}" data-list-group="${esc(id)}"${collapsed.has(id) ? "" : " open"}>`
        + `<summary class="list-group-summary">${icon}<strong>${esc(title)}</strong><span>${WebUI.formatNumber(count)}</span></summary>`;
      return body === undefined ? open : `${open}${body}</details>`;
    }
    function bind(host) {
      host.querySelectorAll("[data-list-group]").forEach((group) => {
        group.addEventListener("toggle", () => {
          if (group.open) collapsed.delete(group.dataset.listGroup);
          else collapsed.add(group.dataset.listGroup);
        });
      });
    }
    function reveal(row) {
      const group = row?.closest("[data-list-group]");
      if (group) { collapsed.delete(group.dataset.listGroup); group.open = true; }
      row?.scrollIntoView({ block: "center", behavior: "smooth" });
    }
    return { section, bind, reveal, render, locate };
  }

  WebUI.listGroups = { create, counts };
})();
