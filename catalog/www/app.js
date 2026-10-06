/* Agent Fleet Store — vanilla ES2020. Single fetch of /api/inventory.json, everything else client-side. */
'use strict';

var PAGES = ['skills', 'mcps', 'plugins', 'tools'];
var PAGE_SIZE = { skills: 24, mcps: 12, plugins: 12, tools: 12 };
var HARNESSES = ['hermes', 'claude', 'opencode', 'gemini', 'antigravity'];
var TITLES = { skills: 'Skills.', mcps: 'MCPs.', plugins: 'Plugins.', tools: 'Tools.' };

/* ---------- pure helpers (unit-checked at the bottom of this file) ---------- */

function esc(v) {
  return String(v == null ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function searchText(page, item) {
  var parts = [item.name, item.description, item.notes];
  if (page === 'tools') parts.push(item.path);
  if (page === 'mcps') parts.push(item.target);
  return parts.filter(Boolean).join(' ').toLowerCase();
}

function matchesFilters(page, item, st) {
  if (page === 'skills' && st.category !== 'All' && item.category !== st.category) return false;
  if (page === 'mcps') {
    if (st.harness !== 'All' && (item.harnesses || []).indexOf(st.harness) === -1) return false;
    if (st.type !== 'All' && item.type !== st.type) return false;
  }
  if ((page === 'plugins' || page === 'tools') && st.kind !== 'All' && item.kind !== st.kind) return false;
  return true;
}

function sortSkills(list, mode) {
  var out = list.slice();
  if (mode === 'category') {
    out.sort(function (a, b) {
      return (a.category || '').localeCompare(b.category || '') || a.name.localeCompare(b.name);
    });
  } else if (mode === 'updated') {
    out.sort(function (a, b) {
      return String(b.updated || '').localeCompare(String(a.updated || '')) || a.name.localeCompare(b.name);
    });
  } else {
    out.sort(function (a, b) { return a.name.localeCompare(b.name); });
  }
  return out;
}

function selectItems(page, all, st) {
  var q = (st.q || '').trim().toLowerCase();
  var list = all.filter(function (item) {
    if (!matchesFilters(page, item, st)) return false;
    return !q || searchText(page, item).indexOf(q) !== -1;
  });
  return page === 'skills' ? sortSkills(list, st.sort) : list;
}

/* Windowed page numbers: first, last, current +/-1, '...' for the holes. */
function pageWindow(current, total) {
  if (total <= 7) {
    var all = [];
    for (var i = 1; i <= total; i++) all.push(i);
    return all;
  }
  var keep = [1, total, current, current - 1, current + 1];
  if (current <= 3) keep.push(2, 3, 4);
  if (current >= total - 2) keep.push(total - 1, total - 2, total - 3);
  var nums = keep.filter(function (n) { return n >= 1 && n <= total; })
    .filter(function (n, i, a) { return a.indexOf(n) === i; })
    .sort(function (a, b) { return a - b; });
  var out = [];
  nums.forEach(function (n, i) {
    if (i > 0 && n - nums[i - 1] > 1) out.push('…');
    out.push(n);
  });
  return out;
}

function clampPage(n, total) { return Math.min(Math.max(1, n), Math.max(1, total)); }

/* ---------- state ---------- */

var inv = null;
var states = {
  skills: { q: '', sort: 'name', category: 'All', page: 1 },
  mcps: { q: '', harness: 'All', type: 'All', page: 1 },
  plugins: { q: '', kind: 'All', page: 1 },
  tools: { q: '', kind: 'All', page: 1 }
};
var current = 'skills';
var renderedChipsFor = null;
var searchTimer = null;
var writingHash = false;

function currentPageFromHash() {
  var h = (location.hash || '').replace(/^#\/?/, '').split('?')[0];
  return PAGES.indexOf(h) === -1 ? 'skills' : h;
}

var HASH_DEFAULTS = { q: '', cat: 'All', harness: 'All', type: 'All', kind: 'All', sort: 'name', p: 1 };
var HASH_KEYS = {
  skills: ['q', 'cat', 'sort', 'p'],
  mcps: ['q', 'harness', 'type', 'p'],
  plugins: ['q', 'kind', 'p'],
  tools: ['q', 'kind', 'p']
};
var HASH_TO_STATE = { cat: 'category', p: 'page' };

function parseHash() {
  var raw = (location.hash || '').replace(/^#\/?/, '');
  var qIdx = raw.indexOf('?');
  var page = qIdx === -1 ? raw : raw.slice(0, qIdx);
  page = PAGES.indexOf(page) === -1 ? 'skills' : page;
  var params = new URLSearchParams(qIdx === -1 ? '' : raw.slice(qIdx + 1));
  return { page: page, params: params };
}

function applyHash() {
  var parsed = parseHash();
  var st = states[parsed.page];
  (HASH_KEYS[parsed.page] || []).forEach(function (key) {
    var stKey = HASH_TO_STATE[key] || key;
    var v = parsed.params.get(key);
    if (v == null) {
      st[stKey] = HASH_DEFAULTS[key];
    } else if (key === 'p') {
      st[stKey] = Math.max(1, Number(v) || 1);
    } else {
      st[stKey] = v;
    }
  });
  current = parsed.page;
}

function writeHash(push) {
  var st = states[current];
  var qs = new URLSearchParams();
  (HASH_KEYS[current] || []).forEach(function (key) {
    var stKey = HASH_TO_STATE[key] || key;
    var v = st[stKey];
    if (key === 'p') {
      if (v && v !== 1) qs.set(key, String(v));
    } else if (v && v !== HASH_DEFAULTS[key]) {
      qs.set(key, v);
    }
  });
  var qsStr = qs.toString();
  var hash = '#/' + current + (qsStr ? '?' + qsStr : '');
  writingHash = true;
  if (push) location.hash = hash;
  else history.replaceState(null, '', hash);
  setTimeout(function () { writingHash = false; }, 0);
}

/* ---------- card fragments ---------- */

function upstreamBits(up) {
  if (!up) return '';
  var bits = '<a class="up-link" href="' + esc(up.url) + '" target="_blank" rel="noopener noreferrer">↗ ' + esc(up.repo) + '</a>';
  if (typeof up.stars === 'number') bits += '<span class="stars">' + up.stars.toLocaleString('en-US') + '★</span>';
  if (up.latest_tag) bits += '<span class="chip chip-ok chip-plain">' + esc(up.latest_tag) + '</span>';
  return '<div class="row">' + bits + '</div>';
}

function skillCard(s) {
  var meta = [];
  if (s.version) meta.push('v' + s.version);
  meta.push(s.files + ' file' + (s.files === 1 ? '' : 's'));
  if (s.updated) meta.push('updated ' + s.updated);
  return '<article class="card' + (s.page ? ' is-linked' : '') + '">' +
    '<div class="card-top">' +
      '<h3 class="card-name">' + esc(s.name) + '</h3>' +
      '<span class="chip">' + esc(s.category) + '</span>' +
    '</div>' +
    '<p class="card-desc" title="' + esc(s.description) + '">' + esc(s.description) + '</p>' +
    '<p class="card-meta">' + esc(meta.join(' · ')) + '</p>' +
    '<div class="row"><span class="chip">' + esc(s.source || 'local') + '</span>' + (s.page ? '<a class="up-link" href="' + esc(s.page) + '">details →</a>' : '') + '</div>' +
    upstreamBits(s.upstream) +
  '</article>';
}

function mcpCard(m) {
  var harness = HARNESSES.map(function (h) {
    var on = (m.harnesses || []).indexOf(h) !== -1;
    return '<span class="chip ' + (on ? 'chip-accent' : 'chip-dim') + '" title="' + (on ? 'configured' : 'not configured') + '">' + esc(h) + '</span>';
  }).join('');
  var envs = (m.env || []).map(function (e) { return '<span class="chip">' + esc(e) + '</span>'; }).join('');
  return '<article class="card' + (m.page ? ' is-linked' : '') + '">' +
    '<div class="card-top">' +
      '<h3 class="card-name">' + esc(m.name) + '</h3>' +
      '<span class="chip">' + esc(m.type) + '</span>' +
    '</div>' +
    '<p class="card-target" title="' + esc(m.target) + '">' + esc(m.target) + '</p>' +
    (envs ? '<div class="row">' + envs + '</div>' : '') +
    '<div class="row">' + harness + (m.machine_local ? '<span class="chip">machine local</span>' : '') + (m.page ? '<a class="up-link" href="' + esc(m.page) + '">details →</a>' : '') + '</div>' +
    (m.notes ? '<p class="card-note">' + esc(m.notes) + '</p>' : '') +
    upstreamBits(m.upstream) +
  '</article>';
}

function pluginCard(p) {
  return '<article class="card' + (p.page ? ' is-linked' : '') + '">' +
    '<div class="card-top">' +
      '<h3 class="card-name">' + esc(p.name) + '</h3>' +
      '<span class="chip">' + esc(p.kind) + '</span>' +
    '</div>' +
    (p.version ? '<p class="card-meta">v' + esc(p.version) + '</p>' : '') +
    '<p class="card-desc" title="' + esc(p.description) + '">' + esc(p.description) + '</p>' +
    (p.homepage ? '<div class="row"><a class="up-link" href="' + esc(p.homepage) + '" target="_blank" rel="noopener noreferrer">↗ homepage</a>' + (p.page ? ' <a class="up-link" href="' + esc(p.page) + '">details →</a>' : '') + '</div>' : '<div class="row">' + (p.page ? '<a class="up-link" href="' + esc(p.page) + '">details →</a>' : '') + '</div>') +
    upstreamBits(p.upstream) +
  '</article>';
}

function toolCard(t) {
  return '<article class="card' + (t.page ? ' is-linked' : '') + '">' +
    '<div class="card-top">' +
      '<h3 class="card-name card-name-mono">' + esc(t.name) + '</h3>' +
      '<span class="chip">' + esc(t.kind) + '</span>' +
    '</div>' +
    '<p class="card-desc" title="' + esc(t.description) + '">' + esc(t.description) + '</p>' +
    '<p class="card-path">' + esc(t.path) + '</p>' +
    '<div class="row">' + (t.page ? '<a class="up-link" href="' + esc(t.page) + '">details →</a>' : '') + '</div>' +
  '</article>';
}

var CARD = { skills: skillCard, mcps: mcpCard, plugins: pluginCard, tools: toolCard };

/* ---------- chips ---------- */

var CHIP_LABEL = { category: 'Filter by category', harness: 'Filter by harness', type: 'Filter by transport', kind: 'Filter by kind' };

function chipRow(key, values, active) {
  return '<div class="chiprow" role="group" aria-label="' + esc(CHIP_LABEL[key] || key) + '" data-key="' + key + '">' + values.map(function (v) {
    var on = v === active;
    return '<button type="button" class="btn' + (on ? ' is-on' : '') + '" aria-pressed="' + on + '" data-key="' + key + '" data-value="' + esc(v) + '">' + esc(v) + '</button>';
  }).join('') + '</div>';
}

function renderChips() {
  var st = states[current];
  var html = '';
  if (current === 'skills') html = chipRow('category', ['All'].concat(inv.categories || []), st.category);
  if (current === 'mcps') {
    html = chipRow('harness', ['All'].concat(HARNESSES), st.harness) +
           chipRow('type', ['All', 'http', 'stdio'], st.type);
  }
  if (current === 'plugins' || current === 'tools') {
    var kinds = [];
    inv[current].forEach(function (i) { if (i.kind && kinds.indexOf(i.kind) === -1) kinds.push(i.kind); });
    kinds.sort();
    html = chipRow('kind', ['All'].concat(kinds), st.kind);
  }
  document.getElementById('chiprows').innerHTML = html;
}

/* ---------- render ---------- */

function activeFilters(st) {
  return ['category', 'harness', 'type', 'kind'].some(function (k) {
    return st[k] && st[k] !== 'All';
  }) || !!(st.q || '').trim();
}

function subLine() {
  var c = inv.counts || {};
  var st = states[current];
  var total = c[current] || 0;
  var base;
  if (current === 'skills') base = total + ' skills · ' + (inv.categories || []).length + ' categories';
  else if (current === 'mcps') base = total + ' mcps · ' + HARNESSES.length + ' harnesses';
  else if (current === 'plugins') base = total + ' plugins';
  else base = total + ' tools';
  if (!activeFilters(st)) return base;
  var shown = selectItems(current, inv[current] || [], st).length;
  return shown + (shown === 1 ? ' match' : ' matches') + ' · ' + base;
}

function renderPager(shown, totalItems, from, to) {
  var st = states[current];
  var size = PAGE_SIZE[current];
  var totalPages = Math.max(1, Math.ceil(totalItems / size));
  if (!totalItems) { document.getElementById('pager').innerHTML = ''; return; }
  var nums = pageWindow(st.page, totalPages).map(function (n) {
    if (n === '…') return '<span class="gap">…</span>';
    var on = n === st.page;
    return '<button type="button" class="btn' + (on ? ' is-on' : '') + '" aria-label="Page ' + n + '"' + (on ? ' aria-current="page"' : '') + ' data-goto="' + n + '">' + n + '</button>';
  }).join('');
  document.getElementById('pager').innerHTML = '<div class="pager">' +
    '<span class="count">showing ' + from + '–' + to + ' of ' + totalItems + '</span>' +
    '<button type="button" class="btn" data-goto="' + (st.page - 1) + '"' + (st.page === 1 ? ' disabled' : '') + '>Prev</button>' +
    nums +
    '<button type="button" class="btn" data-goto="' + (st.page + 1) + '"' + (st.page === totalPages ? ' disabled' : '') + '>Next</button>' +
  '</div>';
  void shown;
}

function render() {
  document.querySelectorAll('.nav-item').forEach(function (a) {
    if (a.dataset.page === current) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
  document.getElementById('page-title').textContent = TITLES[current];
  var st = states[current];
  document.getElementById('sort').hidden = current !== 'skills';
  document.getElementById('search').placeholder = 'Search ' + current + '…';
  if (document.getElementById('search').value !== st.q) document.getElementById('search').value = st.q;
  document.getElementById('sort').value = st.sort || 'name';

  if (!inv) return;
  document.getElementById('page-sub').textContent = subLine();
  if (renderedChipsFor !== current) { renderChips(); renderedChipsFor = current; }

  var items = selectItems(current, inv[current] || [], st);
  var size = PAGE_SIZE[current];
  st.page = clampPage(st.page, Math.ceil(items.length / size));
  var from = (st.page - 1) * size;
  var slice = items.slice(from, from + size);
  var content = document.getElementById('content');

  if (!items.length) {
    content.setAttribute('aria-busy', 'false');
    content.innerHTML = '<div class="state" role="status"><p>No matches — clear filters</p>' +
      '<button type="button" class="btn btn-primary" id="clear-filters">Clear filters</button></div>';
    document.getElementById('pager').innerHTML = '';
    return;
  }
  content.setAttribute('aria-busy', 'false');
  content.innerHTML = '<div class="grid">' + slice.map(CARD[current]).join('') + '</div>';
  renderPager(slice.length, items.length, from + 1, from + slice.length);
}

function showSkeletons() {
  var cells = '';
  for (var i = 0; i < Math.min(PAGE_SIZE[current], 12); i++) cells += '<div class="skel"></div>';
  var content = document.getElementById('content');
  content.setAttribute('aria-busy', 'true');
  content.innerHTML = '<div class="grid" aria-hidden="true">' + cells + '</div>';
}

function showError(msg) {
  document.getElementById('content').innerHTML = '<div class="state" role="alert">' +
    '<p>Could not load inventory.</p><code>' + esc(msg) + '</code>' +
    '<button type="button" class="btn btn-primary" id="retry">Retry</button></div>';
  document.getElementById('pager').innerHTML = '';
}

function renderSidebarMeta() {
  PAGES.forEach(function (p) {
    var el = document.querySelector('[data-count="' + p + '"]');
    var n = (inv.counts || {})[p];
    if (el) el.textContent = (n == null) ? '—' : n.toLocaleString('en-US');
  });
  document.getElementById('foot-head').textContent = 'head ' + (inv.head || '?');
  document.getElementById('foot-updated').textContent = 'updated ' + (inv.generated_at || '?');
}

function load() {
  showSkeletons();
  document.getElementById('page-sub').textContent = 'loading…';
  fetch('/api/inventory.json', { cache: 'no-cache' })
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function (data) {
      inv = data;
      palItems = null;
      renderSidebarMeta();
      renderedChipsFor = null;
      render();
    })
    .catch(function (e) { showError(e.message || String(e)); });
}

/* ---------- events ---------- */

function init() {
  try {
  if (!location.hash) history.replaceState(null, '', '#/skills');
  applyHash();

  window.addEventListener('hashchange', function () {
    if (writingHash) return;
    clearTimeout(searchTimer);
    var prevPage = current;
    applyHash();
    if (prevPage !== current) renderedChipsFor = null;
    render();
    if (prevPage !== current) window.scrollTo(0, 0);
  });

  var search = document.getElementById('search');
  search.addEventListener('input', function () {
    clearTimeout(searchTimer);
    var v = search.value;
    var page = current;
    searchTimer = setTimeout(function () {
      states[page].q = v;
      states[page].page = 1;
      if (page === current) { writeHash(false); render(); }
    }, 150);
  });
  search.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      var page = current;
      search.value = '';
      states[page].q = '';
      states[page].page = 1;
      writeHash(true);
      render();
    }
  });

  document.getElementById('sort').addEventListener('change', function (e) {
    states[current].sort = e.target.value;
    states[current].page = 1;
    writeHash(true);
    render();
  });

  document.getElementById('chiprows').addEventListener('click', function (e) {
    var btn = e.target.closest('button[data-key]');
    if (!btn) return;
    states[current][btn.dataset.key] = btn.dataset.value;
    states[current].page = 1;
    btn.parentNode.querySelectorAll('button').forEach(function (b) {
      b.classList.toggle('is-on', b === btn);
      b.setAttribute('aria-pressed', b === btn ? 'true' : 'false');
    });
    writeHash(true);
    render();
  });

  document.getElementById('pager').addEventListener('click', function (e) {
    var btn = e.target.closest('button[data-goto]');
    if (!btn || btn.disabled) return;
    states[current].page = Number(btn.dataset.goto);
    writeHash(true);
    render();
    window.scrollTo(0, 0);
  });

  document.getElementById('content').addEventListener('click', function (e) {
    if (e.target.id === 'retry') { load(); return; }
    if (e.target.id === 'clear-filters') {
      states[current] = Object.assign(states[current], { q: '', category: 'All', harness: 'All', type: 'All', kind: 'All', page: 1 });
      document.getElementById('search').value = '';
      renderedChipsFor = null;
      writeHash(true);
      render();
    }
  });

  var prefetched = {};
  document.getElementById('content').addEventListener('mouseover', function (e) {
    if (navigator.connection && navigator.connection.saveData) return;
    var a = e.target.closest && e.target.closest('a[href^="/item/"]');
    if (!a || prefetched[a.getAttribute('href')]) return;
    prefetched[a.getAttribute('href')] = 1;
    var l = document.createElement('link');
    l.rel = 'prefetch'; l.href = a.getAttribute('href');
    document.head.appendChild(l);
  });

  var copyBtn = document.getElementById('copy-btn');
  copyBtn.addEventListener('click', function () {
    var text = document.getElementById('install-cmd').textContent.trim();
    var live = document.getElementById('copy-status');
    var done = function (ok) {
      copyBtn.textContent = ok ? 'copied' : 'copy failed';
      if (live) live.textContent = ok ? 'Copied to clipboard' : 'Copy failed — select the command and copy manually';
      setTimeout(function () { copyBtn.textContent = 'Copy'; if (live) live.textContent = ''; }, 1500);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(false); });
    } else {
      done(false);
    }
  });

  try { palInit(); } catch (e) { /* palette is optional — never block page init */ }

  /* collapsible sidebar — state in localStorage, key "S" toggles */
  var sideBtn = document.getElementById('side-toggle');
  if (sideBtn) {
    var sideSet = function (collapsed) {
      document.body.classList.toggle('side-collapsed', collapsed);
      sideBtn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      var lbl = sideBtn.querySelector('.side-toggle-label');
      if (lbl) lbl.textContent = collapsed ? 'Expand' : 'Collapse';
      try { localStorage.setItem('side-collapsed', collapsed ? '1' : '0'); } catch (e) {}
    };
    var saved = null;
    try { saved = localStorage.getItem('side-collapsed'); } catch (e) {}
    sideSet(saved === '1');
    sideBtn.addEventListener('click', function () {
      sideSet(!document.body.classList.contains('side-collapsed'));
    });
    document.addEventListener('keydown', function (e) {
      var tag = (document.activeElement && document.activeElement.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
      if ((e.key === 's' || e.key === 'S') && !e.metaKey && !e.ctrlKey && !e.altKey && (!palBuilt || document.getElementById('pal').hidden)) {
        e.preventDefault();
        sideSet(!document.body.classList.contains('side-collapsed'));
      }
    });
  }

  /* active rail — one pill glides to the current section (skips while collapsed) */
  var rail = document.getElementById('nav-rail');
  var railMove = function () {
    if (!rail) return;
    var act = document.querySelector('.nav-item[aria-current="page"]');
    var nav = document.getElementById('nav');
    if (!act || !nav) { rail.style.opacity = '0'; return; }
    if (document.body.classList.contains('side-collapsed')) { rail.style.opacity = '0'; return; }
    var top = act.offsetTop + (act.offsetHeight - rail.offsetHeight) / 2;
    rail.style.transform = 'translateY(' + top + 'px)';
    rail.style.opacity = '1';
  };
  railMove();
  window.addEventListener('resize', railMove);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(railMove);
  if ('ResizeObserver' in window) {
    new ResizeObserver(railMove).observe(document.getElementById('nav'));
  }
  var _sideSet = sideSet;
  sideSet = function (v) { _sideSet(v); railMove(); };
  var _render = render;
  render = function () { _render(); railMove(); };

  render();
  load();
  } catch (e) {
    // one broken wiring must not blank the page — force the loading state away regardless
    try { render(); load(); } catch (e2) {}
  }
}

/* ---------- command palette (R6.1) ---------- */

var palItems = null, palResults = [], palActive = -1, palReturnFocus = null, palTimer = null;

function palFlatten() {
  var out = [];
  PAGES.forEach(function (p) { (inv[p] || []).forEach(function (it) { out.push({ name: it.name, page: it.page, kind: p, _s: searchText(p, it) }); }); });
  (inv.custom || []).forEach(function (it) { out.push({ name: it.title, page: '/item/custom/' + it.slug, kind: 'custom', _s: searchText('custom', { name: it.title, description: it.summary }) }); });
  return out;
}

function palRender() {
  var input = document.getElementById('pal-input');
  document.getElementById('pal-list').innerHTML = palResults.map(function (it, i) {
    return '<li role="option" tabindex="-1" id="pal-opt-' + i + '" aria-selected="' + (i === palActive) + '" class="' + (i === palActive ? 'is-on' : '') + '" data-i="' + i + '"><span class="card-name">' + esc(it.name) + '</span><span class="chip">' + esc(it.kind) + '</span></li>';
  }).join('');
  if (palActive === -1) input.removeAttribute('aria-activedescendant'); else input.setAttribute('aria-activedescendant', 'pal-opt-' + palActive);
  document.getElementById('pal-status').textContent = palResults.length + ' results';
}

function palFilter(q) {
  q = q.trim().toLowerCase();
  palResults = !q ? [] : palItems.filter(function (it) { return it._s.indexOf(q) !== -1; }).slice(0, 12);
  palActive = palResults.length ? 0 : -1;
  palRender();
}

function palGo(i) {
  var it = palResults[i];
  if (!it) return;
  if (it.page) location.href = it.page; else location.hash = '#/' + it.kind + '?q=' + encodeURIComponent(it.name);
}

function palSetHidden(v) {
  document.querySelector('.sidebar').setAttribute('aria-hidden', v);
  document.getElementById('main').setAttribute('aria-hidden', v);
}

var palBuilt = false;
function palEnsure() {
  if (palBuilt) return;
  var w = document.createElement('div');
  w.id = 'pal'; w.hidden = true;
  w.innerHTML = '<div class="pal-box" role="combobox" aria-expanded="true" aria-haspopup="listbox"'
    + ' aria-owns="pal-list" aria-label="Search everything">'
    + '<input class="pal-input" id="pal-input" type="text" role="searchbox"'
    + ' autocomplete="off" aria-controls="pal-list" aria-autocomplete="list"'
    + ' placeholder="Search skills, MCPs, plugins, tools…">'
    + '<ul class="pal-list" id="pal-list" role="listbox" aria-label="Results"></ul>'
    + '<p class="sr-only" id="pal-status" role="status" aria-live="polite"></p></div>';
  document.body.appendChild(w);
  palBuilt = true;
}
function palOpen() {
  palEnsure();
  if (!inv) return;
  if (!palItems) palItems = palFlatten();
  palReturnFocus = document.activeElement;
  document.getElementById('pal').hidden = false;
  palSetHidden(true);
  document.getElementById('pal-input').value = '';
  palFilter('');
  document.getElementById('pal-input').focus();
}

function palClose() {
  document.getElementById('pal').hidden = true;
  palSetHidden(false);
  if (palReturnFocus && palReturnFocus.focus) palReturnFocus.focus();
  palReturnFocus = null;
}

function palInit() {
  palEnsure();
  var input = document.getElementById('pal-input');
  if (!input) return;
  input.addEventListener('input', function () {
    clearTimeout(palTimer);
    var v = input.value;
    palTimer = setTimeout(function () { palFilter(v); }, 150);
  });
  document.getElementById('pal-list').addEventListener('click', function (e) {
    var li = e.target.closest('li[data-i]');
    if (li) palGo(Number(li.dataset.i));
  });
  document.getElementById('pal').addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { e.preventDefault(); palClose(); }
    else if (e.key === 'ArrowDown' && palResults.length) { e.preventDefault(); palActive = (palActive + 1) % palResults.length; palRender(); }
    else if (e.key === 'ArrowUp' && palResults.length) { e.preventDefault(); palActive = (palActive - 1 + palResults.length) % palResults.length; palRender(); }
    else if (e.key === 'Enter') { e.preventDefault(); palGo(palActive); }
    else if (e.key === 'Tab') {
      var last = document.querySelector('#pal-list li:last-child');
      if (!last) { e.preventDefault(); return; }
      e.preventDefault();
      (document.activeElement === input ? last : input).focus();
    }
  });
  document.addEventListener('keydown', function (e) {
    if ((e.key === 'k' || e.key === 'K') && (e.metaKey || e.ctrlKey)) { e.preventDefault(); palOpen(); return; }
    if (e.key !== '/' || (palBuilt && !document.getElementById('pal').hidden)) return;
    var tag = (document.activeElement && document.activeElement.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
    e.preventDefault();
    palOpen();
  });
}

