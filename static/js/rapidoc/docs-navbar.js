(function () {
  var THEME_KEY = 'app-theme';
  var LOCALE_COOKIE = 'cf_locale';
  var BEARER_SCHEME = 'jwtAuth';
  var SORT_TAGS_KEY = 'api-docs-sort-tags';

  var doc = document.getElementById('rapidoc');
  var navbar = document.getElementById('docs-navbar');
  var media = window.matchMedia('(prefers-color-scheme: dark)');

  function readTheme() {
    try {
      var saved = localStorage.getItem(THEME_KEY);
      if (saved === 'light' || saved === 'dark' || saved === 'system') return saved;
    } catch (e) {}
    return 'system';
  }

  var themePreference = readTheme();

  function applyTheme() {
    var scheme = themePreference === 'system' ? (media.matches ? 'dark' : 'light') : themePreference;
    doc.setAttribute('color-scheme', scheme);
    document.documentElement.classList.toggle('dark', scheme === 'dark');
    document.getElementById('docs-theme-icon').setAttribute('href', scheme === 'dark' ? '#icon-moon' : '#icon-sun');
    navbar.querySelectorAll('[data-theme-value]').forEach(function (item) {
      item.setAttribute('aria-checked', String(item.dataset.themeValue === themePreference));
    });
  }

  function setTheme(preference) {
    themePreference = preference;
    try {
      localStorage.setItem(THEME_KEY, preference);
    } catch (e) {}
    applyTheme();
  }

  applyTheme();
  media.addEventListener('change', function () {
    if (themePreference === 'system') applyTheme();
  });

  function closeDropdown(dropdown, restoreFocus) {
    var trigger = dropdown.querySelector('[data-dropdown-trigger]');
    var panel = dropdown.querySelector('[data-dropdown-panel]');
    if (panel.hidden) return;
    panel.hidden = true;
    trigger.setAttribute('aria-expanded', 'false');
    if (restoreFocus) trigger.focus();
  }

  function closeAll(except) {
    navbar.querySelectorAll('[data-dropdown]').forEach(function (dropdown) {
      if (dropdown !== except) closeDropdown(dropdown, false);
    });
  }

  navbar.querySelectorAll('[data-dropdown]').forEach(function (dropdown) {
    var trigger = dropdown.querySelector('[data-dropdown-trigger]');
    var panel = dropdown.querySelector('[data-dropdown-panel]');
    trigger.addEventListener('click', function () {
      var opening = panel.hidden;
      closeAll(dropdown);
      panel.hidden = !opening;
      trigger.setAttribute('aria-expanded', String(opening));
      if (opening) {
        var target = panel.querySelector('[aria-checked="true"], input, button');
        if (target) target.focus();
      }
    });
    dropdown.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        closeDropdown(dropdown, true);
        return;
      }
      if (panel.getAttribute('role') !== 'menu' || (event.key !== 'ArrowDown' && event.key !== 'ArrowUp')) return;
      var items = Array.prototype.slice.call(panel.querySelectorAll('[role="menuitemradio"]'));
      var index = items.indexOf(document.activeElement);
      var next = event.key === 'ArrowDown' ? index + 1 : index - 1;
      items[(next + items.length) % items.length].focus();
      event.preventDefault();
    });
  });

  document.addEventListener('click', function (event) {
    if (!event.composedPath().some(function (node) { return node.dataset && 'dropdown' in node.dataset; })) closeAll(null);
  });

  navbar.querySelectorAll('[data-theme-value]').forEach(function (item) {
    item.addEventListener('click', function () {
      setTheme(item.dataset.themeValue);
      closeDropdown(item.closest('[data-dropdown]'), true);
    });
  });

  navbar.querySelectorAll('[data-locale]').forEach(function (item) {
    item.addEventListener('click', function () {
      document.cookie = LOCALE_COOKIE + '=' + item.dataset.locale + '; Max-Age=31536000; Path=/; SameSite=Lax' +
        (window.location.protocol === 'https:' ? '; Secure' : '');
      var url = new URL(window.location.href);
      url.searchParams.delete('lang');
      if (url.toString() === window.location.href) {
        window.location.reload();
      } else {
        window.location.assign(url.toString());
      }
    });
  });

  var serverSelect = document.getElementById('docs-server');

  function renderServers(spec) {
    var servers = (spec && spec.servers) || [];
    var selected = doc.selectedServer && doc.selectedServer.url;
    serverSelect.textContent = '';
    servers.forEach(function (server) {
      var option = document.createElement('option');
      option.value = server.url;
      option.textContent = server.computedUrl || server.url;
      option.selected = server.url === selected;
      serverSelect.appendChild(option);
    });
    serverSelect.disabled = servers.length < 2;
  }

  var selectedServerUrl = '';
  var appliedToken = '';

  serverSelect.addEventListener('change', function () {
    selectedServerUrl = serverSelect.value;
    doc.setApiServer(selectedServerUrl);
  });
  doc.addEventListener('spec-loaded', function (event) {
    if (selectedServerUrl) doc.setApiServer(selectedServerUrl);
    renderServers(event.detail);
    setAuthenticated(Boolean(appliedToken) && doc.setApiKey(BEARER_SCHEME, appliedToken));
  });

  function readSortTags() {
    try {
      var saved = localStorage.getItem(SORT_TAGS_KEY);
      if (saved === 'true' || saved === 'false') return saved;
    } catch (e) {}
    return navbar.dataset.sortTagsDefault;
  }

  var sortTagsButton = document.getElementById('docs-sort-tags');
  var sortTags = readSortTags();

  function applySortTags() {
    doc.setAttribute('sort-tags', sortTags);
    sortTagsButton.setAttribute('aria-pressed', sortTags);
  }

  applySortTags();
  sortTagsButton.addEventListener('click', function () {
    sortTags = sortTags === 'true' ? 'false' : 'true';
    try {
      localStorage.setItem(SORT_TAGS_KEY, sortTags);
    } catch (e) {}
    applySortTags();
    doc.loadSpec(doc.getAttribute('spec-url'));
  });

  var status = document.getElementById('docs-auth-status');
  var logout = document.getElementById('docs-logout');
  var loginForm = document.getElementById('docs-login-form');
  var loginError = document.getElementById('docs-login-error');
  var tokenForm = document.getElementById('docs-token-form');

  function setAuthenticated(authenticated) {
    status.dataset.state = authenticated ? 'on' : 'off';
    status.querySelector('.docs-status__text').textContent = authenticated
      ? navbar.dataset.textAuthenticated
      : navbar.dataset.textUnauthenticated;
    logout.hidden = !authenticated;
  }

  function applyToken(token) {
    var applied = doc.setApiKey(BEARER_SCHEME, token.trim());
    appliedToken = applied ? token.trim() : '';
    setAuthenticated(Boolean(applied));
    if (applied) closeDropdown(navbar.querySelector('#docs-auth-panel').closest('[data-dropdown]'), true);
    return applied;
  }

  function showLoginError(message) {
    loginError.textContent = message || '';
    loginError.hidden = !message;
  }

  function readCookie(name) {
    var match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return match ? decodeURIComponent(match[1]) : '';
  }

  function tokenUrl() {
    var base = (doc.selectedServer && doc.selectedServer.computedUrl) || window.location.origin;
    return new URL(navbar.dataset.tokenUrl, base).toString();
  }

  function firstError(data) {
    var error = data && data.error;
    if (!error || typeof error !== 'object') return '';
    var details = error.details;
    if (details && typeof details === 'object') {
      for (var key in details) {
        var value = details[key];
        if (Array.isArray(value) && value.length) return String(value[0]);
        if (typeof value === 'string') return value;
      }
    }
    return typeof error.message === 'string' ? error.message : '';
  }

  loginForm.addEventListener('submit', function (event) {
    event.preventDefault();
    showLoginError('');
    var submit = loginForm.querySelector('[type="submit"]');
    submit.disabled = true;
    var headers = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      'Accept-Language': navbar.dataset.lang,
    };
    var csrf = readCookie('csrftoken');
    if (csrf) headers['X-CSRFToken'] = csrf;
    fetch(tokenUrl(), {
      method: 'POST',
      credentials: 'same-origin',
      headers: headers,
      body: JSON.stringify({ username: loginForm.username.value, password: loginForm.password.value }),
    })
      .then(function (response) {
        return response.json().catch(function () { return {}; }).then(function (data) {
          if (!response.ok || !data.access) throw new Error(firstError(data) || navbar.dataset.textLoginFailed);
          loginForm.reset();
          applyToken(data.access);
        });
      })
      .catch(function (error) {
        showLoginError(error.message || navbar.dataset.textLoginFailed);
      })
      .finally(function () {
        submit.disabled = false;
      });
  });

  tokenForm.addEventListener('submit', function (event) {
    event.preventDefault();
    var token = tokenForm.token.value;
    if (!token.trim()) {
      tokenForm.token.focus();
      return;
    }
    if (applyToken(token)) tokenForm.reset();
  });

  logout.addEventListener('click', function () {
    doc.removeAllSecurityKeys();
    appliedToken = '';
    setAuthenticated(false);
    showLoginError('');
  });
})();
