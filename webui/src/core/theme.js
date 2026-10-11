// Applies the saved colour theme before first paint (loaded synchronously in
// <head>) and binds the topbar #theme select once the DOM exists. Themes are
// CSS token sets in webui/themes.css. Endfield is the default; unsupported
// saved preferences (including the retired Classic theme) fall back to it.
(function () {
  "use strict";
  var KEY = "webui.theme";
  var THEMES = ["endfield", "talos"];
  var DEFAULT_THEME = "endfield";

  function read() {
    try {
      var value = window.localStorage.getItem(KEY);
      return THEMES.indexOf(value) >= 0 ? value : DEFAULT_THEME;
    } catch (_) {
      return DEFAULT_THEME;
    }
  }

  function apply(theme) {
    var root = document.documentElement;
    root.setAttribute("data-theme", theme);
  }

  apply(read());

  document.addEventListener("DOMContentLoaded", function () {
    var select = document.getElementById("theme");
    if (!select) return;
    select.value = read();
    select.addEventListener("change", function () {
      var theme = THEMES.indexOf(select.value) >= 0 ? select.value : DEFAULT_THEME;
      apply(theme);
      try { window.localStorage.setItem(KEY, theme); } catch (_) { /* private mode */ }
    });
  });
})();
