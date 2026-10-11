// Continuous, variable-height sidebar lists. Only the viewport and overscan
// have DOM rows; measured heights survive selection and locale refreshes.
(() => {
  const W = window.WebUI;
  const lists = new WeakMap();
  const OVERSCAN = 600;

  function create(host) {
    const state = { rows: [], heights: new Map(), tops: [0], start: -1, end: -1, frame: 0 };
    host.classList.add('continuous-list');
    const top = document.createElement('div'), body = document.createElement('div'), bottom = document.createElement('div');
    top.className = bottom.className = 'continuous-list-spacer';
    top.setAttribute('aria-hidden', 'true'); bottom.setAttribute('aria-hidden', 'true');
    body.className = 'continuous-list-body';
    host.replaceChildren(top, body, bottom);
    const key = (row) => state.keyOf ? state.keyOf(row) : row;
    function offsets() {
      state.tops = [0];
      for (const row of state.rows) state.tops.push(state.tops.at(-1) + (state.heights.get(key(row)) ?? state.estimate(row)));
    }
    function indexAt(y) {
      let lo = 0, hi = state.rows.length;
      while (lo < hi) {
        const mid = (lo + hi) >>> 1;
        if (state.tops[mid + 1] <= y) lo = mid + 1;
        else hi = mid;
      }
      return lo;
    }
    function scale() {
      const height = state.tops.at(-1), viewport = host.clientHeight || 600;
      return height > 8000000 ? (height - viewport) / (8000000 - viewport) : 1;
    }
    function spacers() {
      const logicalTop = host.scrollTop * scale();
      const leading = Math.max(0, host.scrollTop + (state.tops[state.start] || 0) - logicalTop);
      top.style.height = `${leading}px`;
      const mountedHeight = (state.tops[state.end] || 0) - (state.tops[state.start] || 0);
      bottom.style.height = `${Math.max(0, Math.min(8000000, state.tops.at(-1)) - leading - mountedHeight)}px`;
    }
    const schedule = () => {
      if (state.frame) return;
      state.frame = requestAnimationFrame(() => { state.frame = 0; draw(); });
    };
    const measure = new ResizeObserver((entries) => {
      let changed = false;
      const anchor = indexAt(host.scrollTop * scale());
      const within = host.scrollTop * scale() - (state.tops[anchor] || 0);
      for (const entry of entries) {
        const index = Number(entry.target.dataset.continuousIndex);
        if (!entry.target.isConnected || index >= state.rows.length) continue;
        const height = entry.target.getBoundingClientRect().height;
        if (height > 0 && Math.abs(height - (state.heights.get(key(state.rows[index])) ?? state.estimate(state.rows[index]))) > .5) {
          state.heights.set(key(state.rows[index]), height);
          entry.target.parentElement.style.height = `${height}px`;
          changed = true;
        }
      }
      if (!changed) return;
      offsets();
      spacers();
      host.scrollTop = ((state.tops[anchor] || 0) + within) / scale();
      spacers();
      schedule();
    });
    function draw(force = false) {
      const logicalTop = host.scrollTop * scale();
      const start = indexAt(Math.max(0, logicalTop - OVERSCAN));
      const end = Math.min(state.rows.length, indexAt(logicalTop + (host.clientHeight || 600) + OVERSCAN) + 1);
      if (!force && start === state.start && end === state.end) { spacers(); return; }
      const focused = body.contains(document.activeElement) ? Number(document.activeElement.closest('[data-continuous-index]')?.dataset.continuousIndex) : -1;
      state.start = start; state.end = end;
      measure.disconnect();
      const fragment = document.createDocumentFragment();
      for (let index = start; index < end; index++) {
        const wrapper = document.createElement('div');
        wrapper.className = 'continuous-list-item';
        wrapper.dataset.continuousIndex = String(index);
        wrapper.style.height = `${state.heights.get(key(state.rows[index])) ?? state.estimate(state.rows[index])}px`;
        const contentHost = document.createElement('div');
        contentHost.className = 'continuous-list-content';
        contentHost.dataset.continuousIndex = String(index);
        const content = state.renderRow(state.rows[index], index);
        if (typeof content === 'string') contentHost.innerHTML = content;
        else if (content) contentHost.append(content);
        wrapper.append(contentHost);
        fragment.append(wrapper);
      }
      body.replaceChildren(fragment);
      if (!state.rows.length) body.textContent = window.WEBUI_UI_LOCALE === 'en' ? 'No matching items.' : '没有匹配的项目。';
      spacers();
      for (const child of body.children) measure.observe(child.firstElementChild);
      if (focused >= start && focused < end) body.querySelector(`[data-continuous-index="${focused}"] button`)?.focus({ preventScroll: true });
    }
    host.addEventListener('scroll', schedule, { passive: true });
    const resize = new ResizeObserver(schedule);
    resize.observe(host);
    const keyboard = (event) => {
      const current = event.target.closest('[data-continuous-index]');
      if (!current || !['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
      const index = event.key === 'Home' ? 0 : event.key === 'End' ? state.rows.length - 1
        : Number(current.dataset.continuousIndex) + (event.key === 'ArrowDown' ? 1 : -1);
      if (index < 0 || index >= state.rows.length) return;
      event.preventDefault(); reveal(index)?.querySelector('button')?.focus({ preventScroll: true });
    };
    host.addEventListener('keydown', keyboard);
    function reveal(index) {
      if (index < 0 || index >= state.rows.length) return null;
      const height = state.tops[index + 1] - state.tops[index];
      host.scrollTop = Math.max(0, (state.tops[index] + height / 2 - host.clientHeight / 2) / scale());
      draw(true);
      return body.querySelector(`[data-continuous-index="${index}"]`);
    }
    return {
      update(rows, renderRow, { estimateHeight = 80, keyOf } = {}) {
        const nextKey = (row) => keyOf ? keyOf(row) : row;
        const same = rows.length === state.rows.length && rows.every((row, index) => nextKey(row) === key(state.rows[index]));
        state.rows = rows; state.renderRow = renderRow; state.keyOf = keyOf;
        state.estimate = typeof estimateHeight === 'function' ? estimateHeight : () => estimateHeight;
        if (!same) {
          state.heights.clear(); host.scrollTop = 0;
        }
        offsets(); draw(true);
      }, reveal,
      find(row) { return state.rows.findIndex((candidate) => key(candidate) === key(row)); },
      destroy() {
        measure.disconnect(); resize.disconnect(); cancelAnimationFrame(state.frame);
        host.removeEventListener('scroll', schedule); host.removeEventListener('keydown', keyboard);
      },
    };
  }
  W.continuousList = {
    render(host, rows, renderRow, options) {
      if (!host) return;
      let list = lists.get(host);
      if (!list || !host.querySelector(':scope > .continuous-list-body')) {
        list?.destroy();
        list = create(host); lists.set(host, list);
      }
      list.update(rows, renderRow, options);
    },
    reveal(host, row) {
      const list = lists.get(host);
      return list?.reveal(list.find(row)) || null;
    },
    reset(host) { if (host) host.scrollTop = 0; },
  };
})();