/* ---------- self-check: `node app.js` ---------- */

function selfcheck() {
  var assert = function (cond, msg) { if (!cond) throw new Error('selfcheck: ' + msg); };

  assert(esc('<a href="x">&') === '&lt;a href=&quot;x&quot;&gt;&amp;', 'esc');

  assert(JSON.stringify(pageWindow(1, 3)) === '[1,2,3]', 'window small');
  assert(JSON.stringify(pageWindow(1, 20)) === '[1,2,3,4,"…",20]', 'window head');
  assert(JSON.stringify(pageWindow(10, 20)) === '[1,"…",9,10,11,"…",20]', 'window middle');
  assert(JSON.stringify(pageWindow(20, 20)) === '[1,"…",17,18,19,20]', 'window tail');
  assert(pageWindow(5, 21).indexOf('…') !== -1, 'window ellipsis');

  assert(clampPage(0, 5) === 1 && clampPage(9, 5) === 5 && clampPage(3, 0) === 1, 'clampPage');

  var skills = [
    { name: 'beta', category: 'web', description: 'Runs a server', updated: '2026-01-02' },
    { name: 'alpha', category: 'apple', description: 'Notes tool', updated: '2026-05-01' }
  ];
  assert(sortSkills(skills, 'name').map(function (s) { return s.name; }).join() === 'alpha,beta', 'sort name');
  assert(sortSkills(skills, 'updated')[0].name === 'alpha', 'sort updated');
  assert(sortSkills(skills, 'category')[0].category === 'apple', 'sort category');

  var st = { q: 'server', sort: 'name', category: 'All', page: 1 };
  assert(selectItems('skills', skills, st).length === 1, 'search matches description');
  st.q = ''; st.category = 'apple';
  assert(selectItems('skills', skills, st).length === 1, 'category filter');

  var mcps = [
    { name: 'a', type: 'http', harnesses: ['hermes'], target: 'https://x/mcp', notes: '' },
    { name: 'b', type: 'stdio', harnesses: ['claude', 'hermes'], target: 'npx -y thing', notes: 'shared' }
  ];
  assert(selectItems('mcps', mcps, { q: '', harness: 'claude', type: 'All' }).length === 1, 'harness filter');
  assert(selectItems('mcps', mcps, { q: '', harness: 'All', type: 'http' }).length === 1, 'type filter');
  assert(selectItems('mcps', mcps, { q: 'npx', harness: 'All', type: 'All' }).length === 1, 'mcp target search');

  var tools = [{ name: 'install.sh', kind: 'installer', description: 'one-liner', path: 'install.sh' }];
  assert(selectItems('tools', tools, { q: 'install.sh', kind: 'All' }).length === 1, 'tool path search');
  assert(selectItems('tools', tools, { q: '', kind: 'web' }).length === 0, 'tool kind filter');

  console.log('app.js selfcheck ok');
}

if (typeof document === 'undefined') selfcheck();
else if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
else init();
