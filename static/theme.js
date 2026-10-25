/* theme.js — light / dark toggle, runs on every page */
(function () {
  var STORAGE_KEY = 'yv_theme';
  var DARK  = 'dark';
  var LIGHT = 'light';

  /* ── 1. Apply saved theme immediately (before paint) ── */
  var saved = localStorage.getItem(STORAGE_KEY) || LIGHT;
  document.documentElement.setAttribute('data-theme', saved);

  /* ── 2. Inject toggle button once DOM is ready ── */
  function injectButton() {
    if (document.getElementById('theme-toggle')) return;

    var btn = document.createElement('button');
    btn.id = 'theme-toggle';
    btn.setAttribute('aria-label', 'Temani almashtirish');
    btn.setAttribute('title', 'Temani almashtirish');
    btn.innerHTML = getIcon(saved);

    btn.addEventListener('click', function () {
      var current = document.documentElement.getAttribute('data-theme') || LIGHT;
      var next    = current === DARK ? LIGHT : DARK;
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem(STORAGE_KEY, next);
      btn.innerHTML = getIcon(next);
    });

    document.body.appendChild(btn);
  }

  function getIcon(theme) {
    return theme === DARK
      ? '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>'
      : '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectButton);
  } else {
    injectButton();
  }
})();
