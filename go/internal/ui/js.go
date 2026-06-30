package ui

const appJS = `
'use strict';

// All calls go straight through glaze's Bind bridge:
// window.blindtube_<snake_case method>(args...) returns a Promise, backed
// directly by a Go method on Service (internal/ui/service.go). Only
// playback bytes (internal/ui/server.go's /stream/<id>) go over a normal
// HTTP request, since Bind has no streaming-bytes primitive.

function $(id) { return document.getElementById(id); }

function announce(msg, urgent) {
  var el = urgent ? $('alert-live') : $('status-live');
  el.textContent = '';
  window.setTimeout(function () { el.textContent = msg; }, 30);
}

async function call(fnName) {
  const fn = window['blindtube_' + fnName];
  if (!fn) throw new Error('not available: ' + fnName);
  const args = Array.prototype.slice.call(arguments, 1);
  return await fn.apply(null, args);
}

function fmtDuration(sec) {
  sec = Math.max(0, Math.floor(sec || 0));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  const pad = n => String(n).padStart(2, '0');
  return h > 0 ? (h + ':' + pad(m) + ':' + pad(s)) : (m + ':' + pad(s));
}

// ============== App state ==============

let results = [];          // currently shown list (search results or favorites)
let isFavoritesView = false;
let currentVideo = null;   // last VideoInfo from get_video_info
let searchPending = false;
let currentQuery = '';
let loadingMore = false;

const player = $('video-player');
const resultsList = $('results-list');
const searchField = $('search-field');

// ============== Screens ==============

function showScreen(id) {
  ['screen-info', 'screen-settings'].forEach(function (s) {
    $(s).hidden = (s !== id);
  });
}

function closeDialogs() {
  showScreen(null);
  resultsList.focus();
}

// ============== Results list ==============

function renderResults() {
  resultsList.innerHTML = '';
  results.forEach(function (r, i) {
    const li = document.createElement('li');
    li.id = 'result-' + i;
    li.setAttribute('role', 'option');
    li.setAttribute('tabindex', '-1');
    li.dataset.index = String(i);
    const duration = r.duration ? ' (' + fmtDuration(r.duration) + ')' : '';
    li.textContent = r.title + ' by ' + (r.channel || 'Unknown') + duration;
    li.addEventListener('click', function () { selectResult(i, true); });
    li.addEventListener('dblclick', function () { playResult(i); });
    resultsList.appendChild(li);
  });
  if (results.length > 0) selectResult(0, false);
}

function selectResult(index, focus) {
  const items = resultsList.querySelectorAll('li');
  items.forEach(function (li, i) {
    li.setAttribute('aria-selected', i === index ? 'true' : 'false');
  });
  resultsList.setAttribute('aria-activedescendant', 'result-' + index);
  if (focus && items[index]) items[index].scrollIntoView({ block: 'nearest' });
}

function selectedIndex() {
  const active = resultsList.querySelector('li[aria-selected="true"]');
  return active ? parseInt(active.dataset.index, 10) : -1;
}

resultsList.addEventListener('keydown', function (e) {
  const items = resultsList.querySelectorAll('li');
  if (items.length === 0) return;
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
  }
});

// Infinite scroll: load 10 more results once the user is near the bottom
// of the list, mirroring _on_row_changed's "near the end" trigger in the
// Python version.
resultsList.addEventListener('scroll', function () {
  if (isFavoritesView) return;
  const nearBottom = resultsList.scrollTop + resultsList.clientHeight >= resultsList.scrollHeight - 40;
  if (nearBottom) maybeLoadMore();
});

async function maybeLoadMore() {
  if (loadingMore || searchPending || isFavoritesView || !currentQuery) return;
  loadingMore = true;
  try {
    const more = await call('search_more');
    if (more && more.length > 0) {
      results = results.concat(more);
      renderResults();
    }
  } catch (err) {
    console.error(err);
  } finally {
    loadingMore = false;
  }
}

// ============== Search ==============

$('search-form').addEventListener('submit', async function (e) {
  e.preventDefault();
  await searchAction();
});

async function searchAction() {
  const query = searchField.value.trim();
  if (!query) return;
  isFavoritesView = false;
  searchPending = true;
  currentQuery = query;
  announce('Searching for ' + query + '…');
  try {
    results = await call('search', query) || [];
    renderResults();
    announce(results.length + ' results found.');
  } catch (err) {
    announce('Search failed: ' + err.message, true);
  } finally {
    searchPending = false;
  }
}

// ============== Playback ==============

async function playResult(index) {
  const r = results[index];
  if (!r) return;
  await playByURL(r.url, r.title);
}

async function playByURL(urlOrID, knownTitle) {
  announce('Loading ' + (knownTitle || urlOrID) + '…');
  try {
    currentVideo = await call('get_video_info', urlOrID);
    player.src = currentVideo.streamPath;
    $('now-playing').textContent = currentVideo.title + ' — ' + currentVideo.channel;
    await player.play().catch(function () { /* autoplay may need a user gesture; controls remain usable */ });
    announce('Playing ' + currentVideo.title + ' by ' + currentVideo.channel + ', duration ' + fmtDuration(currentVideo.duration) + '.');
  } catch (err) {
    announce('Could not play video: ' + err.message, true);
  }
}

function playpause() {
  if (!player.src) { announce('Nothing is loaded.'); return; }
  if (player.paused) {
    player.play();
    announce('Playing.');
  } else {
    player.pause();
    announce('Paused.');
  }
}

function seek(forward) {
  if (!player.src) return;
  player.currentTime = Math.max(0, Math.min(player.duration || Infinity, player.currentTime + (forward ? 5 : -5)));
  announcePosition();
}

function volume(up) {
  if (!player.src) return;
  player.volume = Math.max(0, Math.min(1, player.volume + (up ? 0.1 : -0.1)));
  announce('Volume ' + Math.round(player.volume * 100) + ' percent.');
}

function announcePosition() {
  if (!player.src) { announce('Nothing is loaded.'); return; }
  announce(fmtDuration(player.currentTime) + ' of ' + fmtDuration(player.duration) + '.');
}

// ============== Downloads ==============

async function downloadVideoAction() {
  const target = currentVideo ? currentVideo.url : (results[selectedIndex()] || {}).url;
  if (!target) { announce('Select a video first.', true); return; }
  announce('Downloading video, this may take a while…');
  try {
    const path = await call('download_video', target);
    announce('Downloaded: ' + path);
  } catch (err) {
    announce('Download failed: ' + err.message, true);
  }
}

async function downloadAudioAction() {
  const target = currentVideo ? currentVideo.url : (results[selectedIndex()] || {}).url;
  if (!target) { announce('Select a video first.', true); return; }
  announce('Downloading audio…');
  try {
    const path = await call('download_audio', target);
    announce('Downloaded: ' + path);
  } catch (err) {
    announce('Download failed: ' + err.message, true);
  }
}

// ============== Favorites ==============

async function addCurrentToFavorites() {
  const r = results[selectedIndex()];
  const target = currentVideo || r;
  if (!target) { announce('Select a video first.', true); return; }
  const info = target.title ? (target.title + ' by ' + target.channel) : (r.title + ' by ' + r.channel);
  const url = target.url;
  try {
    const added = await call('add_favorite', { info: info, url: url });
    announce(added ? 'Added to favorites.' : 'Already in favorites.');
  } catch (err) {
    announce('Could not add favorite: ' + err.message, true);
  }
}

async function showFavorites() {
  searchField.value = '';
  isFavoritesView = true;
  currentQuery = '';
  try {
    const favs = await call('favorites') || [];
    results = favs.map(function (f) {
      return { title: f.info, channel: '', duration: 0, url: f.url };
    });
    renderResults();
    announce(results.length + ' favorites.');
  } catch (err) {
    announce('Could not load favorites: ' + err.message, true);
  }
}

// ============== Video info / description ==============

async function viewVideoInfo() {
  const r = results[selectedIndex()];
  const target = (currentVideo && currentVideo.url === (r || {}).url) ? currentVideo : null;
  const urlOrID = target ? target.url : (r ? r.url : (currentVideo ? currentVideo.url : null));
  if (!urlOrID) { announce('Select a video first.', true); return; }
  try {
    const info = await call('get_video_info', urlOrID);
    currentVideo = info;
    $('info-heading').textContent = info.title;
    $('info-description').value = info.description || '(no description)';
    showScreen('screen-info');
    $('info-close').focus();
    announce('Showing description for ' + info.title + '.');
  } catch (err) {
    announce('Could not load video info: ' + err.message, true);
  }
}

$('info-close').addEventListener('click', closeDialogs);

// ============== Settings ==============

async function openSettings() {
  try {
    const s = await call('get_settings');
    $('proxy-enabled').checked = !!(s.proxy && s.proxy.enabled);
    $('proxy-url').value = (s.proxy && s.proxy.url) || '';
    $('download-dir').value = s.download_directory || '';
    showScreen('screen-settings');
    $('proxy-enabled').focus();
  } catch (err) {
    announce('Could not load settings: ' + err.message, true);
  }
}

$('settings-form').addEventListener('submit', async function (e) {
  e.preventDefault();
  try {
    await call('set_proxy', { enabled: $('proxy-enabled').checked, url: $('proxy-url').value.trim() });
    await call('set_download_directory', $('download-dir').value.trim());
    announce('Settings saved.');
    closeDialogs();
  } catch (err) {
    announce('Could not save settings: ' + err.message, true);
  }
});

$('settings-close').addEventListener('click', closeDialogs);

// browse-download-dir: glaze/WebView has no folder picker primitive
// exposed to JS, so this just focuses the text field for manual entry —
// paste or type a path. (The Python version uses Qt's native folder
// dialog; that native picker isn't available here without extra
// platform-specific glue.)
$('browse-download-dir').addEventListener('click', function () {
  $('download-dir').focus();
  announce('Type or paste the download directory path.');
});

// ============== Menu buttons ==============

$('nav-home').addEventListener('click', function () {
  closeDialogs();
  searchField.focus();
});
$('nav-download-video').addEventListener('click', downloadVideoAction);
$('nav-download-audio').addEventListener('click', downloadAudioAction);
$('nav-favorite').addEventListener('click', addCurrentToFavorites);
$('nav-info').addEventListener('click', viewVideoInfo);
$('nav-settings').addEventListener('click', openSettings);

// ============== Keyboard shortcuts (match the Python version) ==============

document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') {
    e.preventDefault();
    if (!$('screen-info').hidden || !$('screen-settings').hidden) {
      closeDialogs();
    } else {
      showFavorites();
    }
    return;
  }
  if (!e.ctrlKey) return;

  switch (e.key) {
    case 'd':
    case 'D':
      e.preventDefault();
      if (e.shiftKey) downloadAudioAction(); else downloadVideoAction();
      break;
    case 'f':
    case 'F':
      e.preventDefault();
      addCurrentToFavorites();
      break;
    case 'Enter':
      e.preventDefault();
      viewVideoInfo();
      break;
    case ' ':
      e.preventDefault();
      playpause();
      break;
    case 'ArrowRight':
      e.preventDefault();
      seek(true);
      break;
    case 'ArrowLeft':
      e.preventDefault();
      seek(false);
      break;
    case 'ArrowUp':
      e.preventDefault();
      volume(true);
      break;
    case 'ArrowDown':
      e.preventDefault();
      volume(false);
      break;
    case 'p':
    case 'P':
      e.preventDefault();
      announcePosition();
      break;
  }
});

// ============== Init ==============

searchField.focus();
announce('BlindTube ready. Type a search query and press Enter.');
`
