// Shared "Locate current file" button for list + detail pages.
//   WebUI.locateCurrent.label()               // bilingual button text
//   WebUI.locateCurrent.bind(button, locate)  // click -> locate(); locate returns the row
//   WebUI.locateCurrent.sync(button, enabled) // disabled while nothing is selected
//   WebUI.locateCurrent.reveal(row, leftPane) // open the row's group, scroll to it
// Virtual lists mount and scroll to the selected row before returning it.
(() => {
  const WebUI = window.WebUI = window.WebUI || {};
  const MOBILE_LAYOUT_QUERY = "(max-width: 760px)";

  function label() {
    const zh = String(window.WEBUI_UI_LOCALE || document.documentElement.lang || "zh")
      .toLowerCase().startsWith("zh");
    return zh ? "定位当前文件" : "Locate current file";
  }

  function reveal(row, leftPane) {
    if (!row) return false;
    const group = row.closest("details[data-list-group], details");
    if (group && !group.open) group.open = true;
    row.scrollIntoView({ block: "center", behavior: "smooth" });
    if (leftPane && window.matchMedia(MOBILE_LAYOUT_QUERY).matches) {
      leftPane.scrollIntoView({ block: "start", behavior: "smooth" });
    }
    return true;
  }

  function sync(button, enabled) {
    if (!button) return;
    button.disabled = !enabled;
    button.textContent = label();
  }

  function bind(button, locate, leftPane) {
    if (!button || button.dataset.locateBound) return;
    button.dataset.locateBound = "1";
    button.textContent = label();
    button.addEventListener("click", () => {
      const row = locate();
      if (row) reveal(row, typeof leftPane === "function" ? leftPane() : leftPane);
    });
  }

  window.addEventListener("webui:ui-locale-changed", () => {
    for (const button of document.querySelectorAll(".locate-current-button")) button.textContent = label();
  });

  WebUI.locateCurrent = { label, reveal, sync, bind };
})();
