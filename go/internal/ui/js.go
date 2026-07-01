package ui

const appJS = `
'use strict';

// All communication with Go is plain JSON over HTTP (fetch).
// No glaze Bind. Same code runs in the desktop WebView and in a real
// browser on tube.denizsincar.ru.

function $(id) { return document.getElementById(id); }

// ---------- Live-region announcer ----------
// Uses two regions so rapid sequential announcements still fire:
// swap between them with a tiny delay to force a re-read.
let _announceTarget = 0;
function announce(msg, urgent) {
  const el = urgent ? $('alert-live') : $('status-live');
  el.textContent = '';
  setTimeout(() => { el.textContent = msg; }, 30);
}

// ---------- API wrapper ----------
async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(path, opts);
  if (r.status === 204) return null;
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

// ---------- Helpers ----------
function fmtDuration(sec) {
  sec = Math.max(0, Math.floor(sec || 0));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  const p = n => String(n).padStart(2, '0');
  return h ? (h + ':' + p(m) + ':' + p(s)) : (m + ':' + p(s));
}

// ---------- App state ----------
let results = [];
let isFavoritesView = false;
let currentVideo = null;
let searchPending = false;
let loadingMore = false;
let currentQuery = '';
let appMode = 'desktop'; // filled in from /api/mode on load
let favoriteURLs = new Set(); // known favorites for quick toggle label

const player = $('video-player');
const resultsList = $('results-list');
const searchField = $('search-field');

// ---------- YouTube-compatible URL routing ----------
// Extracts a video id from the current page URL so that sharing or
// typing tube.denizsincar.ru/watch?v=dQw4w9WgXcQ works exactly like
// visiting youtube.com/watch?v=dQw4w9WgXcQ.
function extractVideoIDFromLocation() {
  const path   = location.pathname;   // e.g. /watch  /shorts/abc  /embed/abc
  const params = new URLSearchParams(location.search);

  // /watch?v=<id>
  if (path === '/watch') {
    const v = params.get('v');
    if (v) return v;
  }

  // /shorts/<id>  /embed/<id>  /v/<id>
  const m = path.match(/^\/(?:shorts|embed|v)\/([a-zA-Z0-9_-]{10,12})/);
  if (m) return m[1];

  return null;
}

// ---------- Init ----------
async function init() {
  try {
    const m = await api('GET', '/api/mode');
    appMode = m.mode;
  } catch (_) {}
  if (appMode === 'web') {
    // Hide desktop-only controls.
    document.querySelectorAll('.desktop-only').forEach(el => el.hidden = true);
    // In web mode downloads are browser file downloads, change labels.
    $('nav-download-video').textContent = 'Download Video (Ctrl+D)';
    $('nav-download-audio').textContent = 'Download Audio (Ctrl+Shift+D)';
  }
  await loadFavoriteURLs();
  await showFavorites(); // home screen = favorites, same as Python version

  // Auto-play from URL. Handles YouTube-compatible patterns:
  //   /watch?v=<id>       standard YouTube watch URL
  //   /shorts/<id>        YouTube Shorts
  //   /embed/<id>         embed URL
  //   /v/<id>             legacy /v/ URL
  //   /?url=<id_or_url>   desktop CLI --url flag
  //   /?search=<query>    desktop CLI --search flag
  const autoID = extractVideoIDFromLocation();
  const params = new URLSearchParams(location.search);
  if (autoID) {
    await playByURL(autoID, '');
  } else if (params.get('url')) {
    await playByURL(params.get('url'), '');
  } else if (params.get('search')) {
    searchField.value = params.get('search');
    await searchAction();
  }

  searchField.focus();
  announce('BlindTube ready. Type a search query and press Enter.');
}

async function loadFavoriteURLs() {
  if (appMode === 'web') return;
  try {
    const favs = await api('GET', '/api/favorites') || [];
    favoriteURLs = new Set(favs.map(f => f.url));
  } catch (_) {}
}

// ---------- Results list ----------
function renderResults() {
  resultsList.innerHTML = '';
  results.forEach((r, i) => {
    const li = document.createElement('li');
    li.id = 'result-' + i;
    li.setAttribute('role', 'option');
    li.setAttribute('tabindex', '-1');
    li.dataset.index = String(i);
    const dur = r.duration ? ' (' + fmtDuration(r.duration) + ')' : '';
    li.textContent = r.title + ' by ' + (r.channel || 'Unknown') + dur;
    li.addEventListener('click', () => selectResult(i, true));
    li.addEventListener('dblclick', () => playResult(i));
    li.addEventListener('contextmenu', e => { e.preventDefault(); openActionsMenu(i, e.clientX, e.clientY); });
    resultsList.appendChild(li);
  });
  if (results.length > 0) selectResult(0, false);
}

function selectResult(index, focus) {
  resultsList.querySelectorAll('li').forEach((li, i) => {
    li.setAttribute('aria-selected', i === index ? 'true' : 'false');
  });
  resultsList.setAttribute('aria-activedescendant', 'result-' + index);
  const item = $('result-' + index);
  if (item && focus) item.scrollIntoView({ block: 'nearest' });
}

function selectedIndex() {
  const a = resultsList.querySelector('li[aria-selected="true"]');
  return a ? parseInt(a.dataset.index, 10) : -1;
}

resultsList.addEventListener('keydown', e => {
  const items = resultsList.querySelectorAll('li');
  if (!items.length) return;
  let idx = selectedIndex();
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    idx = Math.min(items.length - 1, idx + 1);
    selectResult(idx, true);
    if (!isFavoritesView && idx >= items.length - 3) maybeLoadMore();
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    idx = Math.max(0, idx - 1);
    selectResult(idx, true);
  } else if (e.key === 'Enter') {
    e.preventDefault();
    if (idx >= 0) playResult(idx);
  } else if (e.key === 'Application' || (e.shiftKey && e.key === 'F10')) {
    e.preventDefault();
    if (idx >= 0) openActionsMenu(idx);
  }
});

resultsList.addEventListener('scroll', () => {
  if (isFavoritesView) return;
  if (resultsList.scrollTop + resultsList.clientHeight >= resultsList.scrollHeight - 60)
    maybeLoadMore();
});

async function maybeLoadMore() {
  if (loadingMore || searchPending || isFavoritesView || !currentQuery) return;
  loadingMore = true;
  try {
    const more = await api('POST', '/api/search/more') || [];
    if (more.length > 0) {
      results = results.concat(more);
      renderResults();
    }
  } catch (err) { console.error(err); }
  finally { loadingMore = false; }
}

// ---------- Context / actions menu (replaces Qt's right-click menu) ----------
// Rendered as a floating <ul> positioned near the cursor (or at the item
// position for keyboard). NVDA reads this as an ARIA menu.
let activeMenu = null;

function closeActionsMenu() {
  if (activeMenu) { activeMenu.remove(); activeMenu = null; }
}

function openActionsMenu(index, x, y) {
  closeActionsMenu();
  const r = results[index];
  if (!r) return;

  const isFav = favoriteURLs.has(r.url);

  const items = [
    { label: 'Play',                     action: () => playResult(index) },
    { label: 'View Description',         action: () => viewVideoInfo(index) },
    { label: 'Download Video',           action: () => downloadOne(r.url, false) },
    { label: 'Download Audio',           action: () => downloadOne(r.url, true) },
    { label: 'Copy link',                action: () => copyLink(r.url) },
    {
      label: isFav ? 'Remove from Favorites' : 'Add to Favorites',
      action: () => isFav ? removeFromFavorites(r.url) : addToFavorites(index)
    },
  ];

  const menu = document.createElement('ul');
  menu.setAttribute('role', 'menu');
  menu.setAttribute('aria-label', 'Video actions');
  menu.className = 'context-menu';

  items.forEach((it, i) => {
    const li = document.createElement('li');
    li.setAttribute('role', 'menuitem');
    li.setAttribute('tabindex', i === 0 ? '0' : '-1');
    li.textContent = it.label;
    li.addEventListener('click', () => { closeActionsMenu(); it.action(); });
    li.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); closeActionsMenu(); it.action(); }
      if (e.key === 'ArrowDown') { e.preventDefault(); (li.nextElementSibling || menu.firstElementChild).focus(); }
      if (e.key === 'ArrowUp')   { e.preventDefault(); (li.previousElementSibling || menu.lastElementChild).focus(); }
      if (e.key === 'Escape')    { e.preventDefault(); closeActionsMenu(); resultsList.focus(); }
    });
    menu.appendChild(li);
  });

  // Position near cursor if coordinates given, else near the selected item.
  if (x !== undefined && y !== undefined) {
    menu.style.left = x + 'px';
    menu.style.top  = y + 'px';
  } else {
    const item = $('result-' + index);
    if (item) {
      const rect = item.getBoundingClientRect();
      menu.style.left = rect.left + 'px';
      menu.style.top  = (rect.bottom + 4) + 'px';
    }
  }

  document.body.appendChild(menu);
  activeMenu = menu;
  menu.firstElementChild.focus();

  // Close when clicking outside.
  setTimeout(() => document.addEventListener('click', closeActionsMenu, { once: true }), 0);
}

// ---------- Search ----------
$('search-form').addEventListener('submit', async e => { e.preventDefault(); await searchAction(); });

async function searchAction() {
  const query = searchField.value.trim();
  if (!query) return;
  isFavoritesView = false;
  currentQuery = query;
  searchPending = true;
  announce('Searching for ' + query + '…');
  try {
    results = await api('POST', '/api/search', { q: query }) || [];
    renderResults();
    announce(results.length + ' results.');
  } catch (err) { announce('Search failed: ' + err.message, true); }
  finally { searchPending = false; }
}

// ---------- Playback ----------
async function playResult(index) {
  const r = results[index];
  if (r) await playByURL(r.url, r.title);
}

async function playByURL(urlOrID, knownTitle) {
  announce('Loading ' + (knownTitle || urlOrID) + '…');
  try {
    currentVideo = await api('GET', '/api/video?id=' + encodeURIComponent(urlOrID));
    player.src = currentVideo.streamPath;
    $('now-playing').textContent = currentVideo.title + ' — ' + currentVideo.channel;
    await player.play().catch(() => {});
    announce('Playing ' + currentVideo.title + ' by ' + currentVideo.channel + ', ' + fmtDuration(currentVideo.duration) + '.');
  } catch (err) { announce('Could not play: ' + err.message, true); }
}

function playpause() {
  if (!player.src) { announce('Nothing loaded.'); return; }
  if (player.paused) { player.play(); announce('Playing.'); }
  else { player.pause(); announce('Paused.'); }
}

function seek(fwd) {
  if (!player.src) return;
  player.currentTime = Math.max(0, Math.min(player.duration || Infinity, player.currentTime + (fwd ? 5 : -5)));
  announcePosition();
}

function adjustVolume(up) {
  if (!player.src) return;
  player.volume = Math.max(0, Math.min(1, player.volume + (up ? 0.1 : -0.1)));
  announce('Volume ' + Math.round(player.volume * 100) + '%.');
}

function announcePosition() {
  if (!player.src) { announce('Nothing loaded.'); return; }
  announce(fmtDuration(player.currentTime) + ' of ' + fmtDuration(player.duration) + '.');
}

// ---------- Downloads ----------
async function downloadOne(urlOrID, audioOnly) {
  if (!urlOrID) { announce('Select a video first.', true); return; }
  const endpoint = audioOnly ? '/api/download/audio' : '/api/download/video';
  const url = endpoint + '?id=' + encodeURIComponent(urlOrID);

  if (appMode === 'web') {
    // Browser download: just navigate to the endpoint.
    announce('Starting download…');
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    a.remove();
    announce('Download started. Check your browser downloads.');
  } else {
    // Desktop: Go saves to download dir, returns path.
    announce('Downloading, please wait…');
    try {
      const res = await api('GET', url);
      announce('Saved to ' + res.path);
    } catch (err) { announce('Download failed: ' + err.message, true); }
  }
}

function currentTargetURL() {
  const r = results[selectedIndex()];
  return (currentVideo && currentVideo.url) || (r && r.url) || null;
}

async function downloadVideoAction() { await downloadOne(currentTargetURL(), false); }
async function downloadAudioAction() { await downloadOne(currentTargetURL(), true); }

async function downloadAllFavorites(audioOnly) {
  if (appMode === 'web') { announce('Download all favorites is a desktop-only feature.', true); return; }
  announce('Starting batch download…');
  try {
    const results = await api('POST', '/api/favorites/download-all', { audio_only: audioOnly });
    const ok = results.filter(r => !r.error).length;
    const fail = results.filter(r => r.error).length;
    announce('Done. ' + ok + ' downloaded' + (fail ? ', ' + fail + ' failed.' : '.'));
  } catch (err) { announce('Batch download failed: ' + err.message, true); }
}

// ---------- Favorites ----------
async function showFavorites() {
  searchField.value = '';
  currentQuery = '';
  isFavoritesView = true;
  try {
    const favs = await api('GET', '/api/favorites') || [];
    favoriteURLs = new Set(favs.map(f => f.url));
    results = favs.map(f => ({ title: f.info, channel: '', duration: 0, url: f.url }));
    renderResults();
    announce('Home. ' + results.length + ' favorites.');
  } catch (err) { announce('Could not load favorites: ' + err.message, true); }
}

async function addToFavorites(index) {
  if (appMode === 'web') { announce('Favorites are a desktop-only feature.', true); return; }
  const r = results[index !== undefined ? index : selectedIndex()];
  const target = r || currentVideo;
  if (!target) { announce('Select a video first.', true); return; }
  const info = target.title + (target.channel ? ' by ' + target.channel : '');
  const url  = target.url;
  try {
    const res = await api('POST', '/api/favorites', { info, url });
    if (res.added) { favoriteURLs.add(url); announce('Added to favorites.'); }
    else announce('Already in favorites.');
  } catch (err) { announce('Could not add favorite: ' + err.message, true); }
}

async function removeFromFavorites(url) {
  if (appMode === 'web') return;
  try {
    await api('DELETE', '/api/favorites?url=' + encodeURIComponent(url));
    favoriteURLs.delete(url);
    await showFavorites(); // refresh list
    announce('Removed from favorites.');
  } catch (err) { announce('Could not remove favorite: ' + err.message, true); }
}

async function addCurrentToFavorites() { await addToFavorites(selectedIndex()); }

function copyLink(url) {
  const target = url || currentTargetURL();
  if (!target) { announce('No video selected.', true); return; }
  navigator.clipboard.writeText(target)
    .then(() => announce('Link copied to clipboard.'))
    .catch(() => {
      // Fallback for WebView2 which may restrict clipboard API.
      const ta = document.createElement('textarea');
      ta.value = target;
      ta.style.position = 'absolute'; ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
      announce('Link copied to clipboard.');
    });
}

// ---------- Video info / description ----------
async function viewVideoInfo(index) {
  const r = results[index !== undefined ? index : selectedIndex()];
  const urlOrID = (r && r.url) || (currentVideo && currentVideo.url);
  if (!urlOrID) { announce('Select a video first.', true); return; }
  try {
    const info = await api('GET', '/api/video?id=' + encodeURIComponent(urlOrID));
    currentVideo = info;
    $('info-heading').textContent = info.title;
    $('info-channel').textContent = info.channel + ' · ' + fmtDuration(info.duration);
    $('info-description').value = info.description || '(no description)';
    showScreen('screen-info');
    $('info-close').focus();
    announce('Description for ' + info.title + '.');
  } catch (err) { announce('Could not load video info: ' + err.message, true); }
}

$('info-close').addEventListener('click', closeDialogs);

// ---------- Settings ----------
async function openSettings() {
  try {
    const s = await api('GET', '/api/settings');
    $('proxy-enabled').checked = !!(s.proxy && s.proxy.enabled);
    $('proxy-url').value = (s.proxy && s.proxy.url) || '';
    $('download-dir').value = s.download_directory || '';
    showScreen('screen-settings');
    $('proxy-enabled').focus();
    announce('Settings dialog open.');
  } catch (err) { announce('Could not load settings: ' + err.message, true); }
}

$('settings-form').addEventListener('submit', async e => {
  e.preventDefault();
  try {
    await api('POST', '/api/settings/proxy', { enabled: $('proxy-enabled').checked, url: $('proxy-url').value.trim() });
    await api('POST', '/api/settings/download-dir', { dir: $('download-dir').value.trim() });
    announce('Settings saved.');
    closeDialogs();
  } catch (err) { announce('Could not save settings: ' + err.message, true); }
});

$('settings-close').addEventListener('click', closeDialogs);

$('browse-download-dir').addEventListener('click', () => {
  $('download-dir').focus();
  announce('Type or paste a directory path.');
});

// ---------- Screens ----------
function showScreen(id) {
  ['screen-info', 'screen-settings'].forEach(s => { $(s).hidden = (s !== id); });
}

function closeDialogs() {
  showScreen(null);
  resultsList.focus();
  announce('Closed.');
}

// ---------- Nav buttons ----------
$('nav-home').addEventListener('click',              () => showFavorites());
$('nav-download-video').addEventListener('click',    () => downloadVideoAction());
$('nav-download-audio').addEventListener('click',    () => downloadAudioAction());
$('nav-dl-all-video').addEventListener('click',      () => downloadAllFavorites(false));
$('nav-dl-all-audio').addEventListener('click',      () => downloadAllFavorites(true));
$('nav-favorite').addEventListener('click',          () => addCurrentToFavorites());
$('nav-copy-link').addEventListener('click',         () => copyLink());
$('nav-info').addEventListener('click',              () => viewVideoInfo());
$('nav-settings').addEventListener('click',          () => openSettings());

// ---------- Keyboard shortcuts (match Python version) ----------
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    e.preventDefault();
    if (!$('screen-info').hidden || !$('screen-settings').hidden) closeDialogs();
    else showFavorites();
    return;
  }
  if (e.key === 'p' || e.key === 'P') {
    if (document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
      e.preventDefault(); announcePosition(); return;
    }
  }
  if (!e.ctrlKey) return;
  switch (e.key) {
    case 'D': case 'd':
      e.preventDefault();
      if (e.shiftKey) downloadAudioAction(); else downloadVideoAction();
      break;
    case 'F': case 'f':
      e.preventDefault(); addCurrentToFavorites(); break;
    case 'Enter':
      e.preventDefault(); viewVideoInfo(); break;
    case ' ':
      e.preventDefault(); playpause(); break;
    case 'ArrowRight':
      e.preventDefault(); seek(true); break;
    case 'ArrowLeft':
      e.preventDefault(); seek(false); break;
    case 'ArrowUp':
      e.preventDefault(); adjustVolume(true); break;
    case 'ArrowDown':
      e.preventDefault(); adjustVolume(false); break;
  }
});

// ---------- Boot ----------
init();
`
